#!/usr/bin/env python3
"""
NEXUS — Processus de décision de l'écosystème (« on ne demande pas, on réalise et on mesure »)
Réponse directe à une correction du Créateur : un changement qui TOUCHE l'écosystème ne se décide
PAS en demandant son avis à l'utilisateur puis en obéissant. Il se décide en RÉALISANT chaque option,
en MESURANT son résultat, et en tranchant par la VALEUR du résultat. Seul le Créateur peut trancher
hors-système (override explicite) ; le reste suit le processus.

Règle des droits de décision :
  • Touche l'écosystème        → le SYSTÈME décide par la valeur mesurée (pas la préférence exprimée).
  • Ne touche pas l'écosystème → l'avis de l'utilisateur peut suffire (faible enjeu).
  • Créateur                   → peut toujours trancher hors-système, explicitement.

Garde-fou central : on NE DÉCIDE PAS tant qu'une option n'est pas RÉALISÉE et MESURÉE.
Une option « pensée mais pas faite » n'entre pas dans la balance (« aucun processus fait » = pas de verdict).

Actions possibles selon le résultat : AJOUTER · ACTIVER · DÉSACTIVER · ARCHIVER (rien ne meurt : on archive,
on réactive si le contexte change — cf. règle de survie).

Usage :
  python3 nexus_process.py decider --sujet "résumé: skill vs préférence" --touche-ecosysteme oui \\
      --option "skill:NM:oui" --option "preference:0.9:oui"
  (chaque option = label:valeur:réalisé   où valeur ∈ [0..1] ou NM=non mesuré ; réalisé ∈ oui/non)
"""
import os, sys, json, argparse, datetime

JOURNAL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "memoire_data", "process", "journal.jsonl")

def parse_option(s):
    parts = s.split(":")
    if len(parts) != 3:
        return None
    label, val, real = parts[0].strip(), parts[1].strip(), parts[2].strip().lower()
    mesuree = val.upper() != "NM"
    valeur = None
    if mesuree:
        try:
            valeur = float(val)
        except ValueError:
            return None
    return {"label": label, "valeur": valeur, "mesuree": mesuree, "realise": real == "oui"}

def decider(g):
    opts = []
    for s in g.option:
        o = parse_option(s)
        if o is None:
            print(f"⚠️ option ignorée (format label:valeur:réalisé) : « {s} »"); continue
        opts.append(o)
    if len(opts) < 2:
        print("🔴 Il faut AU MOINS deux options à comparer (le but est de réaliser les deux)."); return

    touche = (g.touche_ecosysteme == "oui")
    print("⚙️  NEXUS — PROCESSUS DE DÉCISION")
    print(f"   Sujet : « {g.sujet} »")
    print(f"   Touche l'écosystème : {'OUI → le système décide par la valeur' if touche else 'non → l’avis suffit'}\n")

    # 1) État de réalisation/mesure : on n'a pas le droit de décider sur du non-fait.
    non_faites = [o for o in opts if not o["realise"]]
    non_mesurees = [o for o in opts if o["realise"] and not o["mesuree"]]
    pretes = [o for o in opts if o["realise"] and o["mesuree"]]

    print("   État des options :")
    for o in opts:
        if not o["realise"]:
            etat = "❌ PAS RÉALISÉE (pensée, pas faite)"
        elif not o["mesuree"]:
            etat = "🟡 réalisée mais NON MESURÉE"
        else:
            etat = f"✅ réalisée + mesurée (valeur {o['valeur']:.0%})"
        print(f"      · {o['label']:14} {etat}")

    if non_faites or non_mesurees:
        manque = ", ".join(o["label"] for o in (non_faites + non_mesurees))
        print(f"\n   ⛔ PROCESSUS INCOMPLET — à finir avant de trancher : {manque}")
        print("      Règle : on ne décide pas sur une option non réalisée/non mesurée (sinon « on note, on ne fait pas »).")

    # 2) Décision par la valeur, UNIQUEMENT entre options prêtes.
    if not pretes:
        print("\n   → VERDICT : AUCUN. Réalise et mesure au moins une option, puis relance.")
        action = "AUCUN"
        gagnant = None
    else:
        pretes.sort(key=lambda o: (-o["valeur"], o["label"]))
        gagnant = pretes[0]
        print(f"\n   → Meilleure valeur mesurée : « {gagnant['label']} » ({gagnant['valeur']:.0%})")
        if len(pretes) == 1 and (non_faites or non_mesurees):
            action = "ACTIVER (provisoire)"
            print(f"   → ACTION : ACTIVER « {gagnant['label']} » MAINTENANT (seule option prouvée),")
            print(f"             et GARDER les autres en attente de mesure (rien n'est supprimé).")
        else:
            action = "ACTIVER"
            perdantes = pretes[1:]
            print(f"   → ACTION : ACTIVER « {gagnant['label']} » ; ARCHIVER {', '.join(o['label'] for o in perdantes) or '—'} "
                  "(archive réactivable, pas suppression).")

    print(f"\n   Rappel : {'le SYSTÈME a tranché par la valeur' if touche else 'décision de faible enjeu'} ; "
          "le Créateur peut passer outre explicitement.")

    os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"),
                            "sujet": g.sujet, "touche_ecosysteme": touche,
                            "options": opts, "gagnant": gagnant["label"] if gagnant else None,
                            "action": action}, ensure_ascii=False) + "\n")
    print("\n   🧾 tracé dans memoire_data/process/journal.jsonl")

def main():
    p = argparse.ArgumentParser(description="NEXUS — processus de décision (réaliser → mesurer → trancher par la valeur)")
    sub = p.add_subparsers(dest="cmd", required=True)
    pd = sub.add_parser("decider", help="trancher entre options réalisées et mesurées")
    pd.add_argument("--sujet", required=True)
    pd.add_argument("--option", action="append", required=True, help="label:valeur:réalisé (répéter)")
    pd.add_argument("--touche-ecosysteme", dest="touche_ecosysteme", choices=["oui", "non"], default="oui")
    pd.set_defaults(func=decider)
    g = p.parse_args()
    g.func(g)

if __name__ == "__main__":
    main()
