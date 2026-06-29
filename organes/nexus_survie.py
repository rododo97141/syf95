#!/usr/bin/env python3
"""
NEXUS — Règle de survie des solutions (darwinien : plusieurs survivent, aucune ne meurt)
« Où est la limite ? Qui décide ? Sur quelle métrique ? » → une règle, pas une personne.

Réponse à l'architecte (A=90, B=89, C=88, D=20 : on garde quoi ?). La survie n'est pas « le meilleur
seul » ni « tout le monde » : c'est une BANDE de survie + l'archive (rien ne meurt, tout est
réactivable). Décidé par la règle, sur la métrique du score.

Trois sorts :
  🟢 ACTIF    : score ≥ meilleur − bande  (variantes proches du sommet → vivent en parallèle, utiles selon le contexte)
  🟡 RÉSERVE  : sous la bande mais gagne dans ≥1 contexte (--gem)  → archivé, réactivable (pépite dormante)
  ⚪ ARCHIVE  : loin du sommet et sans contexte gagnant → archive profonde, JAMAIS supprimée

Usage :
  python3 nexus_survie.py --solutions "A:90,B:89,C:88,D:20" --bande 5 --gem C
"""
import argparse, math

def main():
    p = argparse.ArgumentParser(description="NEXUS — règle de survie (bande + archive)")
    p.add_argument("--solutions", required=True, help="label:score séparés par des virgules")
    p.add_argument("--bande", type=float, default=5, help="écart max au meilleur pour rester ACTIF")
    p.add_argument("--gem", default="", help="labels qui gagnent dans ≥1 contexte (réserve), séparés par des virgules")
    g = p.parse_args()

    sols = []
    for b in g.solutions.split(","):
        b = b.strip()
        if not b:
            continue
        if b.count(":") != 1:
            print(f"⚠️ bloc ignoré (format label:score) : « {b} »"); continue
        lab, sc = b.split(":")
        try:
            val = float(sc)
        except ValueError:
            print(f"⚠️ score non numérique, ignoré : « {b} »"); continue
        if not math.isfinite(val):
            print(f"⚠️ score non fini, ignoré : « {b} »"); continue
        sols.append({"label": lab.strip(), "score": val})
    if not sols:
        print("🔴 Aucune solution valide (format : label:score, ...)."); return
    sols.sort(key=lambda s: (-s["score"], s["label"]))   # tri déterministe (correctif prouvé par le duo)
    meilleur = sols[0]["score"]
    seuil = meilleur - g.bande
    gems = {x.strip() for x in g.gem.split(",") if x.strip()}

    print("🧬 NEXUS — RÈGLE DE SURVIE")
    print(f"   meilleur = {meilleur:.0f} · bande de survie = {g.bande:.0f} → seuil ACTIF ≥ {seuil:.0f}\n")
    n_act = n_res = n_arc = 0
    for s in sols:
        if s["score"] >= seuil:
            tag = "🟢 ACTIF"; n_act += 1
        elif s["label"] in gems:
            tag = "🟡 RÉSERVE (gagne un contexte)"; n_res += 1
        else:
            tag = "⚪ ARCHIVE (jamais supprimée)"; n_arc += 1
        print(f"   {tag:32} {s['label']:4} score {s['score']:.0f}")
    print(f"\n   → {n_act} actives (variantes du sommet) · {n_res} en réserve · {n_arc} archivées.")
    print("   La limite n'est pas arbitraire : c'est la BANDE (relative au meilleur). Rien ne meurt.")

if __name__ == "__main__":
    main()
