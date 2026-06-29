#!/usr/bin/env python3
"""
NEXUS — Critère d'arrêt (anti « amélioration infinie »)
« Suffisamment bon pour être exécuté > parfait jamais livré. »

Réponse à l'architecte : il existe presque toujours une idée encore meilleure → un système qui
vise l'optimum réfléchit éternellement. La parade est le SATISFICING (Herbert Simon) : on s'arrête
quand l'une des trois conditions est vraie :
  1. le résultat atteint le SEUIL pré-enregistré (« assez bon ») ;
  2. le dernier GAIN est sous le seuil de rendement décroissant (optimiser coûte plus que ça ne rapporte) ;
  3. le BUDGET (temps/itérations) est épuisé.

Usage :
  python3 nexus_stop.py --resultat 0.86 --seuil 0.85 --gain 0.015 --gain-min 0.03 --iter 4 --iter-max 6
"""
import argparse

def main():
    p = argparse.ArgumentParser(description="NEXUS — critère d'arrêt (satisficing)")
    p.add_argument("--resultat", type=float, required=True, help="qualité actuelle 0..1")
    p.add_argument("--seuil", type=float, default=0.85, help="seuil 'suffisamment bon' pré-enregistré")
    p.add_argument("--gain", type=float, default=None, help="gain de la dernière itération")
    p.add_argument("--gain-min", type=float, default=0.03, help="gain minimal qui justifie de continuer")
    p.add_argument("--iter", type=int, default=None); p.add_argument("--iter-max", type=int, default=None)
    g = p.parse_args()

    print("🛑 NEXUS — CRITÈRE D'ARRÊT (suffisamment bon ?)")
    raisons = []
    if g.resultat >= g.seuil:
        raisons.append(f"résultat {g.resultat:.0%} ≥ seuil {g.seuil:.0%} (assez bon)")
    if g.gain is not None and g.gain < g.gain_min:
        raisons.append(f"gain {g.gain:.0%} < {g.gain_min:.0%} (rendement décroissant)")
    if g.iter is not None and g.iter_max is not None and g.iter >= g.iter_max:
        raisons.append(f"budget épuisé ({g.iter}/{g.iter_max} itérations)")

    if raisons:
        print("   → ✅ LIVRER. On s'arrête : " + " ; ".join(raisons) + ".")
        print("   (On garde l'idée en mémoire : on pourra la rouvrir si le contexte l'exige.)")
    else:
        print(f"   → 🔁 CONTINUER. Résultat {g.resultat:.0%} < seuil, gain encore utile, budget restant.")

if __name__ == "__main__":
    main()
