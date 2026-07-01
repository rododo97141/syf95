"""Intégration bout-en-bout du câblage mémoire DANS la boucle (feat/force-cablage).

Vérifie les trois briques ensemble, sur un état/mémoire/capteurs isolés
(jamais le vrai memoire_data/) :

  1) recall consulté AVANT l'appel moteur dans executer_tache/tourner, et la
     meilleure fiche trouvée injectée dans le prompt ;
  2) quand une fiche a servi, un capteur dédié est émis via nexus_sense.log_event
     avec fiche=<slug> et statut=succes|echec ;
  3) le pont capteurs → forces.json fait vraiment monter la force d'une fiche
     réutilisée avec succès (recompute déterministe, additif).
"""
import os
import sys
import json
import importlib.util

import orchestrateur


def _organes():
    ici = os.path.dirname(os.path.abspath(__file__))       # backend/tests
    racine = os.path.dirname(os.path.dirname(ici))          # racine du dépôt
    return os.path.join(racine, "organes")


def _charger_memory_api():
    """Instance FRAÎCHE de memory_api (pas de sys.modules partagé entre tests) :
    ROOT/STRUCT/etc. sont des constantes de chargement, pas relues par appel."""
    ici = os.path.dirname(os.path.abspath(__file__))
    racine = os.path.dirname(os.path.dirname(ici))
    chemin = os.path.join(racine, ".claude", "skills", "memoire-beta",
                          "scripts", "memory_api.py")
    spec = importlib.util.spec_from_file_location("memory_api_force_test", chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fiche(mem, domain, category, nom, contenu):
    d = os.path.join(mem.STRUCT, domain, category)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, nom + ".md"), "w", encoding="utf-8") as f:
        f.write(contenu)


def _etat_une_tache(libelle_1, libelle_2=None):
    taches = [{
        "id": "t1", "libelle": libelle_1, "etat": "a_faire",
        "resultat": None, "verifie": False, "veto": False, "sensible": False,
    }]
    if libelle_2:
        taches.append({
            "id": "t2", "libelle": libelle_2, "etat": "a_faire",
            "resultat": None, "verifie": False, "veto": False, "sensible": False,
        })
    return {
        "version": 1, "cree_le": "2026-01-01T00:00:00+00:00",
        "maj_le": "2026-01-01T00:00:00+00:00", "cycle": 0, "curseur": 0,
        "taches": taches, "ecarts_semes": True,   # évite l'auto-mandat (bruit hors-sujet)
        "archive_96": [], "journal": [],
    }


def _setup(tmp_path, monkeypatch):
    org = _organes()
    if org not in sys.path:
        sys.path.insert(0, org)
    racine_memoire = tmp_path / "memoire_data"
    monkeypatch.setenv("MEMOIRE_ROOT", str(racine_memoire))  # relu par nexus_force à chaque appel

    mem = _charger_memory_api()
    mem.ROOT = str(racine_memoire)
    mem.STRUCT = str(racine_memoire / "structure")
    mem.EN_ATTENTE = str(racine_memoire / "en_attente")
    mem.BRUT = str(racine_memoire / "brut")
    mem.ARCHIVE = str(racine_memoire / "archive")
    return mem, racine_memoire


# --------------------------------------------------------------------------- #
# 1) recall consulté + fiche injectée dans le prompt
# --------------------------------------------------------------------------- #
def test_executer_tache_consulte_le_recall_et_injecte_la_fiche(tmp_path, monkeypatch):
    mem, _racine = _setup(tmp_path, monkeypatch)
    _fiche(mem, "dom", "cat", "zorglubide",
           "Procédure zorglubide : étapes détaillées pour la mission.")

    from moteur import MoteurMock
    moteur = MoteurMock()
    tache = {"id": "t1", "libelle": "Traiter la mission zorglubide",
             "etat": "a_faire", "resultat": None, "verifie": False,
             "veto": False, "sensible": False}

    resultat = orchestrateur.executer_tache(tache, moteur, memoire=mem)

    assert resultat["fiche"] == "zorglubide"
    assert len(moteur.appels) == 1
    assert "[Mémoire rappelée : zorglubide]" in moteur.appels[0]
    assert "Procédure zorglubide" in moteur.appels[0]


def test_executer_tache_sans_fiche_correspondante_ne_pollue_pas_le_prompt(tmp_path, monkeypatch):
    mem, _racine = _setup(tmp_path, monkeypatch)
    # Aucune fiche en structure : le recall ne doit rien injecter.
    from moteur import MoteurMock
    moteur = MoteurMock()
    tache = {"id": "t1", "libelle": "Une tâche sans rapport avec la mémoire",
             "etat": "a_faire", "resultat": None, "verifie": False,
             "veto": False, "sensible": False}

    resultat = orchestrateur.executer_tache(tache, moteur, memoire=mem)

    assert "fiche" not in resultat
    assert "[Mémoire rappelée" not in moteur.appels[0]


# --------------------------------------------------------------------------- #
# 2) capteur dédié (fiche=slug, statut=succes|echec) émis quand une fiche a servi
# --------------------------------------------------------------------------- #
def test_capteur_fiche_emis_avec_statut_succes(tmp_path, monkeypatch):
    mem, _racine = _setup(tmp_path, monkeypatch)
    _fiche(mem, "dom", "cat", "zorglubide", "Procédure zorglubide.")

    etat_path = tmp_path / "etat.json"
    orchestrateur.sauver_etat(etat_path, _etat_une_tache("Traiter la mission zorglubide"))

    from moteur import MoteurMock
    orchestrateur.tourner(etat_path, moteur=MoteurMock(), memoire=mem)

    racine_cap = os.environ["CAPTEURS_ROOT"]  # isolé par le conftest autouse
    journal = os.path.join(racine_cap, "capteurs", "journal.jsonl")
    lignes = [json.loads(l) for l in open(journal, encoding="utf-8") if l.strip()]

    capteurs_fiche = [e for e in lignes if e.get("fiche")]
    assert len(capteurs_fiche) == 1
    assert capteurs_fiche[0]["fiche"] == "zorglubide"
    assert capteurs_fiche[0]["statut"] == "succes"


# --------------------------------------------------------------------------- #
# 3) le pont capteurs → forces.json fait monter la force d'une fiche réutilisée
# --------------------------------------------------------------------------- #
def test_une_tache_qui_reutilise_une_fiche_fait_monter_sa_force(tmp_path, monkeypatch):
    mem, racine_memoire = _setup(tmp_path, monkeypatch)
    _fiche(mem, "dom", "cat", "zorglubide", "Procédure zorglubide.")

    etat_path = tmp_path / "etat.json"
    orchestrateur.sauver_etat(
        etat_path,
        _etat_une_tache("Traiter la mission zorglubide",
                        "Retraiter la mission zorglubide"),
    )

    from moteur import MoteurMock
    chemin_forces = os.path.join(str(racine_memoire), "forces.json")

    # Passage 1 : une seule tâche traitée (pas=1) → la fiche sert une 1re fois.
    orchestrateur.tourner(etat_path, pas=1, moteur=MoteurMock(), memoire=mem)
    forces_1 = json.loads(open(chemin_forces, encoding="utf-8").read())
    assert forces_1["zorglubide"] > 1.0
    force_apres_1 = forces_1["zorglubide"]

    # Passage 2 (reprise) : la 2e tâche réutilise la MÊME fiche → la force remonte encore.
    orchestrateur.tourner(etat_path, pas=1, moteur=MoteurMock(), memoire=mem)
    forces_2 = json.loads(open(chemin_forces, encoding="utf-8").read())
    assert forces_2["zorglubide"] > force_apres_1

    # Et cette force plus élevée est bien celle que recall() applique (contrat forces.json).
    forces_lues = mem.load_forces()
    assert forces_lues["zorglubide"] == forces_2["zorglubide"]


def test_pas_de_fiche_pas_decriture_de_forces_json(tmp_path, monkeypatch):
    """Garde-fou : si aucune fiche n'a servi, aucune écriture forces.json (pas de bruit)."""
    mem, racine_memoire = _setup(tmp_path, monkeypatch)
    # Pas de fiche en structure : recall ne trouvera rien.
    etat_path = tmp_path / "etat.json"
    orchestrateur.sauver_etat(etat_path, _etat_une_tache("Tâche sans rapport"))

    from moteur import MoteurMock
    orchestrateur.tourner(etat_path, moteur=MoteurMock(), memoire=mem)

    chemin_forces = os.path.join(str(racine_memoire), "forces.json")
    assert not os.path.exists(chemin_forces)
