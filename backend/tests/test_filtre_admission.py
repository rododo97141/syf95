"""
Tests unitaires du filtre d'admission de l'organe 96.

Lancement :
    python -m pytest backend/tests -q

Les trois cas demandés par le conseil inter-systèmes sont couverts :
  - un écart périphérique est rejeté (archivé sans alerter 95) ;
  - un écart central est retenu (admis, escaladé vers 95) ;
  - une file saturée élève le seuil (admission plus stricte).
Plus quelques cas de robustesse (budget de génération, coût nul).
"""

import pytest

from filtre_admission import Decision, Ecart, FiltreAdmission


def _ecart_peripherique() -> Ecart:
    """Faibles facteurs, coût élevé → priorité basse : (2×1×1×2)/5 = 0.8."""
    return Ecart(
        "peripherique",
        criticite=2, frequence_usage=1, persistance=1,
        impact_utilisateur=2, cout=5,
    )


def _ecart_central() -> Ecart:
    """Forts facteurs, coût faible → priorité élevée : (9×8×7×9)/2 = 2268."""
    return Ecart(
        "central",
        criticite=9, frequence_usage=8, persistance=7,
        impact_utilisateur=9, cout=2,
    )


# --- Cas 1 : écart périphérique rejeté ------------------------------------
def test_ecart_peripherique_rejete():
    """Un écart périphérique passe sous le seuil → archivé sans alerter 95."""
    filtre = FiltreAdmission(seuil_base=50, capacite_file=10, budget_generation=5)
    resultat = filtre.evaluer(_ecart_peripherique(), taille_file=0)

    assert resultat.decision is Decision.ARCHIVE
    assert resultat.alerte_95 is False
    assert resultat.priorite < resultat.seuil_effectif
    assert filtre.admis == []          # rien n'est escaladé
    assert len(filtre.archive) == 1    # mais c'est tracé pour l'audit


# --- Cas 2 : écart central retenu -----------------------------------------
def test_ecart_central_retenu():
    """Un écart central dépasse le seuil → admis et escaladé vers 95."""
    filtre = FiltreAdmission(seuil_base=50, capacite_file=10, budget_generation=5)
    resultat = filtre.evaluer(_ecart_central(), taille_file=0)

    assert resultat.decision is Decision.ADMIS
    assert resultat.alerte_95 is True
    assert resultat.priorite >= resultat.seuil_effectif
    assert len(filtre.admis) == 1


# --- Cas 3 : file saturée élève le seuil ----------------------------------
def test_file_saturee_eleve_le_seuil():
    """La saturation de la file fait monter le seuil (admission plus stricte)."""
    filtre = FiltreAdmission(
        seuil_base=50, capacite_file=10, budget_generation=5, coef_saturation=1.0
    )

    seuil_vide = filtre.seuil_effectif(taille_file=0)    # 50
    seuil_plein = filtre.seuil_effectif(taille_file=10)  # 100
    assert seuil_plein > seuil_vide

    # Un écart « limite » de priorité 75 : (5×3×5×2)/2 = 75.
    limite = Ecart(
        "limite",
        criticite=5, frequence_usage=3, persistance=5,
        impact_utilisateur=2, cout=2,
    )
    assert limite.priorite() == 75

    # Même écart, deux niveaux de charge → décision opposée.
    sur_file_vide = filtre.evaluer(limite, taille_file=0)
    sur_file_pleine = filtre.evaluer(limite, taille_file=10)
    assert sur_file_vide.decision is Decision.ADMIS        # 75 ≥ 50
    assert sur_file_pleine.decision is Decision.ARCHIVE     # 75 < 100


# --- Robustesse : Détection ≠ Création (budget de génération) --------------
def test_budget_generation_limite_les_creations():
    """Au-delà du budget, une création est différée (95 non alerté)."""
    filtre = FiltreAdmission(seuil_base=50, capacite_file=10, budget_generation=1)
    creation = _ecart_central()
    creation.creation = True

    r1 = filtre.evaluer(creation, taille_file=0)  # budget 1 → 0
    assert r1.decision is Decision.ADMIS

    r2 = filtre.evaluer(creation, taille_file=0)  # budget épuisé
    assert r2.decision is Decision.BUDGET_EPUISE
    assert r2.alerte_95 is False


def test_detection_ignore_le_budget():
    """Une simple détection (non-création) n'est pas limitée par le budget."""
    filtre = FiltreAdmission(seuil_base=50, capacite_file=10, budget_generation=0)
    detection = _ecart_central()  # creation=False par défaut
    resultat = filtre.evaluer(detection, taille_file=0)
    assert resultat.decision is Decision.ADMIS  # budget 0 mais détection → OK


# --- Robustesse : coût strictement positif --------------------------------
def test_cout_nul_rejete():
    """Le coût (dénominateur) doit être strictement positif."""
    mauvais = Ecart(
        "ko",
        criticite=1, frequence_usage=1, persistance=1,
        impact_utilisateur=1, cout=0,
    )
    with pytest.raises(ValueError):
        mauvais.priorite()


# --- Lot d'écarts : tri par priorité décroissante -------------------------
def test_filtrer_lot_trie_les_admis():
    """`filtrer` renvoie les admis triés du plus prioritaire au moins prioritaire."""
    filtre = FiltreAdmission(seuil_base=50, capacite_file=10, budget_generation=5)
    admis = filtre.filtrer(
        [_ecart_peripherique(), _ecart_central()], taille_file=0
    )
    assert [r.ecart.identifiant for r in admis] == ["central"]  # périphérique exclu
