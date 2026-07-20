"""État réel (nexus_etat_reel) — petit serveur HTTP LECTURE SEULE qui affiche
forces, vitalité et (si disponible) la config jeton_seuil.

Reprend le patron déjà prouvé de nexus_bureau_live.py (cf.
test_bureau_live.py / test_bureau_bind_loopback.py) : serveur stdlib,
page échappée, bind loopback codé en dur. Ce fichier vérifie ici :

  1) la page se sert (200, HTML, sans CDN ni JavaScript, avec la balise
     meta refresh) ;
  2) toute autre route → 404 ;
  3) forces + vitalité réelles sont agrégées et affichées, échappées ;
  4) nexus_jeton_seuil ABSENT (état réel de ce dépôt) → _etat() ne lève
     jamais et la page affiche « config indisponible » ;
  5) nexus_jeton_seuil PRÉSENT mais dont lire_config() lève → _etat() ne
     lève jamais non plus (le try/except autour de l'appel est bien là) ;
  6) même quand une config jeton_seuil contient de VRAIS secrets, aucun
     secret n'apparaît jamais dans le HTML rendu — seuls noms de parties
     et seuil sont montrés ;
  7) garde STRUCTUREL (AST) : le paramètre `hote` de creer_serveur reste
     bien codé en dur sur "127.0.0.1", jamais paramétrable.

Isolation : CAPTEURS_ROOT vient du conftest (autouse) ; MEMOIRE_ROOT est posé
par la fixture locale — nexus_force / nexus_vitalite relisent les contrats
env à chaque appel.
"""
import ast
import http.client
import os
import sys
import threading

import pytest


def _organes():
    ici = os.path.dirname(os.path.abspath(__file__))       # backend/tests
    racine = os.path.dirname(os.path.dirname(ici))          # racine du dépôt
    return os.path.join(racine, "organes")


if _organes() not in sys.path:
    sys.path.insert(0, _organes())
import nexus_etat_reel as etat_reel  # noqa: E402


@pytest.fixture(autouse=True)
def _isole(tmp_path, monkeypatch):
    """Forces + vitalité isolées par test dans un dossier temporaire jetable.
    CAPTEURS_ROOT : déjà posé par le conftest autouse (tmp_path/_capteurs)."""
    monkeypatch.setenv("MEMOIRE_ROOT", str(tmp_path / "memoire_data"))


def _ecrire_forces(tmp_path, forces):
    d = tmp_path / "memoire_data"
    d.mkdir(parents=True, exist_ok=True)
    import json
    (d / "forces.json").write_text(
        json.dumps(forces, ensure_ascii=False), encoding="utf-8")


def _serveur():
    """Serveur réel sur un port libre, servi dans un thread démon."""
    srv = etat_reel.creer_serveur(port=0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, srv.server_address[1]


def _get(port, chemin):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", chemin)
        rep = conn.getresponse()
        corps = rep.read().decode("utf-8")
        return rep.status, corps
    finally:
        conn.close()


class _FauxJetonSeuil:
    """Simule un module nexus_jeton_seuil (module non présent sur ce dépôt) :
    on injecte cet objet à la place de `etat_reel.nexus_jeton_seuil`, qui vaut
    None par défaut faute de module réel."""

    def __init__(self, config=None, exception=None):
        self._config = config
        self._exception = exception

    def lire_config(self):
        if self._exception is not None:
            raise self._exception
        return self._config


# --------------------------------------------------------------------------- #
# 1) la page se sert : 200, HTML, meta refresh, ni CDN ni JavaScript
# --------------------------------------------------------------------------- #
def test_get_racine_sert_la_page_html():
    srv, port = _serveur()
    try:
        statut, page = _get(port, "/")
    finally:
        srv.shutdown()
        srv.server_close()

    assert statut == 200
    assert page.strip()
    assert "<!DOCTYPE html>" in page
    assert "NEXUS" in page
    # Rafraîchissement simple par balise meta, PAS de websocket ni de poll JS.
    assert f'content="{etat_reel.REFRESH_S}"' in page
    assert "http-equiv=\"refresh\"" in page
    assert "<script" not in page.lower()
    # Autonome : aucune dépendance externe.
    assert "cdn" not in page.lower()
    assert "http://" not in page and "https://" not in page


# --------------------------------------------------------------------------- #
# 2) toute autre route → 404
# --------------------------------------------------------------------------- #
def test_route_inconnue_404():
    srv, port = _serveur()
    try:
        statut, _ = _get(port, "/autre-chose")
    finally:
        srv.shutdown()
        srv.server_close()
    assert statut == 404


# --------------------------------------------------------------------------- #
# 3) forces + vitalité réelles agrégées et affichées, échappées
# --------------------------------------------------------------------------- #
def test_forces_et_vitalite_reelles_affichees_et_echappees(tmp_path, monkeypatch):
    _ecrire_forces(tmp_path, {"agent<script>": 2.5})
    monkeypatch.setattr(
        etat_reel.nexus_vitalite, "mesurer_vitalite", lambda: {"une-fiche": None})
    monkeypatch.setattr(
        etat_reel.nexus_vitalite, "indice_vitalite", lambda brut=None: {"une-fiche": 0.75})

    etat = etat_reel._etat()
    assert etat["forces"] == {"agent<script>": 2.5}
    assert etat["vitalite"] == {"une-fiche": 0.75}

    page = etat_reel._page_html(etat)
    assert "x2.5000" in page
    assert "0.75" in page
    assert "une-fiche" in page
    # Le nom d'agent est échappé : jamais de balise brute injectée dans le HTML.
    assert "<script>" not in page
    assert "agent&lt;script&gt;" in page


# --------------------------------------------------------------------------- #
# 4) nexus_jeton_seuil ABSENT (état réel de ce dépôt) : jamais d'exception,
#    la page affiche « config indisponible »
# --------------------------------------------------------------------------- #
def test_jeton_seuil_absent_affiche_config_indisponible_sans_exception():
    assert etat_reel.nexus_jeton_seuil is None  # état réel : le module n'existe pas encore

    etat = etat_reel._etat()  # ne doit lever aucune exception
    assert etat["jeton_disponible"] is False
    assert etat["jeton_seuil"] is None
    assert etat["jeton_parties"] == []

    page = etat_reel._page_html(etat)
    assert "indisponible" in page.lower()


# --------------------------------------------------------------------------- #
# 5) nexus_jeton_seuil PRÉSENT mais lire_config() lève : _etat() ne lève
#    jamais non plus (le try/except autour de l'APPEL, pas seulement de
#    l'import, est bien là)
# --------------------------------------------------------------------------- #
def test_jeton_seuil_qui_leve_ne_casse_jamais_etat(monkeypatch):
    monkeypatch.setattr(
        etat_reel, "nexus_jeton_seuil",
        _FauxJetonSeuil(exception=RuntimeError("config corrompue")))

    etat = etat_reel._etat()  # ne doit PAS propager RuntimeError
    assert etat["jeton_disponible"] is False
    assert etat["jeton_seuil"] is None
    assert etat["jeton_parties"] == []

    page = etat_reel._page_html(etat)
    assert "indisponible" in page.lower()


# --------------------------------------------------------------------------- #
# 6) même avec une config jeton_seuil contenant de VRAIS secrets, aucun secret
#    n'apparaît JAMAIS dans le HTML rendu — seuls noms de parties + seuil
# --------------------------------------------------------------------------- #
def test_secret_jamais_affiche_meme_avec_config_jeton_seuil_secrets(monkeypatch):
    secret_alice = "SECRET-DE-TEST-9f8e7d21"
    secret_bob = "AUTRE-SECRET-DE-TEST-abc123"
    secret_global = "SECRET-GLOBAL-DE-TEST-zzz999"
    config = {
        "seuil": 3,
        "secret_global": secret_global,
        "parties": [
            {"nom": "Alice", "jeton": secret_alice},
            {"nom": "Bob", "secret": secret_bob},
        ],
    }
    monkeypatch.setattr(etat_reel, "nexus_jeton_seuil", _FauxJetonSeuil(config=config))

    etat = etat_reel._etat()
    assert etat["jeton_disponible"] is True
    assert etat["jeton_seuil"] == 3
    assert etat["jeton_parties"] == ["Alice", "Bob"]
    # L'état agrégé lui-même ne transporte aucun secret au-delà de _etat().
    assert secret_alice not in str(etat) and secret_bob not in str(etat)
    assert secret_global not in str(etat)

    page = etat_reel._page_html(etat)
    assert "Alice" in page and "Bob" in page
    assert "3" in page
    assert secret_alice not in page
    assert secret_bob not in page
    assert secret_global not in page


# --------------------------------------------------------------------------- #
# 7) garde STRUCTUREL (AST) : `hote` de creer_serveur reste codé en dur sur
#    "127.0.0.1" — jamais paramétrable depuis l'extérieur
# --------------------------------------------------------------------------- #
def test_creer_serveur_hote_code_en_dur_127_0_0_1():
    source = open(
        os.path.join(_organes(), "nexus_etat_reel.py"), encoding="utf-8").read()
    arbre = ast.parse(source)

    defs = [n for n in ast.walk(arbre)
            if isinstance(n, ast.FunctionDef) and n.name == "creer_serveur"]
    assert defs, "creer_serveur introuvable dans le module"
    fn = defs[0]

    noms = [a.arg for a in fn.args.args]
    assert "hote" in noms, "creer_serveur doit exposer un argument `hote`"

    idx = noms.index("hote")
    decalage = len(noms) - len(fn.args.defaults)
    assert idx >= decalage, "`hote` doit avoir une valeur par défaut"
    defaut = fn.args.defaults[idx - decalage]
    assert isinstance(defaut, ast.Constant) and defaut.value == "127.0.0.1", (
        f"le défaut de `hote` doit être '127.0.0.1', trouvé {ast.dump(defaut)}")

    # main() ne doit exposer aucun --host/--hote, ni passer `hote` explicitement.
    mains = [n for n in ast.walk(arbre)
             if isinstance(n, ast.FunctionDef) and n.name == "main"]
    assert mains, "main introuvable dans le module"
    main = mains[0]
    for noeud in ast.walk(main):
        if (isinstance(noeud, ast.Call)
                and isinstance(noeud.func, ast.Attribute)
                and noeud.func.attr == "add_argument"):
            for arg in noeud.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    assert arg.value.lower() not in ("--host", "--hote", "-h"), (
                        f"argparse ne doit pas exposer {arg.value!r}")
        if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
                and noeud.func.id == "creer_serveur"):
            assert len(noeud.args) <= 1, (
                "main() ne doit passer que le port à creer_serveur")
            for kw in noeud.keywords:
                assert kw.arg != "hote", "main() ne doit pas passer `hote`"
