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

# --------------------------------------------------------------------------- #
# Seuils BUDGETS DE BOUCLE (nexus_budget) — PROVISOIRES, LARGES, non dérivés des
# mocks. 98 LIT (jamais ne pilote, jamais ne tombe) : consommé/plafond réels,
# TAUX de coupures (une coupure ISOLÉE = ok-inerte, PAS d'alerte : seule la
# RÉCURRENCE donne VIGILANCE puis ALERTE) et profondeur/TENDANCE de la file
# à-valider (croissance monotone sur k cycles = signal).
# Déclencheur de révision : recaler sur la distribution réelle des N premières
# conversations réelles journalisées (cf. tableau du rapport de PR).
# --------------------------------------------------------------------------- #
BUDGET_COUPURES_VIGILANCE = 2   # PROVISOIRE : 1 coupure = ok-inerte (rien) ; ≥2 = vigilance.
BUDGET_COUPURES_ALERTE = 6      # PROVISOIRE : coupures récurrentes = alerte.
AVALIDER_TENDANCE_K = 3         # PROVISOIRE : croissance monotone sur k cycles = signal.

# Préfixes des capteurs budget — source unique nexus_budget, import DÉFENSIF
# (98 doit rester debout même si le module budget est indisponible).
try:
    import nexus_budget
    _PREFIXE_COUPURE = nexus_budget.TACHE_COUPURE
    _PREFIXE_ITER92 = nexus_budget.TACHE_ITERATION_92
except Exception:  # pragma: no cover - repli si organes/nexus_budget absent
    _PREFIXE_COUPURE = "budget:coupure"
    _PREFIXE_ITER92 = "iteration-92"


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


def calc_verdict(signaux, n_dette=0, n_coupures=0, jointure_alertes=0):
    """Verdict de santé (fonction PURE, testable sans serveur). Reprend la règle
    historique fondée sur le NOMBRE de signaux, et laisse le backlog HITL ET le
    TAUX de coupures budget la faire monter par SEUIL. Une coupure ISOLÉE
    (n_coupures < seuil de vigilance) ne fait RIEN monter : ok-inerte.

    `jointure_alertes` (AJOUT) : nombre de ruptures de la JOINTURE UNIQUE
    jeton↔event de force (self-reward mécanique, id forgé, doublon d'id). Une
    SEULE rupture est une atteinte DIRECTE à la ligne rouge de doctrine — ALERTE
    d'emblée, même isolée (on ne « tolère » pas un début d'auto-récompense)."""
    if jointure_alertes > 0:
        return "🔴 ALERTE — rupture de jointure jeton↔force (auto-récompense ?)"
    if (n_dette >= BACKLOG_ALERTE or n_coupures >= BUDGET_COUPURES_ALERTE
            or len(signaux) > 2):
        return "🔴 ALERTE — plusieurs signaux, intervention recommandée"
    if (signaux or n_dette >= BACKLOG_VIGILANCE
            or n_coupures >= BUDGET_COUPURES_VIGILANCE):
        return "🟡 VIGILANCE — quelques signaux, rien de critique"
    return "🟢 SAIN — l'organisme va bien"


# --------------------------------------------------------------------------- #
# JOINTURE UNIQUE jeton ↔ event de force (3e RIDEAU, LECTURE SEULE).
# 1er rideau = le registre à l'émission (nexus_capital.appliquer refuse un jeton
# absent/inconnu/rejoué) ; 2e rideau = l'AST (l'observer ne peut ni importer la
# fabrique de jetons ni appeler appliquer) ; 3e rideau = CETTE lecture a posteriori.
# Défense en profondeur : même si les deux premiers rideaux étaient contournés, le
# bilan de 98 rendrait l'anomalie VISIBLE (verdict non-SAIN). Cette lecture ne fait
# JAMAIS tomber 98 (tout défensif → aucune alerte inventée en dernier recours).
# --------------------------------------------------------------------------- #
def evenements_force(cap):
    """Events de FORCE parmi les capteurs : porteurs d'une `fiche` ET d'un `statut`
    compté par nexus_force.calculer_forces (succes|echec). Ce sont les SEULS events
    qui bougent la force ; chacun DOIT être adossé à un jeton humain. Défensif."""
    out = []
    for e in (cap or []):
        try:
            if e.get("fiche") and e.get("statut") in ("succes", "echec"):
                out.append(e)
        except Exception:
            continue
    return out


def jetons_registre():
    """Vue LECTURE SEULE du registre des jetons (nexus_capital.jetons_emis) :
    {id: record}. Module absent/cassé → None (98 dégrade, ne tombe pas) : dans ce
    cas on N'INVENTE aucune alerte « inconnu » (dégradation prudente)."""
    try:
        import nexus_capital
        emis = nexus_capital.jetons_emis()
        reg = {}
        for j in (emis or []):
            jid = j.get("id")
            if jid is not None:
                reg[jid] = j
        return reg
    except Exception:
        return None


def signaux_jointure(cap, registre):
    """JOINTURE UNIQUE entre events de force et registre des jetons. Renvoie la
    liste des alertes (str), défensivement (toute anomalie interne → pas d'alerte
    inventée, jamais d'exception remontée au verdict) :
      • event de force SANS jeton                        → auto-récompense / oubli du verrou ;
      • event de force → jeton INCONNU du registre       → id forgé (si registre lisible) ;
      • MÊME jeton référencé par ≥2 events de force       → copie d'id (usage non-unique).
    Un event sans jeton, un jeton inconnu OU un jeton double ⇒ verdict non-SAIN."""
    alertes = []
    try:
        evs = evenements_force(cap)
        sans = 0
        vus = {}
        for e in evs:
            jid = e.get("jeton")
            if not jid:
                sans += 1
            else:
                vus[jid] = vus.get(jid, 0) + 1
        if sans:
            alertes.append(
                "🔴 %d event(s) de force SANS jeton — la force ne peut venir que "
                "d'un jeton humain (nexus_capital)" % sans)
        for jid, n in sorted(vus.items()):
            if registre is not None and jid not in registre:
                alertes.append(
                    "🔴 event de force → jeton INCONNU du registre (%r) — id forgé ?"
                    % (jid,))
            if n >= 2:
                alertes.append(
                    "🔴 jeton %r référencé %d× par des events de force (doublon) — "
                    "copie d'id, un jeton est à usage UNIQUE" % (jid, n))
    except Exception:
        return alertes
    return alertes


# --------------------------------------------------------------------------- #
# BUDGETS DE BOUCLE — bilan LECTURE SEULE (ne peut JAMAIS faire tomber 98).
# Tout est défensif : capteurs corrompus, note illisible, état absent → valeurs
# neutres, jamais d'exception qui remonterait au verdict.
# --------------------------------------------------------------------------- #
def evenements_coupure(cap):
    """Extrait des capteurs les événements de coupure budget (note décodée),
    LECTURE SEULE et défensive : jamais d'exception."""
    out = []
    for e in (cap or []):
        try:
            if not str(e.get("tache", "")).startswith(_PREFIXE_COUPURE):
                continue
            try:
                info = json.loads(e.get("note") or "{}")
            except Exception:
                info = {}
            out.append(info if isinstance(info, dict) else {})
        except Exception:
            continue
    return out


def taux_coupures(cap):
    """Nombre de coupures budget captées (le « taux » brut ; une coupure isolée
    n'est PAS une alerte — cf. signal_coupures)."""
    return len(evenements_coupure(cap))


def signal_coupures(n):
    """Signal de danger dérivé du TAUX de coupures, ou None. Coupure ISOLÉE =
    ok-inerte (n < seuil de vigilance → None) : seule la RÉCURRENCE parle."""
    if n >= BUDGET_COUPURES_ALERTE:
        return ("🔴 coupures budget récurrentes (%d ≥ %d) — deux boucles se "
                "répondent-elles sans fin ? (nexus_budget)" % (n, BUDGET_COUPURES_ALERTE))
    if n >= BUDGET_COUPURES_VIGILANCE:
        return ("🟠 coupures budget répétées (%d) — surveiller échanges/plafonds "
                "(nexus_budget)" % n)
    return None


def profondeur_a_valider(etat_boucle):
    """Profondeur ACTUELLE de la file à-valider (auto-mandat au plafond).
    Défensive : état absent/mauvais → 0."""
    try:
        return max(0, int(len((etat_boucle or {}).get("a_valider", []))))
    except Exception:
        return 0


def tendance_a_valider(etat_boucle, k=AVALIDER_TENDANCE_K):
    """True si la file à-valider croît de façon MONOTONE sur les k derniers
    cycles (backlog qui s'installe = signal). Défensive : série trop courte,
    absente ou mauvaise → False."""
    try:
        serie = [int(x) for x in (etat_boucle or {}).get("a_valider_historique", [])]
        serie = serie[-k:]
        if k < 2 or len(serie) < k:
            return False
        return all(serie[i] < serie[i + 1] for i in range(len(serie) - 1))
    except Exception:
        return False


def signal_a_valider(etat_boucle, k=AVALIDER_TENDANCE_K):
    """Signal si la file à-valider croît en profondeur ET en tendance, ou None."""
    prof = profondeur_a_valider(etat_boucle)
    if prof > 0 and tendance_a_valider(etat_boucle, k):
        return ("🟠 file à-valider en croissance monotone sur %d cycles "
                "(profondeur %d) — auto-mandat sature, valider/borner" % (k, prof))
    return None


def iterations_92(cap):
    """Compte les marqueurs d'itération d'expert-92 (runner futur, hors code).
    Statut VISIBLE-SI-LA-SUPERVISION-TRACE : n'est affiché que s'il en existe."""
    n = 0
    for e in (cap or []):
        try:
            if str(e.get("tache", "")).startswith(_PREFIXE_ITER92):
                n += 1
        except Exception:
            continue
    return n


def bilan_budget(cap, etat_boucle=None):
    """Bilan budget LECTURE SEULE pour 98 : consommé/plafond RÉELS par fil coupé,
    taux de coupures, profondeur ET tendance de la file à-valider, marqueurs 92.
    Ne lève JAMAIS — cette lecture ne peut pas faire tomber 98 (tout défensif →
    dict neutre en dernier recours). Les budgets LOCAUX ne bornent PAS le coût
    GLOBAL (produit, pas somme) : 98 affiche le réel, le budget-tokens est un
    chantier DISTINCT."""
    try:
        evs = evenements_coupure(cap)
        fils = {}
        for info in evs:
            cle = str(info.get("cle"))
            fils[cle] = {"consomme": info.get("consomme"),
                         "plafond": info.get("plafond"),
                         "raison": info.get("raison")}
        return {
            "n_coupures": len(evs),
            "fils_coupes": fils,
            "profondeur_a_valider": profondeur_a_valider(etat_boucle),
            "tendance_a_valider": tendance_a_valider(etat_boucle),
            "iterations_92": iterations_92(cap),
        }
    except Exception:
        return {"n_coupures": 0, "fils_coupes": {}, "profondeur_a_valider": 0,
                "tendance_a_valider": False, "iterations_92": 0}


def _charger_etat_boucle():
    """Lecture SEULE et DÉFENSIVE de l'état de la boucle (backend/etat_boucle.json)
    pour la profondeur/tendance de la file à-valider. Absent/corrompu → None :
    98 rend quand même son verdict (dégradé). Ne lève JAMAIS."""
    try:
        chemin = os.path.join(os.path.dirname(SCRIPT_DIR), "backend", "etat_boucle.json")
        with open(chemin, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except Exception:
        return None


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

# --------------------------------------------------------------------------- #
# PROMOTION — file en_attente comme TRANSIT (lecture seule, ne tombe JAMAIS).
# Profondeur + tendance de la file, âge-en-EXAMENS du plus vieux candidat, et
# comptes d'archives PAR RAISON en repliant le journal de clôture (état courant
# par id : dernier événement effectif gagne ; un clos-puis-réactivé n'est PAS
# compté comme archive). Tout est défensif — aucune de ces lectures ne peut
# faire tomber 98.
# --------------------------------------------------------------------------- #
PROMO_TENDANCE_K = 3    # PROVISOIRE : croissance monotone sur k passes = signal.


def _clotures_path():
    return os.path.join(ROOT, "archive", "clotures.jsonl")


def _examens_path():
    return os.path.join(ROOT, "promotion", "examens.jsonl")


def _lire_jsonl(path):
    """Lecture DÉFENSIVE d'un journal .jsonl (append-only). Absent/corrompu →
    []. Ne lève JAMAIS (un gardien ne tombe pas pour un journal illisible)."""
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return out


def archives_par_raison(evenements):
    """Replie le journal de clôture : état COURANT par id (dernier événement
    EFFECTIF gagne ; les no-op ne changent pas l'état). Un id clos PUIS réactivé
    n'est plus compté comme archive. Renvoie {raison: n}. Défensive."""
    etat = {}
    for e in (evenements or []):
        try:
            if e.get("noop"):
                continue
            sid = e.get("id")
            if sid is None:
                continue
            ev = e.get("event")
            if ev == "clore":
                etat[sid] = e.get("raison")
            elif ev == "reactiver":
                etat[sid] = None      # de retour en file : plus archivé
        except Exception:
            continue
    comptes = {}
    for _sid, raison in etat.items():
        if raison is None:
            continue
        comptes[raison] = comptes.get(raison, 0) + 1
    return comptes


def profondeur_par_passe(examens):
    """Profondeur en_attente estimée à chaque passe = nombre d'ids DISTINCTS
    examinés (une passe est exhaustive). Renvoie [(passe, n)] triée. Défensive."""
    par = {}
    for e in (examens or []):
        try:
            p = int(e.get("passe", 0))
            par.setdefault(p, set()).add(e.get("id"))
        except Exception:
            continue
    return [(p, len(par[p])) for p in sorted(par)]


def tendance_en_attente(examens, k=PROMO_TENDANCE_K):
    """True si la profondeur de la file croît de façon MONOTONE sur les k
    dernières passes (backlog qui s'installe). Série trop courte → False."""
    try:
        serie = [n for _p, n in profondeur_par_passe(examens)][-k:]
        if k < 2 or len(serie) < k:
            return False
        return all(serie[i] < serie[i + 1] for i in range(len(serie) - 1))
    except Exception:
        return False


def _epoch_de(path):
    """Époque d'entrée (meta['reactivations'], 0 par défaut) d'un fichier
    en_attente. Lecture seule, défensive."""
    try:
        with open(path, encoding="utf-8") as f:
            txt = f.read()
        m = re.search(r"<!--\s*meta:\s*(\{.*?\})\s*-->", txt, re.S)
        if m:
            return int(json.loads(m.group(1)).get("reactivations", 0))
    except Exception:
        pass
    return 0


def age_examens_plus_vieux(examens):
    """Âge-en-EXAMENS du plus vieux candidat ENCORE en file : max, sur les ids
    actuellement en en_attente, du nombre d'examens subis dans leur époque
    courante. Défensive → 0. (« Vieux » se mesure en examens subis, pas en
    calendrier : cohérent avec le résidu perime-eligible.)"""
    par_id_epoch = {}
    for e in (examens or []):
        try:
            cle = (e.get("id"), int(e.get("epoch", 0)))
            par_id_epoch[cle] = par_id_epoch.get(cle, 0) + 1
        except Exception:
            continue
    age = 0
    try:
        EN = os.path.join(ROOT, "en_attente")
        for p in glob.glob(os.path.join(EN, "*.md")):
            sid = os.path.basename(p)[:-3]
            age = max(age, par_id_epoch.get((sid, _epoch_de(p)), 0))
    except Exception:
        return age
    return age


def bilan_promotion():
    """Bilan LECTURE SEULE de la file en_attente comme transit. Ne lève JAMAIS
    (tout défensif → dict neutre en dernier recours) : 98 rend son verdict même
    si les journaux sont absents/cassés."""
    try:
        clo = _lire_jsonl(_clotures_path())
        exs = _lire_jsonl(_examens_path())
        depths = profondeur_par_passe(exs)
        return {
            "profondeur": depths[-1][1] if depths else 0,
            "tendance": tendance_en_attente(exs),
            "age_examens_max": age_examens_plus_vieux(exs),
            "archives_par_raison": archives_par_raison(clo),
        }
    except Exception:
        return {"profondeur": 0, "tendance": False, "age_examens_max": 0,
                "archives_par_raison": {}}


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

    # --- BUDGETS DE BOUCLE (nexus_budget) — LECTURE SEULE, ne peut JAMAIS faire
    # tomber 98 : bilan_budget avale toute anomalie. Coupure ISOLÉE = ok-inerte
    # (aucun signal) ; seule la RÉCURRENCE, et la file à-valider en croissance
    # monotone, montent le verdict. ---
    etat_boucle = _charger_etat_boucle()
    bb = bilan_budget(cap, etat_boucle)
    print(f"   Budgets  : {bb['n_coupures']} coupure(s) captée(s) · "
          f"file à-valider {bb['profondeur_a_valider']}"
          f"{' (↗ tendance)' if bb['tendance_a_valider'] else ''}")
    if bb["fils_coupes"]:
        for cle, d in bb["fils_coupes"].items():
            print(f"     · fil {cle} : {d.get('consomme')}/{d.get('plafond')} "
                  f"({d.get('raison')})  [consommé/plafond RÉELS]")
    if bb["iterations_92"]:  # VISIBLE-SI-LA-SUPERVISION-TRACE (sinon masqué)
        print(f"   Itér. 92 : {bb['iterations_92']} marqueur(s) (runner futur, hors code)")
    print("   ⓘ budgets LOCAUX : bornent chaque fil, PAS le coût GLOBAL "
          "(produit, pas somme) — budget-tokens = chantier distinct.\n")
    sig_c = signal_coupures(bb["n_coupures"])
    if sig_c:
        signaux.append(sig_c)
    sig_av = signal_a_valider(etat_boucle)
    if sig_av:
        signaux.append(sig_av)

    # --- PROMOTION (file en_attente comme transit) — LECTURE SEULE, ne peut
    # JAMAIS faire tomber 98 : bilan_promotion avale toute anomalie. On AFFICHE
    # le réel ; le backlog en_attente reste le signal de danger déjà géré plus
    # haut (backlog_danger). ---
    bp = bilan_promotion()
    arch = bp["archives_par_raison"]
    resume_arch = (", ".join("%s=%d" % (r, n) for r, n in sorted(arch.items()))
                   if arch else "aucune")
    print(f"   Promotion : file {bp['profondeur']}"
          f"{' (↗ tendance)' if bp['tendance'] else ''} · "
          f"plus vieux = {bp['age_examens_max']} examen(s) · archives [{resume_arch}]\n")

    # --- JOINTURE UNIQUE jeton ↔ event de force (3e rideau, LECTURE SEULE) : la
    # force ne peut venir que d'un jeton humain valide, consommé UNE fois. Toute
    # rupture (event sans jeton, jeton inconnu, doublon d'id) = auto-récompense
    # potentielle → non-SAIN. Cette lecture ne peut JAMAIS faire tomber 98. ---
    registre = jetons_registre()
    alertes_jointure = signaux_jointure(cap, registre)
    if alertes_jointure:
        for a in alertes_jointure:
            signaux.append(a)

    print("🚨 Signaux de danger (Danger Theory — on réagit au dommage) :")
    if signaux:
        for s in signaux: print(f"   {s}")
    else:
        print("   ✅ aucun signal de dommage actif")

    # Verdict de santé (backlog HITL, taux de coupures ET jointure jeton↔force
    # peuvent faire monter le verdict).
    verdict = calc_verdict(signaux, n_dette, bb["n_coupures"],
                           jointure_alertes=len(alertes_jointure))
    print(f"\n   VERDICT DE SANTÉ : {verdict}")

if __name__ == "__main__":
    main()
