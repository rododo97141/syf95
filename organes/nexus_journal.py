#!/usr/bin/env python3
"""
NEXUS — Journal des causes (l'organe qui EXPLIQUE la force, sans la faire)
« Dire POURQUOI une fiche est forte, sans jamais toucher à sa force. »

Chaînon d'EXPLICATION, pas de calcul : pour une fiche donnée, assemble ses
événements de force DÉJÀ captés (nexus_sense), son champ « Pourquoi » et son
score de force ACTUEL (nexus_force.calculer_forces) en une FICHE DE SCOUT
lisible. Le journal LIT et RESTITUE ; il ne recalcule ni n'écrit JAMAIS la force.

Doctrine (les cinq garde-fous, chacun testé « vu rouge » sur une mutation) :
  1. LECTURE SEULE — n'écrit RIEN. calculer_forces / nexus_sense / les fiches
     restent intacts au bit près. (mutation : le journal écrit un event => rouge)
  2. TRAÇABILITÉ — chaque ligne du carnet pointe un événement RÉEL, avec son ts.
     (mutation : ajouter une cause sans event source => rouge)
  3. EXHAUSTIVITÉ — le carnet montre TOUS les événements, OU déclare
     explicitement « echantillon: {montre, total} ». Jamais de sous-ensemble
     silencieux. (mutation : tronquer sans déclarer => rouge)
  4. SOURCE DU JUGEMENT — un événement porteur d'un `jeton` HITL est un jugement
     HUMAIN (Kily) ; sans jeton, c'est AUTO. Le journal COMPTE, il n'INTERPRÈTE
     jamais une note brute (la note est citée verbatim, jamais muée en verdict).
     (mutation : compter un auto comme humain => rouge)
  5. HONNÊTETÉ STATISTIQUE — gradation selon N événements :
       N < 5   : « trop peu, faits bruts seulement » (AUCUNE éval agrégée)
       5..14   : « tendance provisoire sur N »
       N >= 15 : « evaluation etablie » (calé sur le seuil n>=15, cf. PR#64)
     (mutation : éval etablie sur N<5 => rouge)

HORS PÉRIMÈTRE v0 (NON codé, volontairement) : force VECTORIELLE, capture
dimensionnelle au jugement, jury autonome, dérivation LLM.

Usage :
  python3 nexus_journal.py scout <fiche_path>          # fiche de scout lisible
  python3 nexus_journal.py scout <fiche_path> --limite 20   # carnet plafonné
"""
import os
import re
import sys
import json
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import nexus_sense    # source UNIQUE de lecture des capteurs (respecte CAPTEURS_ROOT)
import nexus_force    # score de force ACTUEL — LECTURE SEULE (calculer_forces)

# Seuils d'honnêteté statistique — calés sur le seuil n>=15 déjà employé par
# l'écosystème (nexus_sense.stats, nexus_cause.conf, PR#64). En dessous de 5 : on
# ne fait AUCUNE évaluation agrégée, on ne restitue que des faits bruts.
SEUIL_FAITS_BRUTS = 5     # N < 5 : faits bruts seulement
SEUIL_ETABLIE = 15        # N >= 15 : évaluation établie

# Champs restitués par ligne de carnet — un miroir strict des champs de l'event
# source (aucun champ dérivé/inventé ici : la ligne EST l'événement).
CHAMPS_CARNET = ("ts", "tache", "statut", "feedback", "note", "jeton")


def slug_de_fiche(fiche_path):
    """Slug d'une fiche = radical du nom de fichier (sans .md), tel qu'il est
    inscrit dans le champ `fiche` des capteurs (cf. orchestrateur : le slug
    retourné par le recall est le radical du fichier)."""
    base = os.path.basename(str(fiche_path))
    return base[:-3] if base.endswith(".md") else base


def lire_pourquoi(fiche_path):
    """Extrait VERBATIM le corps de la section « Pourquoi » d'une fiche markdown
    (titre `### Pourquoi` écrit par nexus_capital.capitaliser ; tout niveau `#`
    accepté). Renvoie le texte tel quel (jamais reformulé) ou None si la fiche
    n'existe pas ou n'a pas de section Pourquoi. LECTURE SEULE."""
    try:
        with open(fiche_path, encoding="utf-8") as f:
            lignes = f.read().splitlines()
    except OSError:
        return None
    debut = None
    for i, ligne in enumerate(lignes):
        m = re.match(r"^\s*#+\s*pourquoi\s*$", ligne, re.IGNORECASE)
        if m:
            debut = i + 1
            break
    if debut is None:
        return None
    corps = []
    for ligne in lignes[debut:]:
        if re.match(r"^\s*#+\s", ligne):      # section suivante → on s'arrête
            break
        corps.append(ligne)
    texte = "\n".join(corps).strip()
    return texte or None


def _evenements_de_la_fiche(evenements, slug):
    """Sous-liste des événements portant `fiche == slug`, dans l'ordre du journal
    (append-only = ordre chronologique). Ne modifie rien."""
    return [ev for ev in evenements if ev.get("fiche") == slug]


def _ligne_carnet(ev):
    """Projette un événement sur les seuls CHAMPS_CARNET. La note est reprise
    VERBATIM (jamais interprétée). `jeton` absent => None (auto)."""
    return {champ: ev.get(champ) for champ in CHAMPS_CARNET}


def _decomposition_score(evs_fiche, slug, evenements):
    """Score de force ACTUEL + décomposition. Le scalaire est AUTORITAIRE : il
    vient de nexus_force.calculer_forces (LECTURE SEULE) — le journal ne recalcule
    JAMAIS la force. n_succes / n_echec sont de simples COMPTAGES d'événements
    (pas un calcul de force), fournis pour lisibilité de la formule documentée."""
    n_succes = sum(1 for ev in evs_fiche if ev.get("statut") == "succes")
    n_echec = sum(1 for ev in evs_fiche if ev.get("statut") == "echec")
    # Scalaire autoritaire : on DEMANDE sa valeur au moteur de force, on ne la
    # dérive pas nous-mêmes. None si la fiche n'a pas (encore) de force connue.
    forces = nexus_force.calculer_forces(evenements)
    valeur = forces.get(slug)
    # Formule documentée, construite depuis les CONSTANTES RÉELLES du module de
    # force (jamais un littéral figé qui pourrait dériver du code source).
    formule = "%.1f + %.1f*n_succes - %.1f*n_echec (borné [%.1f, %.1f])" % (
        nexus_force.FORCE_DEFAUT, nexus_force.DELTA_SUCCES,
        abs(nexus_force.DELTA_ECHEC), nexus_force.FORCE_MIN, nexus_force.FORCE_MAX,
    )
    return {
        "valeur": valeur,                       # scalaire ACTUEL via calculer_forces
        "n_succes": n_succes,
        "n_echec": n_echec,
        "net": n_succes - n_echec,
        "formule": formule,
        "source": "nexus_force.calculer_forces (lecture seule ; scalaire jamais recalculé ici)",
    }


def _jugements(evs_fiche):
    """Distingue les jugements par SOURCE via le seul `jeton` (champ structuré
    HITL, non imitable) : porteur de jeton => HUMAIN (Kily) ; sans jeton => AUTO.
    COMPTE, n'INTERPRÈTE pas. La note est reportée verbatim, jamais en verdict."""
    detail = []
    n_humain = n_auto = 0
    for ev in evs_fiche:
        jeton = ev.get("jeton")
        humain = jeton is not None
        if humain:
            n_humain += 1
        else:
            n_auto += 1
        detail.append({
            "ts": ev.get("ts"),
            "source": "humain" if humain else "auto",
            "jeton": jeton,                     # id du jeton HITL, ou None
            "note": ev.get("note"),             # VERBATIM — jamais transformée en verdict
        })
    return {"humain": n_humain, "auto": n_auto, "detail": detail}


def _honnetete(n):
    """Gradation d'honnêteté selon N événements. En dessous de SEUIL_FAITS_BRUTS,
    AUCUNE évaluation agrégée n'est produite (evaluation_agregee=False)."""
    if n < SEUIL_FAITS_BRUTS:
        return {
            "n": n,
            "niveau": "faits_bruts",
            "message": "trop peu, faits bruts seulement",
            "evaluation_agregee": False,
        }
    if n < SEUIL_ETABLIE:
        return {
            "n": n,
            "niveau": "tendance_provisoire",
            "message": "tendance provisoire sur %d" % n,
            "evaluation_agregee": True,
        }
    return {
        "n": n,
        "niveau": "etablie",
        "message": "evaluation etablie",
        "evaluation_agregee": True,
    }


def scout(fiche_path, limite=None):
    """FICHE DE SCOUT (LECTURE SEULE) d'une fiche : assemble ses événements de
    force existants, son « Pourquoi » et son score de force ACTUEL en un dict
    lisible qui EXPLIQUE la cause de sa force — sans jamais recalculer ni écrire
    la force.

    `limite` : plafond OPTIONNEL du carnet. Si le nombre d'événements le dépasse,
    le carnet est tronqué aux `limite` premiers ET un champ `echantillon`
    {montre, total} le DÉCLARE explicitement (jamais de troncature silencieuse).
    limite=None (défaut) => carnet EXHAUSTIF, aucun champ echantillon.

    N'ÉCRIT RIEN : ni capteurs, ni forces.json, ni la fiche."""
    slug = slug_de_fiche(fiche_path)
    evenements = nexus_sense.lire()                 # tout le journal (lecture seule)
    evs_fiche = _evenements_de_la_fiche(evenements, slug)
    total = len(evs_fiche)

    # --- Carnet : EXHAUSTIF, ou tronqué mais DÉCLARÉ. ------------------------- #
    tronque = limite is not None and total > limite
    montres = evs_fiche[:limite] if tronque else evs_fiche
    carnet = [_ligne_carnet(ev) for ev in montres]

    fiche = {
        "fiche": slug,
        "fiche_path": str(fiche_path),
        "pourquoi": lire_pourquoi(fiche_path),      # VERBATIM ou None
        "carnet": carnet,
        "score": _decomposition_score(evs_fiche, slug, evenements),
        "jugements": _jugements(evs_fiche),
        "honnetete": _honnetete(total),
    }
    if tronque:
        # Sous-ensemble EXPLICITE : jamais un carnet raccourci en silence.
        fiche["echantillon"] = {"montre": len(carnet), "total": total}
    return fiche


# =========================================================================== #
# CLI — affiche la fiche de scout (lecture seule).
# =========================================================================== #
def _fmt_valeur(v):
    return "inconnue (aucune force calculée pour cette fiche)" if v is None else ("×%s" % v)


def _afficher(fiche):
    print("🧭 NEXUS — JOURNAL DES CAUSES · fiche de scout : %s" % fiche["fiche"])
    print("   (lecture seule — n'écrit ni la force, ni les capteurs, ni la fiche)\n")

    pourquoi = fiche["pourquoi"]
    print("📌 Pourquoi (verbatim de la fiche) :")
    if pourquoi:
        for ligne in pourquoi.splitlines():
            print("   %s" % ligne)
    else:
        print("   — aucun champ « Pourquoi » dans la fiche —")
    print()

    sc = fiche["score"]
    print("💪 Force ACTUELLE : %s" % _fmt_valeur(sc["valeur"]))
    print("   décomposition : %d succès · %d échecs · net %+d" % (
        sc["n_succes"], sc["n_echec"], sc["net"]))
    print("   formule : %s" % sc["formule"])
    print("   source  : %s\n" % sc["source"])

    jug = fiche["jugements"]
    print("⚖️  Jugements par source : 👤 %d humain(s) (jeton HITL) · 🤖 %d auto (sans jeton)" % (
        jug["humain"], jug["auto"]))
    print("   (le journal COMPTE les jugements humains ; il n'interprète jamais une note en verdict)\n")

    ech = fiche.get("echantillon")
    if ech:
        print("📓 Carnet (ÉCHANTILLON DÉCLARÉ : %d montrés / %d au total) :" % (
            ech["montre"], ech["total"]))
    else:
        print("📓 Carnet (EXHAUSTIF : %d événement(s)) :" % len(fiche["carnet"]))
    if not fiche["carnet"]:
        print("   — aucun événement de force capté pour cette fiche —")
    for l in fiche["carnet"]:
        src = "👤" if l.get("jeton") is not None else "🤖"
        base = "   %s [%s] %s · %s" % (src, l.get("ts"), l.get("statut"), l.get("tache"))
        if l.get("feedback"):
            base += " · feedback %s" % l["feedback"]
        print(base)
        if l.get("note"):
            print("        note (verbatim) : %s" % l["note"])
    print()

    h = fiche["honnetete"]
    etat = "évaluation agrégée AUTORISÉE" if h["evaluation_agregee"] else "PAS d'évaluation agrégée"
    print("🔎 Honnêteté (N=%d) : %s — %s." % (h["n"], h["message"], etat))


def main(argv=None):
    p = argparse.ArgumentParser(
        description="NEXUS — journal des causes (fiche de scout, lecture seule)")
    sub = p.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("scout", help="assembler la fiche de scout d'une fiche")
    ps.add_argument("fiche_path", help="chemin de la fiche mémoire à expliquer")
    ps.add_argument("--limite", type=int, default=None,
                    help="plafond du carnet (au-delà : echantillon déclaré)")
    ps.add_argument("--json", action="store_true", help="sortie JSON brute")
    args = p.parse_args(argv)

    fiche = scout(args.fiche_path, limite=args.limite)
    if args.json:
        print(json.dumps(fiche, ensure_ascii=False, indent=2))
    else:
        _afficher(fiche)


if __name__ == "__main__":
    main()
