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
import json, urllib.request, itertools, re, glob, os, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import nexus_sense   # source UNIQUE de lecture des capteurs (respecte CAPTEURS_ROOT)
import nexus_vie     # juge de vie des sources : remplacée par une leçon, ou éteinte
                     # par l'horloge d'activité. 98 n'invente plus sa propre récence.

BASE = "http://127.0.0.1:8077"
ROOT = os.path.join(SCRIPT_DIR, "memoire_data")

# --------------------------------------------------------------------------- #
# Seuils du backlog HITL (nexus_capital.bilan) — PROVISOIRES, même discipline
# que les autres jauges v0.1 de 98 (points de départ, pas des valeurs mesurées).
#   • VIGILANCE dès qu'une petite dette persiste : signal, pas panique.
#   • ALERTE quand la dette s'installe : des critères tranchés par Kily restent
#     non capitalisés/non clos — la boucle d'apprentissage fuit.
# Déclencheur de révision : recaler sur la distribution réelle de n_dette une
# fois ≥ 30 consultations fiche-unique observées (cf. N_JOURS_DETTE côté capital).
# --------------------------------------------------------------------------- #
BACKLOG_VIGILANCE = 3    # PROVISOIRE
BACKLOG_ALERTE = 10      # PROVISOIRE


def backlog_capital():
    """Lecture SEULE du backlog HITL via nexus_capital.bilan(). Ne lève JAMAIS :
    module absent, bilan cassé/vide/corrompu → renvoie None, et 98 rend quand
    même son verdict (dégradé). Un gardien ne doit pas tomber pour un organe
    périphérique — d'où l'enveloppe défensive TOTALE."""
    try:
        import nexus_capital
        b = nexus_capital.bilan()
        return b if isinstance(b, dict) else None
    except Exception:
        return None


def n_dette_backlog(bilan):
    """Nombre de consultations en dette, extrait défensivement d'un bilan (None,
    incomplet ou de mauvais type → 0 : jamais d'exception qui remonterait à 98)."""
    try:
        return max(0, int((bilan or {}).get("n_dette", 0)))
    except Exception:
        return 0


def signal_backlog(bilan):
    """Renvoie un signal de danger (str) selon la dette HITL, ou None sous le
    seuil de vigilance. Purement dérivé de n_dette_backlog (donc défensif)."""
    n = n_dette_backlog(bilan)
    if n >= BACKLOG_ALERTE:
        return ("🔴 backlog HITL : %d consultation(s) capitalisées en dette "
                "(>%d) — appliquer/clore (nexus_capital)" % (n, BACKLOG_ALERTE))
    if n >= BACKLOG_VIGILANCE:
        return ("🟠 backlog HITL : %d consultation(s) capitalisées non closes "
                "— appliquer/clore (nexus_capital)" % n)
    return None


def calc_verdict(signaux, n_dette=0):
    """Verdict de santé (fonction PURE, testable sans serveur). Reprend la règle
    historique fondée sur le NOMBRE de signaux, et laisse le backlog HITL la
    faire monter par SEUIL : dette ≥ seuil d'ALERTE force l'ALERTE même en solo,
    dette ≥ seuil de VIGILANCE force au moins la VIGILANCE."""
    if n_dette >= BACKLOG_ALERTE or len(signaux) > 2:
        return "🔴 ALERTE — plusieurs signaux, intervention recommandée"
    if signaux or n_dette >= BACKLOG_VIGILANCE:
        return "🟡 VIGILANCE — quelques signaux, rien de critique"
    return "🟢 SAIN — l'organisme va bien"


def _runs_propres(cap):
    """Horloge d'ACTIVITÉ (pas de calendrier) : pour chaque événement i, combien
    d'événements capteur de statut 'ok' se sont écoulés DEPUIS lui (strictement
    après). C'est la récence « en nombre de runs propres » qu'attend nexus_vie."""
    n = len(cap)
    out = [0] * n
    ok_apres = 0
    for i in range(n - 1, -1, -1):
        out[i] = ok_apres
        if cap[i].get("statut") == "ok":
            ok_apres += 1
    return out


def plaies_vivantes(cap, liaisons):
    """Compte les PLAIES (échec / retour négatif / reprise) encore VIVANTES.
    Une plaie n'est un dommage ACTIF que si nexus_vie.est_vivant la déclare
    vivante : ni remplacée par une leçon (table de liaison), ni éteinte par
    l'horloge d'activité (assez de runs 'ok' écoulés depuis). 98 délègue tout
    le jugement de récence à nexus_vie — plus de bricolage local.
    Renvoie (echecs, fneg, reprises) : plaies encore vives, par type."""
    rp = _runs_propres(cap)
    vivante = lambda i, e: nexus_vie.est_vivant(e, liaisons, rp[i])
    echecs = sum(1 for i, e in enumerate(cap)
                 if e.get("statut") == "echec" and vivante(i, e))
    fneg = sum(1 for i, e in enumerate(cap)
               if e.get("feedback") == "neg" and vivante(i, e))
    reprises = sum(1 for i, e in enumerate(cap)
                   if e.get("qualite") == "reprise" and vivante(i, e))
    return echecs, fneg, reprises


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
    # 98 ne compte plus TOUTES les plaies jamais captées : une plaie déjà
    # réparée (une leçon l'a remplacée) ou refroidie (l'activité a repris sans
    # qu'elle se reproduise) n'est plus un dommage actif. Le verdict de vie est
    # DÉLÉGUÉ à nexus_vie.est_vivant — premier consommateur de est_vivant().
    # LECTURE SEULE : nexus_sense lit les capteurs, nexus_vie lit la table de
    # liaison ; 98 n'écrit ni l'un ni l'autre.
    cap = nexus_sense.lire()               # source UNIQUE de lecture des capteurs
    if cap:
        liaisons = nexus_vie.lire_liaisons()   # table source → leçon, LECTURE SEULE
        echecs, fneg, reprises = plaies_vivantes(cap, liaisons)
        print(f"   Capteurs : {len(cap)} traces · {echecs} échec(s) vivant(s) · "
              f"{fneg} retour(s) négatif(s) vivant(s) · {reprises} reprise(s) vivante(s)\n")
        if echecs > 0:
            signaux.append(f"🔴 {echecs} échec(s) encore vivant(s) — dommage réel non résolu, analyser la cause")
        if fneg > 0:
            signaux.append(f"🟠 {fneg} retour négatif encore vivant — douleur non résolue de Kily")
        if reprises >= 3:
            signaux.append("🟠 reprises fréquentes encore vivantes — qualité à surveiller")
    else:
        print()

    # --- BACKLOG HITL (nexus_capital) — LECTURE SEULE, ne peut JAMAIS faire
    # tomber 98 : bilan absent/vide/corrompu → backlog_capital() = None, dette 0,
    # verdict rendu quand même (dégradé). ---
    bilan_capital = backlog_capital()
    n_dette = n_dette_backlog(bilan_capital)
    print(f"   Backlog HITL : {n_dette} consultation(s) capitalisées en dette\n")
    sig_bl = signal_backlog(bilan_capital)
    if sig_bl:
        signaux.append(sig_bl)

    print("🚨 Signaux de danger (Danger Theory — on réagit au dommage) :")
    if signaux:
        for s in signaux: print(f"   {s}")
    else:
        print("   ✅ aucun signal de dommage actif")

    # Verdict de santé (le backlog HITL peut faire monter en VIGILANCE/ALERTE).
    verdict = calc_verdict(signaux, n_dette)
    print(f"\n   VERDICT DE SANTÉ : {verdict}")

if __name__ == "__main__":
    main()
