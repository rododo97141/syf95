#!/usr/bin/env python3
"""
NEXUS — Confrontation Mémoire ↔ Vérité externe (le lien qui sauve)
« Ce qui sauve un système, ce n'est pas la mémoire — c'est la confrontation entre ce qu'il CROIT
et ce que le RÉEL démontre. »

Réponse au prochain saut architectural (architecte, 23/06/2026) : renforcer le lien mémoire ↔
vérité externe. Une mémoire seule accumule des croyances fausses, des corrélations trompeuses, des
succès non reproductibles. Donc chaque croyance porte un STATUT de validité face au réel :
  ✅ TENUE      : le réel confirme
  ❌ RÉFUTÉE    : le réel contredit → réviser la croyance (la mémoire avait tort)
  ⚠️ NON TESTÉE : croyance nue, jamais confrontée (danger : « apprendre à se convaincre »)
  ⏳ PÉRIMÉE    : confirmée jadis mais ancienne → à revérifier (un succès peut cesser d'être reproductible)

Une croyance sans confrontation au réel n'est PAS une connaissance.

Usage :
  python3 nexus_confront.py confront "la compression de sortie économise 75%" --cru 0.75 --reel 0.55
  python3 nexus_confront.py list
"""
import os, sys, json, argparse, datetime

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoire_data", "confrontations")
JOURNAL = os.path.join(DIR, "journal.jsonl")

def confront(a):
    os.makedirs(DIR, exist_ok=True)
    if a.reel is None:
        statut = "⚠️ NON TESTÉE (croyance nue)"
    else:
        ecart = a.cru - a.reel
        if abs(ecart) <= 0.10:
            statut = "✅ TENUE (le réel confirme)"
        elif a.reel < a.cru - 0.10:
            statut = f"❌ RÉFUTÉE (le réel {a.reel:.0%} < cru {a.cru:.0%} — réviser)"
        else:
            statut = "✅ TENUE+ (le réel dépasse la croyance)"
    rec = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
           "croyance": a.croyance, "cru": a.cru, "reel": a.reel, "statut": statut}
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"🔬 confrontation : « {a.croyance} »")
    print(f"   cru {a.cru:.0%}" + (f" · réel {a.reel:.0%}" if a.reel is not None else " · réel ?") + f"  → {statut}")

def lister(a):
    if not os.path.exists(JOURNAL):
        print("📭 Aucune croyance confrontée. La mémoire n'est pas encore mise à l'épreuve du réel."); return
    rows = [json.loads(l) for l in open(JOURNAL, encoding="utf-8") if l.strip()]
    now = datetime.datetime.now()
    print(f"🔗 MÉMOIRE ↔ VÉRITÉ EXTERNE — {len(rows)} croyance(s) confrontée(s)\n")
    tenue = refut = nontest = 0
    for r in rows[-15:]:
        st = r.get("statut", "")
        age = (now - datetime.datetime.fromisoformat(r["ts"])).days
        vieux = "  ⏳ ancienne, à revérifier" if age >= 30 and st.startswith("✅") else ""
        print(f"   {st:34} « {r['croyance'][:50]} »{vieux}")
        if st.startswith("✅"): tenue += 1
        elif st.startswith("❌"): refut += 1
        elif "NON" in st: nontest += 1
    print(f"\n   bilan : {tenue} tenues · {refut} réfutées · {nontest} non testées.")
    print("   Règle : une croyance non confrontée au réel reste une croyance, pas une connaissance.")

def main():
    p = argparse.ArgumentParser(description="NEXUS — confrontation mémoire ↔ réel")
    sub = p.add_subparsers(dest="cmd", required=True)
    pc = sub.add_parser("confront"); pc.add_argument("croyance")
    pc.add_argument("--cru", type=float, required=True, help="ce que la mémoire CROIT (0..1)")
    pc.add_argument("--reel", type=float, default=None, help="ce que le RÉEL démontre (0..1)")
    pc.set_defaults(func=confront)
    pl = sub.add_parser("list"); pl.set_defaults(func=lister)
    a = p.parse_args(); a.func(a)

if __name__ == "__main__":
    main()
