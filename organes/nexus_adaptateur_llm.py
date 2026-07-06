#!/usr/bin/env python3
"""
NEXUS — Agent OS : adaptateur LLM autonome (Anthropic), branché sur la frontière
« Le hub connaît l'interface, jamais le fournisseur — ni sa clé. »

Nouvel adaptateur RÉEL pour une IA externe Anthropic (Claude), écrit SANS
toucher la colonne vertébrale (nexus_bus, nexus_agentos, nexus_orchestrateur) :
il implémente l'interface prouvée NexusAdapter — nom(), sur_message(msg),
roles() — et rien d'autre du tronc n'est modifié.

Verrous du mandat (prouvés par les tests) :

  1) CLIENT INJECTÉ, ZÉRO CLÉ. Le client Anthropic est INJECTÉ au
     constructeur (inversion de contrôle) : ce module ne le construit
     JAMAIS et ne lit AUCUNE variable d'environnement — aucune référence à
     os.environ / os.getenv, sous aucune forme (garde-fou AST dédié). La
     fabrique d'un vrai client et la lecture de la clé restent hors de ce
     fichier (le geste de Kily).

  2) MAPPING DES STATUTS. sur_message() ne renvoie jamais succès/échec :
     - tout ce qui signifie 429 / rate-limit ou timeout de la lib
       (RateLimitError, APITimeoutError, …) est converti en TimeoutError
       standard (« raise TimeoutError(...) from exc ») avant de remonter ;
     - toute autre erreur (4xx hors 429, authentification, réseau franc,
       exception générique) remonte IMMÉDIATEMENT telle quelle.
     Le SEUL traducteur de statut est observer() (nexus_orchestrateur), qui
     catche TimeoutError (« timeout ») puis Exception (« exception »).

  3) VALEUR STRUCTURÉE. Le retour normal (cas réponse) de sur_message() est
     un dict {texte, tronque, stop_reason} — tronque = (stop_reason !=
     "end_turn"). C'est la valeur rendue à l'orchestrateur AVANT toute
     construction de message bus ; sur le bus ne voyage QUE le texte brut
     (format identique à AdaptateurLoopback) — tronque/stop_reason restent
     dans la valeur de retour, pas sur le fil.

  4) RETRY BORNÉ SUR DEUX AXES INDÉPENDANTS. Sur une erreur retryable, la
     boucle interne backoffe (backoff_base * 2^tentative) mais s'arrête au
     PREMIER des deux plafonds atteint : max_tentatives essais OU
     timeout_global écoulé — jamais au seul compte d'essais. Avant chaque
     tentative on calcule le temps restant ; s'il est insuffisant, on lève
     TimeoutError sans attendre max_tentatives. Chaque appel API reçoit
     timeout = temps_restant (un seul appel lent ne défonce pas le budget),
     et le backoff est tronqué (ou sauté) s'il dépasserait le temps restant.
     Les erreurs non-retryables ne sont JAMAIS réessayées.

Injection du temps : sleep (l'attente) ET maintenant (l'horloge) sont
injectables — par défaut time.sleep et time.monotonic (temps réel en
production). Les tests fournissent une horloge virtuelle partagée : le
budget de boucle devient déterministe SANS dormir réellement en CI.
"""
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
from nexus_adaptateur import NexusAdapter  # LA frontière (forme prouvée)


class AdaptateurAnthropic(NexusAdapter):
    """Adaptateur autonome pour une IA externe Anthropic (Claude).

    Client INJECTÉ (jamais construit ici, aucune clé, aucun os.environ) : tout
    objet exposant messages.create(model=…, max_tokens=…, messages=[…],
    timeout=…) convient — un vrai anthropic.Anthropic, ou un faux client
    déterministe dans les tests. La réponse attendue expose stop_reason et
    content (liste de blocs texte), comme un Message Anthropic.

    sur_message() suit les garde-fous prouvés (pas d'écho, adressé, seul le
    type "demande" déclenche) puis, sur un prompt texte non vide, appelle le
    client sous budget borné (voir _completer_avec_budget) et renvoie la
    valeur STRUCTURÉE {texte, tronque, stop_reason}. En cas de silence
    (message hors périmètre), renvoie None comme la forme prouvée.
    """

    # Configuration d'appel (pas des secrets) : mêmes valeurs que la prise
    # LLM déjà en place (agentos_adaptateurs), surchargeable par sous-classe.
    MODELE_DEFAUT = "claude-opus-4-8"
    MAX_TOKENS_DEFAUT = 1024

    # Familles d'erreurs de la lib Anthropic traitées comme retryables
    # (reconnues par nom de classe, sans importer anthropic) : rate-limit et
    # timeouts de la lib. Le 429 est reconnu en plus par status_code.
    _NOMS_RETRYABLES = frozenset({
        "RateLimitError", "APITimeoutError", "APIConnectionTimeoutError",
    })

    def __init__(self, nom, client, roles=None, max_tentatives=3,
                 backoff_base=0.5, timeout_global=30, sleep=time.sleep,
                 maintenant=time.monotonic):
        self._nom = nom
        self._client = client
        self._roles = list(roles) if roles else []  # défaut [] : rétrocompat
        self._max_tentatives = int(max_tentatives)
        self._backoff_base = float(backoff_base)
        self._timeout_global = float(timeout_global)
        self._sleep = sleep            # attente injectée (défaut time.sleep)
        self._maintenant = maintenant  # horloge injectée (défaut time.monotonic)
        self.recus = []                # journal en mémoire (comme la forme prouvée)

    # ----------------------------------------------------------------- API
    def nom(self):
        return self._nom

    def roles(self):
        """Capacités déclarées (brique 4). Défaut [] : ajout pur, rétrocompatible."""
        return list(self._roles)

    def sur_message(self, msg):
        """Traite UN message. Garde-fous prouvés d'abord (pas d'écho, adressé,
        seul "demande" déclenche, prompt texte non vide) ; sinon None (silence).

        Sur une vraie demande texte : appelle le client sous budget borné et
        renvoie la valeur STRUCTURÉE {texte, tronque, stop_reason}. Ne
        construit JAMAIS de statut succès/échec : sur erreur, laisse remonter
        (TimeoutError pour rate-limit/timeout, brute sinon) — observer() est
        le seul traducteur."""
        if msg.get("expediteur") == self._nom:
            return None  # jamais d'écho sur ses propres messages
        if msg.get("destinataire") not in (self._nom, "*"):
            return None  # pas adressé à cet agent
        self.recus.append(msg)
        if msg.get("type") != "demande":
            return None  # une réponse clôt l'échange ; seul "demande" déclenche
        prompt = msg.get("contenu")
        if not isinstance(prompt, str) or not prompt.strip():
            return None  # pas un prompt texte : silence
        return self._completer_avec_budget(prompt)

    # ------------------------------------------------- budget / retry borné
    def _completer_avec_budget(self, prompt):
        """Appelle le client avec retry backoff BORNÉ sur deux axes
        indépendants : max_tentatives essais OU timeout_global écoulé (le
        premier atteint arrête la boucle). Renvoie la valeur structurée sur
        succès ; lève TimeoutError si le budget (essais/temps) s'épuise sur
        des erreurs retryables ; laisse remonter toute erreur non-retryable."""
        debut = self._maintenant()
        tentative = 0
        dernier_exc = None
        while True:
            temps_restant = self._timeout_global - (self._maintenant() - debut)
            if temps_restant <= 0:
                # Plafond TEMPS atteint avant même de (ré)essayer.
                raise TimeoutError(
                    f"budget de temps épuisé ({self._timeout_global}s) pour "
                    f"{self._nom} après {tentative} tentative(s)") from dernier_exc

            try:
                reponse = self._appeler(prompt, temps_restant)
            except Exception as exc:  # noqa: BLE001 — on trie retryable / non
                if not self._est_retryable(exc):
                    raise  # non-retryable : remonte IMMÉDIATEMENT, telle quelle
                dernier_exc = exc
                prochaine = tentative + 1
                if prochaine >= self._max_tentatives:
                    # Plafond ESSAIS atteint : converti en TimeoutError.
                    raise TimeoutError(
                        f"retry épuisé ({self._max_tentatives} tentatives) pour "
                        f"{self._nom}") from exc
                # Recalcul du temps restant AVANT le backoff.
                temps_restant = self._timeout_global - (self._maintenant() - debut)
                if temps_restant <= 0:
                    raise TimeoutError(
                        f"budget de temps épuisé ({self._timeout_global}s) pour "
                        f"{self._nom} après {prochaine} tentative(s)") from exc
                # Backoff exponentiel, TRONQUÉ pour ne jamais dépasser le budget.
                attente = self._backoff_base * (2 ** tentative)
                if attente > temps_restant:
                    attente = temps_restant  # tronque : reste dans le budget
                self._sleep(attente)
                tentative = prochaine
                continue

            texte, stop_reason = self._extraire(reponse)
            return {
                "texte": texte,
                "tronque": stop_reason != "end_turn",
                "stop_reason": stop_reason,
            }

    def _appeler(self, prompt, timeout):
        """UN appel API au client injecté, avec timeout = temps_restant (pour
        qu'un seul appel lent ne défonce pas le budget global)."""
        return self._client.messages.create(
            model=self.MODELE_DEFAUT,
            max_tokens=self.MAX_TOKENS_DEFAUT,
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout,
        )

    def _est_retryable(self, exc):
        """Vrai si l'erreur signifie 429/rate-limit ou timeout de la lib
        Anthropic — reconnue par status_code == 429 ou par nom de classe (sans
        importer anthropic). Tout le reste est non-retryable."""
        if getattr(exc, "status_code", None) == 429:
            return True
        return any(cls.__name__ in self._NOMS_RETRYABLES
                   for cls in type(exc).__mro__)

    @staticmethod
    def _extraire(reponse):
        """(texte, stop_reason) depuis une réponse type Message Anthropic :
        stop_reason + concaténation des blocs texte de content. Robuste aux
        blocs objets (.text) comme aux blocs dict ({"text": …})."""
        stop_reason = getattr(reponse, "stop_reason", None)
        contenu = getattr(reponse, "content", None)
        if isinstance(contenu, str):
            return contenu, stop_reason
        if contenu is None:
            return "", stop_reason
        parts = []
        for bloc in contenu:
            texte = getattr(bloc, "text", None)
            if texte is None and isinstance(bloc, dict):
                texte = bloc.get("text")
            if texte:
                parts.append(texte)
        return "".join(parts), stop_reason
