#!/usr/bin/env python3
"""
NEXUS — Critère de résolution (le mètre de la valeur)
« Trois opinions convergentes ne sont pas une mesure. » → on arrête de juger l'élégance, on MESURE.

Réponse au verrou que trois modèles (Claude, ChatGPT, Opus) ont tous pointé : la valeur n'est pas
formalisée. Cet outil la rend opérationnelle par un protocole anti-biais et anti-Goodhart (cf.
fiche_mesurer_la_valeur) qui répond à LA question : « NEXUS produit-il plus de valeur que Claude seul ? »

Le protocole (3 verrous méthodologiques) :
  1. GRILLE 1–5 figée  — qualité définie AVANT de voir les résultats (qu'est-ce qu'un 5, un 3, un 1).
  2. NOTATION EN AVEUGLE — deux réponses à la MÊME tâche, étiquettes retirées (X / Y) ; le juge note
     sans savoir laquelle est NEXUS et laquelle est le modèle seul.
  3. BASELINE FORTE     — on compare à une IA seule qui fait DE SON MIEUX (bien promptée, raisonnée),
     PAS à un one-shot bâclé. Une baseline faible = un homme de paille : tout la bat, ça ne prouve rien.

  ⚠️ PARADOXE DE MESURE (appris à la dure) : plus une tâche a une vérité objective, plus « être soigné »
     suffit à la résoudre — et moins NEXUS y est distinctif (sur semver, écart vs baseline soignée = 0).
     L'éventuel avantage de l'orchestration vit dans la zone NON mesurable (tâches ouvertes, jugement).
     Donc ce mètre prouve surtout « soigné > bâclé », pas « NEXUS > IA forte ». À garder en tête.

Grille 1–5 (générique, à spécialiser par type de tâche) :
  5 = résout complètement, juste, utilisable tel quel, anticipe au-delà du demandé
  4 = résout, juste, utilisable ; détail mineur à polir
  3 = résout l'essentiel mais lacunes notables / à reprendre
  2 = partiel ou erreurs réelles ; aide limitée
  1 = hors-sujet, faux ou inutilisable

Usage :
  python3 nexus_critere.py protocole
  python3 nexus_critere.py comparer --tache "..." --note-x 4 --note-y 3 --nexus X
  python3 nexus_critere.py bilan
"""
import os, sys, json, argparse, datetime

JOURNAL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "memoire_data", "critere", "journal.jsonl")

GRILLE = {
    5: "résout complètement, juste, utilisable tel quel, anticipe au-delà du demandé",
    4: "résout, juste, utilisable ; détail mineur à polir",
    3: "résout l'essentiel mais lacunes notables / à reprendre",
    2: "partiel ou erreurs réelles ; aide limitée",
    1: "hors-sujet, faux ou inutilisable",
}

def lire():
    out = []
    if os.path.exists(JOURNAL):
        for l in open(JOURNAL, encoding="utf-8"):
            l = l.strip()
            if l:
                try: out.append(json.loads(l))
                except Exception: pass
    return out

def confiance(n):
    if n < 5:  return "TRÈS FAIBLE", "trop peu de tâches — aucune conclusion, juste des indices"
    if n < 15: return "FAIBLE", "tendance à confirmer"
    if n < 30: return "MOYENNE", "tendance lisible"
    return "BONNE", "volume suffisant"

def protocole(_):
    print("📏 NEXUS — CRITÈRE DE RÉSOLUTION (le mètre de la valeur)\n")
    print("   Grille 1–5 (figée AVANT les résultats) :")
    for n in (5, 4, 3, 2, 1):
        print(f"      {n} = {GRILLE[n]}")
    print("\n   Notation EN AVEUGLE :")
    print("      • même tâche → 2 réponses : NEXUS et « modèle seul ».")
    print("      • on retire les étiquettes → X et Y (mélangées au hasard).")
    print("      • le juge note X et Y sur la grille SANS savoir laquelle est NEXUS.")
    print("      • on révèle après ; on répète sur ≥ 5 tâches (idéalement ≥ 15).")
    print("\n   ⚠️ Baseline = IA forte qui fait de son MIEUX (pas un one-shot bâclé = homme de paille).")
    print("   ⚠️ Paradoxe : tâche à vérité objective → « soigné » suffit → NEXUS peu distinctif.")
    print("      L'avantage éventuel de l'orchestration vit dans la zone NON mesurable (jugement, ouvert).")
    print("\n   Question tranchée : « NEXUS bat-il une IA forte ? » — par la mesure, pas l'avis.")
    print("   (anti-Goodhart : critère figé + aveugle + plusieurs tâches + baseline FORTE.)")

def comparer(g):
    if not (1 <= g.note_x <= 5 and 1 <= g.note_y <= 5):
        print("🔴 Les notes doivent être entre 1 et 5."); return
    if g.nexus not in ("X", "Y"):
        print("🔴 --nexus doit être X ou Y (quelle réponse était NEXUS)."); return
    note_nexus = g.note_x if g.nexus == "X" else g.note_y
    note_base  = g.note_y if g.nexus == "X" else g.note_x
    if note_nexus > note_base:
        verdict = f"✅ NEXUS l'emporte ({note_nexus} vs {note_base})"
    elif note_nexus < note_base:
        verdict = f"❌ modèle seul l'emporte ({note_base} vs {note_nexus})"
    else:
        verdict = f"➖ égalité ({note_nexus})"
    print(f"📏 Tâche : « {g.tache} »  →  {verdict}")
    if g.critere:
        print(f"   critère figé : {g.critere}")
    os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"),
                            "tache": g.tache, "critere": g.critere,
                            "note_nexus": note_nexus, "note_base": note_base}, ensure_ascii=False) + "\n")
    print("   🧾 tracé dans memoire_data/critere/journal.jsonl")

def bilan(_):
    ev = lire()
    n = len(ev)
    print("📏 NEXUS — BILAN : NEXUS bat-il le modèle seul ?\n")
    if n == 0:
        print("   Aucune comparaison enregistrée. Lance des `comparer` (notation en aveugle) d'abord.")
        print("   Honnêteté : sans données, la réponse est « on ne sait pas » — pas « oui ».")
        return
    mn = sum(e["note_nexus"] for e in ev) / n
    mb = sum(e["note_base"] for e in ev) / n
    wins = sum(1 for e in ev if e["note_nexus"] > e["note_base"])
    losses = sum(1 for e in ev if e["note_nexus"] < e["note_base"])
    ties = n - wins - losses
    niveau, note = confiance(n)
    print(f"   Tâches mesurées : {n}  (confiance {niveau} — {note})")
    print(f"   Moyenne NEXUS : {mn:.2f}/5   ·   modèle seul : {mb:.2f}/5   ·   écart : {mn-mb:+.2f}")
    print(f"   Victoires NEXUS : {wins}  ·  défaites : {losses}  ·  égalités : {ties}")
    print()
    if n < 5:
        print("   → VERDICT : INSUFFISANT pour conclure. Continuer à mesurer (≥ 5, idéalement ≥ 15).")
    elif mn - mb >= 0.5 and wins > losses:
        print(f"   → VERDICT : NEXUS apporte une valeur mesurable (+{mn-mb:.2f} pt, {wins} victoires/{n}).")
    elif mb - mn >= 0.5:
        print(f"   → VERDICT : NEXUS ne paie PAS son coût ici (modèle seul {mb-mn:+.2f} pt). À revoir.")
    else:
        print("   → VERDICT : pas de différence nette. Le surcoût de NEXUS n'est pas justifié sur ces tâches.")
    print("\n   ⚠️ Mesure en aveugle, critère figé : c'est une preuve, pas un avis.")

def main():
    p = argparse.ArgumentParser(description="NEXUS — critère de résolution (mètre de la valeur)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("protocole", help="afficher le protocole + la grille").set_defaults(func=protocole)
    pc = sub.add_parser("comparer", help="enregistrer une comparaison en aveugle")
    pc.add_argument("--tache", required=True)
    pc.add_argument("--note-x", dest="note_x", type=int, required=True)
    pc.add_argument("--note-y", dest="note_y", type=int, required=True)
    pc.add_argument("--nexus", required=True, help="X ou Y : quelle réponse était NEXUS (révélé après notation)")
    pc.add_argument("--critere", default=None, help="le critère figé avant de voir les résultats")
    pc.set_defaults(func=comparer)
    sub.add_parser("bilan", help="NEXUS bat-il le modèle seul ?").set_defaults(func=bilan)
    g = p.parse_args()
    g.func(g)

if __name__ == "__main__":
    main()
