"""Ligue NEXUS (nexus_ligue) — bureau visible en LECTURE SEULE.

Quatre exigences vérifiées ici :
  1) tail-since-offset : nouvelles lignes seulement, offset stable quand rien
     ne bouge, fichier absent = liste vide ;
  2) débit réel du journal capteurs MESURÉ et IMPRIMÉ (calibrage du poll 500 ms) ;
  3) latence écriture → lecture < 1 s, mesurée à travers le serveur HTTP réel ;
  4) zéro écriture dans les sources (forces.json, capteurs, leçons) quel que
     soit l'endpoint appelé.

Isolation : CAPTEURS_ROOT vient du conftest (autouse) ; MEMOIRE_ROOT et
LECONS_ROOT sont posés par _setup — nexus_ligue relit les trois à chaque appel.
"""
import os
import sys
import json
import time
import threading
import http.client


def _organes():
    ici = os.path.dirname(os.path.abspath(__file__))       # backend/tests
    racine = os.path.dirname(os.path.dirname(ici))          # racine du dépôt
    return os.path.join(racine, "organes")


if _organes() not in sys.path:
    sys.path.insert(0, _organes())
import nexus_sense  # noqa: E402
import nexus_ligue  # noqa: E402


def _setup(tmp_path, monkeypatch):
    """Isole les TROIS sources dans tmp_path (relues à chaque appel)."""
    monkeypatch.setenv("MEMOIRE_ROOT", str(tmp_path / "memoire_data"))
    monkeypatch.setenv("LECONS_ROOT", str(tmp_path / "memoire_data"))
    # CAPTEURS_ROOT : déjà posé par le conftest autouse (tmp_path/_capteurs).


def _ecrire_forces(tmp_path, forces):
    d = tmp_path / "memoire_data"
    d.mkdir(parents=True, exist_ok=True)
    (d / "forces.json").write_text(
        json.dumps(forces, ensure_ascii=False), encoding="utf-8")
    return d / "forces.json"


def _ecrire_lecon(tmp_path, lecon):
    d = tmp_path / "memoire_data" / "lecons"
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "journal.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(lecon, ensure_ascii=False) + "\n")
    return d / "journal.jsonl"


def _serveur():
    """Serveur réel sur un port libre, servi dans un thread démon."""
    srv = nexus_ligue.creer_serveur(port=0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, srv.server_address[1]


def _get(port, chemin):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", chemin)
        rep = conn.getresponse()
        return rep.status, json.loads(rep.read().decode("utf-8"))
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# 1) tail-since-offset
# --------------------------------------------------------------------------- #
def test_tail_fichier_absent_renvoie_liste_vide(tmp_path):
    lignes, offset = nexus_ligue.tail_depuis(str(tmp_path / "inexistant.jsonl"), 0)
    assert lignes == []
    assert offset == 0


def test_tail_ne_renvoie_que_les_nouvelles_lignes(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    nexus_sense.log_event("premiere tache", statut="succes")
    lignes, off1 = nexus_ligue.evenements_depuis("capteurs", 0)
    assert len(lignes) == 1
    assert json.loads(lignes[0])["tache"] == "premiere tache"

    # Rien de neuf : liste vide ET offset STABLE.
    lignes, off2 = nexus_ligue.evenements_depuis("capteurs", off1)
    assert lignes == []
    assert off2 == off1

    # Deux écritures : seul le delta revient, jamais l'historique.
    nexus_sense.log_event("deuxieme", statut="echec")
    nexus_sense.log_event("troisieme", statut="succes")
    lignes, off3 = nexus_ligue.evenements_depuis("capteurs", off2)
    assert [json.loads(l)["tache"] for l in lignes] == ["deuxieme", "troisieme"]
    assert off3 > off2

    # Relire depuis le nouvel offset : de nouveau rien.
    assert nexus_ligue.evenements_depuis("capteurs", off3) == ([], off3)


def test_tail_ligne_incomplete_attend_le_prochain_poll(tmp_path):
    j = tmp_path / "journal.jsonl"
    j.write_text('{"a": 1}\n{"b": 2', encoding="utf-8")  # écriture en cours
    lignes, off = nexus_ligue.tail_depuis(str(j), 0)
    assert lignes == ['{"a": 1}']
    assert off == len(b'{"a": 1}\n')  # l'offset ne dépasse PAS la ligne partielle
    with open(j, "a", encoding="utf-8") as f:
        f.write("}\n")
    lignes, off = nexus_ligue.tail_depuis(str(j), off)
    assert lignes == ['{"b": 2}']  # servie ENTIÈRE, ni perdue ni coupée


def test_tail_fichier_tronque_repart_de_zero(tmp_path):
    j = tmp_path / "journal.jsonl"
    j.write_text('{"a": 1}\n{"b": 2}\n', encoding="utf-8")
    _, off = nexus_ligue.tail_depuis(str(j), 0)
    j.write_text('{"c": 3}\n', encoding="utf-8")  # rotation/troncature
    lignes, off2 = nexus_ligue.tail_depuis(str(j), off)
    assert lignes == ['{"c": 3}']
    assert off2 == len(b'{"c": 3}\n')


def test_tail_source_lecons_et_source_inconnue(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    lignes, off = nexus_ligue.evenements_depuis("lecons", 0)
    assert (lignes, off) == ([], 0)  # journal absent = liste vide
    _ecrire_lecon(tmp_path, {"ts": "2026-01-01T00:00:00", "type": "methode",
                             "lecon": "tester d'abord"})
    lignes, off = nexus_ligue.evenements_depuis("lecons", off)
    assert len(lignes) == 1 and json.loads(lignes[0])["lecon"] == "tester d'abord"
    try:
        nexus_ligue.evenements_depuis("meteo", 0)
        assert False, "source inconnue : KeyError attendu"
    except KeyError:
        pass


# --------------------------------------------------------------------------- #
# 2) débit réel du journal capteurs (calibrage du poll 500 ms)
# --------------------------------------------------------------------------- #
def test_debit_journal_capteurs_mesure_et_imprime(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    N = 200
    t0 = time.perf_counter()
    for i in range(N):
        nexus_sense.log_event(f"tache {i}", statut="succes",
                              fiche=f"fiche-{i % 7}")
    duree = time.perf_counter() - t0

    debit = N / duree
    lignes, _ = nexus_ligue.evenements_depuis("capteurs", 0)
    assert len(lignes) == N  # le tail voit bien tout ce qui a été écrit

    par_poll = debit * 0.5
    print(f"\n[calibrage] débit d'écriture capteurs : {debit:.0f} evt/s "
          f"({N} événements en {duree * 1000:.1f} ms) "
          f"→ jusqu'à ~{par_poll:.0f} lignes par poll de 500 ms.")
    # Un poll doit rester trivial même à ce débit : relire N lignes < 100 ms.
    t1 = time.perf_counter()
    nexus_ligue.evenements_depuis("capteurs", 0)
    assert time.perf_counter() - t1 < 0.1


# --------------------------------------------------------------------------- #
# 3) latence écriture → lecture < 1 s (à travers le serveur HTTP réel)
# --------------------------------------------------------------------------- #
def test_latence_ecriture_lecture_sous_une_seconde(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    srv, port = _serveur()
    try:
        _, j = _get(port, "/events?source=capteurs&since=0")
        offset = j["offset"]

        t0 = time.perf_counter()
        nexus_sense.log_event("mesure latence", statut="succes")
        vu = None
        while time.perf_counter() - t0 < 2.0:  # borne dure du test
            _, j = _get(port, f"/events?source=capteurs&since={offset}")
            offset = j["offset"]
            if j["lignes"]:
                vu = time.perf_counter() - t0
                break
            time.sleep(0.05)

        assert vu is not None, "l'événement n'est jamais apparu via /events"
        assert vu < 1.0, f"latence écriture→lecture {vu:.3f}s ≥ 1s"
        assert json.loads(j["lignes"][0])["tache"] == "mesure latence"
        print(f"\n[latence] écriture → lecture via HTTP : {vu * 1000:.1f} ms")
    finally:
        srv.shutdown()
        srv.server_close()


# --------------------------------------------------------------------------- #
# Classement : forces = points, flèches promotion/relégation
# --------------------------------------------------------------------------- #
def test_classement_points_et_fleches(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _ecrire_forces(tmp_path, {"veteran": 2.0})  # réglage sans capteur : stable
    # 'etoile' : 6 succès — les 5 derniers événements (fenêtre récente) la font
    # monter. 'boulet' : 1 succès ancien puis 3 échecs récents — descend.
    nexus_sense.log_event("t", statut="succes", fiche="etoile")
    nexus_sense.log_event("t", statut="succes", fiche="boulet")
    for _ in range(5):
        nexus_sense.log_event("t", statut="succes", fiche="etoile")
    for _ in range(3):
        nexus_sense.log_event("t", statut="echec", fiche="boulet")

    joueurs = {j["fiche"]: j for j in nexus_ligue.classement()}
    assert set(joueurs) == {"veteran", "etoile", "boulet"}
    assert joueurs["etoile"]["tendance"] == "promotion"
    assert joueurs["boulet"]["tendance"] == "relegation"
    assert joueurs["veteran"]["tendance"] == "stable"
    assert joueurs["veteran"]["points"] == 2.0  # points = forces.json, pas recalcul
    # Tri par points décroissants, rangs 1..n.
    ordonnes = nexus_ligue.classement()
    assert [j["rang"] for j in ordonnes] == [1, 2, 3]
    assert ordonnes[0]["points"] >= ordonnes[-1]["points"]


def test_endpoints_http_page_classement_et_404(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _ecrire_forces(tmp_path, {"solo": 1.4})
    srv, port = _serveur()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/")
        rep = conn.getresponse()
        page = rep.read().decode("utf-8")
        conn.close()
        assert rep.status == 200
        assert "Ligue NEXUS" in page
        # Aucune dépendance externe : pas de CDN, pas d'URL absolue.
        assert "cdn" not in page.lower()
        assert "https://" not in page and "http://" not in page

        statut, j = _get(port, "/classement")
        assert statut == 200
        assert j["joueurs"][0]["fiche"] == "solo"

        statut, j = _get(port, "/events?source=meteo&since=0")
        assert statut == 400
        statut, _ = _get(port, "/nulle-part")
        assert statut == 404
    finally:
        srv.shutdown()
        srv.server_close()


# --------------------------------------------------------------------------- #
# 4) zéro écriture dans les sources
# --------------------------------------------------------------------------- #
def test_zero_ecriture_dans_les_sources(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    chemin_forces = _ecrire_forces(tmp_path, {"gardien": 3.0})
    nexus_sense.log_event("tache reelle", statut="succes", fiche="gardien")
    chemin_lecons = _ecrire_lecon(tmp_path, {"type": "methode", "lecon": "relire"})
    chemin_capteurs = nexus_ligue._chemin_capteurs()

    def empreinte(p):
        with open(p, "rb") as f:
            return f.read()

    avant = {p: empreinte(p) for p in
             (str(chemin_forces), str(chemin_lecons), chemin_capteurs)}
    racine = tmp_path / "memoire_data"
    fichiers_avant = {str(p) for p in racine.rglob("*") if p.is_file()}

    # On sollicite TOUT : bibliothèque + tous les endpoints HTTP.
    nexus_ligue.classement()
    nexus_ligue.evenements_depuis("capteurs", 0)
    nexus_ligue.evenements_depuis("lecons", 0)
    srv, port = _serveur()
    try:
        for chemin in ("/", "/classement", "/events?source=capteurs&since=0",
                       "/events?source=lecons&since=0", "/events?source=x&since=0",
                       "/inconnu"):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", chemin)
            conn.getresponse().read()
            conn.close()
    finally:
        srv.shutdown()
        srv.server_close()

    for p, contenu in avant.items():
        assert empreinte(p) == contenu, f"source modifiée par le dashboard : {p}"
    assert {str(p) for p in racine.rglob("*") if p.is_file()} == fichiers_avant, \
        "le dashboard a créé un fichier dans les sources"
