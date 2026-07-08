"""Câblage mémoire DANS la boucle — RÉVISÉ par la doctrine « la force reste un
jugement humain externe » (autonomie du déclencheur HITL, étape 1 : la visibilité).

Historiquement (feat/force-cablage) la boucle ÉMETTAIT elle-même des capteurs de
force (fiche=<slug>, statut=succes|echec) et faisait MONTER forces.json : c'était
un chemin MÉCANIQUE qui se récompensait lui-même (Goodhart interne). La nouvelle
doctrine l'INTERDIT : la boucle rend ses rappels VISIBLES (consultations
journalisées via nexus_capital.consulter) puis les CLÔT administrativement
(observer → clore_sans_dette), sans JAMAIS émettre de force. Seul appliquer,
adossé à un jeton HUMAIN, fait bouger la force.

Ce fichier vérifie donc, sur état/mémoire/capteurs isolés (jamais le vrai
memoire_data/) :

  1) le RAPPEL est INCHANGÉ : recall consulté avant l'appel moteur dans
     executer_tache, meilleure fiche injectée dans le prompt (excerpt compris) ;
  2) la boucle N'ÉMET AUCUN capteur de force (aucun event fiche+succes|echec) ;
  3) la boucle N'ÉCRIT PAS forces.json — elle ne se récompense jamais elle-même ;
  4) sans fiche rappelée : ni forces.json, ni consultation (rien de fantôme).
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


def _capteurs():
    journal = os.path.join(os.environ["CAPTEURS_ROOT"], "capteurs", "journal.jsonl")
    if not os.path.exists(journal):
        return []
    return [json.loads(l) for l in open(journal, encoding="utf-8") if l.strip()]


# --------------------------------------------------------------------------- #
# 1) RAPPEL INCHANGÉ : recall consulté + fiche injectée dans le prompt (excerpt).
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
    assert "Procédure zorglubide" in moteur.appels[0]          # excerpt injecté (inchangé)
    # la consultation est ouverte et VISIBLE (portée pour clôture par l'observer).
    assert resultat.get("consultation_id")


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
    assert "consultation_id" not in resultat                   # pas de consultation fantôme
    assert "[Mémoire rappelée" not in moteur.appels[0]


# --------------------------------------------------------------------------- #
# 2) DOCTRINE : la boucle N'ÉMET AUCUN capteur de force (fiche+succes|echec).
# --------------------------------------------------------------------------- #
def test_la_boucle_n_emet_aucun_capteur_de_force(tmp_path, monkeypatch):
    mem, _racine = _setup(tmp_path, monkeypatch)
    _fiche(mem, "dom", "cat", "zorglubide", "Procédure zorglubide.")

    etat_path = tmp_path / "etat.json"
    orchestrateur.sauver_etat(etat_path, _etat_une_tache("Traiter la mission zorglubide"))

    from moteur import MoteurMock
    orchestrateur.tourner(etat_path, moteur=MoteurMock(), memoire=mem)

    # AUCUN event de force issu de la boucle : la force est un jugement HUMAIN.
    forces = [e for e in _capteurs()
              if e.get("fiche") and e.get("statut") in ("succes", "echec")]
    assert forces == [], "la boucle ne doit émettre AUCUN capteur de force"

    # La consultation de boucle a bien été CLÔTURÉE (administrativement) : aucune
    # consultation de boucle ouverte au bilan, aucune dette.
    import nexus_capital
    b = nexus_capital.bilan()
    assert b["n_ouvertes"] == 0 and b["n_dette"] == 0


# --------------------------------------------------------------------------- #
# 3) DOCTRINE : la boucle N'ÉCRIT PAS forces.json (aucune auto-récompense).
# --------------------------------------------------------------------------- #
def test_la_boucle_n_ecrit_pas_forces_json(tmp_path, monkeypatch):
    mem, racine_memoire = _setup(tmp_path, monkeypatch)
    _fiche(mem, "dom", "cat", "zorglubide", "Procédure zorglubide.")

    etat_path = tmp_path / "etat.json"
    orchestrateur.sauver_etat(
        etat_path,
        _etat_une_tache("Traiter la mission zorglubide",
                        "Retraiter la mission zorglubide"),
    )

    from moteur import MoteurMock
    orchestrateur.tourner(etat_path, moteur=MoteurMock(), memoire=mem)

    # La fiche a servi DEUX fois — pourtant forces.json n'existe pas : seul un
    # jeton humain (appliquer) écrirait de la force, jamais la boucle.
    chemin_forces = os.path.join(str(racine_memoire), "forces.json")
    assert not os.path.exists(chemin_forces)


def test_pas_de_fiche_pas_de_forces_ni_de_consultation(tmp_path, monkeypatch):
    """Sans fiche rappelée : aucune écriture forces.json ET aucune consultation
    fantôme (ni bruit de force, ni fausse dette au bilan)."""
    mem, racine_memoire = _setup(tmp_path, monkeypatch)
    # Pas de fiche en structure : recall ne trouvera rien.
    etat_path = tmp_path / "etat.json"
    orchestrateur.sauver_etat(etat_path, _etat_une_tache("Tâche sans rapport"))

    from moteur import MoteurMock
    orchestrateur.tourner(etat_path, moteur=MoteurMock(), memoire=mem)

    chemin_forces = os.path.join(str(racine_memoire), "forces.json")
    assert not os.path.exists(chemin_forces)

    import nexus_capital
    b = nexus_capital.bilan()
    assert b["n_actionnables"] == 0        # aucune consultation ouverte/close/dette
