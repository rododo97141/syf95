"""Tests du gardien 98 — seuils de DANGER pour la redondance et la saturation
(mandat NEXUS 19/07 — réparation vérifiée).

CONTEXTE (mesuré le 19/07 sur la base réelle) : redondance = 6 paires / 288
paires intra-catégorie possibles = 2,08 % ; remplissage = 78,5 %. Les seuils
d'AVANT ce mandat allumaient un signal en PERMANENCE sur cette base saine —
alarme muette par sur-sensibilité :
  • red_danger = redondances >= 3 (un COMPTE BRUT, pas invariant d'échelle) ;
  • sat_danger = remplissage >= 50 % (un cap=200 arbitraire, 50 % n'est pas un
    dommage — Danger Theory : on réagit au dommage réel, pas à un niveau nominal).

Ce qu'on prouve ici :
  (a) paires_intra_cat_possibles / taux_redondance : fonctions PURES, invariant
      d'échelle, défensives (jamais de ZeroDivisionError) ;
  (b) base SAINE réelle (taux ≈ 2,2 %, remplissage 78,5 %) → AUCUN signal de
      redondance ni de saturation ;
  (c) base DÉGRADÉE (+5 doublons injectés dans une même catégorie) → le taux de
      redondance franchit 3,0 % → signal 'redondance élevée'.

MUTATIONS ROUGES couvertes :
  (i)   revenir à un COMPTE brut (redondances >= 3) → test (b) repasserait au
        ROUGE (la base saine, non dégradée, signalerait quand même) ;
  (ii)  garder le seuil de saturation à 50 % → test (b) ROUGE (78,5 % signalerait) ;
  (iii) ne pas faire monter le signal après les +5 doublons → test (c) ROUGE.
"""
import os
import sys
import importlib.util

import pytest


ICI = os.path.dirname(os.path.abspath(__file__))              # backend/tests
RACINE = os.path.dirname(os.path.dirname(ICI))                # racine du dépôt
ORGANES = os.path.join(RACINE, "organes")
if ORGANES not in sys.path:
    sys.path.insert(0, ORGANES)


def _charger(nom, chemin):
    spec = importlib.util.spec_from_file_location(nom, chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def n98():
    return _charger("nexus_98_seuils_test", os.path.join(ORGANES, "nexus_98.py"))


def _fiche(file, excerpt):
    return {"file": file, "excerpt": excerpt}


def _fiches_uniques(n, prefixe):
    """`n` fiches au vocabulaire totalement DISJOINT (jaccard = 0 entre elles ET
    avec toute autre fiche) : chaque mot porte l'indice `i`, donc jamais partagé."""
    return [_fiche(f"{prefixe}{i}.md",
                    f"motunique{i}alpha motunique{i}beta motunique{i}gamma motunique{i}delta")
            for i in range(n)]


def _fiches_dupliquees(template, n, prefixe):
    """`n` fiches PORTANT LE MÊME texte (jaccard = 1.0 entre toute paire)."""
    return [_fiche(f"{prefixe}{i}.md", template) for i in range(n)]


# =========================================================================== #
# (a) paires_intra_cat_possibles — PURE, invariant du nombre de catégories.
# =========================================================================== #
def test_paires_intra_cat_possibles_somme_les_combinaisons_par_categorie(n98):
    groupes = {
        ("d", "a"): [{"file": "1"}, {"file": "2"}, {"file": "3"}],   # C(3,2)=3
        ("d", "b"): [{"file": "4"}, {"file": "5"}],                   # C(2,2)=1
        ("d", "c"): [{"file": "6"}],                                   # C(1,2)=0
    }
    assert n98.paires_intra_cat_possibles(groupes) == 4


def test_paires_intra_cat_possibles_defensif_entrees_degradees(n98):
    assert n98.paires_intra_cat_possibles(None) == 0
    assert n98.paires_intra_cat_possibles({}) == 0
    assert n98.paires_intra_cat_possibles({("d", "c"): "pas une liste"}) == 0
    assert n98.paires_intra_cat_possibles({("d", "c"): None}) == 0


# =========================================================================== #
# (a) taux_redondance — PURE, invariant D'ÉCHELLE, jamais de division par zéro.
# =========================================================================== #
def test_taux_redondance_mesure_reelle_sous_le_seuil(n98):
    # 6 paires / 288 possibles = 2,08 % — la base RÉELLE mesurée le 19/07, saine.
    taux = n98.taux_redondance(6, 288)
    assert taux == pytest.approx(6 / 288)
    assert taux < n98.SEUIL_TAUX_REDONDANCE


def test_taux_redondance_defensif_division_par_zero(n98):
    assert n98.taux_redondance(0, 0) == 0.0
    assert n98.taux_redondance(5, 0) == 0.0


def test_taux_redondance_invariant_d_echelle(n98):
    # MUTATION (i) : un critère en COMPTE BRUT distinguerait (3, 30) de (30, 300)
    # — ici le TAUX (10 %) est identique aux deux échelles : même verdict.
    petit = n98.taux_redondance(3, 30)
    grand = n98.taux_redondance(30, 300)
    assert petit == pytest.approx(grand)
    assert petit == pytest.approx(0.10)


# =========================================================================== #
# (b) BASE SAINE réelle (main(), bout en bout) : taux de redondance ~2,2 % et
#     remplissage 78,5 % → AUCUN signal de redondance ni de saturation.
# =========================================================================== #
def _mocker_base(n98, monkeypatch, fiches, remplissage):
    domains = {"memoire": {"cat_a": []}}

    def fake_get(path):
        if path.startswith("/recall"):
            return {"results": fiches}
        if path == "/stats":
            return {"structure_fiches": int(remplissage * 200), "cap": 200,
                     "remplissage": remplissage}
        if path == "/domains":
            return {"domains": domains}
        raise AssertionError(path)  # pragma: no cover - chemin non attendu

    monkeypatch.setattr(n98, "get", fake_get)
    monkeypatch.setattr(n98.nexus_sense, "lire", lambda: [])
    import nexus_embedder
    monkeypatch.setattr(nexus_embedder, "charger_embedder", lambda *a, **k: None)


def test_b_base_saine_taux_sous_seuil_aucun_signal(n98, monkeypatch, capsys):
    # 8 fiches uniques + 1 paire dupliquée dans LA MÊME catégorie :
    # 1 paire redondante / C(10,2)=45 possibles = 2,22 % < 3,0 % ; remplissage
    # 78,5 % < 90 % (nouveau seuil de saturation).
    fiches = _fiches_uniques(8, "u") + _fiches_dupliquees(
        "budget calcul montant total", 2, "d")
    _mocker_base(n98, monkeypatch, fiches, remplissage=0.785)

    n98.main()
    out = capsys.readouterr().out
    assert "Redondance : 1 paire(s)" in out
    assert "taux 2.22%" in out
    assert "redondance élevée" not in out
    assert "saturation mémoire" not in out
    assert "VERDICT DE SANTÉ : 🟢 SAIN" in out


# =========================================================================== #
# (c) BASE DÉGRADÉE (+5 doublons injectés dans la même catégorie) : le cluster
#     dupliqué passe de 2 à 7 fiches → 21 paires / 105 possibles = 20,0 % ≥
#     3,0 % → signal 'redondance élevée'.
#     MUTATION (iii) : ne pas faire monter le signal ici → ce test passe au ROUGE.
# =========================================================================== #
def test_c_base_degradee_5_doublons_injectes_declenche_le_signal(n98, monkeypatch, capsys):
    fiches = _fiches_uniques(8, "u") + _fiches_dupliquees(
        "budget calcul montant total", 7, "d")   # +5 doublons vs la base saine (b)
    _mocker_base(n98, monkeypatch, fiches, remplissage=0.785)

    n98.main()
    out = capsys.readouterr().out
    assert "Redondance : 21 paire(s)" in out
    assert "redondance élevée" in out
    assert "20.0 % ≥ 3 %" in out
    # La saturation, elle, reste saine (seul le signal de redondance a bougé) :
    assert "saturation mémoire" not in out


# =========================================================================== #
# (b/c) SATURATION seule : 78,5 % (sain, sous le nouveau seuil 90 %) vs 91 %
#       (au-delà) — Danger Theory : un niveau nominal (50-89 %) n'est plus une
#       alerte. MUTATION (ii) : garder le seuil à 50 % → la première assertion
#       casserait (78,5 % signalerait déjà).
# =========================================================================== #
def test_saturation_78_5_sain_91_alerte(n98, monkeypatch, capsys):
    fiches = _fiches_uniques(4, "u")   # base sans redondance, pour isoler le signal

    _mocker_base(n98, monkeypatch, fiches, remplissage=0.785)
    n98.main()
    assert "saturation mémoire" not in capsys.readouterr().out

    _mocker_base(n98, monkeypatch, fiches, remplissage=0.91)
    n98.main()
    assert "saturation mémoire" in capsys.readouterr().out


# =========================================================================== #
# VERROU LECTURE SEULE : les deux nouvelles fonctions restent PURES (aucune
# écriture), et l'honnêteté 'sans embedder → semantique = 0' n'est pas cassée
# par l'ajout du taux (compter_redondances garde son partition non chevauchante).
# =========================================================================== #
def test_sans_embedder_semantique_reste_zero_avec_le_taux(n98):
    groupes = {("d", "c"): [
        _fiche("x.md", "alpha bravo"),
        _fiche("y.md", "charlie delta"),
    ]}
    r = n98.compter_redondances(groupes, embedder=None)
    assert r["semantique"] == 0
    possibles = n98.paires_intra_cat_possibles(groupes)
    assert n98.taux_redondance(r["total"], possibles) == 0.0
