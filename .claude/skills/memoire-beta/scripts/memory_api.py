#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mémoire-beta — API HTTP locale de mémoire auto-organisée (SYF95 / NEXUS).

Trois étages de mémoire :
  - brut/         capture autonome de tout ce qui est utile, vite, sans tri (le filet)
  - en_attente/   candidats analysés et mis en forme, en attente de validation
  - structure/    mémoire validée, dédupliquée, classée par domaine/catégorie
                  (la bibliothèque où l'on vient puiser pour se développer)

Flux : brut  --(analyse)-->  en_attente  --(promotion + dédup)-->  structure

Stockage : fichiers markdown. Zéro dépendance (bibliothèque standard Python).

Démarrage :
    python3 memory_api.py            # http://127.0.0.1:8077, données dans ./memoire_data

Variables d'env optionnelles : MEMOIRE_ROOT, MEMOIRE_HOST, MEMOIRE_PORT.

Endpoints :
    GET  /health
    GET  /domains
    GET  /staging
    POST /note        {content, tag?}                                  -> BRUT
    POST /stage       {content, domain, category, title?, summary?,    -> EN_ATTENTE
                       source?, origin?}
    POST /promote     {id, domain?, category?}                         -> STRUCTURE (dédup)
    POST /clore       {id, raison(doublon|rejete|perime), pointeur?,   -> ARCHIVE (transit)
                       score?, examens?}
    POST /reactiver   {id}                                             -> EN_ATTENTE (retour)
    POST /memorize    {content, domain, category, title?, summary?,    -> STRUCTURE (direct)
                       source?}
    POST /superseder  {path, superseded_par?, date_validite?}          -> supersession (geste humain)
    POST /desuperseder {path}                                          -> annule la supersession
    GET  /recall?query=&domain=&category=&scope=all|brut|en_attente|structure
                 &format=sas   (opt-in : regroupe le classement global par étage,
                                + un 4e bloc `superseded` pour les fiches oubliées)
"""

import os
import re
import math
import json
import datetime
import shutil
import unicodedata
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.environ.get(
    "MEMOIRE_ROOT",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoire_data"),
)
HOST = os.environ.get("MEMOIRE_HOST", "127.0.0.1")
PORT = int(os.environ.get("MEMOIRE_PORT", "8077"))

BRUT = os.path.join(ROOT, "brut")
EN_ATTENTE = os.path.join(ROOT, "en_attente")
STRUCT = os.path.join(ROOT, "structure")
ARCHIVE = os.path.join(ROOT, "archive")

# --- Couche cycle de vie (réglable) ---
ARCHIVE_DAYS = int(os.environ.get("MEMOIRE_ARCHIVE_DAYS", "7"))   # brut ancien -> archive
DELETE_DAYS = int(os.environ.get("MEMOIRE_DELETE_DAYS", "7"))     # archive ancien -> éligible suppression
CAP = int(os.environ.get("MEMOIRE_CAP", "200"))                   # capacité indicative (nb de fiches)
ALERT_RATIO = float(os.environ.get("MEMOIRE_ALERT_RATIO", "0.5")) # seuil d'alerte (0.5 = 50%)


def today():
    return datetime.date.today().strftime("%d/%m/%Y")


def now_hm():
    return datetime.datetime.now().strftime("%H:%M")


def slugify(text):
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "sans-titre"


def _isdir(*parts):
    return os.path.isdir(os.path.join(*parts))


# --------------------------------------------------------------------------- #
# Provenance — champ `source` (+ `verifie`) qui VOYAGE tout le pipeline
# brut -> en_attente -> structure, jamais perdu, jamais blanchi à la promotion.
#   • source  : d'où vient la fiche. 'interne' = produit par le système lui-même
#               (défaut) ; sinon le nom d'une source EXTERNE (allowlist).
#   • verifie : jugement de Kily par fiche (vérité-du-fait). Défaut 'non'
#               (« source fiable, fait non confirmé »). Seul Kily pose 'oui'.
# Stockage machine-lisible SANS toucher la 1re ligne (titre) : marqueurs HTML
# apposés en FIN de fiche pour structure/brut ; pour en_attente, la provenance
# vit déjà dans le bloc meta JSON. Les marqueurs ne sont écrits QUE hors défaut
# (source externe) : une fiche interne reste BYTE-IDENTIQUE à l'existant.
# --------------------------------------------------------------------------- #
SOURCE_INTERNE = "interne"     # sentinelle de provenance interne (EXACT, cf. 98)
VERIFIE_DEFAUT = "non"         # « source fiable, fait non confirmé »

_SOURCE_RE = re.compile(r"<!--\s*source:\s*(.*?)\s*-->")
_VERIFIE_RE = re.compile(r"<!--\s*verifie:\s*(.*?)\s*-->")
_META_RE = re.compile(r"<!-- meta: (.*?) -->", re.S)


def _prov_defaut(source, verifie):
    """True si (source, verifie) sont les valeurs par défaut (interne / non) :
    dans ce cas AUCUN marqueur n'est écrit et la fiche reste byte-identique."""
    return (source or "") in ("", SOURCE_INTERNE) and (verifie or "") in ("", VERIFIE_DEFAUT)


def _marqueurs_provenance(source, verifie):
    """Marqueurs machine (commentaires HTML) apposés en FIN de fiche. Écrits
    seulement hors défaut — la 1re ligne (titre) n'est jamais touchée."""
    return "\n<!-- source: %s -->\n<!-- verifie: %s -->\n" % (
        source or SOURCE_INTERNE, verifie or VERIFIE_DEFAUT)


def _lire_provenance(text, etage=None):
    """Lit (source, verifie) d'une fiche. en_attente : depuis le meta JSON.
    Autres étages : depuis les marqueurs. Absence => défaut (interne / non) :
    tout ce que memory_api (seul écrivain) n'a pas explicitement étiqueté
    externe EST interne par construction."""
    text = text or ""
    if etage == "en_attente":
        m = _META_RE.search(text)
        meta = {}
        if m:
            try:
                meta = json.loads(m.group(1))
            except ValueError:
                meta = {}
        source = (meta.get("source") or "").strip() or SOURCE_INTERNE
        verifie = (meta.get("verifie") or "").strip() or VERIFIE_DEFAUT
        return source, verifie
    ms = _SOURCE_RE.search(text)
    mv = _VERIFIE_RE.search(text)
    source = ms.group(1).strip() if ms else SOURCE_INTERNE
    verifie = mv.group(1).strip() if mv else VERIFIE_DEFAUT
    return source or SOURCE_INTERNE, verifie or VERIFIE_DEFAUT


# --------------------------------------------------------------------------- #
# Supersession — l'ORGANE D'OUBLI v1 (supersession TOTALE). Trois champs de
# provenance qui VOYAGENT brut -> en_attente -> structure exactement comme
# source/verifie, jamais perdus ni blanchis à la promotion :
#   • superseded     : 'oui' si Kily a jugé la fiche fausse ; défaut 'non'.
#   • superseded_par : id/chemin de la fiche successeur, ou texte libre.
#   • date_validite  : date jusqu'à laquelle la fiche était tenue pour vraie.
# Une fiche supersédée CESSE de remonter en tête du recall (sas la route dans un
# 4e bloc, hors des blocs structure/en_attente/brut) SANS être détruite : le
# fichier reste sur disque, réversible via desuperseder. C'est un OUBLI, pas une
# suppression. Comme la provenance : marqueurs HTML en FIN de fiche, écrits
# UNIQUEMENT hors défaut — une fiche superseded='non' reste BYTE-IDENTIQUE.
# GESTE HUMAIN : superseded n'est JAMAIS posé automatiquement (jamais un effet de
# bord d'une écriture) ; seule la fonction superseder() (geste de Kily) le pose.
# --------------------------------------------------------------------------- #
SUPERSEDED_DEFAUT = "non"        # défaut : la fiche est tenue pour valide

_SUPERSEDED_RE = re.compile(r"<!--\s*superseded:\s*(.*?)\s*-->")
_SUPERSEDED_PAR_RE = re.compile(r"<!--\s*superseded_par:\s*(.*?)\s*-->")
_DATE_VALIDITE_RE = re.compile(r"<!--\s*date_validite:\s*(.*?)\s*-->")


def _supersession_defaut(superseded):
    """True si `superseded` est au défaut ('' ou 'non') : dans ce cas AUCUN
    marqueur de supersession n'est écrit et la fiche reste byte-identique."""
    return (superseded or "") in ("", SUPERSEDED_DEFAUT)


def _marqueurs_supersession(superseded, superseded_par, date_validite):
    """Marqueurs machine (commentaires HTML) apposés en FIN de fiche. Écrits
    seulement hors défaut — la 1re ligne (titre) n'est jamais touchée."""
    return "\n<!-- superseded: %s -->\n<!-- superseded_par: %s -->\n<!-- date_validite: %s -->\n" % (
        superseded or SUPERSEDED_DEFAUT, superseded_par or "", date_validite or "")


def _retirer_marqueurs_supersession(text):
    """Retire le bloc de marqueurs de supersession (retour byte-identique à
    l'avant-supersession pour une fiche à marqueurs). Idempotent."""
    return re.sub(
        r"\n<!-- superseded: .*? -->\n<!-- superseded_par: .*? -->\n<!-- date_validite: .*? -->\n",
        "", text or "", flags=re.S)


def _lire_supersession(text, etage=None):
    """Lit (superseded, superseded_par, date_validite) d'une fiche. en_attente :
    depuis le meta JSON. Autres étages : depuis les marqueurs. Absence => défaut
    (non / vide / vide) : une fiche non explicitement supersédée EST valide."""
    text = text or ""
    if etage == "en_attente":
        m = _META_RE.search(text)
        meta = {}
        if m:
            try:
                meta = json.loads(m.group(1))
            except ValueError:
                meta = {}
        superseded = (meta.get("superseded") or "").strip() or SUPERSEDED_DEFAUT
        superseded_par = (meta.get("superseded_par") or "").strip()
        date_validite = (meta.get("date_validite") or "").strip()
        return superseded, superseded_par, date_validite
    ms = _SUPERSEDED_RE.search(text)
    mp = _SUPERSEDED_PAR_RE.search(text)
    md = _DATE_VALIDITE_RE.search(text)
    superseded = (ms.group(1).strip() if ms else SUPERSEDED_DEFAUT) or SUPERSEDED_DEFAUT
    superseded_par = mp.group(1).strip() if mp else ""
    date_validite = md.group(1).strip() if md else ""
    return superseded, superseded_par, date_validite


# --------------------------------------------------------------------------- #
# Étage 1 — BRUT : capture autonome, append-only, un journal par jour
# --------------------------------------------------------------------------- #
def add_note(data):
    content = (data.get("content") or "").strip()
    tag = (data.get("tag") or "").strip()
    source = (data.get("source") or "").strip()
    verifie = (data.get("verifie") or "").strip()
    superseded = (data.get("superseded") or "").strip()
    superseded_par = (data.get("superseded_par") or "").strip()
    date_validite = (data.get("date_validite") or "").strip()
    os.makedirs(BRUT, exist_ok=True)
    day = datetime.date.today().strftime("%Y-%m-%d")
    file_path = os.path.join(BRUT, day + ".md")
    new_file = not os.path.exists(file_path)
    entry = "\n## %s%s\n%s\n" % (now_hm(), (" · #" + slugify(tag)) if tag else "", content)
    # La provenance VOYAGE dès le brut : marqueur écrit SEULEMENT hors défaut
    # (source externe), donc la capture interne reste byte-identique à l'existant.
    if not _prov_defaut(source, verifie):
        entry += _marqueurs_provenance(source, verifie)
    # La supersession voyage aussi dès le brut ; marqueur SEULEMENT hors défaut.
    if not _supersession_defaut(superseded):
        entry += _marqueurs_supersession(superseded, superseded_par, date_validite)
    with open(file_path, "a", encoding="utf-8") as f:
        if new_file:
            f.write("# Notes brutes — %s\n" % today())
        f.write(entry)
    return {
        "ok": True,
        "etage": "brut",
        "path": os.path.relpath(file_path, ROOT),
        "source": source or SOURCE_INTERNE,
        "rappel": "Lance la passe d'analyse pour promouvoir le brut utile vers en_attente.",
    }


# --------------------------------------------------------------------------- #
# Étage 3 — STRUCTURE : écriture validée + dédup + index auto
# --------------------------------------------------------------------------- #
def update_indexes():
    if not os.path.isdir(STRUCT):
        return
    domains = sorted(d for d in os.listdir(STRUCT) if _isdir(STRUCT, d))
    root_lines = ["# Index de la mémoire structurée\n", "> Mis à jour le %s\n\n" % today()]
    if not domains:
        root_lines.append("_(vide pour l'instant)_\n")
    for d in domains:
        cats = sorted(c for c in os.listdir(os.path.join(STRUCT, d)) if _isdir(STRUCT, d, c))
        n = 0
        dom_lines = ["# Domaine : %s\n" % d, "> Mis à jour le %s\n\n" % today()]
        for c in cats:
            files = sorted(
                f for f in os.listdir(os.path.join(STRUCT, d, c))
                if f.endswith(".md") and f != "_index.md"
            )
            n += len(files)
            dom_lines.append("## %s\n" % c)
            for fl in files:
                dom_lines.append("- %s\n" % fl[:-3])
            dom_lines.append("\n")
        with open(os.path.join(STRUCT, d, "_index.md"), "w", encoding="utf-8") as f:
            f.write("".join(dom_lines))
        root_lines.append(
            "- **%s** (%d fiche%s) : %s\n"
            % (d, n, "s" if n != 1 else "", ", ".join(cats) if cats else "—")
        )
    with open(os.path.join(STRUCT, "_index.md"), "w", encoding="utf-8") as f:
        f.write("".join(root_lines))


def _write_struct(domain, category, title, content, summary="", source="", verifie="",
                  superseded="", superseded_par="", date_validite=""):
    """Écrit une fiche structurée. Si elle existe : fusion (section datée), pas de doublon.

    `source`/`verifie` = provenance qui VOYAGE depuis en_attente (jamais blanchie
    à la promotion). Un marqueur machine est apposé en FIN de fiche UNIQUEMENT
    hors défaut (source externe) : les fiches internes restent byte-identiques.
    `superseded`/`superseded_par`/`date_validite` VOYAGENT de la même façon : le
    marqueur de supersession n'est écrit qu'hors défaut (superseded='oui'), donc
    une fiche non supersédée reste byte-identique à l'existant."""
    domain = slugify(domain or "general")
    category = slugify(category or "divers")
    title = (title or content[:60] or "sans-titre").strip()
    slug = slugify(title)
    dir_path = os.path.join(STRUCT, domain, category)
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, slug + ".md")
    created = not os.path.exists(file_path)
    marqueurs = "" if _prov_defaut(source, verifie) else _marqueurs_provenance(source, verifie)
    marqueurs_sup = ("" if _supersession_defaut(superseded)
                     else _marqueurs_supersession(superseded, superseded_par, date_validite))

    if created:
        parts = ["# %s — domaine: %s / catégorie: %s\n" % (title, domain, category)]
        parts.append("> Créé le %s · Dernière mise à jour le %s\n\n" % (today(), today()))
        if summary:
            parts.append("## En bref\n%s\n\n" % summary)
        parts.append("## Détail\n%s\n" % content)
        if source:
            parts.append("\n## Source\n%s\n" % source)
        parts.append(marqueurs)
        parts.append(marqueurs_sup)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("".join(parts))
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            existing = f.read()
        existing = re.sub(
            r"Dernière mise à jour le [^\n]*",
            "Dernière mise à jour le %s" % today(), existing, count=1,
        )
        add = ["\n\n## Ajout du %s\n" % today()]
        if summary:
            add.append("_%s_\n\n" % summary)
        add.append("%s\n" % content)
        if source:
            add.append("\nSource : %s\n" % source)
        # La provenance de la fiche fusionnée n'est (ré)apposée que si elle n'y
        # est pas déjà : le champ VOYAGE sans jamais être blanchi ni dupliqué.
        if marqueurs and not _SOURCE_RE.search(existing):
            add.append(marqueurs)
        # Idem pour la supersession : (ré)apposée seulement si absente.
        if marqueurs_sup and not _SUPERSEDED_RE.search(existing):
            add.append(marqueurs_sup)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(existing + "".join(add))

    update_indexes()
    return {
        "ok": True, "etage": "structure",
        "created": created,
        "action": "création" if created else "fusion",
        "doublon_evite": (not created),
        "domain": domain, "category": category, "title": title,
        "path": os.path.relpath(file_path, ROOT),
    }


def memorize(data):
    return _write_struct(
        data.get("domain"), data.get("category"), data.get("title"),
        (data.get("content") or "").strip(),
        (data.get("summary") or "").strip(), (data.get("source") or "").strip(),
        (data.get("verifie") or "").strip(),
        (data.get("superseded") or "").strip(),
        (data.get("superseded_par") or "").strip(),
        (data.get("date_validite") or "").strip(),
    )


# --------------------------------------------------------------------------- #
# Étage 2 — EN_ATTENTE : candidats analysés, en attente de validation
# --------------------------------------------------------------------------- #
def stage(data):
    domain = slugify(data.get("domain") or "general")
    category = slugify(data.get("category") or "divers")
    content = (data.get("content") or "").strip()
    title = (data.get("title") or content[:60] or "sans-titre").strip()
    summary = (data.get("summary") or "").strip()
    source = (data.get("source") or "").strip()
    verifie = (data.get("verifie") or "").strip()
    superseded = (data.get("superseded") or "").strip()
    superseded_par = (data.get("superseded_par") or "").strip()
    date_validite = (data.get("date_validite") or "").strip()
    origin = (data.get("origin") or "").strip()
    os.makedirs(EN_ATTENTE, exist_ok=True)

    base = datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + slugify(title)[:40]
    sid, i = base, 1
    while os.path.exists(os.path.join(EN_ATTENTE, sid + ".md")):
        i += 1
        sid = "%s-%d" % (base, i)

    # La supersession VOYAGE dans le meta (comme source/verifie) pour survivre à
    # la promotion. Défaut 'non' / vide : une fiche non supersédée reste neutre.
    meta = {"domain": domain, "category": category, "title": title,
            "summary": summary, "source": source, "verifie": verifie,
            "superseded": superseded, "superseded_par": superseded_par,
            "date_validite": date_validite,
            "origin": origin, "staged": today(), "content": content}
    body = ["<!-- meta: %s -->\n" % json.dumps(meta, ensure_ascii=False)]
    body.append("# (en attente) %s — %s / %s\n" % (title, domain, category))
    if summary:
        body.append("_%s_\n\n" % summary)
    body.append(content + "\n")
    if source:
        body.append("\nSource : %s\n" % source)
    if origin:
        body.append("\n_Origine : %s_\n" % origin)
    with open(os.path.join(EN_ATTENTE, sid + ".md"), "w", encoding="utf-8") as f:
        f.write("".join(body))
    return {"ok": True, "etage": "en_attente", "id": sid,
            "domain": domain, "category": category, "title": title}


def _read_meta(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"<!-- meta: (.*?) -->", text, re.S)
    return json.loads(m.group(1)) if m else {}


def list_staging():
    items = []
    if os.path.isdir(EN_ATTENTE):
        for fl in sorted(os.listdir(EN_ATTENTE)):
            if not fl.endswith(".md"):
                continue
            meta = _read_meta(os.path.join(EN_ATTENTE, fl))
            items.append({"id": fl[:-3], "domain": meta.get("domain"),
                          "category": meta.get("category"), "title": meta.get("title")})
    return {"ok": True, "count": len(items), "items": items}


def promote(data):
    sid = (data.get("id") or "").strip()
    if not sid:
        return {"error": "champ 'id' requis"}
    path = os.path.join(EN_ATTENTE, sid + ".md")
    if not os.path.exists(path):
        return {"error": "candidat introuvable: %s" % sid}
    meta = _read_meta(path)
    domain = data.get("domain") or meta.get("domain")
    category = data.get("category") or meta.get("category")
    res = _write_struct(domain, category, meta.get("title"),
                        meta.get("content", ""), meta.get("summary", ""),
                        meta.get("source", ""), meta.get("verifie", ""),
                        meta.get("superseded", ""), meta.get("superseded_par", ""),
                        meta.get("date_validite", ""))
    os.remove(path)  # validé -> sort de la file d'attente
    res["promu_depuis"] = sid
    return res


# --------------------------------------------------------------------------- #
# Cycle de vie de la file en_attente — CLORE / REACTIVER
# --------------------------------------------------------------------------- #
# en_attente est une file de TRANSIT, pas un cimetière. Chaque candidat a quatre
# sorties, toutes tracées, AUCUNE destructive :
#   - promu           (promote — écrit en structure, byte-identique) ;
#   - doublon         (proposition machine + confirmation HUMAINE) ;
#   - rejeté          (décision active du superviseur) ;
#   - périmé          (RÉSIDU du triage : N examens journalisés sans décision).
# clore() déplace en_attente -> archive/en_attente/ (JAMAIS de suppression) et
# journalise l'événement (append-only). reactiver() fait le retour inverse et
# journalise aussi. memory_api est le SEUL écrivain de en_attente/ et archive/.
RAISONS_CLOTURE = ("doublon", "rejete", "perime")


def now_iso():
    """Horodatage ISO à la microseconde : ordre strict entre opérations
    séquentielles (jamais de collision entre deux écritures du journal)."""
    return datetime.datetime.now().isoformat(timespec="microseconds")


def _archive_attente():
    # Recalculé depuis ARCHIVE à chaque appel : suit une redirection de racine
    # (les tests réécrivent ARCHIVE après import).
    return os.path.join(ARCHIVE, "en_attente")


def _cloture_journal():
    return os.path.join(ARCHIVE, "clotures.jsonl")


def _append_cloture(entry):
    """Ajoute une ligne au journal de clôture (append-only, jamais réécrit)."""
    os.makedirs(os.path.dirname(_cloture_journal()), exist_ok=True)
    with open(_cloture_journal(), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def lire_clotures():
    """Lecture DÉFENSIVE du journal de clôture (ordre d'écriture préservé).
    Fichier absent → []. Lignes corrompues ignorées. Ne lève jamais."""
    out = []
    path = _cloture_journal()
    if not os.path.exists(path):
        return out
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return out
    return out


def _bump_reactivations(path):
    """Incrémente meta['reactivations'] dans le fichier (nouvelle ÉPOQUE d'entrée
    en file). La fenêtre d'examens du candidat se compte dans cette époque :
    un réactivé repart donc à zéro. Renvoie la nouvelle valeur d'époque."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"<!-- meta: (.*?) -->", text, re.S)
    meta = json.loads(m.group(1)) if m else {}
    meta["reactivations"] = int(meta.get("reactivations", 0)) + 1
    remplacement = "<!-- meta: %s -->" % json.dumps(meta, ensure_ascii=False)
    if m:
        text = text[:m.start()] + remplacement + text[m.end():]
    else:
        text = remplacement + "\n" + text
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return meta["reactivations"]


def clore(sid, raison, pointeur=None, score=None, examens=None):
    """Clôt un candidat en_attente : le DÉPLACE vers archive/en_attente/ (JAMAIS
    de suppression) et journalise (id, raison, pointeur, score, examens, date).

    raison ∈ {doublon, rejete, perime}. clore sur un id ABSENT = NO-OP TRACÉ :
    jamais d'erreur, jamais d'action sur archive, mais l'événement est journalisé
    (marqué noop) pour que la trace reste complète."""
    sid = (sid or "").strip()
    raison = (raison or "").strip()
    if not sid:
        return {"error": "champ 'id' requis"}
    if raison not in RAISONS_CLOTURE:
        return {"error": "raison invalide: %s (attendu %s)"
                % (raison, "|".join(RAISONS_CLOTURE))}
    src = os.path.join(EN_ATTENTE, sid + ".md")
    entry = {"id": sid, "event": "clore", "raison": raison, "pointeur": pointeur,
             "score": score, "examens": examens, "date": now_iso()}
    if not os.path.exists(src):
        entry["noop"] = True
        _append_cloture(entry)
        return {"ok": True, "noop": True, "id": sid, "raison": raison,
                "message": "id absent de en_attente : clôture no-op tracée"}
    dest_dir = _archive_attente()
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, sid + ".md")
    shutil.move(src, dest)                    # déplacement, JAMAIS suppression
    entry["noop"] = False
    entry["archive"] = os.path.relpath(dest, ROOT)
    _append_cloture(entry)
    return {"ok": True, "id": sid, "raison": raison,
            "archive": os.path.relpath(dest, ROOT)}


def reactiver(sid):
    """Réactive un candidat archivé : le déplace archive/en_attente/ -> en_attente/
    et journalise. Le compteur d'examens REPART À ZÉRO (l'époque d'entrée est
    incrémentée). reactiver sur un id absent = NO-OP TRACÉ (jamais d'erreur)."""
    sid = (sid or "").strip()
    if not sid:
        return {"error": "champ 'id' requis"}
    src = os.path.join(_archive_attente(), sid + ".md")
    entry = {"id": sid, "event": "reactiver", "date": now_iso()}
    if not os.path.exists(src):
        entry["noop"] = True
        _append_cloture(entry)
        return {"ok": True, "noop": True, "id": sid,
                "message": "id absent de l'archive : réactivation no-op tracée"}
    os.makedirs(EN_ATTENTE, exist_ok=True)
    dest = os.path.join(EN_ATTENTE, sid + ".md")
    epoch = _bump_reactivations(src)          # nouvelle époque AVANT le déplacement
    shutil.move(src, dest)
    entry["noop"] = False
    entry["reactivations"] = epoch
    _append_cloture(entry)
    return {"ok": True, "id": sid, "reactivations": epoch,
            "en_attente": os.path.relpath(dest, ROOT)}


# --------------------------------------------------------------------------- #
# Supersession — GESTE HUMAIN (organe d'oubli v1). NON destructif, RÉVERSIBLE.
# --------------------------------------------------------------------------- #
def _chemin_memoire(rel):
    """Résout un chemin relatif SOUS ROOT (garde anti-traversée). Renvoie le
    chemin absolu ou None si hors mémoire."""
    racine = os.path.normpath(ROOT)
    abspath = os.path.normpath(os.path.join(racine, rel))
    if abspath != racine and not abspath.startswith(racine + os.sep):
        return None
    return abspath


def _maj_meta_supersession(text, superseded, superseded_par, date_validite):
    """Met à jour les champs de supersession dans le meta JSON (en_attente)."""
    m = _META_RE.search(text)
    meta = {}
    if m:
        try:
            meta = json.loads(m.group(1))
        except ValueError:
            meta = {}
    meta["superseded"] = superseded
    meta["superseded_par"] = superseded_par
    meta["date_validite"] = date_validite
    remplacement = "<!-- meta: %s -->" % json.dumps(meta, ensure_ascii=False)
    if m:
        return text[:m.start()] + remplacement + text[m.end():]
    return remplacement + "\n" + text


def superseder(data):
    """GESTE HUMAIN — marque une fiche EXISTANTE comme supersédée (Kily l'a jugée
    fausse). NON destructif : le contenu est PRÉSERVÉ, seuls les marqueurs de
    supersession sont (ré)apposés en fin de fiche. RÉVERSIBLE via desuperseder.
    JAMAIS appelé automatiquement : l'oubli est une décision humaine, pas un
    effet de bord d'une écriture. La fiche cesse de remonter en tête du recall
    (sas la route dans le bloc `superseded`) mais reste sur disque et retrouvable."""
    rel = (data.get("path") or "").strip()
    if not rel:
        return {"error": "champ 'path' requis"}
    superseded_par = (data.get("superseded_par") or "").strip()
    date_validite = (data.get("date_validite") or "").strip()
    abspath = _chemin_memoire(rel)
    if abspath is None:
        return {"error": "chemin hors mémoire: %s" % rel}
    if not os.path.exists(abspath):
        return {"error": "fiche introuvable: %s" % rel}
    with open(abspath, "r", encoding="utf-8") as f:
        text = f.read()
    if _META_RE.search(text):
        text = _maj_meta_supersession(text, "oui", superseded_par, date_validite)
    else:
        text = _retirer_marqueurs_supersession(text)   # idempotent : re-supersede
        text += _marqueurs_supersession("oui", superseded_par, date_validite)
    with open(abspath, "w", encoding="utf-8") as f:
        f.write(text)
    return {"ok": True, "path": rel, "superseded": "oui",
            "superseded_par": superseded_par, "date_validite": date_validite,
            "reversible": True}


def desuperseder(data):
    """Inverse de superseder — RÉVERSIBILITÉ de l'oubli : la fiche redevient
    valide (superseded='non'). Sur une fiche à marqueurs, le retour est
    byte-identique à l'avant-supersession (les marqueurs sont retirés)."""
    rel = (data.get("path") or "").strip()
    if not rel:
        return {"error": "champ 'path' requis"}
    abspath = _chemin_memoire(rel)
    if abspath is None:
        return {"error": "chemin hors mémoire: %s" % rel}
    if not os.path.exists(abspath):
        return {"error": "fiche introuvable: %s" % rel}
    with open(abspath, "r", encoding="utf-8") as f:
        text = f.read()
    if _META_RE.search(text):
        text = _maj_meta_supersession(text, SUPERSEDED_DEFAUT, "", "")
    else:
        text = _retirer_marqueurs_supersession(text)
    with open(abspath, "w", encoding="utf-8") as f:
        f.write(text)
    return {"ok": True, "path": rel, "superseded": "non"}


# --------------------------------------------------------------------------- #
# GET /domains et /recall
# --------------------------------------------------------------------------- #
def get_domains():
    tree = {}
    if os.path.isdir(STRUCT):
        for d in sorted(os.listdir(STRUCT)):
            if not _isdir(STRUCT, d):
                continue
            tree[d] = {}
            for c in sorted(os.listdir(os.path.join(STRUCT, d))):
                if not _isdir(STRUCT, d, c):
                    continue
                tree[d][c] = sorted(
                    f[:-3] for f in os.listdir(os.path.join(STRUCT, d, c))
                    if f.endswith(".md") and f != "_index.md"
                )
    return {"root": ROOT, "domains": tree}


def _scan(base, query, etage, fdomain=None, fcategory=None):
    out = []
    if not os.path.isdir(base):
        return out
    for dirpath, _dirs, files in os.walk(base):
        for fl in sorted(files):
            if not fl.endswith(".md") or fl == "_index.md":
                continue
            rel = os.path.relpath(os.path.join(dirpath, fl), ROOT)
            parts = rel.split(os.sep)
            domain = parts[1] if etage == "structure" and len(parts) >= 3 else None
            category = parts[2] if etage == "structure" and len(parts) >= 4 else None
            if fdomain and domain != fdomain:
                continue
            if fcategory and category != fcategory:
                continue
            with open(os.path.join(dirpath, fl), "r", encoding="utf-8") as f:
                text = f.read()
            # Plus de filtre sous-chaîne ici : on collecte tous les candidats
            # (texte + nom de fiche minusculisés dans « _search ») et c'est le
            # classement pertinence(IDF) × force, dans recall(), qui trie et
            # écarte les fiches sans aucun token de la requête.
            # La provenance est LUE ici (jamais dans _search : elle n'influence
            # pas le classement) et n'apparaît QUE dans le format sas.
            source, verifie = _lire_provenance(text, etage)
            superseded, superseded_par, date_validite = _lire_supersession(text, etage)
            out.append({"etage": etage, "domain": domain, "category": category,
                        "file": fl, "path": rel, "excerpt": text[:400],
                        "source": source, "verifie": verifie,
                        "superseded": superseded, "superseded_par": superseded_par,
                        "date_validite": date_validite,
                        "_search": (text + " " + fl).lower()})
    return out


# --------------------------------------------------------------------------- #
# RÉTRO-TAG — memory_api est le SEUL écrivain : stampe la provenance des fiches
# structure existantes qui n'en portent pas encore (baseline 'interne'). Le
# défaut de LECTURE est déjà 'interne' ; le rétro-tag le rend EXPLICITE et
# auditable (marqueur écrit), single-writer. Idempotent : une fiche déjà
# étiquetée n'est jamais réécrite.
# --------------------------------------------------------------------------- #
def retro_tag_source(source=SOURCE_INTERNE, verifie=VERIFIE_DEFAUT):
    """Appose le marqueur de provenance sur chaque fiche structure non encore
    étiquetée. Renvoie {total, etiquetees, deja} — baseline = total/total."""
    total = etiquetees = deja = 0
    if os.path.isdir(STRUCT):
        for dirpath, _dirs, files in os.walk(STRUCT):
            for fl in sorted(files):
                if not fl.endswith(".md") or fl == "_index.md":
                    continue
                total += 1
                p = os.path.join(dirpath, fl)
                with open(p, "r", encoding="utf-8") as f:
                    text = f.read()
                if _SOURCE_RE.search(text):
                    deja += 1
                    continue
                with open(p, "a", encoding="utf-8") as f:
                    f.write(_marqueurs_provenance(source, verifie))
                etiquetees += 1
    return {"ok": True, "total": total, "etiquetees": etiquetees, "deja": deja}


# --------------------------------------------------------------------------- #
# Classement pertinence(IDF) × force
# --------------------------------------------------------------------------- #
_TOKEN_RE = re.compile(r"[0-9a-zà-ÿ_]+", re.IGNORECASE)


def _tokens(s):
    return _TOKEN_RE.findall((s or "").lower())


def load_forces():
    """Lit ROOT/forces.json = {fiche: multiplicateur}. Renvoie {} si absent ou
    illisible. Les valeurs sont coercées en float, les clés en str."""
    path = os.path.join(ROOT, "forces.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            out = {}
            for k, v in data.items():
                try:
                    out[str(k)] = float(v)
                except (TypeError, ValueError):
                    continue
            return out
    except (OSError, ValueError):
        pass
    return {}


def _force_for(forces, fl, rel):
    """Multiplicateur d'une fiche : clé = nom complet, radical (sans .md) ou
    chemin relatif. Défaut 1.0 si absente de forces.json."""
    stem = fl[:-3] if fl.endswith(".md") else fl
    for key in (fl, stem, rel):
        if key in forces:
            return forces[key]
    return 1.0


def idf_sur_corpus(tokens, corpus_token_sets):
    """IDF lissé de `tokens` sur un corpus, en fonction PURE et réutilisable.

    `corpus_token_sets` : itérable de conteneurs de tokens — un par document du
    corpus (idéalement des ensembles). N = nombre de documents ; pour chaque
    token DISTINCT, df = nombre de documents le contenant, et
    IDF = log((N+1)/(df+1)) + 1 — la MÊME formule lissée qu'historiquement :
    ~1 pour un token présent partout (aucun gagnant confiant), élevé pour un
    token rare/distinctif. Corpus vide → N = 1 (bornes identiques à l'ancien
    code, qui prenait `len(cands) or 1`).

    Renvoie {token: idf}. Extraite telle quelle de rank_candidates, qui l'appelle
    désormais : comportement PROUVÉ inchangé (mêmes entrées → mêmes sorties)."""
    corpus = list(corpus_token_sets)
    n = len(corpus) or 1
    idf = {}
    for t in dict.fromkeys(tokens):                        # dédup, ordre stable
        df = sum(1 for toks in corpus if t in toks)
        idf[t] = math.log((n + 1) / (df + 1)) + 1.0
    return idf


def rank_candidates(query, cands, forces=None):
    """Classe des candidats (chacun portant la clé « _search ») par
    pertinence(IDF) × force, sans les modifier en place.

    Pertinence = somme des IDF des tokens *distincts* de la requête présents
    dans la fiche (présence binaire : le bourrage de mots-clés n'élève pas le
    score). IDF lissé = log((N+1)/(df+1)) + 1 : ~1 pour un token présent
    partout (aucun gagnant confiant), élevé pour un token rare/distinctif.
    Le calcul de l'IDF est délégué à `idf_sur_corpus` (fonction pure) — même
    formule, comportement inchangé.

    Renvoie une nouvelle liste triée par score décroissant (départage stable
    par chemin puis nom), chaque élément enrichi de « _relevance », « _force »
    et « _score »."""
    if forces is None:
        forces = load_forces()
    qtokens = list(dict.fromkeys(_tokens(query)))          # dédup, ordre stable
    cand_tokens = [set(_tokens(c.get("_search", ""))) for c in cands]
    idf = idf_sur_corpus(qtokens, cand_tokens)
    ranked = []
    for c, toks in zip(cands, cand_tokens):
        rel = sum(idf[t] for t in qtokens if t in toks)
        force = _force_for(forces, c.get("file", ""), c.get("path", ""))
        item = dict(c)
        item["_relevance"] = rel
        item["_force"] = force
        item["_score"] = rel * force
        ranked.append(item)
    ranked.sort(key=lambda x: (-x["_score"], x.get("path", ""), x.get("file", "")))
    return ranked


def _strip_internal(item):
    """Ne garde que la forme de retour publique (etage/domain/category/...)."""
    return {"etage": item["etage"], "domain": item["domain"],
            "category": item["category"], "file": item["file"],
            "path": item["path"], "excerpt": item["excerpt"]}


# --------------------------------------------------------------------------- #
# SAS mémoire (opt-in format=sas) — étiqueter, jamais cacher ni décoter
# --------------------------------------------------------------------------- #
# Le sas ne recalcule RIEN et ne reclasse RIEN : il prend le classement GLOBAL
# (issu de l'unique appel à rank_candidates dans recall) et le REGROUPE en blocs
# étiquetés — structure (validé) / en_attente (analysé-non-validé) / brut
# (non-trié) — chacun dans l'ordre du classement global. Il dit au consommateur
# ce qu'il regarde ; il ne décide pas à sa place.
#
# ORGANE D'OUBLI : un 4e bloc `superseded` recueille les fiches jugées fausses
# (superseded='oui'), quel que soit leur étage de STOCKAGE. Le routage se fait sur
# superseded AVANT l'étage : une fiche supersédée sort donc de structure/en_attente
# /brut et n'est JAMAIS candidate à `struct_top` (ni à l'alerte). Elle cesse ainsi
# de remonter en tête du recall sans être détruite : elle reste dans le bloc
# `superseded`, retrouvable.
_SAS_ETAGES = ("structure", "en_attente", "brut")   # étages de STOCKAGE (routage par défaut)
_SAS_SUPERSEDED = "superseded"                       # 4e bloc : fiches oubliées (hors étage)
_SAS_BLOCS = _SAS_ETAGES + (_SAS_SUPERSEDED,)        # ordre des blocs dans la réponse


def _sas_candidat(item):
    """Forme SAS d'un candidat : la forme publique + les scores du classement
    global, NON strippés (déjà calculés par rank_candidates : zéro compute
    nouveau). L'étage est toujours présent — le consommateur DOIT router dessus."""
    return {
        "etage": item["etage"], "domain": item["domain"],
        "category": item["category"], "file": item["file"],
        "path": item["path"], "excerpt": item["excerpt"],
        # ÉTIQUETAGE (extension du contrat sas) : la provenance est exposée sur
        # CHAQUE candidat — le sas étiquette, il ne décote ni ne cache. La
        # couverture d'étiquetage est de 100 % (tout candidat porte source+verifie).
        "source": item.get("source", SOURCE_INTERNE),
        "verifie": item.get("verifie", VERIFIE_DEFAUT),
        # Supersession exposée de même : le consommateur voit quelle fiche a été
        # oubliée, par quoi elle est remplacée et jusqu'à quand elle valait.
        "superseded": item.get("superseded", SUPERSEDED_DEFAUT),
        "superseded_par": item.get("superseded_par", ""),
        "date_validite": item.get("date_validite", ""),
        "_relevance": item.get("_relevance", 0.0),
        "_force": item.get("_force", 1.0),
        "_score": item.get("_score", 0.0),
    }


def _format_sas(scope, results):
    """Présentation SAS de `results` (le classement GLOBAL déjà trié et filtré).

    REGROUPEMENT à la présentation seulement : trois blocs étiquetés, jamais
    fondus, chacun dans l'ordre du classement global. Les blocs sont des
    sous-suites du défaut : les scores exposés sont ceux du classement global.

    alerte : null si le meilleur candidat structure (validé) tient la tête —
    égalité inter-étages comprise : le validé gagne. Sinon une liste d'au plus
    une entrée PAR étage hors-structure dont le meilleur candidat bat
    STRICTEMENT le meilleur structure. Chaque entrée = {etage, path, ecart} avec
    ecart = score_étage − score_du_meilleur_structure, ou null si AUCUN structure
    ne matche (pas de sentinelle, pas de seuil).

    Une fiche superseded='oui' est routée dans le bloc `superseded` AVANT tout
    étage : elle sort donc des blocs structure/en_attente/brut et ne peut jamais
    être `struct_top` ni figurer dans l'alerte. Le bloc `superseded` n'entre pas
    dans l'arbitrage de l'alerte (une fiche oubliée n'a plus à concourir)."""
    blocs = {b: [] for b in _SAS_BLOCS}
    for r in results:
        # ROUTAGE : la supersession prime sur l'étage de stockage.
        if r.get("superseded") == "oui":
            blocs[_SAS_SUPERSEDED].append(_sas_candidat(r))
            continue
        et = r.get("etage")
        if et in _SAS_ETAGES:
            blocs[et].append(_sas_candidat(r))

    # results est en ordre de classement global : le 1er de chaque bloc est le
    # meilleur de son étage. Une supersédée est déjà HORS de structure, donc
    # jamais struct_top (garantie du routage ci-dessus).
    struct_top = blocs["structure"][0]["_score"] if blocs["structure"] else None
    alerte = []
    for et in ("en_attente", "brut"):
        if not blocs[et]:
            continue
        meilleur = blocs[et][0]["_score"]
        if struct_top is None:
            alerte.append({"etage": et, "path": blocs[et][0]["path"], "ecart": None})
        elif meilleur > struct_top:  # STRICTEMENT : égalité => le validé garde la tête
            alerte.append({"etage": et, "path": blocs[et][0]["path"],
                           "ecart": meilleur - struct_top})

    count = sum(len(blocs[b]) for b in _SAS_BLOCS)
    return {"ok": True, "scope": scope, "format": "sas", "count": count,
            "blocs": blocs, "alerte": alerte or None}


def recall(params):
    query = (params.get("query", [""])[0] or "").lower()
    scope = (params.get("scope", ["all"])[0] or "all").lower()
    fmt = (params.get("format", [""])[0] or "").lower()
    fdomain = params.get("domain", [None])[0]
    fcategory = params.get("category", [None])[0]
    fdomain = slugify(fdomain) if fdomain else None
    fcategory = slugify(fcategory) if fcategory else None
    results = []
    if scope in ("all", "structure"):
        results += _scan(STRUCT, query, "structure", fdomain, fcategory)
    if scope in ("all", "en_attente") and not fdomain and not fcategory:
        results += _scan(EN_ATTENTE, query, "en_attente")
    if scope in ("all", "brut") and not fdomain and not fcategory:
        results += _scan(BRUT, query, "brut")
    if scope == "archive" and not fdomain and not fcategory:
        results += _scan(ARCHIVE, query, "archive")
    if query:
        ranked = rank_candidates(query, results)
        results = [r for r in ranked if r["_relevance"] > 0]
    if fmt == "sas":
        return _format_sas(scope, results)
    out = [_strip_internal(r) for r in results]
    return {"ok": True, "scope": scope, "count": len(out), "results": out}


# --------------------------------------------------------------------------- #
# Couche cycle de vie — jauge/alerte, archivage, suppression manuelle
# --------------------------------------------------------------------------- #
def _age_days(path):
    return (datetime.datetime.now().timestamp() - os.path.getmtime(path)) / 86400.0


def _count_md(base, skip_index=True):
    n = 0
    if os.path.isdir(base):
        for _dp, _dirs, files in os.walk(base):
            for f in files:
                if f.endswith(".md") and not (skip_index and f == "_index.md"):
                    n += 1
    return n


def stats():
    n_struct = _count_md(STRUCT)
    ratio = round(n_struct / CAP, 3) if CAP else 0.0
    alerte = ratio >= ALERT_RATIO
    return {
        "ok": True,
        "structure_fiches": n_struct,
        "cap": CAP,
        "remplissage": ratio,
        "alerte": alerte,
        "message": ("Seuil atteint (~%d%%) : lance une passe de traitement / archivage."
                    % int(ratio * 100)) if alerte else "OK",
        "brut_fichiers": _count_md(BRUT),
        "en_attente": _count_md(EN_ATTENTE),
        "archive": _count_md(ARCHIVE),
    }


def maintenance(apply=False, purge=False):
    """Sûr par défaut : dry-run. apply=True archive le brut ancien.
    purge=True supprime SEULEMENT ce qui est déjà éligible dans archive (action manuelle).
    Ne touche jamais à structure/. Ne supprime jamais automatiquement."""
    rep = {
        "ok": True, "mode": "dry-run" if not (apply or purge) else "apply",
        "archive_jours": ARCHIVE_DAYS, "suppression_jours": DELETE_DAYS,
        "a_archiver": [], "archives": [], "backlog_en_attente": [],
        "a_supprimer": [], "supprimes": [],
    }
    os.makedirs(ARCHIVE, exist_ok=True)

    # 1. brut ancien -> archive/brut
    if os.path.isdir(BRUT):
        for fl in sorted(os.listdir(BRUT)):
            if not fl.endswith(".md"):
                continue
            p = os.path.join(BRUT, fl)
            if _age_days(p) >= ARCHIVE_DAYS:
                if apply:
                    dest_dir = os.path.join(ARCHIVE, "brut")
                    os.makedirs(dest_dir, exist_ok=True)
                    dest = os.path.join(dest_dir, fl)
                    shutil.move(p, dest)
                    os.utime(dest, None)  # date d'archivage = maintenant
                    rep["archives"].append("brut/" + fl)
                else:
                    rep["a_archiver"].append("brut/" + fl)

    # 2. en_attente ancien -> signalé comme backlog À TRAITER (jamais déplacé/supprimé)
    if os.path.isdir(EN_ATTENTE):
        for fl in sorted(os.listdir(EN_ATTENTE)):
            if fl.endswith(".md") and _age_days(os.path.join(EN_ATTENTE, fl)) >= ARCHIVE_DAYS:
                rep["backlog_en_attente"].append(fl[:-3])

    # 3. archive ancienne -> éligible à suppression (validée à la main via purge=True)
    if os.path.isdir(ARCHIVE):
        for dpth, _dirs, files in os.walk(ARCHIVE):
            for fl in files:
                if not fl.endswith(".md"):
                    continue
                p = os.path.join(dpth, fl)
                if _age_days(p) >= DELETE_DAYS:
                    rel = os.path.relpath(p, ARCHIVE)
                    if purge:
                        os.remove(p)
                        rep["supprimes"].append(rel)
                    else:
                        rep["a_supprimer"].append(rel)
    return rep


# --------------------------------------------------------------------------- #
# Serveur
# --------------------------------------------------------------------------- #
class Handler(BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(u.query)
        if u.path == "/health":
            return self._send({"status": "ok", "root": ROOT,
                               "etages": ["brut", "en_attente", "structure"]})
        if u.path == "/domains":
            return self._send(get_domains())
        if u.path == "/staging":
            return self._send(list_staging())
        if u.path == "/recall":
            return self._send(recall(params))
        if u.path == "/stats":
            return self._send(stats())
        if u.path == "/maintenance":
            return self._send(maintenance(apply=False, purge=False))  # dry-run
        return self._send({"error": "not found", "path": u.path}, 404)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception as e:
            return self._send({"error": "json invalide: %s" % e}, 400)

        if u.path == "/note":
            if not (data.get("content") or "").strip():
                return self._send({"error": "champ 'content' requis"}, 400)
            return self._send(add_note(data))
        if u.path == "/stage":
            if not (data.get("content") or "").strip():
                return self._send({"error": "champ 'content' requis"}, 400)
            return self._send(stage(data))
        if u.path == "/promote":
            res = promote(data)
            return self._send(res, 400 if "error" in res else 200)
        if u.path == "/clore":
            res = clore(data.get("id"), data.get("raison"),
                        data.get("pointeur"), data.get("score"), data.get("examens"))
            return self._send(res, 400 if "error" in res else 200)
        if u.path == "/reactiver":
            res = reactiver(data.get("id"))
            return self._send(res, 400 if "error" in res else 200)
        if u.path == "/memorize":
            if not (data.get("content") or "").strip():
                return self._send({"error": "champ 'content' requis"}, 400)
            return self._send(memorize(data))
        if u.path == "/superseder":
            res = superseder(data)
            return self._send(res, 400 if "error" in res else 200)
        if u.path == "/desuperseder":
            res = desuperseder(data)
            return self._send(res, 400 if "error" in res else 200)
        if u.path == "/retro_tag":
            return self._send(retro_tag_source(
                (data.get("source") or SOURCE_INTERNE).strip() or SOURCE_INTERNE,
                (data.get("verifie") or VERIFIE_DEFAUT).strip() or VERIFIE_DEFAUT))
        if u.path == "/maintenance":
            return self._send(maintenance(apply=bool(data.get("apply")),
                                          purge=bool(data.get("purge"))))
        return self._send({"error": "not found", "path": u.path}, 404)


def main():
    for d in (BRUT, EN_ATTENTE, STRUCT, ARCHIVE):
        os.makedirs(d, exist_ok=True)
    update_indexes()
    print("Mémoire-beta en écoute sur http://%s:%d" % (HOST, PORT))
    print("Données : %s" % ROOT)
    print("  brut/       -> capture autonome")
    print("  en_attente/ -> candidats à valider")
    print("  structure/  -> mémoire classée")
    print("  archive/    -> brut ancien (corbeille manuelle)")
    try:
        ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")


if __name__ == "__main__":
    main()
