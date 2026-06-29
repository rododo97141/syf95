#!/usr/bin/env python3
"""
NEXUS — Maturité : mesurer la PROGRESSION dans le temps (pas l'activité)
« Prouver qu'on grandit, pas seulement qu'on produit. »

Répond au chantier n°1 identifié par l'audit externe (ChatGPT) ET par notre gardien de la réalité :
démontrer objectivement qu'une évolution est réellement meilleure que la précédente.

Méthode : lire les capteurs en ordre chronologique, comparer le DÉBUT et la FIN de la trace sur
3 axes — autonomie (demande-t-il moins d'aide ?), fiabilité (réussit-il mieux ?), impact (la valeur
perçue monte-t-elle ?). Situer le stade (assisté → supervisé → autonome) et rendre un verdict
HONNÊTE. La mesure est imparfaite, et le dire fait partie de la mesure (anti-auto-illusion).

Usage : python3 nexus_maturite.py
"""
import json, os

JOURNAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoire_data", "capteurs", "journal.jsonl")
TRANSFERT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoire_data", "lecons", "transfert.jsonl")

def lire():
    if not os.path.exists(JOURNAL):
        return []
    return [json.loads(l) for l in open(JOURNAL, encoding="utf-8") if l.strip()]

def axes(sub):
    n = len(sub) or 1
    auto = sum(1 for e in sub if e.get("mode") == "auto") / n
    fia = sum(1 for e in sub if e.get("statut") == "ok") / n
    pos = sum(1 for e in sub if e.get("feedback") == "pos")
    neg = sum(1 for e in sub if e.get("feedback") == "neg")
    imp = (pos / (pos + neg)) if (pos + neg) else None
    return auto, fia, imp

def fleche(d):
    return "▲ monte" if d > 0.04 else ("▼ baisse" if d < -0.04 else "= stable")

def main():
    ev = lire()
    n = len(ev)
    print("🌱 NEXUS — MATURITÉ (progression réelle dans le temps)")
    if n < 6:
        print(f"   Échantillon trop petit ({n}) pour prouver une progression. (honnêteté : pas de verdict)")
        return
    h = max(2, n // 3)
    early, late = ev[:h], ev[-h:]
    ae, fe, ie = axes(early)
    al, fl, il = axes(late)

    print(f"   Base : {n} actions captées · début ({h}) vs fin ({h})\n")
    print(f"   Autonomie  : {ae*100:.0f}% → {al*100:.0f}%   {fleche(al-ae)}   (demande-t-il moins d'aide ?)")
    print(f"   Fiabilité  : {fe*100:.0f}% → {fl*100:.0f}%   {fleche(fl-fe)}   (réussit-il mieux ?)")
    if ie is not None and il is not None:
        print(f"   Impact     : {ie*100:.0f}% → {il*100:.0f}%   {fleche(il-ie)}   (la valeur perçue monte-t-elle ?)")
    else:
        print(f"   Impact     : trop peu de 👍/👎 pour une tendance")

    # RIGUEUR : l'autonomie n'est un vrai progrès que si elle monte à difficulté NON décroissante
    DMAP = {"facile": 1, "moyen": 2, "dur": 3}
    de = [DMAP[e["difficulte"]] for e in early if e.get("difficulte") in DMAP]
    dl = [DMAP[e["difficulte"]] for e in late if e.get("difficulte") in DMAP]
    if de and dl:
        mde, mdl = sum(de) / len(de), sum(dl) / len(dl)
        sens = "↗ plus dures" if mdl - mde > 0.2 else ("↘ plus faciles" if mdl - mde < -0.2 else "≈ constantes")
        print(f"   Difficulté : {mde:.1f} → {mdl:.1f}/3   ({sens})   (rigueur : à difficulté égale ?)")
        if (al - ae) > 0.04 and mdl >= mde - 0.2:
            print("      → moins d'aide à difficulté non décroissante = progrès RIGOUREUX.")
        elif (al - ae) > 0.04:
            print("      ⚠️ autonomie en hausse MAIS tâches plus faciles → progrès en partie illusoire.")
    else:
        print("   Difficulté : non renseignée (--difficulte) — sans elle, l'autonomie reste un proxy faible.")

    # Stade de maturité (basé sur l'autonomie récente — proxy assumé)
    stade = "assisté (on fait AVEC lui)" if al < 0.30 else \
            "supervisé (il fait, on surveille)" if al < 0.60 else \
            "autonome (il fait seul)"
    print(f"\n   🧭 Stade actuel : {stade}")

    # Verdict honnête : progression RÉELLE = plusieurs axes montent ensemble
    monte = sum(1 for d in [al-ae, fl-fe, (il-ie if (ie is not None and il is not None) else 0)] if d > 0.04)
    if monte >= 2:
        print("   ✅ Progression RÉELLE : plusieurs axes montent ensemble.")
    elif al-ae > 0.04 and (il is not None and il-ie <= 0):
        print("   ⚠️ Piège : autonomie en hausse mais impact qui ne suit pas → activité, pas (encore) compétence.")
    else:
        print("   ⚠️ Pas de progression prouvée : on produit, on ne s'améliore pas (encore). Activité ≠ progrès.")

    # GRANDIR vs ACCUMULER : le transfert (leçon réappliquée à du NEUF) — le marqueur décisif
    tr = [json.loads(l) for l in open(TRANSFERT, encoding="utf-8") if l.strip()] if os.path.exists(TRANSFERT) else []
    n_tr = len(tr)
    n_mieux = sum(1 for t in tr if t.get("resultat") == "mieux")
    print("\n   🧫 GRANDIR vs ACCUMULER (le test décisif) :")
    if n_tr:
        print(f"      transferts captés : {n_tr} · dont {n_mieux} ont fait MIEUX sur une tâche NOUVELLE")
        print("      → une leçon réappliquée avec succès = croissance ; jamais réappliquée = simple accumulation.")
    else:
        print("      aucun transfert capté encore — donc pour l'instant : accumulation, pas (preuve de) croissance.")

    # Honnêteté sur la mesure elle-même (les 4 vrais marqueurs — audit ChatGPT)
    mesures = 2 + (1 if n_tr else 0)
    print("\n   🔬 Ce qu'une VRAIE mesure de maturité exige (et où on en est) :")
    print("      • demander moins d'aide      → mesuré (proxy autonomie)")
    print("      • mieux gérer l'erreur       → partiel (statut ok/partiel/échec)")
    print(f"      • transférer à du nouveau    → {'amorcé (journal de transfert)' if n_tr else 'PAS encore mesuré'}")
    print("      • expliquer ses choix        → amorcé (leçons + pourquoi)")
    print(f"\n   Honnêteté : {mesures} marqueurs sur 4. Une preuve de croissance se construit, elle n'est pas acquise.")

if __name__ == "__main__":
    main()
