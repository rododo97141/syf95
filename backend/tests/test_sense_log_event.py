"""Test du refactor de nexus_sense : log_event(**kwargs) + redirection CAPTEURS_ROOT.
Isolé : écrit dans tmp_path via CAPTEURS_ROOT, ne touche jamais le vrai memoire_data/capteurs/."""
import os, sys, json

def _organes():
    ici = os.path.dirname(os.path.abspath(__file__))          # backend/tests
    racine = os.path.dirname(os.path.dirname(ici))            # racine du repo
    return os.path.join(racine, "organes")

def test_log_event_ecrit_une_ligne_jsonl_valide(tmp_path, monkeypatch):
    org = _organes()
    if org not in sys.path:
        sys.path.insert(0, org)
    # Redirection propre vers tmp (pas de monkeypatch d'attribut, juste l'env)
    monkeypatch.setenv("CAPTEURS_ROOT", str(tmp_path))
    import nexus_sense

    ev = nexus_sense.log_event(tache="essai-pont", statut="ok", mode="auto",
                               tier="DUO", difficulte="moyen")
    journal = tmp_path / "capteurs" / "journal.jsonl"
    assert journal.exists(), "le journal doit être créé sous CAPTEURS_ROOT"
    lignes = journal.read_text(encoding="utf-8").strip().splitlines()
    assert len(lignes) == 1
    obj = json.loads(lignes[0])               # JSONL valide
    assert obj["tache"] == "essai-pont"
    assert obj["statut"] == "ok" and obj["mode"] == "auto" and obj["tier"] == "DUO"
    assert "ts" in obj
    # anti-Goodhart : feedback/impact non fournis -> restent None (jamais auto-remplis)
    assert obj["feedback"] is None and obj["impact"] is None
    assert ev["tache"] == "essai-pont"        # la fonction renvoie aussi l'événement
