#!/usr/bin/env python3
"""
NEXUS — Orchestrateur de ressources (Fugu adapté · piloté par 96)
« Une seule tâche, le bon spécialiste pour chaque morceau, vérifié par un autre, puis recousu. »

Origine : Sakana « Fugu » — un modèle qui décompose une tâche dure, route chaque sous-partie vers
le meilleur spécialiste (y compris des instances de lui-même), fait VÉRIFIER, puis SYNTHÉTISE.
Ce qu'on garde (la méthode), ce qu'on jette (le marketing « bat tout le monde » + les 30 min d'attente).

Adaptation NEXUS, sous l'organe 96 (« voir pour agir ») :
  96 LIT le profil de la tâche → RECOMMANDE la bonne intensité d'orchestration et les ressources.
  96 PROPOSE, il ne décide pas : c'est 95 qui tranche (invariant). Le vérificateur est TOUJOURS
  une ressource DIFFÉRENTE du constructeur (un modèle ne voit pas ses propres angles morts).
  Le coût est BORNÉ : on ne paie l'orchestration que quand l'enjeu la justifie (anti « 30 min »).

3 intensités (la moins chère qui suffit gagne — satisficing) :
  🟢 SOLO     : tâche facile + réversible + enjeu bas → 1 ressource, zéro surcoût d'orchestration.
  🟡 DUO      : tâche moyenne (ou dure mais réversible/bas enjeu) → constructeur + vérificateur croisé.
  🔴 CONSEIL  : tâche dure ET (enjeu haut OU non-réversible OU nouveauté forte)
                → décomposer, router chaque morceau vers un spécialiste, vérif croisée, synthèse.

Usage :
  python3 nexus_orchestre.py --tache "refacto paiement" --difficulte dur --enjeu haut --reversible non
  python3 nexus_orchestre.py --tache "ajouter l'auth" --difficulte moyen --prompts   # génère les prompts
"""
import argparse, json, os, sys, datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
JOURNAL = os.path.join(SCRIPT_DIR, "memoire_data", "orchestre", "journal.jsonl")

POOL_DEFAUT = {
    "Claude":  "code, raisonnement, rédaction",
    "Codex":   "revue de code, repérage de bugs",
    "Kimi":    "contexte très long",
    "Gemini":  "vision, recherche, second regard",
    "Mistral": "français, rapidité",
}

CHARGE = {
    "difficulte": {"facile": 0, "moyen": 1, "dur": 2},
    "enjeu":      {"bas": 0, "moyen": 1, "haut": 2},
    "nouveaute":  {"faible": 0, "forte": 1},
}

# Hypothèses CONFIGURABLES (tokens ≈ entrée+sortie d'une « passe » de travail, selon la difficulté).
# Ce sont des ordres de grandeur pour COMPARER les intensités entre elles — PAS une facture exacte.
TOKENS_PASSE = {"facile": 1500, "moyen": 4000, "dur": 10000}

def estimer_cout(plan, cout_1k=None):
    """Estime le coût d'une intensité, en séparant PRODUCTION et ORCHESTRATION (comme la console Sakana).
    Honnête : ordres de grandeur depuis des hypothèses configurables (TOKENS_PASSE), pas une facture."""
    base = TOKENS_PASSE[plan["profil"]["difficulte"]]
    tier = plan["tier"]; n = len(plan["ressources"])
    if tier == "SOLO":
        prod_passes, orch_passes = 1, 0                 # 1 passe, aucune coordination
    elif tier == "DUO":
        prod_passes, orch_passes = 4, 1                 # plan+impl+relire+vérif ; 1 de coordination croisée
    else:  # CONSEIL
        prod_passes, orch_passes = n + 1, 2             # n spécialistes + synthèse ; décompose + vérif croisée
    prod = prod_passes * base
    orch = int(orch_passes * base * 0.5)                # la coordination = passes plus courtes que le travail
    total = prod + orch
    out = {"base": base, "prod_passes": prod_passes, "orch_passes": orch_passes,
           "prod": prod, "orch": orch, "total": total,
           "ratio": (orch / total) if total else 0.0}
    if cout_1k is not None:
        out["argent"] = total / 1000 * cout_1k
    return out

def parse_pool(s):
    pool = {}
    for bloc in s.split(","):
        bloc = bloc.strip()
        if not bloc:
            continue
        if bloc.count(":") != 1:
            print(f"⚠️ ressource ignorée (format ressource:force) : « {bloc} »"); continue
        nom, force = bloc.split(":")
        pool[nom.strip()] = force.strip()
    return pool

def choisir_constructeur(pool, difficulte, nouveaute):
    """Heuristique transparente : qui correspond le mieux au besoin dominant."""
    noms = list(pool)
    if not noms:
        return None
    if nouveaute == "forte":
        cle = "raison"          # explorer du neuf : raisonnement
    elif difficulte == "dur":
        cle = "code"            # tâche dure : capacité technique
    else:
        cle = "rapid"           # tâche simple : rapidité
    for n in noms:
        if cle in pool[n].lower():
            return n
    return noms[0]              # défaut déterministe

def choisir_verificateur(pool, constructeur):
    """Vérificateur = ressource DIFFÉRENTE (angles morts). Préfère une force « revue/regard »."""
    autres = [n for n in pool if n != constructeur]
    if not autres:
        return None
    for n in autres:
        f = pool[n].lower()
        if "revue" in f or "regard" in f or "bug" in f:
            return n
    return sorted(autres)[0]    # déterministe

def recommander(tache, difficulte="moyen", enjeu="moyen", reversible="oui",
                nouveaute="faible", pool=None, budget=3):
    """Cœur réutilisable : 96 lit le profil → renvoie un plan d'orchestration (dict). Aucune impression."""
    pool = pool or dict(POOL_DEFAUT)
    diff = CHARGE["difficulte"][difficulte]
    enj  = CHARGE["enjeu"][enjeu]
    nouv = CHARGE["nouveaute"][nouveaute]
    irreversible = (reversible == "non")
    charge = diff + enj + nouv + (1 if irreversible else 0)

    if difficulte == "facile" and not irreversible and enjeu == "bas":
        tier = "SOLO"
    elif difficulte == "dur" and (enjeu == "haut" or irreversible or nouveaute == "forte"):
        tier = "CONSEIL"
    else:
        tier = "DUO"

    constructeur = choisir_constructeur(pool, difficulte, nouveaute)
    verificateur = choisir_verificateur(pool, constructeur) if tier != "SOLO" else None
    if tier == "CONSEIL":
        ressources = list(pool)[:max(2, budget)]
    elif tier == "DUO":
        ressources = [constructeur, verificateur]
    else:
        ressources = [constructeur]

    return {"tache": tache, "tier": tier, "charge": charge, "constructeur": constructeur,
            "verificateur": verificateur, "ressources": ressources, "pool": pool,
            "profil": {"difficulte": difficulte, "enjeu": enjeu,
                       "reversible": reversible, "nouveaute": nouveaute}}

def _n(x):
    """Formate un entier avec des espaces comme séparateurs de milliers (sans toucher au reste du texte)."""
    return f"{x:,}".replace(",", " ")

def imprimer_cout(plan, cout_1k=None):
    c = estimer_cout(plan, cout_1k)
    print("\n   💰 Coût estimé (ordre de grandeur, hypothèses configurables — pas une facture) :")
    print(f"      • production   : ~{_n(c['prod'])} tokens   ({c['prod_passes']} passe(s) × {_n(c['base'])})")
    print(f"      • orchestration: ~{_n(c['orch'])} tokens   (la couche EN PLUS, facturée à part chez Sakana)")
    print(f"      • TOTAL        : ~{_n(c['total'])} tokens   · part d'orchestration : {c['ratio']*100:.0f}%")
    if "argent" in c:
        print(f"      • soit ~{c['argent']:.2f} (à {cout_1k}/1k tokens) — indicatif")
    if plan["tier"] == "SOLO":
        print("      → orchestration nulle : on ne paie QUE le travail. C'est l'intérêt du SOLO.")
    else:
        print(f"      → on accepte ces ~{_n(c['orch'])} tokens d'orchestration parce que le profil le justifie.")

def imprimer_plan(plan, cout_1k=None):
    pool = plan["pool"]; tier = plan["tier"]
    constructeur = plan["constructeur"]; verificateur = plan["verificateur"]
    print("🧠 NEXUS — ORCHESTRATEUR (96 voit → propose ; 95 décide)")
    print(f"   Tâche : « {plan['tache']} »")
    pr = plan["profil"]
    print(f"   Profil : difficulté={pr['difficulte']} · enjeu={pr['enjeu']} · réversible={pr['reversible']} · "
          f"nouveauté={pr['nouveaute']}  → charge={plan['charge']}/6\n")
    badge = {"SOLO": "🟢 SOLO", "DUO": "🟡 DUO CROISÉ", "CONSEIL": "🔴 CONSEIL (décomposition)"}[tier]
    print(f"   → Intensité recommandée : {badge}")

    if tier == "SOLO":
        print(f"      • 1 seule ressource : {constructeur} ({pool[constructeur]})")
        print("      • Pas de couche d'orchestration : on ne paie pas des tokens en plus pour rien.")
        etapes = ["FAIRE (1 ressource)", "livrer"]
    elif tier == "DUO":
        print(f"      • Constructeur : {constructeur} ({pool[constructeur]})")
        print(f"      • Vérificateur (≠) : {verificateur} ({pool[verificateur]})")
        print("      • Le vérificateur RELIT sans réécrire (il cherche les angles morts du constructeur).")
        etapes = [f"PLAN ({constructeur})", f"IMPLÉMENTER ({constructeur})",
                  f"RELIRE sans réécrire ({verificateur})", f"CORRIGER ({constructeur})", "SYNTHÈSE"]
    else:  # CONSEIL
        print(f"      • Décomposer la tâche, router chaque morceau vers un spécialiste (max {len(plan['ressources'])}) :")
        for n in plan["ressources"]:
            print(f"          - {n} → {pool[n]}")
        print(f"      • Vérification CROISÉE : {verificateur} relit le travail des autres.")
        print(f"      • SYNTHÈSE finale par {constructeur}.")
        etapes = ["DÉCOMPOSER (96 lit, propose le découpage)",
                  "ROUTER chaque sous-tâche → spécialiste",
                  f"VÉRIFIER en croisé ({verificateur})",
                  f"SYNTHÉTISER ({constructeur})", "SYNTHÈSE remontée à 95"]

    print("\n   Pipeline : " + " → ".join(etapes))
    print("\n   🔒 Garde-fous :")
    print("      • 96 PROPOSE, 95 DÉCIDE (96 éclaire, il ne tranche pas).")
    if tier != "SOLO":
        print("      • Vérificateur ≠ constructeur (un système ne voit pas ses propres angles morts).")
    cout = {"SOLO": "nul", "DUO": "modéré (×2)",
            "CONSEIL": f"élevé (×{len(plan['ressources'])})"}[tier]
    print(f"      • Coût d'orchestration : {cout}. On l'a pris SEULEMENT parce que le profil le justifie.")
    if tier == "CONSEIL":
        print("        (Rappel honnête : l'orchestration = tokens + latence en plus — cf. Fugu, ~30 min."
              " On la réserve aux tâches dures à fort enjeu.)")
    imprimer_cout(plan, cout_1k)

def imprimer_prompts(plan):
    """Génère les VRAIS prompts à donner aux ressources — réutilise les gabarits du duo croisé."""
    tier = plan["tier"]; tache = plan["tache"]
    a = plan["constructeur"]; b = plan["verificateur"]
    print("\n" + "=" * 66)
    print("📝 PROMPTS PRÊTS À L'EMPLOI (générés depuis le plan ci-dessus)\n")
    if tier == "SOLO":
        print(f"[{a}]  Fais directement : « {tache} ». "
              "Tâche simple et réversible — pas de revue croisée nécessaire, livre le résultat.")
        return
    try:
        from nexus_duo import PLAN, RELIRE, IMPL, VERIF
    except Exception as e:
        print(f"⚠️ gabarits duo indisponibles ({e}) — plan affiché sans prompts."); return
    if tier == "DUO":
        for bloc in (PLAN, RELIRE, IMPL, VERIF):
            print(bloc.format(a=a, b=b, tache=tache)); print()
        print(f"→ Boucle : {a} propose · {b} conteste, jusqu'à OK.")
    else:  # CONSEIL : décomposition + routage + vérif croisée + synthèse
        specialistes = plan["ressources"]
        print(f"[ÉTAPE 1 · 96]  Décompose « {tache} » en {len(specialistes)} sous-tâches indépendantes,"
              " une par spécialiste ci-dessous, avec critères de réussite par morceau.\n")
        for i, n in enumerate(specialistes, 1):
            print(f"[ÉTAPE 2.{i} · {n} = spécialiste « {plan['pool'][n]} »]  "
                  f"Traite la sous-tâche {i} de « {tache} ». Reste dans ton domaine, signale tes hypothèses.\n")
        print(f"[ÉTAPE 3 · {b} = VÉRIFICATEUR croisé (≠ des spécialistes constructeurs)]  "
              "Relis chaque morceau : bugs, angles morts, contradictions entre sous-tâches, "
              "tests manquants. Conteste sans complaisance — NE RÉÉCRIS PAS, signale.\n")
        print(f"[ÉTAPE 4 · {a} = SYNTHÈSE]  Recouds les morceaux vérifiés en UNE réponse cohérente,"
              " résous les contradictions, remonte le résultat + les risques résiduels à 95.")

def main():
    p = argparse.ArgumentParser(description="NEXUS — orchestrateur de ressources (Fugu adapté, piloté par 96)")
    p.add_argument("--tache", required=True)
    p.add_argument("--difficulte", choices=list(CHARGE["difficulte"]), default="moyen")
    p.add_argument("--enjeu", choices=list(CHARGE["enjeu"]), default="moyen")
    p.add_argument("--reversible", choices=["oui", "non"], default="oui")
    p.add_argument("--nouveaute", choices=list(CHARGE["nouveaute"]), default="faible")
    p.add_argument("--pool", default=None, help="ressource:force séparés par des virgules")
    p.add_argument("--budget", type=int, default=3, help="nb max de ressources mobilisées (coût borné)")
    p.add_argument("--prompts", action="store_true", help="générer aussi les prompts prêts à l'emploi")
    p.add_argument("--cout-1k", type=float, default=None, dest="cout_1k",
                   help="prix par 1000 tokens (€ ou $) pour une estimation monétaire indicative")
    p.add_argument("--no-log", action="store_true")
    g = p.parse_args()

    pool = parse_pool(g.pool) if g.pool else dict(POOL_DEFAUT)
    if not pool:
        print("🔴 Pool vide. Format : ressource:force, ..."); return

    plan = recommander(g.tache, g.difficulte, g.enjeu, g.reversible, g.nouveaute, pool, g.budget)
    imprimer_plan(plan, g.cout_1k)
    if g.prompts:
        imprimer_prompts(plan)

    if not g.no_log:
        os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
        c = estimer_cout(plan, g.cout_1k)
        rec = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
               "tache": plan["tache"], "tier": plan["tier"], "charge": plan["charge"],
               "constructeur": plan["constructeur"], "verificateur": plan["verificateur"],
               "ressources": plan["ressources"], "profil": plan["profil"],
               "cout_tokens": c["total"], "cout_orchestration": c["orch"]}
        with open(JOURNAL, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"\n   🧾 tracé dans memoire_data/orchestre/journal.jsonl")

if __name__ == "__main__":
    main()
