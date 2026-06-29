#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nexus_progression.py — Carnet de progression NEXUS (brique 1, version minuscule).

Mode "dictée" : l'utilisateur remplit le journal par des commandes.
Pas de détection automatique, pas de %, pas de dépendances. Volontairement minimal.

Stockage : progression/journal.jsonl (une brique par ligne).
Chaque ligne a EXACTEMENT 5 champs : projet, brique, statut, origine, date.
"""

import argparse
import json
import os
from datetime import datetime

# --- Constantes ------------------------------------------------------------

# Dossier et fichier de stockage (relatifs au dossier courant).
DOSSIER = "progression"
JOURNAL = os.path.join(DOSSIER, "journal.jsonl")

# Valeurs autorisées (validation stricte).
STATUTS_OK = ("a_venir", "en_cours", "fait")
ORIGINES_OK = ("createur", "systeme")


# --- Lecture / écriture du journal ----------------------------------------

def lire_journal():
    """Renvoie la liste des briques. Gère fichier vide ou inexistant sans crash."""
    if not os.path.exists(JOURNAL):
        return []
    briques = []
    with open(JOURNAL, "r", encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue  # on ignore les lignes vides
            briques.append(json.loads(ligne))
    return briques


def ecrire_journal(briques):
    """Réécrit tout le journal à partir de la liste (crée le dossier si besoin)."""
    os.makedirs(DOSSIER, exist_ok=True)
    with open(JOURNAL, "w", encoding="utf-8") as f:
        for b in briques:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")


# --- Commandes -------------------------------------------------------------

def cmd_ajouter(args):
    """Ajoute une brique au journal. La date est posée automatiquement."""
    # Validation des valeurs fermées.
    if args.statut not in STATUTS_OK:
        print(f"Erreur : statut '{args.statut}' invalide. Choix : {', '.join(STATUTS_OK)}.")
        return
    if args.origine not in ORIGINES_OK:
        print(f"Erreur : origine '{args.origine}' invalide. Choix : {', '.join(ORIGINES_OK)}.")
        return

    brique = {
        "projet": args.projet,
        "brique": args.brique,
        "statut": args.statut,
        "origine": args.origine,
        "date": datetime.now().isoformat(timespec="seconds"),
    }
    briques = lire_journal()
    briques.append(brique)
    ecrire_journal(briques)
    print(f"Ajouté : {args.projet} / {args.brique} [{args.statut}, {args.origine}]")


def cmd_maj(args):
    """Met à jour le statut d'une brique existante (même projet + même brique)."""
    if args.statut not in STATUTS_OK:
        print(f"Erreur : statut '{args.statut}' invalide. Choix : {', '.join(STATUTS_OK)}.")
        return

    briques = lire_journal()
    trouvee = False
    for b in briques:
        if b["projet"] == args.projet and b["brique"] == args.brique:
            ancien = b["statut"]
            b["statut"] = args.statut
            trouvee = True
            print(f"Mis à jour : {args.projet} / {args.brique} : {ancien} -> {args.statut}")
            break

    if not trouvee:
        print(f"Introuvable : aucune brique '{args.brique}' dans le projet '{args.projet}'.")
        return

    ecrire_journal(briques)


def _afficher_tableau(briques):
    """Affiche un tableau lisible + un petit compte par statut."""
    if not briques:
        print("(aucune brique)")
        return

    # Largeurs de colonnes adaptées au contenu.
    l_brique = max([len("brique")] + [len(b["brique"]) for b in briques])
    l_statut = max([len("statut")] + [len(b["statut"]) for b in briques])
    l_origine = max([len("origine")] + [len(b["origine"]) for b in briques])

    entete = f"{'brique':<{l_brique}} | {'statut':<{l_statut}} | {'origine':<{l_origine}} | date"
    print(entete)
    print("-" * len(entete))
    for b in briques:
        print(f"{b['brique']:<{l_brique}} | {b['statut']:<{l_statut}} | "
              f"{b['origine']:<{l_origine}} | {b['date']}")

    # Compte par statut, dans l'ordre logique.
    comptes = []
    for s in STATUTS_OK:
        n = sum(1 for b in briques if b["statut"] == s)
        comptes.append(f"{s}: {n}")
    print("  ".join(comptes))


def cmd_etat(args):
    """Affiche l'état des briques. Filtre par projet si demandé, sinon groupe par projet."""
    briques = lire_journal()
    if not briques:
        print("Journal vide.")
        return

    if args.projet:
        filtrees = [b for b in briques if b["projet"] == args.projet]
        print(f"=== Projet : {args.projet} ===")
        _afficher_tableau(filtrees)
    else:
        # Groupé par projet (ordre d'apparition).
        projets = []
        for b in briques:
            if b["projet"] not in projets:
                projets.append(b["projet"])
        for p in projets:
            print(f"=== Projet : {p} ===")
            _afficher_tableau([b for b in briques if b["projet"] == p])
            print()


# --- Point d'entrée CLI ----------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Carnet de progression NEXUS (minimal).")
    sous = parser.add_subparsers(dest="commande", required=True)

    # ajouter
    p_add = sous.add_parser("ajouter", help="Ajouter une brique.")
    p_add.add_argument("--projet", required=True)
    p_add.add_argument("--brique", required=True)
    p_add.add_argument("--statut", required=True)
    p_add.add_argument("--origine", required=True)
    p_add.set_defaults(func=cmd_ajouter)

    # maj
    p_maj = sous.add_parser("maj", help="Mettre à jour le statut d'une brique.")
    p_maj.add_argument("--projet", required=True)
    p_maj.add_argument("--brique", required=True)
    p_maj.add_argument("--statut", required=True)
    p_maj.set_defaults(func=cmd_maj)

    # etat
    p_etat = sous.add_parser("etat", help="Afficher l'état des briques.")
    p_etat.add_argument("--projet", required=False)
    p_etat.set_defaults(func=cmd_etat)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
