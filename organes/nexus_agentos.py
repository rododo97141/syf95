#!/usr/bin/env python3
"""
NEXUS — Agent OS, orchestrateur minimal (brique 1, phase SHU)
« Il route, il n'altère pas. »

router(bus, adaptateurs) : UNE passe NON bloquante sur la colonne
vertébrale (nexus_bus) —
  1. lit les nouveaux messages depuis l'offset donné (lire_depuis) ;
  2. les remet au destinataire nommé, ou à TOUS les adaptateurs sauf
     l'expéditeur si destinataire = "*" (broadcast) ;
  3. publie sur le bus les réponses renvoyées par les adaptateurs,
     VERBATIM — l'orchestrateur route, il n'altère jamais le contenu.

Deux adaptateurs peuvent ainsi s'adresser en pair-à-pair (destinataire
nommé) : A publie une demande pour B, une passe la remet à B et publie sa
réponse, la passe suivante remet la réponse à A. Les réponses publiées
pendant une passe sont des messages comme les autres : elles sont remises
à la passe SUIVANTE (non bloquant — jamais de boucle d'attente ici).

L'orchestrateur ne connaît que l'interface NexusAdapter (nom(),
sur_message(msg)) — jamais le fournisseur d'IA derrière (la frontière,
cf. nexus_adaptateur).

Brique 4 — AJOUT PUR d'un 3e mode de destinataire, "role:<capacité>", à côté
des modes existants (nommé et étoile), RÉTROCOMPATIBLE : nommé et étoile sont
strictement inchangés. Sur "role:<capacité>", le routage délègue à
nexus_orchestrateur.choisir_agent (routage par force vivante, LECTURE SEULE) le
choix du meilleur agent DISPONIBLE déclarant ce rôle, puis lui remet le message
avec l'enveloppe résolue à son nom (le CONTENU reste verbatim). Les paramètres
`forces`/`exploration` sont optionnels : absents, `forces` est chargé en lecture
seule depuis forces.json et une politique d'exploration fraîche est créée — un
appelant qui veut du round-robin persistant entre passes fournit la sienne.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import nexus_orchestrateur  # routage par force vivante (brique 4)
import nexus_budget          # budget d'échanges par vie du fil (le couteau)

PREFIXE_ROLE = "role:"


def router(bus, adaptateurs, offset=0, forces=None, exploration=None,
           budget=None):
    """UNE passe de routage non bloquante.

    bus         : module/objet exposant lire_depuis(offset) et publier(msg)
                  (nexus_bus) ;
    adaptateurs : liste d'objets NexusAdapter ;
    offset      : position de lecture atteinte à la passe précédente ;
    forces      : (brique 4) dict {agent: force} pour le mode "role:", ou None
                  → chargé en LECTURE SEULE depuis forces.json au 1er besoin ;
    exploration : (brique 4) politique d'exploration ε (CompteurExploration) ou
                  None → une politique fraîche est créée au 1er besoin ;
    budget      : budget d'échanges par VIE du fil (nexus_budget.BudgetFils) ou
                  None → un budget frais est créé pour cette passe. Comme pour
                  `exploration`, un appelant qui veut BORNER une conversation à
                  travers plusieurs passes/cycles fournit LE SIEN (persistant) :
                  c'est ce qui rend le budget « par vie » et non « par passe ».
                  Au plafond du fil (ou sur stagnation), le message n'est plus
                  remis et un capteur de coupure NEUTRE est journalisé ; SOUS le
                  budget, le routage (nommé/étoile/rôle) reste STRICTEMENT
                  byte-identique.

    Renvoie (reponses_publiees, nouvel_offset) — repasser nouvel_offset à
    l'appel suivant pour ne router que le neuf (tail-since-offset)."""
    par_nom = {a.nom(): a for a in adaptateurs}
    messages, nouvel_offset = bus.lire_depuis(offset)
    reponses = []
    _forces = forces            # résolus PARESSEUSEMENT, seulement si "role:"
    _exploration = exploration  # apparaît (passes nommé/étoile inchangées)
    _budget = budget if budget is not None else nexus_budget.BudgetFils()
    for msg in messages:
        # Le couteau, à la FRONTIÈRE du message (avant toute remise) : au
        # plafond du fil, on ne remet plus (coupure journalisée). Sous le
        # budget, la suite est inchangée — byte-identique.
        if not _budget.admettre(msg).admis:
            continue
        destinataire = msg.get("destinataire")
        msg_livre = msg  # par défaut : verbatim (nommé/étoile inchangés)
        if destinataire == "*":  # broadcast : tous sauf l'expéditeur
            cibles = [a for nom, a in par_nom.items()
                      if nom != msg.get("expediteur")]
        elif isinstance(destinataire, str) and destinataire.startswith(PREFIXE_ROLE):
            # Brique 4 : routage par force vivante vers le meilleur agent du rôle.
            if _forces is None:
                _forces = nexus_orchestrateur.charger_forces()  # LECTURE SEULE
            if _exploration is None:
                _exploration = nexus_orchestrateur.CompteurExploration()
            role = destinataire[len(PREFIXE_ROLE):]
            cible = nexus_orchestrateur.choisir_agent(
                role, adaptateurs, _forces, _exploration)
            cibles = [cible]
            # Enveloppe résolue au nom concret de l'élu (le CONTENU, lui, reste
            # verbatim) pour que sur_message reconnaisse le message comme sien.
            msg_livre = dict(msg, destinataire=cible.nom())
        else:  # pair-à-pair : le destinataire nommé, s'il est branché
            cible = par_nom.get(destinataire)
            cibles = [cible] if cible is not None else []
        for adaptateur in cibles:
            reponse = adaptateur.sur_message(msg_livre)
            if reponse is not None:
                reponses.append(bus.publier(reponse))  # VERBATIM, jamais altéré
    return reponses, nouvel_offset
