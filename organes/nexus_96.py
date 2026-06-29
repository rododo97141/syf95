#!/usr/bin/env python3
"""
NEXUS — Organe 96 (ANALYSTE : « voit pour agir »)
Dans la boucle. Regarde LE MONDE (les données stockées) POUR AGIR.
Lit la mémoire vivante, calcule des métriques sur le CONTENU, identifie des
patterns, et PROPOSE des recommandations stratégiques à 95. Il propose, 95 décide.

Honnêteté statistique : sur petit échantillon, 96 DÉCLARE sa confiance.
Garde-fou : 96 ne décide pas — il éclaire. La décision reste à 95.

Usage : python3 nexus_96.py
        python3 nexus_96.py --tache "refonte paiement" --difficulte dur --enjeu haut --reversible non
        (avec --tache, 96 appelle l'ORCHESTRATEUR et propose l'intensité d'orchestration à 95)
"""
import json, urllib.request, collections, os, sys, argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
BASE = "http://127.0.0.1:8077"
CAPTEURS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoire_data", "capteurs", "journal.jsonl")
LECONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoire_data", "lecons", "journal.jsonl")

def lire_lecons():
    ev = []
    if os.path.exists(LECONS):
        for l in open(LECONS, encoding="utf-8"):
            l = l.strip()
            if l:
                try: ev.append(json.loads(l))
                except Exception: pass
    return ev

def lire_capteurs():
    ev = []
    if os.path.exists(CAPTEURS):
        for l in open(CAPTEURS, encoding="utf-8"):
            l = l.strip()
            if l:
                try: ev.append(json.loads(l))
                except Exception: pass
    return ev

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as r:
        return json.loads(r.read().decode())

def confiance(n):
    if n < 15:  return "FAIBLE", "échantillon trop petit pour des conclusions statistiques — pistes, pas vérités"
    if n < 50:  return "MOYENNE", "tendances lisibles, à confirmer par l'usage"
    return "BONNE", "volume suffisant pour des constats fiables"

def router_tache(g):
    """96 « voit pour agir » sur UNE tâche : appelle l'orchestrateur et propose l'intensité à 95.
    Indépendant de la mémoire (fonctionne même API éteinte) — c'est une recommandation de routage."""
    try:
        from nexus_orchestre import recommander, imprimer_plan
    except Exception as e:
        print(f"⚠️ orchestrateur indisponible ({e})."); return
    print("🧭 NEXUS-96 — ROUTAGE D'UNE TÂCHE (voit pour agir → propose à 95)\n")
    plan = recommander(g.tache, g.difficulte, g.enjeu, g.reversible, g.nouveaute)
    imprimer_plan(plan)
    print("\n   ↳ 96 a vu et PROPOSÉ l'intensité ci-dessus. La décision d'engager les ressources reste à 95.\n")

def main():
    p = argparse.ArgumentParser(description="NEXUS — organe 96 (analyste)")
    p.add_argument("--tache", default=None, help="si fourni : router cette tâche via l'orchestrateur")
    p.add_argument("--difficulte", choices=["facile", "moyen", "dur"], default="moyen")
    p.add_argument("--enjeu", choices=["bas", "moyen", "haut"], default="moyen")
    p.add_argument("--reversible", choices=["oui", "non"], default="oui")
    p.add_argument("--nouveaute", choices=["faible", "forte"], default="faible")
    g = p.parse_args()

    if g.tache:
        router_tache(g)   # 96 appelle l'orchestrateur (marche même si la mémoire est éteinte)

    try:
        domains = get("/domains").get("domains", {})
        stats = get("/stats")
    except Exception as e:
        if g.tache:
            return  # le routage a déjà été rendu ; pas besoin de la mémoire pour ça
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

    # --- LECTURE DES CAPTEURS : les KPIs réels de l'activité (sentir → analyser) ---
    cap = lire_capteurs()
    if cap:
        nc = len(cap)
        ok = sum(1 for e in cap if e.get("statut") == "ok")
        auto = sum(1 for e in cap if e.get("mode") == "auto")
        qv = sum(1 for e in cap if e.get("qualite") == "validee")
        qt = qv + sum(1 for e in cap if e.get("qualite") == "reprise")
        fpos = sum(1 for e in cap if e.get("feedback") == "pos")
        fneg = sum(1 for e in cap if e.get("feedback") == "neg")
        # Impact_Utilisateur dérivé du signal EXTERNE de Kily (👍/👎), JAMAIS auto-attribué (anti-Goodhart)
        fb_tot = fpos + fneg
        mimp = (fpos / fb_tot) if fb_tot else None
        print("\n📡 KPIs réels (lus dans les capteurs) :")
        print(f"   fiabilité {ok}/{nc} ({ok/nc*100:.0f}%) · autonomie {auto/nc*100:.0f}%"
              + (f" · qualité {qv/qt*100:.0f}%" if qt else "")
              + (f" · satisfaction 👍{fpos}/👎{fneg}" if (fpos or fneg) else "")
              + (f" · impact (👍/👎) {mimp:.0%}" if mimp is not None else ""))
        if auto/nc < 0.3:
            recos.append(f"Autonomie faible ({auto/nc*100:.0f}%) : NEXUS dépend encore beaucoup de Kily — "
                         "axe d'amélioration si l'objectif est plus d'indépendance.")
        if fneg > 0:
            recos.append(f"{fneg} retour(s) négatif(s) capté(s) : revenir sur ces tâches pour comprendre la cause.")
        if mimp is not None and mimp < 0.5:
            recos.append(f"Impact utilisateur moyen faible ({mimp:.0%}) : signal de GOODHART — beaucoup "
                         "d'activité, peu de valeur réelle. Recentrer sur l'impact, pas le score interne.")

        # 🪞 GARDIEN DE LA RÉALITÉ (anti-auto-illusion) : le progrès est-il RÉEL, ou juste de l'activité ?
        print("\n🪞 Gardien de la réalité (progrès réel ?) :")
        if nc >= 6:
            moitie = nc // 2
            anc, rec = cap[:moitie], cap[moitie:]
            tx = lambda lst, c, v: (sum(1 for e in lst if e.get(c) == v) / len(lst)) if lst else 0
            fa, fr = tx(anc, "statut", "ok"), tx(rec, "statut", "ok")
            d = (fr - fa) * 100
            if abs(d) < 5:
                print(f"   Fiabilité STABLE ({fa*100:.0f}% → {fr*100:.0f}%). ⚠️ On produit, mais on ne s'AMÉLIORE pas (encore). Activité ≠ progrès.")
                recos.append("Vigilance auto-illusion : l'activité est forte mais la performance ne monte pas — chercher un VRAI gain mesurable.")
            elif d > 0:
                print(f"   Fiabilité EN HAUSSE ({fa*100:.0f}% → {fr*100:.0f}%, +{d:.0f} pts). Progrès RÉEL mesuré. ✅")
            else:
                print(f"   Fiabilité EN BAISSE ({fa*100:.0f}% → {fr*100:.0f}%). Régression — à traiter en priorité.")
        else:
            print(f"   Échantillon trop petit ({nc} traces) pour PROUVER un progrès.")
            print("   Honnêteté : on ne se déclare pas « en progrès » sans preuve. (anti-auto-illusion)")

    # 🎓 LEÇONS (Reflexion) : rappeler l'expérience accumulée pour éclairer 95
    lec = lire_lecons()
    if lec:
        ic = {"succes": "✅", "echec": "❌", "methode": "🛠️"}
        print("\n🎓 Leçons à garder en tête (apprendre le POURQUOI, pas juste le quoi) :")
        for r in lec[-3:]:
            ligne = f"   {ic.get(r.get('type'),'•')} {r.get('lecon','')}"
            if r.get("pourquoi"):
                ligne += f"  — pourquoi : {r['pourquoi']}"
            print(ligne)
        nb_echec = sum(1 for r in lec if r.get("type") == "echec")
        if nb_echec:
            recos.append(f"{nb_echec} leçon(s) d'échec en mémoire : vérifier qu'on ne répète pas ces causes.")

    print("\n🎯 Recommandations à 95 (96 propose, 95 décide) :")
    for i, r in enumerate(recos, 1):
        print(f"   {i}. {r}")

    print(f"\n   ⚠️ Rappel : confiance {niveau}. Ces recommandations ÉCLAIRENT la décision de 95, "
          "elles ne la remplacent pas.")

if __name__ == "__main__":
    main()
