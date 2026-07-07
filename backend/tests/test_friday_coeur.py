"""Friday brique 1 — cœur : LA frontière texte→texte, traiter_ligne(texte) → str | None.
Commande reconnue → réponse TTS + capteur ok (force vivante via nexus_sense) ;
bruit ambiant → None, ZÉRO action du lecteur (prouvé par sabotage des actions),
capteur refus. Aucune dépendance audio dans les modules Friday (frontière)."""
import ast, json, os, sys


def _organes():
    ici = os.path.dirname(os.path.abspath(__file__))
    racine = os.path.dirname(os.path.dirname(ici))
    return os.path.join(racine, "organes")


org = _organes()
if org not in sys.path:
    sys.path.insert(0, org)
import friday_coeur
import friday_lecteur
import friday_routeur


def _mini_depot(tmp_path):
    racine = tmp_path / "mini"
    (racine / "organes").mkdir(parents=True)
    (racine / ".git").mkdir()
    (racine / ".git" / "HEAD").write_text("ref: refs/heads/branche-essai\n", encoding="utf-8")
    (racine / "organes" / "exemple.py").write_text(
        '"""Organe exemple : cible des tests de Friday."""\n\n'
        'def bonjour():\n'
        '    """Dit bonjour, rien de plus."""\n'
        '    return "bonjour"\n',
        encoding="utf-8")
    return racine


def _journal():
    """Capteurs écrits pendant le test (CAPTEURS_ROOT est isolé par conftest)."""
    chemin = os.path.join(os.environ["CAPTEURS_ROOT"], "capteurs", "journal.jsonl")
    if not os.path.exists(chemin):
        return []
    with open(chemin, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def test_commande_reconnue_reponse_texte_et_capteur_ok(tmp_path):
    racine = _mini_depot(tmp_path)
    reponse = friday_coeur.traiter_ligne("montre exemple.py", racine=str(racine))
    assert isinstance(reponse, str) and "exemple.py" in reponse
    evenements = _journal()
    assert len(evenements) == 1
    assert evenements[0]["tache"] == "friday:montre"
    assert evenements[0]["statut"] == "ok"
    assert evenements[0]["note"] == "exemple.py"


def test_chaque_intention_traverse_la_frontiere(tmp_path):
    racine = _mini_depot(tmp_path)
    lignes = ["où est bonjour", "explique exemple", "statut"]
    for ligne in lignes:
        assert isinstance(friday_coeur.traiter_ligne(ligne, racine=str(racine)), str)
    taches = [e["tache"] for e in _journal()]
    assert taches == ["friday:ou_est", "friday:explique", "friday:statut"]
    assert all(e["statut"] == "ok" for e in _journal())


def test_bruit_aucune_action_du_lecteur_et_capteur_refus(tmp_path, monkeypatch):
    def _interdit(*args, **kwargs):
        raise AssertionError("le lecteur ne doit JAMAIS être appelé sur du bruit")
    for action in ("chercher", "montrer", "expliquer", "statut"):
        monkeypatch.setattr(friday_lecteur, action, _interdit)
    bruit = [
        "il fait beau aujourd'hui",
        "tu peux fermer la fenêtre s'il te plaît",
        "on mange à quelle heure ce soir",
    ]
    for phrase in bruit:
        assert friday_coeur.traiter_ligne(phrase) is None
    evenements = _journal()
    assert [e["statut"] for e in evenements] == ["refus"] * len(bruit)
    assert all(e["tache"] == "friday:refus" for e in evenements)


def test_frontiere_texte_texte_aucune_dependance_audio():
    """La frontière est texte→texte : les modules Friday n'importent que la
    bibliothèque standard non audio et les organes du dépôt."""
    autorises = {"os", "sys", "ast", "unicodedata",
                 "friday_routeur", "friday_lecteur", "friday_ecrivain", "nexus_sense"}
    for module in (friday_coeur, friday_routeur, friday_lecteur):
        with open(module.__file__, encoding="utf-8") as f:
            arbre = ast.parse(f.read())
        importes = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                importes |= {a.name.split(".")[0] for a in noeud.names}
            elif isinstance(noeud, ast.ImportFrom):
                importes.add((noeud.module or "").split(".")[0])
        assert importes <= autorises, f"{module.__name__} importe hors frontière : {importes - autorises}"
