"""Friday brique 1 — lecteur : LECTURE SEULE PAR CONSTRUCTION, prouvée trois fois.
1) Verrou STRUCTUREL : inspection AST du module — imports fermés (os, ast),
   aucun open() hors mode "r"/"rb", aucun appel de mutation de fichiers.
2) Répertoire chmod LECTURE SEULE : toutes les actions passent sans erreur
   → zéro tentative d'écriture, zéro fichier créé.
3) Empreintes BINAIRES : aucun fichier lu n'est muté (sha256 avant/après),
   sur un mini-dépôt jetable ET sur organes/ du vrai dépôt."""
import ast, hashlib, os, sys


def _organes():
    ici = os.path.dirname(os.path.abspath(__file__))
    racine = os.path.dirname(os.path.dirname(ici))
    return os.path.join(racine, "organes")


org = _organes()
if org not in sys.path:
    sys.path.insert(0, org)
import friday_lecteur

CHEMIN_LECTEUR = os.path.join(org, "friday_lecteur.py")
IMPORTS_AUTORISES = {"os", "ast"}
APPELS_INTERDITS = {
    "write", "writelines", "makedirs", "mkdir", "remove", "unlink", "rename",
    "renames", "removedirs", "rmdir", "truncate", "chmod", "chown", "replace",
    "symlink", "link", "utime", "touch", "write_text", "write_bytes",
    "system", "popen", "run", "call",
}


def _arbre_lecteur():
    with open(CHEMIN_LECTEUR, encoding="utf-8") as f:
        return ast.parse(f.read())


def test_verrou_structurel_imports_fermes():
    importes = set()
    for noeud in ast.walk(_arbre_lecteur()):
        if isinstance(noeud, ast.Import):
            importes |= {a.name.split(".")[0] for a in noeud.names}
        elif isinstance(noeud, ast.ImportFrom):
            importes.add((noeud.module or "").split(".")[0])
    assert importes <= IMPORTS_AUTORISES, f"imports hors verrou : {importes - IMPORTS_AUTORISES}"


def test_verrou_structurel_aucun_chemin_ecriture():
    for noeud in ast.walk(_arbre_lecteur()):
        if not isinstance(noeud, ast.Call):
            continue
        fonction = noeud.func
        nom = fonction.id if isinstance(fonction, ast.Name) else (
            fonction.attr if isinstance(fonction, ast.Attribute) else None)
        assert nom not in APPELS_INTERDITS, f"appel interdit dans le lecteur : {nom}"
        if nom == "open":
            mode = None
            if len(noeud.args) >= 2 and isinstance(noeud.args[1], ast.Constant):
                mode = noeud.args[1].value
            for kw in noeud.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = kw.value.value
            assert mode in ("r", "rb"), f"open() doit être en lecture explicite, vu : {mode!r}"


# ---------- mini-dépôt jetable + empreintes ----------

def _mini_depot(tmp_path):
    racine = tmp_path / "mini"
    (racine / "organes").mkdir(parents=True)
    (racine / "backend" / "tests").mkdir(parents=True)
    (racine / ".git").mkdir()
    (racine / ".git" / "HEAD").write_text("ref: refs/heads/branche-essai\n", encoding="utf-8")
    (racine / "organes" / "exemple.py").write_text(
        '"""Organe exemple : cible des tests de Friday."""\n\n'
        'def bonjour():\n'
        '    """Dit bonjour, rien de plus."""\n'
        '    return "bonjour"\n',
        encoding="utf-8")
    (racine / "backend" / "tests" / "test_exemple.py").write_text(
        "def test_vrai():\n    assert True\n", encoding="utf-8")
    (racine / "notes.md").write_text("# Notes\nUne ligne.\n", encoding="utf-8")
    return racine


def _empreintes(racine):
    """sha256 de chaque fichier (hors __pycache__/.git : l'interpréteur peut y
    écrire des .pyc, ce ne sont pas des fichiers LUS par le lecteur)."""
    empreintes = {}
    for dossier, sous, noms in os.walk(racine):
        sous[:] = [s for s in sous if s not in ("__pycache__",)]
        for nom in noms:
            chemin = os.path.join(dossier, nom)
            with open(chemin, "rb") as f:
                empreintes[os.path.relpath(chemin, racine)] = hashlib.sha256(f.read()).hexdigest()
    return empreintes


def _toutes_actions(racine):
    r = str(racine)
    return [
        friday_lecteur.chercher("exemple", racine=r),
        friday_lecteur.chercher("bonjour", racine=r),
        friday_lecteur.montrer("exemple.py", racine=r),
        friday_lecteur.montrer("un fichier qui n'existe pas", racine=r),
        friday_lecteur.expliquer("exemple", racine=r),
        friday_lecteur.expliquer("bonjour", racine=r),
        friday_lecteur.statut(racine=r),
    ]


def test_repertoire_lecture_seule_zero_tentative_zero_erreur(tmp_path):
    racine = _mini_depot(tmp_path)
    avant = _empreintes(racine)
    chemins = [os.path.join(d, n) for d, _, noms in os.walk(racine) for n in noms]
    dossiers = [d for d, _, _ in os.walk(racine)]
    for chemin in chemins:
        os.chmod(chemin, 0o444)
    for dossier in dossiers:
        os.chmod(dossier, 0o555)
    try:
        sorties = _toutes_actions(racine)   # la moindre tentative d'écriture lèverait
    finally:
        for dossier in dossiers:
            os.chmod(dossier, 0o755)
        for chemin in chemins:
            os.chmod(chemin, 0o644)
    assert all(isinstance(s, str) and s for s in sorties)
    # même ensemble de fichiers (rien créé), mêmes octets (rien muté)
    assert _empreintes(racine) == avant


def test_empreintes_binaires_mini_depot_intact(tmp_path):
    racine = _mini_depot(tmp_path)
    avant = _empreintes(racine)
    _toutes_actions(racine)
    assert _empreintes(racine) == avant


def test_empreintes_binaires_vrai_depot_organes_intacts():
    racine_repo = os.path.dirname(org)
    avant = _empreintes(org)
    friday_lecteur.chercher("nexus_sense", racine=racine_repo)
    friday_lecteur.montrer("nexus_sense.py", racine=racine_repo)
    friday_lecteur.expliquer("log_event", racine=racine_repo)
    friday_lecteur.statut(racine=racine_repo)
    assert _empreintes(org) == avant


# ---------- comportement des actions (sortie = texte prêt pour un TTS) ----------

def test_chercher_trouve_fichier_et_fonction(tmp_path):
    racine = _mini_depot(tmp_path)
    sortie = friday_lecteur.chercher("bonjour", racine=str(racine))
    assert "def bonjour" in sortie and "exemple.py" in sortie


def test_montrer_donne_un_extrait(tmp_path):
    racine = _mini_depot(tmp_path)
    sortie = friday_lecteur.montrer("exemple.py", racine=str(racine))
    assert sortie.startswith("Extrait de") and "Organe exemple" in sortie


def test_expliquer_module_et_fonction(tmp_path):
    racine = _mini_depot(tmp_path)
    assert "cible des tests" in friday_lecteur.expliquer("exemple", racine=str(racine))
    assert "Dit bonjour" in friday_lecteur.expliquer("bonjour", racine=str(racine))


def test_statut_via_fichiers_locaux(tmp_path):
    racine = _mini_depot(tmp_path)
    sortie = friday_lecteur.statut(racine=str(racine))
    assert "branche-essai" in sortie          # branche lue dans .git/HEAD (fichier local)
    assert "1 fichiers de tests" in sortie and "1 organes" in sortie
