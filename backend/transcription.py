"""
Transcription audio — l'« oreille » de l'écosystème NEXUS (Voie 6 / Whisper).

`transcrire(chemin_audio)` renvoie le texte d'un fichier audio en s'appuyant
sur Whisper s'il est installé. Whisper est une dépendance OPTIONNELLE : s'il
n'est pas disponible, la fonction NE PLANTE PAS.

Comportement quand Whisper (lib ou modèle) est absent :
  - `strict=False` (défaut) → renvoie un message de repli clair et reconnaissable
    (préfixe « [transcription indisponible] ») ; zéro plantage ;
  - `strict=True`           → lève `TranscriptionIndisponible` (pour les appelants
    qui préfèrent gérer l'absence par exception).

Aucune dépendance imposée : la bibliothèque standard suffit ; Whisper n'est
importé que s'il est réellement présent (import tardif → reste léger sinon).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

# Préfixe du message de repli — stable, pour que l'appelant puisse le détecter.
PREFIXE_REPLI = "[transcription indisponible]"


class TranscriptionIndisponible(RuntimeError):
    """Levée (en mode strict) quand Whisper, lib ou modèle, n'est pas disponible."""


def whisper_disponible() -> bool:
    """True si la bibliothèque Whisper est importable — sans la charger."""
    return importlib.util.find_spec("whisper") is not None


def transcrire(chemin_audio, *, modele: str = "base", strict: bool = False) -> str:
    """
    Transcrit `chemin_audio` en texte.

    - Si Whisper est installé : effectue la transcription et renvoie le texte.
    - Sinon :
        * strict=False (défaut) → renvoie un message de repli clair (pas de crash) ;
        * strict=True           → lève `TranscriptionIndisponible`.

    Le fichier doit exister (sinon `FileNotFoundError`, quel que soit `strict` :
    un fichier manquant est une vraie erreur, pas un cas de repli).
    """
    chemin = Path(chemin_audio)
    if not chemin.exists():
        raise FileNotFoundError(f"Fichier audio introuvable : {chemin}")

    if not whisper_disponible():
        message = (
            f"{PREFIXE_REPLI} Whisper n'est pas installé. "
            f"Installez-le avec « pip install openai-whisper » (et ffmpeg) "
            f"pour activer l'oreille de NEXUS."
        )
        if strict:
            raise TranscriptionIndisponible(message)
        return message

    # Import tardif : on ne charge Whisper que s'il est présent.
    import whisper  # type: ignore

    modele_charge = whisper.load_model(modele)
    resultat = modele_charge.transcribe(str(chemin))
    return resultat.get("text", "").strip()
