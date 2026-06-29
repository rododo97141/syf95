#!/usr/bin/env python3
"""
NEXUS — Triage (anti-explosion combinatoire)
« Le défi n'est plus d'avoir des idées, c'est de choisir lesquelles méritent du temps. »

Réponse à l'architecte : un système qui génère ET fusionne des idées explose combinatoirement
(N idées → 2^N−1 combinaisons). La parade n'est PAS d'évaluer tout — c'est la stratégie de
l'ÉVOLUTION : population bornée + pression de sélection + budget. On ne déroule jamais tous les
sous-ensembles ; on trie les survivants en 3 niveaux sous un budget de coût cognitif.

3 verdicts (ce que l'architecte demande) :
  EXPLORER  (vaut le temps plein)  ·  SIMULER  (vérif rapide, pas cher)  ·  ABANDONNER

Score = valeur estimée ÷ coût estimé (le meilleur ratio gagne ; rien à voir avec « ça a l'air bien »).

Usage :
  python3 nexus_triage.py --idees "indexA:9:2,fusionAB:8:3,refacto:4:6,cache:7:2,ui:3:5" --budget 2
"""
import sys, argparse, math

def main():
    p = argparse.ArgumentParser(description="NEXUS — triage anti-explosion (population bornée + sélection)")
    p.add_argument("--idees", required=True, help="label:valeur:cout séparés par des virgules")
    p.add_argument("--budget", type=int, default=2, help="nb max d'idées à EXPLORER à fond (coût cognitif)")
    g = p.parse_args()

    idees = []
    for bloc in g.idees.split(","):
        bloc = bloc.strip()
        if not bloc:
            continue
        if bloc.count(":") != 2:
            print(f"⚠️ bloc ignoré (format label:valeur:cout) : « {bloc} »"); continue
        lab, val, cout = bloc.split(":")
        try:
            val = float(val); cout = float(cout)
        except ValueError:
            print(f"⚠️ valeur/coût non numérique, ignoré : « {bloc} »"); continue
        if not (math.isfinite(val) and math.isfinite(cout)):
            print(f"⚠️ valeur non finie, ignoré : « {bloc} »"); continue
        idees.append({"label": lab.strip(), "valeur": val, "cout": cout,
                      "score": val / max(cout, 0.1)})
    if not idees:
        print("🔴 Aucune idée valide (format : label:valeur:cout, ...)."); return
    n = len(idees)
    idees.sort(key=lambda x: (-x["score"], x["label"]))   # tri déterministe (correctif prouvé par le duo)

    combinaisons = 2 ** n - 1  # ce qu'une exploration NAÏVE devrait considérer
    b = max(1, g.budget)

    print("🧮 NEXUS — TRIAGE (anti-explosion combinatoire)")
    print(f"   {n} idées → {combinaisons} combinaisons possibles si on déroulait TOUT.")
    print(f"   Stratégie évolutive : population bornée + sélection + budget ({b} à explorer).\n")

    for i, e in enumerate(idees):
        if i < b:
            tier = "🟢 EXPLORER  (temps plein)"
        elif i < 2 * b:
            tier = "🟡 SIMULER   (vérif rapide)"
        else:
            tier = "⚪ ABANDONNER"
        print(f"   {tier}  · {e['label']:12} valeur {e['valeur']:.0f} / coût {e['cout']:.0f} = score {e['score']:.1f}")

    explore = min(b, n); simule = min(b, max(0, n - b)); drop = max(0, n - 2 * b)
    print(f"\n   → On explore {explore}, on simule {simule}, on abandonne {drop}.")
    print(f"   Explosion évitée : {combinaisons} possibles → {explore} réellement explorées. "
          "On ne déroule jamais tout ; la sélection fait le tri (comme l'évolution).")

if __name__ == "__main__":
    main()
