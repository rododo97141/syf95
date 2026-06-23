"""
Configuration pytest minimale.

Ajoute le dossier `backend/` au chemin d'import pour que les tests puissent
faire `from filtre_admission import ...` quel que soit le répertoire depuis
lequel pytest est lancé (racine du dépôt ou backend/).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
