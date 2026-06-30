"""
Configuration pytest minimale.

Ajoute le dossier `backend/` au chemin d'import pour que les tests puissent
faire `from filtre_admission import ...` quel que soit le répertoire depuis
lequel pytest est lancé (racine du dépôt ou backend/).

Isole aussi les CAPTEURS : depuis le branchement de la capture dans la boucle,
chaque test écrit ses capteurs dans un dossier temporaire (CAPTEURS_ROOT), jamais
le vrai `memoire_data/capteurs/`.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture(autouse=True)
def _capteurs_isoles(tmp_path, monkeypatch):
    """Capteurs isolés par test : CAPTEURS_ROOT → dossier temporaire jetable."""
    monkeypatch.setenv("CAPTEURS_ROOT", str(tmp_path / "_capteurs"))
