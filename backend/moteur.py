"""
Moteur interchangeable — couche d'abstraction de l'IA derrière les organes NEXUS.

But (« loop engineering », Voie 5) : rendre l'intelligence qui équipe les
organes (95/96/97/98) INTERCHANGEABLE. Un organe ne parle jamais directement à
un fournisseur ; il parle à un `Moteur`. On peut donc brancher Claude, Gemini,
GPT, Kimi… sans toucher au reste du backend (injection de dépendance).

Deux implémentations fournies :
  - `MoteurMock`     : déterministe, hors-ligne, pour les tests et le mode dégradé.
  - `AdaptateurAPI`  : générique, vers une API compatible « OpenAI Chat
    Completions » (le format que parlent GPT, Kimi/Moonshot, et — via leur
    endpoint compatible — Claude et Gemini). La clé d'API est lue dans une
    VARIABLE D'ENVIRONNEMENT, JAMAIS écrite en dur.

Zéro dépendance lourde : appels HTTP via `urllib` (bibliothèque standard).

Note d'honnêteté : `AdaptateurAPI` suppose le schéma OpenAI Chat Completions.
Pour l'API NATIVE d'un fournisseur (ex. Anthropic `POST /v1/messages`, en-tête
`x-api-key` + `anthropic-version`, réponse `content[0].text`), il faut une
petite sous-classe qui surcharge `generer` — voir le README.
"""

from __future__ import annotations

import abc
import json
import os
import urllib.error
import urllib.request


class ErreurMoteur(RuntimeError):
    """Erreur d'un moteur : clé absente, appel réseau échoué, réponse invalide."""


class Moteur(abc.ABC):
    """
    Interface abstraite. Tout moteur sait produire du texte à partir d'un prompt.
    Les organes dépendent de CETTE interface, pas d'un fournisseur précis.
    """

    @abc.abstractmethod
    def generer(self, prompt: str) -> str:
        """Renvoie la réponse du moteur pour `prompt`."""
        raise NotImplementedError

    @property
    def nom(self) -> str:
        """Nom lisible du moteur (par défaut, le nom de la classe)."""
        return type(self).__name__


class MoteurMock(Moteur):
    """
    Moteur factice DÉTERMINISTE — aucun appel réseau.

    Même prompt → même sortie : indispensable pour des tests reproductibles et
    pour faire tourner la boucle hors-ligne. Journalise les prompts reçus
    (`self.appels`) afin que les tests puissent vérifier l'injection.
    """

    def __init__(self, prefixe: str = "[mock]"):
        self.prefixe = prefixe
        self.appels: list[str] = []  # journal des prompts reçus

    def generer(self, prompt: str) -> str:
        self.appels.append(prompt)
        # Résumé déterministe du prompt (sans aléa, sans horloge).
        resume = " ".join(prompt.split())
        if len(resume) > 60:
            resume = resume[:57] + "..."
        return f"{self.prefixe} {resume}"


class AdaptateurAPI(Moteur):
    """
    Adaptateur générique vers une API compatible « OpenAI Chat Completions ».

    Paramètres :
      - base_url    : racine de l'API (ex. https://api.openai.com/v1).
      - modele      : identifiant du modèle (ex. claude-opus-4-8, gpt-..., kimi-...).
      - cle_env     : NOM de la variable d'environnement contenant la clé d'API.
      - entete_cle  : en-tête HTTP qui porte la clé (Authorization par défaut).
      - prefixe_cle : préfixe devant la clé ("Bearer " par défaut).
      - timeout     : délai max de l'appel réseau, en secondes.

    La clé n'est JAMAIS en dur : si la variable d'environnement est absente,
    `generer` lève une `ErreurMoteur` au message explicite.
    """

    def __init__(
        self,
        base_url: str,
        modele: str,
        *,
        cle_env: str = "MOTEUR_API_CLE",
        entete_cle: str = "Authorization",
        prefixe_cle: str = "Bearer ",
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.modele = modele
        self.cle_env = cle_env
        self.entete_cle = entete_cle
        self.prefixe_cle = prefixe_cle
        self.timeout = timeout

    def _cle(self) -> str:
        """Lit la clé dans l'environnement, ou lève une erreur claire si absente."""
        cle = os.environ.get(self.cle_env)
        if not cle:
            raise ErreurMoteur(
                f"Clé d'API absente : définissez la variable d'environnement "
                f"« {self.cle_env} » (ex. export {self.cle_env}=sk-...). "
                f"La clé n'est jamais écrite en dur dans le code."
            )
        return cle

    def generer(self, prompt: str) -> str:
        cle = self._cle()  # lève une ErreurMoteur claire si la clé manque
        url = f"{self.base_url}/chat/completions"
        corps = json.dumps(
            {
                "model": self.modele,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode("utf-8")

        requete = urllib.request.Request(url, data=corps, method="POST")
        requete.add_header("Content-Type", "application/json")
        requete.add_header(self.entete_cle, f"{self.prefixe_cle}{cle}")

        try:
            with urllib.request.urlopen(requete, timeout=self.timeout) as reponse:
                charge = json.loads(reponse.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise ErreurMoteur(f"Appel API échoué ({e.code}) sur {url}.") from e
        except urllib.error.URLError as e:
            raise ErreurMoteur(f"Réseau indisponible pour {url} : {e.reason}.") from e

        return self._extraire(charge)

    @staticmethod
    def _extraire(charge: dict) -> str:
        """Extrait le texte d'une réponse au format OpenAI Chat Completions."""
        try:
            return charge["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise ErreurMoteur("Réponse API au format inattendu.") from e
