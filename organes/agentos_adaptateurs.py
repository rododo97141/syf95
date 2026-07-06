#!/usr/bin/env python3
"""
NEXUS — Agent OS, brique 2 (phase HA) : premiers adaptateurs RÉELS
« La forme prouvée (NexusAdapter) s'étend au réel sans se casser. »

La brique 1 (mergée) a livré la colonne vertébrale : nexus_bus (journal
append-only), nexus_adaptateur.NexusAdapter (LA frontière) et
nexus_agentos.router (il route, il n'altère pas). Cette brique 2 branche
les premiers agents réels sur cette colonne, en gardant EXACTEMENT
l'interface prouvée — nom() + sur_message(msg), dual-mode strict — et en
l'étendant au réel sans la casser :

  - AdaptateurMemoire : agent LOCAL réel, sans clé, sans réseau. Sur un
    message type "demande" dont le contenu est une requête texte, il
    interroge la VRAIE mémoire — le recall classé pertinence(IDF) × force
    de mémoire-beta (memory_api.recall, RÉUTILISÉ tel quel, jamais
    réimplémenté) — et répond avec les fiches trouvées (ou "aucune").
    LECTURE SEULE : il n'écrit aucune fiche. Verrou STRUCTUREL : ce
    module ne contient AUCUNE ouverture de fichier en écriture (prouvé
    par test AST) — publier sur le bus est le travail de nexus_bus.

  - AdaptateurLLM : la PRISE pour une IA externe (Claude / GPT / Gemini)
    par INVERSION DE CONTRÔLE : le client d'inférence est INJECTÉ au
    constructeur — un objet exposant completer(prompt) -> str. Le module
    ne crée JAMAIS le client lui-même et ne contient AUCUNE clé. La
    fabrique séparée client_depuis_env(fournisseur) peut construire un
    client réel en lisant la clé dans une variable d'environnement
    fournie par l'utilisateur (ex. OPENAI_API_KEY) — clé ni codée en dur,
    ni stockée ailleurs, ni loggée (repr masqué). Cette fabrique n'est
    appelée par AUCUN test : en CI, AdaptateurLLM est exercé avec un faux
    client déterministe injecté (zéro clé, zéro réseau, zéro coût).

Dual-mode STRICT hérité de la brique 1, les DEUX testés :
  - SOLO    : sur_message(msg) traite un message SANS bus ;
  - BRANCHÉ : pomper(bus) lit depuis son offset et publie ses réponses.
Le même adaptateur répond PAREIL dans les deux modes (prouvé par test).

Garde-fous durs :
  - un adaptateur LLM répond du TEXTE sur le bus — aucune action
    irréversible, rien ne touche fonds / secrets / publication ;
  - le SEUL chemin réseau du module vit dans _ClientHTTP.completer
    (import paresseux d'urllib), jamais exécuté par les tests ;
  - AdaptateurMemoire ne fait que LIRE la mémoire (recall).
"""
import os
import sys
import json
import importlib.util

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import nexus_bus  # schéma des messages + BROADCAST (source UNIQUE)
from nexus_adaptateur import NexusAdapter  # LA frontière (forme prouvée)


# --------------------------------------------------------------------------- #
# Socle commun : mêmes garde-fous et même dual-mode que la forme prouvée
# --------------------------------------------------------------------------- #
class AdaptateurReel(NexusAdapter):
    """Socle des adaptateurs réels : reprend à l'identique les garde-fous et
    le dual-mode PROUVÉS en brique 1 (AdaptateurLoopback) ; seule la
    production de la réponse (_repondre) change d'un agent à l'autre.

    Garde-fous (déterminisme, pas d'écho infini) :
      - ne répond jamais à ses propres messages ;
      - ne traite que les messages qui lui sont adressés (nom ou "*") ;
      - seul le type "demande" déclenche une réponse — une "reponse"
        clôt l'échange (pas de ping-pong), les autres types sont
        journalisés sans réponse.

    recus = journal en mémoire des messages remis (permet aux tests de
    prouver « l'agent reçoit », comme en brique 1).
    """

    def __init__(self, nom, roles=None):
        self._nom = nom
        self._roles = list(roles) if roles else []  # défaut [] : rétrocompat
        self._offset = 0  # position de lecture propre au mode BRANCHÉ
        self.recus = []

    def nom(self):
        return self._nom

    def roles(self):
        """Capacités déclarées (brique 4). Défaut [] : ajout pur — un agent réel
        qui ne déclare rien reste routable en nommé/étoile, invisible au rôle."""
        return list(self._roles)

    def _repondre(self, msg):
        """Produit le CONTENU de la réponse à une demande, ou None
        (silence). C'est le seul point qui varie entre agents réels."""
        raise NotImplementedError("un adaptateur réel doit fournir _repondre")

    def sur_message(self, msg):
        """Mode SOLO : traite UN message sans bus, renvoie msg | None."""
        if msg.get("expediteur") == self._nom:
            return None  # jamais d'écho sur ses propres messages
        if msg.get("destinataire") not in (self._nom, nexus_bus.BROADCAST):
            return None  # pas adressé à cet agent
        self.recus.append(msg)
        if msg.get("type") != "demande":
            return None  # une réponse clôt l'échange ; seul "demande" déclenche
        contenu = self._repondre(msg)
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
        """Mode BRANCHÉ : lit le neuf depuis son offset, traite avec la MÊME
        logique sur_message et publie ses réponses sur le bus. Non bloquant :
        une passe, puis la main est rendue. Renvoie les réponses publiées."""
        messages, self._offset = bus.lire_depuis(self._offset)
        reponses = []
        for msg in messages:
            reponse = self.sur_message(msg)
            if reponse is not None:
                reponses.append(bus.publier(reponse))
        return reponses


# --------------------------------------------------------------------------- #
# Agent 1 — AdaptateurMemoire : la vraie mémoire, en LECTURE SEULE
# --------------------------------------------------------------------------- #
_MEMORY_API = None


def _charger_memory_api():
    """Charge UNE fois le VRAI module memory_api (mémoire-beta) — celui qui
    porte le recall classé pertinence(IDF) × force. On RÉUTILISE, on ne
    réimplémente pas : c'est le même code que l'API HTTP locale."""
    global _MEMORY_API
    if _MEMORY_API is None:
        chemin = os.path.join(
            os.path.dirname(SCRIPT_DIR),  # organes/ -> racine du dépôt
            ".claude", "skills", "memoire-beta", "scripts", "memory_api.py",
        )
        spec = importlib.util.spec_from_file_location("memory_api_agentos", chemin)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MEMORY_API = module
    return _MEMORY_API


def _repointer_memoire(memoire):
    """memory_api fige ROOT à l'import ; on le repointe ici à CHAQUE appel
    depuis MEMOIRE_ROOT (même contrat relu-à-chaque-appel que CAPTEURS_ROOT /
    AGENTOS_ROOT — les tests s'isolent sans monkeypatch), sinon le même
    défaut que memory_api calcule (scripts/memoire_data à côté du script)."""
    base = os.environ.get("MEMOIRE_ROOT")
    root = base if base else os.path.join(
        os.path.dirname(os.path.abspath(memoire.__file__)), "memoire_data")
    memoire.ROOT = root
    memoire.BRUT = os.path.join(root, "brut")
    memoire.EN_ATTENTE = os.path.join(root, "en_attente")
    memoire.STRUCT = os.path.join(root, "structure")
    memoire.ARCHIVE = os.path.join(root, "archive")


class AdaptateurMemoire(AdaptateurReel):
    """Agent RÉEL local : la mémoire vivante branchée sur le bus.

    Sur une "demande" dont le contenu est une requête texte non vide,
    interroge le recall EXISTANT de mémoire-beta (classement
    pertinence(IDF) × force — memory_api.recall, réutilisé) et répond :
      - {"requete", "nb", "fiches"} si des fiches sont trouvées ;
      - "aucune" si le recall ne rend rien.

    LECTURE SEULE sur la mémoire : recall ne fait que lire ; ce module ne
    contient aucun open() en écriture (verrou structurel, prouvé par test).
    Sans clé, sans réseau : un agent réel peut l'être localement.
    """

    def __init__(self, nom, scope="all", roles=("memoire",)):
        super().__init__(nom, roles=roles)  # déclare le rôle "memoire" par défaut
        self._scope = scope  # all | structure | en_attente | brut

    def _repondre(self, msg):
        requete = msg.get("contenu")
        if not isinstance(requete, str) or not requete.strip():
            return None  # pas une requête texte : silence
        memoire = _charger_memory_api()
        _repointer_memoire(memoire)
        resultat = memoire.recall({"query": [requete], "scope": [self._scope]})
        if not resultat.get("count"):
            return "aucune"
        return {
            "requete": requete,
            "nb": resultat["count"],
            "fiches": resultat["results"],
        }


# --------------------------------------------------------------------------- #
# Agent 2 — AdaptateurLLM : la prise IA externe, par inversion de contrôle
# --------------------------------------------------------------------------- #
class AdaptateurLLM(AdaptateurReel):
    """La PRISE pour une IA externe, par INVERSION DE CONTRÔLE.

    Le client d'inférence est INJECTÉ au constructeur : tout objet exposant
    completer(prompt) -> str convient — un vrai client HTTP fabriqué par
    client_depuis_env, ou un faux client déterministe dans les tests. Cet
    adaptateur ne sait pas (et n'a pas à savoir) quel fournisseur est
    derrière : le hub connaît l'interface, jamais le fournisseur.

    Sur une "demande" au contenu texte non vide, passe le contenu à
    client.completer et publie le texte rendu comme "reponse". Du TEXTE
    sur le bus, rien d'autre : aucune action irréversible.
    """

    def __init__(self, nom, client):
        super().__init__(nom)
        if not callable(getattr(client, "completer", None)):
            raise TypeError("client doit exposer completer(prompt) -> str")
        self._client = client

    def _repondre(self, msg):
        prompt = msg.get("contenu")
        if not isinstance(prompt, str) or not prompt.strip():
            return None  # pas un prompt texte : silence
        return str(self._client.completer(prompt))


# --------------------------------------------------------------------------- #
# Fabrique de client réel — clé lue dans l'environnement, jamais codée
# --------------------------------------------------------------------------- #
# Fournisseurs supportés : variable d'env de la clé, point d'entrée HTTP et
# modèle par défaut. Les URL et modèles sont de la CONFIGURATION, pas des
# secrets — la clé, elle, ne vit QUE dans l'environnement.
_FOURNISSEURS = {
    "openai": {
        "env": "OPENAI_API_KEY",
        "url": "https://api.openai.com/v1/chat/completions",
        "modele": "gpt-4o-mini",
    },
    "anthropic": {
        "env": "ANTHROPIC_API_KEY",
        "url": "https://api.anthropic.com/v1/messages",
        "modele": "claude-opus-4-8",
    },
    "gemini": {
        "env": "GEMINI_API_KEY",
        "url": ("https://generativelanguage.googleapis.com/v1beta/models/"
                "{modele}:generateContent"),
        "modele": "gemini-2.0-flash",
    },
}
_ALIAS_FOURNISSEURS = {"gpt": "openai", "claude": "anthropic",
                       "google": "gemini"}


class _ClientHTTP:
    """Client d'inférence minimal, stdlib uniquement, pour AdaptateurLLM.

    La clé reçue au constructeur n'est NI écrite, NI loggée : repr masqué,
    et elle ne quitte l'objet que dans l'en-tête d'authentification de la
    requête HTTP. completer() est le SEUL chemin réseau du module — import
    paresseux d'urllib, jamais exécuté par les tests (vérifié par test AST
    + blocage runtime des sockets dans la suite).
    """

    def __init__(self, fournisseur, cle, modele):
        self._fournisseur = fournisseur
        self._cle = cle
        self._modele = modele

    def __repr__(self):
        return (f"_ClientHTTP(fournisseur={self._fournisseur!r}, "
                f"modele={self._modele!r}, cle='***')")

    def completer(self, prompt):
        """Envoie le prompt au fournisseur et renvoie le texte de réponse."""
        import urllib.request  # import PARESSEUX : seul chemin réseau du module

        if self._fournisseur == "openai":
            url = self._url()
            entetes = {"Authorization": "Bearer " + self._cle}
            corps = {"model": self._modele,
                     "messages": [{"role": "user", "content": prompt}]}
        elif self._fournisseur == "anthropic":
            url = self._url()
            entetes = {"x-api-key": self._cle,
                       "anthropic-version": "2023-06-01"}
            corps = {"model": self._modele, "max_tokens": 1024,
                     "messages": [{"role": "user", "content": prompt}]}
        else:  # gemini
            url = self._url()
            entetes = {"x-goog-api-key": self._cle}
            corps = {"contents": [{"parts": [{"text": prompt}]}]}
        entetes["Content-Type"] = "application/json"

        requete = urllib.request.Request(
            url, data=json.dumps(corps).encode("utf-8"),
            headers=entetes, method="POST")
        with urllib.request.urlopen(requete, timeout=120) as reponse:
            donnees = json.loads(reponse.read().decode("utf-8"))

        if self._fournisseur == "openai":
            return donnees["choices"][0]["message"]["content"]
        if self._fournisseur == "anthropic":
            return "".join(bloc.get("text", "") for bloc in donnees["content"]
                           if bloc.get("type") == "text")
        return donnees["candidates"][0]["content"]["parts"][0]["text"]

    def _url(self):
        return _FOURNISSEURS[self._fournisseur]["url"].format(
            modele=self._modele)


def client_depuis_env(fournisseur, modele=None):
    """Fabrique un client réel pour AdaptateurLLM en lisant la clé API dans
    la variable d'environnement du fournisseur (ex. OPENAI_API_KEY,
    ANTHROPIC_API_KEY, GEMINI_API_KEY) — fournie par l'utilisateur, jamais
    codée ici, jamais stockée ailleurs, jamais loggée.

    Cette fabrique n'est appelée par AUCUN test : en CI, AdaptateurLLM est
    exercé avec un faux client déterministe injecté (zéro clé, zéro réseau,
    zéro coût). Elle existe pour que Kily branche une vraie IA d'un geste :
        AdaptateurLLM("gpt", client_depuis_env("openai"))
    """
    nom = str(fournisseur).strip().lower()
    nom = _ALIAS_FOURNISSEURS.get(nom, nom)
    if nom not in _FOURNISSEURS:
        raise ValueError(
            f"fournisseur inconnu : {fournisseur!r} "
            f"(attendu {sorted(_FOURNISSEURS)} ou alias "
            f"{sorted(_ALIAS_FOURNISSEURS)})")
    spec = _FOURNISSEURS[nom]
    cle = os.environ.get(spec["env"], "").strip()
    if not cle:
        # Message SANS la clé (elle n'existe pas) et sans rien logger d'autre.
        raise RuntimeError(
            f"variable d'environnement {spec['env']} absente ou vide : "
            f"impossible de fabriquer un client {nom} réel")
    return _ClientHTTP(nom, cle, modele or spec["modele"])
