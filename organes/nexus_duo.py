#!/usr/bin/env python3
"""
NEXUS — Duo croisé (relecture par une 2ᵉ IA) · spécialisation code du conseil inter-systèmes
« Un modèle ne voit pas ses propres angles morts — un modèle DIFFÉRENT, lui, les repère. »

Méthode (d'après @dupflodev / repos shanraisshan partagés par Boris Cherny) : pour le code critique,
NE PAS faire relire par l'IA qui a écrit. Brancher deux modèles DIFFÉRENTS dans une boucle :
  A planifie → B relit le plan contre le vrai code (ajoute ce qui manque, NE RÉÉCRIT PAS)
  → A implémente → B vérifie. L'un propose, l'autre conteste, en boucle.
⚠️ Plus lourd (2 outils/abos) : à réserver aux projets critiques.

Dans NEXUS : c'est le conseil inter-systèmes appliqué au code, via le moteur INTERCHANGEABLE
(A et B = deux moteurs distincts : Claude ↔ Codex/GPT ↔ Gemini…). Rôle de B = le contradicteur
(parenté avec 98/ZÉRO). Journalise la session avec `nexus_council log`.

Usage :
  python3 nexus_duo.py prompts "ajouter l'authentification" --a Claude --b Codex
"""
import argparse

PLAN = """[ÉTAPE 1 · {a} = CONSTRUCTEUR]  Fais un PLAN détaillé pour : « {tache} ».
Pas de code encore — étapes, fichiers touchés, risques, critères de réussite."""

RELIRE = """[ÉTAPE 2 · {b} = RELECTEUR (modèle DIFFÉRENT de {a})]
Relis le plan ci-dessus CONTRE le vrai code du projet. Repère les angles morts, ce qui manque,
les cas limites, les risques de régression. AJOUTE ce qui manque — NE RÉÉCRIS PAS le plan."""

IMPL = """[ÉTAPE 3 · {a} = CONSTRUCTEUR]  Implémente le plan AMENDÉ (avec les ajouts de {b})."""

VERIF = """[ÉTAPE 4 · {b} = RELECTEUR]  Vérifie l'implémentation : bugs, angles morts, tests
manquants, écarts au plan. Conteste sans complaisance. → boucle jusqu'à OK."""

def main():
    p = argparse.ArgumentParser(description="NEXUS — duo croisé (pipeline code à 2 modèles)")
    sub = p.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("prompts"); pp.add_argument("tache")
    pp.add_argument("--a", default="Claude", help="modèle constructeur (planifie + code)")
    pp.add_argument("--b", default="Codex", help="modèle relecteur (DIFFÉRENT de A)")
    pp.set_defaults(func=lambda g: None)
    g = p.parse_args()
    if g.a.lower() == g.b.lower():
        print("⚠️ A et B doivent être DEUX modèles DIFFÉRENTS (sinon pas d'angles morts détectés).")
    print("🤝 NEXUS — DUO CROISÉ (plan → relire → implémenter → vérifier)\n")
    for bloc in (PLAN, RELIRE, IMPL, VERIF):
        print(bloc.format(a=g.a, b=g.b, tache=g.tache)); print()
    print("="*66)
    print(f"→ Boucle : {g.a} propose · {g.b} conteste, jusqu'à OK. (réserver au code critique)")
    print("  Journalise la session : python3 nexus_council.py log ...")

if __name__ == "__main__":
    main()
