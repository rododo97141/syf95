"""Bureau 2D LIVE (nexus_bureau_live) — le serveur ne se lie QU'À la loopback.

Contexte : le Bureau live est hébergé pour un accès distant PRIVÉ (Kily seul, via
Tailscale), JAMAIS publié. La garantie porteuse de tout le montage est que le
serveur HTTP ne s'ouvre pas sur le LAN : il n'écoute que sur 127.0.0.1. Si un
jour le bind passait à 0.0.0.0 (ou à une interface publique), le Bureau serait
exposé à tout le réseau local — exactement ce qu'on refuse. Ce fichier verrouille
cette garantie par deux preuves complémentaires :

  1) COMPORTEMENTAL (la preuve qui compte) : on instancie le VRAI serveur par le
     MÊME chemin que main() — creer_serveur(port=0) — puis on lit l'adresse
     RÉELLEMENT liée par la socket (server_address / getsockname()) et on affirme
     qu'elle vaut 127.0.0.1. C'est le comportement observé, pas une lecture de
     source : si le défaut de bind changeait, ce test rougirait.

  2) STRUCTUREL (défense secondaire, ne remplace jamais le comportemental) : un
     garde AST bannit tout littéral de bind « ouvert » (0.0.0.0, chaîne vide,
     "0", ::) dans le module, et vérifie que main() n'introduit pas de --host ni
     ne passe d'hôte à creer_serveur. Il complète le test comportemental en
     attrapant une régression même si, un jour, personne ne lançait la socket.

Isolation : AGENTOS_ROOT / MEMOIRE_ROOT posés en fixture (les modules relisent
les contrats env à chaque appel) ; CAPTEURS_ROOT vient du conftest autouse.
"""
import ast
import os
import socket
import sys

import pytest


def _organes():
    ici = os.path.dirname(os.path.abspath(__file__))       # backend/tests
    racine = os.path.dirname(os.path.dirname(ici))          # racine du dépôt
    return os.path.join(racine, "organes")


if _organes() not in sys.path:
    sys.path.insert(0, _organes())
import nexus_bureau_live as live  # noqa: E402


@pytest.fixture(autouse=True)
def _isole(tmp_path, monkeypatch):
    """Bus + mémoire isolés par test dans des dossiers temporaires jetables."""
    monkeypatch.setenv("AGENTOS_ROOT", str(tmp_path / "_agentos"))
    monkeypatch.setenv("MEMOIRE_ROOT", str(tmp_path / "memoire_data"))
    # CAPTEURS_ROOT : déjà posé par le conftest autouse (tmp_path/_capteurs).


# --------------------------------------------------------------------------- #
# 1) PREUVE COMPORTEMENTALE : le serveur réellement instancié se lie à 127.0.0.1
# --------------------------------------------------------------------------- #
def test_le_serveur_se_lie_a_la_loopback():
    """Instancie le VRAI serveur comme main() le ferait (creer_serveur, sans
    passer d'hôte, port=0 pour un port libre), puis lit l'adresse RÉELLEMENT
    liée par la socket et affirme 127.0.0.1. C'est un test de comportement :
    on observe le bind effectif, pas la source. Un basculement du défaut vers
    0.0.0.0 le ferait rougir."""
    srv = live.creer_serveur(port=0)          # même appel que main(), hôte par défaut
    try:
        # (a) l'adresse enregistrée par le serveur HTTP…
        hote_enregistre = srv.server_address[0]
        # (b) …et l'adresse RÉELLEMENT liée par la socket noyau (getsockname()).
        hote_socket = srv.socket.getsockname()[0]
    finally:
        srv.server_close()

    assert hote_enregistre == "127.0.0.1", (
        f"le serveur s'annonce sur {hote_enregistre!r} au lieu de la loopback : "
        "le Bureau serait exposé hors de 127.0.0.1")
    assert hote_socket == "127.0.0.1", (
        f"la socket est réellement liée à {hote_socket!r} au lieu de 127.0.0.1 : "
        "le Bureau serait accessible sur le LAN, pas seulement via Tailscale")


def test_la_loopback_ne_repond_pas_hors_127():
    """Contre-preuve d'exposition : la socket liée à la loopback n'accepte AUCUNE
    connexion venue d'une adresse non-loopback. On tente de joindre le port sur
    l'IP LAN de la machine ; la connexion doit échouer (refus/timeout), preuve
    que rien n'écoute hors de 127.0.0.1. Si aucune IP LAN n'est disponible, on
    saute (l'environnement de CI peut n'avoir que la loopback)."""
    srv = live.creer_serveur(port=0)
    port = srv.server_address[1]
    import threading
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        ip_lan = _ip_lan()
        if ip_lan is None or ip_lan.startswith("127."):
            pytest.skip("aucune IP LAN non-loopback disponible dans cet environnement")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.5)
        with pytest.raises((ConnectionRefusedError, socket.timeout, OSError)):
            try:
                s.connect((ip_lan, port))
            finally:
                s.close()
    finally:
        srv.shutdown()
        srv.server_close()


def _ip_lan():
    """Meilleure estimation de l'IP LAN de la machine (sans trafic réel).
    Renvoie None si indéterminable."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))       # ne transmet rien : fixe juste l'IP source
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


# --------------------------------------------------------------------------- #
# 2) DÉFENSE SECONDAIRE (structurelle, AST) : aucun littéral de bind « ouvert »,
#    et main() n'introduit ni --host ni hôte passé à creer_serveur.
# --------------------------------------------------------------------------- #
_LITTERAUX_OUVERTS = {"0.0.0.0", "", "0", "::", "0:0:0:0:0:0:0:0"}


def _source():
    return open(os.path.join(_organes(), "nexus_bureau_live.py"),
                encoding="utf-8").read()


def _est_bind(call):
    """Vrai si l'appel est une construction de serveur (…HTTPServer(...)) ou un
    bind() de socket — les seules positions où un hôte est réellement lié."""
    f = call.func
    if isinstance(f, ast.Name):
        return f.id.endswith("HTTPServer") or f.id.endswith("Server")
    if isinstance(f, ast.Attribute):
        return f.attr in ("bind",) or f.attr.endswith("Server")
    return False


def _chaines_hote_dans_bind(arbre):
    """Récolte (lineno, valeur) de tout littéral chaîne placé en POSITION D'HÔTE
    d'un bind : premier élément du tuple d'adresse passé à un constructeur de
    serveur ou à socket.bind(). C'est là — et là seulement — qu'un littéral
    « ouvert » exposerait le service ; on ignore les "" / "0" innocents d'ailleurs
    (jointures HTML, défauts de query-string, etc.)."""
    trouves = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Call) and _est_bind(noeud) and noeud.args:
            adresse = noeud.args[0]
            if isinstance(adresse, ast.Tuple) and adresse.elts:
                hote = adresse.elts[0]
                if isinstance(hote, ast.Constant) and isinstance(hote.value, str):
                    trouves.append((hote.lineno, hote.value))
    return trouves


def test_aucun_littéral_de_bind_ouvert():
    """Garde anti-littéral (défense SECONDAIRE, en complément — jamais en
    remplacement — du test comportemental) : partout où un hôte est réellement
    lié (constructeur …HTTPServer, socket.bind), le littéral n'est JAMAIS un bind
    « ouvert » (0.0.0.0, chaîne vide, "0", ::). Cible les positions de bind pour
    ne pas confondre avec les "" / "0" innocents du reste du module."""
    trouves = _chaines_hote_dans_bind(ast.parse(_source()))
    ouverts = [(l, v) for (l, v) in trouves if v in _LITTERAUX_OUVERTS]
    assert ouverts == [], (
        f"littéral(aux) de bind « ouvert » en position d'hôte : {ouverts} "
        "— seul 127.0.0.1 est autorisé")
    # Et si un hôte littéral EST présent au bind, il doit valoir la loopback.
    for lineno, valeur in trouves:
        assert valeur == "127.0.0.1", (
            f"hôte littéral non-loopback lié ligne {lineno} : {valeur!r}")


def test_creer_serveur_a_pour_defaut_la_loopback():
    """Le défaut de l'argument `hote` de creer_serveur est EXACTEMENT
    "127.0.0.1" (lu sur l'AST). C'est ce défaut que main() utilise en ne passant
    jamais d'hôte."""
    arbre = ast.parse(_source())
    defs = [n for n in ast.walk(arbre)
            if isinstance(n, ast.FunctionDef) and n.name == "creer_serveur"]
    assert defs, "creer_serveur introuvable dans le module"
    fn = defs[0]

    noms = [a.arg for a in fn.args.args]
    assert "hote" in noms, "creer_serveur doit exposer un argument `hote`"

    # Le défaut aligné sur l'argument `hote` (defaults sont alignés à droite).
    idx = noms.index("hote")
    decalage = len(noms) - len(fn.args.defaults)
    assert idx >= decalage, "`hote` doit avoir une valeur par défaut"
    defaut = fn.args.defaults[idx - decalage]
    assert isinstance(defaut, ast.Constant) and defaut.value == "127.0.0.1", (
        f"le défaut de `hote` doit être '127.0.0.1', trouvé {ast.dump(defaut)}")


def test_main_ne_definit_pas_host_et_ne_passe_pas_d_hote():
    """main() doit rester neutre sur l'hôte : aucun argparse `--host`/`--hote`,
    et l'appel à creer_serveur ne passe QUE le port (jamais un second argument
    positionnel ni un kwarg `hote`) — sinon la valeur par défaut loopback
    pourrait être contournée depuis la CLI."""
    arbre = ast.parse(_source())
    mains = [n for n in ast.walk(arbre)
             if isinstance(n, ast.FunctionDef) and n.name == "main"]
    assert mains, "main introuvable dans le module"
    main = mains[0]

    for noeud in ast.walk(main):
        # (a) aucun add_argument("--host"/"--hote", ...)
        if (isinstance(noeud, ast.Call)
                and isinstance(noeud.func, ast.Attribute)
                and noeud.func.attr == "add_argument"):
            for arg in noeud.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    bas = arg.value.lower()
                    assert bas not in ("--host", "--hote", "-h"), (
                        f"argparse ne doit pas exposer {arg.value!r} : "
                        "l'hôte reste fixé à la loopback")
        # (b) creer_serveur(...) n'accepte qu'un seul argument (le port).
        if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
                and noeud.func.id == "creer_serveur"):
            assert len(noeud.args) <= 1, (
                "main() ne doit passer que le port à creer_serveur "
                "(un second positionnel serait l'hôte)")
            for kw in noeud.keywords:
                assert kw.arg != "hote", (
                    "main() ne doit pas passer `hote` à creer_serveur : "
                    "le défaut loopback doit rester en vigueur")
