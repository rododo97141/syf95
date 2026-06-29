#!/usr/bin/env python3
"""
NEXUS — Registre des décisions (porter le coût, mais le PROUVER)
« Garder le moment du choix, pas seulement le résultat d'après. »

Réponse à l'exigence : la responsabilité doit être MESURABLE, TRACÉE, RÉVERSIBLE quand c'est
possible — sinon le discours est noble mais pas vérifiable. Et garde-fou de l'architecte :
DIFFICILE ≠ JUSTE. Une décision lourde n'est pas bonne parce qu'elle est lourde ; elle est jugée
sur son RÉSULTAT (la vérité externe), pas sur le poids ressenti.

Chaque décision importante garde : ce qui a été choisi · ce qui a été REJETÉ · le COÛT / ce qui a
été sacrifié · les HYPOTHÈSES initiales · réversible ou non. Puis, après action : un BILAN qui dit
si c'était juste — sur le résultat.

Usage :
  python3 nexus_decision.py log "ne pas merger #26 moi-même" \
     --rejete "auto-merger sur main" --cout "paraître moins '100% autonome'" \
     --hypotheses "un acte irréversible sur le repo du créateur lui revient" --reversible oui
  python3 nexus_decision.py bilan "ne pas merger #26 moi-même" --juste oui \
     --resultat "rien cassé, confiance préservée" --lecon "réversibilité > vitesse"
  python3 nexus_decision.py list
"""
import os, sys, json, argparse, datetime

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoire_data", "decisions")
JOURNAL = os.path.join(DIR, "journal.jsonl")

def _add(rec):
    os.makedirs(DIR, exist_ok=True)
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def log(a):
    _add({"ts": datetime.datetime.now().isoformat(timespec="seconds"), "type": "choix",
          "decision": a.decision, "rejete": a.rejete, "cout": a.cout,
          "hypotheses": a.hypotheses, "reversible": a.reversible,
          "prediction": a.prediction, "a_change": a.a_change, "orchestre": a.orchestre})
    print(f"📝 choix enregistré : « {a.decision} »")
    print(f"   rejeté : {a.rejete or '—'} · coût : {a.cout or '—'} · réversible : {a.reversible}")
    if a.a_change:   print(f"   a changé ma décision ? {a.a_change}   (colonne discipline)")
    if a.orchestre:  print(f"   orchestré a battu l'instinct ? {a.orchestre}   (colonne « battre une IA »)")
    if a.prediction: print(f"   🔮 prédiction (le pourquoi qui PARIE sur le cas suivant) : {a.prediction}")
    print("   → au prochain cas : `nexus_decision.py verifie \"…\" --tenu oui|non`. "
          "Tenu = mécanisme ; pas tenu = narration.")

def bilan(a):
    _add({"ts": datetime.datetime.now().isoformat(timespec="seconds"), "type": "bilan",
          "decision": a.decision, "juste": a.juste, "resultat": a.resultat, "lecon": a.lecon})
    verdict = "JUSTE" if a.juste == "oui" else ("PAS JUSTE" if a.juste == "non" else "INCERTAIN")
    print(f"⚖️  bilan après action : « {a.decision} » → {verdict}")
    print(f"   jugé sur le RÉSULTAT : {a.resultat or '—'}  (pas sur le poids ressenti)")
    if a.juste == "non":
        print("   ✓ honnêteté : une décision difficile peut être MAUVAISE — on l'assume, on apprend.")

def verifie(a):
    _add({"ts": datetime.datetime.now().isoformat(timespec="seconds"), "type": "verif",
          "decision": a.decision, "tenu": a.tenu, "cas": a.cas})
    if a.tenu == "oui":
        print(f"🔑 « {a.decision} » → la prédiction A TENU au cas suivant ({a.cas or '—'}).")
        print("   = MÉCANISME : ce pourquoi prédit, donc il vaut quelque chose. Première mesure du serrurier.")
    elif a.tenu == "non":
        print(f"🌫️ « {a.decision} » → la prédiction N'A PAS tenu ({a.cas or '—'}).")
        print("   = NARRATION : jolie histoire sans pouvoir prédictif. On révise le pourquoi (et c'est un VRAI gain).")
    else:
        print(f"… « {a.decision} » → cas suivant pas encore arrivé. En attente.")

def lister(a):
    if not os.path.exists(JOURNAL):
        print("📭 Aucune décision enregistrée."); return
    rows = [json.loads(l) for l in open(JOURNAL, encoding="utf-8") if l.strip()]
    choix = [r for r in rows if r.get("type") == "choix"]
    bilans = {r["decision"]: r for r in rows if r.get("type") == "bilan"}
    print(f"🗂️  REGISTRE DES DÉCISIONS — {len(choix)} choix\n")
    for r in choix:
        print(f"   • « {r['decision']} »  (réversible : {r.get('reversible','?')})")
        print(f"     rejeté : {r.get('rejete','—')} · coût : {r.get('cout','—')}")
        if r.get("hypotheses"): print(f"     hypothèses : {r['hypotheses']}")
        b = bilans.get(r["decision"])
        if b:
            v = "JUSTE" if b.get("juste") == "oui" else ("PAS JUSTE" if b.get("juste") == "non" else "?")
            print(f"     → bilan : {v} (sur le résultat : {b.get('resultat','—')})")
        else:
            print("     → bilan : en attente (à juger sur le RÉSULTAT, pas la difficulté)")
    print("\n   Règle : difficile ≠ juste. Le poids d'un choix ne le rend pas bon — seul le résultat le dit.")

def main():
    p = argparse.ArgumentParser(description="NEXUS — registre des décisions (responsabilité tracée)")
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("log"); pl.add_argument("decision")
    pl.add_argument("--rejete", default=None); pl.add_argument("--cout", default=None)
    pl.add_argument("--hypotheses", default=None)
    pl.add_argument("--reversible", choices=("oui", "non", "partiel"), default="partiel")
    pl.add_argument("--prediction", default=None, help="le pourquoi qui PARIE sur le cas suivant (falsifiable)")
    pl.add_argument("--a-change", dest="a_change", choices=("oui", "non"), default=None, help="a changé ma décision ?")
    pl.add_argument("--orchestre", choices=("oui", "non", "na"), default=None, help="l'orchestré a-t-il battu l'instinct ?")
    pl.set_defaults(func=log)
    pv = sub.add_parser("verifie"); pv.add_argument("decision")
    pv.add_argument("--tenu", choices=("oui", "non", "attente"), default="attente")
    pv.add_argument("--cas", default=None, help="le cas suivant qui a testé la prédiction")
    pv.set_defaults(func=verifie)
    pb = sub.add_parser("bilan"); pb.add_argument("decision")
    pb.add_argument("--juste", choices=("oui", "non", "incertain"), default="incertain")
    pb.add_argument("--resultat", default=None); pb.add_argument("--lecon", default=None)
    pb.set_defaults(func=bilan)
    ps = sub.add_parser("list"); ps.set_defaults(func=lister)
    a = p.parse_args(); a.func(a)

if __name__ == "__main__":
    main()
