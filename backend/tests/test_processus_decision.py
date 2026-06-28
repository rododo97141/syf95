"""
Tests du processus de décision mesuré (`processus_decision.py`).

Lancement :  python -m pytest backend/tests -q

Couvre les cas nominaux ET les garde-fous :
  - REFUS de trancher sur du non-réalisé / non-mesuré ;
  - la meilleure VALEUR gagne (jamais l'avis) ;
  - activer le gagnant / archiver les autres (réversible, rien supprimé) ;
  - override explicite du Créateur (couche méta).
"""

import pytest

from processus_decision import MSG_INCOMPLET, Decision, Option, decider


# --- Garde-fou : on ne tranche pas sur du non-mesuré ----------------------
def test_refuse_si_rien_de_realise_ni_mesure():
    """Aucune option réalisée+mesurée → 'processus incomplet', pas de gagnant."""
    res = decider([
        {"label": "A", "valeur": None, "realise": False},
        {"label": "B", "valeur": None, "realise": False},
    ])
    assert res.statut == "incomplet"
    assert res.gagnant is None
    assert res.message == MSG_INCOMPLET
    assert res.actions == []


def test_realise_mais_non_mesure_reste_incomplet():
    """Réalisé mais valeur None = non mesuré → ne suffit pas pour trancher."""
    res = decider([{"label": "A", "valeur": None, "realise": True}])
    assert res.statut == "incomplet"
    assert res.message == MSG_INCOMPLET


def test_mesure_mais_non_realise_reste_incomplet():
    """Mesuré mais non réalisé (simple projection) → ne suffit pas non plus."""
    res = decider([{"label": "A", "valeur": 0.9, "realise": False}])
    assert res.statut == "incomplet"
    assert res.non_pretes == ["A"]
    assert res.pretes == []


# --- Cas nominal : la meilleure valeur gagne ------------------------------
def test_meilleure_valeur_gagne_parmi_les_pretes():
    """Entre options prêtes, la plus haute valeur l'emporte ; les autres archivées."""
    res = decider([
        {"label": "A", "valeur": 0.4, "realise": True},
        {"label": "B", "valeur": 0.8, "realise": True},
        {"label": "C", "valeur": 0.6, "realise": True},
    ])
    assert res.statut == "tranché"
    assert res.gagnant == "B"
    assert {"action": "activer", "label": "B"} in res.actions
    # Les deux autres sont archivées (pas supprimées) → réversible.
    archives = {a["label"] for a in res.actions if a["action"] == "archiver"}
    assert archives == {"A", "C"}
    assert res.reversible is True


def test_option_non_prete_est_ignoree_mais_archivee():
    """Une option non prête ne peut pas gagner, mais elle est archivée (réversible)."""
    res = decider([
        {"label": "prete", "valeur": 0.5, "realise": True},
        {"label": "brouillon", "valeur": None, "realise": False},
    ])
    assert res.gagnant == "prete"
    assert {"action": "archiver", "label": "brouillon"} in res.actions


def test_egalite_de_valeur_est_deterministe():
    """En cas d'égalité, le 1er dans l'ordre d'entrée gagne (déterministe)."""
    res = decider([
        {"label": "premier", "valeur": 0.7, "realise": True},
        {"label": "second", "valeur": 0.7, "realise": True},
    ])
    assert res.gagnant == "premier"


# --- Garde-fou : on décide par la VALEUR, jamais par l'avis ----------------
def test_l_avis_n_influence_pas_la_decision():
    """Un champ 'avis' fort sur une option faible ne la fait PAS gagner."""
    res = decider([
        {"label": "faible_mais_adorée", "valeur": 0.2, "realise": True, "avis": 10},
        {"label": "forte", "valeur": 0.9, "realise": True, "avis": 0},
    ])
    assert res.gagnant == "forte"  # la valeur mesurée tranche, pas l'avis


def test_touche_ecosysteme_autorite_systeme():
    """Décision qui touche l'écosystème → autorité = système (valeur mesurée)."""
    res = decider(
        [{"label": "A", "valeur": 0.5, "realise": True}],
        touche_ecosysteme=True,
    )
    assert res.autorite == "système (valeur mesurée)"
    assert res.gagnant == "A"


# --- Override explicite du Créateur (couche méta) -------------------------
def test_override_createur_impose_le_gagnant():
    """Le Créateur peut imposer explicitement un autre gagnant (tracé, réversible)."""
    res = decider(
        [
            {"label": "mesurée_meilleure", "valeur": 0.9, "realise": True},
            {"label": "choix_createur", "valeur": 0.3, "realise": True},
        ],
        override_createur="choix_createur",
    )
    assert res.gagnant == "choix_createur"
    assert res.par_override is True
    assert res.autorite == "créateur (override explicite)"
    assert {"action": "archiver", "label": "mesurée_meilleure"} in res.actions


def test_override_sur_option_non_prete_est_trace():
    """Override possible même sur une option non mesurée, mais explicitement tracé."""
    res = decider(
        [{"label": "pas_mesurée", "valeur": None, "realise": False}],
        override_createur="pas_mesurée",
    )
    assert res.gagnant == "pas_mesurée"
    assert res.par_override is True
    assert "non réalisée" in res.note or "non mesuré" in res.note.lower()


def test_override_label_absent_leve():
    """Un override vers un label inexistant lève une ValueError claire."""
    with pytest.raises(ValueError):
        decider([{"label": "A", "valeur": 0.5, "realise": True}],
                override_createur="fantome")


# --- Validation des entrées ------------------------------------------------
def test_liste_vide_leve():
    with pytest.raises(ValueError):
        decider([])


def test_valeur_hors_bornes_leve():
    with pytest.raises(ValueError):
        decider([{"label": "A", "valeur": 1.5, "realise": True}])


def test_label_manquant_leve():
    with pytest.raises(ValueError):
        decider([{"valeur": 0.5, "realise": True}])


def test_accepte_les_objets_option():
    """`decider` accepte aussi des instances Option (pas seulement des dicts)."""
    res = decider([
        Option(label="A", valeur=0.3, realise=True),
        Option(label="B", valeur=0.6, realise=True),
    ])
    assert res.gagnant == "B"


def test_to_dict_serialisable():
    """Le résultat est exportable en dict (journal / état JSON)."""
    res = decider([{"label": "A", "valeur": 0.5, "realise": True}])
    d = res.to_dict()
    assert d["gagnant"] == "A" and d["statut"] == "tranché"
