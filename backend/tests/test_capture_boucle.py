"""La boucle écrit un capteur par tâche traitée (ok / bloque), via nexus_sense.
Isolé par le conftest (CAPTEURS_ROOT temporaire) : ne touche jamais le vrai journal."""
import json
import os

from orchestrateur import tourner


def test_la_boucle_ecrit_des_capteurs(tmp_path):
    racine_cap = os.environ["CAPTEURS_ROOT"]  # fixé (isolé) par le conftest
    etat = tourner(tmp_path / "etat.json")
    journal = os.path.join(racine_cap, "capteurs", "journal.jsonl")
    assert os.path.exists(journal), "la boucle doit écrire des capteurs"
    lignes = [json.loads(l) for l in open(journal, encoding="utf-8") if l.strip()]
    traitees = sum(1 for t in etat["taches"] if t["etat"] in ("fait", "bloque"))
    assert len(lignes) == traitees and traitees >= 5
    statuts = {e["statut"] for e in lignes}
    assert "ok" in statuts and "bloque" in statuts          # faites + sensible bloquée
    assert all(e["feedback"] is None and e["impact"] is None for e in lignes)  # anti-Goodhart
    assert all(e["tier"] in ("SOLO", "DUO", "CONSEIL") for e in lignes)        # dosage présent
