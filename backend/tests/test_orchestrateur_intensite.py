"""
Tests du dosage d'intensité (`orchestrateur_intensite.py`).

Lancement :  python -m pytest backend/tests -q

Couvre les cas de palier ET les garde-fous :
  - SOLO / DUO / CONSEIL selon les règles ;
  - le vérificateur est TOUJOURS différent du constructeur ;
  - SOLO n'a aucun surcoût d'orchestration ;
  - « la moins chère qui suffit » : SOLO < DUO < CONSEIL à difficulté égale.
"""

import itertools

import pytest

from orchestrateur_intensite import Niveau, cout_palier, niveau, recommander


# --- Choix du palier -------------------------------------------------------
def test_solo_si_facile_reversible_enjeu_bas():
    r = recommander("petite tâche", difficulte="facile", enjeu="bas",
                    reversible=True, nouveaute="faible")
    assert r["tier"] == "SOLO"


def test_conseil_si_dur_et_enjeu_haut():
    r = recommander("refonte", difficulte="dur", enjeu="haut",
                    reversible=True, nouveaute="faible")
    assert r["tier"] == "CONSEIL"


def test_conseil_si_dur_et_irreversible():
    r = recommander("migration", difficulte="dur", enjeu="bas",
                    reversible=False, nouveaute="faible")
    assert r["tier"] == "CONSEIL"


def test_conseil_si_dur_et_nouveaute_forte():
    r = recommander("R&D", difficulte="dur", enjeu="bas",
                    reversible=True, nouveaute="forte")
    assert r["tier"] == "CONSEIL"


def test_duo_par_defaut_cas_intermediaire():
    """Ni trivial ni à haut risque → DUO."""
    r = recommander("tâche moyenne", difficulte="moyen", enjeu="moyen",
                    reversible=True, nouveaute="moyen")
    assert r["tier"] == "DUO"


def test_facile_mais_irreversible_passe_en_duo():
    """Irréversible retire le droit au SOLO même si la tâche est facile."""
    r = recommander("suppression facile mais définitive", difficulte="facile",
                    enjeu="bas", reversible=False, nouveaute="faible")
    assert r["tier"] == "DUO"


def test_dur_mais_sur_et_reversible_reste_duo():
    """Dur mais réversible, enjeu bas, rien de neuf → pas de CONSEIL, donc DUO."""
    r = recommander("gros refactor sûr", difficulte="dur", enjeu="bas",
                    reversible=True, nouveaute="faible")
    assert r["tier"] == "DUO"


# --- Garde-fou : vérificateur TOUJOURS différent du constructeur ----------
def test_verificateur_toujours_different_du_constructeur():
    """Sur toute la grille d'entrées, vérificateur != constructeur."""
    niveaux = ["faible", "moyen", "fort"]
    for diff, enj, nouv, rev in itertools.product(niveaux, niveaux, niveaux, [True, False]):
        r = recommander("t", difficulte=diff, enjeu=enj, reversible=rev, nouveaute=nouv)
        assert r["verificateur"] != r["constructeur"], (diff, enj, nouv, rev)


# --- Garde-fou : SOLO sans surcoût d'orchestration ------------------------
def test_solo_sans_surcout_orchestration():
    r = recommander("t", difficulte="facile", enjeu="bas",
                    reversible=True, nouveaute="faible")
    assert r["tier"] == "SOLO"
    assert r["cout_estime"]["orchestration"] == 0


# --- Coût : séparé production / orchestration, ordres de grandeur ----------
def test_cout_separe_et_total_coherent():
    r = recommander("t", difficulte="dur", enjeu="haut",
                    reversible=False, nouveaute="forte")
    c = r["cout_estime"]
    assert set(["production", "orchestration", "total", "unite"]) <= set(c)
    assert c["total"] == c["production"] + c["orchestration"]
    assert "ordre de grandeur" in c["unite"]


def test_moins_chere_qui_suffit_ordre_des_couts():
    """À difficulté égale, SOLO < DUO < CONSEIL (le moins cher qui suffit)."""
    for diff in (Niveau.FAIBLE, Niveau.MOYEN, Niveau.FORT):
        solo = cout_palier("SOLO", diff)["total"]
        duo = cout_palier("DUO", diff)["total"]
        conseil = cout_palier("CONSEIL", diff)["total"]
        assert solo < duo < conseil, diff


def test_conseil_mobilise_plus_de_ressources_que_solo():
    solo = recommander("t", difficulte="facile", enjeu="bas",
                       reversible=True, nouveaute="faible")
    conseil = recommander("t", difficulte="dur", enjeu="haut",
                          reversible=False, nouveaute="forte")
    assert len(conseil["ressources"]) > len(solo["ressources"])


# --- Normalisation des niveaux --------------------------------------------
def test_niveau_accepte_synonymes_et_flottants():
    assert niveau("facile") == Niveau.FAIBLE
    assert niveau("dur") == Niveau.FORT
    assert niveau("haut") == Niveau.FORT
    assert niveau(0.1) == Niveau.FAIBLE
    assert niveau(0.9) == Niveau.FORT
    assert niveau(0.5) == Niveau.MOYEN
    assert niveau(2) == Niveau.MOYEN


def test_niveau_rejette_inconnu_et_booleen():
    with pytest.raises(ValueError):
        niveau("gigantesque")
    with pytest.raises(TypeError):
        niveau(True)  # un booléen n'est pas un niveau


def test_entrees_normalisees_dans_le_retour():
    """Le retour ré-expose les entrées normalisées (traçabilité)."""
    r = recommander("t", difficulte=0.9, enjeu="haut", reversible=False, nouveaute=0.1)
    assert r["entrees"]["difficulte"] == "FORT"
    assert r["entrees"]["reversible"] is False
    assert r["entrees"]["nouveaute"] == "FAIBLE"
