#!/usr/bin/env python3
"""
NEXUS — Continuité de la force (ouvrir la voie du jugement, JAMAIS l'émettre)
« La force se prépare par voie humaine ; aucune main mécanique ne la décerne. »

Quand un critère-Kily RÉELLEMENT capitalisé est appliqué à une tâche nouvelle,
cet organe OUVRE une consultation force-éligible (fiche-unique) dans le journal
capital — un point d'ancrage pour un jugement HUMAIN futur (appliquer + jeton).
Il n'émet AUCUN capteur de force : la continuité qu'il installe est celle de la
VOIE (une consultation ouverte, à juger), jamais celle du VERDICT (le succès /
l'échec, qui reste un geste humain externe — cf. nexus_capital.appliquer).

LIGNE ROUGE DE DOCTRINE (reprise de nexus_capital) : aucun chemin MÉCANIQUE ne
décerne de force. Cet organe respecte la dissymétrie :
  • ouvrir_pour_tache  → écrit une consultation OUVERTE (fiche_retenue=None),
                         SANS capteur de force, SANS jeton, SANS appeler appliquer.
  • file_a_juger       → LECTURE SEULE : les consultations ouvertes non jugées.
Le jugement (capteur de force) reste hors de portée d'ici, par construction.

Le chantier CÂBLE nexus_capital, il ne le réécrit pas : il réutilise ses helpers
(_chemin_consultations / _prochain_id / _append_consultation / _lire_consultations
/ _candidats / _now) — un seul écrivain du journal capital, une seule vérité.

Gestes :
  ouvrir_pour_tache(critere_slug, tache)  -> cons_id : ouvre UNE consultation
      force-éligible pour un critère-Kily EXISTANT (sinon ValueError).
  file_a_juger()                          -> [{id, critere, tache, ts}, ...] : les
      consultations ouvertes non jugées (ni appliquées, ni closes). LECTURE SEULE.

Usage bibliothèque + CLI de lecture (main : ventilation succès/échec + garde).
"""
import os
import sys
import contextlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import nexus_capital   # SEUL écrivain du journal capital : on réutilise SES helpers


@contextlib.contextmanager
def _avec_racine(racine):
    """Fixe temporairement MEMOIRE_ROOT sur `racine` (même contrat d'override que
    nexus_force._racine_memoire, relu à CHAQUE appel), puis restaure l'état exact.
    `racine=None` : ne touche à rien (on suit MEMOIRE_ROOT tel que configuré)."""
    if racine is None:
        yield
        return
    ancien = os.environ.get("MEMOIRE_ROOT")
    os.environ["MEMOIRE_ROOT"] = str(racine)
    try:
        yield
    finally:
        if ancien is None:
            os.environ.pop("MEMOIRE_ROOT", None)
        else:
            os.environ["MEMOIRE_ROOT"] = ancien


# =========================================================================== #
# 1) ouvrir_pour_tache — ouvre UNE consultation force-éligible (fiche-unique),
#    SANS jamais émettre de capteur de force. C'est la « voie », pas le verdict.
# =========================================================================== #
def ouvrir_pour_tache(critere_slug, tache, racine=None):
    """Ouvre une consultation force-éligible pour le critère-Kily `critere_slug`
    RÉELLEMENT appliqué à `tache`, et renvoie son id (cons_id).

    - `critere_slug` DOIT être une fiche existante sous
      structure/<dom>/criteres-kily/ — sinon REFUS (ValueError). Aucune
      consultation « fantôme » sur un critère qui n'existe pas.
    - La consultation est écrite fiche-UNIQUE (slugs_retournes=[critere_slug]) et
      OUVERTE (fiche_retenue=None) : le seul état qui pourra un jour recevoir un
      jugement humain (nexus_capital.appliquer + jeton).
    - N'ÉMET AUCUN capteur de force : ni log_event, ni champ capteur_force, ni
      jeton. La force reste un geste humain externe, hors de portée d'ici.

    Réutilise les helpers de nexus_capital (un seul écrivain du journal)."""
    slug = (critere_slug or "").strip()
    if not slug:
        raise ValueError("ouvrir_pour_tache: 'critere_slug' est requis.")
    tache = (tache or "").strip()
    if not tache:
        raise ValueError("ouvrir_pour_tache: 'tache' est requise (traçabilité).")

    with _avec_racine(racine):
        # Existence RÉELLE : le slug doit être une fiche criteres-kily du corpus
        # (mêmes candidats que rank() lit sur le corpus). Sinon, critère fantôme → REFUS.
        existants = {nexus_capital._slug_de(c) for c in nexus_capital._candidats()}
        if slug not in existants:
            raise ValueError(
                "ouvrir_pour_tache: REFUS — %r n'est pas une fiche criteres-kily "
                "existante (structure/<dom>/criteres-kily/). Aucune consultation "
                "fantôme sur un critère inexistant." % (slug,))

        cons_id = nexus_capital._prochain_id()
        rec = {
            "type": "consultation",
            "id": cons_id,
            "ts": nexus_capital._now(),
            "requete": tache,
            "slugs_retournes": [slug],   # fiche-UNIQUE → force-éligible (jugement futur)
            "fiche_retenue": None,       # OUVERTE : le verdict reste un geste HUMAIN
            "tache": tache,
            # PAS de capteur_force, PAS de jeton, PAS de statut : la voie, pas la force.
        }
        nexus_capital._append_consultation(rec)
        return cons_id


# =========================================================================== #
# 2) file_a_juger — LECTURE SEULE : les consultations OUVERTES non jugées, i.e.
#    de type consultation SANS application NI clôture pour le même id.
# =========================================================================== #
def file_a_juger(racine=None):
    """Renvoie la liste des consultations OUVERTES non jugées, chacune décrite par
    {id, critere, tache, ts}. « Ouverte » = un enregistrement de type consultation
    dont l'id n'a NI application NI cloture_sans_dette (une appliquée ou une close
    est EXCLUE — elle a déjà quitté la file). LECTURE SEULE, ordre d'ouverture.

    `critere` = la fiche constatée (slugs_retournes[0]) quand il y en a une, sinon
    None. Robuste : journal absent/corrompu → liste vide (délégué à nexus_capital)."""
    with _avec_racine(racine):
        consultations = {}   # id -> dernier record d'ouverture (last-write-wins)
        closes = set()       # ids appliqués OU clos-sans-dette → hors file
        for rec in nexus_capital._lire_consultations():
            t = rec.get("type")
            cid = rec.get("id")
            if cid is None:
                continue
            if t == "consultation":
                consultations[cid] = rec
            elif t in ("application", "cloture_sans_dette"):
                closes.add(cid)

        out = []
        for cid, rec in consultations.items():
            if cid in closes:
                continue                       # jugée / close : EXCLUE de la file
            slugs = rec.get("slugs_retournes") or []
            out.append({
                "id": cid,
                "critere": slugs[0] if slugs else None,
                "tache": rec.get("tache"),
                "ts": rec.get("ts"),
            })
        return out


# =========================================================================== #
# Lecture des events de force RÉELS (applications capteur_force=True) — sert le
# garde de discrimination (nexus_98). LECTURE SEULE.
# =========================================================================== #
def evenements_force(racine=None):
    """Les applications de force réelles du journal capital (capteur_force=True),
    telles quelles — c'est nexus_98.garde_discrimination_force qui les interprète
    (statut_juge ∈ {succes, echec}). LECTURE SEULE ; journal absent → []."""
    with _avec_racine(racine):
        return [r for r in nexus_capital._lire_consultations() if r.get("capteur_force")]


# =========================================================================== #
# main — vue LECTURE SEULE : ventilation succès/échec des jugements + garde.
#    Ne touche AUCUN autre signal ; n'émet AUCUNE force.
# =========================================================================== #
def main(racine=None):
    import nexus_98   # garde PUR (import tardif : évite tout cycle à l'import)

    with _avec_racine(racine):
        events = evenements_force()
        file = file_a_juger()
    garde = nexus_98.garde_discrimination_force(events, file=file)

    print("🔗 NEXUS — CONTINUITÉ DE LA FORCE")
    print("   (ouvre la voie du jugement ; n'ÉMET jamais de force par voie mécanique)\n")
    print("   Jugements de force : %d  (%d succès / %d échec) · taux d'échec %.0f%%"
          % (garde["total"], garde["succes"], garde["echec"], garde["taux_echec"] * 100))
    print("   File à juger (consultations ouvertes) : %d\n" % len(file))

    if garde["alerte"]:
        print("   🟠 %s" % garde["alerte"])
    else:
        print("   ✅ jugement discriminant, file sous contrôle (aucun signe de tampon)")


if __name__ == "__main__":
    main()
