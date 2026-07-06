#!/usr/bin/env python3
"""
NEXUS — Agent OS, brique 4 : orchestrateur ACTIF (routage par force vivante)
« Il route vers le plus fort DISPONIBLE ; il observe la fiabilité, mais ne la
laisse JAMAIS décider. »

Suite de Shu/Ha/Ri (colonne vertébrale + adaptateurs réels + vues lecture
seule, déjà mergés). Cette brique route une tâche vers le MEILLEUR agent
DISPONIBLE parmi ceux qui DÉCLARENT le rôle demandé, mesuré par la FORCE
VIVANTE (forces.json, en LECTURE SEULE via nexus_force). Elle journalise en
plus une FIABILITÉ mécanique dans un fichier SÉPARÉ qui n'influence AUCUNE
décision de routage.

choisir_agent(role, adaptateurs, forces, rng_ou_compteur) — SANS paramètre
fiabilité, ne lit QUE `forces` :
  0. filtre les adaptateurs qui déclarent le rôle (roles()) ; aucun → ERREUR
     claire (ValueError), jamais un silence ;
  1. EXPLORATION : avec une petite probabilité ε (paramétrable, portée par
     rng_ou_compteur), route vers l'agent LE MOINS APPELÉ du rôle (compteur
     d'appels) — la chance au nouveau et à l'oublié ;
  2. sinon EXPLOITATION : score chaque candidat par sa force vivante
     (_force_de(forces, nom) — même pattern PROUVÉ que nexus_bureau_agentos,
     lecture seule sur forces.json), le PLUS FORT gagne ; égalité → round-robin
     entre égaux (le moins appelé d'entre eux, PAS le premier enregistré).

FRONTIÈRE DURE avec la force réelle (verrous du mandat) :
  - ce module ne calcule ni n'écrit JAMAIS la force : nexus_force (le pont)
    reste le SEUL écrivain de forces.json ; ici, tout est LECTURE SEULE ;
  - la FIABILITÉ observée (réponse / exception / timeout) est journalisée dans
    un fichier SÉPARÉ (fiabilite_agents.json), que choisir_agent ne relit
    JAMAIS — aucun chemin de la fiabilité vers une décision de routage.

Le nom `rng_ou_compteur` dit sa nature : une politique d'exploration qui tire ε
soit d'un compteur DÉTERMINISTE (tests reproductibles, round-robin mesurable),
soit d'un vrai random.Random injecté (production). Voir CompteurExploration.
"""
import os
import sys
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import nexus_force  # forces vivantes (forces.json) — LECTURE SEULE, jamais écrit

# ε par défaut si CompteurExploration n'en reçoit pas : petit (« petite
# probabilité »), paramétrable au constructeur — jamais dans choisir_agent.
EPSILON_DEFAUT = 0.1

# Issues mécaniques observées par la boucle d'observation (design point 3).
ISSUES = ("reponse", "exception", "timeout")

# Fichier de fiabilité — SÉPARÉ de forces.json, jamais relu pour router.
FIABILITE_FICHIER = "fiabilite_agents.json"


# --------------------------------------------------------------------------- #
# Lecture de la force vivante — pattern PROUVÉ, réutilisé, LECTURE SEULE
# --------------------------------------------------------------------------- #
def charger_forces():
    """forces.json en LECTURE SEULE (dict {agent: multiplicateur}), via le
    loader du pont nexus_force (respecte MEMOIRE_ROOT, absent → {}). Le pont
    reste seul écrivain : ici on ne fait QUE lire."""
    return nexus_force._lire_forces_existantes()


def _force_de(forces, nom):
    """Force vivante d'un agent par son nom — MÊME pattern que
    nexus_bureau_agentos._force_de (valeur numérique validée, arrondie à 4,
    défaut hérité de nexus_force.FORCE_DEFAUT quand l'agent n'a pas d'entrée).

    Anti-invention de valeur : sans donnée de force, on rend la force NEUTRE
    1.0 de nexus_force — jamais une valeur inventée ici."""
    valeur = forces.get(nom)
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
        return round(float(valeur), 4)
    return nexus_force.FORCE_DEFAUT


def _roles_de(adaptateur):
    """Rôles déclarés par un adaptateur, robuste : roles() → liste (défaut []).
    Un adaptateur d'avant la brique 4 (sans roles()) ne déclare rien."""
    fn = getattr(adaptateur, "roles", None)
    if callable(fn):
        rs = fn()
        return list(rs) if rs else []
    return []


# --------------------------------------------------------------------------- #
# rng_ou_compteur : politique d'exploration ε + mémoire des appels
# --------------------------------------------------------------------------- #
class CompteurExploration:
    """Le `rng_ou_compteur` de choisir_agent : porte ε ET la mémoire des appels.

    - epsilon  : petite probabilité d'exploration (PARAMÉTRABLE ici, jamais
      dans la signature de choisir_agent).
    - appels   : {nom_agent: nombre de fois routé} — sert au « moins appelé »
      (exploration) ET au round-robin entre égaux (exploitation).
    - source du tirage ε :
        * DÉTERMINISTE par défaut (compteur interne) : exactement une
          exploration tous les round(1/ε) appels — tests reproductibles,
          round-robin MESURABLE, borne quantitative du « chance au nouveau » ;
        * un random.Random injecté en `alea` → vrai hasard en production
          (« rng OU compteur »).
    """

    def __init__(self, epsilon=EPSILON_DEFAUT, alea=None):
        self.epsilon = float(epsilon)
        self.alea = alea
        self.appels = {}
        self._tick = 0

    def explorer(self):
        """True si CE routage doit explorer (ε), False s'il doit exploiter."""
        self._tick += 1
        if self.epsilon <= 0:
            return False
        if self.alea is not None:
            return self.alea.random() < self.epsilon
        periode = max(1, round(1.0 / self.epsilon))
        return (self._tick % periode) == 0

    def enregistrer(self, nom):
        """Compte un appel routé vers `nom` (met à jour le round-robin)."""
        self.appels[nom] = self.appels.get(nom, 0) + 1


def _moins_appele(candidats, rng_ou_compteur):
    """L'agent le moins appelé parmi `candidats` (compteur d'appels de
    rng_ou_compteur). `min` est STABLE : à égalité de compteur, il rend le
    PREMIER dans l'ordre donné — ce qui, une fois l'élu incrémenté, fait
    tourner le choix (round-robin, PAS toujours le premier enregistré)."""
    appels = getattr(rng_ou_compteur, "appels", {}) or {}
    return min(candidats, key=lambda a: appels.get(a.nom(), 0))


# --------------------------------------------------------------------------- #
# LE routage : choisir_agent — ne lit QUE `forces`, jamais la fiabilité
# --------------------------------------------------------------------------- #
def choisir_agent(role, adaptateurs, forces, rng_ou_compteur):
    """Route une tâche du rôle `role` vers le meilleur agent DISPONIBLE.

    role            : capacité demandée (str) ;
    adaptateurs     : liste d'objets NexusAdapter (roles() déclare leurs rôles) ;
    forces          : dict {agent: multiplicateur} déjà chargé (LECTURE SEULE) ;
    rng_ou_compteur : politique d'exploration ε + mémoire des appels
                      (CompteurExploration ou compatible).

    AUCUN paramètre fiabilité : cette fonction ne lit QUE `forces`. La fiabilité
    journalisée ailleurs n'entre JAMAIS ici (vérifié par test structurel et par
    test d'anti-régression comportemental).

    Renvoie l'adaptateur élu. Lève ValueError si AUCUN agent ne déclare le rôle
    — erreur claire, jamais un silence."""
    candidats = [a for a in adaptateurs if role in _roles_de(a)]
    if not candidats:
        raise ValueError(
            f"aucun agent ne déclare le rôle {role!r} : routage impossible "
            f"(déclarez roles() incluant {role!r} sur au moins un adaptateur)")

    # Étape 1 — EXPLORATION ε : la chance au moins appelé (nouveau / oublié).
    if rng_ou_compteur is not None and rng_ou_compteur.explorer():
        choisi = _moins_appele(candidats, rng_ou_compteur)
    else:
        # Étape 2 — EXPLOITATION : la force vivante décide, le plus fort gagne.
        meilleure = max(_force_de(forces, a.nom()) for a in candidats)
        egaux = [a for a in candidats
                 if _force_de(forces, a.nom()) == meilleure]
        # Égalité → round-robin entre égaux (le moins appelé d'entre eux).
        choisi = _moins_appele(egaux, rng_ou_compteur)

    if rng_ou_compteur is not None:
        rng_ou_compteur.enregistrer(choisi.nom())
    return choisi


# --------------------------------------------------------------------------- #
# Boucle d'observation : fiabilité MÉCANIQUE, dans un fichier SÉPARÉ
# --------------------------------------------------------------------------- #
# NOTE FRONTIÈRE : rien ci-dessous n'est jamais appelé par choisir_agent. La
# fiabilité est un journal d'observabilité, coupé du routage par conception.
def _chemin_fiabilite():
    """Chemin du journal de fiabilité — SÉPARÉ de forces.json, même racine
    mémoire (respecte MEMOIRE_ROOT via nexus_force._racine_memoire)."""
    return os.path.join(nexus_force._racine_memoire(), FIABILITE_FICHIER)


def _lire_fiabilite_brut():
    try:
        with open(_chemin_fiabilite(), encoding="utf-8") as f:
            data = json.load(f)
        return dict(data) if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def journaliser_fiabilite(nom, issue):
    """Journalise UNE issue mécanique (réponse / exception / timeout) pour
    l'agent `nom`, dans le fichier SÉPARÉ fiabilite_agents.json. N'écrit JAMAIS
    dans forces.json (nexus_force reste seul écrivain de la force réelle) et
    n'est JAMAIS relu par choisir_agent. Renvoie le compteur de l'agent."""
    if issue not in ISSUES:
        raise ValueError(f"issue inconnue : {issue!r} (attendu {ISSUES})")
    data = _lire_fiabilite_brut()
    entree = data.get(nom)
    if not isinstance(entree, dict):
        entree = {i: 0 for i in ISSUES}
    entree[issue] = int(entree.get(issue, 0)) + 1
    data[nom] = entree
    chemin = _chemin_fiabilite()
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
    return entree


def lire_fiabilite(nom=None):
    """Lecture d'OBSERVABILITÉ seulement (jamais appelée par choisir_agent) :
    tout le journal, ou l'entrée d'un agent (défaut zéro si absent)."""
    data = _lire_fiabilite_brut()
    if nom is None:
        return data
    entree = data.get(nom)
    return dict(entree) if isinstance(entree, dict) else {i: 0 for i in ISSUES}


def observer(nom, action):
    """Boucle d'observation : exécute `action()` (l'appel réel à l'agent) et
    journalise l'issue MÉCANIQUE — reponse / exception / timeout — SANS jamais
    influencer un futur routage. Renvoie (issue, valeur_ou_exception).

    Un TimeoutError est classé « timeout » ; toute autre exception « exception » ;
    un retour normal « reponse ». L'exception n'est pas relancée : l'observation
    ne casse pas la boucle appelante (elle observe, elle ne décide de rien)."""
    try:
        valeur = action()
    except TimeoutError as exc:
        journaliser_fiabilite(nom, "timeout")
        return "timeout", exc
    except Exception as exc:  # noqa: BLE001 — on observe TOUTE défaillance
        journaliser_fiabilite(nom, "exception")
        return "exception", exc
    journaliser_fiabilite(nom, "reponse")
    return "reponse", valeur
