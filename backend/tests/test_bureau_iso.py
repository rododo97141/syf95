"""Bureau 3D ISOMÉTRIQUE (skin esthétique du bureau LIVE) — LECTURE SEULE.

Ce skin ne change QUE le template HTML/CSS/JS servi par GET / de
nexus_bureau_live : les cartes agents 2D deviennent une scène isométrique
(grille en losanges, agents en jetons SVG). Rien côté serveur ne bouge, aucune
dépendance n'est ajoutée. On verrouille ici, à la lettre, les six points du
mandat :

  (1) INVARIANT SERVEUR : synthese() (nexus_bureau_agentos), le handler /events
      (BureauLiveHandler.do_GET) et nexus_bus.lire_depuis doivent rester
      byte-for-byte identiques à la version mergée en PR #55 — prouvé par une
      EMPREINTE FIGÉE (sha256 du corps source) de chaque fonction, pas par une
      simple absence de diff visuel.
  (2) le template servi par GET / rend bien une scène ISOMÉTRIQUE (SVG/CSS,
      losanges) à la place des cartes 2D ;
  (4) AUCUNE dépendance externe : ni three.js, ni CDN, ni URL, ni <link>/<script
      src> — HTML/CSS/JS vanilla ;
  (5) le VERROU AST zéro-écriture est ÉTENDU au nouveau template (le rendu
      isométrique n'appelle aucun mutateur du monde ni open() en écriture) ;
  (6) tout ce que le rendu isométrique veut (position, rang, état visuel) est
      calculé CÔTÉ CLIENT depuis ce que /events fournit DÉJÀ — le serveur
      n'expose AUCUN nouveau champ (ni x, ni y, ni rang, ni état).

Le point (3) — fil de conversation + KPIs affichés à côté de la scène — est
vérifié par test_scene_fil_et_kpis_cote_a_cote et reste couvert par la suite
historique test_bureau_live (fil live, KPIs, tail O(1), lecture seule, etc.).

Isolation : CAPTEURS_ROOT vient du conftest (autouse) ; AGENTOS_ROOT et
MEMOIRE_ROOT sont posés par la fixture locale.
"""
import ast
import hashlib
import http.client
import inspect
import json
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
import nexus_bus              # noqa: E402
import nexus_bureau_agentos as bureau  # noqa: E402
import nexus_bureau_live as live       # noqa: E402


@pytest.fixture(autouse=True)
def _isole(tmp_path, monkeypatch):
    """Bus + mémoire isolés par test dans des dossiers temporaires jetables."""
    monkeypatch.setenv("AGENTOS_ROOT", str(tmp_path / "_agentos"))
    monkeypatch.setenv("MEMOIRE_ROOT", str(tmp_path / "memoire_data"))


def _pub(exp, dest, type="demande", contenu="ping", ref=None):
    return nexus_bus.publier(
        nexus_bus.creer_message(exp, dest, type, contenu, ref=ref))


def _serveur():
    srv = live.creer_serveur(port=0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, srv.server_address[1]


def _get(port, chemin):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", chemin)
        rep = conn.getresponse()
        return rep.status, rep.read().decode("utf-8")
    finally:
        conn.close()


def _get_json(port, chemin):
    statut, corps = _get(port, chemin)
    return statut, json.loads(corps)


# --------------------------------------------------------------------------- #
# (1) INVARIANT SERVEUR : empreintes FIGÉES du contrat PR #55
# --------------------------------------------------------------------------- #
# sha256 du corps source EXACT (inspect.getsource) des trois fonctions serveur
# telles que mergées en PR #55. Vérifié : `git diff bfe2f54 HEAD` est VIDE pour
# organes/nexus_bureau_agentos.py, nexus_bureau_live.py et nexus_bus.py — donc
# la source actuelle EST, byte-for-byte, celle de la PR #55 (merge bfe2f54).
# Ce skin isométrique ne touche QUE le template (page_live/_SCRIPT_LIVE/...),
# jamais ces trois fonctions : si l'une d'elles change, ces empreintes rougissent.
REF_PR55 = {
    "nexus_bureau_agentos.synthese":
        "f7108ecf5453260df6c58340b2a66b539a01abc464e6f7c442a2ce710ae24b19",
    "nexus_bureau_live.BureauLiveHandler.do_GET (handler /events)":
        "8cdab2d3a5efa8733cc46585602a64dc7e5c3c468ed305e300de88768ff0f104",
    "nexus_bus.lire_depuis":
        "e6e444cae3cb2dadd8de5d9ba1f906a632d7b88cf5031fdac40254c86d2a43f3",
}


def _empreinte_corps(fn):
    """sha256 du corps source EXACT d'une fonction (inspect.getsource)."""
    return hashlib.sha256(inspect.getsource(fn).encode("utf-8")).hexdigest()


def test_invariant_serveur_byte_for_byte_pr55():
    cibles = {
        "nexus_bureau_agentos.synthese": bureau.synthese,
        "nexus_bureau_live.BureauLiveHandler.do_GET (handler /events)":
            live.BureauLiveHandler.do_GET,
        "nexus_bus.lire_depuis": nexus_bus.lire_depuis,
    }
    for nom, fn in cibles.items():
        courant = _empreinte_corps(fn)
        assert courant == REF_PR55[nom], (
            f"INVARIANT ROMPU — {nom} n'est plus identique à PR #55.\n"
            f"  attendu (PR #55) : {REF_PR55[nom]}\n"
            f"  obtenu           : {courant}\n"
            f"Ce skin isométrique doit laisser le serveur inchangé : "
            f"synthese(), le handler /events et lire_depuis sont figés.")


def test_events_ne_fournit_aucun_champ_de_position_ni_de_rang():
    """(6) Le serveur n'expose RIEN de nouveau pour le rendu isométrique :
    /events garde EXACTEMENT ses clés PR #55 {messages, offset, forces,
    flux_max}, et chaque message garde le schéma du bus (aucun x/y/rang/état).
    Toute géométrie est donc forcément déduite côté client."""
    _pub("A", "B", "demande", "un")
    _pub("B", "A", "reponse", "deux")
    srv, port = _serveur()
    try:
        _, j = _get_json(port, "/events?since=0")
    finally:
        srv.shutdown()
        srv.server_close()

    assert set(j.keys()) == {"messages", "offset", "forces", "flux_max"}
    for m in j["messages"]:
        # Schéma bus strict : aucune coordonnée / rang / état visuel injecté.
        assert set(m.keys()) <= set(nexus_bus.CHAMPS)
        for interdit in ("x", "y", "col", "row", "rang", "etat", "position"):
            assert interdit not in m


# --------------------------------------------------------------------------- #
# (2) le template servi par GET / est une SCÈNE ISOMÉTRIQUE (SVG/losanges)
# --------------------------------------------------------------------------- #
def test_page_rend_une_scene_isometrique():
    _pub("champion", "*", "proposition", "je propose")
    _pub("agentA", "agentB", "demande", "confirme ?")
    srv, port = _serveur()
    try:
        statut, page = _get(port, "/")
    finally:
        srv.shutdown()
        srv.server_close()

    assert statut == 200
    # La zone de scène et son conteneur isométrique sont présents.
    assert 'id="scene"' in page
    assert "scene-wrap" in page
    # Le skin est bien ISOMÉTRIQUE (vocabulaire de la grille en losanges + SVG).
    assert "isom" in page.lower()          # « isométrique » dans le titre/sous-titre
    assert "svg.iso" in page               # styles de la scène SVG
    assert "rendreScene" in page           # le constructeur de scène côté client
    assert "function losange(" in page     # la fabrique de losanges
    assert "isoCentre" in page             # la projection isométrique
    assert 'class="iso" viewBox=' in page  # un vrai <svg> est construit


def test_scene_fil_et_kpis_cote_a_cote():
    """(3) La scène isométrique cohabite avec le fil de conversation ET les
    KPIs — les trois sont dans la même page, autour de la scène."""
    _pub("A", "B", "reponse", "salut")
    srv, port = _serveur()
    try:
        _, page = _get(port, "/")
    finally:
        srv.shutdown()
        srv.server_close()
    assert 'id="scene"' in page                     # la scène
    assert 'class="fil" id="fil"' in page           # le fil de conversation
    assert 'id="kpi-agents"' in page                 # les KPIs
    assert 'id="kpi-messages"' in page
    assert 'id="kpi-types"' in page
    assert "Fil de conversation" in page


# --------------------------------------------------------------------------- #
# (4) AUCUNE dépendance externe — vanilla, zéro CDN / three.js / URL
# --------------------------------------------------------------------------- #
def test_zero_dependance_externe():
    _pub("A", "B", "demande", "x")
    srv, port = _serveur()
    try:
        _, page = _get(port, "/")
    finally:
        srv.shutdown()
        srv.server_close()
    bas = page.lower()
    assert "http://" not in page and "https://" not in page  # aucune URL absolue
    assert "cdn" not in bas
    assert "three" not in bas                # pas de three.js
    assert "<link" not in bas                # aucune feuille/police externe
    assert "src=" not in bas                 # aucun script/asset externe chargé
    assert "import " not in page             # pas de module JS distant


# --------------------------------------------------------------------------- #
# (5) VERROU AST zéro-écriture ÉTENDU au nouveau template isométrique
# --------------------------------------------------------------------------- #
_MUTATEURS = {"publier", "ecrire_forces", "ecrire_html", "appliquer", "log_event"}


def _scanner(source):
    """Renvoie (attributs appelés, modes des open() en écriture) dans `source`."""
    arbre = ast.parse(source)
    attrs, ecritures = set(), []
    for n in ast.walk(arbre):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            attrs.add(n.func.attr)
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "open"):
            mode = "r"
            if len(n.args) >= 2 and isinstance(n.args[1], ast.Constant):
                mode = n.args[1].value
            for kw in n.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = kw.value.value
            if any(c in str(mode) for c in "wax+"):
                ecritures.append(mode)
    return attrs, ecritures


def test_verrou_ast_etendu_au_rendu_isometrique():
    """Le garde zéro-écriture de PR #55 est ÉTENDU aux fonctions qui produisent
    le NOUVEAU template (page_live + _corps_initial) : aucune ouverture en
    écriture, aucun mutateur du monde appelé. Et on lie le garde au skin
    isométrique réel (markers présents), pour qu'il ne puisse pas passer sur un
    rendu obsolète. Ce test est CAPABLE DE ROUGIR : glisser un
    `nexus_bus.publier(...)` dans page_live le fait échouer (preuve de mutation
    rouge/vert dans la description de PR)."""
    source = (inspect.getsource(live.page_live) + "\n"
              + inspect.getsource(live._corps_initial))
    attrs, ecritures = _scanner(source)

    assert ecritures == [], (
        f"ouverture(s) en écriture dans le rendu isométrique : {ecritures}")
    assert not (attrs & _MUTATEURS), (
        f"mutateur du monde appelé dans le rendu : {sorted(attrs & _MUTATEURS)}")

    # Le garde porte bien sur le NOUVEAU template (scène isométrique), pas sur
    # un rendu 2D résiduel : les marqueurs du skin doivent être là.
    assert "rendreScene" in live._SCRIPT_LIVE
    assert 'class="iso"' in live._SCRIPT_LIVE
    assert "isoCentre" in live._SCRIPT_LIVE
    assert 'id="scene"' in live.page_live()


# --------------------------------------------------------------------------- #
# Échappement : le rendu isométrique n'insère AUCUN texte de message brut
# --------------------------------------------------------------------------- #
def test_scene_echappe_noms_et_contenus():
    """La scène côté client passe TOUT ce qui vient du bus par esc() : le nom
    de l'agent, le résumé de son dernier message (infobulle). Preuve statique
    sur le corps du script embarqué."""
    src = live._SCRIPT_LIVE
    assert "function esc(" in src
    assert "esc(k.nom)" in src                    # nom d'agent échappé
    assert "esc(resumer(dernier.contenu))" in src  # dernier message échappé
    assert "esc(resumer(m.contenu))" in src        # contenu du fil échappé


def test_scene_echappe_injection_dans_le_repli_serveur():
    """Le rendu initial (repli sans JavaScript, servi dans #scene) échappe
    l'injection HTML côté serveur, comme le bureau prouvé."""
    _pub("A", "B", "demande", "<script>alert('xss')</script>")
    srv, port = _serveur()
    try:
        _, page = _get(port, "/")
    finally:
        srv.shutdown()
        srv.server_close()
    assert "<script>alert" not in page
    assert "&lt;script&gt;alert" in page
