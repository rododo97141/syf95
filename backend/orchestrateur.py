"""
Orchestrateur de boucle minimal — « loop engineering » de l'écosystème NEXUS.

La boucle auto-mandatée enchaîne :

    planifie (95) → exécute (97) → vérifie (96/98) → écrit l'état JSON → reprend

Propriété clé du « loop engineering » : la boucle est REPRISE-able. L'état est
sauvegardé après CHAQUE tâche dans un fichier JSON (la « mémoire » de la
boucle). Si on l'interrompt, le prochain lancement repart exactement là où elle
s'était arrêtée.

Rôle des organes (ici sous forme de STUBS à remplacer plus tard) :
  - 95  pense / planifie       → construit (ou recharge) le plan de tâches.
  - 97  agit                   → exécute une tâche via un Moteur injecté
                                 (IA interchangeable ; `MoteurMock` par défaut).
  - 96  voit / analyse         → vérifie la cohérence + auto-mandate via le filtre.
  - 98  immunité / veto        → bloque une action sensible non autorisée.
  - mémoire                    → le fichier d'état JSON.

Honnêteté technique (cf. principes NEXUS) : 96/97/98 sont des AMORCES. Le vrai
apport de ce fichier est la mécanique de boucle reprenable, pas une fausse
exécution autonome. Aucune dépendance externe : bibliothèque standard.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from filtre_admission import Decision, Ecart, FiltreAdmission
from moteur import Moteur, MoteurMock
from orchestrateur_intensite import recommander

# Fichier d'état par défaut : la « mémoire » de la boucle, à côté de ce script.
ETAT_DEFAUT = Path(__file__).resolve().parent / "etat_boucle.json"
VERSION_ETAT = 1


def _horodatage() -> str:
    """Horodatage ISO 8601 (UTC, à la seconde)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Mémoire de la boucle : persistance JSON
# ---------------------------------------------------------------------------
def charger_etat(chemin: Path) -> dict | None:
    """Charge l'état depuis le JSON, ou None s'il n'existe pas encore."""
    if not chemin.exists():
        return None
    with chemin.open("r", encoding="utf-8") as f:
        return json.load(f)


def sauver_etat(chemin: Path, etat: dict) -> None:
    """
    Sauvegarde l'état en JSON de façon ATOMIQUE (écriture dans un fichier
    temporaire puis remplacement) : si on est coupé en plein milieu, l'état
    précédent reste intact et la reprise reste possible.
    """
    etat["maj_le"] = _horodatage()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tmp = chemin.with_suffix(chemin.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(etat, f, ensure_ascii=False, indent=2)
    tmp.replace(chemin)  # remplacement atomique


# ---------------------------------------------------------------------------
# Organe 95 : pense / planifie
# ---------------------------------------------------------------------------
def plan_initial() -> list[dict]:
    """Plan de démarrage produit par 95 (organe qui planifie)."""
    libelles = [
        "Cartographier les organes 95/96/97/98 et la mémoire",
        "Établir le contrat d'état JSON de la boucle",
        "Brancher le filtre d'admission de l'organe 96",
        "Exécuter une action sensible (soumise au veto de 98)",
        "Clôturer le cycle et préparer la capitalisation",
    ]
    taches = []
    for i, libelle in enumerate(libelles, start=1):
        taches.append(
            {
                "id": f"t{i}",
                "libelle": libelle,
                "etat": "a_faire",       # a_faire | fait | bloque
                "resultat": None,
                "verifie": False,
                "veto": False,
                # La 4e tâche est « sensible » → déclenchera le veto de 98 (stub).
                "sensible": (i == 4),
            }
        )
    return taches


def planifier(chemin_etat: Path) -> dict:
    """
    Recharge l'état existant (REPRISE) ou crée un plan neuf (95).
    En reprise, on conserve le plan en cours : on ne replanifie pas de zéro.
    """
    etat = charger_etat(chemin_etat)
    if etat is not None:
        return etat
    return {
        "version": VERSION_ETAT,
        "cree_le": _horodatage(),
        "maj_le": _horodatage(),
        "cycle": 0,
        "curseur": 0,                 # index de la prochaine tâche à traiter
        "taches": plan_initial(),
        "ecarts_semes": False,        # garde-fou : on ne sème les écarts qu'une fois
        "archive_96": [],             # écarts vus par 96 mais non escaladés
        "journal": [],                # trace lisible des événements
    }


# ---------------------------------------------------------------------------
# Organe 97 : agit (STUB)
# ---------------------------------------------------------------------------
def executer_tache(tache: dict, moteur: Moteur) -> dict:
    """
    STUB de l'organe 97 : agit en s'appuyant sur un Moteur (l'IA injectée).
    L'IA est INTERCHANGEABLE — `MoteurMock` en test/hors-ligne, `AdaptateurAPI`
    (Claude/Gemini/GPT/Kimi) en production — sans rien changer ici.
    """
    prompt = f"Réalise la tâche NEXUS suivante : {tache['libelle']}"
    sortie = moteur.generer(prompt)
    return {"sortie": f"[97] {sortie}", "ok": True}


# ---------------------------------------------------------------------------
# Organes 96 (voit) + 98 (veto) : vérifient (STUB)
# ---------------------------------------------------------------------------
def verifier(tache: dict, resultat: dict) -> tuple[bool, bool, str]:
    """
    STUB de vérification :
      - 96 contrôle la cohérence du résultat de 97 ;
      - 98 exerce son droit de veto sur une action sensible non autorisée.

    Renvoie (ok_96, veto_98, motif).
    """
    ok_96 = bool(resultat.get("ok"))
    veto_98 = bool(tache.get("sensible"))  # sensible → veto par défaut (amorce)
    if veto_98:
        return ok_96, True, "[98] VETO : action sensible, autorisation explicite requise"
    if not ok_96:
        return False, False, "[96] résultat incohérent"
    return True, False, "[96] vérifié, conforme"


# ---------------------------------------------------------------------------
# Organe 96 : auto-mandat via le filtre d'admission
# ---------------------------------------------------------------------------
def detecter_et_filtrer(etat: dict, filtre: FiltreAdmission) -> None:
    """
    96 « voit pour agir » : il détecte des écarts et les passe au filtre
    d'admission. Un écart ADMIS qui est une CRÉATION devient une nouvelle tâche
    AUTO-MANDATÉE (la boucle se donne du travail à elle-même) ; les autres sont
    archivés sans alerter 95.

    Les écarts sont pré-définis (déterministes) : ceci est une amorce, pas un
    vrai détecteur. Le garde-fou `ecarts_semes` empêche tout emballement.
    """
    if etat.get("ecarts_semes"):
        return  # déjà fait à un cycle précédent → on ne resème pas

    ecarts = [
        # Écart CENTRAL : forte criticité/impact → doit être retenu.
        Ecart("e-central", criticite=9, frequence_usage=8, persistance=7,
              impact_utilisateur=9, cout=2, creation=True,
              libelle="Corriger une dérive structurelle détectée"),
        # Écart PÉRIPHÉRIQUE : faible → doit être archivé sans alerter 95.
        Ecart("e-peripherique", criticite=2, frequence_usage=1, persistance=1,
              impact_utilisateur=2, cout=5, creation=True,
              libelle="Ajuster un détail cosmétique mineur"),
    ]
    taille_file = sum(1 for t in etat["taches"] if t["etat"] == "a_faire")

    for resultat in (filtre.evaluer(e, taille_file) for e in ecarts):
        etat["archive_96"].append(resultat.en_dict())
        if resultat.decision is Decision.ADMIS and resultat.ecart.creation:
            # Auto-mandat : 96 fait inscrire une nouvelle tâche au plan de 95.
            nouvel_id = f"t{len(etat['taches']) + 1}"
            etat["taches"].append(
                {
                    "id": nouvel_id,
                    "libelle": f"[auto-mandat 96] {resultat.ecart.libelle}",
                    "etat": "a_faire",
                    "resultat": None,
                    "verifie": False,
                    "veto": False,
                    "sensible": False,
                }
            )
            etat["journal"].append(
                f"{_horodatage()} · 96 ADMET {resultat.ecart.identifiant} "
                f"(priorité {resultat.priorite:.1f} ≥ seuil {resultat.seuil_effectif:.1f}) "
                f"→ nouvelle tâche {nouvel_id}"
            )
        else:
            etat["journal"].append(
                f"{_horodatage()} · 96 archive {resultat.ecart.identifiant} "
                f"({resultat.decision.value}) — 95 non alerté"
            )

    etat["ecarts_semes"] = True


# ---------------------------------------------------------------------------
# La boucle (loop engineering)
# ---------------------------------------------------------------------------
def _capter_tache(tache: dict, tier: str) -> None:
    """Capture SIMPLE : un capteur par tâche traitée, via nexus_sense (mode bibliothèque).
    Import paresseux de organes/ (pas au niveau module). feedback/impact restent VIDES
    (jugement externe — anti-Goodhart). La capture ne doit JAMAIS casser la boucle."""
    try:
        import os
        import sys
        _org = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "organes"
        )
        if _org not in sys.path:
            sys.path.insert(0, _org)
        import nexus_sense
        statut = "ok" if tache["etat"] == "fait" else "bloque"
        nexus_sense.log_event(
            tache=tache["libelle"],
            statut=statut,
            mode="auto",
            difficulte="moyen",
            tier=tier,
            feedback=None,
            impact=None,
        )
    except Exception:
        return


def tourner(chemin_etat: Path, pas: int | None = None,
            moteur: Moteur | None = None) -> dict:
    """
    Exécute la boucle : planifie → exécute → vérifie → écrit l'état → reprend.

    `pas` : nombre maximum de tâches traitées pour CE passage (None = jusqu'au
    bout). Utiliser `--pas 1` plusieurs fois de suite démontre la reprise :
    chaque lancement avance d'une tâche et repart où le précédent s'est arrêté.

    `moteur` : l'IA injectée qu'utilise l'organe 97 (injection de dépendance).
    Par défaut `MoteurMock` (déterministe, hors-ligne) : la boucle tourne sans
    réseau ni clé d'API.
    """
    if moteur is None:
        moteur = MoteurMock()
    etat = planifier(chemin_etat)        # 95 : (re)charge le plan
    etat["cycle"] += 1

    # 96 amorce d'éventuelles tâches auto-mandatées (dans la limite du budget).
    filtre = FiltreAdmission(seuil_base=50, capacite_file=10, budget_generation=1)
    detecter_et_filtrer(etat, filtre)
    sauver_etat(chemin_etat, etat)

    traitees = 0
    for index, tache in enumerate(etat["taches"]):
        if tache["etat"] != "a_faire":
            continue  # déjà faite ou bloquée → on saute (c'est la reprise)
        if pas is not None and traitees >= pas:
            break     # quota du passage atteint → on s'arrête proprement

        # Dosage d'intensité (1er organe réel branché) : journalisé,
        # sans toucher à la forme des tâches ni au contrat d'état JSON.
        reco = recommander(
            tache["libelle"],
            difficulte="moyen",
            enjeu="fort" if tache["sensible"] else "moyen",
            reversible=not tache["sensible"],
            nouveaute="faible",
        )
        etat["journal"].append(
            f"{_horodatage()} · dosage {tache['id']} → {reco['tier']} ({reco['raison']})"
        )

        # 97 agit (via le Moteur injecté).
        resultat = executer_tache(tache, moteur)
        tache["resultat"] = resultat["sortie"]

        # 96 + 98 vérifient.
        ok_96, veto_98, motif = verifier(tache, resultat)
        tache["verifie"] = ok_96
        tache["veto"] = veto_98
        tache["etat"] = "bloque" if (veto_98 or not ok_96) else "fait"

        etat["curseur"] = index + 1
        etat["journal"].append(
            f"{_horodatage()} · {tache['id']} → {tache['etat']} ({motif})"
        )
        # Capture simple : un capteur par tâche (mémoire vivante via nexus_sense).
        _capter_tache(tache, reco["tier"])
        sauver_etat(chemin_etat, etat)  # ← persistance APRÈS CHAQUE tâche
        traitees += 1

    sauver_etat(chemin_etat, etat)
    return etat


def resumer(etat: dict) -> str:
    """Résumé d'une ligne de l'état courant (pour la sortie console)."""
    faits = sum(1 for t in etat["taches"] if t["etat"] == "fait")
    bloques = sum(1 for t in etat["taches"] if t["etat"] == "bloque")
    restants = sum(1 for t in etat["taches"] if t["etat"] == "a_faire")
    total = len(etat["taches"])
    return (
        f"Cycle {etat['cycle']} · {faits}/{total} faite(s) · "
        f"{bloques} bloquée(s) par 98 · {restants} en attente"
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Orchestrateur de boucle NEXUS (loop engineering)."
    )
    parser.add_argument(
        "--etat", type=Path, default=ETAT_DEFAUT,
        help="Chemin du fichier d'état JSON (mémoire de la boucle).",
    )
    parser.add_argument(
        "--pas", type=int, default=None,
        help="Nombre max de tâches pour ce passage (démontre la reprise).",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Efface l'état et repart de zéro.",
    )
    args = parser.parse_args(argv)

    if args.reset and args.etat.exists():
        args.etat.unlink()
        print(f"État réinitialisé : {args.etat}")

    etat = tourner(args.etat, pas=args.pas)
    print(resumer(etat))
    print(f"État écrit dans : {args.etat}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
