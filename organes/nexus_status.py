#!/usr/bin/env python3
"""
NEXUS — Status (le tableau de bord en UNE commande)
« Un seul code pour voir tout l'organisme. »

Au lieu de lancer 3 scripts (sense + 96 + 98), un seul point d'entrée fluide :
   python3 nexus_status.py
Il orchestre : capteurs (sentir) → 96 (analyser + gardien de la réalité) → 98 (veiller).
C'est l'application du principe « codes/commandes fluides » : un mot, tout l'état.
"""
import os, subprocess, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

def api_up():
    try:
        urllib.request.urlopen("http://127.0.0.1:8077/stats", timeout=3); return True
    except Exception:
        return False

def run(script, args=None, grep_from=None):
    out = subprocess.run(["python3", os.path.join(HERE, script)] + (args or []),
                         capture_output=True, text=True).stdout
    lines = out.strip().splitlines()
    if grep_from:
        keep, started = [], False
        for l in lines:
            if grep_from in l: started = True
            if started: keep.append(l)
        return keep
    return lines

def main():
    # 0. S'assurer que la mémoire vivante tourne (booter SEULEMENT si l'API ne répond pas)
    if not api_up():
        subprocess.run(["bash", os.path.join(HERE, "nexus_boot.sh")], capture_output=True, text=True)

    print("╔════════════════════════════════════════╗")
    print("║   NEXUS — TABLEAU DE BORD (1 commande)  ║")
    print("╚════════════════════════════════════════╝")

    print("\n🫀 SENTIR — les capteurs")
    for l in run("nexus_sense.py", ["stats"])[2:8]:
        print("  " + l.strip())

    print("\n🔎 ANALYSER — 96 (KPIs + gardien de la réalité)")
    for l in run("nexus_96.py", grep_from="📡 KPIs"):
        if "🎯 Recommand" in l: break
        print("  " + l.strip())

    print("\n🛡️  VEILLER — 98 (santé)")
    for l in run("nexus_98.py", grep_from="VERDICT"):
        print("  " + l.strip())

    print("\n✅ État complet de NEXUS en un coup d'œil.")

if __name__ == "__main__":
    main()
