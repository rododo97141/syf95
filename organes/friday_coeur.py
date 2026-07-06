#!/usr/bin/env python3
"""
NEXUS — Friday · brique 1 : cœur (LA frontière texte→texte)
« Une ligne entre, une phrase sort — ou rien. »

traiter_ligne(texte) -> reponse_texte | None  est LA couture avec le poste
micro/TTS : AUCUNE dépendance audio dans syf95, le matériel reste côté poste.
Le cœur est donc testable sans micro, une ligne de texte à la fois.

Chaîne : routeur (règles, vocabulaire fermé) → lecteur (lecture seule par
construction) → réponse texte prête pour un TTS. Bruit ambiant → REFUS du
routeur → aucune action du lecteur, réponse None.

FORCE VIVANTE : chaque ligne traitée logue UN capteur via nexus_sense.log_event
(tache friday:<intention>, statut ok/refus) — Friday joue dans la même ligue
que les autres organes, sa force se mesurera comme les leurs. Le capteur est
câblé ICI et jamais dans le lecteur : log_event écrit, le lecteur n'écrit pas.

Usage :
  python3 friday_coeur.py "montre nexus_sense.py"   # une commande
  echo "statut" | python3 friday_coeur.py           # ou des lignes sur stdin
"""
import os, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import friday_routeur
import friday_lecteur
import nexus_sense  # côté ÉCRITURE de la force vivante — jamais importé par le lecteur


def traiter_ligne(texte, racine=None):
    """LA frontière texte→texte : ligne transcrite → réponse à lire, ou None.
    racine (optionnelle) pointe le lecteur sur un autre dépôt — les tests
    s'isolent ainsi, même doctrine que CAPTEURS_ROOT."""
    resultat = friday_routeur.router(texte)
    intention, argument = resultat["intention"], resultat["argument"]
    if intention == friday_routeur.REFUS:
        nexus_sense.log_event(tache="friday:refus", statut="refus", mode="auto")
        return None
    if intention == "statut":
        reponse = friday_lecteur.statut(racine=racine)
    elif intention == "montre":
        reponse = friday_lecteur.montrer(argument, racine=racine)
    elif intention == "ou_est":
        reponse = friday_lecteur.chercher(argument, racine=racine)
    else:  # explique — vocabulaire fermé, le routeur ne renvoie rien d'autre
        reponse = friday_lecteur.expliquer(argument, racine=racine)
    nexus_sense.log_event(tache=f"friday:{intention}", statut="ok", mode="auto",
                          note=argument)
    return reponse


def main():
    if len(sys.argv) > 1:
        reponse = traiter_ligne(" ".join(sys.argv[1:]))
        if reponse is not None:
            print(reponse)
        return
    for ligne in sys.stdin:
        reponse = traiter_ligne(ligne)
        if reponse is not None:
            print(reponse)


if __name__ == "__main__":
    main()
