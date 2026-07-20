#!/usr/bin/env python3
"""
NEXUS — Vitalité observée (réutilisation cross-session d'une fiche mémoire)
« Ce qui revient et sert, dans le temps et sur plusieurs tâches, est vivant. »

Lecture SEULE : ce module n'écrit JAMAIS aucun fichier. Il croise deux sources
déjà écrites ailleurs (jamais dupliquées ici) :

  - <MEMOIRE_ROOT>/capital/consultations.jsonl (écrit par nexus_capital.consulter)
    — champs `type`, `ts`, `tache`, `slugs_retournes`.
  - <CAPTEURS_ROOT>/capteurs/journal.jsonl (écrit par nexus_sense.log_event)
    — champs `ts`, `tache`, `fiche`.

Racines : MÊMES contrats d'environnement que nexus_force (MEMOIRE_ROOT, relu à
chaque appel via nexus_force._racine_memoire) et nexus_sense (CAPTEURS_ROOT,
relu à chaque appel via nexus_sense.lire) — pas de cache d'import, pas de
logique de chemin dupliquée pour les capteurs.

AJOUT PUR opt-in : ce module n'est branché nulle part par défaut. Seul un
appelant qui passe explicitement `vitalite=...` à nexus_force.calculer_forces
en subit l'effet (cf. nexus_force.DELTA_VITALITE_MAX).

Usage :
  python3 nexus_vitalite.py     # dry-run : indice de vitalité par fiche
"""
import os
import sys
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import nexus_force  # source UNIQUE de _racine_memoire (respecte MEMOIRE_ROOT)
import nexus_sense   # source UNIQUE de lecture des capteurs (respecte CAPTEURS_ROOT)

# Garde-fou anti-forgeage en une seule session : sous ce double seuil, indice=0
# quel que soit le nombre d'événements accumulés le même jour.
JOURS_MIN_VIVANTE = 2
TACHES_MIN_VIVANTE = 2

# Montée linéaire de l'indice, plafonnée : au-delà, un jour/une tâche de plus
# ne fait plus monter l'indice.
JOURS_PLAFOND = 10
TACHES_PLAFOND = 10


def _chemin_consultations():
    return os.path.join(nexus_force._racine_memoire(), "capital", "consultations.jsonl")


def _lire_consultations():
    """Lecture SEULE de consultations.jsonl. Fichier absent => liste vide (jamais
    créé ici). Ligne corrompue ignorée (robustesse), jamais d'exception remontée."""
    chemin = _chemin_consultations()
    if not os.path.exists(chemin):
        return []
    out = []
    for line in open(chemin, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _jour(ts):
    """Jour calendaire (YYYY-MM-DD) d'un horodatage ISO, ou None si absent —
    un événement sans `ts` exploitable n'ajoute aucun jour distinct."""
    if not ts:
        return None
    jour = str(ts)[:10]
    return jour or None


def mesurer_vitalite(consultations=None, capteurs=None):
    """Brut de réutilisation observée par fiche : {fiche: {"jours": set, "taches": set}}.

    Fusionne consultations.jsonl (une fiche par slug de `slugs_retournes`) et
    capteurs/journal.jsonl (champ `fiche`) SANS double-compte : un même
    (fiche, jour) ou (fiche, tâche) vu dans les DEUX sources ne compte qu'une
    fois, parce que jours/taches sont des ENSEMBLES, pas des compteurs.

    Lecture SEULE — n'écrit jamais rien. `consultations`/`capteurs` injectables
    pour les tests ; par défaut, lus depuis les sources réelles (respectant
    MEMOIRE_ROOT / CAPTEURS_ROOT)."""
    if consultations is None:
        consultations = _lire_consultations()
    if capteurs is None:
        capteurs = nexus_sense.lire()

    brut = {}

    def _toucher(fiche, jour, tache):
        if not fiche:
            return
        rec = brut.setdefault(fiche, {"jours": set(), "taches": set()})
        if jour:
            rec["jours"].add(jour)
        if tache:
            rec["taches"].add(tache)

    for rec in consultations:
        if rec.get("type") != "consultation":
            continue
        jour = _jour(rec.get("ts"))
        tache = rec.get("tache")
        for slug in (rec.get("slugs_retournes") or []):
            _toucher(slug, jour, tache)

    for ev in capteurs:
        _toucher(ev.get("fiche"), _jour(ev.get("ts")), ev.get("tache"))

    return brut


def indice_vitalite(brut=None):
    """Indice de vitalité par fiche, dans [0, 1] : {fiche: indice}.

    Sous le double seuil JOURS_MIN_VIVANTE ET TACHES_MIN_VIVANTE (garde-fou
    anti-forgeage — empêche une seule session à répétition de se faire passer
    pour de la vitalité réelle), indice=0. Au-dessus, montée LINÉAIRE des deux
    ratios (jours/JOURS_PLAFOND, taches/TACHES_PLAFOND), chacun plafonné à 1.0 ;
    indice = moyenne des deux ratios."""
    if brut is None:
        brut = mesurer_vitalite()

    indices = {}
    for fiche, rec in brut.items():
        n_jours = len(rec.get("jours") or ())
        n_taches = len(rec.get("taches") or ())
        if n_jours < JOURS_MIN_VIVANTE or n_taches < TACHES_MIN_VIVANTE:
            indices[fiche] = 0.0
            continue
        ratio_jours = min(1.0, n_jours / JOURS_PLAFOND)
        ratio_taches = min(1.0, n_taches / TACHES_PLAFOND)
        indices[fiche] = (ratio_jours + ratio_taches) / 2.0
    return indices


def rapport():
    """Dry-run affiché, trié par indice décroissant puis fiche. Lecture SEULE
    (n'écrit jamais rien) ; renvoie l'indice calculé."""
    brut = mesurer_vitalite()
    indices = indice_vitalite(brut)
    print("🌱 NEXUS — Vitalité observée (réutilisation cross-session)\n")
    if not indices:
        print("📭 Aucune fiche avec consultation/capteur : rien à mesurer.")
        return indices
    ordre = sorted(indices.items(), key=lambda kv: (-kv[1], kv[0]))
    for fiche, idx in ordre:
        rec = brut[fiche]
        print(f"   • {fiche} : indice={idx:.2f} "
              f"(jours={len(rec['jours'])}, taches={len(rec['taches'])})")
    return indices


if __name__ == "__main__":
    rapport()
