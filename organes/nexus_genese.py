#!/usr/bin/env python3
"""
NEXUS — Organogenèse gouvernée (usage CADRÉ de skill-creator)
« Le système peut faire grandir ses propres organes — mais c'est l'acte le plus risqué de tous,
  donc le plus encadré. »

Pourquoi cet outil. Les organes de NEXUS SONT des skills (95, 96, 97, 98, 92, mémoire…). skill-creator
sait créer/améliorer/MESURER des skills (eval avec variance, split train/test 60/40 anti-surapprentissage,
A/B en aveugle, optimisation de description, packaging). C'est donc le bras concret de la 4ᵉ couche —
ÉVOLUTION (« comment je deviens meilleur ? ») : l'organogenèse, NEXUS qui fait grandir/réparer ses organes.

Mais un système qui se modifie lui-même = le risque d'auto-amélioration récursive que notre recherche
sécurité a déjà pointé (corrigibilité, réversibilité, racine de confiance, régression du vérificateur).
Donc skill-creator ne « vit » pas sous un seul organe : c'est une CAPACITÉ MÉTA, orchestrée, et PASSÉE
PAR CE PORTAIL qui impose les invariants à l'acte le plus dangereux du système.

Les 5 verrous (l'invariant rendu exécutable) :
  1. MANDAT souverain     — créé/modifié seulement sur mandat du Créateur (ou de 95). Sinon REFUS.
  2. RÉVERSIBILITÉ        — snapshot de l'organe AVANT (cp -r) ; rollback possible. Sinon REFUS.
  3. VÉRITÉ EXTERNE       — doit battre la baseline sur le test HELD-OUT (pas le train). Anti-Goodhart/overfit.
  4. IMPACT RÉEL          — eval réussie MAIS 👍 du Créateur faible → À RETESTER (activité ≠ valeur).
  5. INSTALLATION HUMAINE — NEXUS propose + package ; le Créateur INSTALLE (la gâchette reste humaine).

Usage :
  python3 nexus_genese.py propose --organe "nexus-resumeur" --type creer --raison "..." --mandat createur
  python3 nexus_genese.py valider --organe "nexus-resumeur" --mandat createur --snapshot oui \\
                                  --bat-baseline oui --impact-reel 0.8 --installe-par createur
  python3 nexus_genese.py list
"""
import os, sys, json, argparse, datetime

JOURNAL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "memoire_data", "genese", "journal.jsonl")
SEUIL_IMPACT = 0.5
MANDATS_VALIDES = {"createur", "créateur", "95"}

def _journal(rec):
    os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
    rec["ts"] = datetime.datetime.now().isoformat(timespec="seconds")
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def lire():
    out = []
    if os.path.exists(JOURNAL):
        for l in open(JOURNAL, encoding="utf-8"):
            l = l.strip()
            if l:
                try: out.append(json.loads(l))
                except Exception: pass
    return out

def propose(g):
    print(f"🌱 NEXUS — ORGANOGENÈSE : proposition « {g.organe} » ({g.type})")
    print(f"   Raison : {g.raison or '—'}")
    print(f"   Mandat déclaré : {g.mandat or '— (manquant)'}\n")
    print("   Portail à franchir AVANT installation (les 5 verrous) :")
    print("     1. MANDAT souverain     — Créateur ou 95")
    print("     2. RÉVERSIBILITÉ        — snapshot de l'organe avant (rollback possible)")
    print("     3. VÉRITÉ EXTERNE       — bat la baseline sur le test HELD-OUT (skill-creator: eval + variance)")
    print("     4. IMPACT RÉEL          — 👍 du Créateur (sinon eval-OK mais sans valeur = Goodhart)")
    print("     5. INSTALLATION HUMAINE — NEXUS package, le Créateur installe")
    print("\n   → Étape suivante : faire tourner skill-creator (draft → eval → A/B → améliorer),")
    print("     puis `nexus_genese.py valider …` avec les preuves.")
    _journal({"phase": "propose", "organe": g.organe, "type": g.type,
              "raison": g.raison, "mandat": g.mandat})

def valider(g):
    mandat = (g.mandat or "").strip().lower()
    verrous = []  # (ok, libellé)
    v1 = mandat in MANDATS_VALIDES
    verrous.append((v1, f"MANDAT souverain ({g.mandat or 'manquant'})"))
    v2 = (g.snapshot == "oui")
    verrous.append((v2, "RÉVERSIBILITÉ (snapshot avant)"))
    v3 = (g.bat_baseline == "oui")
    verrous.append((v3, "VÉRITÉ EXTERNE (bat la baseline sur held-out)"))
    v4 = (g.impact_reel is not None and g.impact_reel >= SEUIL_IMPACT)
    verrous.append((v4, f"IMPACT RÉEL ≥ {SEUIL_IMPACT:.0%} "
                        f"({g.impact_reel:.0%} mesuré)" if g.impact_reel is not None else "IMPACT RÉEL (non mesuré)"))
    v5 = ((g.installe_par or "").strip().lower() in MANDATS_VALIDES)
    verrous.append((v5, f"INSTALLATION HUMAINE ({g.installe_par or 'non précisé'})"))

    # Verdict : refus dur si un verrou DE SÉCURITÉ saute (mandat/réversibilité/vérité externe/installation).
    # « à retester » seulement si tout est sûr mais l'impact réel manque (eval OK, valeur non prouvée).
    if not v1:
        verdict, motif = "⛔ REFUSER", "pas de mandat souverain (souveraineté du Créateur)"
    elif not v2:
        verdict, motif = "⛔ REFUSER", "pas réversible (snapshot manquant) — on n'installe jamais sans rollback"
    elif not v3:
        verdict, motif = "⛔ REFUSER", "ne bat pas la baseline sur le test held-out (pas de gain prouvé / risque de surapprentissage)"
    elif not v5:
        verdict, motif = "⛔ REFUSER", "installation non humaine — la gâchette reste au Créateur"
    elif not v4:
        verdict, motif = "🟡 À RETESTER", "eval réussie mais impact réel faible : activité ≠ valeur (Goodhart) — mesurer la valeur réelle"
    else:
        verdict, motif = "✅ ACCEPTER", "les 5 verrous sont francs — NEXUS package, le Créateur installe"

    print(f"🌱 NEXUS — ORGANOGENÈSE : validation « {g.organe} »\n")
    for ok, lib in verrous:
        print(f"   {'✅' if ok else '❌'} {lib}")
    print(f"\n   → VERDICT : {verdict} — {motif}")
    print("   (Rappel : 96 propose/mesure, 92 perfectionne, 97 exécute, 98 garde, 95 décide ;")
    print("    l'installation d'un organe est l'acte le plus risqué → elle reste HUMAINE.)")
    _journal({"phase": "valider", "organe": g.organe, "verdict": verdict.split()[-1],
              "mandat": g.mandat, "snapshot": g.snapshot, "bat_baseline": g.bat_baseline,
              "impact_reel": g.impact_reel, "installe_par": g.installe_par})

def lister(g):
    ev = lire()
    if not ev:
        print("📭 Aucune organogenèse enregistrée."); return
    print(f"📒 NEXUS — REGISTRE D'ORGANOGENÈSE ({len(ev)} entrées)\n")
    for e in ev:
        if e.get("phase") == "valider":
            print(f"   [{e['ts'][:16]}] {e['organe']:22} → {e.get('verdict','?')}")
        else:
            print(f"   [{e['ts'][:16]}] {e['organe']:22} · proposé ({e.get('type','?')})")

def main():
    p = argparse.ArgumentParser(description="NEXUS — organogenèse gouvernée (usage cadré de skill-creator)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("propose", help="enregistrer une proposition d'organe + afficher le portail")
    pp.add_argument("--organe", required=True)
    pp.add_argument("--type", choices=["creer", "ameliorer"], default="creer")
    pp.add_argument("--raison", default=None)
    pp.add_argument("--mandat", default=None)
    pp.set_defaults(func=propose)

    pv = sub.add_parser("valider", help="passer les 5 verrous et rendre un verdict")
    pv.add_argument("--organe", required=True)
    pv.add_argument("--mandat", default=None)
    pv.add_argument("--snapshot", choices=["oui", "non"], default="non")
    pv.add_argument("--bat-baseline", dest="bat_baseline", choices=["oui", "non"], default="non")
    pv.add_argument("--impact-reel", dest="impact_reel", type=float, default=None)
    pv.add_argument("--installe-par", dest="installe_par", default=None)
    pv.set_defaults(func=valider)

    pl = sub.add_parser("list", help="afficher le registre")
    pl.set_defaults(func=lister)

    g = p.parse_args()
    g.func(g)

if __name__ == "__main__":
    main()
