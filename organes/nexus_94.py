#!/usr/bin/env python3
"""
NEXUS — Organe 94 (CONSERVATEUR : gardien d'identité)
« Un historien, un témoin, un miroir — pas un bloqueur. »

Réponse au problème central : comment NEXUS évolue sans cesser d'être NEXUS ?
94 surveille les DÉRIVES d'identité : il rappelle le noyau immuable (invariants), retrace ce qui a
CHANGÉ et ce qu'on a PERDU en échange, repère une dérive de qualité/personnalité, et pose la
question : « pourquoi avons-nous changé ? est-ce un invariant ? ». Il n'interdit pas — il éclaire,
et si un invariant est touché, il escalade au Créateur.

Différence avec 98 : 98 garde contre le DANGER externe ; 94 garde la CONTINUITÉ de soi (interne).

Usage : python3 nexus_94.py
"""
import os, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "memoire_data")
DECISIONS = os.path.join(ROOT, "decisions", "journal.jsonl")
CAPTEURS = os.path.join(ROOT, "capteurs", "journal.jsonl")
INVARIANTS_DOC = os.path.join(HERE, "canoniques", "invariants.md")

INVARIANTS = [
    "Souveraineté du Créateur (racine de confiance)",
    "Honnêteté / gardien de la réalité (activité ≠ progrès)",
    "Réversibilité (toujours pouvoir défaire)",
    "La vérité externe tranche (le résultat, pas la cohérence interne)",
    "La mémoire conserve (archiver, jamais effacer)",
    "Responsabilité tracée (porter et tracer le coût)",
]

def lire(path):
    if not os.path.exists(path):
        return []
    out = []
    for l in open(path, encoding="utf-8"):
        l = l.strip()
        if l:
            try: out.append(json.loads(l))
            except Exception: pass
    return out

def main():
    print("🪞 NEXUS-94 — CONSERVATEUR (gardien d'identité · un témoin, pas un bloqueur)")
    print("   Question : NEXUS évolue-t-il sans cesser d'être NEXUS ?\n")

    socle = "✅ présent" if os.path.exists(INVARIANTS_DOC) else "🔴 ABSENT (danger : plus de noyau)"
    print(f"   🧬 Noyau immuable (invariants.md) : {socle}")
    for i, inv in enumerate(INVARIANTS, 1):
        print(f"      {i}. {inv}")

    # Ce qui a changé récemment + ce qu'on a perdu (l'historien)
    dec = [d for d in lire(DECISIONS) if d.get("type") == "choix"]
    print("\n   📜 Ce qui a changé récemment (et ce qu'on a perdu) :")
    if dec:
        for d in dec[-4:]:
            print(f"      • « {d.get('decision','')[:60]} »  — perdu : {d.get('cout','—')}"
                  f"  · réversible : {d.get('reversible','?')}")
        # garde-fou : un changement irréversible mérite l'attention du Conservateur
        irr = [d for d in dec if d.get("reversible") == "non"]
        if irr:
            print(f"      ⚠️ {len(irr)} décision(s) IRRÉVERSIBLE(s) — à confronter aux invariants (escalade Créateur).")
    else:
        print("      (aucune décision tracée — `nexus_decision` pour commencer)")

    # Dérive de qualité/personnalité (proxy : l'impact dans le temps)
    cap = lire(CAPTEURS)
    print("\n   📉 Dérive de personnalité/qualité (proxy capteurs) :")
    fb = [e for e in cap if e.get("feedback") in ("pos", "neg")]
    if len(fb) >= 4:
        h = len(fb) // 2
        def ratio(x):
            p = sum(1 for e in x if e.get("feedback") == "pos"); return p / len(x) if x else 0
        a, b = ratio(fb[:h]), ratio(fb[h:])
        d = (b - a) * 100
        tend = "stable" if abs(d) < 10 else ("en hausse ✅" if d > 0 else "EN BAISSE ⚠️ (à examiner)")
        print(f"      satisfaction {a*100:.0f}% → {b*100:.0f}% — {tend}")
    else:
        print("      échantillon trop petit pour juger d'une dérive.")

    print("\n   ❓ La question du Conservateur : « pourquoi avons-nous changé — et est-ce un invariant ? »")
    print("      → Si non : l'évolution est libre. Si oui : escalade au Créateur (seul lui touche le noyau).")
    print("   🦅 94 n'interdit pas. Il garde la mémoire de qui NEXUS est, pour qu'en évoluant il le reste.")

if __name__ == "__main__":
    main()
