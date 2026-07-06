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

# Pas de gagnant écrasant : petit pas par événement, borné.
DELTA_SUCCES = 0.2
DELTA_ECHEC = -0.1
FORCE_DEFAUT = 1.0
FORCE_MIN = 0.2
FORCE_MAX = 5.0


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


def calculer_forces(evenements=None):
    """Calcule le multiplicateur de force par fiche à partir des capteurs
    porteurs d'un champ `fiche` non vide. Score net = (succès - échecs) pour
    cette fiche, sur TOUT l'historique ; multiplicateur = 1.0 ± pas fixe par
    unité de score net, borné à [FORCE_MIN, FORCE_MAX]. Fusionne avec les
    forces déjà présentes dans forces.json (préserve les réglages manuels des
    fiches sans capteur)."""
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
    for fiche, s in score.items():
        valeur = FORCE_DEFAUT + DELTA_SUCCES * max(s, 0) + DELTA_ECHEC * max(-s, 0)
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


def _rank_lexical(query, cands, forces=None):
    """Classement pertinence(IDF) × force — MIROIR STRICT de
    memory_api.rank_candidates. C'est le chemin de RÉTROCOMPAT : rank() sans
    embedder délègue ici et renvoie exactement la forme/le score historiques."""
    if forces is None:
        forces = _lire_forces_existantes()
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


def _texte_fiche(cand):
    return cand.get("_search") or cand.get("excerpt") or ""


def rank(query, candidates, forces=None, embedder=None,
         poids_semantique=POIDS_SEMANTIQUE_DEFAUT,
         poids_force=POIDS_FORCE_DEFAUT,
         semantique_ouvre_candidats=False,
         seuil_semantique_elargissement=SEUIL_ELARGISSEMENT_DEFAUT,
         corpus=None):
    """Classe des candidats (chacun portant « _search », « file », « path »).

    RÉTROCOMPAT : `embedder=None` → comportement HISTORIQUE strictement
    identique (score = pertinence(IDF) × force), forme de retour inchangée.

    Avec un embedder injecté, fusion multi-signaux ADDITIVE :
        rel_n = pertinence(IDF) normalisée par le max des candidats  ∈ [0,1]
        sem   = cosinus(embedder(query), embedder(fiche))            ∈ [0,1]
        pert  = (1 - alpha) * rel_n + alpha * sem                    ∈ [0,1]
        score = pert + beta * f(force)      (JAMAIS pert * force)

    `semantique_ouvre_candidats=True` (+ embedder + `corpus`) : le sémantique
    ÉLARGIT le jeu candidat — des fiches à fort sem mais SANS recouvrement
    lexical (seuil `seuil_semantique_elargissement`) sont ajoutées, pas
    seulement reclassées. Sans `corpus`, aucun élargissement possible.

    Fonction PURE : ne lit/écrit aucun fichier hors chargement optionnel de
    forces.json (lecture seule), ne modifie pas `candidates` en place."""
    # --- Chemin de RÉTROCOMPAT : aucun embedder → aucun signal sémantique. --- #
    if embedder is None:
        return _rank_lexical(query, candidates, forces)

    if forces is None:
        forces = _lire_forces_existantes()
    alpha = _clamp01(poids_semantique)
    # PLAFOND de la force : jamais plus que la moitié du poids de la pertinence.
    beta = min(0.5 * (1.0 - alpha), max(0.0, poids_force))

    qvec = _embed_robuste(embedder, query)

    # 1) Base lexicale : pertinence(IDF) via le MÊME calcul (rel, force).
    pool = _rank_lexical(query, candidates, forces)
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

    # 4) Fusion additive + score final (jamais de multiplication terminale).
    ranked = []
    for it in pool:
        rel = it.get("_relevance", 0.0)
        rel_n = (rel / max_rel) if max_rel > 0 else 0.0
        sem = it.get("_sem", 0.0)
        pert = (1.0 - alpha) * rel_n + alpha * sem
        force = it.get("_force", 1.0)
        ff = f_force(force)
        item = dict(it)
        item["_relevance"] = rel
        item["_rel_n"] = rel_n
        item["_sem"] = sem
        item["_pert"] = pert
        item["_force"] = force
        item["_f_force"] = ff
        item["_score"] = pert + beta * ff
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
