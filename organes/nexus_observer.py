#!/usr/bin/env python3
"""
NEXUS — Observer (l'organe de CLÔTURE administrative des consultations de boucle)
« Automatiser la CLÔTURE, jamais le JUGEMENT. »

Étape 1 de l'autonomie du déclencheur HITL : LA VISIBILITÉ. La boucle
(orchestrateur.tourner) rend désormais ses rappels COMPTABLES en passant par
nexus_capital.consulter — chaque tâche avec fiche ouvre une consultation visible
au bilan. Sans clôture, ces consultations s'accumuleraient en fausse « dette ».

L'observer clôt ces consultations de boucle — mais UNIQUEMENT en clôture
ADMINISTRATIVE : clore_sans_dette(raison="boucle-sans-verdict-humain"). Il ne
JUGE jamais : il n'appelle NI generer_jeton_confirmation NI la clôture de
jugement. Dissymétrie de doctrine : la cloture administrative est libre, le
jugement (la force) reste verrouillé derrière un jeton humain.

Deux propriétés NON négociables :
  1) DÉFENSIF : toute exception côté clôture est AVALÉE — la tâche de la boucle
     continue TOUJOURS (un organe périphérique ne casse jamais la boucle).
  2) TRAÇANT : chaque échec de clôture est JOURNALISÉ dans un event dédié (jamais
     d'échec silencieux). La consultation qui n'a pas pu être close reste OUVERTE,
     donc VISIBLE au bilan — l'inverse d'un échec avalé en silence (Goodhart).

GARDE MULTI-FICHES : quelle que soit la consultation (même multi-fiches un jour),
le chemin route TOUJOURS vers clore_sans_dette, JAMAIS vers un capteur de force.

Usage bibliothèque uniquement.
"""
import os
import sys
import json
import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# Raison de clôture administrative des consultations de boucle (traçable au bilan).
RAISON_CLOTURE_BOUCLE = "boucle-sans-verdict-humain"


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _chemin_echecs():
    """Journal PROPRE de l'observer (fichier distinct : l'observer est son seul
    écrivain). Racine mémoire déléguée à nexus_capital (source unique, lecture)."""
    import nexus_capital
    return os.path.join(nexus_capital._racine(), "observer", "echecs_cloture.jsonl")


def cloturer_consultation_boucle(consultation_id):
    """Clôt UNE consultation de boucle en clôture ADMINISTRATIVE
    (clore_sans_dette, raison boucle-sans-verdict-humain). Ne JUGE jamais.

    - `consultation_id is None` (aucune fiche rappelée) : rien à clôturer.
    - clôture qui lève : l'exception est AVALÉE (la boucle continue) MAIS
      journalisée (échec tracé, consultation laissée OUVERTE donc visible).

    Renvoie l'enregistrement de clôture, ou None (rien à faire / échec avalé)."""
    if consultation_id is None:
        return None
    try:
        import nexus_capital
        return nexus_capital.clore_sans_dette(consultation_id, RAISON_CLOTURE_BOUCLE)
    except Exception as exc:                       # DÉFENSIF : la boucle continue
        _journaliser_echec_cloture(consultation_id, exc)   # TRAÇANT : jamais silencieux
        return None


def _journaliser_echec_cloture(consultation_id, exc):
    """Trace un échec de clôture (event dédié). La consultation reste OUVERTE au
    bilan (pas de fausse clôture) : la trace + l'ouverture rendent l'échec VISIBLE.
    Best-effort, ne lève JAMAIS (double rideau défensif : ni la clôture ni sa
    journalisation ne peuvent casser la boucle)."""
    try:
        chemin = _chemin_echecs()
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        rec = {
            "type": "echec_cloture",
            "consultation_id": consultation_id,
            "raison": RAISON_CLOTURE_BOUCLE,
            "erreur": repr(exc),
            "ts": _now(),
        }
        with open(chemin, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        return None


def echecs_cloture():
    """Vue LECTURE SEULE des échecs de clôture journalisés (tests / diagnostic).
    Absent/corrompu → [] (défensif, ne lève jamais)."""
    try:
        chemin = _chemin_echecs()
    except Exception:
        return []
    if not os.path.exists(chemin):
        return []
    out = []
    try:
        for line in open(chemin, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        return []
    return out
