#!/usr/bin/env python3
"""
NEXUS — Bilan de l'orchestrateur (boucler la mesure : décider → mesurer → apprendre)
« Recommander, c'est une décision. Mais une décision ne vaut que mesurée au réel. »

Ferme la boucle métabolique sur l'orchestrateur. Croise DEUX sources :
  1. ce que 96 a RECOMMANDÉ  → memoire_data/orchestre/journal.jsonl (intensité + coût estimé)
  2. ce que le réel a DONNÉ   → memoire_data/capteurs/journal.jsonl (statut, impact, et le tier RÉEL)

Il répond à trois questions, honnêtement (confiance déclarée selon l'échantillon) :
  • Quelle intensité 96 recommande-t-il le plus, et pour quel coût estimé cumulé ?
  • L'intensité réellement utilisée PAIE-t-elle (taux de réussite / impact par intensité) ?
  • Sur- ou sous-orchestration ? (payer cher sans gain mesurable = Goodhart du coût)

96 PROPOSE le constat, 95 décide. Aucun jugement définitif sur petit échantillon.

Usage : python3 nexus_orchestre_bilan.py
"""
import os, json, collections

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoire_data")
ORCH = os.path.join(ROOT, "orchestre", "journal.jsonl")
CAPT = os.path.join(ROOT, "capteurs", "journal.jsonl")
TIERS = ("SOLO", "DUO", "CONSEIL")

def lire(path):
    out = []
    if os.path.exists(path):
        for l in open(path, encoding="utf-8"):
            l = l.strip()
            if l:
                try: out.append(json.loads(l))
                except Exception: pass
    return out

def confiance(n):
    if n < 5:  return "TRÈS FAIBLE", "trop peu de mesures — ce sont des indices, pas des conclusions"
    if n < 15: return "FAIBLE", "tendance à confirmer par plus de mesures"
    if n < 50: return "MOYENNE", "tendance lisible"
    return "BONNE", "volume suffisant"

def _n(x):
    return f"{x:,}".replace(",", " ")

def main():
    reco = lire(ORCH)        # recommandations + coût estimé
    capt = lire(CAPT)        # résultats réels

    print("📈 NEXUS — BILAN DE L'ORCHESTRATEUR (décider → mesurer → apprendre)\n")

    # ---------- 1) Côté RECOMMANDATION (ce que 96 a proposé) ----------
    if not reco:
        print("① Recommandations : journal d'orchestration vide.")
        print("   → Lance des routages SANS --no-log (python3 nexus_orchestre.py --tache ...) pour nourrir la mesure.\n")
    else:
        dist = collections.Counter(r.get("tier") for r in reco)
        tok_tot = sum(r.get("cout_tokens", 0) or 0 for r in reco)
        orch_tot = sum(r.get("cout_orchestration", 0) or 0 for r in reco)
        print(f"① Recommandations de 96 : {len(reco)} routages")
        for t in TIERS:
            if dist.get(t):
                print(f"   {t:8} : {dist[t]}×")
        print(f"   Coût estimé cumulé : ~{_n(tok_tot)} tokens, dont ~{_n(orch_tot)} d'orchestration "
              f"({(orch_tot/tok_tot*100) if tok_tot else 0:.0f}%).\n")

    # ---------- 2) Côté RÉEL (ce que les capteurs ont mesuré, par intensité) ----------
    mesures = [e for e in capt if e.get("tier") in TIERS]
    print(f"② Résultats réels mesurés par intensité : {len(mesures)} tâche(s) étiquetée(s) d'un tier")
    par_tier = {}
    if not mesures:
        print("   → Aucune tâche capturée avec son intensité réelle (champ --tier).")
        print("     Pour mesurer : python3 nexus_sense.py log \"...\" --tier DUO --statut ok --feedback pos\n")
    else:
        for t in TIERS:
            sous = [e for e in mesures if e.get("tier") == t]
            if not sous:
                continue
            n = len(sous)
            ok = sum(1 for e in sous if e.get("statut") == "ok")
            imps = [e["impact"] for e in sous if isinstance(e.get("impact"), (int, float))]
            mimp = sum(imps)/len(imps) if imps else None
            par_tier[t] = {"n": n, "reussite": ok/n, "impact": mimp}
            ligne = f"   {t:8} : {n} tâche(s) · réussite {ok}/{n} ({ok/n*100:.0f}%)"
            if mimp is not None:
                ligne += f" · impact moyen {mimp:.0%}"
            print(ligne)
        print()

    # ---------- 3) CONSTAT à 95 (sur/sous-orchestration) ----------
    niveau, note = confiance(len(mesures))
    print(f"③ Constat à 95 (96 propose · confiance {niveau} — {note}) :")
    constats = []
    # sur-orchestration : CONSEIL ne réussit pas mieux que DUO mais coûte bien plus
    if "CONSEIL" in par_tier and "DUO" in par_tier:
        rc, rd = par_tier["CONSEIL"]["reussite"], par_tier["DUO"]["reussite"]
        if rc <= rd + 0.05:
            constats.append("SUR-ORCHESTRATION possible : le CONSEIL ne réussit pas mieux que le DUO "
                            "alors qu'il coûte bien plus (×N). Réserver le CONSEIL aux cas où le DUO échoue.")
        elif rc > rd + 0.15:
            constats.append("Le CONSEIL paie : nettement plus fiable que le DUO sur ces tâches — "
                            "son surcoût est justifié là où l'enjeu est haut.")
    # sous-orchestration : SOLO échoue souvent → il fallait au moins un DUO
    if "SOLO" in par_tier and par_tier["SOLO"]["n"] >= 3 and par_tier["SOLO"]["reussite"] < 0.6:
        constats.append(f"SOUS-ORCHESTRATION possible : le SOLO échoue souvent "
                        f"({par_tier['SOLO']['reussite']*100:.0f}% de réussite) — "
                        "passer ces tâches en DUO (vérificateur croisé) pourrait rattraper.")
    if not constats:
        if len(mesures) < 5:
            constats.append("Pas encore assez de tâches mesurées par intensité pour conclure. "
                            "Continuer à étiqueter les tâches avec --tier : la boucle se referme avec les données.")
        else:
            constats.append("Aucun signal franc de sur/sous-orchestration : le dosage actuel paraît cohérent. "
                            "Continuer à mesurer.")
    for i, c in enumerate(constats, 1):
        print(f"   {i}. {c}")
    print("\n   ⚠️ Rappel : ce bilan ÉCLAIRE 95, il ne décide pas. Sur petit échantillon, ce sont des pistes.")

if __name__ == "__main__":
    main()
