#!/usr/bin/env python3
"""
NEXUS — Pont capteurs → forces (« la force devient vivante »)
« Ce qui sert et réussit doit remonter ; ce qui sert et échoue, redescendre. »

Chaînon manquant entre le capteur dédié posé par la boucle (nexus_sense,
champ `fiche=<slug>` quand un recall a servi à une tâche) et le classement
pertinence(IDF) × force de memory_api.recall() (champ `force`, lu dans
ROOT/forces.json = {fiche: multiplicateur}).

DÉTERMINISTE, sans IA : chaque appel RECALCULE l'intégralité des forces à
partir de TOUT l'historique des capteurs porteurs d'une fiche (idempotent —
rejouable sans double-comptage, pas d'état de progression à maintenir). Les
fiches jamais vues dans les capteurs conservent leur valeur existante dans
forces.json (aucun réglage manuel écrasé).

Garde-fous :
  - N'écrit QUE si demandé (`--apply` en CLI ; `appliquer()` en bibliothèque).
  - N'efface jamais une entrée : fusion avec l'existant, jamais un remplacement.
  - Ne lève jamais depuis `appliquer()` (le pont ne doit jamais casser la boucle).

Usage :
  python3 nexus_force.py            # calcule et affiche les forces (dry-run)
  python3 nexus_force.py --apply    # + écrit ROOT/forces.json
"""
import os
import sys
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import nexus_sense  # source UNIQUE de lecture des capteurs (respecte CAPTEURS_ROOT)

# Pas de gagnant écrasant : petit pas par événement, borné.
DELTA_SUCCES = 0.2
DELTA_ECHEC = -0.1
FORCE_DEFAUT = 1.0
FORCE_MIN = 0.2
FORCE_MAX = 5.0


def _racine_memoire():
    """Racine des données mémoire-beta = ROOT de memory_api.py.
    Override MEMOIRE_ROOT (même contrat que CAPTEURS_ROOT/LECONS_ROOT, relu à
    CHAQUE appel — pas de cache d'import), sinon le même chemin par défaut que
    memory_api.py calcule."""
    base = os.environ.get("MEMOIRE_ROOT")
    if base:
        return base
    racine_depot = os.path.dirname(os.path.dirname(SCRIPT_DIR))  # organes/ -> racine
    return os.path.join(
        racine_depot, ".claude", "skills", "memoire-beta", "scripts", "memoire_data"
    )


def _chemin_forces():
    return os.path.join(_racine_memoire(), "forces.json")


def _lire_forces_existantes():
    try:
        with open(_chemin_forces(), encoding="utf-8") as f:
            data = json.load(f)
        return dict(data) if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def calculer_forces(evenements=None):
    """Calcule le multiplicateur de force par fiche à partir des capteurs
    porteurs d'un champ `fiche` non vide. Score net = (succès - échecs) pour
    cette fiche, sur TOUT l'historique ; multiplicateur = 1.0 ± pas fixe par
    unité de score net, borné à [FORCE_MIN, FORCE_MAX]. Fusionne avec les
    forces déjà présentes dans forces.json (préserve les réglages manuels des
    fiches sans capteur)."""
    if evenements is None:
        evenements = nexus_sense.lire()

    score = {}
    for ev in evenements:
        fiche = ev.get("fiche")
        if not fiche:
            continue
        statut = ev.get("statut")
        if statut == "succes":
            score[fiche] = score.get(fiche, 0) + 1
        elif statut == "echec":
            score[fiche] = score.get(fiche, 0) - 1

    forces = _lire_forces_existantes()
    for fiche, s in score.items():
        valeur = FORCE_DEFAUT + DELTA_SUCCES * max(s, 0) + DELTA_ECHEC * max(-s, 0)
        forces[fiche] = round(min(FORCE_MAX, max(FORCE_MIN, valeur)), 4)
    return forces


def ecrire_forces(forces):
    chemin = _chemin_forces()
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(forces, f, ensure_ascii=False, indent=2, sort_keys=True)
    return chemin


def appliquer():
    """Appel de bibliothèque pour la boucle : calcule ET écrit directement
    (pas de dry-run ici — purement additif/recalculable, jamais destructif).
    Ne lève jamais : protège l'appelant (la boucle orchestrateur)."""
    try:
        forces = calculer_forces()
        ecrire_forces(forces)
        return forces
    except Exception:
        return {}


def main():
    apply = "--apply" in sys.argv
    forces = calculer_forces()
    print("🔗 NEXUS — Pont capteurs → forces (force vivante)\n")
    if not forces:
        print("📭 Aucune fiche avec capteur : rien à calculer.")
    else:
        for fiche, mult in sorted(forces.items()):
            print(f"   • {fiche} : ×{mult}")
    if apply:
        chemin = ecrire_forces(forces)
        print(f"\n✅ Écrit dans {chemin}")
    else:
        print(f"\n🛡️  DRY-RUN : rien écrit. Relancer avec --apply pour écrire "
              f"{_chemin_forces()}.")


if __name__ == "__main__":
    main()
