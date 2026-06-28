"""
Tests unitaires de la transcription (Voie 6 / Whisper — l'« oreille »).

Lancement :  python -m pytest backend/tests -q

On force l'absence de Whisper (monkeypatch) pour tester le repli de façon
déterministe, quel que soit l'environnement (Whisper installé ou non).
"""

import pytest

import transcription
from transcription import PREFIXE_REPLI, TranscriptionIndisponible, transcrire


@pytest.fixture
def audio_factice(tmp_path):
    """Crée un faux fichier audio (le contenu importe peu : Whisper est neutralisé)."""
    chemin = tmp_path / "extrait.wav"
    chemin.write_bytes(b"RIFF....WAVE")  # octets bidon, jamais lus dans ces tests
    return chemin


def test_fallback_propre_si_whisper_absent(audio_factice, monkeypatch):
    """Whisper absent + strict=False → message de repli clair, ZÉRO plantage."""
    monkeypatch.setattr(transcription, "whisper_disponible", lambda: False)
    texte = transcrire(audio_factice)  # strict=False par défaut
    assert texte.startswith(PREFIXE_REPLI)
    assert "Whisper" in texte


def test_mode_strict_leve_si_whisper_absent(audio_factice, monkeypatch):
    """Whisper absent + strict=True → exception typée et explicite."""
    monkeypatch.setattr(transcription, "whisper_disponible", lambda: False)
    with pytest.raises(TranscriptionIndisponible):
        transcrire(audio_factice, strict=True)


def test_fichier_absent_leve_toujours(monkeypatch):
    """Un fichier introuvable est une vraie erreur, même en mode repli."""
    monkeypatch.setattr(transcription, "whisper_disponible", lambda: False)
    with pytest.raises(FileNotFoundError):
        transcrire("/chemin/inexistant/extrait.wav")


def test_whisper_disponible_renvoie_un_booleen():
    """`whisper_disponible()` répond par un booléen, sans charger Whisper."""
    assert isinstance(transcription.whisper_disponible(), bool)
