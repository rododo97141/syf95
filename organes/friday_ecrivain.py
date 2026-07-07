#!/usr/bin/env python3
"""
NEXUS — Friday · brique 2+ : écrivain mémoire piloté par la voix
« Écrire seulement après relecture — et une seule fois. »

Brique 1 (PR #50) = boucle vocale LECTURE SEULE. Brique 2+ ajoute l'unique
capacité d'ÉCRIRE en mémoire : une note ou une tâche, mise en STAGING
(`memory_api.stage` → étage `en_attente/`), JAMAIS en écriture directe
(`memorize`), JAMAIS ailleurs. Trois fonctions cœur, et une SEULE porte vers
stage() dans tout Friday : `confirmer_ecriture`.

Pourquoi une relecture OBLIGATOIRE et BLOQUANTE ? Constat vérifié dans le code
réel de la mémoire : `memory_api.recall({"scope": ["all"]})` (le défaut) scanne
`structure` + `en_attente` + `brut` sans aucun filtre de type « promu » — il
n'existe pas de « sas » au staging. Une fiche stagée reste donc lisible comme un
fait par n'importe quel appelant de recall() TANT QU'ELLE N'A PAS ÉTÉ PROMUE
(promote() la retire alors de `en_attente` pour l'écrire dans `structure`).
Autrement dit, stager = déjà exposer. La relecture bloquante COMPENSE ce défaut
réel du système de mémoire (elle ne le corrige pas — corriger recall() est un
chantier mémoire séparé, hors de ce mandat ; nexus_memfs/memory_api n'est pas
touché ici).

Frontière POSTE / cœur logique : le mot d'éveil (trigger vocal) est détecté
CÔTÉ POSTE (matériel / détection vocale). Le cœur logique ne le détecte pas : il
reçoit `trigger_present: bool` et fait confiance à ce qu'on lui donne. Le
mécanisme de trigger reste à construire côté poste (hors de ce mandat).

Mémoire injectée (même patron que backend/orchestrateur.executer_tache :
`memoire=None` → import paresseux de la VRAIE mémoire-beta ; les tests injectent
une instance isolée). Aucun `importlib` : import direct via sys.path — cohérent
avec l'exclusion de la zone 3 (voir la garde AST dans les tests).
"""
import os
import sys
import secrets

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import friday_routeur          # vocabulaire fermé partagé avec la brique 1
import nexus_sense             # côté ÉCRITURE de la force vivante (comme friday_coeur)


# --------------------------------------------------------------------------- #
# Mémoire injectée — import paresseux de memory_api (mémoire-beta), en mode
# bibliothèque. MÊME patron que backend/orchestrateur._memoire_api_defaut :
# sys.path + `import memory_api`, JAMAIS importlib (interdit zone 3). Retourne
# None si indisponible.
# --------------------------------------------------------------------------- #
def _memoire_api_defaut():
    try:
        _scripts = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # organes/ → racine
            ".claude", "skills", "memoire-beta", "scripts",
        )
        if _scripts not in sys.path:
            sys.path.insert(0, _scripts)
        import memory_api
        return memory_api
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Brouillon + registre des jetons — EN MÉMOIRE DU PROCESS, jamais sur disque.
# --------------------------------------------------------------------------- #
class Brouillon:
    """Une écriture PRÉPARÉE mais pas encore confirmée. Porte son jeton d'usage
    unique. Rien ici ne touche le disque : un brouillon vit en mémoire jusqu'à
    ce que `confirmer_ecriture` (avec le bon jeton) le mette en staging, ou que
    `annuler_ecriture` le referme."""
    __slots__ = ("intention", "contenu", "domain", "category", "title",
                 "certain", "jeton")

    def __init__(self, intention, contenu, domain, category, title, certain, jeton):
        self.intention = intention      # "note" | "tache"
        self.contenu = contenu
        self.domain = domain
        self.category = category
        self.title = title
        self.certain = certain          # True si trigger vocal explicite présent
        self.jeton = jeton


# Registre { jeton -> Brouillon } : en mémoire du process, JAMAIS persisté.
# Un jeton n'y figure que tant qu'il est valide et non consommé.
_REGISTRE = {}

_DESTINATIONS = {
    "note": ("friday", "notes"),
    "tache": ("friday", "taches"),
}


def preparer_ecriture(texte, trigger_present):
    """texte transcrit + `trigger_present` (bool, fourni par le POSTE) → un
    Brouillon, ou None.

    DÉCLENCHEUR PUR : sans trigger vocal explicite, preparer_ecriture ne produit
    AUCUN brouillon (retourne None) — exactement comme un texte hors
    vocabulaire. Une phrase note/tâche captée sans mot d'éveil ne s'adresse
    pas forcément à Friday : on ne fabrique donc pas un brouillon « incertain »
    à rattraper en aval, on ne fabrique rien. (Le marquage certain/incertain et
    la logique silence≠accord de traiter_relecture restent néanmoins en place
    comme défense en profondeur, au cas où un Brouillon incertain viendrait d'un
    autre chemin — mais ce chemin-ci ne les alimente plus.)

    PUR aussi au sens disque : ne touche RIEN sur le disque (prouvé par test).
    N'appelle jamais stage(). Génère un jeton d'usage unique non forgeable
    (secrets) et l'enregistre en mémoire du process."""
    if not trigger_present:
        return None                            # déclencheur pur : pas de trigger → aucun brouillon
    resultat = friday_routeur.router(texte)
    intention, argument = resultat["intention"], resultat["argument"]
    if intention not in _DESTINATIONS or not argument:
        return None
    contenu = argument.strip()
    if not contenu:
        return None
    domain, category = _DESTINATIONS[intention]
    title = contenu[:60].strip() or ("note vocale" if intention == "note" else "tâche vocale")
    jeton = secrets.token_urlsafe(32)          # non forgeable, à usage unique
    brouillon = Brouillon(intention, contenu, domain, category, title,
                          bool(trigger_present), jeton)  # certain=True (trigger présent)
    _REGISTRE[jeton] = brouillon               # registre EN MÉMOIRE, pas sur disque
    return brouillon


def confirmer_ecriture(brouillon, jeton, memoire=None):
    """LA SEULE porte vers stage() de tout Friday (garde AST : un seul point
    d'appel de stage() dans la codebase). Met le brouillon en STAGING
    (`memoire.stage`, étage `en_attente/`, champ source="voix") UNIQUEMENT si :
      - le jeton correspond EXACTEMENT au brouillon qui l'a émis, ET
      - le jeton n'a pas déjà été consommé (usage unique : un replay échoue).
    Un jeton absent/erroné/rejoué est REFUSÉ et n'écrit rien.

    `memoire=None` (défaut) → import paresseux de la vraie mémoire-beta ; les
    tests injectent une mémoire isolée (aucun disque touché)."""
    attendu = _REGISTRE.get(jeton)
    if (brouillon is None or attendu is None
            or attendu is not brouillon or brouillon.jeton != jeton):
        # jeton absent, erroné, ou déjà consommé (replay) → aucune écriture
        return {"ok": False, "ecrit": False,
                "raison": "jeton invalide, absent ou déjà consommé"}

    if memoire is None:
        memoire = _memoire_api_defaut()
    if memoire is None:
        # mémoire indisponible : on n'écrit pas ET on NE consomme PAS le jeton
        # (une nouvelle tentative reste possible) — fail-closed.
        return {"ok": False, "ecrit": False, "raison": "mémoire indisponible"}

    resultat = memoire.stage({
        "content": brouillon.contenu,
        "domain": brouillon.domain,
        "category": brouillon.category,
        "title": brouillon.title,
        "source": "voix",              # champ déjà présent dans le schéma de stage
        "origin": "friday:ecriture",
    })
    del _REGISTRE[jeton]               # succès → jeton consommé (un replay échouera)
    return {"ok": True, "ecrit": True, "staging": resultat}


def annuler_ecriture(brouillon):
    """Referme un brouillon sans rien écrire, et journalise UN capteur
    nexus_sense tache="friday:ecriture" statut="ok". JAMAIS "echec" : un
    refus/une annulation n'est pas un échec, c'est le fonctionnement NORMAL du
    garde-fou (même doctrine que le logger, PR #58)."""
    if brouillon is not None:
        _REGISTRE.pop(brouillon.jeton, None)   # invalide le jeton : plus aucune écriture possible
    nexus_sense.log_event(tache="friday:ecriture", statut="ok", mode="auto",
                          note="annulation/refus (garde-fou normal, aucune écriture)")
    return {"ok": True, "ecrit": False}


# --------------------------------------------------------------------------- #
# Relecture OBLIGATOIRE et BLOQUANTE — jamais « annoncer puis écrire ».
# --------------------------------------------------------------------------- #
AFFIRMATIONS = {"oui", "ok", "okay", "d accord", "vas y", "confirme", "confirmer",
                "valide", "valider", "c est bon", "enregistre", "enregistrer"}
REFUS_ORAL = {"non", "annule", "annuler", "laisse", "laisse tomber", "oublie",
              "oublier", "stop", "efface", "abandonne"}


def annoncer(brouillon):
    """Le texte de RELECTURE à lire à voix haute avant toute écriture.
    certain=True → annonce puis silence=accord (voir traiter_relecture) ;
    certain=False → demande une confirmation orale explicite."""
    quoi = "note" if brouillon.intention == "note" else "tâche"
    if brouillon.certain:
        return (f"J'ai préparé une {quoi} : « {brouillon.contenu} ». "
                f"Sans réaction de ta part, je l'enregistre.")
    return (f"J'ai peut-être capté une {quoi} : « {brouillon.contenu} ». "
            f"Dois-je l'enregistrer ? Dis « oui » pour confirmer.")


def traiter_relecture(brouillon, reponse_orale="", silence=False, memoire=None):
    """Décision de relecture. `reponse_orale` = ce que le POSTE a transcrit en
    réponse (vide si rien) ; `silence` = le délai fixe s'est écoulé sans réaction.

    Règle silence=accord — UNIQUEMENT pour certain=True (trigger vocal explicite
    présent) : oui explicite OU silence après le délai → on confirme.
    certain=False (pas de trigger) : SEUL un « oui » explicite écrit ; le silence
    ne vaut jamais accord (une phrase captée dans une conversation qui ne
    s'adresse pas à Friday ne doit pas être écrite au motif que Kily n'a pas
    réagi). Un refus oral explicite annule dans les deux cas."""
    if brouillon is None:
        return {"ok": False, "raison": "aucun brouillon"}
    reponse = friday_routeur.normaliser(reponse_orale)
    if reponse in REFUS_ORAL:
        return annuler_ecriture(brouillon)                     # refus explicite → annulation
    consent = reponse in AFFIRMATIONS
    if brouillon.certain:
        if consent or (silence and not reponse):               # oui, OU silence après le délai
            return confirmer_ecriture(brouillon, brouillon.jeton, memoire=memoire)
        return {"ok": False, "en_attente": True}               # ni oui ni silence écoulé : on attend
    # certain=False : le silence ne vaut PAS accord — il faut un « oui »
    if consent:
        return confirmer_ecriture(brouillon, brouillon.jeton, memoire=memoire)
    return annuler_ecriture(brouillon)                         # silence / pas de oui → aucune écriture


def apercu(texte):
    """Accusé de réception PARLÉ (lecture seule, sans jeton, sans disque) d'une
    commande note/tâche entendue par le cœur brique 1. Le cycle complet
    preparer → relecture → confirmer/annuler est piloté par le POSTE via ce
    module ; le cœur, lui, ne fait que diriger la commande hors du chemin de
    lecture et rappeler que rien n'est écrit sans relecture. Renvoie None si le
    texte n'est pas une commande d'écriture."""
    resultat = friday_routeur.router(texte)
    intention, argument = resultat["intention"], resultat["argument"]
    if intention not in _DESTINATIONS or not argument:
        return None
    quoi = "note" if intention == "note" else "tâche"
    return (f"J'ai entendu une {quoi} : « {argument} ». "
            f"Je ne l'enregistre qu'après relecture et confirmation.")
