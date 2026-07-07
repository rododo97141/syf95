#!/usr/bin/env python3
"""
NEXUS — Friday · brique 1 : routeur d'intention (règles, vocabulaire fermé)
« Comprendre l'ordre exact, refuser tout le reste. »

Routeur PAR RÈGLES : aucun LLM, aucun fuzzy, aucune correction. Le vocabulaire
est FERMÉ, déclaré dans les deux tables ci-dessous (la table EST la règle).
Tout ce qui n'y correspond pas est un REFUS explicite : le bruit ambiant
(conversation autour du micro) ne déclenche AUCUNE action.

Entrée  : une ligne de texte transcrit. Le matériel (micro, transcription,
          TTS) reste côté poste — la frontière de syf95 est texte→texte,
          voir friday_coeur.traiter_ligne.
Sortie  : {"intention": ..., "argument": ...}
          intentions : montre / ou_est / explique / statut
          refus      : {"intention": REFUS, "argument": None}
"""
import unicodedata

INTENTIONS = ("montre", "ou_est", "explique", "statut", "note", "tache")
REFUS = "refus"

# --- VOCABULAIRE FERMÉ --------------------------------------------------
# Commandes À ARGUMENT : la ligne normalisée doit COMMENCER par le préfixe,
# suivi d'un argument non vide (« montre » tout seul = refus).
#
# Brique 2+ (écriture mémoire vocale) : POINT DE BRANCHEMENT. Les préfixes
# d'ÉCRITURE « note » / « tache » sont déclarés ICI, à côté des commandes de
# lecture — le vocabulaire reste fermé (la table EST la règle). Le routeur ne
# fait que RECONNAÎTRE l'intention ; l'écriture réelle (préparation, relecture
# obligatoire, staging) vit dans friday_ecrivain et ne se déclenche jamais
# depuis ce simple routage. « note » / « tache » seuls (sans argument) = refus.
PREFIXES = {
    "montre moi": "montre",
    "montre": "montre",
    "affiche": "montre",
    "ou est": "ou_est",
    "ou se trouve": "ou_est",
    "explique moi": "explique",
    "explique": "explique",
    "prends note": "note",
    "note que": "note",
    "note": "note",
    "nouvelle tache": "tache",
    "ajoute une tache": "tache",
    "rappelle moi de": "tache",
    "tache": "tache",
}
# Commandes SANS argument : la ligne normalisée doit être EXACTEMENT le mot
# (« le statut de la réunion » ne déclenche rien).
EXACTS = {
    "statut": "statut",
    "status": "statut",
    "etat": "statut",
}


def normaliser(texte):
    """Minuscules, accents retirés, ponctuation → espace (on garde . et _
    des noms de fichiers), espaces réduits. Déterministe, aucune correction."""
    texte = unicodedata.normalize("NFD", texte or "")
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn").lower()
    propre = "".join(c if (c.isalnum() or c in "._") else " " for c in texte)
    return " ".join(propre.split())


def router(texte):
    """Une ligne transcrite → {"intention", "argument"}, ou REFUS explicite."""
    ligne = normaliser(texte)
    if not ligne:
        return {"intention": REFUS, "argument": None}
    if ligne in EXACTS:
        return {"intention": EXACTS[ligne], "argument": None}
    for prefixe in sorted(PREFIXES, key=len, reverse=True):
        if ligne.startswith(prefixe + " "):
            argument = ligne[len(prefixe):].strip()
            if argument:
                return {"intention": PREFIXES[prefixe], "argument": argument}
    return {"intention": REFUS, "argument": None}
