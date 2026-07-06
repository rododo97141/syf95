"""Bureau 2D LIVE de l'Agent OS (nexus_bureau_live) — serveur LECTURE SEULE.

Le mariage de deux briques prouvées : le serveur lecture seule de la Ligue
(nexus_ligue : http.server stdlib, tail-since-offset O(1)) et le rendu du
bureau agentos (nexus_bureau_agentos). On vérifie ici, à la lettre, la spec de
la brique « 2D live » :

  1) le handler sert la page HTML (200, non vide) ;
  2) /events?since=0 = TOUS les messages ; /events?since=OFFSET = SEULEMENT les
     nouveaux (+ un nouvel offset stable quand rien ne bouge) ;
  3) tail O(1) : le delta lu à 1 message et à 5000 messages ne dépend pas de la
     taille totale du bus (mesuré et imprimé) ;
  4) échappement HTML dans le fil (anti-injection), côté serveur ET côté script ;
  5) LECTURE SEULE prouvée par empreintes binaires : bus + mémoire INCHANGÉS
     après une série de requêtes, et verrou STRUCTUREL sur l'AST (ZÉRO ouverture
     en écriture, aucun mutateur du monde appelé) ;
  6) robustesse : bus vide/absent → page « aucun agent » sans erreur.

Isolation : CAPTEURS_ROOT vient du conftest (autouse) ; AGENTOS_ROOT et
MEMOIRE_ROOT sont posés par la fixture locale — les modules relisent les
contrats env à chaque appel.
"""
import ast
import json
import os
import sys
import time
import threading
import http.client

import pytest


def _organes():
    ici = os.path.dirname(os.path.abspath(__file__))       # backend/tests
    racine = os.path.dirname(os.path.dirname(ici))          # racine du dépôt
    return os.path.join(racine, "organes")


if _organes() not in sys.path:
    sys.path.insert(0, _organes())
import nexus_bus            # noqa: E402
import nexus_force          # noqa: E402
import nexus_bureau_live as live  # noqa: E402


@pytest.fixture(autouse=True)
def _isole(tmp_path, monkeypatch):
    """Bus + mémoire isolés par test dans des dossiers temporaires jetables."""
    monkeypatch.setenv("AGENTOS_ROOT", str(tmp_path / "_agentos"))
    monkeypatch.setenv("MEMOIRE_ROOT", str(tmp_path / "memoire_data"))
    # CAPTEURS_ROOT : déjà posé par le conftest autouse (tmp_path/_capteurs).


def _pub(exp, dest, type="demande", contenu="ping", ref=None):
    """Publie un vrai message sur le bus de test (construit un bus réaliste)."""
    return nexus_bus.publier(
        nexus_bus.creer_message(exp, dest, type, contenu, ref=ref))


def _ecrire_forces(tmp_path, forces):
    d = tmp_path / "memoire_data"
    d.mkdir(parents=True, exist_ok=True)
    (d / "forces.json").write_text(
        json.dumps(forces, ensure_ascii=False), encoding="utf-8")
    return d / "forces.json"


def _serveur():
    """Serveur réel sur un port libre, servi dans un thread démon."""
    srv = live.creer_serveur(port=0)
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


def _get_json(port, chemin):
    statut, corps = _get(port, chemin)
    return statut, json.loads(corps)


# --------------------------------------------------------------------------- #
# 1) le handler sert la page HTML (200, non vide)
# --------------------------------------------------------------------------- #
def test_handler_sert_la_page_html():
    _pub("agentA", "agentB", "demande", "bonjour, une question ?")
    _pub("agentB", "agentA", "reponse", "voici la réponse")
    srv, port = _serveur()
    try:
        statut, page = _get(port, "/")
    finally:
        srv.shutdown()
        srv.server_close()

    assert statut == 200
    assert page.strip()                       # non vide
    assert "<!DOCTYPE html>" in page          # page HTML complète
    assert "BUREAU NEXUS" in page and "LIVE" in page
    # Le rendu initial contient déjà les agents et le contenu réels.
    assert "agentA" in page and "agentB" in page
    assert "voici la réponse" in page
    # Live : un script de poll est bien présent (c'est ce qui fait le direct).
    assert "<script" in page.lower()
    assert "/events?since=" in page
    # Autonome : aucune dépendance externe (ni CDN, ni URL absolue).
    assert "cdn" not in page.lower()
    assert "http://" not in page and "https://" not in page


def test_page_sert_aussi_sur_index_html():
    srv, port = _serveur()
    try:
        s1, _ = _get(port, "/")
        s2, _ = _get(port, "/index.html")
    finally:
        srv.shutdown()
        srv.server_close()
    assert s1 == 200 and s2 == 200


def test_route_inconnue_404():
    srv, port = _serveur()
    try:
        statut, j = _get_json(port, "/nulle-part")
    finally:
        srv.shutdown()
        srv.server_close()
    assert statut == 404
    assert "erreur" in j


# --------------------------------------------------------------------------- #
# 2) /events?since=0 = tous ; /events?since=OFFSET = seulement les nouveaux
# --------------------------------------------------------------------------- #
def test_events_since0_tout_puis_since_offset_delta():
    _pub("A", "B", "demande", "un")
    _pub("B", "A", "reponse", "deux")
    srv, port = _serveur()
    try:
        # since=0 : TOUS les messages, dans l'ordre du bus.
        statut, j = _get_json(port, "/events?since=0")
        assert statut == 200
        assert [m["contenu"] for m in j["messages"]] == ["un", "deux"]
        off1 = j["offset"]
        assert off1 > 0

        # Rien de neuf : liste vide ET offset STABLE.
        _, j = _get_json(port, f"/events?since={off1}")
        assert j["messages"] == []
        assert j["offset"] == off1

        # Un nouveau message : SEUL le delta revient, jamais l'historique.
        _pub("A", "B", "demande", "trois")
        _, j = _get_json(port, f"/events?since={off1}")
        assert [m["contenu"] for m in j["messages"]] == ["trois"]
        assert j["offset"] > off1

        # Relire depuis le nouvel offset : de nouveau rien.
        off2 = j["offset"]
        _, j = _get_json(port, f"/events?since={off2}")
        assert j["messages"] == [] and j["offset"] == off2
    finally:
        srv.shutdown()
        srv.server_close()


def test_events_expose_forces_et_flux_max(tmp_path):
    _ecrire_forces(tmp_path, {"champion": 3.5})
    _pub("champion", "public", "proposition", "je gagne")
    srv, port = _serveur()
    try:
        _, j = _get_json(port, "/events?since=0")
    finally:
        srv.shutdown()
        srv.server_close()
    # Les forces vivantes voyagent avec le delta (cartes à jour à chaque poll).
    assert j["forces"]["champion"] == 3.5
    assert j["flux_max"] == live.bureau.FLUX_MAX_DEFAUT


def test_events_since_invalide_repart_de_zero():
    _pub("A", "B", "demande", "x")
    srv, port = _serveur()
    try:
        _, j = _get_json(port, "/events?since=pasunentier")
        assert [m["contenu"] for m in j["messages"]] == ["x"]
    finally:
        srv.shutdown()
        srv.server_close()


# --------------------------------------------------------------------------- #
# 3) tail O(1) : le delta ne dépend pas de la taille totale du bus
# --------------------------------------------------------------------------- #
def _mesurer_delta(offset_apres_ajout, repetitions=30):
    """Publie UN message puis chronomètre la lecture du delta (1 message)
    depuis l'offset de fin. min() sur N répétitions écrase le bruit d'OS."""
    mesures = []
    for _ in range(repetitions):
        _, offset = nexus_bus.lire_depuis(0)      # offset de fin courant
        _pub("mesure", "banc", "capteur", "tic")  # +1 message
        t0 = time.perf_counter()
        messages, _ = live.evenements_depuis(offset)
        mesures.append(time.perf_counter() - t0)
        assert len(messages) == 1  # on lit bien LE delta, pas tout le bus
    return min(mesures)


def test_tail_o1_delta_independant_de_la_taille_du_bus():
    # Petit bus (~1 message) : delta.
    _pub("amorce", "banc", "capteur", "démarrage")
    t_petit = _mesurer_delta(0)
    _, taille_petite = nexus_bus.lire_depuis(0)

    # Gonflage à ~5000 messages, puis même mesure du delta (1 message).
    for i in range(5000):
        _pub("lest", "banc", "capteur", f"remplissage {i}")
    t_gros = _mesurer_delta(0)
    _, taille_grosse = nexus_bus.lire_depuis(0)

    print(f"\n[tail O(1)] bus ~{taille_petite} msg → delta lu en "
          f"{t_petit * 1e6:.1f} µs ; bus ~{taille_grosse} msg → delta lu en "
          f"{t_gros * 1e6:.1f} µs (ratio ×{t_gros / t_petit:.2f} pour "
          f"×{taille_grosse / max(taille_petite, 1):.0f} en messages).")
    # O(1) à bruit d'ordonnanceur près : plancher absolu de 3 ms pour ne pas
    # transformer un aléa d'OS en faux rouge — un tail O(n) sur 5000 messages
    # coûterait bien plus que ça.
    assert t_gros < max(t_petit * 10, 0.003), (
        f"le delta croît avec la taille du bus : {t_petit * 1e6:.1f} µs → "
        f"{t_gros * 1e6:.1f} µs")


# --------------------------------------------------------------------------- #
# 4) échappement HTML dans le fil (anti-injection)
# --------------------------------------------------------------------------- #
def test_echappement_html_dans_le_fil_anti_injection():
    injection = "<script>alert('xss')</script>"
    _pub("A", "B", "demande", injection)
    srv, port = _serveur()
    try:
        _, page = _get(port, "/")
    finally:
        srv.shutdown()
        srv.server_close()
    # Anti-injection côté serveur : le <script> du contenu n'apparaît JAMAIS brut…
    assert "<script>alert" not in page
    # … mais bien dans sa forme ÉCHAPPÉE, dans le fil rendu.
    assert "&lt;script&gt;alert" in page


def test_echappement_html_cote_script_live():
    """Le script de poll échappe AUSSI ce qu'il insère dans le DOM (esc()) :
    aucune concaténation brute de contenu de message. Preuve statique sur le
    corps du script embarqué (les lignes/cartes passent toutes par esc())."""
    src = live._SCRIPT_LIVE
    assert "function esc(" in src
    # Le fil et les cartes n'insèrent le texte des messages qu'ÉCHAPPÉ.
    assert "esc(resumer(m.contenu))" in src
    assert "esc(resumer(dernier.contenu))" in src
    assert "esc(m.expediteur)" in src


# --------------------------------------------------------------------------- #
# 5) LECTURE SEULE : empreintes binaires inchangées + verrou structurel (AST)
# --------------------------------------------------------------------------- #
def test_lecture_seule_empreintes_bus_et_memoire_inchangees(tmp_path):
    _pub("A", "B", "demande", "une trace réelle")
    _pub("B", "A", "reponse", "reçu")
    chemin_forces = _ecrire_forces(tmp_path, {"A": 2.0, "B": 1.4})
    _, bus_journal = nexus_bus._chemins()

    def empreinte(p):
        with open(p, "rb") as f:
            return f.read()

    cibles = [bus_journal, str(chemin_forces)]
    avant = {p: empreinte(p) for p in cibles}
    fichiers_avant = {str(p) for p in tmp_path.rglob("*") if p.is_file()}

    # On sollicite TOUT : bibliothèque + tous les endpoints, plusieurs fois.
    live.evenements_depuis(0)
    live._forces()
    live.page_live()
    srv, port = _serveur()
    try:
        for _ in range(3):
            for chemin in ("/", "/index.html", "/events?since=0",
                           "/events?since=999999", "/events?since=pas",
                           "/inconnu"):
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request("GET", chemin)
                conn.getresponse().read()
                conn.close()
    finally:
        srv.shutdown()
        srv.server_close()

    # Aucune source touchée : empreintes binaires identiques.
    for p, contenu in avant.items():
        assert empreinte(p) == contenu, f"source modifiée par le dashboard : {p}"
    # Le dashboard n'a créé AUCUN fichier (il ne fait que lire et servir).
    assert {str(p) for p in tmp_path.rglob("*") if p.is_file()} == fichiers_avant, \
        "le dashboard a créé un fichier — il doit être strictement lecture seule"


def _mode_ouverture(call):
    if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
        return call.args[1].value
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            return kw.value.value
    return "r"


def test_verrou_structurel_zero_ecriture_aucun_mutateur():
    """Verrou STRUCTUREL (prouvé sur l'AST, pas par un if) : le module n'ouvre
    RIEN en écriture (zéro open() en mode w/a/x/+) et n'appelle AUCUN mutateur
    du monde (publier / ecrire_forces / ecrire_html / appliquer / log_event) —
    donc ni le bus, ni la mémoire, ni les forces, ni aucun fichier ne sont
    jamais écrits. C'est un serveur en LECTURE SEULE STRICTE."""
    source = open(os.path.join(_organes(), "nexus_bureau_live.py"),
                  encoding="utf-8").read()
    arbre = ast.parse(source)

    ecritures = []       # (fonction, mode) des open() en écriture
    appels_attr = set()  # noms d'attributs appelés : m.publier(...), etc.

    def visiter(noeud, fonction):
        if isinstance(noeud, ast.FunctionDef):
            fonction = noeud.name
        if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
                and noeud.func.id == "open"):
            mode = _mode_ouverture(noeud)
            if any(c in str(mode) for c in "wax+"):
                ecritures.append((fonction, mode))
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute):
            appels_attr.add(noeud.func.attr)
        for enfant in ast.iter_child_nodes(noeud):
            visiter(enfant, fonction)

    visiter(arbre, fonction=None)

    # (a) AUCUNE ouverture en écriture, où que ce soit.
    assert ecritures == [], f"ouverture(s) en écriture interdites : {ecritures}"

    # (b) le module n'appelle JAMAIS de mutateur du monde.
    mutateurs = {"publier", "ecrire_forces", "ecrire_html", "appliquer",
                 "log_event"}
    assert not (appels_attr & mutateurs), (
        f"appel mutateur interdit : {sorted(appels_attr & mutateurs)}")

    # (c) aucun appel os destructeur.
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Attribute)
                and isinstance(noeud.value, ast.Name)
                and noeud.value.id == "os"):
            assert noeud.attr not in ("system", "remove", "rename", "unlink",
                                      "rmdir", "truncate"), (
                f"appel destructeur : os.{noeud.attr}")


# --------------------------------------------------------------------------- #
# 6) robustesse : bus vide/absent → page « aucun agent » sans erreur
# --------------------------------------------------------------------------- #
def test_bus_absent_page_aucun_agent_sans_erreur():
    # Aucun message publié : le journal du bus n'existe même pas.
    _, bus_journal = nexus_bus._chemins()
    assert not os.path.exists(bus_journal)

    srv, port = _serveur()
    try:
        statut, page = _get(port, "/")
        st_ev, j = _get_json(port, "/events?since=0")
    finally:
        srv.shutdown()
        srv.server_close()

    assert statut == 200
    assert "<!DOCTYPE html>" in page            # page valide malgré le vide
    assert "aucun agent" in page.lower()        # message « aucun agent »
    # /events reste propre et vide sur un bus absent.
    assert st_ev == 200
    assert j["messages"] == [] and j["offset"] == 0
