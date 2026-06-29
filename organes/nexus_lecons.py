#!/usr/bin/env python3
"""
NEXUS — Journal de leçons (Reflexion / experience store)
« Retenir ce qui marche et ce qui rate, pour ne pas répéter. »

Pattern d'auto-amélioration (Reflexion/ExpeL) : après une tâche, on garde UNE leçon courte
(succès → méthode qui a marché ; échec → cause + correctif). 96 les rappelle (recall) pour
éclairer 95. Append-only, robuste (pas de dépendance à l'API mémoire), comme les capteurs.

Usage :
  python3 nexus_lecons.py add "get_page_text récupère la légende quand la vidéo gèle" \
        --type methode --contexte "analyse vidéos TikTok"
  python3 nexus_lecons.py list
"""
import os, sys, json, argparse, datetime

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoire_data")
DIR = os.path.join(ROOT, "lecons")
JOURNAL = os.path.join(DIR, "journal.jsonl")
TRANSFERT = os.path.join(DIR, "transfert.jsonl")  # preuve de CROISSANCE : une leçon réappliquée à du NEUF
TYPES = ("succes", "echec", "methode")
RESULTATS = ("mieux", "pareil", "pire")
ICON = {"succes": "✅", "echec": "❌", "methode": "🛠️"}

def add(a):
    os.makedirs(DIR, exist_ok=True)
    rec = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "type": a.type, "contexte": a.contexte, "lecon": a.lecon, "correctif": a.correctif,
        "pourquoi": a.pourquoi,   # la CAUSE : pourquoi c'est bon ou mauvais (apprendre, pas juste retenir)
    }
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"{ICON.get(a.type,'•')} leçon retenue [{a.type}] : {a.lecon}")

def lire():
    if not os.path.exists(JOURNAL):
        return []
    return [json.loads(l) for l in open(JOURNAL, encoding="utf-8") if l.strip()]

def appliquer(a):
    """Journalise le TRANSFERT : une leçon passée réutilisée sur une tâche NOUVELLE.
    C'est la preuve « grandir » vs « accumuler » — une leçon jamais réappliquée = poids mort."""
    os.makedirs(DIR, exist_ok=True)
    rec = {"ts": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
           "lecon_cle": a.lecon_cle, "tache_nouvelle": a.tache, "resultat": a.resultat}
    with open(TRANSFERT, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"🔄 transfert capté : « {a.lecon_cle} » réappliquée sur « {a.tache} » → {a.resultat}")

def lister(a):
    rows = lire()
    if not rows:
        print("📭 Aucune leçon retenue pour l'instant."); return
    print(f"🎓 NEXUS — Leçons retenues : {len(rows)}\n")
    for r in rows[-15:]:
        c = f" ({r['contexte']})" if r.get("contexte") else ""
        why = f"\n      pourquoi : {r['pourquoi']}" if r.get("pourquoi") else ""
        fix = f"\n      → correctif : {r['correctif']}" if r.get("correctif") else ""
        print(f"   {ICON.get(r.get('type'),'•')} {r['lecon']}{c}{why}{fix}")

def main():
    p = argparse.ArgumentParser(description="NEXUS — journal de leçons (Reflexion)")
    sub = p.add_subparsers(dest="cmd", required=True)
    pa = sub.add_parser("add", help="retenir une leçon")
    pa.add_argument("lecon")
    pa.add_argument("--type", choices=TYPES, default="methode")
    pa.add_argument("--contexte", default=None)
    pa.add_argument("--correctif", default=None)
    pa.add_argument("--pourquoi", default=None, help="la cause : POURQUOI c'est bon ou mauvais")
    pa.set_defaults(func=add)
    pl = sub.add_parser("list", help="lister les leçons"); pl.set_defaults(func=lister)
    pt = sub.add_parser("applique", help="journaliser le transfert d'une leçon à une tâche nouvelle")
    pt.add_argument("lecon_cle"); pt.add_argument("--tache", required=True)
    pt.add_argument("--resultat", choices=RESULTATS, default="mieux")
    pt.set_defaults(func=appliquer)
    a = p.parse_args(); a.func(a)

if __name__ == "__main__":
    main()
