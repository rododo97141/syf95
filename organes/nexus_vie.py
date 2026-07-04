#!/usr/bin/env python3
"""
NEXUS — Vie des sources (remplace_par)
« Une plaie n'est plus vivante quand une leçon l'a remplacée — ou quand l'activité l'a éteinte. »

Micro-module DÉDIÉ, en LECTURE SEULE : il dit si une source (événement capteur,
« plaie ») est encore VIVANTE, à partir de la table de liaison source → leçon
(lecons/brouillons_promus.jsonl, écrite par nexus_pont à la promotion).

Doctrine :
  - Une source est « REMPLACÉE » si sa clé figure dans la table de liaison avec
    AU MOINS UNE lecon_ref. La relation est N-N et gérée explicitement :
    une même leçon peut remplacer plusieurs plaies, une même plaie peut être
    remplacée par plusieurs leçons (lecons_remplacantes les liste toutes).
  - La RÉCENCE est une HORLOGE D'ACTIVITÉ : elle se compte en nombre de runs
    (propres) écoulés, PAS en jours calendaires. Un organisme qui ne tourne pas
    ne vieillit pas.
  - VIVANTE = ni remplacée, ni éteinte par l'horloge d'activité.

Garde-fou : ce module LIT la table de liaison, il ne l'écrit JAMAIS
(seul nexus_pont écrit brouillons_promus.jsonl, append-only).

Rétrocompatibilité : les anciennes lignes {cle, promu_le} (sans lecon_ref)
restent valides — pas de lecon_ref = source NON remplacée.
"""
import os, json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# INTERIMAIRE : seuil de récence en nombre de runs, choisi à la louche en
# attendant des mesures réelles (96 pourra le calibrer). Paramétrable partout.
SEUIL_RECENCE_RUNS = 7


def _dir_lecons():
    """Même résolution que nexus_pont._dir_lecons (LECONS_ROOT isole les tests)."""
    base = os.environ.get("LECONS_ROOT")
    root = base if base else os.path.join(SCRIPT_DIR, "memoire_data")
    return os.path.join(root, "lecons")


def _lire_jsonl(chemin):
    out = []
    if not os.path.exists(chemin):
        return out
    for l in open(chemin, encoding="utf-8"):
        l = l.strip()
        if l:
            try:
                out.append(json.loads(l))
            except Exception:
                pass
    return out


def lire_liaisons():
    """Lit la table de liaison source → leçon (brouillons_promus.jsonl).
    LECTURE SEULE : ne crée ni ne modifie jamais le fichier."""
    return _lire_jsonl(os.path.join(_dir_lecons(), "brouillons_promus.jsonl"))


def cle_source(rec):
    """Clé d'une source : soit déjà une clé (str), soit un événement capteur
    (même identité que nexus_pont._cle : « ts|tache »)."""
    if isinstance(rec, str):
        return rec
    return f"{rec.get('ts','')}|{rec.get('tache','')}"


def _cle_liaison(ligne):
    """Clé portée par une ligne de liaison — nouveau format (cle_source) ou
    ancien format (cle), les deux restent valides."""
    return ligne.get("cle_source") or ligne.get("cle") or ""


def lecons_remplacantes(rec, liaisons):
    """Toutes les lecon_ref qui remplacent cette source (N-N : il peut y en
    avoir plusieurs). Dédoublonnées, ordre d'apparition conservé.
    Les lignes anciennes (sans lecon_ref) ne comptent pas."""
    cle = cle_source(rec)
    refs = []
    for ligne in liaisons:
        if _cle_liaison(ligne) == cle:
            ref = ligne.get("lecon_ref")
            if ref and ref not in refs:
                refs.append(ref)
    return refs


def est_remplacee(rec, liaisons):
    """True si la source est remplacée : sa clé figure dans la table de liaison
    avec AU MOINS UNE lecon_ref."""
    return bool(lecons_remplacantes(rec, liaisons))


def est_recent(runs_propres, seuil=SEUIL_RECENCE_RUNS):
    """Horloge d'ACTIVITÉ : récent tant que moins de `seuil` runs propres se
    sont écoulés depuis la source. Pas de calendrier ici."""
    return runs_propres < seuil


def est_vivant(rec, liaisons, runs_propres, seuil=SEUIL_RECENCE_RUNS):
    """Une source est VIVANTE si elle n'est PAS remplacée par une leçon ET que
    l'horloge d'activité ne l'a pas encore éteinte (< seuil runs propres).
    Remplacée → morte (la leçon a pris le relais) ; trop de runs propres →
    éteinte (le signal ne s'est pas reproduit)."""
    if est_remplacee(rec, liaisons):
        return False
    return est_recent(runs_propres, seuil)
