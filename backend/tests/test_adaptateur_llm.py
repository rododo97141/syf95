"""Agent OS de NEXUS — adaptateur LLM autonome (Anthropic).

Exigences vérifiées ici (SPEC validée sur 7 points, à la lettre) :

  1) INTERFACE : AdaptateurAnthropic implémente NexusAdapter — nom(),
     sur_message(msg), roles() — client INJECTÉ, sleep ET horloge injectés.
  2) CLIENT INJECTÉ, ZÉRO CLÉ : garde-fou AST (aucune référence os.environ /
     os.getenv, sous aucune forme) — prouvé rougir par mutation, cf. rapport.
  3) MAPPING DES STATUTS : rate-limit/timeout → TimeoutError ; autre erreur
     remonte brute. observer() (nexus_orchestrateur) est le seul traducteur.
  4) VALEUR STRUCTURÉE : {texte, tronque, stop_reason}, tronque =
     (stop_reason != "end_turn").
  5) RETRY BORNÉ SUR DEUX AXES : max_tentatives OU timeout_global, premier
     atteint ; timeout par appel = temps restant ; backoff tronqué au budget.
  6) FAKE PARAMÉTRABLE : FakeClientAnthropic, comportement ET latence simulée,
     zéro réseau, zéro clé, zéro variable d'env.
  7) GARDE-FOU AST : test statique dédié (bas du fichier).

Isolation : CAPTEURS_ROOT vient du conftest (autouse) ; MEMOIRE_ROOT (où
observer journalise la fiabilité) est posé ici par une fixture autouse — les
modules relisent ces ROOT à chaque appel, sans monkeypatch de code. Le temps
est VIRTUEL (horloge injectée) : aucun sommeil réel, budget déterministe.
"""
import ast
import os
import socket
import sys

import pytest


def _racine():
    ici = os.path.dirname(os.path.abspath(__file__))        # backend/tests
    return os.path.dirname(os.path.dirname(ici))            # racine du dépôt


def _organes():
    return os.path.join(_racine(), "organes")


if _organes() not in sys.path:
    sys.path.insert(0, _organes())
import nexus_bus  # noqa: E402
import nexus_orchestrateur  # noqa: E402  (le SEUL traducteur de statut)
from nexus_adaptateur_llm import AdaptateurAnthropic  # noqa: E402


# --------------------------------------------------------------------------- #
# Isolation + garde-fou réseau (s'applique à TOUS les tests du fichier)
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _memoire_isolee(tmp_path, monkeypatch):
    """observer() journalise la fiabilité sous MEMOIRE_ROOT → dossier jetable."""
    monkeypatch.setenv("MEMOIRE_ROOT", str(tmp_path / "_memoire"))


@pytest.fixture(autouse=True)
def _reseau_interdit(monkeypatch):
    """Garde-fou dur : AUCUN appel réseau réel. Toute socket fait échouer."""
    def _interdit(*args, **kwargs):
        raise AssertionError("appel réseau interdit dans les tests")
    monkeypatch.setattr(socket, "socket", _interdit)
    monkeypatch.setattr(socket, "create_connection", _interdit)


# --------------------------------------------------------------------------- #
# Horloge VIRTUELLE partagée : sleep ET maintenant injectés, zéro sommeil réel
# --------------------------------------------------------------------------- #
class Horloge:
    """Temps virtuel partagé entre l'adaptateur et le faux client.

    - maintenant()   : l'horloge injectée (lue par le budget de l'adaptateur) ;
    - dormir(d)      : le sleep injecté — avance le temps ET journalise la durée
      (pour prouver le backoff et sa troncature) ;
    - avancer(d)     : latence d'un appel API — avance le temps SANS être un
      sleep de backoff (n'est pas journalisé dans .sleeps).
    """

    def __init__(self):
        self.t = 0.0
        self.sleeps = []

    def maintenant(self):
        return self.t

    def dormir(self, d):
        self.sleeps.append(d)
        self.t += d

    def avancer(self, d):
        self.t += d


# --------------------------------------------------------------------------- #
# Erreurs simulées (reconnues par l'adaptateur SANS importer anthropic)
# --------------------------------------------------------------------------- #
class RateLimitError(Exception):
    """429 : retryable, reconnue par status_code ET par nom de classe."""
    status_code = 429


class APITimeoutError(Exception):
    """Timeout de la lib : retryable, reconnue par nom de classe."""


class ErreurFranche(Exception):
    """Erreur générique non-retryable. NE DOIT PAS être une sous-classe de
    TimeoutError (sinon observer() la classerait à tort en « timeout »)."""


assert not issubclass(ErreurFranche, TimeoutError)  # verrou du mandat


# --------------------------------------------------------------------------- #
# FakeClientAnthropic : paramétrable par COMPORTEMENT et par LATENCE simulée
# --------------------------------------------------------------------------- #
class _Bloc:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Reponse:
    """Mime un Message Anthropic : content (blocs texte) + stop_reason."""

    def __init__(self, texte, stop_reason):
        self.content = [_Bloc(texte)]
        self.stop_reason = stop_reason


class _Messages:
    def __init__(self, client):
        self._client = client

    def create(self, **kwargs):
        return self._client._create(**kwargs)


class FakeClientAnthropic:
    """Faux client injectable — zéro réseau, zéro clé, construit SANS clé.

    `reaction(appel_index, kwargs, horloge)` décide de CHAQUE appel : renvoie
    une _Reponse (succès) ou lève une exception (retryable ou non), et peut
    simuler une LATENCE en avançant l'horloge. Journalise chaque appel dans
    `appels` (les kwargs, dont timeout = temps restant vu par l'adaptateur)."""

    def __init__(self, reaction, horloge=None):
        self.messages = _Messages(self)
        self._reaction = reaction
        self._horloge = horloge
        self.appels = []

    def _create(self, **kwargs):
        index = len(self.appels)
        self.appels.append(kwargs)
        return self._reaction(index, kwargs, self._horloge)


# Fabriques de comportement (le « paramétrable par comportement »).
def reponse_normale(texte="réponse complète du faux client"):
    return lambda i, kw, h: _Reponse(texte, "end_turn")


def reponse_tronquee(texte="réponse coupée"):
    return lambda i, kw, h: _Reponse(texte, "max_tokens")


def rate_limit_puis_ok(n, texte="enfin ok"):
    """N-1 rate-limits puis un succès (le N-ième appel)."""
    def _r(i, kw, h):
        if i < n - 1:
            raise RateLimitError("429 simulé")
        return _Reponse(texte, "end_turn")
    return _r


def rate_limit_epuise():
    """429 en continu, jusqu'à épuisement du budget."""
    def _r(i, kw, h):
        raise RateLimitError("429 en continu")
    return _r


def appels_lents(fraction=0.9):
    """Chaque appel simule une latence PRÈS du budget restant (timeout reçu),
    puis échoue en timeout de lib — le temps consommé vient des APPELS."""
    def _r(i, kw, h):
        h.avancer(kw["timeout"] * fraction)
        raise APITimeoutError("appel lent, timeout de lib")
    return _r


def erreur_franche():
    """Exception générique immédiate, non-retryable (pas de latence)."""
    def _r(i, kw, h):
        raise ErreurFranche("panne franche")
    return _r


# --------------------------------------------------------------------------- #
# Aides
# --------------------------------------------------------------------------- #
def _demande(contenu="fais quelque chose", destinataire="claude",
             expediteur="kily"):
    return nexus_bus.creer_message(expediteur, destinataire, "demande", contenu)


def _adaptateur(reaction, horloge=None, **kw):
    """Fabrique un adaptateur avec le faux client et (par défaut) le temps
    VIRTUEL de l'horloge — sleep et maintenant injectés, zéro sommeil réel."""
    client = FakeClientAnthropic(reaction, horloge=horloge)
    if horloge is not None:
        kw.setdefault("sleep", horloge.dormir)
        kw.setdefault("maintenant", horloge.maintenant)
    return AdaptateurAnthropic("claude", client, **kw), client


# --------------------------------------------------------------------------- #
# 1) réponse_normale → tronque=False accessible
# --------------------------------------------------------------------------- #
def test_reponse_normale_tronque_false():
    agent, client = _adaptateur(reponse_normale("bonjour"))
    resultat = agent.sur_message(_demande())

    assert resultat == {"texte": "bonjour", "tronque": False,
                        "stop_reason": "end_turn"}
    assert resultat["tronque"] is False        # accessible
    assert len(client.appels) == 1             # un seul appel


# --------------------------------------------------------------------------- #
# 2) réponse_tronquée → tronque=True accessible, information non perdue
# --------------------------------------------------------------------------- #
def test_reponse_tronquee_tronque_true_info_non_perdue():
    agent, _ = _adaptateur(reponse_tronquee("moitié de "))
    resultat = agent.sur_message(_demande())

    assert resultat["tronque"] is True                 # accessible
    assert resultat["stop_reason"] == "max_tokens"     # info NON perdue
    assert resultat["texte"] == "moitié de "           # le texte partiel est là


# --------------------------------------------------------------------------- #
# 3) rate_limit_puis_ok → retour normal, appels au fake == tentatives internes
# --------------------------------------------------------------------------- #
def test_rate_limit_puis_ok_retour_normal_et_compte_appels():
    horloge = Horloge()
    agent, client = _adaptateur(
        rate_limit_puis_ok(3), horloge=horloge,
        max_tentatives=3, backoff_base=0.5, timeout_global=1000)

    resultat = agent.sur_message(_demande())  # aucune exception

    assert resultat["tronque"] is False and resultat["texte"] == "enfin ok"
    # 3 appels au fake = 3 tentatives internes (2 backoffs entre elles).
    assert len(client.appels) == 3
    assert horloge.sleeps == [0.5, 1.0]  # backoff entre les 3 tentatives


# --------------------------------------------------------------------------- #
# 4) rate_limit_épuisé → observer() retourne bien ("timeout", ...)
# --------------------------------------------------------------------------- #
def test_rate_limit_epuise_observer_retourne_timeout():
    horloge = Horloge()
    agent, _ = _adaptateur(
        rate_limit_epuise(), horloge=horloge,
        max_tentatives=3, backoff_base=0.5, timeout_global=1000)
    msg = _demande()

    # Intégration RÉELLE avec observer() : c'est LUI qui traduit le statut.
    issue, valeur = nexus_orchestrateur.observer(
        "claude", lambda: agent.sur_message(msg))

    assert issue == "timeout"                        # PAS « une exception »
    assert isinstance(valeur, TimeoutError)


# --------------------------------------------------------------------------- #
# 5) appels_lents → TimeoutError AVANT max_tentatives (timeout_global actif)
# --------------------------------------------------------------------------- #
def test_appels_lents_timeout_global_plafond_actif():
    horloge = Horloge()
    # max_tentatives volontairement GRAND : si le plafond actif était le
    # compte d'essais, on ne lèverait pas si tôt. C'est le TEMPS qui borne.
    agent, client = _adaptateur(
        appels_lents(fraction=0.9), horloge=horloge,
        max_tentatives=50, backoff_base=0.5, timeout_global=10)

    with pytest.raises(TimeoutError):
        agent.sur_message(_demande())

    # Preuve : bien moins d'appels que max_tentatives — c'est le budget TEMPS
    # (appels lents) qui a arrêté la boucle, pas le compte d'essais.
    assert len(client.appels) < 50
    assert horloge.t <= 10 + 1e-9  # jamais au-delà du budget global


# --------------------------------------------------------------------------- #
# 6) erreur_franche → observer() confirme ("exception", ...)
# --------------------------------------------------------------------------- #
def test_erreur_franche_observer_retourne_exception():
    agent, client = _adaptateur(erreur_franche(), max_tentatives=5)
    msg = _demande()

    issue, valeur = nexus_orchestrateur.observer(
        "claude", lambda: agent.sur_message(msg))

    assert issue == "exception"                 # PAS « timeout »
    assert isinstance(valeur, ErreurFranche)
    assert not isinstance(valeur, TimeoutError)
    assert len(client.appels) == 1              # non-retryable : aucun retry


# --------------------------------------------------------------------------- #
# 7) isolation → tourne SANS aucune variable d'env de clé définie
# --------------------------------------------------------------------------- #
def test_isolation_aucune_cle_env_supposee(monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    agent, client = _adaptateur(reponse_normale("sans clé"))
    resultat = agent.sur_message(_demande())

    assert resultat["texte"] == "sans clé"      # aucune clé requise
    assert len(client.appels) == 1


# --------------------------------------------------------------------------- #
# 8) BACKOFF TESTÉ → sleep injecté, appelé avec (0.5, 1, 2), sans dormir en CI
# --------------------------------------------------------------------------- #
def test_backoff_durees_via_sleep_injecte():
    horloge = Horloge()
    # 4 tentatives permises → 3 backoffs (0.5, 1, 2) puis épuisement d'essais.
    agent, client = _adaptateur(
        rate_limit_epuise(), horloge=horloge,
        max_tentatives=4, backoff_base=0.5, timeout_global=1000)

    with pytest.raises(TimeoutError):
        agent.sur_message(_demande())

    assert horloge.sleeps == [0.5, 1.0, 2.0]   # backoff exponentiel exact
    assert len(client.appels) == 4             # 4 tentatives, 3 attentes


# --------------------------------------------------------------------------- #
# 9) BACKOFF TRONQUÉ → budget trop faible pour le prochain backoff calculé
# --------------------------------------------------------------------------- #
def test_backoff_tronque_reste_dans_le_budget():
    horloge = Horloge()
    # Budget 3s, backoff 0.5→1→2 ; le 3e backoff (2s) dépasserait le reste
    # (1.5s) : la boucle le TRONQUE puis lève dans le budget. max_tentatives
    # grand pour prouver que c'est le TEMPS, pas le compte, qui borne.
    agent, client = _adaptateur(
        rate_limit_epuise(), horloge=horloge,
        max_tentatives=50, backoff_base=0.5, timeout_global=3)

    with pytest.raises(TimeoutError):
        agent.sur_message(_demande())

    # Le dernier backoff a été TRONQUÉ (1.5 < 2 = valeur calculée).
    assert horloge.sleeps == [0.5, 1.0, 1.5]
    assert horloge.sleeps[-1] < 0.5 * (2 ** 2)  # tronqué sous le calcul brut
    assert horloge.t <= 3 + 1e-9                # jamais au-delà de timeout_global
    assert len(client.appels) < 50              # borné par le temps, pas les essais


# --------------------------------------------------------------------------- #
# 7 bis) GARDE-FOU AST : aucune référence à os.environ / os.getenv, sous AUCUNE
# forme (accès direct, import indirect, ou alias). Prouvé rougir par mutation
# (cf. rapport final : ajout temporaire d'os.environ → test rouge → retrait).
# --------------------------------------------------------------------------- #
def _arbre_adaptateur():
    chemin = os.path.join(_organes(), "nexus_adaptateur_llm.py")
    with open(chemin, encoding="utf-8") as f:
        return ast.parse(f.read())


def test_garde_fou_aucune_lecture_environnement():
    """L'adaptateur ne lit JAMAIS l'environnement : aucune référence à
    os.environ / os.getenv, quelle que soit la forme d'accès."""
    arbre = _arbre_adaptateur()

    # 1) Repérer les alias : `import os as x`, `import os` (x == "os"),
    #    et les noms importés directement depuis os : `from os import environ`.
    alias_os = set()          # noms qui désignent le module os (os, x, …)
    noms_interdits = set()    # noms liés directement à environ/getenv
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            for alias in noeud.names:
                if alias.name == "os" or alias.name.startswith("os."):
                    alias_os.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(noeud, ast.ImportFrom) and noeud.module == "os":
            for alias in noeud.names:
                if alias.name in ("environ", "getenv"):
                    noms_interdits.add(alias.asname or alias.name)

    # 2) Accès par attribut : <alias_os>.environ / <alias_os>.getenv.
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Attribute)
                and isinstance(noeud.value, ast.Name)
                and noeud.value.id in alias_os
                and noeud.attr in ("environ", "getenv")):
            raise AssertionError(
                f"lecture d'environnement interdite : "
                f"{noeud.value.id}.{noeud.attr}")

    # 3) Usage direct d'un nom importé (environ[...] / getenv(...)) ou aliasé.
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Name) and noeud.id in noms_interdits:
            raise AssertionError(
                f"lecture d'environnement interdite via import direct : "
                f"{noeud.id}")
