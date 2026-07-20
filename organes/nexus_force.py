#!/usr/bin/env python3
"""
NEXUS — Pont capteurs → forces (« la force devient vivante »)
« Ce qui sert et réussit doit remonter ; ce qui sert et échoue, redescendre. »

Chaînon manquant entre le capteur dédié posé par la boucle (nexus_sense,
champ `fiche=<slug>` quand un recall a servi à une tâche) et le classement
pertinence(IDF) × force de memory_api.recall() (champ `force`, lu dans
ROOT/forces.json = {fiche: multiplicateur}).

DÉTERMINISTE, sans IA : chaque appel RECALCULE l'intégralité des forces à
partir de TOUT l'historique des capteurs porteurs d'une fiche (idempotent —
rejouable sans double-comptage, pas d'état de progression à maintenir). Les
fiches jamais vues dans les capteurs conservent leur valeur existante dans
forces.json (aucun réglage manuel écrasé).

Garde-fous :
  - N'écrit QUE si demandé (`--apply` en CLI ; `appliquer()` en bibliothèque).
  - N'efface jamais une entrée : fusion avec l'existant, jamais un remplacement.
  - Ne lève jamais depuis `appliquer()` (le pont ne doit jamais casser la boucle).

Usage :
  python3 nexus_force.py            # calcule et affiche les forces (dry-run)
  python3 nexus_force.py --apply    # + écrit ROOT/forces.json
"""
import os
import re
import sys
import json
import math
import hashlib
import unicodedata

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import nexus_sense  # source UNIQUE de lecture des capteurs (respecte CAPTEURS_ROOT)
import nexus_liens  # source UNIQUE de voisins() pour le bonus de co-sélection de rank()

# Pas de gagnant écrasant : petit pas par événement, borné.
DELTA_SUCCES = 0.2
DELTA_ECHEC = -0.1
FORCE_DEFAUT = 1.0
FORCE_MIN = 0.2
FORCE_MAX = 5.0

# --------------------------------------------------------------------------- #
# PORTE À SEUIL doctrinale de la force (auto-levante : ni flag, ni état, ni
# migration — la porte s'ouvre d'elle-même quand le signal réel devient assez
# fort). La force d'une fiche n'influence rank() QUE si son signal jugé est
# suffisant ; sinon elle reste NEUTRE — aucun bonus, aucune pénalité.
#   • SEUIL_FORCE_GLOBAL : nombre TOTAL d'événements de force jugés (toutes
#     fiches confondues) en deçà duquel AUCUNE force ne s'applique — le corpus
#     n'a pas encore assez vécu pour que la force veuille dire quoi que ce soit.
#   • SEUIL_FORCE_SLUG : nombre d'événements jugés POUR CETTE fiche en deçà
#     duquel SA force reste neutre — une fiche à peine éprouvée ne pèse pas.
# Au régime NOMINAL (les deux seuils atteints), la sortie de rank() est
# BYTE-IDENTIQUE à l'historique. Sous seuil, la force ne peut NI monter NI
# descendre une fiche. PROVISOIRES (doctrine, non mesurés).
# --------------------------------------------------------------------------- #
SEUIL_FORCE_GLOBAL = 15
SEUIL_FORCE_SLUG = 3

# Apport MAXIMAL de la vitalité (réutilisation observée, cf. nexus_vitalite)
# SEULE, sans aucun succès/échec — PROVISOIRE, plafonné loin de FORCE_MAX pour
# qu'un indice de vitalité plein (1.0) ne puisse jamais, à lui seul, faire
# gagner une fiche jamais éprouvée par succes/echec réels.
DELTA_VITALITE_MAX = 0.3


def _racine_memoire():
    """Racine des données mémoire-beta = ROOT de memory_api.py.
    Override MEMOIRE_ROOT (même contrat que CAPTEURS_ROOT/LECONS_ROOT, relu à
    CHAQUE appel — pas de cache d'import), sinon le même chemin par défaut que
    memory_api.py calcule."""
    base = os.environ.get("MEMOIRE_ROOT")
    if base:
        return base
    racine_depot = os.path.dirname(os.path.dirname(SCRIPT_DIR))  # organes/ -> racine
    return os.path.join(
        racine_depot, ".claude", "skills", "memoire-beta", "scripts", "memoire_data"
    )


def _chemin_forces():
    return os.path.join(_racine_memoire(), "forces.json")


def _lire_forces_existantes():
    try:
        with open(_chemin_forces(), encoding="utf-8") as f:
            data = json.load(f)
        return dict(data) if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def calculer_forces(evenements=None, vitalite=None):
    """Calcule le multiplicateur de force par fiche à partir des capteurs
    porteurs d'un champ `fiche` non vide. Score net = (succès - échecs) pour
    cette fiche, sur TOUT l'historique ; multiplicateur = 1.0 ± pas fixe par
    unité de score net, borné à [FORCE_MIN, FORCE_MAX]. Fusionne avec les
    forces déjà présentes dans forces.json (préserve les réglages manuels des
    fiches sans capteur).

    `vitalite` (AJOUT PUR, opt-in) : dict optionnel {fiche: indice 0..1}
    (typiquement nexus_vitalite.indice_vitalite()). Défaut None = AUCUN
    changement de comportement historique — invariant préservé :
    calculer_forces() sans activité succes/echec reste {} (cf.
    test_orchestrateur_routage.test_observer_ok_laisse_calculer_forces_inerte).

    Quand `vitalite` est fourni, DEUX cas STRICTEMENT distincts (bug PR#86
    corrigé : la vitalité seule NE DOIT JAMAIS écraser une force déjà présente) :
      - fiche AVEC score succes/echec réel : formule HISTORIQUE inchangée
        (FORCE_DEFAUT + DELTA_SUCCES/DELTA_ECHEC), vitalité ADDITIONNÉE en plus.
      - fiche SANS aucun succes/echec (vitalité SEULE) : ADDITIVE sur ce qui
        existe déjà dans forces.json (forces.get(fiche, FORCE_DEFAUT)), JAMAIS
        un écrasement depuis FORCE_DEFAUT — une force manuelle/antérieure forte
        ne peut être dégradée par la seule vitalité.
    Les deux cas restent bornés à [FORCE_MIN, FORCE_MAX]."""
    if evenements is None:
        evenements = nexus_sense.lire()

    score = {}
    for ev in evenements:
        fiche = ev.get("fiche")
        if not fiche:
            continue
        statut = ev.get("statut")
        if statut == "succes":
            score[fiche] = score.get(fiche, 0) + 1
        elif statut == "echec":
            score[fiche] = score.get(fiche, 0) - 1

    forces = _lire_forces_existantes()

    if vitalite is None:
        for fiche, s in score.items():
            valeur = FORCE_DEFAUT + DELTA_SUCCES * max(s, 0) + DELTA_ECHEC * max(-s, 0)
            forces[fiche] = round(min(FORCE_MAX, max(FORCE_MIN, valeur)), 4)
        return forces

    fiches = set(score) | {fiche for fiche, idx in vitalite.items() if idx}
    for fiche in fiches:
        idx = vitalite.get(fiche) or 0.0
        if fiche in score:
            # Activité succes/echec réelle : formule HISTORIQUE, vitalité en plus.
            s = score[fiche]
            valeur = (FORCE_DEFAUT + DELTA_SUCCES * max(s, 0) + DELTA_ECHEC * max(-s, 0)
                      + DELTA_VITALITE_MAX * idx)
        else:
            # Vitalité SEULE : ADDITIVE sur la force existante, jamais un écrasement
            # depuis FORCE_DEFAUT (sinon une force manuelle/antérieure dégraderait).
            valeur = forces.get(fiche, FORCE_DEFAUT) + DELTA_VITALITE_MAX * idx
        forces[fiche] = round(min(FORCE_MAX, max(FORCE_MIN, valeur)), 4)
    return forces


def ecrire_forces(forces):
    chemin = _chemin_forces()
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(forces, f, ensure_ascii=False, indent=2, sort_keys=True)
    return chemin


def appliquer():
    """Appel de bibliothèque pour la boucle : calcule ET écrit directement
    (pas de dry-run ici — purement additif/recalculable, jamais destructif).
    Ne lève jamais : protège l'appelant (la boucle orchestrateur)."""
    try:
        forces = calculer_forces()
        ecrire_forces(forces)
        return forces
    except Exception:
        return {}


def compter_events_force(evenements=None):
    """Compte, PAR FICHE, les événements de force JUGÉS — la MATIÈRE de la porte
    à seuil. Miroir EXACT du filtre de calculer_forces (fiche non vide ET statut
    ∈ {succes, echec}), avec le MÊME repli LEGACY que le garde 98
    (statut_juge → statut) : un event d'avant l'ajout de statut_juge se rabat sur
    `statut`. Un 'ok'/'partiel' (inerte, ignoré par calculer_forces) n'est JAMAIS
    compté.

    Renvoie {fiche: n_par_fiche, "_total": n_total} où n_total est la somme des
    comptes de toutes les fiches. LECTURE SEULE : lit les capteurs via
    nexus_sense (comme calculer_forces), n'écrit rien, ne modifie rien.

    Fonction PURE et injectable (evenements fournis en test) : elle décide, pour
    chaque fiche, si son signal est assez fort pour que sa force pèse dans
    rank() (cf. SEUIL_FORCE_GLOBAL / SEUIL_FORCE_SLUG)."""
    if evenements is None:
        evenements = nexus_sense.lire()

    comptes = {}
    total = 0
    for ev in evenements:
        fiche = ev.get("fiche")
        if not fiche:
            continue
        # statut_juge = jugement humain (avant retrogradation) ; repli sur
        # `statut` pour les events LEGACY — exactement comme le garde 98.
        statut = ev.get("statut_juge")
        if statut is None:
            statut = ev.get("statut")
        if statut in ("succes", "echec"):
            comptes[fiche] = comptes.get(fiche, 0) + 1
            total += 1
    comptes["_total"] = total
    return comptes


# =========================================================================== #
# RECALL MULTI-SIGNAUX (lexical + sémantique + force vivante)
# ---------------------------------------------------------------------------
# Brique v1 : rank() fusionne trois signaux SANS jamais multiplier la
# pertinence par la force (la force additionne, elle ne domine pas).
#
#   • lexical    : pertinence(IDF) — le calcul HISTORIQUE de memory_api,
#                  rejoué à l'identique ici (rel_n = rel normalisée par le max
#                  des candidats).
#   • sémantique : cosinus d'un embedder INJECTÉ (jamais de réseau/clé/coût de
#                  notre part). 0 si aucun embedder n'est fourni.
#   • force      : force vivante f(force) ∈ [0,1], normalisation LINÉAIRE des
#                  constantes réelles FORCE_MIN/FORCE_MAX de ce module.
#
# RÉTROCOMPAT TOTALE : sans embedder, rank() reproduit STRICTEMENT le
# comportement actuel (score = pertinence(IDF) × force). Le nouveau modèle
# additif n'entre en jeu QUE si un embedder est injecté.
#
# Portée v1 ASSUMÉE : coût O(corpus) par requête, accepté à l'échelle du corpus
# réel (une centaine de fiches). Pas d'index d'embeddings persistant ici.
# =========================================================================== #

# --------------------------------------------------------------------------- #
# Poids de fusion — LES TROIS SONT EXPLICITEMENT PROVISOIRES.
# Ce ne sont PAS des valeurs neutres ni mesurées : ce sont des points de départ
# raisonnables, à réviser par l'instrumentation (cf. livraison de la brique).
# --------------------------------------------------------------------------- #

# alpha — part du signal sémantique dans la pertinence fusionnée.
#   pert = (1 - alpha) * rel_n + alpha * sem.
#   0.5 = PROVISOIRE (poids égal lexical/sémantique faute de mesure). PAS neutre,
#   PAS mesuré : à revoir dès qu'on saura, sur requêtes réelles, lequel des deux
#   signaux prédit le mieux la fiche effectivement utile.
POIDS_SEMANTIQUE_DEFAUT = 0.5  # PROVISOIRE

# beta — poids ADDITIF de la force vivante dans le score final.
#   score = pert + beta * f(force). JAMAIS pert * force.
#   PLAFONNÉ à la moitié du poids de la pertinence lexicale (1 - alpha) : au plein
#   régime (f(force)=1) la force n'ajoute au plus que ce plafond, incapable de
#   renverser un écart de pertinence normalisée ≥ 0.5. Elle DÉPARTAGE à pertinence
#   égale sans jamais DOMINER ni ÉCRASER la pertinence. Statut PROVISOIRE, même
#   nature que f(force) : forme choisie, non mesurée.
POIDS_FORCE_DEFAUT = 0.25  # PROVISOIRE (== plafond à alpha=0.5)

# gamma — poids ADDITIF du bonus de co-sélection de liens (nexus_liens) dans le
# score final. score = pert + beta*f(force) + gamma*liens_bonus. JAMAIS de
# multiplication. MÊME plafond structurel que beta : gamma = min(0.5*(1-alpha),
# max(0.0, poids_liens)) — au plein régime, le bonus de liens ne peut pas plus
# renverser un écart de pertinence que la force ne le peut. N'AGIT QUE sur le
# chemin additif (embedder fourni) : _rank_lexical (chemin légataire) ne reçoit
# jamais ce paramètre, structurellement impossible à casser depuis là. Statut
# PROVISOIRE (forme choisie, non mesurée), même nature que POIDS_FORCE_DEFAUT.
POIDS_LIENS_DEFAUT = 0.15  # PROVISOIRE

# seuil au-dessus duquel une fiche à fort score sémantique mais SANS recouvrement
# lexical est ajoutée au jeu candidat (élargissement). Réglé pour séparer un vrai
# rapprochement de surface (~0.6 sur EmbedderFake) du bruit (~0.1). PROVISOIRE.
SEUIL_ELARGISSEMENT_DEFAUT = 0.35  # PROVISOIRE

# Réglages de l'EmbedderFake de test (déterministe, hors production).
EMBED_NGRAM = 3
EMBED_DIM = 512

# Tokenisation lexicale : MÊME expression que memory_api (rétrocompat stricte).
_TOKEN_RE = re.compile(r"[0-9a-zà-ÿ_]+", re.IGNORECASE)


def _tokens(s):
    return _TOKEN_RE.findall((s or "").lower())


def _force_for(forces, fl, rel):
    """Multiplicateur d'une fiche (clé = nom complet, radical sans .md, ou chemin
    relatif ; défaut 1.0). Miroir EXACT de memory_api._force_for."""
    stem = fl[:-3] if fl.endswith(".md") else fl
    for key in (fl, stem, rel):
        if key in forces:
            return forces[key]
    return 1.0


def _count_for(comptes, fl, rel):
    """Nombre d'événements de force jugés POUR une fiche — résolu par la MÊME clé
    que _force_for (nom complet, radical sans .md, ou chemin relatif), pour que le
    compte et la force d'une fiche se retrouvent TOUJOURS sous la même clé. 0 si
    aucune correspondance. Miroir EXACT de _force_for, côté comptes."""
    stem = fl[:-3] if fl.endswith(".md") else fl
    for key in (fl, stem, rel):
        if key in comptes:
            return comptes[key]
    return 0


def _porte_force_ouverte(comptes, total, fl, rel):
    """PORTE À SEUIL : la force de cette fiche a-t-elle le droit de peser ?
    Ouverte SEULEMENT si le signal global ET le signal propre à la fiche sont
    tous deux suffisants (total ≥ SEUIL_FORCE_GLOBAL ET n_fiche ≥
    SEUIL_FORCE_SLUG). Sinon fermée → force NEUTRE en aval."""
    return total >= SEUIL_FORCE_GLOBAL and _count_for(comptes, fl, rel) >= SEUIL_FORCE_SLUG


def _rank_lexical(query, cands, forces=None, comptes=None):
    """Classement pertinence(IDF) × force EFFECTIVE — MIROIR STRICT de
    memory_api.rank_candidates quand la porte est ouverte. C'est le chemin de
    RÉTROCOMPAT : rank() sans embedder délègue ici.

    Force EFFECTIVE : la force réelle de la fiche SI sa porte à seuil est ouverte,
    SINON FORCE_DEFAUT (1.0, multiplicateur neutre) — la force ne peut alors ni
    monter ni descendre la fiche. Au régime nominal (portes ouvertes) la sortie
    est BYTE-IDENTIQUE à l'historique (force_eff == force, _score == rel × force).
    Les comptes viennent de compter_events_force (calculés une fois par appel,
    injectables ; lus ici seulement s'ils ne sont pas fournis)."""
    if forces is None:
        forces = _lire_forces_existantes()
    if comptes is None:
        comptes = compter_events_force()
    total = comptes.get("_total", 0)
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
        # PORTE À SEUIL : force réelle seulement si le signal suffit, sinon neutre.
        if _porte_force_ouverte(comptes, total, c.get("file", ""), c.get("path", "")):
            force_eff = force
        else:
            force_eff = FORCE_DEFAUT
        item = dict(c)
        item["_relevance"] = rel
        item["_force"] = force_eff
        item["_score"] = rel * force_eff
        ranked.append(item)
    ranked.sort(key=lambda x: (-x["_score"], x.get("path", ""), x.get("file", "")))
    return ranked


def f_force(force):
    """Force vivante normalisée dans [0,1] : normalisation LINÉAIRE
    (force - FORCE_MIN) / (FORCE_MAX - FORCE_MIN), BORNÉE aux vraies constantes
    du module (FORCE_MIN=0.2, FORCE_MAX=5.0) même si forces.json contient une
    valeur hors plage. Statut PROVISOIRE (forme choisie, non mesurée)."""
    f = min(FORCE_MAX, max(FORCE_MIN, force))
    return (f - FORCE_MIN) / (FORCE_MAX - FORCE_MIN)


def _clamp01(x):
    return max(0.0, min(1.0, x))


def _normaliser_texte(text):
    """minuscule + sans accents + alphanumérique/espaces : maximise le
    recouvrement de n-grammes entre 'reformulé' et 'reformulation'."""
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9 ]", " ", t.lower())


def _ngrams_caracteres(text, n):
    """n-grammes de caractères par mot, bornés par des marqueurs de frontière
    (#mot#) pour que le début/la fin d'un mot comptent."""
    out = []
    for mot in _normaliser_texte(text).split():
        w = "#" + mot + "#"
        for i in range(len(w) - n + 1):
            out.append(w[i:i + n])
    return out


class EmbedderFake:
    """Embedder DÉTERMINISTE de TEST (jamais en production) : projette un texte
    sur un vecteur de comptes de n-grammes de caractères, hachés dans EMBED_DIM
    cases via un hachage STABLE (md5, pas le hash() salé de Python).

    LIMITE ASSUMÉE : ne capte QUE la proximité de SURFACE (caractères partagés).
    Deux vrais synonymes sans n-grammes communs (« voiture » / « automobile »)
    ont une similarité ≈ 0 — cf. le test xfail dédié. Un vrai embedder sémantique
    (geste ultérieur de Kily) lèvera cette limite SANS changer rank()."""

    def __init__(self, n=EMBED_NGRAM, dim=EMBED_DIM):
        self.n = n
        self.dim = dim

    def embed(self, text):
        vec = [0.0] * self.dim
        for g in _ngrams_caracteres(text, self.n):
            h = int(hashlib.md5(g.encode("utf-8")).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        return vec


def _cosine(a, b):
    """Cosinus BORNÉ [0,1]. Lève ValueError si les dimensions diffèrent (capté
    plus haut pour dégrader vers le lexical)."""
    if len(a) != len(b):
        raise ValueError("dimensions d'embedding incompatibles: %d vs %d" % (len(a), len(b)))
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return _clamp01(dot / (na * nb))


def _embed_robuste(embedder, text):
    """Vecteur de l'embedder, ou None si l'embedder échoue (jamais de crash)."""
    try:
        return embedder.embed(text)
    except Exception:
        return None


def _sem(embedder, qvec, text):
    """Similarité sémantique bornée [0,1]. ROBUSTE : toute défaillance de
    l'embedder (exception, mauvaise dimension) dégrade PROPREMENT vers 0.0
    (= lexical seul pour cette fiche), jamais de crash."""
    if qvec is None:
        return 0.0
    try:
        return _cosine(qvec, embedder.embed(text))
    except Exception:
        return 0.0


# Queue de métadonnées d'un titre de fiche : « — domaine: X / catégorie: Y ».
# Les fiches ont la forme `# <Titre> — domaine: X / catégorie: Y`. On coupe cette
# queue pour ne garder que le TITRE (signal sémantique dense), jamais le
# boilerplate. Tolère em-dash (—), en-dash (–) ou tiret (-) devant « domaine: ».
_QUEUE_META_TITRE_RE = re.compile(r"\s*[—–-]\s*domaine\s*:.*$", re.IGNORECASE | re.DOTALL)


def _titre_fiche(cand):
    """TITRE de la fiche pour l'embedding sémantique : 1re ligne de titre markdown
    de `cand['excerpt']` (ligne commençant par '#'), '#' retirés et queue de
    métadonnées « — domaine: … / catégorie: … » COUPÉE. Le titre seul est un
    signal plus dense que le texte complet tronqué (boilerplate dilué → mesuré
    le 10/07 : recall@3 des reformulations synonymes 2/10 → 3/10, r@1 0 → 1).

    Fallbacks DÉTERMINISTES si aucun titre — JAMAIS une chaîne vide, JAMAIS
    d'exception : nom de fichier dé-sluggé (tirets → espaces, sans .md), puis
    `_search` / `excerpt`."""
    excerpt = cand.get("excerpt") or ""
    for ligne in excerpt.splitlines():
        s = ligne.strip()
        if s.startswith("#"):
            titre = _QUEUE_META_TITRE_RE.sub("", s.lstrip("#").strip()).strip()
            if titre:
                return titre
            break  # ligne de titre présente mais vide après coupe → fallback
    # Fallback 1 : nom de fichier dé-sluggé (tirets/underscores → espaces, sans .md).
    fichier = cand.get("file") or ""
    stem = fichier[:-3] if fichier.endswith(".md") else fichier
    desslug = stem.replace("-", " ").replace("_", " ").strip()
    if desslug:
        return desslug
    # Fallback 2 : texte de recherche / excerpt — jamais vide au-delà de ça.
    return cand.get("_search") or excerpt or ""


def _texte_fiche(cand):
    """Texte embarqué pour l'embedding sémantique : le TITRE SEUL (dense), PAS le
    texte complet tronqué (`_search`, dilué par le boilerplate). Utilisé UNIQUEMENT
    sur le chemin embedder — le défaut lexical (embedder=None) reste byte-identique."""
    return _titre_fiche(cand)


def _liens_id_for(fl):
    """Identité d'une fiche pour nexus_liens : radical sans « .md » — MÊME
    convention que nexus_liens (fiches.id = fl[:-3]). `fl` est un nom de
    fichier (« file » d'un candidat rank()), jamais un chemin complet."""
    return fl[:-3] if fl.endswith(".md") else fl


def _liens_bonus_for(graphe_liens, fl, cands_ids):
    """Bonus de CO-SÉLECTION : le plus fort poids d'arête (via nexus_liens.
    voisins) entre la fiche `fl` et un AUTRE candidat DÉJÀ présent dans
    `cands_ids` — le jeu de candidats de CET appel de rank(), calculé sur le
    POOL FINAL (après élargissement sémantique éventuel).

    N'ÉLARGIT JAMAIS le jeu de candidats via les liens (contrairement au
    sémantique avec `semantique_ouvre_candidats`) : un voisin absent de
    `cands_ids` est ignoré, jamais ajouté.

    0.0 si `graphe_liens` est None/vide, si aucun voisin n'est dans
    `cands_ids`, ou si le seul voisin trouvé est la fiche elle-même."""
    if not graphe_liens:
        return 0.0
    fid = _liens_id_for(fl)
    meilleur = 0.0
    for v in nexus_liens.voisins(graphe_liens, fid):
        voisin = v.get("voisin")
        if not voisin or voisin == fid:
            continue
        if voisin in cands_ids:
            poids = v.get("poids", 0.0)
            if poids > meilleur:
                meilleur = poids
    return meilleur


def rank(query, candidates, forces=None, embedder=None,
         poids_semantique=POIDS_SEMANTIQUE_DEFAUT,
         poids_force=POIDS_FORCE_DEFAUT,
         semantique_ouvre_candidats=False,
         seuil_semantique_elargissement=SEUIL_ELARGISSEMENT_DEFAUT,
         corpus=None, comptes_force=None,
         liens=None, poids_liens=POIDS_LIENS_DEFAUT):
    """Classe des candidats (chacun portant « _search », « file », « path »).

    RÉTROCOMPAT : `embedder=None` → comportement HISTORIQUE strictement
    identique (score = pertinence(IDF) × force) au régime NOMINAL, forme de
    retour inchangée. `liens`/`poids_liens` sont IGNORÉS sur ce chemin : ils
    n'agissent QUE sur le chemin additif (embedder fourni), structurellement
    impossible à casser depuis le chemin légataire (_rank_lexical ne reçoit
    jamais ces paramètres).

    Avec un embedder injecté, fusion multi-signaux ADDITIVE :
        rel_n = pertinence(IDF) normalisée par le max des candidats  ∈ [0,1]
        sem   = cosinus(embedder(query), embedder(fiche))            ∈ [0,1]
        pert  = (1 - alpha) * rel_n + alpha * sem                    ∈ [0,1]
        score = pert + beta * f(force) + gamma * liens_bonus  (JAMAIS de ×)

    `liens` (nexus_liens.construire_liens(), optionnel) : `liens_bonus` = le
    plus fort poids d'arête vers un AUTRE candidat déjà présent dans le jeu de
    candidats de CET appel (cf. `_liens_bonus_for`) — 0.0 par défaut
    (`liens=None`), ce qui rend le score BYTE-IDENTIQUE à avant l'ajout de ce
    paramètre. Le jeu de candidats n'est JAMAIS élargi via les liens
    (contrairement au sémantique) : un voisin absent du jeu ne compte pas.

    PORTE À SEUIL de la force (les DEUX chemins) : la force d'une fiche n'influence
    le classement QUE si son signal jugé est suffisant (cf. compter_events_force /
    SEUIL_FORCE_GLOBAL / SEUIL_FORCE_SLUG). Sous seuil elle est NEUTRE — additif :
    f(force) forcé à 0 (beta·f = 0, ni bonus ni pénalité) ; légataire : force_eff
    = FORCE_DEFAUT (multiplicateur 1.0). Les comptes viennent de
    compter_events_force(), calculés UNE FOIS par appel (injectables via
    `comptes_force` pour les tests).

    `semantique_ouvre_candidats=True` (+ embedder + `corpus`) : le sémantique
    ÉLARGIT le jeu candidat — des fiches à fort sem mais SANS recouvrement
    lexical (seuil `seuil_semantique_elargissement`) sont ajoutées, pas
    seulement reclassées. Sans `corpus`, aucun élargissement possible.

    Fonction PURE : lecture seule (chargement optionnel de forces.json et des
    capteurs pour les comptes, sauf `comptes_force` injecté), ne modifie pas
    `candidates` en place."""
    # Comptes de force calculés UNE SEULE FOIS par appel (injectables en test).
    comptes = comptes_force if comptes_force is not None else compter_events_force()
    total = comptes.get("_total", 0)

    # --- Chemin de RÉTROCOMPAT : aucun embedder → aucun signal sémantique. --- #
    # `liens`/`poids_liens` n'existent PAS pour _rank_lexical : structurellement
    # impossible à casser depuis ce chemin.
    if embedder is None:
        return _rank_lexical(query, candidates, forces, comptes)

    if forces is None:
        forces = _lire_forces_existantes()
    alpha = _clamp01(poids_semantique)
    # PLAFOND de la force : jamais plus que la moitié du poids de la pertinence.
    beta = min(0.5 * (1.0 - alpha), max(0.0, poids_force))
    # MÊME plafond pour le bonus de liens.
    gamma = min(0.5 * (1.0 - alpha), max(0.0, poids_liens))

    qvec = _embed_robuste(embedder, query)

    # 1) Base lexicale : pertinence(IDF) via le MÊME calcul (rel, force).
    pool = _rank_lexical(query, candidates, forces, comptes)
    for it in pool:
        it["_sem"] = _sem(embedder, qvec, _texte_fiche(it))

    # 2) Élargissement sémantique optionnel : fiches à fort sem SANS lexical.
    if semantique_ouvre_candidats and corpus and qvec is not None:
        deja = {(c.get("path"), c.get("file")) for c in pool}
        for c in corpus:
            cle = (c.get("path"), c.get("file"))
            if cle in deja:
                continue
            s = _sem(embedder, qvec, _texte_fiche(c))
            if s >= seuil_semantique_elargissement:
                item = dict(c)
                item["_relevance"] = 0.0          # aucun recouvrement lexical
                item["_force"] = _force_for(forces, c.get("file", ""), c.get("path", ""))
                item["_sem"] = s
                pool.append(item)
                deja.add(cle)

    # 3) Normalisation lexicale par le max du POOL FINAL (élargissement compris).
    max_rel = max((it.get("_relevance", 0.0) for it in pool), default=0.0)

    # jeu de candidats de CET appel pour le bonus de liens — le POOL FINAL
    # (élargissement sémantique compris), JAMAIS élargi par les liens eux-mêmes.
    cands_ids = {_liens_id_for(it.get("file", "")) for it in pool}

    # 4) Fusion additive + score final (jamais de multiplication terminale).
    ranked = []
    for it in pool:
        rel = it.get("_relevance", 0.0)
        rel_n = (rel / max_rel) if max_rel > 0 else 0.0
        sem = it.get("_sem", 0.0)
        pert = (1.0 - alpha) * rel_n + alpha * sem
        # Force RÉELLE de la fiche (indépendante du _force éventuellement
        # neutralisé par _rank_lexical), et PORTE À SEUIL : sous seuil, f(force)
        # est forcé à 0 → beta·f = 0, la force ne peut NI monter NI descendre la
        # fiche. Au régime nominal (porte ouverte), f(force) == f_force(réelle),
        # score BYTE-IDENTIQUE à l'historique.
        force = _force_for(forces, it.get("file", ""), it.get("path", ""))
        if _porte_force_ouverte(comptes, total, it.get("file", ""), it.get("path", "")):
            ff = f_force(force)
        else:
            ff = 0.0
        liens_bonus = _liens_bonus_for(liens, it.get("file", ""), cands_ids)
        item = dict(it)
        item["_relevance"] = rel
        item["_rel_n"] = rel_n
        item["_sem"] = sem
        item["_pert"] = pert
        item["_force"] = force
        item["_f_force"] = ff
        item["_liens_bonus"] = liens_bonus
        item["_score"] = pert + beta * ff + gamma * liens_bonus
        ranked.append(item)
    ranked.sort(key=lambda x: (-x["_score"], x.get("path", ""), x.get("file", "")))
    return ranked


def histogramme_forces(forces=None, bornes=(0.2, 0.8, 1.0, 1.2, 2.0, 5.0)):
    """Histogramme simple de la distribution des forces (instrumentation du
    paramètre provisoire f(force)). Sans argument, calcule sur le corpus réel via
    calculer_forces(). Renvoie {tranche: nombre_de_fiches}. Lecture seule."""
    if forces is None:
        forces = calculer_forces()
    seuils = sorted(set(bornes))
    hist = {}
    for i, hi in enumerate(seuils):
        lo = seuils[i - 1] if i else FORCE_MIN
        hist["]%.2f..%.2f]" % (lo, hi)] = 0
    valeurs = list(forces.values()) if forces else []
    for v in valeurs:
        for i, hi in enumerate(seuils):
            lo = seuils[i - 1] if i else FORCE_MIN
            if (i == 0 and v <= hi) or (lo < v <= hi):
                hist["]%.2f..%.2f]" % (lo, hi)] += 1
                break
    return {"n_fiches": len(valeurs), "tranches": hist}


def main():
    apply = "--apply" in sys.argv
    forces = calculer_forces()
    print("🔗 NEXUS — Pont capteurs → forces (force vivante)\n")
    if not forces:
        print("📭 Aucune fiche avec capteur : rien à calculer.")
    else:
        for fiche, mult in sorted(forces.items()):
            print(f"   • {fiche} : ×{mult}")
    if apply:
        chemin = ecrire_forces(forces)
        print(f"\n✅ Écrit dans {chemin}")
    else:
        print(f"\n🛡️  DRY-RUN : rien écrit. Relancer avec --apply pour écrire "
              f"{_chemin_forces()}.")


if __name__ == "__main__":
    main()
