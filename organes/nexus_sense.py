#!/usr/bin/env python3
"""
NEXUS — Capteur (le premier nerf de l'organisme)
« Sentir pour apprendre. »
Enregistre une trace par tache/action : reussi ou non, mode, duree, ton feedback.
C'est la matiere brute que 96 (analyse) et 98 (sante) liront ensuite.

Minimal par conception : un evenement = une ligne JSON (format JSONL, append-only).
On n'efface jamais une trace — une erreur observee est une donnee, pas une honte.

Usage :
  python3 nexus_sense.py log "analyser les sessions" --statut partiel --mode assiste --feedback neg --note "2/8 au depart"
  python3 nexus_sense.py stats
"""
import os, sys, json, argparse, datetime

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoire_data")
DIR = os.path.join(ROOT, "capteurs")
JOURNAL = os.path.join(DIR, "journal.jsonl")

STATUTS = ("ok", "partiel", "echec")
MODES = ("auto", "assiste")
FEEDBACKS = ("pos", "neg")
QUALITES = ("validee", "reprise")  # validée du 1er coup, ou a nécessité une reprise

def log(args):
    os.makedirs(DIR, exist_ok=True)
    event = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "tache": args.tache,
        "statut": args.statut,
        "mode": args.mode,
        "duree_min": args.duree,
        "feedback": args.feedback,
        "qualite": args.qualite,
        "tokens": args.tokens,   # verbosité : tokens (ou longueur) de SORTIE — efficacité ≠ activité
        "impact": args.impact,   # Impact_Utilisateur 0..1 : valeur RÉELLE livrée (anti-Goodhart)
        "difficulte": args.difficulte,  # facile/moyen/dur : pour normaliser le progrès (rigueur)
        "tier": args.tier,       # intensité d'orchestration RÉELLEMENT utilisée (SOLO/DUO/CONSEIL) — boucle la mesure
        "note": args.note,
    }
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    print(f"🟢 capté : [{event['statut']}/{event['mode']}] {event['tache']}"
          + (f" · feedback {event['feedback']}" if event['feedback'] else ""))

def lire():
    if not os.path.exists(JOURNAL):
        return []
    out = []
    for line in open(JOURNAL, encoding="utf-8"):
        line = line.strip()
        if line:
            try: out.append(json.loads(line))
            except Exception: pass
    return out

def stats(args):
    ev = lire()
    n = len(ev)
    if n == 0:
        print("📭 Aucun événement capté pour l'instant."); return
    ok = sum(1 for e in ev if e["statut"] == "ok")
    partiel = sum(1 for e in ev if e["statut"] == "partiel")
    echec = sum(1 for e in ev if e["statut"] == "echec")
    auto = sum(1 for e in ev if e["mode"] == "auto")
    fb_pos = sum(1 for e in ev if e["feedback"] == "pos")
    fb_neg = sum(1 for e in ev if e["feedback"] == "neg")
    durees = [e["duree_min"] for e in ev if isinstance(e.get("duree_min"), (int, float))]
    toks = [e["tokens"] for e in ev if isinstance(e.get("tokens"), (int, float))]
    imps = [e["impact"] for e in ev if isinstance(e.get("impact"), (int, float))]
    q_val = sum(1 for e in ev if e.get("qualite") == "validee")
    q_rep = sum(1 for e in ev if e.get("qualite") == "reprise")
    q_tot = q_val + q_rep

    print("🫀 NEXUS — CAPTEURS (ce que l'organisme a senti)")
    print(f"   Événements captés : {n}\n")
    print(f"   Fiabilité  : {ok}/{n} réussis ({ok/n*100:.0f}%)  ·  {partiel} partiels  ·  {echec} échecs")
    print(f"   Autonomie  : {auto}/{n} en autonomie ({auto/n*100:.0f}%)")
    if q_tot:
        print(f"   Qualité    : {q_val}/{q_tot} validés sans reprise ({q_val/q_tot*100:.0f}%)")
    else:
        print(f"   Qualité    : non renseignée")
    if fb_pos or fb_neg:
        print(f"   Satisfaction : 👍 {fb_pos}  /  👎 {fb_neg}  (ton retour = arbitre ultime)")
    if durees:
        print(f"   Efficacité : durée moyenne {sum(durees)/len(durees):.0f} min (sur {len(durees)} mesurées)")
    else:
        print(f"   Efficacité : durée non renseignée (à mesurer sur les prochaines tâches)")
    if toks:
        moy = sum(toks)/len(toks)
        tend = ""
        if len(toks) >= 4:  # tendance verbosité : 1re moitié vs 2de (devient-on plus sec ?)
            h = len(toks)//2
            a, b = sum(toks[:h])/h, sum(toks[h:])/(len(toks)-h)
            d = b - a
            tend = (f" · tendance {'▼ plus sec' if d < -1 else '▲ plus bavard' if d > 1 else '= stable'}"
                    f" ({a:.0f}→{b:.0f})")
        print(f"   Verbosité  : {moy:.0f} tokens/tâche en moyenne (sur {len(toks)} mesurées){tend}")
    else:
        print(f"   Verbosité  : tokens non renseignés (token = ressource à concevoir — à mesurer)")
    fb_tot = fb_pos + fb_neg
    if fb_tot:
        print(f"   Impact util.: {fb_pos/fb_tot:.0%} (dérivé de tes 👍/👎 — signal EXTERNE, anti-Goodhart)")
    else:
        print(f"   Impact util.: non mesuré (donne 👍/👎 — c'est TON jugement qui fait foi)")
    print(f"\n   → Matière prête pour 96 (analyse des tendances) et 98 (signaux de santé).")
    print(f"   ⚠️ Confiance : {'faible' if n < 15 else 'moyenne' if n < 50 else 'bonne'} "
          f"(échantillon de {n}).")

def main():
    p = argparse.ArgumentParser(description="NEXUS — capteur (sentir pour apprendre)")
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("log", help="enregistrer un événement")
    pl.add_argument("tache")
    pl.add_argument("--statut", choices=STATUTS, default="ok")
    pl.add_argument("--mode", choices=MODES, default="assiste")
    pl.add_argument("--duree", type=float, default=None)
    pl.add_argument("--feedback", choices=FEEDBACKS, default=None)
    pl.add_argument("--qualite", choices=QUALITES, default=None)
    pl.add_argument("--tokens", type=int, default=None, help="tokens/longueur de sortie (verbosité)")
    pl.add_argument("--impact", type=float, default=None, help="Impact_Utilisateur 0..1 : valeur réelle livrée (anti-Goodhart)")
    pl.add_argument("--difficulte", choices=("facile", "moyen", "dur"), default=None, help="difficulté (pour normaliser le progrès)")
    pl.add_argument("--tier", choices=("SOLO", "DUO", "CONSEIL"), default=None, help="intensité d'orchestration utilisée (boucle la mesure)")
    pl.add_argument("--note", default=None)
    pl.set_defaults(func=log)
    ps = sub.add_parser("stats", help="résumer ce qui a été senti")
    ps.set_defaults(func=stats)
    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
