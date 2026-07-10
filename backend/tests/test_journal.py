"""Tests du journal des causes (nexus_journal.scout) — organe d'EXPLICATION de
la force, LECTURE SEULE.

Isolés : capteurs via CAPTEURS_ROOT, mémoire/forces via MEMOIRE_ROOT, tmp jetable.
Ne touchent jamais le vrai memoire_data/.

Chaque garde-fou du mandat a son test « vu ROUGE » : un commentaire décrit la
mutation qui ferait échouer l'assertion (la preuve que le test mord).
"""
import os
import sys
import json

import pytest


def _organes():
    ici = os.path.dirname(os.path.abspath(__file__))       # backend/tests
    racine = os.path.dirname(os.path.dirname(ici))          # racine du dépôt
    return os.path.join(racine, "organes")


def _setup(tmp_path, monkeypatch):
    org = _organes()
    if org not in sys.path:
        sys.path.insert(0, org)
    # Capteurs ET forces isolés dans le tmp jetable.
    monkeypatch.setenv("CAPTEURS_ROOT", str(tmp_path))
    monkeypatch.setenv("MEMOIRE_ROOT", str(tmp_path / "memoire_data"))
    import nexus_sense, nexus_force, nexus_journal
    return nexus_sense, nexus_force, nexus_journal


def _fiche_md(tmp_path, slug, pourquoi=None, corps_extra=""):
    """Écrit une fiche markdown minimale (avec ou sans section Pourquoi) et
    renvoie son chemin. Le slug = radical du fichier (= champ `fiche` capteur)."""
    chemin = tmp_path / (slug + ".md")
    parties = ["# %s — fiche de test\n\n" % slug, "## En bref\ntest\n\n", corps_extra]
    if pourquoi is not None:
        parties.append("\n### Pourquoi\n%s\n" % pourquoi)
    chemin.write_text("".join(parties), encoding="utf-8")
    return chemin


def _capteurs_path():
    return os.path.join(os.environ["CAPTEURS_ROOT"], "capteurs", "journal.jsonl")


# --------------------------------------------------------------------------- #
# Comportement de base : assemblage carnet + pourquoi + score.
# --------------------------------------------------------------------------- #
def test_scout_assemble_carnet_pourquoi_et_score(tmp_path, monkeypatch):
    sense, force, journal = _setup(tmp_path, monkeypatch)
    sense.log_event(tache="mission A", statut="succes", fiche="zorglub", feedback="pos")
    sense.log_event(tache="mission B", statut="echec", fiche="zorglub", note="raté au 2e essai")
    sense.log_event(tache="autre fiche", statut="succes", fiche="autre")   # bruit : autre fiche

    fp = _fiche_md(tmp_path, "zorglub", pourquoi="Elle marche car le contexte est stable.")
    r = journal.scout(str(fp))

    assert r["fiche"] == "zorglub"
    assert r["pourquoi"] == "Elle marche car le contexte est stable."
    # Le carnet ne contient QUE les événements de CETTE fiche (l'autre est exclu).
    assert len(r["carnet"]) == 2
    assert {l["tache"] for l in r["carnet"]} == {"mission A", "mission B"}
    # Score décomposé : 1 succès, 1 échec, net 0.
    assert r["score"]["n_succes"] == 1
    assert r["score"]["n_echec"] == 1
    assert r["score"]["net"] == 0


def test_scout_note_citee_verbatim_jamais_en_verdict(tmp_path, monkeypatch):
    sense, force, journal = _setup(tmp_path, monkeypatch)
    note = "2/8 au départ — pas convaincant"
    sense.log_event(tache="t", statut="partiel", fiche="f", note=note)
    fp = _fiche_md(tmp_path, "f")
    r = journal.scout(str(fp))
    # La note est reprise TELLE QUELLE dans le carnet ET dans le détail des jugements.
    assert r["carnet"][0]["note"] == note
    assert r["jugements"]["detail"][0]["note"] == note
    # Aucune clé « verdict » nulle part : le journal ne juge pas la note.
    assert "verdict" not in r["jugements"]
    assert all("verdict" not in l for l in r["carnet"])


def test_scout_pourquoi_absent_est_none(tmp_path, monkeypatch):
    sense, force, journal = _setup(tmp_path, monkeypatch)
    fp = _fiche_md(tmp_path, "sans_pourquoi", pourquoi=None)
    r = journal.scout(str(fp))
    assert r["pourquoi"] is None


# --------------------------------------------------------------------------- #
# GARDE-FOU 1 — LECTURE SEULE : scout n'écrit RIEN.
# --------------------------------------------------------------------------- #
def test_lecture_seule_aucune_ecriture(tmp_path, monkeypatch):
    sense, force, journal = _setup(tmp_path, monkeypatch)
    sense.log_event(tache="t1", statut="succes", fiche="f")
    sense.log_event(tache="t2", statut="echec", fiche="f")
    fp = _fiche_md(tmp_path, "f", pourquoi="cause X")

    cap = _capteurs_path()
    forces_path = os.path.join(str(tmp_path / "memoire_data"), "forces.json")
    avant_cap = open(cap, "rb").read()
    avant_fiche = fp.read_bytes()
    assert not os.path.exists(forces_path)     # aucune force écrite avant

    journal.scout(str(fp))

    # ROUGE si le journal écrit un event : le journal des capteurs est IDENTIQUE au bit près.
    assert open(cap, "rb").read() == avant_cap
    # ROUGE si scout déclenchait une écriture de force : forces.json reste absent.
    assert not os.path.exists(forces_path)
    # ROUGE si scout réécrivait la fiche : la fiche est intacte.
    assert fp.read_bytes() == avant_fiche


# --------------------------------------------------------------------------- #
# GARDE-FOU 2 — TRAÇABILITÉ : chaque ligne du carnet pointe un event réel (ts).
# --------------------------------------------------------------------------- #
def test_chaque_ligne_carnet_pointe_un_event_reel(tmp_path, monkeypatch):
    sense, force, journal = _setup(tmp_path, monkeypatch)
    sense.log_event(tache="t1", statut="succes", fiche="f")
    sense.log_event(tache="t2", statut="echec", fiche="f")
    fp = _fiche_md(tmp_path, "f")

    ts_reels = {ev["ts"] for ev in sense.lire() if ev.get("fiche") == "f"}
    r = journal.scout(str(fp))

    # ROUGE si une cause était fabriquée sans event source : chaque ligne du carnet
    # se retrouve, à l'identique, dans les événements réels de la fiche (mêmes ts,
    # tâche, statut) — aucune ligne fantôme, aucun ts nul.
    events_reels = [ev for ev in sense.lire() if ev.get("fiche") == "f"]
    empreintes = {(ev["ts"], ev["tache"], ev["statut"]) for ev in events_reels}
    for l in r["carnet"]:
        assert l["ts"] is not None
        assert l["ts"] in ts_reels
        assert (l["ts"], l["tache"], l["statut"]) in empreintes
    # Une ligne par événement réel (multiplicité conservée, même à ts égal).
    assert len(r["carnet"]) == len(events_reels)


# --------------------------------------------------------------------------- #
# GARDE-FOU 3 — EXHAUSTIVITÉ : tout montrer, OU déclarer montre/total.
# --------------------------------------------------------------------------- #
def test_carnet_exhaustif_sans_limite(tmp_path, monkeypatch):
    sense, force, journal = _setup(tmp_path, monkeypatch)
    for i in range(7):
        sense.log_event(tache="t%d" % i, statut="succes", fiche="f")
    fp = _fiche_md(tmp_path, "f")
    r = journal.scout(str(fp))
    # Sans limite : carnet EXHAUSTIF, aucun champ echantillon.
    assert len(r["carnet"]) == 7
    assert "echantillon" not in r


def test_troncature_toujours_declaree(tmp_path, monkeypatch):
    sense, force, journal = _setup(tmp_path, monkeypatch)
    for i in range(10):
        sense.log_event(tache="t%d" % i, statut="succes", fiche="f")
    fp = _fiche_md(tmp_path, "f")
    r = journal.scout(str(fp), limite=4)
    # ROUGE si on tronquait en silence : le carnet est réduit MAIS déclaré.
    assert len(r["carnet"]) == 4
    assert r["echantillon"] == {"montre": 4, "total": 10}


def test_limite_non_atteinte_pas_d_echantillon(tmp_path, monkeypatch):
    sense, force, journal = _setup(tmp_path, monkeypatch)
    for i in range(3):
        sense.log_event(tache="t%d" % i, statut="succes", fiche="f")
    fp = _fiche_md(tmp_path, "f")
    r = journal.scout(str(fp), limite=10)
    # Limite non atteinte : pas de troncature, donc pas de champ echantillon.
    assert len(r["carnet"]) == 3
    assert "echantillon" not in r


# --------------------------------------------------------------------------- #
# GARDE-FOU 4 — JUGEMENT humain vs auto, distingué par le SEUL jeton.
# --------------------------------------------------------------------------- #
def test_jugement_humain_vs_auto_par_jeton(tmp_path, monkeypatch):
    sense, force, journal = _setup(tmp_path, monkeypatch)
    sense.log_event(tache="jugé par Kily", statut="succes", fiche="f", jeton="hitl-123")
    sense.log_event(tache="auto 1", statut="succes", fiche="f")
    sense.log_event(tache="auto 2", statut="echec", fiche="f")
    fp = _fiche_md(tmp_path, "f")
    r = journal.scout(str(fp))

    # ROUGE si un auto était compté comme humain : 1 seul humain (celui au jeton).
    assert r["jugements"]["humain"] == 1
    assert r["jugements"]["auto"] == 2
    par_source = {d["ts"]: d["source"] for d in r["jugements"]["detail"]}
    humains = [d for d in r["jugements"]["detail"] if d["source"] == "humain"]
    assert len(humains) == 1
    assert humains[0]["jeton"] == "hitl-123"
    # Tous les auto ont un jeton None (aucun jeton fabriqué).
    autos = [d for d in r["jugements"]["detail"] if d["source"] == "auto"]
    assert all(d["jeton"] is None for d in autos)


def test_jugement_carnet_expose_le_jeton(tmp_path, monkeypatch):
    sense, force, journal = _setup(tmp_path, monkeypatch)
    sense.log_event(tache="humain", statut="succes", fiche="f", jeton="j-1")
    sense.log_event(tache="auto", statut="succes", fiche="f")
    fp = _fiche_md(tmp_path, "f")
    r = journal.scout(str(fp))
    jetons = {l["tache"]: l["jeton"] for l in r["carnet"]}
    assert jetons["humain"] == "j-1"
    assert jetons["auto"] is None


# --------------------------------------------------------------------------- #
# GARDE-FOU 5 — HONNÊTETÉ : gradation selon N, pas d'éval agrégée sous 5.
# --------------------------------------------------------------------------- #
def test_honnetete_faits_bruts_sous_5(tmp_path, monkeypatch):
    sense, force, journal = _setup(tmp_path, monkeypatch)
    for i in range(4):     # N=4 < 5
        sense.log_event(tache="t%d" % i, statut="succes", fiche="f")
    fp = _fiche_md(tmp_path, "f")
    r = journal.scout(str(fp))
    # ROUGE si on déclarait « etablie » (ou toute éval agrégée) sur N<5.
    assert r["honnetete"]["niveau"] == "faits_bruts"
    assert r["honnetete"]["evaluation_agregee"] is False
    assert r["honnetete"]["n"] == 4


def test_honnetete_tendance_provisoire_entre_5_et_15(tmp_path, monkeypatch):
    sense, force, journal = _setup(tmp_path, monkeypatch)
    for i in range(9):     # 5 <= N=9 < 15
        sense.log_event(tache="t%d" % i, statut="succes", fiche="f")
    fp = _fiche_md(tmp_path, "f")
    r = journal.scout(str(fp))
    assert r["honnetete"]["niveau"] == "tendance_provisoire"
    assert r["honnetete"]["evaluation_agregee"] is True
    assert "9" in r["honnetete"]["message"]


def test_honnetete_etablie_a_15(tmp_path, monkeypatch):
    sense, force, journal = _setup(tmp_path, monkeypatch)
    for i in range(15):    # N=15 => seuil PR#64
        sense.log_event(tache="t%d" % i, statut="succes", fiche="f")
    fp = _fiche_md(tmp_path, "f")
    r = journal.scout(str(fp))
    assert r["honnetete"]["niveau"] == "etablie"
    assert r["honnetete"]["evaluation_agregee"] is True


# --------------------------------------------------------------------------- #
# SCORE — scalaire actuel délégué à calculer_forces, jamais recalculé ici.
# --------------------------------------------------------------------------- #
def test_score_scalaire_vient_de_calculer_forces(tmp_path, monkeypatch):
    sense, force, journal = _setup(tmp_path, monkeypatch)
    # 3 succès, 1 échec => net 2 => calculer_forces : 1.0 + 0.2*2 = 1.4
    for _ in range(3):
        sense.log_event(tache="ok", statut="succes", fiche="f")
    sense.log_event(tache="ko", statut="echec", fiche="f")
    fp = _fiche_md(tmp_path, "f")
    r = journal.scout(str(fp))

    attendu = force.calculer_forces(sense.lire())["f"]
    assert r["score"]["valeur"] == attendu       # scalaire = valeur autoritaire
    assert r["score"]["n_succes"] == 3
    assert r["score"]["n_echec"] == 1
    # Le module n'écrit toujours pas forces.json (calculer_forces est un dry-run).
    assert not os.path.exists(os.path.join(str(tmp_path / "memoire_data"), "forces.json"))


def test_score_valeur_none_si_fiche_jamais_vue(tmp_path, monkeypatch):
    sense, force, journal = _setup(tmp_path, monkeypatch)
    # Événement sur une AUTRE fiche : « f » n'a aucune force calculée.
    sense.log_event(tache="x", statut="succes", fiche="autre")
    fp = _fiche_md(tmp_path, "f")
    r = journal.scout(str(fp))
    assert r["score"]["valeur"] is None
    assert r["carnet"] == []


# --------------------------------------------------------------------------- #
# Robustesse : fiche sans aucun événement / fiche inexistante.
# --------------------------------------------------------------------------- #
def test_scout_fiche_sans_evenement(tmp_path, monkeypatch):
    sense, force, journal = _setup(tmp_path, monkeypatch)
    fp = _fiche_md(tmp_path, "vide", pourquoi="hypothèse initiale")
    r = journal.scout(str(fp))
    assert r["carnet"] == []
    assert r["jugements"] == {"humain": 0, "auto": 0, "detail": []}
    assert r["honnetete"]["niveau"] == "faits_bruts"
    assert r["pourquoi"] == "hypothèse initiale"


def test_scout_fiche_inexistante_pourquoi_none(tmp_path, monkeypatch):
    sense, force, journal = _setup(tmp_path, monkeypatch)
    sense.log_event(tache="t", statut="succes", fiche="fantome")
    r = journal.scout(str(tmp_path / "fantome.md"))   # fichier absent
    assert r["pourquoi"] is None
    assert len(r["carnet"]) == 1                       # les events existent malgré tout


# --------------------------------------------------------------------------- #
# Extraction Pourquoi : verbatim multi-ligne, borné à la section suivante.
# --------------------------------------------------------------------------- #
def test_lire_pourquoi_multiligne_borne_a_section_suivante(tmp_path, monkeypatch):
    sense, force, journal = _setup(tmp_path, monkeypatch)
    chemin = tmp_path / "f.md"
    chemin.write_text(
        "# f\n\n### Pourquoi\nLigne 1 de la cause.\nLigne 2 de la cause.\n\n"
        "### Autre section\nne doit PAS apparaître\n",
        encoding="utf-8",
    )
    p = journal.lire_pourquoi(str(chemin))
    assert p == "Ligne 1 de la cause.\nLigne 2 de la cause."
    assert "Autre section" not in p
    assert "ne doit PAS" not in p


# --------------------------------------------------------------------------- #
# CLI — la commande scout affiche la fiche sans lever.
# --------------------------------------------------------------------------- #
def test_cli_scout_affiche(tmp_path, monkeypatch, capsys):
    sense, force, journal = _setup(tmp_path, monkeypatch)
    sense.log_event(tache="mission", statut="succes", fiche="f", jeton="j-9")
    fp = _fiche_md(tmp_path, "f", pourquoi="parce que ça marche")
    journal.main(["scout", str(fp)])
    out = capsys.readouterr().out
    assert "JOURNAL DES CAUSES" in out
    assert "parce que ça marche" in out
    assert "mission" in out


def test_cli_scout_json(tmp_path, monkeypatch, capsys):
    sense, force, journal = _setup(tmp_path, monkeypatch)
    sense.log_event(tache="mission", statut="succes", fiche="f")
    fp = _fiche_md(tmp_path, "f")
    journal.main(["scout", str(fp), "--json"])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["fiche"] == "f"
    assert len(data["carnet"]) == 1
