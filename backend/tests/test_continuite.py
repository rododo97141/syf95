"""Continuité de la force — organes/nexus_continuite.py.

Le mandat, point par point (isolation TOTALE : MEMOIRE_ROOT, CAPTEURS_ROOT et
les journaux de nexus_lecons sont redirigés vers des dossiers jetables — on ne
touche JAMAIS le vrai memoire_data/ ni le vrai journal des leçons) :

  T1  ouvrir_pour_tache crée une consultation OUVERTE fiche-UNIQUE pour un
      critère-Kily existant, N'ÉMET JAMAIS de capteur de force, et REFUSE un
      critère fantôme (inexistant sous structure/<dom>/criteres-kily/).
  T2  file_a_juger liste les consultations OUVERTES et EXCLUT les appliquées /
      closes-sans-dette (LECTURE SEULE).

Mutations ROUGES couvertes (chaque assertion tue une mutation) :
  (i)   ouvrir_pour_tache émettrait un capteur_force            → T1 (sense vide).
  (iii) file_a_juger inclurait une consultation close           → T2 (exclusion).
  (iv)  ouvrir accepterait un critère fantôme                   → T1 (ValueError).
"""
import os
import sys
import json
import importlib

import pytest


# --------------------------------------------------------------------------- #
# Chargement des modules + racines isolées (miroir de test_capital)
# --------------------------------------------------------------------------- #
def _racine_depot():
    ici = os.path.dirname(os.path.abspath(__file__))          # backend/tests
    return os.path.dirname(os.path.dirname(ici))              # racine du dépôt


def _organes():
    org = os.path.join(_racine_depot(), "organes")
    if org not in sys.path:
        sys.path.insert(0, org)
    return org


class _Cap:
    """Contexte de test : modules chargés + racines isolées."""


@pytest.fixture
def cap(tmp_path, monkeypatch):
    _organes()
    racine_memoire = tmp_path / "memoire_data"
    monkeypatch.setenv("MEMOIRE_ROOT", str(racine_memoire))   # relu à chaque appel

    import nexus_force
    import nexus_sense
    import nexus_lecons
    import nexus_capital
    import nexus_continuite
    nexus_force = importlib.reload(nexus_force)
    # journaux de leçons isolés (capitaliser en écrit un pointeur).
    dl = tmp_path / "lecons"
    monkeypatch.setattr(nexus_lecons, "DIR", str(dl))
    monkeypatch.setattr(nexus_lecons, "JOURNAL", str(dl / "journal.jsonl"))
    monkeypatch.setattr(nexus_lecons, "TRANSFERT", str(dl / "transfert.jsonl"))

    c = _Cap()
    c.nf = nexus_force
    c.sense = nexus_sense
    c.lecons = nexus_lecons
    c.cap = nexus_capital
    c.cont = nexus_continuite
    c.tmp = tmp_path
    c.racine_memoire = racine_memoire
    return c


def _consultations(c):
    chemin = c.cap._chemin_consultations()
    if not os.path.exists(chemin):
        return []
    return [json.loads(l) for l in open(chemin, encoding="utf-8") if l.strip()]


def _fiche(c, question, domaine="nexus"):
    """Capitalise une fiche criteres-kily réelle et renvoie son slug."""
    return c.cap.capitaliser(question, "réponse verbatim de Kily",
                             "contexte de la tâche", domaine)


# =========================================================================== #
# T1 — ouvrir_pour_tache : consultation ouverte fiche-unique, ZÉRO force, refus fantôme
# =========================================================================== #
def test_t1_ouvrir_pour_tache_ouverte_fiche_unique_sans_force(cap):
    slug = _fiche(cap, "Critères pour juger une synthèse ouverte")

    cons_id = cap.cont.ouvrir_pour_tache(slug, "nouvelle synthèse à évaluer")

    # --- consultation OUVERTE, fiche-UNIQUE, bien formée ---
    recs = _consultations(cap)
    ouvertures = [r for r in recs if r.get("type") == "consultation"
                  and r.get("id") == cons_id]
    assert len(ouvertures) == 1
    rec = ouvertures[0]
    assert rec["slugs_retournes"] == [slug]        # fiche-UNIQUE → force-éligible
    assert rec["fiche_retenue"] is None            # OUVERTE : verdict = geste humain
    assert rec["tache"] == "nouvelle synthèse à évaluer"
    assert "ts" in rec and cons_id.startswith("cons-")

    # --- MUTATION (i) : ouvrir n'émet JAMAIS de force ---
    #     ni champ capteur_force sur l'enregistrement…
    assert rec.get("capteur_force") is not True
    assert "jeton" not in rec and "statut" not in rec
    #     …ni AUCUN capteur écrit dans nexus_sense (source unique des capteurs).
    assert cap.sense.lire() == []

    # --- MUTATION (iv) : critère fantôme (inexistant) → REFUS strict ---
    with pytest.raises(ValueError):
        cap.cont.ouvrir_pour_tache("critere-qui-nexiste-pas-du-tout", "tâche")

    # une ouverture refusée n'écrit RIEN de plus (pas de consultation fantôme).
    assert [r for r in _consultations(cap) if r.get("type") == "consultation"] == [rec]


# =========================================================================== #
# T2 — file_a_juger : liste les ouvertes, EXCLUT appliquées et closes-sans-dette
# =========================================================================== #
def test_t2_file_a_juger_exclut_appliquees_et_closes(cap):
    slug_a = _fiche(cap, "Critères A pour un rapport détaillé")
    slug_b = _fiche(cap, "Critères B pour une relecture")
    slug_c = _fiche(cap, "Critères C pour un choix technique")

    id_a = cap.cont.ouvrir_pour_tache(slug_a, "tâche A")
    id_b = cap.cont.ouvrir_pour_tache(slug_b, "tâche B")
    id_c = cap.cont.ouvrir_pour_tache(slug_c, "tâche C")

    # les trois sont ouvertes et non jugées → toutes dans la file.
    file0 = cap.cont.file_a_juger()
    assert {f["id"] for f in file0} == {id_a, id_b, id_c}
    fa = next(f for f in file0 if f["id"] == id_a)
    assert fa["critere"] == slug_a and fa["tache"] == "tâche A" and fa["ts"]

    # --- MUTATION (iii) : une consultation APPLIQUÉE quitte la file ---
    #     jugement HUMAIN complet (jeton + appliquer) — la SEULE voie vers la force.
    jeton = cap.cap.generer_jeton_confirmation(id_a)
    cap.cap.appliquer(id_a, slug_a, "succes", "tâche A", jeton=jeton)

    # --- une consultation CLOSE-SANS-DETTE quitte aussi la file ---
    cap.cap.clore_sans_dette(id_b, "hors critère")

    file1 = cap.cont.file_a_juger()
    ids = {f["id"] for f in file1}
    assert id_a not in ids          # appliquée : EXCLUE
    assert id_b not in ids          # close-sans-dette : EXCLUE
    assert ids == {id_c}            # seule l'ouverte non jugée reste


# =========================================================================== #
# T3 — LECTURE SEULE : file_a_juger n'écrit rien, n'émet aucune force
# =========================================================================== #
def test_t3_file_a_juger_lecture_seule(cap):
    slug = _fiche(cap, "Critères pour un audit")
    cap.cont.ouvrir_pour_tache(slug, "tâche audit")

    avant = _consultations(cap)
    for _ in range(3):
        cap.cont.file_a_juger()
    apres = _consultations(cap)

    assert avant == apres           # aucune écriture au journal
    assert cap.sense.lire() == []   # aucun capteur de force
