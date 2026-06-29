#!/usr/bin/env python3
"""
NEXUS — Analyse causale (passer de « A a marché » à « A a marché PARCE QUE… »)
« La corrélation n'est pas la cause. »

Réponse au prochain grand chantier (architecte, 23/06/2026) : mémoire + détecteurs produisent des
corrélations, pas une compréhension. Avant de dire « A est meilleure », il faut ÉCARTER les
hypothèses rivales (confusions) :
  - A a-t-elle été testée sur des cas plus FACILES ?      → contrôle par la difficulté (stratification)
  - A a-t-elle eu plus de RESSOURCES (temps/coût) ?        → contrôle par le coût
  - info de meilleure qualité / bon timing ?               → NON mesuré → réserve honnête

Verdict : on ne déclare une CAUSE que si A gagne ET que les confusions mesurables sont écartées.
Sinon : « corrélation, pas (encore) cause ». Et on déclare la confiance (petit n = piste).

Usage :
  python3 nexus_cause.py --a A --succesA 0.8 --diffA 2 --coutA 4 \
                         --b B --succesB 0.4 --diffB 2 --coutB 4 --n 12
  (diff : 1=facile, 2=moyen, 3=dur ; coût : ressources consommées)
"""
import argparse

def conf(n):
    return "FAIBLE (piste, pas preuve)" if n < 15 else ("MOYENNE" if n < 50 else "BONNE")

def main():
    p = argparse.ArgumentParser(description="NEXUS — analyse causale (écarter les confusions)")
    p.add_argument("--a", default="A"); p.add_argument("--succesA", type=float, required=True)
    p.add_argument("--diffA", type=float, required=True); p.add_argument("--coutA", type=float, required=True)
    p.add_argument("--b", default="B"); p.add_argument("--succesB", type=float, required=True)
    p.add_argument("--diffB", type=float, required=True); p.add_argument("--coutB", type=float, required=True)
    p.add_argument("--n", type=int, default=10)
    g = p.parse_args()

    print(f"🔬 NEXUS — ANALYSE CAUSALE : pourquoi « {g.a} » plutôt que « {g.b} » ?")
    print(f"   Observation : {g.a} {g.succesA:.0%} vs {g.b} {g.succesB:.0%}\n")
    if g.succesA <= g.succesB:
        print(f"   {g.a} ne surpasse pas {g.b} — pas de cause à expliquer ici."); return

    print("   Hypothèses rivales (à écarter avant de conclure) :")
    diff_ok = g.diffA >= g.diffB
    cost_ok = g.coutA <= g.coutB
    print(f"   • « {g.a} sur cas plus faciles ? »   diff {g.diffA} vs {g.diffB} → "
          + ("écartée (≥ difficulté)" if diff_ok else "⚠️ PLAUSIBLE (cas plus faciles)"))
    print(f"   • « {g.a} avec plus de ressources ? » coût {g.coutA} vs {g.coutB} → "
          + ("écartée (≤ coût)" if cost_ok else "⚠️ PLAUSIBLE (plus de ressources)"))
    print(f"   • « meilleure info / bon timing ? »  → NON mesuré → réserve")

    print()
    if diff_ok and cost_ok:
        print(f"   → CAUSE PROBABLE : « {g.a} » est réellement meilleure "
              "(confusions difficulté + ressources écartées).")
    else:
        causes = []
        if not diff_ok: causes.append("des tâches plus faciles")
        if not cost_ok: causes.append("plus de ressources")
        print(f"   → CORRÉLATION, PAS (encore) CAUSE : l'avantage de « {g.a} » s'explique au moins "
              f"en partie par {', '.join(causes)}. Refaire à difficulté/coût ÉGAUX pour trancher.")
    print(f"\n   Confiance : {conf(g.n)} (n={g.n}). Facteurs non mesurés (info, timing) → on reste prudent.")

if __name__ == "__main__":
    main()
