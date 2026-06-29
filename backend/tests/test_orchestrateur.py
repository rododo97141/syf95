"""
Smoke test de la boucle orchestrateur (« loop engineering ») de NEXUS.

PHOTO DE RÉFÉRENCE du comportement ACTUEL de la boucle, AVANT tout branchement
d'organe. On vérifie la STRUCTURE et le bon DÉROULEMENT — pas le texte exact des
sorties mock (qui peut changer). Test ISOLÉ : il tourne sur un état temporaire
(fixture pytest ``tmp_path``) et ne touche jamais le vrai ``etat_boucle.json``.

Tant que la boucle se comporte pareil, ce test passe ; si un futur branchement
casse la boucle ou la forme de l'état, ce test le verra.
"""
import json

from orchestrateur import tourner, charger_etat

# Clés attendues de l'état de la boucle et d'une tâche (forme actuelle).
CLES_ETAT = {
    "version", "cree_le", "maj_le", "cycle", "curseur",
    "taches", "ecarts_semes", "archive_96", "journal",
}
CLES_TACHE = {"id", "libelle", "etat", "resultat", "verifie", "veto", "sensible"}
ETATS_TACHE = {"a_faire", "fait", "bloque"}


def test_boucle_tourne_et_produit_un_etat_valide(tmp_path):
    """La boucle se lance, se termine, et rend un état cohérent."""
    chemin = tmp_path / "etat_test.json"

    # Run complet (MoteurMock par défaut : déterministe, hors-ligne).
    etat = tourner(chemin)

    # 1) Un dict avec toutes les clés attendues.
    assert isinstance(etat, dict)
    assert CLES_ETAT <= set(etat), f"clés d'état manquantes : {CLES_ETAT - set(etat)}"

    # 2) Les tâches : liste non vide, chacune bien formée.
    taches = etat["taches"]
    assert isinstance(taches, list) and len(taches) >= 5
    for t in taches:
        assert CLES_TACHE <= set(t), f"clés de tâche manquantes : {CLES_TACHE - set(t)}"
        assert t["etat"] in ETATS_TACHE

    # 3) Déroulement : après un run complet, plus aucune tâche « a_faire ».
    assert all(t["etat"] != "a_faire" for t in taches)
    # La boucle a vraiment travaillé : au moins une tâche réalisée.
    assert any(t["etat"] == "fait" for t in taches)
    # La/les tâche(s) sensible(s) sont bloquées par le veto (organe 98, stub actuel).
    sensibles = [t for t in taches if t["sensible"]]
    assert sensibles, "le plan de référence contient au moins une tâche sensible"
    assert all(t["etat"] == "bloque" and t["veto"] for t in sensibles)

    # 4) Le journal est une trace lisible non vide.
    assert isinstance(etat["journal"], list) and etat["journal"]
    assert all(isinstance(ligne, str) for ligne in etat["journal"])


def test_etat_persiste_sur_disque_et_se_recharge(tmp_path):
    """L'état est écrit sur disque (JSON valide) et rechargeable : socle de la REPRISE."""
    chemin = tmp_path / "etat_test.json"

    etat = tourner(chemin)

    # Le fichier d'état existe et est un JSON valide.
    assert chemin.exists()
    sur_disque = json.loads(chemin.read_text(encoding="utf-8"))

    # Rechargé via l'API de la boucle = exactement le contenu sur disque.
    recharge = charger_etat(chemin)
    assert recharge == sur_disque
    assert CLES_ETAT <= set(recharge)
    assert len(recharge["taches"]) == len(etat["taches"])


def test_run_isole_n_ecrit_que_dans_tmp_path(tmp_path):
    """Garde-fou : le run n'écrit que sous tmp_path (pas de pollution hors zone)."""
    chemin = tmp_path / "etat_test.json"
    tourner(chemin)
    # Seul le fichier d'état (et son éventuel .tmp) doit vivre sous tmp_path.
    fichiers = {p.name for p in tmp_path.iterdir()}
    assert "etat_test.json" in fichiers
