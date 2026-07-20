# -*- coding: utf-8 -*-
"""
NEXUS — fix BUG PR#86 : la vitalité SEULE ne doit JAMAIS écraser une force
déjà présente dans forces.json.

Mesuré sur la vraie mémoire (memoire_data réelle) : quand `vitalite` est fourni
à calculer_forces(), une fiche JAMAIS vue en succes/echec mais avec un indice de
vitalité non nul entrait dans le recalcul FORCE_DEFAUT + DELTA_VITALITE_MAX*idx
— ÉCRASANT toute force manuelle/antérieure déjà présente dans forces.json (une
fiche réelle à force 1.20 tombait à 1.06, DEGRADÉE par la seule vitalité :
contraire à la doctrine « la vitalité AIDE, ne retire jamais »).

Fix : distinguer
  - fiche IN score (activité succes/echec réelle) : formule HISTORIQUE
    inchangée, vitalité ADDITIVE en plus — CE CAS N'ÉTAIT PAS BOGUÉ ;
  - fiche NOT IN score (vitalité SEULE) : valeur = forces.get(fiche,
    FORCE_DEFAUT) + DELTA_VITALITE_MAX*idx — ADDITIF sur ce qui existe déjà,
    JAMAIS un écrasement depuis FORCE_DEFAUT.

`vitalite=None` (défaut) reste totalement inchangé (couvert par ailleurs, cf.
test_vitalite.py test_calculer_forces_sans_vitalite_comportement_historique_inchange).
"""
import os
import sys
import json
import importlib

import pytest


def _racine():
    ici = os.path.dirname(os.path.abspath(__file__))          # backend/tests
    return os.path.dirname(os.path.dirname(ici))               # racine du dépôt


@pytest.fixture
def nf(tmp_path, monkeypatch):
    org = os.path.join(_racine(), "organes")
    if org not in sys.path:
        sys.path.insert(0, org)
    racine_memoire = tmp_path / "memoire_data"
    monkeypatch.setenv("MEMOIRE_ROOT", str(racine_memoire))    # relu à chaque appel
    import nexus_force
    return importlib.reload(nexus_force)


def _ecrire_forces(nf_mod, forces):
    chemin = nf_mod._chemin_forces()
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(forces, f)


# --------------------------------------------------------------------------- #
# RÉGRESSION EXPLICITE — le cœur du mandat : force déjà FORTE (2.0) jamais
# dégradée par la seule vitalité. Avec l'ANCIENNE formule bogue de PR#86, ce
# test DOIT échouer (vérifié ci-dessous par mutation temporaire, restaurée) ;
# avec le fix, il DOIT passer.
# --------------------------------------------------------------------------- #
def test_regression_force_deja_forte_jamais_degradee_par_la_seule_vitalite(nf):
    # "fiche-forte" a une force ANTÉRIEURE de 2.0 dans forces.json (ex: montée
    # par succes/echec passés, ou réglage manuel), mais AUCUNE activité
    # succes/echec dans CET appel (evenements=[] : pas dans `score`).
    _ecrire_forces(nf, {"fiche-forte": 2.0})

    forces = nf.calculer_forces(evenements=[], vitalite={"fiche-forte": 1.0})

    assert forces["fiche-forte"] >= 2.0, (
        "RÉGRESSION : la seule vitalité a dégradé une force déjà forte — "
        "contraire à la doctrine (la vitalité AIDE, ne retire jamais)."
    )
    attendu = round(min(nf.FORCE_MAX, 2.0 + nf.DELTA_VITALITE_MAX * 1.0), 4)
    assert forces["fiche-forte"] == attendu


def test_mutation_ancienne_formule_bogue_casse_la_regression(nf):
    """Preuve, pas supposition : on REJOUE ici l'ANCIENNE formule bogue de
    PR#86 (recalcul depuis FORCE_DEFAUT, ignorant la force existante) et on
    vérifie qu'ELLE casse l'assertion de non-dégradation — donc que le test de
    régression ci-dessus est bien un test ROUGE→VERT et pas un vrai-positif
    accidentel. Mutation strictement LOCALE à ce test (aucun fichier modifié)."""
    force_existante = 2.0
    idx = 1.0

    def _ancienne_formule_bogue(existante, idx):
        # reproduction FIDÈLE du bug : ignore `existante`, repart de FORCE_DEFAUT.
        valeur = nf.FORCE_DEFAUT + nf.DELTA_VITALITE_MAX * idx
        return round(min(nf.FORCE_MAX, max(nf.FORCE_MIN, valeur)), 4)

    resultat_bogue = _ancienne_formule_bogue(force_existante, idx)
    assert resultat_bogue < force_existante, (
        "la mutation devrait reproduire la dégradation observée par PR#86 "
        "(1.20 -> 1.06) ; si elle ne dégrade plus rien, la mutation ne teste "
        "plus le bug historique."
    )

    # Le FIX (code réel) ne dégrade jamais : preuve que le fix diffère bien de
    # la mutation bogue ci-dessus, sur les MÊMES valeurs d'entrée.
    _ecrire_forces(nf, {"fiche-forte": force_existante})
    forces_fix = nf.calculer_forces(evenements=[], vitalite={"fiche-forte": idx})
    assert forces_fix["fiche-forte"] != resultat_bogue
    assert forces_fix["fiche-forte"] >= force_existante


# --------------------------------------------------------------------------- #
# Cas historique NON bogué : fiche AVEC succes/echec réel — formule HISTORIQUE
# inchangée, vitalité additive en plus (ne pas casser ce chemin en corrigeant
# l'autre).
# --------------------------------------------------------------------------- #
def test_fiche_avec_activite_reelle_formule_historique_inchangee(nf):
    evenements = [{"fiche": "fiche-active", "statut": "succes"}]
    forces = nf.calculer_forces(evenements=evenements, vitalite={"fiche-active": 0.5})

    attendu = round(
        nf.FORCE_DEFAUT + nf.DELTA_SUCCES * 1 + nf.DELTA_VITALITE_MAX * 0.5, 4
    )
    assert forces["fiche-active"] == attendu


# --------------------------------------------------------------------------- #
# Vitalité seule, SANS force préexistante : additif depuis FORCE_DEFAUT (le
# comportement de la fiche jamais vue nulle part -- PAS de régression ici, cf.
# test_vitalite.py test_vitalite_seule_plafonnee_loin_de_force_max, préservé).
# --------------------------------------------------------------------------- #
def test_vitalite_seule_sans_force_existante_part_de_force_defaut(nf):
    forces = nf.calculer_forces(evenements=[], vitalite={"fiche-neuve": 1.0})
    attendu = round(nf.FORCE_DEFAUT + nf.DELTA_VITALITE_MAX * 1.0, 4)
    assert forces["fiche-neuve"] == attendu


# --------------------------------------------------------------------------- #
# Bornée : une force déjà proche de FORCE_MAX + vitalité plafonnée reste
# borné à FORCE_MAX (jamais un dépassement).
# --------------------------------------------------------------------------- #
def test_vitalite_seule_sur_force_existante_reste_bornee_a_force_max(nf):
    _ecrire_forces(nf, {"fiche-quasi-max": nf.FORCE_MAX - 0.05})
    forces = nf.calculer_forces(evenements=[], vitalite={"fiche-quasi-max": 1.0})
    assert forces["fiche-quasi-max"] == nf.FORCE_MAX


# --------------------------------------------------------------------------- #
# vitalite=None reste totalement inchangé même avec une force existante (aucun
# des deux nouveaux chemins n'est emprunté).
# --------------------------------------------------------------------------- #
def test_vitalite_none_reste_inchange_avec_force_existante(nf):
    _ecrire_forces(nf, {"fiche-inerte": 1.5})
    forces = nf.calculer_forces(evenements=[], vitalite=None)
    assert forces == {"fiche-inerte": 1.5}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
