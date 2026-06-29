#!/usr/bin/env python3
"""
NEXUS — Organe 96 (ANALYSTE : « voit pour agir »)
Dans la boucle. Regarde LE MONDE (les données stockées) POUR AGIR.
Lit la mémoire vivante, calcule des métriques sur le CONTENU, identifie des
patterns, et PROPOSE des recommandations stratégiques à 95. Il propose, 95 décide.

Honnêteté statistique : sur petit échantillon, 96 DÉCLARE sa confiance.
Garde-fou : 96 ne décide pas — il éclaire. La décision reste à 95.

Usage : python3 nexus_96.py
"""
import json, urllib.request, collections

BASE = "http://127.0.0.1:8077"

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as r:
        return json.loads(r.read().decode())

def confiance(n):
    if n < 15:  return "FAIBLE", "échantillon trop petit pour des conclusions statistiques — pistes, pas vérités"
    if n < 50:  return "MOYENNE", "tendances lisibles, à confirmer par l'usage"
    return "BONNE", "volume suffisant pour des constats fiables"

def main():
    try:
        domains = get("/domains").get("domains", {})
        stats = get("/stats")
    except Exception as e:
        print(f"🔴 Mémoire injoignable : {e}. Lance nexus_boot.sh."); return

    # --- Collecte : compter les fiches par domaine et par catégorie ---
    par_domaine = collections.Counter()
    par_categorie = collections.Counter()
    total = 0
    for dom, cats in domains.items():
        for cat, fiches in cats.items():
            n = len(fiches)
            par_domaine[dom] += n
            par_categorie[cat] += n
            total += n

    niveau, note = confiance(total)

    print("🔎 NEXUS-96 — ANALYSTE (voit pour agir)")
    print(f"   Confiance : {niveau} — {note}")
    print(f"   Base observée : {total} fiches · {len(domains)} domaines\n")

    print("📊 Répartition par domaine :")
    for dom, n in par_domaine.most_common():
        print(f"   {n:>3}  {dom}")

    # --- Lecture sémantique : catégories porteuses de sens ---
    reussites = par_categorie.get("reussites", 0) + par_categorie.get("realise", 0)
    limites   = par_categorie.get("limites", 0)
    insights  = par_categorie.get("insights", 0) + par_categorie.get("lucidite", 0)
    methodes  = par_categorie.get("methodes", 0)
    archi     = par_categorie.get("architecture", 0)
    gouv      = par_categorie.get("gouvernance", 0)

    print("\n🧭 Signaux de contenu :")
    print(f"   réussites/réalisé : {reussites}   limites : {limites}   insights : {insights}")
    print(f"   méthodes : {methodes}   architecture : {archi}   gouvernance : {gouv}")

    # --- Déduction de recommandations (96 propose, 95 décide) ---
    recos = []
    if limites > reussites:
        recos.append(f"Plus de limites identifiées ({limites}) que de réussites ({reussites}) : "
                     "prioriser la RÉSOLUTION des limites avant d'ajouter du neuf.")
    else:
        recos.append(f"Réussites ({reussites}) ≥ limites ({limites}) : dynamique de réalisation saine.")
    if (archi + gouv) > (reussites + methodes):
        recos.append("Beaucoup de conception (archi/gouvernance) vs réalisation : "
                     "risque de sur-théorisation — basculer vers l'EXÉCUTION (le piège du nombrilisme).")
    plus_dev = par_domaine.most_common(1)[0][0] if par_domaine else "—"
    moins = [d for d, n in par_domaine.items() if n <= 1]
    recos.append(f"Domaine le plus développé : « {plus_dev} ». "
                 + (f"Domaines à peine explorés : {', '.join(moins)}." if moins else "Couverture équilibrée."))

    print("\n🎯 Recommandations à 95 (96 propose, 95 décide) :")
    for i, r in enumerate(recos, 1):
        print(f"   {i}. {r}")

    print(f"\n   ⚠️ Rappel : confiance {niveau}. Ces recommandations ÉCLAIRENT la décision de 95, "
          "elles ne la remplacent pas.")

if __name__ == "__main__":
    main()
