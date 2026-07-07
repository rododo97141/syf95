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
    POST /memorize    {content, domain, category, title?, summary?,    -> STRUCTURE (direct)
                       source?}
    GET  /recall?query=&domain=&category=&scope=all|brut|en_attente|structure
                 &format=sas   (opt-in : regroupe le classement global par étage)
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
# Étage 1 — BRUT : capture autonome, append-only, un journal par jour
# --------------------------------------------------------------------------- #
def add_note(data):
    content = (data.get("content") or "").strip()
    tag = (data.get("tag") or "").strip()
    os.makedirs(BRUT, exist_ok=True)
    day = datetime.date.today().strftime("%Y-%m-%d")
    file_path = os.path.join(BRUT, day + ".md")
    new_file = not os.path.exists(file_path)
    entry = "\n## %s%s\n%s\n" % (now_hm(), (" · #" + slugify(tag)) if tag else "", content)
    with open(file_path, "a", encoding="utf-8") as f:
        if new_file:
            f.write("# Notes brutes — %s\n" % today())
        f.write(entry)
    return {
        "ok": True,
        "etage": "brut",
        "path": os.path.relpath(file_path, ROOT),
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


def _write_struct(domain, category, title, content, summary="", source=""):
    """Écrit une fiche structurée. Si elle existe : fusion (section datée), pas de doublon."""
    domain = slugify(domain or "general")
    category = slugify(category or "divers")
    title = (title or content[:60] or "sans-titre").strip()
    slug = slugify(title)
    dir_path = os.path.join(STRUCT, domain, category)
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, slug + ".md")
    created = not os.path.exists(file_path)

    if created:
        parts = ["# %s — domaine: %s / catégorie: %s\n" % (title, domain, category)]
        parts.append("> Créé le %s · Dernière mise à jour le %s\n\n" % (today(), today()))
        if summary:
            parts.append("## En bref\n%s\n\n" % summary)
        parts.append("## Détail\n%s\n" % content)
        if source:
            parts.append("\n## Source\n%s\n" % source)
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
    origin = (data.get("origin") or "").strip()
    os.makedirs(EN_ATTENTE, exist_ok=True)

    base = datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + slugify(title)[:40]
    sid, i = base, 1
    while os.path.exists(os.path.join(EN_ATTENTE, sid + ".md")):
        i += 1
        sid = "%s-%d" % (base, i)

    meta = {"domain": domain, "category": category, "title": title,
            "summary": summary, "source": source, "origin": origin, "staged": today(),
            "content": content}
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
                        meta.get("source", ""))
    os.remove(path)  # validé -> sort de la file d'attente
    res["promu_depuis"] = sid
    return res


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
            out.append({"etage": etage, "domain": domain, "category": category,
                        "file": fl, "path": rel, "excerpt": text[:400],
                        "_search": (text + " " + fl).lower()})
    return out


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


def rank_candidates(query, cands, forces=None):
    """Classe des candidats (chacun portant la clé « _search ») par
    pertinence(IDF) × force, sans les modifier en place.

    Pertinence = somme des IDF des tokens *distincts* de la requête présents
    dans la fiche (présence binaire : le bourrage de mots-clés n'élève pas le
    score). IDF lissé = log((N+1)/(df+1)) + 1 : ~1 pour un token présent
    partout (aucun gagnant confiant), élevé pour un token rare/distinctif.

    Renvoie une nouvelle liste triée par score décroissant (départage stable
    par chemin puis nom), chaque élément enrichi de « _relevance », « _force »
    et « _score »."""
    if forces is None:
        forces = load_forces()
    qtokens = list(dict.fromkeys(_tokens(query)))          # dédup, ordre stable
    n = len(cands) or 1
    cand_tokens = [set(_tokens(c.get("_search", ""))) for c in cands]
    df = {t: 0 for t in qtokens}
    for toks in cand_tokens:
        for t in qtokens:
            if t in toks:
                df[t] += 1
    idf = {t: math.log((n + 1) / (df[t] + 1)) + 1.0 for t in qtokens}
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
# (issu de l'unique appel à rank_candidates dans recall) et le REGROUPE en trois
# blocs étiquetés — structure (validé) / en_attente (analysé-non-validé) / brut
# (non-trié) — chacun dans l'ordre du classement global. Il dit au consommateur
# ce qu'il regarde ; il ne décide pas à sa place.
_SAS_ETAGES = ("structure", "en_attente", "brut")


def _sas_candidat(item):
    """Forme SAS d'un candidat : la forme publique + les scores du classement
    global, NON strippés (déjà calculés par rank_candidates : zéro compute
    nouveau). L'étage est toujours présent — le consommateur DOIT router dessus."""
    return {
        "etage": item["etage"], "domain": item["domain"],
        "category": item["category"], "file": item["file"],
        "path": item["path"], "excerpt": item["excerpt"],
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
    ne matche (pas de sentinelle, pas de seuil)."""
    blocs = {e: [] for e in _SAS_ETAGES}
    for r in results:
        et = r.get("etage")
        if et in blocs:
            blocs[et].append(_sas_candidat(r))

    # results est en ordre de classement global : le 1er de chaque bloc est le
    # meilleur de son étage.
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

    count = sum(len(blocs[e]) for e in _SAS_ETAGES)
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
        if u.path == "/memorize":
            if not (data.get("content") or "").strip():
                return self._send({"error": "champ 'content' requis"}, 400)
            return self._send(memorize(data))
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
