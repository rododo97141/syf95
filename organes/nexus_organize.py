#!/usr/bin/env python3
"""
NEXUS — Organisateur (range et journalise l'état du système)
« Organiser en générant des données. »

Ce n'est PAS un gestionnaire abstrait : c'est un outil concret qui (1) inventorie l'état,
(2) orchestre la maintenance de la mémoire (un seul point d'entrée), et (3) JOURNALISE
chaque passe — produisant ainsi des données d'organisation que 96 et 98 pourront lire.

Il EXÉCUTE et TRACE ; il ne décide pas la priorité (ça, c'est 95).

Usage :
  python3 nexus_organize.py            # inventaire + journal (dry-run maintenance)
  python3 nexus_organize.py --apply    # + lance la maintenance mémoire (reconcile)
"""
import os, sys, json, glob, subprocess, datetime, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "memoire_data")
JDIR = os.path.join(ROOT, "organisation")
JOURNAL = os.path.join(JDIR, "journal.jsonl")
BASE = "http://127.0.0.1:8077"

def api(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception:
        return {}

def compter_fiches_fs():
    """Repli : compter les fiches structurées sur le DISQUE quand l'API mémoire dort.
    Évite un faux « 0 fiche » (et un faux « -76 ») qui tromperait 98 (Danger Theory :
    réagir au dommage réel, pas à un artefact de mesure)."""
    base = os.path.join(ROOT, "structure")
    if not os.path.isdir(base):
        return 0
    n = 0
    for _d, _s, files in os.walk(base):
        n += sum(1 for f in files if f.endswith((".json", ".md")))
    return n

def derniere_passe():
    if not os.path.exists(JOURNAL):
        return None
    last = None
    for l in open(JOURNAL, encoding="utf-8"):
        l = l.strip()
        if l:
            try: last = json.loads(l)
            except Exception: pass
    return last

def main():
    apply = "--apply" in sys.argv
    os.makedirs(JDIR, exist_ok=True)

    # --- 1. INVENTAIRE ---
    scripts = sorted(os.path.basename(p) for p in glob.glob(os.path.join(HERE, "nexus_*.py")) + glob.glob(os.path.join(HERE, "*.sh")))
    docs = len(glob.glob(os.path.join(HERE, "*.md"))) + len(glob.glob(os.path.join(HERE, "canoniques", "*.md")))
    stats = api("/stats")
    # API si dispo et > 0, sinon repli disque (évite le faux « 0 » quand l'API dort ou pointe ailleurs)
    fiches = stats.get("structure_fiches") or compter_fiches_fs()
    # backlog : notes capturées avec le tag "backlog"
    bk = api("/recall?query=backlog&scope=brut").get("results", [])

    print("🗂️  NEXUS — ORGANISATEUR")
    print(f"   {len(scripts)} scripts · {docs} documents · {fiches} fiches mémoire · {len(bk)} note(s) backlog\n")
    print("   Scripts de l'écosystème :")
    for s in scripts:
        print(f"     · {s}")

    # --- 2. MAINTENANCE (orchestrée — UN SEUL point d'entrée pour toute la maintenance) ---
    # nexus_organize est le seul outil que l'utilisateur lance ; consolidate et reconcile
    # sont des utilitaires internes, appelés ici. (Simplification d'interface : 1 commande.)
    actions = []
    con = os.path.join(HERE, "nexus_consolidate.py")
    if os.path.exists(con):
        out = subprocess.run(["python3", con], capture_output=True, text=True).stdout.strip().splitlines()
        red = next((l for l in out if "paire" in l or "Aucune" in l), "")
        actions.append(f"consolidate (dry-run) : {red.strip()}")
        print(f"\n   🔎 Redondance (consolidate) : {red.strip() or 'rien à signaler'}")
    rec = os.path.join(HERE, "nexus_reconcile.py")
    if os.path.exists(rec):
        cmd = ["python3", rec] + (["--apply"] if apply else [])
        out = subprocess.run(cmd, capture_output=True, text=True).stdout.strip().splitlines()
        resume = out[-1] if out else ""
        actions.append(f"reconcile ({'apply' if apply else 'dry-run'}) : {resume}")
        print(f"   🧹 Nettoyage en_attente (reconcile) : {resume}")

    # --- 3. CHANGEMENTS depuis la dernière passe ---
    prev = derniere_passe()
    if prev:
        df = fiches - prev.get("fiches", fiches)
        ds = len(scripts) - prev.get("n_scripts", len(scripts))
        print(f"\n   📈 Depuis la dernière passe ({prev.get('ts','?')[:16]}) : "
              f"{'+' if df>=0 else ''}{df} fiche(s), {'+' if ds>=0 else ''}{ds} script(s)")
    else:
        print("\n   📈 Première passe d'organisation (pas d'historique).")

    # --- 4. JOURNAL (les données d'organisation) ---
    entry = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "n_scripts": len(scripts), "scripts": scripts,
        "docs": docs, "fiches": fiches, "backlog_notes": len(bk),
        "actions": actions,
    }
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"\n   📓 Journalisé dans organisation/journal.jsonl (matière pour 96 et 98).")
    print("   ✅ Organisation à jour." + ("" if apply else "  (relancer avec --apply pour appliquer la maintenance)"))

if __name__ == "__main__":
    main()
