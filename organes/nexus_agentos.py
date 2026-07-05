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
"""


def router(bus, adaptateurs, offset=0):
    """UNE passe de routage non bloquante.

    bus         : module/objet exposant lire_depuis(offset) et publier(msg)
                  (nexus_bus) ;
    adaptateurs : liste d'objets NexusAdapter ;
    offset      : position de lecture atteinte à la passe précédente.

    Renvoie (reponses_publiees, nouvel_offset) — repasser nouvel_offset à
    l'appel suivant pour ne router que le neuf (tail-since-offset)."""
    par_nom = {a.nom(): a for a in adaptateurs}
    messages, nouvel_offset = bus.lire_depuis(offset)
    reponses = []
    for msg in messages:
        destinataire = msg.get("destinataire")
        if destinataire == "*":  # broadcast : tous sauf l'expéditeur
            cibles = [a for nom, a in par_nom.items()
                      if nom != msg.get("expediteur")]
        else:  # pair-à-pair : le destinataire nommé, s'il est branché
            cible = par_nom.get(destinataire)
            cibles = [cible] if cible is not None else []
        for adaptateur in cibles:
            reponse = adaptateur.sur_message(msg)
            if reponse is not None:
                reponses.append(bus.publier(reponse))  # VERBATIM, jamais altéré
    return reponses, nouvel_offset
