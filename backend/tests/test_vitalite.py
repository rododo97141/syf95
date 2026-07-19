"""Vitalité observée (réutilisation cross-session) — organes/nexus_vitalite.py
+ son branchement opt-in dans organes/nexus_force.calculer_forces(vitalite=...).

Isolation TOTALE (jamais le vrai memoire_data/) : MEMOIRE_ROOT -> tmp_path,
CAPTEURS_ROOT -> tmp_path (autouse via backend/conftest.py). Les journaux
(consultations.jsonl, capteurs/journal.jsonl) sont écrits directement en
JSONL pour contrôler précisément jours/tâches distincts, sans dépendre de
l'horloge réelle.

Couvre :
  (a) une fiche vue un seul jour reste à indice 0 même avec plusieurs tâches
      ce jour-là (garde-fou anti-forgeage en une seule session) ;
  (b) 2 jours + 2 tâches distincts franchit le seuil ;
  (c) fusion consultations+capteurs sans double-compte du même (fiche, jour) ;
  (d) indice plafonné à 1.0 ;
  (e) module 100% lecture seule : aucun fichier créé ;
  (f) calculer_forces() sans vitalite reste EXACTEMENT le comportement
      historique (dont le cas {} de test_orchestrateur_routage) ;
  (g) vitalité seule (indice=1.0, aucun succes/echec) plafonnée à
      FORCE_DEFAUT + DELTA_VITALITE_MAX, loin de FORCE_MAX ;
  (h) succes/echec et vitalité se cumulent additivement.
"""
import os
import sys
import json

import pytest


def _organes():
    ici = os.path.dirname(os.path.abspath(__file__))          # backend/tests
    racine = os.path.dirname(os.path.dirname(ici))             # racine du dépôt
    return os.path.join(racine, "organes")


class _Vit:
    """Contexte de test : modules chargés + racines isolées."""


@pytest.fixture
def vit(tmp_path, monkeypatch):
    org = _organes()
    if org not in sys.path:
        sys.path.insert(0, org)
    racine_memoire = tmp_path / "memoire_data"
    monkeypatch.setenv("MEMOIRE_ROOT", str(racine_memoire))    # relu à chaque appel

    import nexus_force
    import nexus_sense
    import nexus_vitalite

    c = _Vit()
    c.force = nexus_force
    c.sense = nexus_sense
    c.vitalite = nexus_vitalite
    c.tmp = tmp_path
    c.racine_memoire = racine_memoire
    c.chemin_consultations = os.path.join(str(racine_memoire), "capital", "consultations.jsonl")
    c.chemin_capteurs = os.path.join(os.environ["CAPTEURS_ROOT"], "capteurs", "journal.jsonl")
    return c


def _consultation(chemin, ts, tache, slugs):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    rec = {
        "type": "consultation", "id": "cons-test", "ts": ts,
        "requete": "peu importe", "slugs_retournes": list(slugs),
        "fiche_retenue": None, "tache": tache,
    }
    with open(chemin, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _capteur(chemin, ts, tache, fiche):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    rec = {"ts": ts, "tache": tache, "statut": "ok", "fiche": fiche}
    with open(chemin, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# (a) un seul jour, plusieurs tâches -> indice 0
# --------------------------------------------------------------------------- #
def test_un_seul_jour_reste_indice_zero_meme_avec_plusieurs_taches(vit):
    _consultation(vit.chemin_consultations, "2026-07-01T09:00:00", "tache-1", ["critere-a"])
    _consultation(vit.chemin_consultations, "2026-07-01T15:00:00", "tache-2", ["critere-a"])
    _consultation(vit.chemin_consultations, "2026-07-01T18:00:00", "tache-3", ["critere-a"])

    brut = vit.vitalite.mesurer_vitalite()
    assert brut["critere-a"]["jours"] == {"2026-07-01"}
    assert brut["critere-a"]["taches"] == {"tache-1", "tache-2", "tache-3"}

    indices = vit.vitalite.indice_vitalite(brut)
    assert indices["critere-a"] == 0.0


# --------------------------------------------------------------------------- #
# (b) 2 jours + 2 tâches distincts franchit le seuil
# --------------------------------------------------------------------------- #
def test_deux_jours_et_deux_taches_franchit_le_seuil(vit):
    _consultation(vit.chemin_consultations, "2026-07-01T09:00:00", "tache-1", ["critere-b"])
    _consultation(vit.chemin_consultations, "2026-07-02T09:00:00", "tache-2", ["critere-b"])

    indices = vit.vitalite.indice_vitalite()
    assert indices["critere-b"] > 0.0
    # ratio_jours = 2/10, ratio_taches = 2/10 -> moyenne = 0.2
    assert indices["critere-b"] == pytest.approx(0.2)


# --------------------------------------------------------------------------- #
# (c) fusion consultations + capteurs sans double-compte
# --------------------------------------------------------------------------- #
def test_fusion_consultations_capteurs_sans_double_compte(vit):
    # même (fiche, jour, tâche) rapporté par les DEUX sources -> compte UNE fois.
    _consultation(vit.chemin_consultations, "2026-07-01T09:00:00", "tache-1", ["critere-c"])
    _capteur(vit.chemin_capteurs, "2026-07-01T10:00:00", "tache-1", "critere-c")
    _consultation(vit.chemin_consultations, "2026-07-02T09:00:00", "tache-2", ["critere-c"])
    _capteur(vit.chemin_capteurs, "2026-07-02T10:00:00", "tache-2", "critere-c")

    brut = vit.vitalite.mesurer_vitalite()
    assert brut["critere-c"]["jours"] == {"2026-07-01", "2026-07-02"}
    assert brut["critere-c"]["taches"] == {"tache-1", "tache-2"}
    assert len(brut["critere-c"]["jours"]) == 2
    assert len(brut["critere-c"]["taches"]) == 2


# --------------------------------------------------------------------------- #
# (d) indice plafonné à 1.0
# --------------------------------------------------------------------------- #
def test_indice_plafonne_a_un(vit):
    for i in range(1, 13):  # 12 jours et 12 tâches distincts (> plafond 10)
        _consultation(
            vit.chemin_consultations, "2026-07-%02dT09:00:00" % i, "tache-%d" % i, ["critere-d"]
        )

    indices = vit.vitalite.indice_vitalite()
    assert indices["critere-d"] == 1.0


# --------------------------------------------------------------------------- #
# (e) module 100% lecture seule : aucun fichier créé
# --------------------------------------------------------------------------- #
def test_module_lecture_seule_aucun_fichier_cree(vit, capsys):
    assert not os.path.exists(vit.racine_memoire)
    assert not os.path.exists(os.environ["CAPTEURS_ROOT"])

    brut = vit.vitalite.mesurer_vitalite()
    indices = vit.vitalite.indice_vitalite(brut)
    rapport = vit.vitalite.rapport()
    capsys.readouterr()  # ne laisse pas fuiter l'affichage dans le run pytest

    assert brut == {}
    assert indices == {}
    assert rapport == {}
    # aucun répertoire/fichier créé par la seule lecture, même quand les
    # sources sont absentes.
    assert not os.path.exists(vit.racine_memoire)
    assert not os.path.exists(os.environ["CAPTEURS_ROOT"])

    # même constat avec des sources PRÉSENTES : la lecture ne crée rien de plus.
    _consultation(vit.chemin_consultations, "2026-07-01T09:00:00", "tache-1", ["critere-e"])
    _capteur(vit.chemin_capteurs, "2026-07-02T09:00:00", "tache-2", "critere-e")
    avant = _empreinte_arborescence(vit.tmp)
    vit.vitalite.mesurer_vitalite()
    vit.vitalite.indice_vitalite()
    vit.vitalite.rapport()
    capsys.readouterr()
    apres = _empreinte_arborescence(vit.tmp)
    assert avant == apres


def _empreinte_arborescence(racine):
    fichiers = set()
    for dirpath, _dirnames, filenames in os.walk(str(racine)):
        for nom in filenames:
            fichiers.add(os.path.relpath(os.path.join(dirpath, nom), str(racine)))
    return fichiers


# --------------------------------------------------------------------------- #
# (f) calculer_forces() sans vitalite : comportement historique INCHANGÉ
# --------------------------------------------------------------------------- #
def test_calculer_forces_sans_vitalite_comportement_historique_inchange(vit):
    # cas {} protégé (cf. test_orchestrateur_routage.
    # test_observer_ok_laisse_calculer_forces_inerte) : aucun capteur -> {}.
    assert vit.force.calculer_forces() == {}
    assert vit.force.calculer_forces(vitalite=None) == {}

    # avec de l'activité succes/echec, vitalite omis -> résultat identique à
    # avant l'ajout du signal de vitalité.
    vit.sense.log_event(tache="t1", statut="succes", fiche="critere-f")
    vit.sense.log_event(tache="t2", statut="echec", fiche="critere-g")

    forces_defaut = vit.force.calculer_forces()
    forces_vitalite_none = vit.force.calculer_forces(vitalite=None)
    assert forces_defaut == forces_vitalite_none

    attendu_f = round(vit.force.FORCE_DEFAUT + vit.force.DELTA_SUCCES, 4)
    attendu_g = round(vit.force.FORCE_DEFAUT + vit.force.DELTA_ECHEC, 4)
    assert forces_defaut["critere-f"] == attendu_f
    assert forces_defaut["critere-g"] == attendu_g


# --------------------------------------------------------------------------- #
# (g) vitalité seule, jamais au-delà de FORCE_DEFAUT + DELTA_VITALITE_MAX
# --------------------------------------------------------------------------- #
def test_vitalite_seule_plafonnee_loin_de_force_max(vit):
    # aucun succes/echec pour "critere-h" -> score net nul, vitalite=1.0 (max).
    forces = vit.force.calculer_forces(vitalite={"critere-h": 1.0})

    attendu = round(vit.force.FORCE_DEFAUT + vit.force.DELTA_VITALITE_MAX, 4)
    assert forces["critere-h"] == attendu
    assert forces["critere-h"] < vit.force.FORCE_MAX
    # loin de FORCE_MAX : la marge doit rester majoritaire.
    assert (vit.force.FORCE_MAX - forces["critere-h"]) > (vit.force.FORCE_MAX - vit.force.FORCE_DEFAUT) / 2


# --------------------------------------------------------------------------- #
# (h) succes/echec et vitalité se cumulent additivement
# --------------------------------------------------------------------------- #
def test_succes_et_vitalite_cumul_additif(vit):
    vit.sense.log_event(tache="t1", statut="succes", fiche="critere-i")
    forces = vit.force.calculer_forces(vitalite={"critere-i": 0.5})

    attendu = round(
        vit.force.FORCE_DEFAUT + vit.force.DELTA_SUCCES * 1 + vit.force.DELTA_VITALITE_MAX * 0.5,
        4,
    )
    assert forces["critere-i"] == attendu

    # le seul succès sans vitalité vaut STRICTEMENT moins que succès + vitalité.
    forces_sans_vitalite = vit.force.calculer_forces()
    assert forces["critere-i"] > forces_sans_vitalite["critere-i"]
