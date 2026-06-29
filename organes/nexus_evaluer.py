#!/usr/bin/env python3
"""
NEXUS — Évaluateur (définir « meilleur » : Score = f(contexte))
« Il n'y a pas de "il veut gagner" — il y a un Score, et le contexte fixe les poids. »

Réponse directe à l'architecte :
  (1) « Qui décide que c'est le meilleur ? » → personne ne "décide" : on CALCULE un score, et la
      valeur dépend du CONTEXTE (les poids). La même solution gagne ici, perd là.
  (2) anti-anthropomorphisme : pas d'intérêt, pas de volonté — juste une fonction d'évaluation.

  Score(solution, contexte) = Σ  poids_contexte[critère] × valeur_effective[critère]   (normalisé /Σpoids)
  (les critères « moins = mieux » — coût, risque — sont inversés : valeur_effective = 10 − valeur)

Usage :
  python3 nexus_evaluer.py --solutions "A:9,3,5,5,5,9;B:3,9,5,5,5,2;C:5,6,9,2,4,4;D:5,6,5,9,9,4"
  (ordre des 6 valeurs : creativite,fiabilite,rentabilite,rapidite,cout,risque)
  (sans --contexte : évalue sous TOUS les contextes pour montrer que le gagnant CHANGE)
"""
import sys, argparse, math

CRITERES = ["creativite", "fiabilite", "rentabilite", "rapidite", "cout", "risque"]
MOINS_MIEUX = {"cout", "risque"}  # inversés
CONTEXTES = {
    "innovation": {"creativite": 3, "fiabilite": 1, "rentabilite": 1, "rapidite": 1, "cout": 0.5, "risque": 0.5},
    "production": {"creativite": 0.5, "fiabilite": 3, "rentabilite": 2, "rapidite": 1, "cout": 2, "risque": 2},
    "urgence":    {"creativite": 0.5, "fiabilite": 2, "rentabilite": 1, "rapidite": 3, "cout": 1, "risque": 1},
}

def score(sol, poids):
    s = w = 0.0
    for c in CRITERES:
        p = poids.get(c, 0)
        if not math.isfinite(p) or p < 0:   # correctif B : poids non finis ou négatifs ignorés
            continue
        val = sol[c]
        if not math.isfinite(val):           # correctif B : valeur non finie ignorée
            continue
        eff = (10 - val) if c in MOINS_MIEUX else val
        s += p * eff; w += p
    return s / w if w else 0

def main():
    p = argparse.ArgumentParser(description="NEXUS — évaluateur contextuel (Score = f(contexte))")
    p.add_argument("--solutions", required=True, help="label:creativite,fiabilite,rentabilite,rapidite,cout,risque ; séparés par ;")
    p.add_argument("--contexte", choices=list(CONTEXTES), default=None)
    g = p.parse_args()

    sols = []
    for bloc in g.solutions.split(";"):
        bloc = bloc.strip()
        if not bloc:
            continue
        if bloc.count(":") != 1:
            print(f"⚠️ bloc ignoré (format label:v,v,...) : « {bloc} »"); continue
        lab, vals = bloc.split(":")
        try:
            nums = [float(x) for x in vals.split(",")]
        except ValueError:
            print(f"⚠️ valeurs non numériques, bloc ignoré : « {bloc} »"); continue
        if len(nums) != len(CRITERES):
            print(f"⚠️ il faut {len(CRITERES)} valeurs ({','.join(CRITERES)}), bloc ignoré : « {lab.strip()} »"); continue
        nums = [min(10.0, max(0.0, n)) for n in nums]   # durcissement A : clamp 0..10
        sols.append({"label": lab.strip(), **dict(zip(CRITERES, nums))})
    if not sols:
        print("🔴 Aucune solution valide. Format : label:creativite,fiabilite,rentabilite,rapidite,cout,risque ; ..."); return

    contextes = [g.contexte] if g.contexte else list(CONTEXTES)
    print("⚖️  NEXUS — ÉVALUATEUR CONTEXTUEL (« meilleur » = Score, pas volonté)")
    print("   Score = Σ poids_contexte × critère (coût/risque inversés). Le CONTEXTE fixe les poids.\n")
    gagnants = {}
    for ctx in contextes:
        poids = CONTEXTES[ctx]
        # correctif B : départage déterministe des ex aequo (score desc, puis risque bas, puis label)
        classés = sorted(sols, key=lambda s: (-score(s, poids), s.get("risque", 0), s["label"]))
        gagnants[ctx] = classés[0]["label"]
        ligne = " · ".join(f"{s['label']} {score(s, poids):.1f}" for s in classés)
        print(f"   [{ctx:11}] {ligne}   → 🏆 {classés[0]['label']}")
    if len(contextes) > 1:
        diff = len(set(gagnants.values()))
        print(f"\n   → {diff} gagnant(s) différent(s) selon le contexte : la valeur DÉPEND du contexte (c'est calculé, pas décrété).")
        # MOTEUR DE VALEUR : éliminer le faible SANS tuer les futures pépites
        winners = set(gagnants.values())
        print("\n   🌱 Moteur de valeur (on n'élimine jamais — on archive) :")
        for s in sols:
            if s["label"] in winners:
                print(f"      ✅ GARDER   {s['label']} — gagne dans ≥1 contexte (pépite active)")
            else:
                print(f"      📦 ARCHIVER {s['label']} — dominée dans CES contextes ; jamais supprimée "
                      "(elle peut briller dans un contexte futur — cf. smartphone tactile 2005→2025)")
        print("      Règle : archiver, pas supprimer ; réévaluer les archives quand le contexte change.")

if __name__ == "__main__":
    main()
