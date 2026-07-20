#!/usr/bin/env python3
"""
NEXUS — Jeton à seuil multi-parties (M-sur-N)
« Aucune partie seule ne décide ; aucun secret ne circule. »

Vérification d'un jeton de confirmation à SEUIL entre plusieurs parties
(ex. Kily + un autre socle NEXUS) : la config déclare un seuil `seuil_m` et,
pour chaque partie, le HASH de son secret (jamais le secret lui-même). Une
présentation est valide si AU MOINS `seuil_m` secrets candidats DISTINCTS
hashent vers un hash de partie connu — comparé en temps constant
(hmac.compare_digest) pour ne pas fuiter d'information par le timing.

LIGNE ROUGE DE DOCTRINE : aucun secret n'est jamais reconstruit, combiné ni
partagé entre parties (ce n'est PAS du partage de secret façon Shamir) —
chaque candidat est comparé INDIVIDUELLEMENT à chaque hash connu. La config
elle-même (capital/jeton_seuil_config.json) ne stocke QUE des hashes ; elle
n'est jamais committée avec de vrais secrets (voir organes/jeton_seuil_config.json.exemple).

FAIL-CLOSED : toute config absente, illisible, ou de forme invalide se lit
comme une config INVALIDE (seuil_m=None, parties=[]) — verifier_jeton_seuil
refuse alors systématiquement (jamais un seuil permissif par défaut).

Usage bibliothèque uniquement (pas de CLI serveur ici) :
  from nexus_jeton_seuil import verifier_jeton_seuil
  valide, parties_confirmees = verifier_jeton_seuil(["<secret-kily>", "..."])
"""
import os
import sys
import json
import hmac
import hashlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

RACINE_DEPOT = os.path.dirname(SCRIPT_DIR)  # organes/ -> racine du dépôt

# Config INVALIDE canonique — retournée par lire_config() dès que le fichier
# est absent, illisible, mal formé ou incomplet. Un seuil_m=None ne peut
# JAMAIS être atteint par verifier_jeton_seuil (comparaison isinstance stricte).
_CONFIG_INVALIDE = {"seuil_m": None, "parties": []}


def _chemin_config():
    """Emplacement de la config réelle (NON versionnée — voir .gitignore et le
    fichier exemple organes/jeton_seuil_config.json.exemple). Override
    JETON_SEUIL_CONFIG (relu à chaque appel), même contrat que les autres
    organes NEXUS (MEMOIRE_ROOT, CAPTEURS_ROOT, ...)."""
    return os.environ.get(
        "JETON_SEUIL_CONFIG",
        os.path.join(RACINE_DEPOT, "capital", "jeton_seuil_config.json"),
    )


def _hash_secret(secret):
    """Hash SHA-256 (hex) d'un secret. Ne renvoie et ne journalise jamais le
    secret lui-même — seul ce hash a vocation à être stocké ou comparé."""
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    return hashlib.sha256(secret).hexdigest()


def lire_config(chemin=None):
    """Lit capital/jeton_seuil_config.json. FAIL-CLOSED : toute anomalie
    (fichier absent, JSON invalide, structure incomplète, seuil_m non entier
    positif, partie mal formée, nom de partie dupliqué) renvoie la config
    INVALIDE — jamais une exception, jamais un seuil par défaut permissif.

    Renvoie {"seuil_m": int|None, "parties": [{"nom": str, "hash": str}, ...]}."""
    chemin = chemin or _chemin_config()
    try:
        with open(chemin, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return dict(_CONFIG_INVALIDE)

    if not isinstance(data, dict):
        return dict(_CONFIG_INVALIDE)

    seuil_m = data.get("seuil_m")
    parties = data.get("parties")
    if not isinstance(seuil_m, int) or isinstance(seuil_m, bool) or seuil_m < 1:
        return dict(_CONFIG_INVALIDE)
    if not isinstance(parties, list) or not parties:
        return dict(_CONFIG_INVALIDE)

    noms_vus = set()
    parties_valides = []
    for p in parties:
        if not isinstance(p, dict):
            return dict(_CONFIG_INVALIDE)
        nom = p.get("nom")
        hash_partie = p.get("hash")
        if not isinstance(nom, str) or not nom.strip():
            return dict(_CONFIG_INVALIDE)
        if not isinstance(hash_partie, str) or not hash_partie.strip():
            return dict(_CONFIG_INVALIDE)
        if nom in noms_vus:
            return dict(_CONFIG_INVALIDE)
        noms_vus.add(nom)
        parties_valides.append({"nom": nom, "hash": hash_partie})

    return {"seuil_m": seuil_m, "parties": parties_valides}


def verifier_jeton_seuil(signatures, config=None):
    """Vérifie un jeton à seuil M-sur-N à partir d'une liste de secrets candidats
    (`signatures` — un candidat par partie qui se présente).

    Pour chaque candidat DISTINCT, hash-le (_hash_secret) et compare-le, via
    hmac.compare_digest (temps constant), au hash de chaque partie connue de la
    config. Le compte de parties DISTINCTES ainsi confirmées doit atteindre
    seuil_m pour que le jeton soit valide. Aucun secret n'est jamais reconstruit
    ni partagé entre parties — seulement comparé individuellement.

    `config` est optionnel (défaut : lire_config()) — utile pour injecter une
    config déjà lue/validée sans retoucher le disque.

    Renvoie (valide: bool, parties_confirmees: list[str])."""
    cfg = config if config is not None else lire_config()
    seuil_m = cfg.get("seuil_m") if isinstance(cfg, dict) else None
    parties = cfg.get("parties") if isinstance(cfg, dict) else None

    if not isinstance(seuil_m, int) or isinstance(seuil_m, bool) or seuil_m < 1:
        return False, []
    if not isinstance(parties, list) or not parties:
        return False, []
    if not signatures:
        return False, []

    vues = set()
    candidats = []
    for sig in signatures:
        if not isinstance(sig, str) or not sig:
            continue
        if sig in vues:
            continue
        vues.add(sig)
        candidats.append(sig)

    parties_confirmees = []
    for sig in candidats:
        sig_hash = _hash_secret(sig)
        for p in parties:
            nom = p.get("nom") if isinstance(p, dict) else None
            if nom is None or nom in parties_confirmees:
                continue
            hash_attendu = p.get("hash", "") if isinstance(p, dict) else ""
            if hmac.compare_digest(sig_hash, hash_attendu):
                parties_confirmees.append(nom)
                break

    valide = len(parties_confirmees) >= seuil_m
    return valide, parties_confirmees
