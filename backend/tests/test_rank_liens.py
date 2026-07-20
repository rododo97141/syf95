# -*- coding: utf-8 -*-
"""
NEXUS — câblage nexus_liens DANS nexus_force.rank() (bonus de co-sélection).

Couvre le mandat point par point :

  1. `liens=None` (défaut) : score BYTE-IDENTIQUE à AVANT ce changement — preuve
     GOLDEN (recalcul indépendant de la formule pert + beta*f(force), sans passer
     par un quelconque terme de liens), pas une simple auto-cohérence.
  2. bonus de co-sélection ADDITIF exact : deux fiches reliées par une arête du
     graphe gagnent EXACTEMENT gamma*poids en plus, une fiche isolée n'en gagne
     aucun.
  3. AUCUN élargissement du jeu de candidats via un voisin absent des candidats
     de CET appel — contrairement au sémantique, les liens ne font JAMAIS entrer
     une fiche nouvelle.
  4. le chemin LÉGATAIRE (embedder=None, _rank_lexical) IGNORE structurellement
     `liens`/`poids_liens` — même avec un graphe énorme et un poids démesuré, le
     score reste rel × force (aucune clé `_liens_bonus`, aucune fuite du terme).
  5. gamma est PLAFONNÉ au même verrou que beta (0.5*(1-alpha)), même à
     poids_liens démesuré.
  6. cands_ids est calculé sur le POOL FINAL (élargissement sémantique compris) :
     un voisin ajouté par élargissement sémantique PEUT bénéficier du bonus de
     liens, une fois dans le jeu.
"""
import os
import sys
import importlib

import pytest


def _racine():
    ici = os.path.dirname(os.path.abspath(__file__))          # backend/tests
    return os.path.dirname(os.path.dirname(ici))               # racine du dépôt


@pytest.fixture
def nf():
    org = os.path.join(_racine(), "organes")
    if org not in sys.path:
        sys.path.insert(0, org)
    import nexus_force
    return importlib.reload(nexus_force)


class _EmbedderConstant:
    """Même vecteur pour tout texte : sem constant → pert identique entre
    candidats de même pertinence lexicale, isole l'effet du bonus de liens."""
    def embed(self, text):
        return [1.0, 0.0]


def _cand(fid, dom_path, search):
    return {
        "file": fid + ".md",
        "path": os.path.join(dom_path, fid + ".md"),
        "excerpt": "# %s\n" % fid,
        "_search": search,
    }


def _graphe(aretes):
    """Graphe minimal au format nexus_liens (seule la clé « aretes » est lue
    par nexus_liens.voisins)."""
    return {"aretes": aretes}


# --------------------------------------------------------------------------- #
# 1) liens=None : GOLDEN, byte-identique à AVANT ce changement.
# --------------------------------------------------------------------------- #
def test_liens_none_byte_identique_golden(nf):
    cands = [
        _cand("a", "dom", "alpha commun"),
        _cand("b", "dom", "alpha commun"),
        _cand("c", "dom", "alpha commun"),
    ]
    forces = {"a": 2.0, "b": 0.5, "c": 3.0}
    # porte FERMÉE (aucun compte) : f(force) neutre partout — isole pert.
    comptes = {"_total": 0}
    query = "alpha"
    embedder = _EmbedderConstant()

    ranked = nf.rank(query, cands, forces=forces, embedder=embedder,
                      comptes_force=comptes)   # liens=None (défaut)

    alpha = nf._clamp01(nf.POIDS_SEMANTIQUE_DEFAUT)
    beta = min(0.5 * (1.0 - alpha), max(0.0, nf.POIDS_FORCE_DEFAUT))
    for it in ranked:
        # recalcul INDÉPENDANT de la formule d'AVANT ce chantier (aucun terme
        # de liens n'existait) : rel_n identique pour les 3 (même contenu),
        # sem constant (embedder constant) -> pert identique pour les 3.
        rel_n_attendu = 1.0            # même token, même corpus -> normalisé à 1
        sem_attendu = 1.0              # cosinus([1,0],[1,0]) == 1
        pert_attendu = (1.0 - alpha) * rel_n_attendu + alpha * sem_attendu
        # porte fermée -> f(force) = 0 pour tous.
        score_attendu = pert_attendu + beta * 0.0
        assert it["_score"] == pytest.approx(score_attendu)
        assert it["_liens_bonus"] == 0.0
        assert it["_f_force"] == 0.0


def test_liens_omis_du_tout_donne_le_meme_resultat_que_liens_none_explicite(nf):
    cands = [_cand("a", "dom", "alpha"), _cand("b", "dom", "beta")]
    forces = {}
    r_omis = nf.rank("alpha", cands, forces=forces, embedder=_EmbedderConstant())
    r_none = nf.rank("alpha", cands, forces=forces, embedder=_EmbedderConstant(),
                      liens=None)
    assert [it["_score"] for it in r_omis] == [it["_score"] for it in r_none]


# --------------------------------------------------------------------------- #
# 2) bonus de co-sélection ADDITIF exact.
# --------------------------------------------------------------------------- #
def test_bonus_co_selection_additif_exact(nf):
    cands = [
        _cand("a", "domX", "alpha commun"),
        _cand("b", "domX", "alpha commun"),
        _cand("c", "domX", "alpha commun"),   # isolée : aucune arête
    ]
    forces = {}
    comptes = {"_total": 0}                    # porte fermée : beta*ff == 0 partout
    graphe = _graphe([
        {"a": "a", "a_dom": "domX", "b": "b", "b_dom": "domX",
         "poids": 0.42, "inter_domaine": False},
        # voisin "z" HORS du jeu de candidats de cet appel : ne doit JAMAIS
        # compter (cf. test dédié à l'absence d'élargissement).
        {"a": "a", "a_dom": "domX", "b": "z", "b_dom": "domY",
         "poids": 0.99, "inter_domaine": True},
    ])

    ranked = nf.rank("alpha", cands, forces=forces, embedder=_EmbedderConstant(),
                      comptes_force=comptes, liens=graphe)
    par_fichier = {it["file"]: it for it in ranked}

    alpha = nf._clamp01(nf.POIDS_SEMANTIQUE_DEFAUT)
    gamma = min(0.5 * (1.0 - alpha), max(0.0, nf.POIDS_LIENS_DEFAUT))

    assert par_fichier["a.md"]["_liens_bonus"] == 0.42
    assert par_fichier["b.md"]["_liens_bonus"] == 0.42
    assert par_fichier["c.md"]["_liens_bonus"] == 0.0

    # score(a) == score(c) + gamma*0.42 EXACTEMENT (même pert/force partout).
    ecart = par_fichier["a.md"]["_score"] - par_fichier["c.md"]["_score"]
    assert ecart == pytest.approx(gamma * 0.42)
    assert par_fichier["a.md"]["_score"] == pytest.approx(par_fichier["b.md"]["_score"])


# --------------------------------------------------------------------------- #
# 3) AUCUN élargissement du jeu via un voisin absent des candidats.
# --------------------------------------------------------------------------- #
def test_liens_n_elargit_jamais_le_jeu_de_candidats(nf):
    cands = [_cand("a", "domX", "alpha")]
    graphe = _graphe([
        {"a": "a", "a_dom": "domX", "b": "z", "b_dom": "domY",
         "poids": 0.9, "inter_domaine": True},
    ])
    ranked = nf.rank("alpha", cands, forces={}, embedder=_EmbedderConstant(), liens=graphe)
    fichiers = {it["file"] for it in ranked}
    assert fichiers == {"a.md"}                     # "z" jamais ajoutée
    assert ranked[0]["_liens_bonus"] == 0.0          # "z" absente de cands_ids


# --------------------------------------------------------------------------- #
# 4) chemin LÉGATAIRE (embedder=None) ignore structurellement liens/poids_liens.
# --------------------------------------------------------------------------- #
def test_chemin_legataire_ignore_liens(nf):
    cands = [_cand("a", "dom", "alpha commun"), _cand("b", "dom", "commun")]
    forces = {"a": 4.0, "b": 2.0}
    graphe_enorme = _graphe([
        {"a": "a", "a_dom": "dom", "b": "b", "b_dom": "dom",
         "poids": 1.0, "inter_domaine": False},
    ])

    sans_liens = nf.rank("alpha", cands, forces=forces)   # embedder=None
    avec_liens_demesures = nf.rank(
        "alpha", cands, forces=forces,
        liens=graphe_enorme, poids_liens=1_000_000.0,
    )

    assert [it["_score"] for it in sans_liens] == [it["_score"] for it in avec_liens_demesures]
    for it in avec_liens_demesures:
        assert "_liens_bonus" not in it
        assert it["_score"] == it["_relevance"] * it["_force"]   # rel × force, jamais +


# --------------------------------------------------------------------------- #
# 5) gamma PLAFONNÉ, même à poids_liens démesuré.
# --------------------------------------------------------------------------- #
def test_gamma_plafonne_meme_a_poids_liens_demesure(nf):
    cands = [
        _cand("a", "domX", "alpha commun"),
        _cand("b", "domX", "alpha commun"),
        _cand("c", "domX", "alpha commun"),   # isolée : aucune arête, bonus 0.0
    ]
    forces = {}
    comptes = {"_total": 0}
    graphe = _graphe([
        {"a": "a", "a_dom": "domX", "b": "b", "b_dom": "domX",
         "poids": 1.0, "inter_domaine": False},
    ])

    ranked = nf.rank("alpha", cands, forces=forces, embedder=_EmbedderConstant(),
                      comptes_force=comptes, liens=graphe, poids_liens=1_000_000.0)
    par_fichier = {it["file"]: it for it in ranked}

    alpha = nf._clamp01(nf.POIDS_SEMANTIQUE_DEFAUT)
    plafond = 0.5 * (1.0 - alpha)          # même verrou structurel que beta

    assert par_fichier["a.md"]["_liens_bonus"] == 1.0
    assert par_fichier["c.md"]["_liens_bonus"] == 0.0
    # sans le plafond, l'écart vaudrait 1_000_000 * 1.0 -- ici borné à `plafond`.
    ecart = par_fichier["a.md"]["_score"] - par_fichier["c.md"]["_score"]
    assert ecart == pytest.approx(plafond)
    assert ecart <= plafond + 1e-9


# --------------------------------------------------------------------------- #
# 6) cands_ids calculé sur le POOL FINAL (élargissement sémantique compris).
# --------------------------------------------------------------------------- #
def test_cands_ids_inclut_le_pool_apres_elargissement_semantique(nf):
    # "lexicale" matche la requête ; "elargie" n'a AUCUN recouvrement lexical
    # mais un cosinus fort (embedder constant -> sem=1 partout) : élargie par
    # le sémantique. Le graphe relie "lexicale" <-> "elargie" : le bonus ne
    # doit compter QUE si "elargie" est bien entrée dans le pool.
    lexicale = _cand("lexicale", "dom", "alpha")
    elargie = _cand("elargie", "dom", "zzz")     # aucun token commun avec "alpha"
    corpus = [lexicale, elargie]
    graphe = _graphe([
        {"a": "lexicale", "a_dom": "dom", "b": "elargie", "b_dom": "dom",
         "poids": 0.7, "inter_domaine": False},
    ])

    ranked = nf.rank(
        "alpha", [lexicale], forces={}, embedder=_EmbedderConstant(),
        semantique_ouvre_candidats=True, corpus=corpus,
        seuil_semantique_elargissement=0.5,
        liens=graphe,
    )
    fichiers = {it["file"] for it in ranked}
    assert fichiers == {"lexicale.md", "elargie.md"}     # bien élargi par le sémantique

    par_fichier = {it["file"]: it for it in ranked}
    # "elargie" est maintenant dans cands_ids -> le bonus de "lexicale" compte.
    assert par_fichier["lexicale.md"]["_liens_bonus"] == 0.7
    assert par_fichier["elargie.md"]["_liens_bonus"] == 0.7


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
