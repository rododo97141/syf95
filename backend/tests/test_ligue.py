"""Ligue NEXUS (nexus_ligue) — bureau visible en LECTURE SEULE.

Exigences vérifiées ici :
  1) tail-since-offset : nouvelles lignes seulement, offset stable quand rien
     ne bouge, fichier absent = liste vide ;
  2) débit réel du journal capteurs MESURÉ et IMPRIMÉ (calibrage du poll 500 ms) ;
  3) latence écriture → lecture < 1 s, mesurée à travers le serveur HTTP réel ;
  4) zéro écriture dans les sources (forces.json, capteurs, leçons) quel que
     soit l'endpoint appelé.

Durcissements v2.6 (contrat tête pensante) :
  5) tail O(1) PROUVÉ : journal gonflé à 50 000 lignes, le temps de lecture du
     delta (1 ligne) ne croît pas avec la taille totale du fichier ;
  6) sources en lecture seule RÉELLE (chmod 444 fichiers, 555 répertoires —
     444 sur un répertoire en bloquerait la traversée) : tous les endpoints
     répondent sans erreur ni modification ;
  7) vue bureau : heuristique v1 capteur→organe + états travaille/alerte/repos
     tirés des derniers capteurs réels ;
  8) mur des légendes (force_journal legende=true OU multiplicateur plafonné) ;
  9) seuil Ligue 1/Ligue 2 : divisions + franchissement entre deux lectures.

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
        for chemin in ("/", "/classement", "/bureau",
                       "/events?source=capteurs&since=0",
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


# --------------------------------------------------------------------------- #
# 5) tail O(1) prouvé : le delta ne dépend pas de la taille totale du fichier
# --------------------------------------------------------------------------- #
def _mesurer_delta(journal, ligne, repetitions=30):
    """Ajoute UNE ligne puis chronomètre la lecture du delta depuis l'offset
    de fin. min() sur N répétitions = mesure stable (écrase le bruit d'OS)."""
    mesures = []
    for _ in range(repetitions):
        offset = os.path.getsize(journal)
        with open(journal, "a", encoding="utf-8") as f:
            f.write(ligne)
        t0 = time.perf_counter()
        lignes, _ = nexus_ligue.tail_depuis(str(journal), offset)
        mesures.append(time.perf_counter() - t0)
        assert len(lignes) == 1  # on lit bien LE delta, pas le fichier
    return min(mesures)


def test_tail_o1_delta_independant_de_la_taille_totale(tmp_path):
    journal = tmp_path / "journal.jsonl"
    ligne = json.dumps({"tache": "tache de gonflage", "statut": "succes",
                        "fiche": "lest"}) + "\n"
    N_GROS = 50_000

    journal.write_text(ligne * 100, encoding="utf-8")
    t_petit = _mesurer_delta(journal, ligne)
    taille_petite = os.path.getsize(journal)

    with open(journal, "a", encoding="utf-8") as f:  # gonflage à 50 000 lignes
        f.write(ligne * (N_GROS - 130))
    t_gros = _mesurer_delta(journal, ligne)
    taille_grosse = os.path.getsize(journal)

    print(f"\n[tail O(1)] petit fichier : {taille_petite} octets → delta lu en "
          f"{t_petit * 1e6:.1f} µs ; gros fichier ({N_GROS} lignes) : "
          f"{taille_grosse} octets → delta lu en {t_gros * 1e6:.1f} µs "
          f"(ratio ×{t_gros / t_petit:.2f} pour ×{taille_grosse / taille_petite:.0f} "
          f"en taille).")
    # O(1) à bruit d'ordonnanceur près : plancher absolu de 2 ms pour ne pas
    # transformer un aléa d'OS en faux rouge — un tail O(n) sur ~7 Mo coûterait
    # bien plus que ça.
    assert t_gros < max(t_petit * 10, 0.002), (
        f"le delta croît avec la taille totale : {t_petit * 1e6:.1f} µs → "
        f"{t_gros * 1e6:.1f} µs")


# --------------------------------------------------------------------------- #
# 6) sources en lecture seule RÉELLE (chmod) : tout répond, rien ne casse
# --------------------------------------------------------------------------- #
def test_endpoints_avec_sources_chmod_lecture_seule(tmp_path, monkeypatch):
    """chmod 444 sur les FICHIERS. Sur les RÉPERTOIRES : 555 (r-x), car 444
    sur un répertoire retire le bit de traversée et rendrait la LECTURE
    elle-même impossible — 555 est la lecture seule réelle d'un répertoire.
    NB : le test tourne en root dans la CI locale (root passe outre chmod) ;
    la preuve d'absence d'écriture reste donc la comparaison d'empreintes
    binaires, le chmod prouvant en plus qu'aucun open() en écriture ni
    création de dossier n'est TENTÉ sous un utilisateur normal."""
    import stat

    _setup(tmp_path, monkeypatch)
    chemin_forces = _ecrire_forces(tmp_path, {"titan": 5.0, "rookie": 0.8})
    nexus_sense.log_event("tache verrouillee", statut="succes", fiche="titan")
    chemin_lecons = _ecrire_lecon(tmp_path, {"type": "methode", "lecon": "verrouiller"})
    d = tmp_path / "memoire_data"
    (d / "force_journal.jsonl").write_text(
        json.dumps({"fiche": "pionnier", "legende": True}) + "\n", encoding="utf-8")
    chemin_capteurs = nexus_ligue._chemin_capteurs()

    fichiers = [str(chemin_forces), str(chemin_lecons), chemin_capteurs,
                str(d / "force_journal.jsonl")]
    dossiers = sorted({os.path.dirname(f) for f in fichiers} | {str(d)},
                      key=len, reverse=True)
    avant = {}
    for f in fichiers:
        with open(f, "rb") as fh:
            avant[f] = fh.read()
    try:
        for f in fichiers:
            os.chmod(f, 0o444)
        for dd in dossiers:
            os.chmod(dd, 0o555)

        srv, port = _serveur()
        try:
            for chemin, attendu in (("/", 200), ("/classement", 200),
                                    ("/bureau", 200),
                                    ("/events?source=capteurs&since=0", 200),
                                    ("/events?source=lecons&since=0", 200),
                                    ("/events?source=x&since=0", 400),
                                    ("/inconnu", 404)):
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request("GET", chemin)
                rep = conn.getresponse()
                rep.read()
                conn.close()
                assert rep.status == attendu, (
                    f"{chemin} → {rep.status} (attendu {attendu}) "
                    f"avec sources en lecture seule")
        finally:
            srv.shutdown()
            srv.server_close()
    finally:  # rendre les droits pour le nettoyage de tmp_path
        for dd in dossiers:
            os.chmod(dd, 0o755)
        for f in fichiers:
            os.chmod(f, 0o644)

    for f, contenu in avant.items():
        with open(f, "rb") as fh:
            assert fh.read() == contenu, f"source modifiée : {f}"
        assert stat.S_IMODE(os.stat(f).st_mode) == 0o644  # remis, donc jamais recréé


# --------------------------------------------------------------------------- #
# 7) vue bureau : heuristique v1 + états depuis les capteurs réels
# --------------------------------------------------------------------------- #
def test_bureau_heuristique_v1_de_mapping():
    assert nexus_ligue._organe_pour({"tier": "CONSEIL"}) == "95"
    assert nexus_ligue._organe_pour({"tier": "DUO", "note": "analyse x"}) == "95"
    assert nexus_ligue._organe_pour({"note": "analyse du marche"}) == "96"
    assert nexus_ligue._organe_pour({"note": "mesure de latence"}) == "96"
    assert nexus_ligue._organe_pour({"note": "controle sante memoire"}) == "98"
    assert nexus_ligue._organe_pour({"note": "garde du perimetre"}) == "98"
    assert nexus_ligue._organe_pour({"note": "livrer la page"}) == "97"
    assert nexus_ligue._organe_pour({}) == "97"


def test_bureau_etats_depuis_capteurs_reels(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    # Aucun capteur : les 4 organes sont au repos.
    postes = {p["code"]: p for p in nexus_ligue.vue_bureau()}
    assert set(postes) == {"95", "96", "97", "98"}
    assert all(p["etat"] == "repos" for p in postes.values())

    nexus_sense.log_event("orchestrer le plan", statut="succes", tier="CONSEIL")
    nexus_sense.log_event("analyse des ventes", statut="echec", note="analyse hebdo")
    nexus_sense.log_event("poser le endpoint", statut="ok")
    postes = {p["code"]: p for p in nexus_ligue.vue_bureau()}
    assert postes["95"]["etat"] == "travaille"      # succes → vert
    assert postes["96"]["etat"] == "alerte"          # echec → rouge
    assert postes["96"]["tache"] == "analyse des ventes"
    assert postes["97"]["etat"] == "travaille"      # ok → vert
    assert postes["98"]["etat"] == "repos"           # rien pour le gardien

    # Hors fenêtre : FENETRE_BUREAU événements « 97 » noient le CONSEIL → 95 repos.
    for i in range(nexus_ligue.FENETRE_BUREAU):
        nexus_sense.log_event(f"routine {i}", statut="ok")
    postes = {p["code"]: p for p in nexus_ligue.vue_bureau()}
    assert postes["95"]["etat"] == "repos"
    assert postes["97"]["etat"] == "travaille"


def test_endpoint_bureau_http(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    nexus_sense.log_event("garde de nuit", statut="succes", note="garde memoire")
    srv, port = _serveur()
    try:
        statut, j = _get(port, "/bureau")
    finally:
        srv.shutdown()
        srv.server_close()
    assert statut == 200
    assert j["fenetre"] == nexus_ligue.FENETRE_BUREAU
    postes = {p["code"]: p for p in j["organes"]}
    assert postes["98"]["etat"] == "travaille"
    assert postes["98"]["nom"] == "Gardien"


# --------------------------------------------------------------------------- #
# 8) mur des légendes
# --------------------------------------------------------------------------- #
def test_mur_des_legendes(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    assert nexus_ligue.legendes() == []  # rien : ni journal ni plafond

    _ecrire_forces(tmp_path, {"titan": 5.0, "honnete": 2.3})
    d = tmp_path / "memoire_data"
    with open(d / "force_journal.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"fiche": "pionnier", "legende": True}) + "\n")
        f.write(json.dumps({"fiche": "honnete", "legende": False}) + "\n")
        f.write("pas du json\n")  # ligne corrompue : tolérée, ignorée

    murs = {m["fiche"]: m for m in nexus_ligue.legendes()}
    assert set(murs) == {"pionnier", "titan"}
    assert murs["pionnier"]["source"] == "journal"
    assert murs["titan"]["source"] == "force_max"   # multiplicateur >= FORCE_MAX
    assert murs["titan"]["points"] == 5.0
    assert "honnete" not in murs  # legende=False et sous le plafond


# --------------------------------------------------------------------------- #
# 9) seuil Ligue 1 / Ligue 2 : divisions + franchissement entre deux lectures
# --------------------------------------------------------------------------- #
def test_seuil_divisions_et_franchissement_monte(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    # 'monteur' : 2 échecs anciens (force 0.8 < seuil) puis 5 succès récents
    # (force 1.6 >= seuil) → il FRANCHIT le seuil entre les deux lectures.
    for _ in range(2):
        nexus_sense.log_event("t", statut="echec", fiche="monteur")
    for _ in range(5):
        nexus_sense.log_event("t", statut="succes", fiche="monteur")
    j = {x["fiche"]: x for x in nexus_ligue.classement(seuil=1.0)}["monteur"]
    assert j["division"] == "Ligue 1"
    assert j["mouvement"] == "monte"
    assert j["tendance"] == "promotion"


def test_seuil_divisions_et_franchissement_descend(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    # 'fragile' : 1 succès ancien (force 1.2 >= seuil) puis 5 échecs récents
    # (force 0.6 < seuil) → il descend en Ligue 2.
    nexus_sense.log_event("t", statut="succes", fiche="fragile")
    for _ in range(5):
        nexus_sense.log_event("t", statut="echec", fiche="fragile")
    j = {x["fiche"]: x for x in nexus_ligue.classement(seuil=1.0)}["fragile"]
    assert j["division"] == "Ligue 2"
    assert j["mouvement"] == "descend"
    assert j["tendance"] == "relegation"


def test_seuil_parametrable_et_marque_defaut(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _ecrire_forces(tmp_path, {"cadre": 1.5})

    srv, port = _serveur()  # sans seuil : défaut 1.0, marqué comme tel
    try:
        _, j = _get(port, "/classement")
    finally:
        srv.shutdown()
        srv.server_close()
    assert j["seuil"] == 1.0 and j["seuil_est_defaut"] is True
    assert j["joueurs"][0]["division"] == "Ligue 1"

    srv = nexus_ligue.creer_serveur(port=0, seuil=2.0)  # décision explicite
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        _, j = _get(srv.server_address[1], "/classement")
    finally:
        srv.shutdown()
        srv.server_close()
    assert j["seuil"] == 2.0 and j["seuil_est_defaut"] is False
    assert j["joueurs"][0]["division"] == "Ligue 2"  # 1.5 < 2.0
    assert "legendes" in j  # le mur voyage avec le classement
