"""Assemblage d'un LLM RÉEL (Anthropic) — nexus_llm_reel.

Ce module de PRODUCTION est l'autre moitié du geste : là où l'adaptateur
(nexus_adaptateur_llm) ne lit JAMAIS l'environnement (garde-fou AST), la
fabrique construire_adaptateur_anthropic() lit la clé ET fabrique le vrai
client, avant de l'injecter dans l'adaptateur.

Exigences vérifiées ici (à la lettre du mandat) :

  1) CLÉ ABSENTE → erreur explicite. Sans ANTHROPIC_API_KEY (delenv), la
     fabrique lève RuntimeError — jamais de valeur par défaut, jamais de repli.
  2) CLÉ VIDE → même erreur (garde ".strip()" : "" ou "   " comptent comme vide).
  3) CLÉ POSÉE → vrai client construit AVEC cette clé, puis injecté. La lib
     anthropic est STUBBÉE (setitem sur sys.modules) : anthropic.Anthropic(...)
     enregistre la clé reçue, ZÉRO réseau, ZÉRO vraie clé. On prouve que le
     client de l'adaptateur a bien été construit avec la valeur factice posée.
  4) ZÉRO CLÉ EN DUR. La valeur factice n'existe QUE dans ce test : le source
     de production ne la contient nulle part (lecture statique du fichier).

Discipline réseau : même garde-fou dur que test_adaptateur_llm.py — toute
socket réelle fait échouer le test (aucun appel réseau, même par accident).
"""
import os
import socket
import sys

import pytest


def _racine():
    ici = os.path.dirname(os.path.abspath(__file__))        # backend/tests
    return os.path.dirname(os.path.dirname(ici))            # racine du dépôt


def _organes():
    return os.path.join(_racine(), "organes")


if _organes() not in sys.path:
    sys.path.insert(0, _organes())
import nexus_llm_reel  # noqa: E402
from nexus_adaptateur_llm import AdaptateurAnthropic  # noqa: E402


# Valeur FACTICE de test — jamais une vraie clé. N'existe QUE dans ce fichier
# (prouvé par test_aucune_cle_en_dur_dans_le_source).
CLE_FACTICE = "cle-de-test-bidon-ne-pas-utiliser-en-prod"


# --------------------------------------------------------------------------- #
# Garde-fou réseau (s'applique à TOUS les tests) : AUCUN appel réseau réel.
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _reseau_interdit(monkeypatch):
    def _interdit(*args, **kwargs):
        raise AssertionError("appel réseau interdit dans les tests")
    monkeypatch.setattr(socket, "socket", _interdit)
    monkeypatch.setattr(socket, "create_connection", _interdit)


# --------------------------------------------------------------------------- #
# Stub de la lib anthropic : anthropic.Anthropic(api_key=...) enregistre la
# clé reçue, sans réseau ni vraie clé. Injecté à la place du vrai module.
# --------------------------------------------------------------------------- #
class _FauxClientAnthropic:
    """Mime anthropic.Anthropic : mémorise la clé reçue, zéro réseau."""

    def __init__(self, api_key=None, **kwargs):
        self.api_key = api_key
        self.kwargs = kwargs
        # Un vrai client expose messages.create(...) ; inutile ici (on ne teste
        # que l'ASSEMBLAGE), mais on le pose pour rester fidèle à la forme.
        self.messages = None


class _FauxModuleAnthropic:
    """Mime le module anthropic : expose la classe Anthropic."""

    Anthropic = _FauxClientAnthropic


@pytest.fixture
def _anthropic_stubbe(monkeypatch):
    """Injecte le faux module anthropic à la place du vrai (import paresseux
    dans la fabrique → resolu via sys.modules)."""
    monkeypatch.setitem(sys.modules, "anthropic", _FauxModuleAnthropic)
    return _FauxModuleAnthropic


# --------------------------------------------------------------------------- #
# 1) Clé ABSENTE → RuntimeError explicite (jamais de valeur par défaut)
# --------------------------------------------------------------------------- #
def test_cle_absente_leve_runtime_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(RuntimeError) as info:
        nexus_llm_reel.construire_adaptateur_anthropic()

    # Message explicite qui NOMME la variable, mais ne contient aucune clé.
    assert "ANTHROPIC_API_KEY" in str(info.value)


# --------------------------------------------------------------------------- #
# 2) Clé VIDE / blanche → même RuntimeError (garde ".strip()")
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("valeur", ["", "   ", "\t\n"])
def test_cle_vide_leve_runtime_error(monkeypatch, valeur):
    monkeypatch.setenv("ANTHROPIC_API_KEY", valeur)

    with pytest.raises(RuntimeError):
        nexus_llm_reel.construire_adaptateur_anthropic()


# --------------------------------------------------------------------------- #
# 3) Clé POSÉE → AdaptateurAnthropic dont le client a été construit AVEC la clé
# --------------------------------------------------------------------------- #
def test_cle_posee_construit_adaptateur_avec_client_de_la_cle(
        monkeypatch, _anthropic_stubbe):
    monkeypatch.setenv("ANTHROPIC_API_KEY", CLE_FACTICE)

    adaptateur = nexus_llm_reel.construire_adaptateur_anthropic()

    # On récupère bien un adaptateur prouvé, nommé par défaut "claude".
    assert isinstance(adaptateur, AdaptateurAnthropic)
    assert adaptateur.nom() == "claude"
    # Le client injecté est le faux client, construit AVEC la clé de l'env.
    client = adaptateur._client
    assert isinstance(client, _FauxClientAnthropic)
    assert client.api_key == CLE_FACTICE


# --------------------------------------------------------------------------- #
# 3 bis) nom et **kwargs sont bien transmis à l'adaptateur
# --------------------------------------------------------------------------- #
def test_nom_et_kwargs_transmis_a_l_adaptateur(monkeypatch, _anthropic_stubbe):
    monkeypatch.setenv("ANTHROPIC_API_KEY", CLE_FACTICE)

    adaptateur = nexus_llm_reel.construire_adaptateur_anthropic(
        "assistant", roles=["memoire"], max_tentatives=7)

    assert isinstance(adaptateur, AdaptateurAnthropic)
    assert adaptateur.nom() == "assistant"
    assert adaptateur.roles() == ["memoire"]           # kwargs → adaptateur
    assert adaptateur._max_tentatives == 7             # kwargs → adaptateur
    assert adaptateur._client.api_key == CLE_FACTICE   # client bien construit


# --------------------------------------------------------------------------- #
# 4) ZÉRO CLÉ EN DUR : la valeur factice n'apparaît PAS dans le source de prod
# --------------------------------------------------------------------------- #
def test_aucune_cle_en_dur_dans_le_source():
    chemin = os.path.join(_organes(), "nexus_llm_reel.py")
    with open(chemin, encoding="utf-8") as f:
        source = f.read()

    # Ni la valeur factice de test, ni un littéral d'assignation de clé.
    assert CLE_FACTICE not in source
    assert "api_key=\"" not in source and "api_key='" not in source
