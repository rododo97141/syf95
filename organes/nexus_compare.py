#!/usr/bin/env python3
"""
NEXUS — Comparateur (l'étape « Comparaison » du pipeline d'apprentissage)
« Est-ce un meilleur RÉSULTAT — pas : est-ce que ça en a l'air ? »

Réponse directe à l'architecte : recherche ≠ validation. La recherche améliore les HYPOTHÈSES ;
seule la comparaison de RÉSULTATS prouve qu'une version est meilleure. On compare deux versions
de la MÊME tâche sur des résultats objectifs (temps ↓, erreurs ↓, succès ↑) — jamais sur la
créativité, l'apparence, ou « on a beaucoup débattu ».

Règle anti-illusion : on ne déclare un gagnant que s'il DOMINE (au moins aussi bon partout, et
strictement meilleur quelque part). Sinon : pas de gagnant clair → arbitrage à pré-enregistrer.

Usage :
  python3 nexus_compare.py --tache "générer le rapport" \
     --a prose   --tempsA 8 --erreursA 3 --succesA 0.6 \
     --b schema  --tempsB 5 --erreursB 1 --succesB 0.9
"""
import os, sys, json, argparse, datetime

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoire_data", "comparaisons")
JOURNAL = os.path.join(DIR, "journal.jsonl")

def verdict(a, b):
    """b vs a sur 3 axes résultat : temps (moins=mieux), erreurs (moins=mieux), succès (plus=mieux)."""
    axes = [("temps", a["temps"], b["temps"], "min"),
            ("erreurs", a["erreurs"], b["erreurs"], "min"),
            ("succès", a["succes"], b["succes"], "max")]
    b_mieux = b_pire = 0
    detail = []
    for nom, va, vb, sens in axes:
        if sens == "min":
            if vb < va: b_mieux += 1; signe = "✓ B"
            elif vb > va: b_pire += 1; signe = "✗ B"
            else: signe = "="
        else:
            if vb > va: b_mieux += 1; signe = "✓ B"
            elif vb < va: b_pire += 1; signe = "✗ B"
            else: signe = "="
        detail.append(f"   {nom:8} A={va} · B={vb}   {signe}")
    if b_mieux >= 1 and b_pire == 0:
        v = f"🏆 B (« {b['label']} ») DOMINE — meilleur résultat, sans contrepartie."
    elif b_pire >= 1 and b_mieux == 0:
        v = f"🏆 A (« {a['label']} ») DOMINE — B n'apporte rien de mieux."
    else:
        v = "⚖️ Pas de gagnant CLAIR (compromis). Pré-enregistre le critère qui prime avant de trancher."
    return detail, v

def main():
    p = argparse.ArgumentParser(description="NEXUS — comparateur de résultats (étape Comparaison)")
    p.add_argument("--tache", required=True)
    p.add_argument("--a", default="A"); p.add_argument("--tempsA", type=float, required=True)
    p.add_argument("--erreursA", type=int, required=True); p.add_argument("--succesA", type=float, required=True)
    p.add_argument("--b", default="B"); p.add_argument("--tempsB", type=float, required=True)
    p.add_argument("--erreursB", type=int, required=True); p.add_argument("--succesB", type=float, required=True)
    g = p.parse_args()
    a = {"label": g.a, "temps": g.tempsA, "erreurs": g.erreursA, "succes": g.succesA}
    b = {"label": g.b, "temps": g.tempsB, "erreurs": g.erreursB, "succes": g.succesB}
    detail, v = verdict(a, b)
    print(f"⚖️  NEXUS — COMPARAISON : « {g.tache} »  ({g.a} vs {g.b})")
    print("   (on compare des RÉSULTATS, pas l'apparence ni la créativité)\n")
    print("\n".join(detail))
    print(f"\n   → {v}")
    os.makedirs(DIR, exist_ok=True)
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"),
                            "tache": g.tache, "a": a, "b": b, "verdict": v}, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    main()
