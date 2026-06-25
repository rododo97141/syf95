"""
Tests du CÂBLAGE de l'organe 96 → évaluateur consultatif + TRACE persistante.

Lancement :  python -m pytest backend/tests -q

Vérifie que `FiltreAdmission.remonter_decision` :
  - appelle bien `evaluateur_ouvert.recommander_par_preferences` quand des
    comparaisons par paires sont fournies, et expose la RECOMMANDATION SANS trancher
    (96 propose, ne décide jamais : decide=False, et n'obéit pas automatiquement) ;
  - reste rétro-compatible quand aucune comparaison n'est fournie ;
  - remonte fidèlement les signaux de l'évaluateur (cycle, séparation) ;
  - ÉCRIT une trace persistante (JSONL) à chaque appel — la future « ligne du
    compteur » (décision, options, classement rendu, champ `suivi`) ;
  - n'altère pas le filtrage d'écarts historique (câblage purement additif).

Le journal est dirigé vers un `tmp_path` à chaque test → aucune pollution.
"""

import json

from filtre_admission import Decision, Ecart, FiltreAdmission


def _filtre(tmp_path):
    """FiltreAdmission dont le journal JSONL est isolé dans le tmp du test."""
    return FiltreAdmission(
        seuil_base=50, capacite_file=10, budget_generation=1,
        chemin_journal=tmp_path / "journal_decisions.jsonl",
    )


def _pairs(spec):
    out = []
    for gagnant, perdant, n in spec:
        out += [(gagnant, perdant)] * n
    return out


def _lire_journal(chemin):
    return [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()]


# --- 96 APPELLE l'évaluateur et RECOMMANDE sans trancher -------------------
def test_96_appelle_evaluateur_et_recommande_sans_trancher(tmp_path):
    f = _filtre(tmp_path)
    options = ["A", "B", "C"]
    comparaisons = _pairs([("A", "B", 8), ("B", "A", 2),
                           ("B", "C", 8), ("C", "B", 2),
                           ("A", "C", 9), ("C", "A", 1)])
    sortie = f.remonter_decision(options, comparaisons, identifiant="d1")

    assert sortie["consulte_evaluateur"] is True
    assert sortie["decide"] is False              # 96 ne décide JAMAIS
    reco = sortie["recommandation"]
    assert reco is not None
    assert reco["decide"] is False                # la recommandation non plus
    assert reco["nature"] == "recommandation"
    assert reco["verdict"]["tete"] == "A"         # exposée telle quelle (A>B>C)
    assert "gagnant" not in sortie                # 96 n'a rien tranché


def test_96_transmet_les_options_et_s_identifie(tmp_path):
    f = _filtre(tmp_path)
    sortie = f.remonter_decision(["X", "Y"], _pairs([("X", "Y", 3), ("Y", "X", 1)]))
    assert sortie["options"] == ["X", "Y"]
    assert sortie["organe"] == "96"


# --- Rétro-compatibilité : sans comparaisons, comme avant ------------------
def test_96_sans_comparaisons_inchange(tmp_path):
    f = _filtre(tmp_path)
    sortie = f.remonter_decision(["A", "B", "C"])     # aucune comparaison
    assert sortie["consulte_evaluateur"] is False
    assert sortie["recommandation"] is None
    assert sortie["decide"] is False
    assert sortie["options"] == ["A", "B", "C"]


def test_96_comparaisons_vides_traitees_comme_absentes(tmp_path):
    f = _filtre(tmp_path)
    sortie = f.remonter_decision(["A", "B"], [])      # liste vide → comme avant
    assert sortie["consulte_evaluateur"] is False
    assert sortie["recommandation"] is None


# --- 96 remonte fidèlement les SIGNAUX de l'évaluateur --------------------
def test_96_remonte_le_signal_de_cycle(tmp_path):
    f = _filtre(tmp_path)
    comp = _pairs([("A", "B", 2), ("B", "A", 1),
                   ("B", "C", 2), ("C", "B", 1),
                   ("C", "A", 2), ("A", "C", 1)])
    reco = f.remonter_decision(["A", "B", "C"], comp)["recommandation"]
    assert len(reco["cycles"]) == 1               # le cycle est bien remonté
    assert set(reco["cycles"][0]["membres"]) == {"A", "B", "C"}


def test_96_remonte_le_signal_de_separation(tmp_path):
    f = _filtre(tmp_path)
    comp = _pairs([("A", "B", 3), ("B", "C", 3), ("A", "C", 3)])  # ordre total propre
    reco = f.remonter_decision(["A", "B", "C"], comp)["recommandation"]
    assert reco["divergence"]["separation"] is True
    assert reco["p"] is None                      # MLE diverge → on ne chiffre pas


# --- TRACE persistante (JSONL) — la future « ligne du compteur » -----------
def test_trace_persistante_ecrite(tmp_path):
    """À chaque appel, une ligne JSONL est écrite : décision, options, classement, suivi."""
    f = _filtre(tmp_path)
    journal = tmp_path / "journal_decisions.jsonl"
    comp = _pairs([("A", "B", 8), ("B", "A", 2),
                   ("B", "C", 8), ("C", "B", 2),
                   ("A", "C", 9), ("C", "A", 1)])
    sortie = f.remonter_decision(["A", "B", "C"], comp, identifiant="d1", libelle="choix")

    assert journal.exists()
    lignes = _lire_journal(journal)
    assert len(lignes) == 1
    t = lignes[0]
    assert t["identifiant"] == "d1"
    assert t["libelle"] == "choix"
    assert t["options"] == ["A", "B", "C"]
    assert t["classement"] == ["A", "B", "C"]     # classement RENDU par l'évaluateur
    assert t["tete_recommandee"] == "A"
    assert t["decide"] is False
    assert t["suivi"] is None                     # rien suivi (96 est consultatif)
    assert "horodatage" in t
    # la sortie expose aussi la trace et le chemin du journal
    assert sortie["trace"] == t
    assert sortie["journal"] == str(journal)


def test_trace_ecrite_aussi_sans_comparaisons(tmp_path):
    """Même sans comparaisons, 96 trace la décision (classement None)."""
    f = _filtre(tmp_path)
    journal = tmp_path / "journal_decisions.jsonl"
    f.remonter_decision(["A", "B", "C"], identifiant="brut")
    t = _lire_journal(journal)[0]
    assert t["consulte_evaluateur"] is False
    assert t["classement"] is None
    assert t["suivi"] is None


def test_trace_append_a_chaque_appel(tmp_path):
    """Le journal s'enrichit d'une ligne par appel (append JSONL)."""
    f = _filtre(tmp_path)
    journal = tmp_path / "journal_decisions.jsonl"
    f.remonter_decision(["A", "B"], _pairs([("A", "B", 2), ("B", "A", 1)]), identifiant="d1")
    f.remonter_decision(["A", "B"], identifiant="d2")
    lignes = _lire_journal(journal)
    assert len(lignes) == 2
    assert [l["identifiant"] for l in lignes] == ["d1", "d2"]


def test_96_reste_consultatif_ne_suit_pas_automatiquement(tmp_path):
    """Même avec une reco nette, 96 logue mais n'obéit pas : decide=False, suivi=None."""
    f = _filtre(tmp_path)
    comp = _pairs([("A", "B", 9), ("B", "A", 1)])     # reco : tête = A
    sortie = f.remonter_decision(["A", "B"], comp)
    assert sortie["recommandation"]["verdict"]["tete"] == "A"
    assert sortie["decide"] is False
    assert sortie["trace"]["suivi"] is None           # 96 n'a PAS suivi la reco


def test_trace_suivi_renseignable_pour_le_compteur(tmp_path):
    """Le champ `suivi` enregistre ce qui a été RÉELLEMENT suivi (futur compteur)."""
    f = _filtre(tmp_path)
    journal = tmp_path / "journal_decisions.jsonl"
    comp = _pairs([("A", "B", 9), ("B", "A", 1),
                   ("B", "C", 9), ("C", "B", 1),
                   ("A", "C", 9), ("C", "A", 1)])
    # Le système a finalement suivi « B » alors que la reco disait « A » : mesurable.
    f.remonter_decision(["A", "B", "C"], comp, identifiant="d1", suivi="B")
    t = _lire_journal(journal)[0]
    assert t["tete_recommandee"] == "A"
    assert t["suivi"] == "B"                           # divergence reco/suivi traçable


def test_journal_param_prioritaire_sur_le_champ(tmp_path):
    """Le paramètre `journal=` l'emporte sur `chemin_journal` (override ponctuel)."""
    f = _filtre(tmp_path)
    autre = tmp_path / "autre.jsonl"
    f.remonter_decision(["A", "B"], journal=autre)
    assert autre.exists()
    assert not (tmp_path / "journal_decisions.jsonl").exists()


# --- Additif : le filtrage d'écarts historique est INCHANGÉ ----------------
def test_filtrage_ecarts_toujours_operationnel(tmp_path):
    """Câblage purement additif : l'API historique de 96 fonctionne encore."""
    f = _filtre(tmp_path)
    ecart = Ecart("e1", criticite=9, frequence_usage=9, persistance=9,
                  impact_utilisateur=9, cout=1.0)
    res = f.evaluer(ecart, taille_file=0)
    assert res.decision is Decision.ADMIS
    assert res.alerte_95 is True
