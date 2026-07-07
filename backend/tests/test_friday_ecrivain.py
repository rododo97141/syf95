"""Friday brique 2+ — écrivain mémoire piloté par la voix.

Couvre la SPEC (négociée sur ~8 boucles) :
  - preparer_ecriture est PUR (n'ouvre aucun fichier, ne touche pas le disque) ;
  - confirmer_ecriture avec le BON jeton appelle stage() avec les bons champs,
    dont source="voix" ;
  - confirmer_ecriture avec un jeton absent/erroné est REFUSÉ (n'écrit rien) ;
  - confirmer_ecriture rejoué avec le MÊME jeton (replay) est REFUSÉ (usage unique) ;
  - annuler_ecriture n'écrit rien et journalise un capteur statut="ok" (jamais "echec") ;
  - relecture : certain=True + silence → confirmer invoqué ; certain=False + silence
    → confirmer PAS invoqué ; certain=False + "oui" → confirmer invoqué ;
  - GARDE AST : un seul point d'appel de stage() dans tout Friday ;
  - GARDE AST zone 3 : aucun primitif d'exécution (subprocess, os.system, os.popen,
    eval, exec, importlib/import_module, pty.spawn) sous aucune forme d'import,
    dans les modules Friday.

Les deux gardes AST sont fournies avec la PREUVE qu'elles ROUGISSENT : des
extraits mutés (un seul primitif réintroduit / un 2e appel stage() ajouté) sont
passés au même détecteur et doivent produire une violation. Isolation :
CAPTEURS_ROOT vient du conftest (autouse) ; le staging réel est écrit dans un
MEMOIRE_ROOT jetable (test d'intégration).
"""
import ast
import glob
import json
import os
import sys

import pytest


def _racine():
    ici = os.path.dirname(os.path.abspath(__file__))          # backend/tests
    return os.path.dirname(os.path.dirname(ici))              # racine du dépôt


def _organes():
    return os.path.join(_racine(), "organes")


if _organes() not in sys.path:
    sys.path.insert(0, _organes())
import friday_ecrivain  # noqa: E402


@pytest.fixture(autouse=True)
def _registre_propre():
    """Chaque test part d'un registre de jetons vierge (état de process)."""
    friday_ecrivain._REGISTRE.clear()
    yield
    friday_ecrivain._REGISTRE.clear()


# --------------------------------------------------------------------------- #
# Faux de mémoire injectable (aucun disque) — même patron d'injection que
# backend/orchestrateur : confirmer_ecriture(..., memoire=<fake>).
# --------------------------------------------------------------------------- #
class FakeMemoire:
    def __init__(self):
        self.appels = []

    def stage(self, data):
        self.appels.append(data)
        return {"ok": True, "etage": "en_attente", "id": "fake-id"}


class MemoireInterdite:
    """Toute écriture est une faute : stage() ne doit JAMAIS être appelée."""
    def stage(self, data):
        raise AssertionError("stage() ne doit pas être appelée ici")


def _journal_capteurs():
    chemin = os.path.join(os.environ["CAPTEURS_ROOT"], "capteurs", "journal.jsonl")
    if not os.path.exists(chemin):
        return []
    with open(chemin, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


# --------------------------------------------------------------------------- #
# 1) preparer_ecriture est PUR : n'ouvre AUCUN fichier, ne crée rien.
# --------------------------------------------------------------------------- #
def test_preparer_ne_touche_pas_le_disque(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMOIRE_ROOT", str(tmp_path / "mem"))  # inexistant

    import builtins
    def _open_interdit(*a, **k):
        raise AssertionError("preparer_ecriture ne doit ouvrir aucun fichier")
    monkeypatch.setattr(builtins, "open", _open_interdit)

    b1 = friday_ecrivain.preparer_ecriture("note acheter du pain", trigger_present=True)
    b2 = friday_ecrivain.preparer_ecriture("tache rappeler le médecin", trigger_present=False)

    assert b1 is not None and b2 is not None
    assert b1.certain is True and b2.certain is False       # trigger → certain
    assert b1.jeton and b2.jeton and b1.jeton != b2.jeton   # jetons uniques
    # Aucun fichier créé nulle part sous MEMOIRE_ROOT.
    assert not (tmp_path / "mem").exists()


def test_preparer_refuse_ce_qui_n_est_pas_une_ecriture():
    assert friday_ecrivain.preparer_ecriture("montre le moteur", trigger_present=True) is None
    assert friday_ecrivain.preparer_ecriture("note", trigger_present=True) is None  # sans argument


# --------------------------------------------------------------------------- #
# 2) confirmer_ecriture (bon jeton) → stage() avec les bons champs, source="voix"
# --------------------------------------------------------------------------- #
def test_confirmer_bon_jeton_appelle_stage_avec_source_voix():
    fake = FakeMemoire()
    b = friday_ecrivain.preparer_ecriture("note appeler le plombier", trigger_present=True)

    res = friday_ecrivain.confirmer_ecriture(b, b.jeton, memoire=fake)

    assert res["ok"] is True and res["ecrit"] is True
    assert len(fake.appels) == 1
    envoye = fake.appels[0]
    assert envoye["source"] == "voix"                 # exigence centrale
    assert envoye["content"] == "appeler le plombier"
    assert envoye["domain"] == "friday"
    assert envoye["category"] == "notes"              # note → catégorie notes
    assert envoye["origin"] == "friday:ecriture"


def test_confirmer_tache_va_en_categorie_taches():
    fake = FakeMemoire()
    b = friday_ecrivain.preparer_ecriture("tache réserver le train", trigger_present=True)
    friday_ecrivain.confirmer_ecriture(b, b.jeton, memoire=fake)
    assert fake.appels[0]["category"] == "taches"
    assert fake.appels[0]["source"] == "voix"


# --------------------------------------------------------------------------- #
# 3) confirmer_ecriture avec jeton absent / erroné → REFUSÉ, rien écrit
# --------------------------------------------------------------------------- #
def test_confirmer_jeton_absent_ou_errone_est_refuse():
    fake = MemoireInterdite()
    b = friday_ecrivain.preparer_ecriture("note quelque chose", trigger_present=True)

    r_absent = friday_ecrivain.confirmer_ecriture(b, None, memoire=fake)
    r_faux = friday_ecrivain.confirmer_ecriture(b, "jeton-forge-au-hasard", memoire=fake)

    assert r_absent["ok"] is False and r_absent["ecrit"] is False
    assert r_faux["ok"] is False and r_faux["ecrit"] is False
    # Rien n'a été consommé : le BON jeton fonctionne toujours ensuite.
    bon = FakeMemoire()
    ok = friday_ecrivain.confirmer_ecriture(b, b.jeton, memoire=bon)
    assert ok["ok"] is True and len(bon.appels) == 1


def test_confirmer_jeton_d_un_autre_brouillon_est_refuse():
    fake = MemoireInterdite()
    a = friday_ecrivain.preparer_ecriture("note A", trigger_present=True)
    b = friday_ecrivain.preparer_ecriture("note B", trigger_present=True)
    # Le jeton de A ne doit pas valider le brouillon B (correspondance exacte).
    r = friday_ecrivain.confirmer_ecriture(b, a.jeton, memoire=fake)
    assert r["ok"] is False and r["ecrit"] is False


# --------------------------------------------------------------------------- #
# 4) confirmer_ecriture rejoué avec le MÊME jeton (replay) → REFUSÉ
# --------------------------------------------------------------------------- #
def test_confirmer_replay_meme_jeton_est_refuse():
    fake = FakeMemoire()
    b = friday_ecrivain.preparer_ecriture("note à écrire une fois", trigger_present=True)

    premier = friday_ecrivain.confirmer_ecriture(b, b.jeton, memoire=fake)
    replay = friday_ecrivain.confirmer_ecriture(b, b.jeton, memoire=fake)

    assert premier["ok"] is True
    assert replay["ok"] is False and replay["ecrit"] is False
    assert len(fake.appels) == 1               # UNE seule écriture, pas deux


# --------------------------------------------------------------------------- #
# 5) annuler_ecriture : rien écrit + capteur statut="ok" (jamais "echec")
# --------------------------------------------------------------------------- #
def test_annuler_n_ecrit_rien_et_journalise_ok():
    b = friday_ecrivain.preparer_ecriture("note qui sera annulée", trigger_present=True)

    res = friday_ecrivain.annuler_ecriture(b)

    assert res["ok"] is True and res["ecrit"] is False
    evts = _journal_capteurs()
    ecr = [e for e in evts if e["tache"] == "friday:ecriture"]
    assert len(ecr) == 1
    assert ecr[0]["statut"] == "ok"                       # jamais "echec"
    assert all(e["statut"] != "echec" for e in evts)
    # Le jeton est invalidé : plus aucune écriture possible après annulation.
    r = friday_ecrivain.confirmer_ecriture(b, b.jeton, memoire=MemoireInterdite())
    assert r["ok"] is False


# --------------------------------------------------------------------------- #
# 6) Relecture obligatoire — silence=accord SEULEMENT si certain=True
# --------------------------------------------------------------------------- #
def _espion_confirmer(monkeypatch):
    appels = []
    def _faux(brouillon, jeton, memoire=None):
        appels.append((brouillon, jeton))
        return {"ok": True, "ecrit": True}
    monkeypatch.setattr(friday_ecrivain, "confirmer_ecriture", _faux)
    return appels


def test_certain_true_silence_confirme(monkeypatch):
    b = friday_ecrivain.preparer_ecriture("note importante", trigger_present=True)
    appels = _espion_confirmer(monkeypatch)

    friday_ecrivain.traiter_relecture(b, reponse_orale="", silence=True)

    assert appels == [(b, b.jeton)]                       # silence = accord (certain=True)


def test_certain_false_silence_ne_confirme_pas(monkeypatch):
    b = friday_ecrivain.preparer_ecriture("note ambiguë", trigger_present=False)
    appels = _espion_confirmer(monkeypatch)

    friday_ecrivain.traiter_relecture(b, reponse_orale="", silence=True)

    assert appels == []                                   # sans trigger, silence ≠ accord


def test_certain_false_oui_explicite_confirme(monkeypatch):
    b = friday_ecrivain.preparer_ecriture("note à confirmer", trigger_present=False)
    appels = _espion_confirmer(monkeypatch)

    friday_ecrivain.traiter_relecture(b, reponse_orale="Oui !", silence=False)

    assert appels == [(b, b.jeton)]                       # "oui" explicite requis et suffisant


def test_refus_oral_annule_dans_les_deux_cas(monkeypatch):
    appels = _espion_confirmer(monkeypatch)
    for trig in (True, False):
        b = friday_ecrivain.preparer_ecriture("note à refuser", trigger_present=trig)
        friday_ecrivain.traiter_relecture(b, reponse_orale="non", silence=True)
    assert appels == []                                   # un "non" explicite ne confirme jamais


# --------------------------------------------------------------------------- #
# GARDES AST — détecteurs réutilisables (appliqués aux vrais modules ET à des
# mutations, pour PROUVER que la garde rougit).
# --------------------------------------------------------------------------- #
def _modules_friday():
    return sorted(glob.glob(os.path.join(_organes(), "friday_*.py")))


def _source(chemin):
    with open(chemin, encoding="utf-8") as f:
        return f.read()


# --- détecteur : appels à stage() ---
def _appels_stage(source):
    """Liste les nœuds d'APPEL à stage() (par nom `stage(...)` ou par attribut
    `<x>.stage(...)`). Un import de stage n'est pas un appel."""
    arbre = ast.parse(source)
    return [n for n in ast.walk(arbre)
            if isinstance(n, ast.Call) and (
                (isinstance(n.func, ast.Name) and n.func.id == "stage")
                or (isinstance(n.func, ast.Attribute) and n.func.attr == "stage"))]


# --- détecteur : primitifs d'exécution interdits (zone 3) ---
_MODULES_INTERDITS = {"subprocess", "pty", "importlib"}      # tout accès interdit
_OS_ATTR_INTERDITS = {"system", "popen"}
_ATTR_INTERDITS = {
    "os": _OS_ATTR_INTERDITS,     # os.system / os.popen
    "subprocess": None,           # tout attribut de subprocess
    "pty": {"spawn"},             # pty.spawn
    "importlib": None,            # tout (dont importlib.import_module)
}
_BUILTINS_INTERDITS = {"eval", "exec"}


def _primitifs_interdits(source):
    """Toutes les manières de tendre vers un primitif d'exécution, sous TOUTE
    forme d'accès : `import X`, `import X as alias`, `from X import Y`, accès par
    attribut `alias.attr`, et les builtins eval/exec. Renvoie la liste des
    violations (vide = propre)."""
    arbre = ast.parse(source)
    violations = []
    alias = {}   # nom local → module réel surveillé (os / subprocess / pty / importlib)

    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            for a in n.names:
                top = a.name.split(".")[0]
                local = (a.asname or a.name).split(".")[0]
                if top in _MODULES_INTERDITS:
                    violations.append("import " + a.name
                                      + (" as " + a.asname if a.asname else ""))
                if top in ({"os"} | _MODULES_INTERDITS):
                    alias[local] = top
        elif isinstance(n, ast.ImportFrom):
            mod = (n.module or "").split(".")[0]
            if mod in _MODULES_INTERDITS:
                violations.append("from %s import ..." % n.module)
            elif mod == "os":
                for a in n.names:
                    if a.name in _OS_ATTR_INTERDITS:
                        violations.append("from os import " + a.name)

    for n in ast.walk(arbre):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
            mod = alias.get(n.value.id)
            if mod in _ATTR_INTERDITS:
                permis = _ATTR_INTERDITS[mod]
                if permis is None or n.attr in permis:
                    violations.append("%s.%s" % (n.value.id, n.attr))

    for n in ast.walk(arbre):
        if isinstance(n, ast.Name) and n.id in _BUILTINS_INTERDITS:
            violations.append(n.id)

    return violations


# --------------------------------------------------------------------------- #
# 7) GARDE AST : un SEUL point d'appel de stage() dans tout Friday
# --------------------------------------------------------------------------- #
def test_un_seul_point_d_appel_stage_dans_tout_friday():
    total = 0
    porteur = []
    for chemin in _modules_friday():
        appels = _appels_stage(_source(chemin))
        if appels:
            porteur.append(os.path.basename(chemin))
        total += len(appels)
    assert total == 1, f"stage() doit être appelé une seule fois ; trouvé {total}"
    assert porteur == ["friday_ecrivain.py"]              # et uniquement là


def test_garde_un_seul_stage_rougit_sur_mutation():
    """PREUVE de rougissement : un module Friday avec un 2e appel stage() serait
    détecté (total passerait à 2 → l'assertion `== 1` échouerait)."""
    mutant = "def f(memoire):\n    stage({'a': 1})\n    memoire.stage({'b': 2})\n"
    assert len(_appels_stage(mutant)) == 2


# --------------------------------------------------------------------------- #
# 8) GARDE AST zone 3 : aucun primitif d'exécution dans les modules Friday
# --------------------------------------------------------------------------- #
def test_aucun_primitif_execution_dans_les_modules_friday():
    for chemin in _modules_friday():
        violations = _primitifs_interdits(_source(chemin))
        assert violations == [], f"{os.path.basename(chemin)} : {violations}"


@pytest.mark.parametrize("mutant", [
    "import subprocess",
    "import subprocess as sp\nsp.run(['x'])",
    "from subprocess import run",
    "import os\nos.system('rm -rf /')",
    "import os\nos.popen('ls')",
    "from os import system",
    "eval('1 + 1')",
    "exec('x = 1')",
    "import importlib\nimportlib.import_module('os')",
    "from importlib import import_module",
    "import pty\npty.spawn('bash')",
])
def test_garde_zone3_rougit_sur_chaque_primitif(mutant):
    """PREUVE de rougissement : réintroduire UN SEUL primitif, sous n'importe
    quelle forme d'accès, produit au moins une violation."""
    assert _primitifs_interdits(mutant), f"mutation non détectée : {mutant!r}"


def test_garde_zone3_ne_flague_pas_les_usages_legitimes():
    """Contrôle négatif : os.path / os.environ.get / secrets ne sont PAS des
    primitifs d'exécution (sinon la garde serait un faux positif inutile)."""
    legitime = ("import os\nimport secrets\n"
                "os.path.join('a', 'b')\nos.environ.get('X')\n"
                "secrets.token_urlsafe(32)\n")
    assert _primitifs_interdits(legitime) == []


# --------------------------------------------------------------------------- #
# 9) INTÉGRATION RÉELLE : la vraie mémoire-beta écrit bien en_attente, source=voix
# --------------------------------------------------------------------------- #
def _memory_api_reel(racine_tmp):
    scripts = os.path.join(_racine(), ".claude", "skills", "memoire-beta", "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import memory_api
    root = str(racine_tmp)
    memory_api.ROOT = root
    memory_api.BRUT = os.path.join(root, "brut")
    memory_api.EN_ATTENTE = os.path.join(root, "en_attente")
    memory_api.STRUCT = os.path.join(root, "structure")
    memory_api.ARCHIVE = os.path.join(root, "archive")
    return memory_api


def test_integration_stage_reel_ecrit_en_attente_avec_source_voix(tmp_path):
    mem = _memory_api_reel(tmp_path / "mem")
    b = friday_ecrivain.preparer_ecriture("note appeler le plombier demain",
                                          trigger_present=True)

    res = friday_ecrivain.confirmer_ecriture(b, b.jeton, memoire=mem)

    assert res["ok"] is True and res["ecrit"] is True
    fiches = list((tmp_path / "mem" / "en_attente").glob("*.md"))
    assert len(fiches) == 1                               # bien mis en STAGING
    contenu = fiches[0].read_text(encoding="utf-8")
    assert "appeler le plombier demain" in contenu
    assert '"source": "voix"' in contenu                 # source=voix atteint le disque
    # N'a PAS écrit en structure (staging uniquement, jamais memorize).
    assert not (tmp_path / "mem" / "structure").exists() or \
        not list((tmp_path / "mem" / "structure").rglob("*.md"))
