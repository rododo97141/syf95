"""
Tests du CÂBLAGE de l'organe 96 → évaluateur consultatif.

Lancement :  python -m pytest backend/tests -q

Vérifie que `FiltreAdmission.remonter_decision` :
  - appelle bien `evaluateur_ouvert.recommander_par_preferences` quand des
    comparaisons par paires sont fournies, et expose la RECOMMANDATION SANS trancher
    (96 propose, ne décide jamais : decide=False) ;
  - reste rétro-compatible quand aucune comparaison n'est fournie ;
  - remonte fidèlement les signaux de l'évaluateur (cycle, séparation) ;
  - n'altère pas le filtrage d'écarts historique (câblage purement additif).
"""

from filtre_admission import Decision, Ecart, FiltreAdmission


def _filtre():
    return FiltreAdmission(seuil_base=50, capacite_file=10, budget_generation=1)


def _pairs(spec):
    out = []
    for gagnant, perdant, n in spec:
        out += [(gagnant, perdant)] * n
    return out


# --- 96 APPELLE l'évaluateur et RECOMMANDE sans trancher -------------------
def test_96_appelle_evaluateur_et_recommande_sans_trancher():
    f = _filtre()
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


def test_96_transmet_les_options_et_s_identifie():
    f = _filtre()
    sortie = f.remonter_decision(["X", "Y"], _pairs([("X", "Y", 3), ("Y", "X", 1)]))
    assert sortie["options"] == ["X", "Y"]
    assert sortie["organe"] == "96"


# --- Rétro-compatibilité : sans comparaisons, comme avant ------------------
def test_96_sans_comparaisons_inchange():
    f = _filtre()
    sortie = f.remonter_decision(["A", "B", "C"])     # aucune comparaison
    assert sortie["consulte_evaluateur"] is False
    assert sortie["recommandation"] is None
    assert sortie["decide"] is False
    assert sortie["options"] == ["A", "B", "C"]


def test_96_comparaisons_vides_traitees_comme_absentes():
    f = _filtre()
    sortie = f.remonter_decision(["A", "B"], [])      # liste vide → comme avant
    assert sortie["consulte_evaluateur"] is False
    assert sortie["recommandation"] is None


# --- 96 remonte fidèlement les SIGNAUX de l'évaluateur --------------------
def test_96_remonte_le_signal_de_cycle():
    f = _filtre()
    comp = _pairs([("A", "B", 2), ("B", "A", 1),
                   ("B", "C", 2), ("C", "B", 1),
                   ("C", "A", 2), ("A", "C", 1)])
    reco = f.remonter_decision(["A", "B", "C"], comp)["recommandation"]
    assert len(reco["cycles"]) == 1               # le cycle est bien remonté
    assert set(reco["cycles"][0]["membres"]) == {"A", "B", "C"}


def test_96_remonte_le_signal_de_separation():
    f = _filtre()
    comp = _pairs([("A", "B", 3), ("B", "C", 3), ("A", "C", 3)])  # ordre total propre
    reco = f.remonter_decision(["A", "B", "C"], comp)["recommandation"]
    assert reco["divergence"]["separation"] is True
    assert reco["p"] is None                      # MLE diverge → on ne chiffre pas


# --- Additif : le filtrage d'écarts historique est INCHANGÉ ----------------
def test_filtrage_ecarts_toujours_operationnel():
    """Câblage purement additif : l'API historique de 96 fonctionne encore."""
    f = _filtre()
    ecart = Ecart("e1", criticite=9, frequence_usage=9, persistance=9,
                  impact_utilisateur=9, cout=1.0)
    res = f.evaluer(ecart, taille_file=0)
    assert res.decision is Decision.ADMIS
    assert res.alerte_95 is True
