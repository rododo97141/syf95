#!/usr/bin/env python3
"""
NEXUS — Adaptateur d'agent (la FRONTIÈRE de l'Agent OS, brique 1)
« Le hub connaît l'interface, jamais le fournisseur. »

NexusAdapter est LA frontière de l'Agent OS : le bus et l'orchestrateur ne
voient que cette interface — nom() et sur_message(msg) — jamais le
fournisseur d'IA derrière. Brancher une vraie IA externe (phase Ha) se fera
en écrivant un nouvel adaptateur, sans toucher à la colonne vertébrale.

En brique 1 (phase SHU), AUCUNE IA externe réelle : AdaptateurLoopback est
un agent MOCK déterministe (des règles contenu → contenu) qui prouve la
boucle de messagerie de bout en bout.

Dual-mode STRICT, les DEUX testés :
  - mode SOLO    : sur_message(msg) traite un message SANS bus et renvoie
    la réponse (ou None) — l'adaptateur marche seul ;
  - mode BRANCHÉ : pomper(bus) s'abonne au bus via lire_depuis (offset
    propre à l'adaptateur), traite les nouveaux messages qui lui sont
    adressés et PUBLIE ses réponses sur le bus.
Le même adaptateur répond PAREIL dans les deux modes (prouvé par test).
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import nexus_bus  # schéma des messages + BROADCAST (source UNIQUE)


class NexusAdapter:
    """Interface commune de tout agent branché sur l'Agent OS.

    C'est LA frontière : le hub ne connaît que ces deux méthodes, jamais le
    fournisseur d'IA. Tout adaptateur doit fournir :
      - nom()            → str : identité de l'agent sur le bus ;
      - sur_message(msg) → msg | None : traite UN message (schéma
        nexus_bus), renvoie un message de réponse ou None (silence).

    roles() est un AJOUT PUR (brique 4) : la liste des capacités que l'agent
    déclare servir (ex. ["memoire", "resume"]). Défaut = liste vide —
    RÉTROCOMPATIBLE : un adaptateur écrit avant la brique 4 ne déclare aucun
    rôle et reste invisible au routage par rôle (destinataire "role:<capacité>"),
    sans que rien de son comportement nommé/étoile ne change.
    """

    def nom(self):
        raise NotImplementedError("un adaptateur doit fournir nom()")

    def sur_message(self, msg):
        raise NotImplementedError("un adaptateur doit fournir sur_message(msg)")

    def roles(self):
        """Capacités déclarées par l'agent, pour le routage par force vivante
        (brique 4). Défaut : aucune — ajout pur, rétrocompatible."""
        return []


class AdaptateurLoopback(NexusAdapter):
    """Agent MOCK déterministe : prouve la boucle SANS IA externe.

    regles = dict contenu → contenu de réponse. Un message adressé à cet
    adaptateur (destinataire = son nom ou "*") dont le contenu figure dans
    les règles produit UNE réponse (type "reponse", destinataire =
    l'expéditeur d'origine, ref = ts du message d'origine) ; sinon None.
    Déterministe : même message entrant → même réponse, en solo comme en
    branché.

    Garde-fous (déterminisme, pas d'écho infini) :
      - ne répond jamais à ses propres messages ;
      - ne répond jamais à un type "reponse" (une réponse clôt l'échange).

    recus = journal en mémoire des messages qui lui ont été remis (permet
    aux tests de prouver « A reçoit » et « le broadcast atteint tous »).
    """

    def __init__(self, nom, regles, roles=None):
        self._nom = nom
        self._regles = dict(regles)
        self._roles = list(roles) if roles else []  # défaut [] : rétrocompat
        self._offset = 0  # position de lecture propre au mode BRANCHÉ
        self.recus = []

    def nom(self):
        return self._nom

    def roles(self):
        """Rôles déclarés par ce mock (défaut [] : rétrocompatible). Permet aux
        tests de la brique 4 de fabriquer des agents fictifs d'un même rôle."""
        return list(self._roles)

    def sur_message(self, msg):
        """Mode SOLO : traite UN message sans bus, renvoie msg | None."""
        if msg.get("expediteur") == self._nom:
            return None  # jamais d'écho sur ses propres messages
        if msg.get("destinataire") not in (self._nom, nexus_bus.BROADCAST):
            return None  # pas adressé à cet agent
        self.recus.append(msg)
        if msg.get("type") == "reponse":
            return None  # une réponse clôt l'échange (pas de ping-pong)
        contenu = self._regles.get(msg.get("contenu"))
        if contenu is None:
            return None
        return nexus_bus.creer_message(
            expediteur=self._nom,
            destinataire=msg["expediteur"],
            type="reponse",
            contenu=contenu,
            ref=msg.get("ts"),
        )

    def pomper(self, bus):
        """Mode BRANCHÉ : s'abonne au bus via lire_depuis (offset propre),
        traite les nouveaux messages avec la MÊME logique sur_message et
        publie ses réponses sur le bus. Non bloquant : une passe, puis la
        main est rendue. Renvoie la liste des réponses publiées."""
        messages, self._offset = bus.lire_depuis(self._offset)
        reponses = []
        for msg in messages:
            reponse = self.sur_message(msg)
            if reponse is not None:
                reponses.append(bus.publier(reponse))
        return reponses
