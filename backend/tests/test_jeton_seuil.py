# -*- coding: utf-8 -*-
"""
NEXUS — jeton à seuil multi-parties (M-sur-N) : organes/nexus_jeton_seuil.py.

Couvre : hash déterministe, fail-closed (config absente/invalide), seuil
atteint/non atteint, signature invalide rejetée, doublons non comptés deux
fois, et une propriété Hypothesis (300 cas) qui prouve qu'aucune combinaison
de faux secrets ne peut jamais franchir le seuil.
"""
import os
import sys
import json
import hashlib

import pytest
from hypothesis import given, settings, assume, strategies as st


def _racine_depot():
    ici = os.path.dirname(os.path.abspath(__file__))          # backend/tests
    return os.path.dirname(os.path.dirname(ici))               # racine du dépôt


def _organes():
    org = os.path.join(_racine_depot(), "organes")
    if org not in sys.path:
        sys.path.insert(0, org)
    return org


_organes()
import nexus_jeton_seuil as njs  # noqa: E402


SECRET_KILY = "secret-kily-x9f2c7e1b4a8d0"
SECRET_AUTRE = "secret-nexus-autre-socle-77ab3e"


def _config_reelle():
    return {
        "seuil_m": 2,
        "parties": [
            {"nom": "kily", "hash": njs._hash_secret(SECRET_KILY)},
            {"nom": "nexus-autre-socle", "hash": njs._hash_secret(SECRET_AUTRE)},
        ],
    }


# --------------------------------------------------------------------------- #
# 1) hash déterministe
# --------------------------------------------------------------------------- #
def test_hash_secret_deterministe():
    h1 = njs._hash_secret("un-secret-quelconque")
    h2 = njs._hash_secret("un-secret-quelconque")
    assert h1 == h2
    assert h1 == hashlib.sha256(b"un-secret-quelconque").hexdigest()
    assert njs._hash_secret("autre-secret") != h1


# --------------------------------------------------------------------------- #
# 2) config absente -> fail-closed
# --------------------------------------------------------------------------- #
def test_lire_config_fichier_absent_fail_closed(tmp_path):
    chemin = tmp_path / "capital" / "jeton_seuil_config.json"   # jamais créé
    cfg = njs.lire_config(str(chemin))
    assert cfg["seuil_m"] is None
    assert cfg["parties"] == []


# --------------------------------------------------------------------------- #
# 3) config invalide (JSON cassé ou structure incomplète) -> fail-closed
# --------------------------------------------------------------------------- #
def test_lire_config_invalide_fail_closed(tmp_path):
    chemin_json_casse = tmp_path / "casse.json"
    chemin_json_casse.write_text("{ceci n'est pas du json", encoding="utf-8")
    cfg = njs.lire_config(str(chemin_json_casse))
    assert cfg["seuil_m"] is None
    assert cfg["parties"] == []

    chemin_incomplet = tmp_path / "incomplet.json"
    chemin_incomplet.write_text(json.dumps({"parties": []}), encoding="utf-8")
    cfg2 = njs.lire_config(str(chemin_incomplet))
    assert cfg2["seuil_m"] is None
    assert cfg2["parties"] == []

    chemin_seuil_invalide = tmp_path / "seuil_invalide.json"
    chemin_seuil_invalide.write_text(
        json.dumps({"seuil_m": 0, "parties": [{"nom": "kily", "hash": "abc"}]}),
        encoding="utf-8",
    )
    cfg3 = njs.lire_config(str(chemin_seuil_invalide))
    assert cfg3["seuil_m"] is None
    assert cfg3["parties"] == []


# --------------------------------------------------------------------------- #
# 4) seuil atteint -> valide
# --------------------------------------------------------------------------- #
def test_verifier_jeton_seuil_atteint_valide():
    cfg = _config_reelle()
    valide, parties = njs.verifier_jeton_seuil([SECRET_KILY, SECRET_AUTRE], config=cfg)
    assert valide is True
    assert sorted(parties) == ["kily", "nexus-autre-socle"]


# --------------------------------------------------------------------------- #
# 5) seuil non atteint -> invalide
# --------------------------------------------------------------------------- #
def test_verifier_jeton_seuil_non_atteint_invalide():
    cfg = _config_reelle()
    valide, parties = njs.verifier_jeton_seuil([SECRET_KILY], config=cfg)
    assert valide is False
    assert parties == ["kily"]


# --------------------------------------------------------------------------- #
# 6) signature invalide rejetée
# --------------------------------------------------------------------------- #
def test_verifier_jeton_seuil_signature_invalide_rejetee():
    cfg = _config_reelle()
    valide, parties = njs.verifier_jeton_seuil(
        [SECRET_KILY, "faux-secret-qui-ne-hash-vers-rien-de-connu"], config=cfg
    )
    assert valide is False
    assert parties == ["kily"]


# --------------------------------------------------------------------------- #
# 7) signatures dupliquées non comptées deux fois
# --------------------------------------------------------------------------- #
def test_verifier_jeton_seuil_signatures_dupliquees_non_comptees_deux_fois():
    cfg = _config_reelle()
    valide, parties = njs.verifier_jeton_seuil([SECRET_KILY, SECRET_KILY, SECRET_KILY], config=cfg)
    assert valide is False          # un seul secret réel distinct, seuil_m=2 non atteint
    assert parties == ["kily"]


# --------------------------------------------------------------------------- #
# 8) aucune signature -> fail-closed (pas d'exception, refus net)
# --------------------------------------------------------------------------- #
def test_verifier_jeton_seuil_aucune_signature_fail_closed():
    cfg = _config_reelle()
    valide, parties = njs.verifier_jeton_seuil([], config=cfg)
    assert valide is False
    assert parties == []


# --------------------------------------------------------------------------- #
# 9) propriété Hypothesis (300 cas) : aucune combinaison de FAUX secrets ne
#    peut jamais franchir le seuil (aucun secret n'est jamais reconstruit ou
#    partagé — seule une correspondance individuelle de hash compte).
# --------------------------------------------------------------------------- #
@settings(max_examples=300, deadline=None)
@given(st.lists(st.text(min_size=1, max_size=40), min_size=0, max_size=8))
def test_hypothesis_faux_secrets_ne_franchissent_jamais_le_seuil(faux_secrets):
    assume(SECRET_KILY not in faux_secrets)
    assume(SECRET_AUTRE not in faux_secrets)
    cfg = _config_reelle()
    valide, parties = njs.verifier_jeton_seuil(faux_secrets, config=cfg)
    assert valide is False
    assert parties == []
