# -*- coding: utf-8 -*-
"""
NEXUS — câblage nexus_vitalite DANS organes/nexus_capital.consulter() (chemin
CAPITAL, memoire=None).

Contexte mesuré le 19/07 : nexus_vitalite (PR#86) est en production mais vit À
CÔTÉ de la boucle — aucun appelant réel en dehors de ses propres tests. Ce
fichier couvre le câblage réel :

  1. environnement VIDE : consulter() reste NUMÉRIQUEMENT IDENTIQUE (aucune
     vitalité mesurable -> calculer_forces(vitalite={}) == calculer_forces()).
  2. consulter() appelle RÉELLEMENT calculer_forces avec `vitalite=` — vérifié
     par un ESPION sur nexus_force.calculer_forces (pas supposé) : le kwarg est
     bien présent et vaut nexus_vitalite.indice_vitalite().
  3. vitalité RÉELLE (fiche jamais vue en succes/echec mais consultée sur ≥2
     jours et ≥2 tâches distincts) fait franchir FORCE_DEFAUT à la force
     calculée par consulter() — la vitalité AIDE bien, dans le vrai chemin.
"""
import os
import sys
import json
import importlib
import importlib.util

import pytest


def _racine_depot():
    ici = os.path.dirname(os.path.abspath(__file__))          # backend/tests
    return os.path.dirname(os.path.dirname(ici))               # racine du dépôt


def _organes():
    org = os.path.join(_racine_depot(), "organes")
    if org not in sys.path:
        sys.path.insert(0, org)
    return org


class _Cap:
    """Contexte de test : modules chargés + racines isolées."""


@pytest.fixture
def cap(tmp_path, monkeypatch):
    _organes()
    racine_memoire = tmp_path / "memoire_data"
    monkeypatch.setenv("MEMOIRE_ROOT", str(racine_memoire))    # relu à chaque appel

    import nexus_force
    import nexus_sense
    import nexus_lecons
    import nexus_vitalite
    import nexus_capital
    nexus_force = importlib.reload(nexus_force)
    nexus_vitalite = importlib.reload(nexus_vitalite)
    nexus_capital = importlib.reload(nexus_capital)
    dl = tmp_path / "lecons"
    monkeypatch.setattr(nexus_lecons, "DIR", str(dl))
    monkeypatch.setattr(nexus_lecons, "JOURNAL", str(dl / "journal.jsonl"))
    monkeypatch.setattr(nexus_lecons, "TRANSFERT", str(dl / "transfert.jsonl"))

    c = _Cap()
    c.nf = nexus_force
    c.vit = nexus_vitalite
    c.lecons = nexus_lecons
    c.cap = nexus_capital
    c.tmp = tmp_path
    c.racine_memoire = racine_memoire
    c.chemin_consultations = os.path.join(str(racine_memoire), "capital", "consultations.jsonl")
    return c


def _consultation_brute(chemin, ts, tache, slugs):
    """Écrit directement une ligne consultation.jsonl — la SOURCE que lit
    nexus_vitalite.mesurer_vitalite (indépendante de nexus_capital.consulter,
    pour construire un historique de vitalité SANS dépendre de la fonction
    testée)."""
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    rec = {
        "type": "consultation", "id": "cons-vitalite-seed", "ts": ts,
        "requete": "peu importe", "slugs_retournes": list(slugs),
        "fiche_retenue": None, "tache": tache,
    }
    with open(chemin, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# 1) environnement VIDE : numériquement identique à avant le câblage.
# --------------------------------------------------------------------------- #
def test_environnement_vide_numeriquement_identique(cap):
    cap.cap.capitaliser("Critère sans aucune activité", "reponse", "contexte", "nexus")

    assert cap.vit.indice_vitalite() == {}      # rien à mesurer, environnement vide
    forces_sans_vitalite = cap.nf.calculer_forces()
    forces_avec_vitalite_vide = cap.nf.calculer_forces(vitalite=cap.vit.indice_vitalite())
    assert forces_sans_vitalite == forces_avec_vitalite_vide == {}

    rec = cap.cap.consulter("Critère sans aucune activité", "tache-test")
    assert rec["slugs_retournes"]      # la délégation à rank() fonctionne toujours


# --------------------------------------------------------------------------- #
# 2) consulter() appelle RÉELLEMENT calculer_forces(vitalite=...) — ESPION.
# --------------------------------------------------------------------------- #
def test_consulter_appelle_reellement_calculer_forces_avec_vitalite(cap, monkeypatch):
    cap.cap.capitaliser("Critère espionné", "reponse", "contexte", "nexus")

    vrai_calculer_forces = cap.nf.calculer_forces
    vrai_indice_vitalite = cap.vit.indice_vitalite
    appels = []
    indices_espionnes = []

    def _espion_forces(*args, **kwargs):
        appels.append(kwargs)
        return vrai_calculer_forces(*args, **kwargs)

    def _espion_vitalite(*args, **kwargs):
        r = vrai_indice_vitalite(*args, **kwargs)
        indices_espionnes.append(r)
        return r

    monkeypatch.setattr(cap.cap.nexus_force, "calculer_forces", _espion_forces)
    monkeypatch.setattr(cap.cap.nexus_vitalite, "indice_vitalite", _espion_vitalite)

    cap.cap.consulter("Critère espionné", "tache-espion")

    assert len(appels) == 1
    assert "vitalite" in appels[0], (
        "consulter() doit appeler calculer_forces AVEC le kwarg vitalite= "
        "(pas calculer_forces() sans argument)."
    )
    assert len(indices_espionnes) == 1, (
        "consulter() doit appeler RÉELLEMENT nexus_vitalite.indice_vitalite() "
        "(et pas une valeur en dur)."
    )
    # même valeur, capturée AU MOMENT de l'appel (avant que consulter() n'écrive
    # sa propre consultation, qui changerait indice_vitalite() ex-post).
    assert appels[0]["vitalite"] == indices_espionnes[0]


# --------------------------------------------------------------------------- #
# 3) vitalité RÉELLE fait franchir FORCE_DEFAUT — le chemin réel, bout en bout.
# --------------------------------------------------------------------------- #
def test_vitalite_reelle_fait_franchir_force_defaut(cap):
    slug = cap.cap.capitaliser("Critère vivant sans succes ni echec",
                               "reponse", "contexte", "nexus")

    # ≥2 jours ET ≥2 tâches distincts consultant CE slug -> franchit le double
    # seuil anti-forgeage de nexus_vitalite (JOURS_MIN_VIVANTE/TACHES_MIN_VIVANTE).
    _consultation_brute(cap.chemin_consultations, "2026-07-01T09:00:00", "tache-1", [slug])
    _consultation_brute(cap.chemin_consultations, "2026-07-05T09:00:00", "tache-2", [slug])

    idx = cap.vit.indice_vitalite()
    assert idx.get(slug, 0.0) > 0.0                 # la vitalité est bien mesurée

    forces = cap.nf.calculer_forces(vitalite=idx)   # même appel que consulter()
    # AUCUNE activité succes/echec pour ce slug : la force vient de la vitalité SEULE.
    assert forces[slug] > cap.nf.FORCE_DEFAUT
    attendu = round(cap.nf.FORCE_DEFAUT + cap.nf.DELTA_VITALITE_MAX * idx[slug], 4)
    assert forces[slug] == attendu

    # bout en bout : consulter() (qui délègue à calculer_forces(vitalite=...))
    # continue de fonctionner sans lever, la fiche vivante reste retrouvable.
    rec = cap.cap.consulter("Critère vivant sans succes ni echec", "tache-recherche")
    assert slug in rec["slugs_retournes"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
