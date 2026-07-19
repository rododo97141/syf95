#!/usr/bin/env python3
"""
NEXUS — Capital de critères (la brique HITL capitalisante)
« Ce que Kily tranche une fois doit servir mille fois — et peser selon ce qu'il rend. »

Quand une tâche subjective bute sur « quels critères / quels tests appliquer ? »,
Kily répond. Cet organe CAPITALISE cette réponse pour qu'elle :
  (a) devienne une FICHE retrouvable par le classement pertinence(IDF) × force
      de rank() (nexus_force / memory_api : PR 57) ;
  (b) alimente enfin calculer_forces() — jusqu'ici {} car le logger auto n'émet
      que `statut="ok"`, un statut que calculer_forces NE COMPTE PAS. Ici, le
      geste de clôture émet un capteur `statut=succes|echec` (les DEUX seuls
      statuts que calculer_forces compte : +1 / -1), fiche=<slug> : la force
      d'une fiche monte quand elle sert et réussit, descend quand elle rate.

Le chantier CÂBLE des organes existants, il ne les reconstruit pas :
  - nexus_lecons  : journal + transfert (pointeur de leçon, RÉFÉRENCE jamais copie)
  - nexus_sense   : log_event(fiche=<slug>, statut=succes|echec) — le capteur
  - nexus_force   : calculer_forces + rank + bornes FORCE_MIN 0.2 / FORCE_MAX 5.0

nexus_capital est le SEUL écrivain de SES fichiers :
  - fiches      : <MEMOIRE_ROOT>/structure/<domaine>/criteres-kily/<slug>.md
  - journal     : <MEMOIRE_ROOT>/capital/consultations.jsonl (append-only)
  - registre    : <MEMOIRE_ROOT>/capital/jetons.jsonl (append-only) — écrit UNIQUEMENT
                  par generer_jeton_confirmation (LE geste humain).
Il n'écrit JAMAIS memory_api.py, nexus_force.py, nexus_sense.py, nexus_lecons.py :
  les capteurs et le journal des leçons sont écrits VIA ces organes (un écrivain
  par fichier). L'emplacement des fiches est celui que rank()/memory_api lisent
  RÉELLEMENT par défaut (MEMOIRE_ROOT/structure) — décision vérifiée, cf. la PR :
  `memoire/` à la racine (committé) n'est lu par aucun code runtime.

LIGNE ROUGE DE DOCTRINE (non négociable) : aucun chemin MÉCANIQUE ne peut atteindre
appliquer — le système ne se récompense JAMAIS lui-même (modèle de menace :
le-code-s-auto-récompense / Goodhart interne). La force reste un signal de JUGEMENT
HUMAIN externe : appliquer exige un jeton de confirmation VALIDE et NON CONSOMMÉ,
matérialisé par generer_jeton_confirmation (le seul geste humain). Dissymétrie nette :
clore_sans_dette (clôture administrative) n'exige RIEN ; appliquer (jugement) est verrouillé.

Les gestes :
  1) capitaliser(question, reponse, contexte, domaine)  -> écrit la fiche + pointeur leçon
  2) consulter(query, tache, memoire=None)              -> délègue à rank() ; avec `memoire`,
                                                           délègue le rappel à recall (chemin boucle)
  3) generer_jeton_confirmation(consultation_id, secret=None) -> LE geste humain : émet un jeton
                                                           usage-unique (barrière secret optionnelle,
                                                           cf. capital/jeton_secret.json)
  4) appliquer(consultation_id, fiche_retenue, resultat, tache, jeton) -> clôture + capteur de force
                                                           (EXIGE un jeton valide non consommé, l'inscrit)
  5) clore_sans_dette(consultation_id, raison)          -> clôture SANS capteur de force (rien exigé)
  6) bilan()                                            -> dette de consultations non closes

Usage bibliothèque uniquement (pas de CLI serveur ici).
"""
import os
import re
import sys
import json
import hashlib
import datetime
import unicodedata

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import nexus_force    # source UNIQUE du chemin mémoire + rank/calculer_forces (LU)
import nexus_sense    # capteur : log_event(fiche=<slug>, statut=succes|echec)
import nexus_lecons   # journal de leçons + transfert (pointeur, RÉFÉRENCE)

# --------------------------------------------------------------------------- #
# Catégorie fixe des fiches capitalisées : le 2e niveau sous structure/<domaine>/.
# _scan (memory_api) en dérive `category` = parts[2] → filtrable par recall().
# --------------------------------------------------------------------------- #
CATEGORIE = "criteres-kily"

# --------------------------------------------------------------------------- #
# Provenance d'une fiche (source / verifie) — LECTURE des marqueurs machine posés
# par memory_api (même format : commentaires HTML en fin de fiche). Réplique
# volontaire (comme _slug réplique slugify) : nexus_capital LIT, il n'écrit pas
# memory_api. Absence => défaut (interne / non) : tout ce qui n'est pas
# EXPLICITEMENT externe EST interne (miroir de memory_api._lire_provenance).
# --------------------------------------------------------------------------- #
_SOURCE_RE = re.compile(r"<!--\s*source:\s*(.*?)\s*-->")
_VERIFIE_RE = re.compile(r"<!--\s*verifie:\s*(.*?)\s*-->")

# --------------------------------------------------------------------------- #
# N_JOURS_DETTE — fenêtre au-delà de laquelle une consultation fiche-unique NI
# appliquée NI close-sans-dette bascule en DETTE. PROVISOIRE, même discipline
# que PR 57 : ce n'est pas une valeur mesurée, c'est un point de départ.
#   • Mesure de qualité : délai médian observé consultation -> application (P50)
#     et P90, sur le journal consultations.jsonl.
#   • Déclencheur chiffré de révision : dès ≥ 30 consultations fiche-unique
#     clôturées, recalculer P50/P90. Si P90 < 2 j → abaisser N à 3 ; si P50 > 5 j
#     → relever N à 14 (sinon la dette « crie » sur un rythme de travail normal).
# --------------------------------------------------------------------------- #
N_JOURS_DETTE = 7  # PROVISOIRE


# =========================================================================== #
# Chemins — ADOSSÉS à nexus_force._racine_memoire() : une SEULE source de vérité
# pour la racine mémoire (respecte MEMOIRE_ROOT, relu à chaque appel). Garantit
# que les fiches atterrissent là où rank()/memory_api lisent.
# =========================================================================== #
def _racine():
    return nexus_force._racine_memoire()


def _dir_structure():
    return os.path.join(_racine(), "structure")


def _dir_fiches(domaine):
    return os.path.join(_dir_structure(), _slug(domaine), CATEGORIE)


def _chemin_fiche(domaine, slug):
    return os.path.join(_dir_fiches(domaine), slug + ".md")


def _provenance_fiche(slug):
    """Lit (source, verifie) de la fiche criteres-kily `slug` là où rank()/
    memory_api lisent réellement (structure/<dom>/criteres-kily/<slug>.md). Défaut
    (interne, non) si la fiche est absente ou non étiquetée. LECTURE SEULE."""
    struct = _dir_structure()
    if os.path.isdir(struct):
        cible = slug + ".md"
        for dirpath, _dirs, files in os.walk(struct):
            if os.path.basename(dirpath) != CATEGORIE:
                continue
            if cible in files:
                try:
                    text = open(os.path.join(dirpath, cible), encoding="utf-8").read()
                except OSError:
                    break
                ms = _SOURCE_RE.search(text)
                mv = _VERIFIE_RE.search(text)
                source = (ms.group(1).strip() if ms else "interne") or "interne"
                verifie = (mv.group(1).strip() if mv else "non") or "non"
                return source, verifie
    return "interne", "non"


def _chemin_consultations():
    return os.path.join(_racine(), "capital", "consultations.jsonl")


def _chemin_jetons():
    return os.path.join(_racine(), "capital", "jetons.jsonl")


# --------------------------------------------------------------------------- #
# Secret de confirmation (OPTIONNEL) — capital/jeton_secret.json ne contient
# JAMAIS le secret en clair, seulement son hash SHA-256. Absent : comportement
# historique INCHANGÉ (rétrocompat totale, cf. generer_jeton_confirmation).
# --------------------------------------------------------------------------- #
def _chemin_secret_jeton():
    return os.path.join(_racine(), "capital", "jeton_secret.json")


def _hash_secret(secret):
    return hashlib.sha256((secret or "").encode("utf-8")).hexdigest()


def _secret_configure():
    """Renvoie le hash configuré (str) ou None si jeton_secret.json est absent
    ou invalide. LECTURE SEULE : cet organe n'écrit jamais ce fichier (geste de
    Kily, hors session agent)."""
    chemin = _chemin_secret_jeton()
    try:
        with open(chemin, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    h = (data.get("hash") or "").strip()
    return h or None


# =========================================================================== #
# Slug — RÉPLIQUE EXACTE de memory_api.slugify : même nom de fichier que le
# corpus réel, donc dédup naturelle (un slug = un fichier).
# =========================================================================== #
def _slug(text):
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "sans-titre"


def _today():
    return datetime.date.today().strftime("%d/%m/%Y")


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


# =========================================================================== #
# 1) capitaliser — écrit LA fiche (source unique) + un pointeur de leçon
#    (RÉFÉRENCE : le slug, JAMAIS une copie de la réponse verbatim).
# =========================================================================== #
def capitaliser(question, reponse, contexte, domaine, pourquoi=None,
                source="interne", verifie="non"):
    """Écrit une fiche criteres-kily au format du corpus réel et un pointeur de
    leçon (référence au slug, aucune copie de contenu).

    - contexte est OBLIGATOIRE (sans lui, la fiche est un critère hors-sol,
      inapplicable : on lève plutôt que d'écrire une fiche muette).
    - `pourquoi` (cause) est OPTIONNEL : ajouté à la fiche et porté par le
      pointeur de leçon quand il est fourni.
    - slug dérivé UNE seule fois (de la question), réutilisé pour le fichier, le
      pointeur de leçon ET la valeur de retour. Recapitaliser le même intitulé
      met à jour LE même fichier (pas de doublon) et préserve la date de création.

    Renvoie le slug (identité stable de la fiche)."""
    if not (contexte or "").strip():
        raise ValueError("capitaliser: 'contexte' est OBLIGATOIRE (un critère sans "
                         "contexte est inapplicable).")
    question = (question or "").strip()
    reponse = (reponse or "").strip()
    contexte = contexte.strip()
    pourquoi = (pourquoi or "").strip() or None
    if not question:
        raise ValueError("capitaliser: 'question' est requise.")
    if not reponse:
        raise ValueError("capitaliser: 'reponse' est requise (verbatim de Kily).")

    slug = _slug(question)                         # dérivé UNE fois
    chemin = _chemin_fiche(domaine, slug)
    os.makedirs(os.path.dirname(chemin), exist_ok=True)

    cree_le = _today()
    if os.path.exists(chemin):                     # recapitalisation : garder la date d'origine
        try:
            ancien = open(chemin, encoding="utf-8").read()
            m = re.search(r"Créé le ([^\s·]+)", ancien)
            if m:
                cree_le = m.group(1)
        except OSError:
            pass

    dom = _slug(domaine)
    corps = [
        "# %s — domaine: %s / catégorie: %s\n" % (question, dom, CATEGORIE),
        "> Créé le %s · Dernière mise à jour le %s\n\n" % (cree_le, _today()),
        "## En bref\n%s\n\n" % contexte,
        "## Détail\n",
        "### Question\n%s\n\n" % question,
        "### Réponse (verbatim)\n%s\n\n" % reponse,       # verbatim, source unique
        "### Contexte\n%s\n" % contexte,
    ]
    if pourquoi:
        corps.append("\n### Pourquoi\n%s\n" % pourquoi)
    # Provenance : marqueur machine en FIN de fiche (la 1re ligne reste le titre),
    # écrit UNIQUEMENT hors défaut (source externe) → une fiche interne reste
    # byte-identique à l'existant. Une fiche criteres-kily EXTERNE non certifiée
    # verra sa force retrogradée par appliquer (garde source-consciente).
    source = (source or "interne").strip() or "interne"
    verifie = (verifie or "non").strip() or "non"
    if source != "interne" or verifie != "non":
        corps.append("\n<!-- source: %s -->\n<!-- verifie: %s -->\n" % (source, verifie))
    with open(chemin, "w", encoding="utf-8") as f:
        f.write("".join(corps))

    # Pointeur de leçon : une RÉFÉRENCE au slug, PAS la réponse. Éditer la fiche
    # ne crée aucune copie divergente (la leçon ne stocke jamais le verbatim).
    ns = _Namespace(
        type="methode",
        contexte="%s / %s" % (dom, CATEGORIE),
        lecon="critère capitalisé → fiche %s/%s/%s (recall par rank)" % (dom, CATEGORIE, slug),
        correctif=None,
        pourquoi=pourquoi,
    )
    nexus_lecons.add(ns)
    return slug


# =========================================================================== #
# 2) consulter — délègue le CLASSEMENT à nexus_force.rank() (aucune logique de
#    tri nouvelle ici), journalise la consultation (fiche_retenue=null provisoire).
# =========================================================================== #
def consulter(query, tache, k=3, memoire=None):
    """Cherche les critères capitalisés pertinents pour `query` et journalise la
    consultation. Renvoie l'enregistrement de consultation (dont `id` et
    `slugs_retournes`).

    DEUX chemins, choisis par `memoire` :

      • `memoire=None` (défaut, chemin CAPITAL) : le tri est INTÉGRALEMENT délégué
        à nexus_force.rank() sur les fiches criteres-kily — cet organe ne calcule
        aucun score. `slugs_retournes` = slugs des candidats à pertinence non nulle,
        plafonnés aux `k` premiers. COMPORTEMENT HISTORIQUE INCHANGÉ.

      • `memoire` fourni (chemin BOUCLE) : le RAPPEL est DÉLÉGUÉ à `memoire.recall`
        (portée `all`, results[0] — MIROIR EXACT du rappel historique de la boucle),
        et la consultation est JOURNALISÉE pour être VISIBLE au bilan. La boucle ne
        JUGE jamais : elle rend simplement ses consultations comptables. consulter
        PEUT lever (recall qui casse) ; l'appelant (orchestrateur) avale — la boucle
        continue TOUJOURS. Sans fiche rappelée : rien n'est journalisé (pas de
        consultation fantôme au bilan).

    Une consultation fiche-UNIQUE (len==1) est la seule qui pourra émettre un
    capteur de force (cf. appliquer)."""
    query = query or ""
    if memoire is not None:
        # CHEMIN BOUCLE : rappel délégué à recall (inchangé), une fiche par tâche.
        fiche = _recall_fiche_unique(memoire, query)      # dict result[0] ou None
        slug = _slug_recall(fiche)                        # slug ou None
        if slug is None:
            # aucune fiche : rien à injecter/clôturer/journaliser (id None).
            return {
                "type": "consultation", "id": None, "ts": _now(),
                "requete": query, "slugs_retournes": [],
                "fiche_retenue": None, "tache": tache, "_fiche": None,
            }
        cid = _prochain_id()
        rec = {
            "type": "consultation", "id": cid, "ts": _now(),
            "requete": query, "slugs_retournes": [slug],
            "fiche_retenue": None, "tache": tache,
        }
        _append_consultation(rec)                         # journal LEAN (slug seul)
        out = dict(rec)
        out["_fiche"] = fiche      # transient (NON journalisé) : porte l'excerpt
        return out                 # pour l'injection prompt de l'orchestrateur.

    # CHEMIN CAPITAL (historique) : délégation PURE à rank() sur criteres-kily.
    cands = _candidats()                                  # collecte I/O, PAS du tri
    forces = nexus_force.calculer_forces()                # forces vivantes courantes
    ranked = nexus_force.rank(query, cands, forces=forces)   # DÉLÉGATION pure
    retenus = [_slug_de(c) for c in ranked if c.get("_relevance", 0.0) > 0.0][:k]

    cid = _prochain_id()
    rec = {
        "type": "consultation",
        "id": cid,
        "ts": _now(),
        "requete": query,
        "slugs_retournes": retenus,
        "fiche_retenue": None,        # PROVISOIRE — figé par appliquer()
        "tache": tache,
    }
    _append_consultation(rec)
    return rec


def _recall_fiche_unique(memoire, query):
    """Rappel DÉLÉGUÉ à memoire.recall (portée `all`, results[0]) — MIROIR EXACT
    du _rappeler_fiche historique de l'orchestrateur (rappel INCHANGÉ). Renvoie la
    meilleure fiche (dict), ou None. NE protège PAS contre une exception de recall :
    elle remonte à consulter, puis à l'orchestrateur qui l'avale (boucle continue)."""
    reponse = memoire.recall({"query": [query], "scope": ["all"]})
    resultats = reponse.get("results") or []
    return resultats[0] if resultats else None


def _slug_recall(fiche):
    """Slug (radical .md) d'une fiche recall, ou None si absente/sans nom."""
    if not fiche:
        return None
    nom = fiche.get("file", "")
    slug = nom[:-3] if nom.endswith(".md") else nom
    return slug or None


# =========================================================================== #
# 3) appliquer — geste de clôture d'une consultation fiche-UNIQUE : fige la fiche
#    retenue, émet UN capteur de force (statut succes|echec) + un transfert.
#    REFUSE d'émettre un capteur de force si la consultation était multi-fiches.
# =========================================================================== #
def appliquer(consultation_id, fiche_retenue, resultat, tache, jeton=None):
    """Clôt une consultation en constatant qu'UNE fiche a servi et a réussi/échoué.

    VERROU DE JUGEMENT (ligne rouge) : appliquer EXIGE un `jeton` de confirmation
    HITL VALIDE et NON CONSOMMÉ (émis par generer_jeton_confirmation — le geste
    humain). C'est la 1re couche de défense : le REGISTRE À L'ÉMISSION. Sans jeton
    valide, aucun capteur de force n'est émis — le système ne se récompense JAMAIS
    lui-même. Le jeton est ensuite CONSOMMÉ (marqué utilisé par sa présence dans
    l'event de force) et son id est INSCRIT dans l'event, dans un champ structuré.

    Garde-fous (sémantique PR 64 INCHANGÉE une fois le jeton validé) :
      - la consultation doit exister et avoir retourné EXACTEMENT une fiche
        (« une fiche constatée ») ; sinon REFUS (multi-fiches → clore_sans_dette).
      - `fiche_retenue` doit être cette unique fiche constatée.
      - `resultat` doit se réduire à succes|echec — les SEULS statuts que
        nexus_force.calculer_forces compte (+1 / -1). « ok » / « partiel » sont
        rejetés ici : les émettre laisserait la force PLATE (le bug historique).

    Émet le capteur via nexus_sense.log_event(fiche=<slug>, statut=..., jeton=<id>),
    journalise le transfert via nexus_lecons.appliquer, et fige la clôture dans le
    journal (l'id du jeton figé avec elle)."""
    cons = _consultation(consultation_id)
    if cons is None:
        raise ValueError("appliquer: consultation inconnue: %r" % consultation_id)

    # --- VERROU DE JUGEMENT : jeton VALIDE et NON CONSOMMÉ, exigé AVANT tout
    #     capteur de force. Un chemin mécanique (boucle/observer) n'a jamais de
    #     jeton : il ne peut donc PAS émettre de force. ---
    if jeton is None:
        raise ValueError(
            "appliquer: REFUS — un jeton de confirmation HITL est OBLIGATOIRE "
            "(generer_jeton_confirmation). Aucun chemin mécanique ne se récompense "
            "lui-même : la force reste un jugement humain externe.")
    jrec = _jeton_record(jeton)
    if jrec is None:
        raise ValueError("appliquer: jeton %r inconnu du registre." % (jeton,))
    if jrec.get("consultation_id") != consultation_id:
        raise ValueError(
            "appliquer: jeton %r émis pour la consultation %r — ne peut confirmer %r."
            % (jeton, jrec.get("consultation_id"), consultation_id))
    if _jeton_deja_reference(jeton):
        raise ValueError(
            "appliquer: jeton %r DÉJÀ consommé (rejoué) — usage UNIQUE." % (jeton,))

    slugs = cons.get("slugs_retournes") or []
    if len(slugs) != 1:
        raise ValueError(
            "appliquer: REFUS d'émettre un capteur de force — la consultation %r "
            "a retourné %d fiche(s) (attendu 1). Multi-fiches ⇒ clore_sans_dette."
            % (consultation_id, len(slugs)))
    if fiche_retenue != slugs[0]:
        raise ValueError(
            "appliquer: fiche_retenue %r ≠ la fiche constatée %r de la consultation."
            % (fiche_retenue, slugs[0]))

    statut = _statut_force(resultat)   # succes|echec, ou lève

    # --- GARDE FORCE SOURCE-CONSCIENTE : la force est un CRÉDIT-VÉRITÉ ----------
    # appliquer lit la provenance de la fiche_retenue. Si elle vient d'une source
    # EXTERNE (source != 'interne') NON certifiée par Kily (verifie != 'oui'), un
    # 'succes' est RETROGRADÉ en statut 'ok' : INERTE (calculer_forces IGNORE
    # 'ok'), la force NE MONTE PAS. 'echec' reste 'echec' (la force descend).
    # L'asymétrie passe par le CHOIX du statut ÉMIS — nexus_force n'est JAMAIS
    # touché. VOULU : ceci peut retrograder un succes jugé UTILE par Kily (le
    # jeton reste consommé) — l'humain valide l'UTILITÉ, la garde protège le
    # crédit-VÉRITÉ. Si Kily certifie la source (verifie='oui'), la retrogradation
    # cesse (la fiche redevient un chemin de force plein).
    source_f, verifie_f = _provenance_fiche(fiche_retenue)
    retrograde = (statut == "succes" and source_f != "interne" and verifie_f != "oui")
    statut_emis = "ok" if retrograde else statut

    # (b) le capteur : fiche=<slug>, statut compté par calculer_forces + jeton=<id>
    #     (champ structuré). C'est CE geste, adossé au jeton humain, qui rend la
    #     force vivante. Consommer = ce jeton apparaît désormais dans un event de
    #     force (aucune ré-émission possible : _jeton_deja_reference le verra).
    #     Un statut RETROGRADÉ ('ok') consomme quand même le jeton (tracé, inerte).
    nexus_sense.log_event(
        tache=tache,
        statut=statut_emis,
        mode="assiste",
        fiche=fiche_retenue,
        note="capital: application d'un critère capitalisé",
        jeton=jeton,
    )

    # transfert : la leçon (référence au slug) réappliquée à une tâche nouvelle.
    # Fondé sur le JUGEMENT humain d'utilité (statut), pas sur le crédit-force :
    # la leçon ne nourrit pas calculer_forces (seul le capteur le fait).
    ns = _Namespace(
        lecon_cle=fiche_retenue,
        tache=tache,
        resultat="mieux" if statut == "succes" else "pire",
    )
    nexus_lecons.appliquer(ns)

    rec = {
        "type": "application",
        "id": consultation_id,
        "ts": _now(),
        "fiche_retenue": fiche_retenue,   # figé
        "resultat": resultat,
        "statut": statut_emis,            # statut RÉELLEMENT émis (retrogradé le cas échéant)
        "statut_juge": statut,            # jugement humain (succes|echec) avant garde
        "retrograde": retrograde,         # True si succes externe non-vérifié rendu inerte
        "source": source_f,               # provenance lue de la fiche
        "verifie": verifie_f,
        "tache": tache,
        "capteur_force": True,
        "jeton": jeton,                   # id du jeton consommé, figé avec la clôture
    }
    _append_consultation(rec)
    return rec


# =========================================================================== #
# 3bis) generer_jeton_confirmation — LE GESTE HUMAIN, seule écrivaine du registre
#    jetons.jsonl. Un jeton = une confirmation humaine, à usage UNIQUE, adossée à
#    une consultation existante. Aucun chemin mécanique ne l'appelle (ni appliquer).
# =========================================================================== #
def generer_jeton_confirmation(consultation_id, secret=None):
    """Émet un jeton de confirmation à USAGE UNIQUE pour `consultation_id` et
    renvoie son id. SEULE écrivaine du registre jetons.jsonl.

    C'est LE geste humain : sa seule invocation matérialise un jugement humain
    externe. La consultation doit exister (on ne confirme pas dans le vide). Le
    jeton reste « non consommé » tant qu'aucun event de force ne le référence
    (cf. appliquer / _jeton_deja_reference).

    BARRIÈRE TECHNIQUE (optionnelle, activée par capital/jeton_secret.json) :
    sans ce fichier, RIEN ne change (rétrocompat totale — le geste reste
    accessible à quiconque appelle la fonction, comme avant). Une fois le
    fichier posé par Kily (hors session agent — jamais le secret en clair dans
    ce dépôt), `secret` doit correspondre au hash configuré, sinon REFUS : plus
    aucun chemin mécanique ne peut alors forger la confirmation."""
    cons = _consultation(consultation_id)
    if cons is None:
        raise ValueError(
            "generer_jeton_confirmation: consultation inconnue: %r"
            % (consultation_id,))
    hash_configure = _secret_configure()
    if hash_configure is not None and (secret is None or _hash_secret(secret) != hash_configure):
        raise ValueError(
            "generer_jeton_confirmation: REFUS - secret de confirmation absent ou "
            "incorrect (capital/jeton_secret.json configuré : seul le geste humain "
            "qui connaît le secret peut émettre un jeton).")
    jid = _prochain_jeton_id()
    rec = {
        "type": "jeton",
        "id": jid,
        "consultation_id": consultation_id,
        "ts": _now(),
    }
    _append_jeton(rec)
    return jid


# =========================================================================== #
# 4) clore_sans_dette — clôture SANS capteur de force (multi-fiches ou
#    sans-critère) : sort la consultation du dénominateur du backlog.
# =========================================================================== #
def clore_sans_dette(consultation_id, raison):
    """Clôt une consultation sans émettre de capteur de force. Usage : la
    consultation était multi-fiches (outcome non attribuable à UNE fiche) ou
    « sans-critère » (la fiche retenue n'était finalement pas un critère). La
    consultation sort du dénominateur du backlog (ni dette, ni à traiter)."""
    if not (raison or "").strip():
        raise ValueError("clore_sans_dette: 'raison' est requise (traçabilité).")
    rec = {
        "type": "cloture_sans_dette",
        "id": consultation_id,
        "ts": _now(),
        "raison": raison.strip(),
    }
    _append_consultation(rec)
    return rec


# =========================================================================== #
# 5) bilan — dette = consultations fiche-UNIQUE NI appliquées NI closes-sans-dette
#    au-delà de N_JOURS_DETTE. Les multi-fiches ne sont JAMAIS dans la dette.
# =========================================================================== #
def bilan(now=None, n_jours=None):
    """Renvoie l'état du backlog HITL. Lecture seule, robuste (journal absent ou
    lignes corrompues → ignorées).

    - `now` : instant de référence (datetime ou ISO str) ; défaut = maintenant.
      Injectable pour tester le franchissement de N jours de façon déterministe.
    - `n_jours` : fenêtre de dette ; défaut = N_JOURS_DETTE.

    Dénominateur du backlog = consultations fiche-UNIQUE (len(slugs)==1). Une
    telle consultation est CLOSE si elle a une application OU une clôture-sans-dette.
    Dette = fiche-unique, non close, âge > n_jours. Multi-fiches : hors backlog."""
    if n_jours is None:
        n_jours = N_JOURS_DETTE
    ref = _to_dt(now) if now is not None else datetime.datetime.now()

    consultations = {}     # id -> record d'ouverture
    closes = set()         # ids appliqués ou clos-sans-dette
    for rec in _lire_consultations():
        t = rec.get("type")
        cid = rec.get("id")
        if cid is None:
            continue
        if t == "consultation":
            consultations[cid] = rec
        elif t in ("application", "cloture_sans_dette"):
            closes.add(cid)

    dette, ouvertes, n_closes, n_multi = [], [], 0, 0
    for cid, rec in consultations.items():
        slugs = rec.get("slugs_retournes") or []
        if len(slugs) != 1:
            n_multi += 1               # multi-fiches (ou zéro) : hors backlog
            continue
        if cid in closes:
            n_closes += 1              # appliquée ou close-sans-dette : hors dette
            continue
        age = _age_jours(rec.get("ts"), ref)
        if age is not None and age > n_jours:
            dette.append({"id": cid, "ts": rec.get("ts"), "slug": slugs[0],
                          "requete": rec.get("requete"), "tache": rec.get("tache"),
                          "age_jours": round(age, 2)})
        else:
            ouvertes.append(cid)       # dans le dénominateur, pas encore en retard

    n_actionnables = len(dette) + len(ouvertes) + n_closes
    return {
        "n_dette": len(dette),
        "dette": dette,
        "n_ouvertes": len(ouvertes),
        "n_closes": n_closes,
        "n_multi_fiches": n_multi,
        "n_actionnables": n_actionnables,
        "n_jours": n_jours,
    }


# =========================================================================== #
# Helpers internes
# =========================================================================== #
class _Namespace:
    """Petit porteur d'attributs pour les API bibliothèque de nexus_lecons
    (add/appliquer attendent un objet façon argparse)."""
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _statut_force(resultat):
    """Réduit `resultat` au vocabulaire que calculer_forces COMPTE : succes|echec.
    Vérifié dans nexus_force.calculer_forces : seuls statut=='succes' (+1) et
    statut=='echec' (-1) bougent la force ; 'ok'/'partiel' sont ignorés (c'est
    exactement pourquoi la force restait plate). On lève sur tout le reste plutôt
    que d'émettre un capteur inerte."""
    if resultat in (True,):
        return "succes"
    if resultat in (False,):
        return "echec"
    r = str(resultat).strip().lower()
    if r in ("succes", "succès", "reussi", "réussi", "reussite", "ok_succes", "mieux"):
        return "succes"
    if r in ("echec", "échec", "echoue", "échoué", "rate", "raté", "pire"):
        return "echec"
    raise ValueError(
        "appliquer: 'resultat' doit se réduire à succes|echec (les seuls statuts "
        "comptés par calculer_forces). Reçu %r — 'ok'/'partiel' laisseraient la "
        "force plate." % (resultat,))


def _slug_de(cand):
    f = cand.get("file", "")
    return f[:-3] if f.endswith(".md") else f


def _candidats():
    """Collecte les fiches criteres-kily du corpus réel (structure/<dom>/criteres-kily),
    au format candidat attendu par rank() (mêmes clés que memory_api._scan :
    file / path / _search / etc.). C'est de l'I/O de COLLECTE, pas du classement.

    Portée = la catégorie criteres-kily sur tous les domaines : les critères
    capitalisés se départagent entre eux, ce qui garde une consultation
    fiche-unique naturelle. rank() lit ces candidats à l'identique du recall."""
    racine = _racine()
    struct = _dir_structure()
    out = []
    if not os.path.isdir(struct):
        return out
    for dirpath, _dirs, files in os.walk(struct):
        if os.path.basename(dirpath) != CATEGORIE:
            continue
        for fl in sorted(files):
            if not fl.endswith(".md") or fl == "_index.md":
                continue
            full = os.path.join(dirpath, fl)
            rel = os.path.relpath(full, racine)
            parts = rel.split(os.sep)
            domain = parts[1] if len(parts) >= 3 else None
            category = parts[2] if len(parts) >= 4 else None
            try:
                text = open(full, encoding="utf-8").read()
            except OSError:
                continue
            out.append({
                "etage": "structure", "domain": domain, "category": category,
                "file": fl, "path": rel, "excerpt": text[:400],
                "_search": (text + " " + fl).lower(),
            })
    return out


def _lire_consultations():
    chemin = _chemin_consultations()
    if not os.path.exists(chemin):
        return []
    out = []
    for line in open(chemin, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue          # ligne corrompue ignorée (robustesse bilan)
    return out


def _consultation(cid):
    """Dernier enregistrement d'OUVERTURE pour cet id (fold last-write-wins)."""
    trouve = None
    for rec in _lire_consultations():
        if rec.get("type") == "consultation" and rec.get("id") == cid:
            trouve = rec
    return trouve


def _append_consultation(rec):
    chemin = _chemin_consultations()
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _prochain_id():
    n = sum(1 for r in _lire_consultations() if r.get("type") == "consultation")
    return "cons-%04d" % (n + 1)


# --------------------------------------------------------------------------- #
# Registre des jetons de confirmation (jetons.jsonl) — append-only, écrit
# UNIQUEMENT par generer_jeton_confirmation. Lecture SEULE partout ailleurs.
# --------------------------------------------------------------------------- #
def _lire_jetons():
    chemin = _chemin_jetons()
    if not os.path.exists(chemin):
        return []
    out = []
    for line in open(chemin, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue          # ligne corrompue ignorée (robustesse)
    return out


def jetons_emis():
    """Vue LECTURE SEULE du registre : la liste des jetons émis (type='jeton').
    Sert la jointure unique de nexus_98 (3e rideau). nexus_capital reste le SEUL
    écrivain du registre — ceci n'écrit rien."""
    return [j for j in _lire_jetons() if j.get("type") == "jeton"]


def _jeton_record(jid):
    """Dernier enregistrement de jeton pour cet id (ou None)."""
    trouve = None
    for j in _lire_jetons():
        if j.get("type") == "jeton" and j.get("id") == jid:
            trouve = j
    return trouve


def _prochain_jeton_id():
    n = sum(1 for j in _lire_jetons() if j.get("type") == "jeton")
    return "jeton-%04d" % (n + 1)


def _jeton_deja_reference(jid):
    """True si `jid` est DÉJÀ référencé par un event de force émis (capteur porteur
    d'un champ `jeton`). C'est la définition de CONSOMMÉ, lue à la source unique
    des capteurs (nexus_sense) : 1re couche de défense « le registre à l'émission »."""
    for ev in nexus_sense.lire():
        if ev.get("jeton") == jid:
            return True
    return False


def _append_jeton(rec):
    chemin = _chemin_jetons()
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _to_dt(x):
    if isinstance(x, datetime.datetime):
        return x
    return datetime.datetime.fromisoformat(str(x))


def _age_jours(ts, ref):
    if not ts:
        return None
    try:
        t = datetime.datetime.fromisoformat(str(ts))
    except ValueError:
        return None
    return (ref - t).total_seconds() / 86400.0
