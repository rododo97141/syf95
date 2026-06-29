#!/usr/bin/env python3
"""
NEXUS — Conseil inter-systèmes (multi-agent reflection)
« Un modèle construit, un autre attaque, NEXUS tranche. »

Outil léger qui formalise la méthode : il GÉNÈRE les deux prompts (constructeur / red-team)
prêts à coller dans deux modèles différents, et JOURNALISE chaque conseil (matière pour 96).
Il ne décide pas — il structure et trace. La décision reste à 95/Kily.

Usage :
  python3 nexus_council.py prompts "doit-on faire X ?"
  python3 nexus_council.py log "doit-on faire X ?" --constructeur Gemini --critique ChatGPT \
        --decision "on garde A + correctif B" --lecon "convergence sur le risque Goodhart"
  python3 nexus_council.py list
"""
import os, sys, json, argparse, datetime

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoire_data")
DIR = os.path.join(ROOT, "conseil")
JOURNAL = os.path.join(DIR, "journal.jsonl")

BUILD = """[RÔLE : CONSTRUCTEUR]
Tu fais partie du conseil de NEXUS (écosystème d'agents : 95 pense, 96 analyse, 97 agit,
98 immunité, + mémoire). Conçois la MEILLEURE solution au sujet ci-dessous, au niveau du
top 0,1 % du domaine. Sois concret et structuré (mécanismes + garde-fous). N'édulcore pas.

SUJET : {sujet}"""

REDTEAM = """[RÔLE : RED-TEAM / AVOCAT DU DIABLE]
Tu fais partie du conseil de NEXUS. On te soumet une solution au sujet ci-dessous. Ton job :
trouver les 3 failles ou risques MAJEURS (sécurité, boucles pathologiques, biais de mesure /
Goodhart, coûts cachés) et donner un correctif minimal pour chacune. Sois critique, PAS
complaisant. Si la solution est bonne, dis aussi ce qui tient.

SUJET : {sujet}"""

def prompts(a):
    print("="*70)
    print("📐 PROMPT CONSTRUCTEUR (modèle A — ex. Gemini)\n")
    print(BUILD.format(sujet=a.sujet))
    print("\n" + "="*70)
    print("🛡️  PROMPT RED-TEAM (modèle B — DIFFÉRENT, ex. ChatGPT)\n")
    print(REDTEAM.format(sujet=a.sujet))
    print("\n" + "="*70)
    print("→ Colle chaque prompt dans un modèle DIFFÉRENT, puis 95 synthétise, puis `log`.")

def log(a):
    os.makedirs(DIR, exist_ok=True)
    rec = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "sujet": a.sujet, "constructeur": a.constructeur, "critique": a.critique,
        "decision": a.decision, "lecon": a.lecon,
    }
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"🟢 conseil journalisé : « {a.sujet} » — {a.constructeur} ⚔ {a.critique}")
    print(f"   décision : {a.decision}")

def lister(a):
    if not os.path.exists(JOURNAL):
        print("📭 Aucun conseil tenu pour l'instant."); return
    rows = [json.loads(l) for l in open(JOURNAL, encoding="utf-8") if l.strip()]
    print(f"🏛️  NEXUS — Conseils tenus : {len(rows)}\n")
    for r in rows[-10:]:
        print(f"   • {r['ts'][:16]} — « {r['sujet']} »  ({r.get('constructeur','?')} ⚔ {r.get('critique','?')})")
        print(f"     → {r.get('decision','(décision non notée)')}")

def main():
    p = argparse.ArgumentParser(description="NEXUS — conseil inter-systèmes")
    sub = p.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("prompts", help="générer les 2 prompts (constructeur + red-team)")
    pp.add_argument("sujet"); pp.set_defaults(func=prompts)
    pl = sub.add_parser("log", help="journaliser un conseil")
    pl.add_argument("sujet")
    pl.add_argument("--constructeur", required=True)
    pl.add_argument("--critique", required=True)
    pl.add_argument("--decision", required=True)
    pl.add_argument("--lecon", default=None)
    pl.set_defaults(func=log)
    ps = sub.add_parser("list", help="lister les conseils tenus"); ps.set_defaults(func=lister)
    a = p.parse_args(); a.func(a)

if __name__ == "__main__":
    main()
