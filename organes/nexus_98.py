#!/usr/bin/env python3
"""
NEXUS — Organe 98 (GARDIEN : « veille pour protéger »)
HORS de la boucle. Regarde NEXUS LUI-MÊME POUR VEILLER.
Ne demande pas « que faire ? » (c'est 96) mais « le système va-t-il bien ? ».
Surveille la santé de l'organisme, détecte les signaux de DANGER (Danger Theory :
on réagit au dommage, pas à la nouveauté) et rend un verdict de santé.

Système immunitaire v0.1 : externe par conception (un gardien dans la boucle
qu'il surveille pourrait être corrompu par elle).

Usage : python3 nexus_98.py
"""
import json, urllib.request, itertools, re, glob, os

BASE = "http://127.0.0.1:8077"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoire_data")
CAPTEURS = os.path.join(ROOT, "capteurs", "journal.jsonl")

def lire_capteurs():
    ev = []
    if os.path.exists(CAPTEURS):
        for l in open(CAPTEURS, encoding="utf-8"):
            l = l.strip()
            if l:
                try: ev.append(json.loads(l))
                except Exception: pass
    return ev

def vrais_en_attente():
    """Compte les candidats en_attente RÉELLEMENT actifs (exclut les tombes promu:true).
    Corrige le compteur /stats trompeur qui compte aussi les fiches déjà promues."""
    EN = os.path.join(ROOT, "en_attente")
    n = 0
    for p in glob.glob(os.path.join(EN, "*.md")):
        try: first = open(p, encoding="utf-8").readline()
        except Exception: continue
        m = re.search(r"<!--\s*meta:\s*(\{.*\})\s*-->", first)
        promu = False
        if m:
            try: promu = bool(json.loads(m.group(1)).get("promu"))
            except Exception: pass
        if not promu: n += 1
    return n

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as r:
        return json.loads(r.read().decode())

def mots(t):
    return {w for w in re.findall(r"[a-zà-ÿ0-9]+", (t or "").lower()) if len(w) > 3}

def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0

def main():
    try:
        stats = get("/stats")
        domains = get("/domains").get("domains", {})
    except Exception as e:
        print(f"🔴 Mémoire injoignable : {e}. Lance nexus_boot.sh."); return

    fiches = stats.get("structure_fiches", 0)
    cap = stats.get("cap", 200)
    remplissage = stats.get("remplissage", 0) * 100
    en_attente = vrais_en_attente()  # compte honnête : vrais candidats, pas les tombes

    # Signal 1 — saturation mémoire
    sat_danger = remplissage >= 50

    # Signal 2 — redondance (gonflement = douleur)
    redondances = 0
    for dom, cats in domains.items():
        for cat, fl in cats.items():
            sigs = []
            for f in fl:
                res = get(f"/recall?domain={dom}&category={cat}").get("results", [])
                for r in res:
                    sigs.append(mots(r.get("file","") + " " + r.get("excerpt","")))
            for a, b in itertools.combinations(sigs, 2):
                if jaccard(a, b) >= 0.50:   # seuil relevé : ne signaler que les VRAIS doublons
                    redondances += 1
            break  # 1 échantillon de catégorie par domaine suffit pour la jauge v0.1
    red_danger = redondances >= 3

    # Signal 3 — limites non résolues (les « douleurs » du système)
    nb_limites = sum(len(c) for d, cats in domains.items() for cn, c in cats.items() if cn == "limites")
    lim_danger = False  # connaître ses limites n'est PAS un dommage (info, pas alerte — Danger Theory)

    # Signal 4 — backlog en_attente trompeur / tombes
    backlog_danger = en_attente >= 10

    print("🛡️  NEXUS-98 — GARDIEN (veille pour protéger)")
    print("   (hors boucle — observe l'organisme lui-même)\n")
    print(f"   Mémoire : {fiches}/{cap} ({remplissage:.0f}% rempli)")
    print(f"   Redondance détectée : {redondances} paire(s) (jauge v0.1)")
    print(f"   Limites enregistrées (douleurs) : {nb_limites}")
    print(f"   File en_attente : {en_attente}\n")

    signaux = []
    if sat_danger:     signaux.append("🟠 saturation mémoire (≥50 %) — lancer une passe de tri")
    if red_danger:     signaux.append("🟠 redondance élevée — lancer nexus_consolidate/reconcile")
    if lim_danger:     signaux.append("🟠 limites non résolues qui s'accumulent — en traiter")
    if backlog_danger: signaux.append("🟠 backlog en_attente — réconcilier (nexus_reconcile)")

    # --- SIGNAUX issus des CAPTEURS (la douleur réelle, ressentie) ---
    cap = lire_capteurs()
    if cap:
        echecs = sum(1 for e in cap if e.get("statut") == "echec")
        fneg = sum(1 for e in cap if e.get("feedback") == "neg")
        reprises = sum(1 for e in cap if e.get("qualite") == "reprise")
        print(f"   Capteurs : {len(cap)} traces · {echecs} échec(s) · {fneg} retour(s) négatif(s) · {reprises} reprise(s)\n")
        if echecs > 0:
            signaux.append(f"🔴 {echecs} échec(s) capté(s) — dommage réel, analyser la cause")
        if fneg > 0:
            signaux.append(f"🟠 {fneg} retour négatif de Kily — douleur ressentie par l'utilisateur")
        if reprises >= 3:
            signaux.append("🟠 reprises fréquentes — qualité à surveiller")
    else:
        print()

    print("🚨 Signaux de danger (Danger Theory — on réagit au dommage) :")
    if signaux:
        for s in signaux: print(f"   {s}")
    else:
        print("   ✅ aucun signal de dommage actif")

    # Verdict de santé
    if not signaux:
        verdict = "🟢 SAIN — l'organisme va bien"
    elif len(signaux) <= 2:
        verdict = "🟡 VIGILANCE — quelques signaux, rien de critique"
    else:
        verdict = "🔴 ALERTE — plusieurs signaux, intervention recommandée"
    print(f"\n   VERDICT DE SANTÉ : {verdict}")

if __name__ == "__main__":
    main()
