"""Tests du banc de qualité recall (`bench/recall_bench.py`).

Le banc est un OUTIL de mesure, LECTURE SEULE. Ces tests ancrent trois
propriétés et gardent trois MUTATIONS en rouge :

  (a) test_bench_fixture_lexical_baseline
        Sur la FIXTURE, en LEXICAL (embedder=None), r@1/r@3 par famille sont
        ÉGAUX à des valeurs attendues STABLES.
        → ANCRE de non-régression du harnais ET du lexical.
        MUTATION (iii) : modifier la fixture (corpus/requêtes) fait bouger un
        chiffre → ROUGE.

  (b) test_bench_embedder_none_dit_indisponible
        Sans embedder, le rapport marque « sémantique indisponible » et ne
        fabrique AUCUN score sémantique (le lexical n'est jamais rebaptisé).
        MUTATION (ii) : rapporter l'absence d'embedder comme du « sémantique »
        → ROUGE.

  (c) test_bench_calcul_rang_correct
        Sur un cas monté, la position (1-indexée) et le r@k (<= k) sont exacts.
        MUTATION (i) : compter en 0-indexé, ou r@k avec « < k » au lieu de
        « <= k » → ROUGE.
"""
import os
import sys
import importlib.util

import pytest


# --------------------------------------------------------------------------- #
# Chargement du banc — backend/ est déjà sur le sys.path (cf. conftest), donc
# `bench` est importable comme package.
# --------------------------------------------------------------------------- #
def _charger_bench():
    ici = os.path.dirname(os.path.abspath(__file__))          # backend/tests
    backend = os.path.dirname(ici)                            # backend/
    if backend not in sys.path:
        sys.path.insert(0, backend)
    chemin = os.path.join(backend, "bench", "recall_bench.py")
    spec = importlib.util.spec_from_file_location("recall_bench_sous_test", chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def rb():
    return _charger_bench()


# --------------------------------------------------------------------------- #
# Valeurs ATTENDUES de l'ancre (lues d'une exécution réelle du banc sur la
# fixture figée). Trois reformulations sont volontairement pauvres en tokens
# exacts (le cas où le sémantique aiderait) : le lexical n'en récupère que la
# moitié. Le contrôle (tokens rares exacts) est parfait.
# --------------------------------------------------------------------------- #
BASELINE_ATTENDUE = {
    "reformulation": {"r@1": 0.5, "r@3": 0.5, "n": 6},
    "controle": {"r@1": 1.0, "r@3": 1.0, "n": 6},
}


# =========================================================================== #
# (a) ANCRE : baseline lexical de la fixture
# =========================================================================== #
def test_bench_fixture_lexical_baseline(rb):
    """MUTATION (iii) : toucher au corpus ou aux requêtes déplace un chiffre.
    En lexical pur (embedder=None), r@1/r@3 par famille == valeurs figées."""
    with rb._corpus_temporaire(rb.CORPUS_FIXTURE) as root:
        mesure = rb.mesurer(None, root)

    assert set(mesure.keys()) == set(BASELINE_ATTENDUE.keys())
    for famille, attendu in BASELINE_ATTENDUE.items():
        obtenu = mesure[famille]
        assert obtenu["n"] == attendu["n"], famille
        assert obtenu["r@1"] == pytest.approx(attendu["r@1"]), famille
        assert obtenu["r@3"] == pytest.approx(attendu["r@3"]), famille

    # La fixture doit rester non dégénérée : une famille sous le plafond
    # (sinon l'ancre ne détecterait plus une régression du lexical).
    assert mesure["reformulation"]["r@1"] < 1.0
    # r@3 >= r@1 toujours (le top-3 contient le top-1).
    for famille in mesure:
        assert mesure[famille]["r@3"] >= mesure[famille]["r@1"], famille


# =========================================================================== #
# (b) HONNÊTETÉ : embedder None => sémantique indisponible, jamais fabriqué
# =========================================================================== #
class _FauxEmbedder:
    """Embedder DÉTERMINISTE minimal (hash de surface) : prouve que le chemin
    sémantique produit un vrai rapport quand un embedder est présent. Ne teste
    PAS la qualité sémantique — seulement que le rapport n'est plus « indispo »."""
    version = "faux-embedder-test-v1"

    def embed(self, text):
        h = 0
        for c in (text or ""):
            h = (h * 131 + ord(c)) & 0xFFFFFFFF
        return [float((h >> (8 * i)) & 0xFF) for i in range(4)]


def test_bench_embedder_none_dit_indisponible(rb):
    """MUTATION (ii) : sans embedder, marquer du « sémantique » (ou fabriquer un
    score) → ROUGE. Le rapport doit dire l'indisponibilité et ne porter AUCUN
    chiffre sémantique."""
    with rb._corpus_temporaire(rb.CORPUS_FIXTURE) as root:
        rapport = rb.construire_rapport(root, embedder=None)

    # Structure : pas de sémantique, honnêtement signalé.
    assert rapport["semantique"] is None
    assert rapport["semantique_disponible"] is False
    assert rapport["embedder_version"] is None

    texte = rb.formater_rapport(rapport)
    assert "indisponible" in texte
    assert "indispo" in texte
    # Aucun score sémantique fabriqué : seuls les DEUX chiffres lexicaux
    # (un par famille) apparaissent, jamais quatre.
    assert texte.count("r@1=") == len(rapport["familles"])


def test_bench_embedder_present_produit_semantique(rb):
    """Contre-épreuve d'honnêteté : AVEC un embedder, le rapport porte bien un
    volet sémantique (mesuré, non fabriqué) et n'affiche plus « indisponible ».
    Garantit que la mention d'indisponibilité est LIÉE à l'absence d'embedder."""
    with rb._corpus_temporaire(rb.CORPUS_FIXTURE) as root:
        rapport = rb.construire_rapport(root, embedder=_FauxEmbedder())

    assert rapport["semantique_disponible"] is True
    assert rapport["semantique"] is not None
    assert rapport["embedder_version"] == "faux-embedder-test-v1"
    for famille in rapport["familles"]:
        assert set(rapport["semantique"][famille]) >= {"r@1", "r@3", "n"}

    texte = rb.formater_rapport(rapport)
    assert "indisponible" not in texte
    assert "faux-embedder-test-v1" in texte
    # Quatre chiffres cette fois : lexical ET sémantique, une famille chacun.
    assert texte.count("r@1=") == 2 * len(rapport["familles"])


# =========================================================================== #
# (c) RANG : position 1-indexée et r@k inclusif (<= k), sur un cas monté
# =========================================================================== #
def _resultats(*noms):
    """Monte une liste de résultats recall minimale (clé « file » = <nom>.md)."""
    return [{"file": nom + ".md"} for nom in noms]


def test_bench_calcul_rang_correct(rb):
    """MUTATION (i) : 0-indexé, ou r@k avec « < k » au lieu de « <= k » → ROUGE."""
    # --- Position 1-INDEXÉE (premier = 1, jamais 0). ----------------------- #
    r = _resultats("a", "b", "cible", "d")
    assert rb._position_cible(r, "cible") == 3          # 0-indexé donnerait 2
    assert rb._position_cible(_resultats("cible"), "cible") == 1   # jamais 0
    assert rb._position_cible(r, "absente") is None

    # --- r@k INCLUSIF : une cible EXACTEMENT en position k COMPTE. ---------- #
    assert rb._r_at_k([3], 3) == 1.0                    # « < 3 » donnerait 0.0
    assert rb._r_at_k([3], 1) == 0.0                    # hors du top-1
    assert rb._r_at_k([1], 1) == 1.0
    assert rb._r_at_k([4], 3) == 0.0                    # au-delà du top-3

    # --- Agrégation avec un miss (None) : compté au dénominateur, pas au num. #
    assert rb._r_at_k([1, None, 3], 3) == pytest.approx(2.0 / 3.0)
    assert rb._r_at_k([1, None, 3], 1) == pytest.approx(1.0 / 3.0)
    assert rb._r_at_k([], 3) == 0.0

    # --- Cohérence bout-en-bout de mesurer() sur un cas monté : la cible en
    #     position 3 est bien dans r@3 mais hors r@1. ----------------------- #
    positions = [rb._position_cible(r, "cible")]
    assert rb._r_at_k(positions, 3) == 1.0
    assert rb._r_at_k(positions, 1) == 0.0
