"""Tests du gardien 98 (nexus_98) — chantier « câbler 98 sur nexus_vie ».

98 devient le PREMIER consommateur de nexus_vie.est_vivant() : une plaie
(échec / retour négatif / reprise) n'est un dommage ACTIF que si elle est
encore VIVANTE — ni remplacée par une leçon (table de liaison), ni éteinte
par l'horloge d'activité (assez de runs 'ok' écoulés depuis).

Invariants prouvés ici :
  - la récence est déléguée à nexus_vie (plus de bricolage local dans 98) ;
  - runs_propres = nb d'événements 'ok' écoulés DEPUIS la source (activité, pas
    calendrier) ;
  - rétrocompat : ancienne ligne {cle, promu_le} sans lecon_ref = NON remplacée ;
  - VERROU STRUCTUREL : 98 est en LECTURE SEULE — aucun open() en écriture.

Isolés : LECONS_ROOT / CAPTEURS_ROOT → tmp jetable, jamais le vrai memoire_data/.
"""
import os, sys, ast, json


def _organes():
    ici = os.path.dirname(os.path.abspath(__file__))      # backend/tests
    racine = os.path.dirname(os.path.dirname(ici))         # racine du dépôt
    return os.path.join(racine, "organes")


def _setup(tmp_path, monkeypatch):
    org = _organes()
    if org not in sys.path:
        sys.path.insert(0, org)
    monkeypatch.setenv("LECONS_ROOT", str(tmp_path / "lec"))
    monkeypatch.setenv("CAPTEURS_ROOT", str(tmp_path / "cap"))
    import nexus_98
    return nexus_98


def _plaie(ts, tache, statut="echec", feedback=None, qualite=None):
    return {"ts": ts, "tache": tache, "statut": statut,
            "feedback": feedback, "qualite": qualite}


def _ok(ts, tache="run propre"):
    return {"ts": ts, "tache": tache, "statut": "ok", "feedback": None, "qualite": None}


# ---------------------- HORLOGE D'ACTIVITÉ (runs_propres) ----------------------
def test_runs_propres_compte_les_ok_apres_chaque_evenement(tmp_path, monkeypatch):
    g = _setup(tmp_path, monkeypatch)
    cap = [
        _plaie("t0", "plaie A"),   # 3 'ok' après
        _ok("t1"),
        _plaie("t2", "partiel", statut="partiel"),  # 2 'ok' après
        _ok("t3"),
        _ok("t4"),
    ]
    assert g._runs_propres(cap) == [3, 2, 2, 1, 0]


def test_runs_propres_ignore_les_statuts_non_ok(tmp_path, monkeypatch):
    """Seul 'ok' fait avancer l'horloge (pas 'partiel', 'echec', 'succes')."""
    g = _setup(tmp_path, monkeypatch)
    cap = [_plaie("t0", "A"),
           {"ts": "t1", "tache": "s", "statut": "succes"},
           {"ts": "t2", "tache": "e", "statut": "echec"}]
    assert g._runs_propres(cap) == [0, 0, 0]


# ---------------------- PLAIES VIVANTES (via nexus_vie) ----------------------
def test_plaie_fraiche_non_remplacee_est_vivante(tmp_path, monkeypatch):
    g = _setup(tmp_path, monkeypatch)
    cap = [_plaie("t0", "analyse qui gele")]
    echecs, fneg, reprises = g.plaies_vivantes(cap, liaisons=[])
    assert echecs == 1


def test_plaie_remplacee_par_lecon_ne_compte_plus(tmp_path, monkeypatch):
    """Une leçon a remplacé la plaie (lecon_ref dans la table) → résolue, donc
    plus un dommage actif, même toute fraîche (0 run propre écoulé)."""
    g = _setup(tmp_path, monkeypatch)
    import nexus_vie
    ev = _plaie("2026-07-01T09:00:00", "analyse qui gele")
    cle = nexus_vie.cle_source(ev)
    liaisons = [{"cle_source": cle, "lecon_ref": "t#ab12cd34", "promu_le": "t"}]
    echecs, fneg, reprises = g.plaies_vivantes([ev], liaisons)
    assert echecs == 0


def test_plaie_eteinte_par_horloge_activite(tmp_path, monkeypatch):
    """7 runs 'ok' écoulés depuis la plaie (seuil intérimaire par défaut) →
    éteinte par l'activité, plus comptée, sans qu'aucune leçon ne l'ait remplacée."""
    g = _setup(tmp_path, monkeypatch)
    cap = [_plaie("t0", "vieille plaie")] + [_ok(f"t{i}") for i in range(1, 8)]  # 7 'ok'
    echecs, _, _ = g.plaies_vivantes(cap, liaisons=[])
    assert echecs == 0


def test_plaie_encore_chaude_sous_le_seuil_reste_vivante(tmp_path, monkeypatch):
    g = _setup(tmp_path, monkeypatch)
    cap = [_plaie("t0", "plaie recente")] + [_ok(f"t{i}") for i in range(1, 7)]  # 6 'ok' < 7
    echecs, _, _ = g.plaies_vivantes(cap, liaisons=[])
    assert echecs == 1


def test_retour_negatif_et_reprise_aussi_soumis_a_la_vie(tmp_path, monkeypatch):
    g = _setup(tmp_path, monkeypatch)
    cap = [
        _plaie("t0", "tache A", statut="ok", feedback="neg"),   # retour négatif vivant
        _plaie("t1", "tache B", statut="ok", qualite="reprise"),  # reprise vivante
    ]
    echecs, fneg, reprises = g.plaies_vivantes(cap, liaisons=[])
    assert (echecs, fneg, reprises) == (0, 1, 1)


def test_retrocompat_ancienne_ligne_sans_lecon_ref_ne_resout_pas(tmp_path, monkeypatch):
    """Ancien format {cle, promu_le} sans lecon_ref = source NON remplacée :
    la plaie reste vivante (tant que l'horloge ne l'a pas éteinte)."""
    g = _setup(tmp_path, monkeypatch)
    import nexus_vie
    ev = _plaie("2026-06-01T08:00:00", "vieille tache")
    cle = nexus_vie.cle_source(ev)
    liaisons = [{"cle": cle, "promu_le": "2026-06-01T08:00:00"}]  # ancien format
    echecs, _, _ = g.plaies_vivantes([ev], liaisons)
    assert echecs == 1


def test_bout_en_bout_promotion_eteint_la_plaie_pour_98(tmp_path, monkeypatch):
    """Chaîne réelle : capteur d'échec → ingestion → promotion (nexus_pont écrit
    la liaison) → 98 ne compte plus la plaie (est_vivant la voit remplacée).
    Preuve que 98 consomme la MÊME table que celle qu'écrit le pont."""
    g = _setup(tmp_path, monkeypatch)
    import nexus_sense, nexus_pont, nexus_vie
    nexus_sense.log_event(tache="analyse video qui gele", statut="echec")
    cap = nexus_sense.lire()
    assert g.plaies_vivantes(cap, nexus_vie.lire_liaisons())[0] == 1  # vivante avant

    nexus_pont.construire_brouillons()
    chemin_b = os.path.join(nexus_pont._dir_lecons(), "brouillons.jsonl")
    b = [json.loads(l) for l in open(chemin_b, encoding="utf-8") if l.strip()][0]
    b["lecon"] = "verifier l'etat avant de lancer"
    with open(chemin_b, "w", encoding="utf-8") as f:
        f.write(json.dumps(b, ensure_ascii=False) + "\n")
    assert nexus_pont.promouvoir_brouillons()["promus"] == 1

    assert g.plaies_vivantes(cap, nexus_vie.lire_liaisons())[0] == 0  # éteinte après


# ---------------------- VERROU STRUCTUREL : LECTURE SEULE ----------------------
def _modes_open(source):
    """Tous les modes d'ouverture de fichier appelés dans le source (via open())."""
    modes = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            fn = node.func
            nom = getattr(fn, "id", None) or getattr(fn, "attr", None)
            if nom != "open":
                continue
            mode = "r"  # défaut d'open() = lecture
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                mode = node.args[1].value
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = kw.value.value
            modes.append(mode or "")
    return modes


def test_98_n_ouvre_aucun_fichier_en_ecriture(tmp_path, monkeypatch):
    """Verrou structurel : 98 OBSERVE, il n'écrit NI la mémoire, NI la table de
    liaison, NI les forces. Aucun open() de 98 ne porte un mode d'écriture
    (w / a / x / +). Si quelqu'un ajoute une écriture à 98, ce test casse."""
    chemin_98 = os.path.join(_organes(), "nexus_98.py")
    modes = _modes_open(open(chemin_98, encoding="utf-8").read())
    ecritures = [m for m in modes if any(c in m for c in "wax+")]
    assert ecritures == [], f"98 doit rester lecture seule, modes d'écriture trouvés : {ecritures}"


def test_98_lecture_liaisons_ne_cree_aucun_fichier(tmp_path, monkeypatch):
    """La lecture par 98 de la table de liaison (via nexus_vie) ne crée rien
    quand elle est absente : preuve comportementale de la lecture seule."""
    g = _setup(tmp_path, monkeypatch)
    import nexus_vie
    liaisons = nexus_vie.lire_liaisons()
    g.plaies_vivantes([_plaie("t0", "x")], liaisons)
    assert not os.path.exists(tmp_path / "lec" / "lecons" / "brouillons_promus.jsonl")


# ---------------- GARDE ANTI-TAMPON (garde_discrimination_force) ----------------
def _juge(statut_juge):
    """Un event de force capitalisé (application) portant un jugement humain."""
    return {"type": "application", "capteur_force": True, "statut_juge": statut_juge}


def test_garde_jury_tamponneur_sur_echantillon_suffisant_zero_echec(tmp_path, monkeypatch):
    """5 succès / 0 échec (total ≥ SEUIL_MIN) → alerte « jury tamponneur ». Un juge
    qui ne discrimine JAMAIS sur un échantillon suffisant tamponne."""
    g = _setup(tmp_path, monkeypatch)
    events = [_juge("succes")] * 5
    r = g.garde_discrimination_force(events)
    assert r["total"] == 5 and r["succes"] == 5 and r["echec"] == 0
    assert r["taux_echec"] == 0.0
    # MUTATION (ii) : un garde qui n'alerte pas sur 0 échec passerait ici → ROUGE.
    assert r["alerte"] is not None
    assert "tamponneur" in r["alerte"]


def test_garde_un_seul_echec_ne_tamponne_pas(tmp_path, monkeypatch):
    """4 succès / 1 échec (total = SEUIL_MIN, mais echec > 0) → AUCUNE alerte : le
    juge discrimine, même faiblement. C'est le garde-fou contre le faux positif."""
    g = _setup(tmp_path, monkeypatch)
    events = [_juge("succes")] * 4 + [_juge("echec")]
    r = g.garde_discrimination_force(events)
    assert r["total"] == 5 and r["echec"] == 1
    assert r["alerte"] is None


def test_garde_file_trop_longue_est_un_signal_de_volume(tmp_path, monkeypatch):
    """File de 13 consultations ouvertes (> CAP=12) → alerte de VOLUME (retard de
    jugement), indépendante de la discrimination. Sur peu d'events jugés, aucune
    alerte de tampon ne masque le signal de volume."""
    g = _setup(tmp_path, monkeypatch)
    file = [{"id": "cons-%04d" % i} for i in range(13)]
    r = g.garde_discrimination_force([_juge("succes")], file=file)
    assert r["alerte"] is not None
    assert "trop longue" in r["alerte"]


def test_garde_sous_le_seuil_aucune_alerte(tmp_path, monkeypatch):
    """Total < SEUIL_MIN : échantillon trop maigre pour conclure → alerte None,
    même à 0 échec (2 succès ne prouvent pas un tampon). File courte : rien non plus."""
    g = _setup(tmp_path, monkeypatch)
    r = g.garde_discrimination_force([_juge("succes")] * 2, file=[{"id": "cons-0001"}])
    assert r["total"] == 2 and r["alerte"] is None


def test_garde_ne_compte_que_les_events_de_force_juges(tmp_path, monkeypatch):
    """Défensif : sans capteur_force, ou sans statut_juge ∈ {succes, echec}, un
    enregistrement N'ENTRE PAS dans le compte (une ligne parasite ne fait pas
    mentir le garde)."""
    g = _setup(tmp_path, monkeypatch)
    events = [
        _juge("succes"), _juge("succes"), _juge("succes"),
        _juge("succes"), _juge("succes"),
        {"type": "application", "capteur_force": False, "statut_juge": "echec"},  # pas force
        {"type": "consultation", "statut_juge": "echec"},                          # pas force
        {"capteur_force": True, "statut_juge": "ok"},                              # ni succes ni echec
    ]
    r = g.garde_discrimination_force(events)
    assert r["total"] == 5 and r["echec"] == 0     # les 3 parasites ignorés
    assert "tamponneur" in r["alerte"]
