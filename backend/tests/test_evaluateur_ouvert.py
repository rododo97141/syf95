"""
Tests de l'évaluateur de tâches ouvertes (`evaluateur_ouvert.py`) — filtre
consultatif de 96.

Lancement :  python -m pytest backend/tests -q

Couvre les 4 cas demandés + garde-fous :
  - séparation signalée (MLE Bradley-Terry diverge → on ne chiffre pas) ;
  - cycle de préférence détecté (rapporté comme SIGNAL) ;
  - divergence Bradley-Terry / Copeland signalée ;
  - cas transitif bruité concordant ;
  - axiome « recommandation, jamais décision » (96 propose, ne décide jamais).
"""

import pytest

from evaluateur_ouvert import (
    bradley_terry,
    copeland,
    detecter_cycles,
    detecter_separation,
    recommander_par_preferences,
)


def pairs(spec):
    """Déplie une liste de (gagnant, perdant, n) en n comparaisons."""
    out = []
    for gagnant, perdant, n in spec:
        out += [(gagnant, perdant)] * n
    return out


# --- (a) Séparation signalée ----------------------------------------------
def test_separation_signalee():
    """Ordre total propre (aucun upset) → MLE BT diverge : on le SIGNALE, p=None."""
    opts = ["A", "B", "C"]
    comp = pairs([("A", "B", 3), ("B", "C", 3), ("A", "C", 3)])
    r = recommander_par_preferences(opts, comp)

    assert r["divergence"]["separation"] is True
    assert r["divergence"]["bradley_terry_diverge"] is True
    assert r["p"] is None  # on ne chiffre pas un MLE qui n'existe pas
    assert r["bradley_terry"]["forces"] is None
    # groupes de domination ordonnés du dominant au dominé
    assert r["divergence"]["groupes_domination"] == [["A"], ["B"], ["C"]]
    # mais une recommandation ordinale (Copeland) reste fournie
    assert r["verdict"]["tete"] == "A"
    assert any("séparation" in a.lower() for a in r["avertissements"])


def test_separation_si_option_sans_comparaison():
    """Une option jamais comparée casse la connexité → séparation honnêtement signalée."""
    sep = detecter_separation(["A", "B", "Z"], pairs([("A", "B", 2), ("B", "A", 1)]))
    assert sep["separation"] is True


# --- (b) Cycle détecté comme SIGNAL ---------------------------------------
def test_cycle_detecte_comme_signal():
    """A>B>C>A en majorité → cycle rapporté (signal), pas lissé en bruit."""
    opts = ["A", "B", "C"]
    comp = pairs([("A", "B", 2), ("B", "A", 1),
                  ("B", "C", 2), ("C", "B", 1),
                  ("C", "A", 2), ("A", "C", 1)])
    r = recommander_par_preferences(opts, comp)

    assert len(r["cycles"]) == 1
    assert set(r["cycles"][0]["membres"]) == {"A", "B", "C"}
    assert r["cycles"][0]["exemple"][0] == r["cycles"][0]["exemple"][-1]  # cycle fermé
    assert r["divergence"]["separation"] is False  # tout le monde se bat (connexe)
    assert r["verdict"]["confiance"] == "faible"
    assert any("cycle" in a.lower() for a in r["avertissements"])


def test_detecter_cycles_directement():
    comp = pairs([("A", "B", 1), ("B", "C", 1), ("C", "A", 1)])
    cycles = detecter_cycles(["A", "B", "C"], comp)
    assert len(cycles) == 1 and set(cycles[0]["membres"]) == {"A", "B", "C"}


# --- (c) Divergence Bradley-Terry / Copeland signalée ---------------------
def test_divergence_bt_copeland_signalee():
    """X = la plus large (Copeland) ; Y a écrasé X en face-à-face (Bradley-Terry).

    X bat P, Q, R (largeur) → Copeland favorise X. Mais Y bat X 6-1 (force) →
    Bradley-Terry favorise Y. Les deux méthodes divergent en tête : on le signale.
    """
    opts = ["X", "Y", "P", "Q", "R"]
    comp = pairs([
        ("Y", "X", 6), ("X", "Y", 1),        # Y écrase X (mais X gagne 1 → connexité)
        ("X", "P", 2), ("P", "X", 1),
        ("X", "Q", 2), ("Q", "X", 1),
        ("X", "R", 2), ("R", "X", 1),
    ])
    r = recommander_par_preferences(opts, comp)

    assert r["divergence"]["separation"] is False  # BT converge bien
    assert r["cycles"] == []                        # pas un cycle : vraie divergence
    assert r["divergence"]["bt_vs_copeland"] is True
    assert r["divergence"]["tete_copeland"] == "X"
    assert r["divergence"]["tete_bt"] == "Y"
    assert r["verdict"]["confiance"] == "faible"
    assert any("divergence" in a.lower() for a in r["avertissements"])


# --- (d) Cas transitif bruité concordant ----------------------------------
def test_transitif_bruite_concordant():
    """A>B>C avec upsets : BT et Copeland concordent, pas de cycle, confiance forte."""
    opts = ["A", "B", "C"]
    comp = pairs([("A", "B", 8), ("B", "A", 2),
                  ("B", "C", 8), ("C", "B", 2),
                  ("A", "C", 9), ("C", "A", 1)])
    r = recommander_par_preferences(opts, comp)

    assert r["divergence"]["separation"] is False
    assert r["cycles"] == []
    assert r["divergence"]["bt_vs_copeland"] is False
    assert r["verdict"]["tete"] == "A"
    assert r["verdict"]["confiance"] == "forte"
    # ordre des forces BT cohérent : A > B > C
    f = r["bradley_terry"]["forces"]
    assert f["A"] > f["B"] > f["C"]


# --- Axiome : RECOMMANDATION, jamais une décision -------------------------
def test_recommandation_jamais_decision():
    """96 propose, ne décide jamais : decide=False, nature='recommandation'."""
    r = recommander_par_preferences(["A", "B"], pairs([("A", "B", 3), ("B", "A", 2)]))
    assert r["decide"] is False
    assert r["nature"] == "recommandation"
    assert "96" in r["appelant"]


# --- Bradley-Terry : probabilités cohérentes ------------------------------
def test_bradley_terry_probabilites_coherentes():
    """P(A>B) + P(B>A) = 1 ; le plus fort a P > 0.5."""
    bt = bradley_terry(["A", "B"], pairs([("A", "B", 7), ("B", "A", 3)]))
    assert bt["convergence"] is True
    p = bt["p"]
    assert abs(p["A"]["B"] + p["B"]["A"] - 1.0) < 1e-9
    assert p["A"]["B"] > 0.5  # A a gagné plus souvent


def test_copeland_robuste_aux_marges():
    """Copeland ne regarde que la majorité face-à-face, pas la marge."""
    cop = copeland(["A", "B", "C"],
                   pairs([("A", "B", 1), ("B", "C", 1), ("A", "C", 1)]))
    assert cop["classement"][0] == "A"
    assert cop["scores"]["A"] == 2 and cop["scores"]["C"] == -2


# --- Validation des entrées -----------------------------------------------
def test_label_inconnu_leve():
    with pytest.raises(ValueError):
        recommander_par_preferences(["A", "B"], [("A", "Z")])


def test_auto_comparaison_leve():
    with pytest.raises(ValueError):
        recommander_par_preferences(["A", "B"], [("A", "A")])


def test_options_vides_levent():
    with pytest.raises(ValueError):
        recommander_par_preferences([], [])


def test_options_dupliquees_levent():
    with pytest.raises(ValueError):
        recommander_par_preferences(["A", "A"], [])


def test_comparaison_format_dict():
    """Les comparaisons acceptent le format dict {gagnant, perdant}."""
    r = recommander_par_preferences(
        ["A", "B"],
        [{"gagnant": "A", "perdant": "B"}, {"gagnant": "A", "perdant": "B"},
         {"gagnant": "B", "perdant": "A"}],
    )
    assert r["verdict"]["tete"] == "A"
