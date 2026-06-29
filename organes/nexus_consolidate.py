#!/usr/bin/env python3
"""
[Utilitaire interne — orchestré par nexus_organize. Ne pas lancer à la main.]
NEXUS Consolidate — prototype de la "boucle manquante" de la memoire vivante.
Inspire du "Dreaming" (Anthropic) et des approches PREMem / TiM : reperer les
fiches semantiquement redondantes et PROPOSER leur fusion.

Garde-fou de securite : DRY-RUN par defaut. Ne supprime, ne modifie, ne fusionne
RIEN. Il se contente de lister les candidats a consolidation pour decision humaine.

Usage : python3 nexus_consolidate.py
"""
import json, urllib.request, itertools, re

BASE = "http://127.0.0.1:8077"
SEUIL = 0.50  # seuil relevé (cohérent avec 98) : ne signaler que les VRAIS doublons

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as r:
        return json.loads(r.read().decode())

def mots(txt):
    txt = (txt or "").lower()
    return {w for w in re.findall(r"[a-zà-ÿ0-9]+", txt) if len(w) > 3}

def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)

def main():
    try:
        domains = get("/domains").get("domains", {})
    except Exception as e:
        print(f"🔴 API injoignable : {e}. Lance d'abord nexus_boot.sh.")
        return

    candidats = []
    total = 0
    for domaine, cats in domains.items():
        for cat in cats:
            res = get(f"/recall?domain={domaine}&category={cat}").get("results", [])
            total += len(res)
            # signature = titre + extrait, reduit en sac de mots
            fiches = [(f.get("file", "?"), mots(f.get("file", "") + " " + f.get("excerpt", ""))) for f in res]
            for (fa, ma), (fb, mb) in itertools.combinations(fiches, 2):
                s = jaccard(ma, mb)
                if s >= SEUIL:
                    candidats.append((round(s, 2), domaine, cat, fa, fb))

    print(f"📊 {total} fiches analysees sur {sum(len(c) for c in domains.values())} categories.")
    if not candidats:
        print("✅ Aucune redondance au-dessus du seuil. Memoire saine, rien a consolider.")
        return
    print(f"🔎 {len(candidats)} paire(s) candidate(s) a la consolidation (DRY-RUN, rien n'est touche) :\n")
    for s, d, c, fa, fb in sorted(candidats, reverse=True):
        print(f"  • [{s:.0%}] {d} › {c}")
        print(f"      ↳ {fa}")
        print(f"      ↳ {fb}")
    print("\n🛡️  Aucune fusion appliquee. A toi de valider les rapprochements pertinents.")

if __name__ == "__main__":
    main()
