"""
Tests unitaires du moteur interchangeable (Voie 5).

Lancement :  python -m pytest backend/tests -q

Couvre : le déterminisme du MoteurMock, l'abstraction, l'extraction de réponse
de l'AdaptateurAPI, et surtout l'erreur CLAIRE quand la clé d'API est absente
(aucun appel réseau n'est effectué dans ces tests).
"""

import pytest

from moteur import AdaptateurAPI, ErreurMoteur, Moteur, MoteurMock


# --- MoteurMock : déterministe et hors-ligne ------------------------------
def test_mock_est_deterministe():
    """Même prompt → même sortie (indispensable pour des tests reproductibles)."""
    m = MoteurMock()
    assert m.generer("Bonjour NEXUS") == m.generer("Bonjour NEXUS")


def test_mock_prefixe_et_resume():
    """La sortie porte le préfixe et résume le prompt (sans aléa)."""
    m = MoteurMock(prefixe="[mock]")
    sortie = m.generer("  planifie   la   boucle  ")
    assert sortie.startswith("[mock]")
    assert "planifie la boucle" in sortie  # espaces normalisés


def test_mock_journalise_les_appels():
    """Le mock garde la trace des prompts reçus → preuve d'injection pour les tests."""
    m = MoteurMock()
    m.generer("p1")
    m.generer("p2")
    assert m.appels == ["p1", "p2"]


# --- Moteur : interface abstraite -----------------------------------------
def test_moteur_abstrait_non_instanciable():
    """On ne peut pas instancier l'interface directement (méthode abstraite)."""
    with pytest.raises(TypeError):
        Moteur()  # type: ignore[abstract]


# --- AdaptateurAPI : clé via variable d'environnement ----------------------
def test_adaptateur_cle_absente_erreur_claire(monkeypatch):
    """Clé manquante → ErreurMoteur explicite, AUCUN appel réseau, rien en dur."""
    monkeypatch.delenv("MOTEUR_API_CLE", raising=False)
    moteur = AdaptateurAPI(base_url="https://exemple.invalide/v1", modele="x")
    with pytest.raises(ErreurMoteur) as exc:
        moteur.generer("salut")
    # Le message nomme la variable d'environnement attendue.
    assert "MOTEUR_API_CLE" in str(exc.value)


def test_adaptateur_lit_la_cle_depuis_l_environnement(monkeypatch):
    """La clé provient bien de la variable d'environnement configurée."""
    monkeypatch.setenv("MA_CLE_A_MOI", "secret-123")
    moteur = AdaptateurAPI(base_url="https://x/v1", modele="x", cle_env="MA_CLE_A_MOI")
    assert moteur._cle() == "secret-123"


def test_adaptateur_extrait_le_format_openai():
    """Extraction du texte d'une réponse au format OpenAI Chat Completions."""
    charge = {"choices": [{"message": {"content": "bonjour"}}]}
    assert AdaptateurAPI._extraire(charge) == "bonjour"


def test_adaptateur_format_invalide_leve():
    """Une réponse mal formée lève une ErreurMoteur (pas un KeyError brut)."""
    with pytest.raises(ErreurMoteur):
        AdaptateurAPI._extraire({"oops": True})


# --- Injection dans l'orchestrateur ---------------------------------------
def test_orchestrateur_utilise_le_moteur_injecte(tmp_path):
    """L'organe 97 passe par le Moteur injecté ; MoteurMock par défaut en test."""
    from orchestrateur import tourner

    mock = MoteurMock()
    etat = tourner(tmp_path / "etat.json", moteur=mock)

    assert mock.appels                                   # 97 a sollicité l'IA
    assert any(t["etat"] == "fait" for t in etat["taches"])  # la boucle a avancé
