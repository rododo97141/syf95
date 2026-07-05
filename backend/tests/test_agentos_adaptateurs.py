"""Agent OS de NEXUS — brique 2 (phase HA) : premiers adaptateurs RÉELS.

Exigences vérifiées ici (spec brique 2, à la lettre) :
  1) AdaptateurMemoire rend un VRAI résultat de recall (memory_api.recall,
     réutilisé — classement pertinence×force) sur une vraie demande, au bon
     format (type "reponse", destinataire = expéditeur, ref = ts de la
     demande), et "aucune" quand rien n'est trouvé ; LECTURE SEULE prouvée
     (la mémoire est binairement identique avant/après) ;
  2) dual-mode Mémoire : solo (sur_message) == branché (pomper) ;
  3) AdaptateurLLM avec FAUX client injecté : demande → completer appelé
     EXACTEMENT une fois avec le contenu → réponse publiée avec le texte du
     client — zéro réseau ;
  4) dual-mode LLM : solo == branché ;
  5) BOUT-EN-BOUT inter-agents réels sur le bus : une demande de l'agent LLM
     adressée à l'agent Mémoire → réponse réelle (recall) publiée → l'agent
     LLM la REÇOIT à la passe suivante (et n'y répond pas : pas de ping-pong) ;
  6) frontière : AUCUNE clé en dur (AST), la clé ne vient que de
     os.environ.get, AUCUN import réseau hors du client réel (completer),
     AUCUNE ouverture de fichier en écriture dans le module (mémoire lecture
     seule — structurel), et AUCUN appel réseau réel pendant la suite
     (sockets bloqués en runtime par fixture autouse) ;
  7) (CI) la suite complète reste verte — tests.yml sur la PR.

Isolation : CAPTEURS_ROOT vient du conftest (autouse) ; AGENTOS_ROOT (bus)
et MEMOIRE_ROOT (mémoire-beta) sont posés ici par des fixtures autouse —
les modules relisent ces ROOT à chaque appel, sans monkeypatch de code.
"""
import ast
import os
import re
import socket
import sys

import pytest


def _racine():
    ici = os.path.dirname(os.path.abspath(__file__))        # backend/tests
    return os.path.dirname(os.path.dirname(ici))             # racine du dépôt


def _organes():
    return os.path.join(_racine(), "organes")


if _organes() not in sys.path:
    sys.path.insert(0, _organes())
import nexus_bus  # noqa: E402
import nexus_agentos  # noqa: E402
import agentos_adaptateurs  # noqa: E402
from agentos_adaptateurs import AdaptateurLLM, AdaptateurMemoire  # noqa: E402


# --------------------------------------------------------------------------- #
# Isolation + garde-fou réseau (s'applique à TOUS les tests du fichier)
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _racines_isolees(tmp_path, monkeypatch):
    """Bus et mémoire isolés par test : ROOT d'env → dossiers jetables."""
    monkeypatch.setenv("AGENTOS_ROOT", str(tmp_path / "_agentos"))
    monkeypatch.setenv("MEMOIRE_ROOT", str(tmp_path / "_memoire"))


@pytest.fixture(autouse=True)
def _reseau_interdit(monkeypatch):
    """Garde-fou dur : AUCUN appel réseau réel dans les tests. Toute
    tentative d'ouvrir une socket fait échouer le test immédiatement."""
    def _interdit(*args, **kwargs):
        raise AssertionError(
            "appel réseau interdit dans les tests (garde-fou brique 2)")
    monkeypatch.setattr(socket, "socket", _interdit)
    monkeypatch.setattr(socket, "create_connection", _interdit)


# --------------------------------------------------------------------------- #
# Aides
# --------------------------------------------------------------------------- #
def _fiche(domaine, categorie, nom, contenu):
    """Écrit une vraie fiche .md dans la mémoire isolée (MEMOIRE_ROOT)."""
    dossier = os.path.join(os.environ["MEMOIRE_ROOT"], "structure",
                           domaine, categorie)
    os.makedirs(dossier, exist_ok=True)
    with open(os.path.join(dossier, nom + ".md"), "w", encoding="utf-8") as f:
        f.write(contenu)


def _msg(expediteur, destinataire, type="demande", contenu="", ref=None):
    return nexus_bus.creer_message(expediteur, destinataire, type,
                                   contenu, ref=ref)


def _sans_ts(msg):
    return {k: v for k, v in msg.items() if k != "ts"}


def _empreinte_memoire():
    """Photo binaire complète de l'arbre mémoire (chemin → octets)."""
    racine = os.environ["MEMOIRE_ROOT"]
    photo = {}
    for dossier, _sous, fichiers in os.walk(racine):
        for nom in fichiers:
            chemin = os.path.join(dossier, nom)
            with open(chemin, "rb") as f:
                photo[os.path.relpath(chemin, racine)] = f.read()
    return photo


class FauxClient:
    """Faux client d'inférence, déterministe, injecté dans AdaptateurLLM :
    zéro clé, zéro réseau, zéro coût. Journalise chaque appel."""

    def __init__(self, texte="réponse déterministe du faux client"):
        self.texte = texte
        self.appels = []

    def completer(self, prompt):
        self.appels.append(prompt)
        return self.texte


# --------------------------------------------------------------------------- #
# 1) AdaptateurMemoire : vrai recall, bon format, lecture seule
# --------------------------------------------------------------------------- #
def test_memoire_rend_un_vrai_resultat_de_recall():
    _fiche("nexus", "methodes", "commun_a", "projet équipe réunion budget")
    _fiche("nexus", "methodes", "rare", "projet zorglubide singulier")
    avant = _empreinte_memoire()

    agent = AdaptateurMemoire("memoire")
    demande = _msg("kily", "memoire", "demande", "zorglubide")
    reponse = agent.sur_message(dict(demande))

    # Bon format : reponse, destinataire = expéditeur, ref = ts de la demande.
    assert reponse is not None
    assert reponse["type"] == "reponse"
    assert reponse["expediteur"] == "memoire"
    assert reponse["destinataire"] == "kily"
    assert reponse["ref"] == demande["ts"]

    # Vrai résultat du recall classé : LA bonne fiche, forme publique intacte.
    contenu = reponse["contenu"]
    assert contenu["requete"] == "zorglubide"
    assert contenu["nb"] == 1
    fiche = contenu["fiches"][0]
    assert fiche["file"] == "rare.md"
    assert set(fiche.keys()) == {"etage", "domain", "category",
                                 "file", "path", "excerpt"}
    assert fiche["domain"] == "nexus" and fiche["category"] == "methodes"

    # LECTURE SEULE : la mémoire est binairement identique après le recall.
    assert _empreinte_memoire() == avant


def test_memoire_repond_aucune_quand_rien_trouve():
    _fiche("nexus", "methodes", "seule", "contenu sans rapport")
    agent = AdaptateurMemoire("memoire")
    reponse = agent.sur_message(_msg("kily", "memoire", "demande",
                                     "introuvablexyz"))
    assert reponse is not None
    assert reponse["type"] == "reponse" and reponse["destinataire"] == "kily"
    assert reponse["contenu"] == "aucune"


def test_memoire_silence_hors_perimetre():
    """Mêmes garde-fous que la forme prouvée : pas adressé → silence ;
    type reponse → silence ; contenu non texte → silence."""
    agent = AdaptateurMemoire("memoire")
    assert agent.sur_message(_msg("kily", "autre", "demande", "x")) is None
    assert agent.sur_message(_msg("kily", "memoire", "reponse", "x")) is None
    assert agent.sur_message(_msg("kily", "memoire", "demande",
                                  {"pas": "du texte"})) is None
    assert agent.sur_message(_msg("memoire", "memoire", "demande", "x")) is None


# --------------------------------------------------------------------------- #
# 2) Dual-mode Mémoire : solo == branché
# --------------------------------------------------------------------------- #
def test_dual_mode_memoire_solo_et_branche_repondent_pareil():
    _fiche("nexus", "methodes", "rare", "projet zorglubide singulier")
    demande = _msg("kily", "memoire", "demande", "zorglubide")

    # SOLO : traite le message SANS bus.
    solo = AdaptateurMemoire("memoire")
    r_solo = solo.sur_message(dict(demande))

    # BRANCHÉ : le MÊME message passe par le bus, l'adaptateur pompe et publie.
    branche = AdaptateurMemoire("memoire")
    nexus_bus.publier(dict(demande))
    publiees = branche.pomper(nexus_bus)
    assert len(publiees) == 1
    sur_bus, _ = nexus_bus.lire_depuis(0)
    assert sur_bus[-1] == publiees[0]  # la réponse est bien SUR le bus

    # Même réponse dans les deux modes (seul le ts d'émission diffère).
    assert r_solo is not None
    assert _sans_ts(r_solo) == _sans_ts(publiees[0])

    # Silence identique aussi : rien trouvé de plus à pomper.
    assert branche.pomper(nexus_bus) == []


# --------------------------------------------------------------------------- #
# 3) AdaptateurLLM avec faux client : un appel, texte publié, zéro réseau
# --------------------------------------------------------------------------- #
def test_llm_faux_client_un_appel_et_reponse_publiee():
    client = FauxClient("le faux client répond ceci")
    agent = AdaptateurLLM("kily-llm", client)
    demande = _msg("memoire", "kily-llm", "demande", "quelle heure ?")

    reponse = agent.sur_message(dict(demande))

    # completer appelé EXACTEMENT une fois, avec le contenu de la demande.
    assert client.appels == ["quelle heure ?"]
    # Réponse au bon format, avec le texte du client, adressée à l'expéditeur.
    assert reponse["type"] == "reponse"
    assert reponse["expediteur"] == "kily-llm"
    assert reponse["destinataire"] == "memoire"
    assert reponse["ref"] == demande["ts"]
    assert reponse["contenu"] == "le faux client répond ceci"
    # (zéro réseau : garanti par la fixture autouse qui bloque les sockets)


def test_llm_refuse_un_client_sans_completer():
    with pytest.raises(TypeError):
        AdaptateurLLM("kily-llm", object())


# --------------------------------------------------------------------------- #
# 4) Dual-mode LLM : solo == branché
# --------------------------------------------------------------------------- #
def test_dual_mode_llm_solo_et_branche_repondent_pareil():
    demande = _msg("kily", "llm", "demande", "résume la journée")

    solo = AdaptateurLLM("llm", FauxClient("texte déterministe"))
    r_solo = solo.sur_message(dict(demande))

    branche = AdaptateurLLM("llm", FauxClient("texte déterministe"))
    nexus_bus.publier(dict(demande))
    publiees = branche.pomper(nexus_bus)
    assert len(publiees) == 1
    sur_bus, _ = nexus_bus.lire_depuis(0)
    assert sur_bus[-1] == publiees[0]

    assert r_solo is not None
    assert _sans_ts(r_solo) == _sans_ts(publiees[0]) == {
        "expediteur": "llm", "destinataire": "kily",
        "type": "reponse", "contenu": "texte déterministe",
        "ref": demande["ts"],
    }


# --------------------------------------------------------------------------- #
# 5) Bout-en-bout inter-agents réels : LLM → Mémoire → LLM, via le bus
# --------------------------------------------------------------------------- #
def test_bout_en_bout_llm_demande_memoire_repond_llm_recoit():
    _fiche("nexus", "methodes", "rare", "projet zorglubide singulier")

    client = FauxClient()
    llm = AdaptateurLLM("kily-llm", client)
    memoire = AdaptateurMemoire("memoire")
    adaptateurs = [llm, memoire]

    # L'agent LLM publie une demande ADRESSÉE à l'agent Mémoire.
    demande = nexus_bus.publier(_msg("kily-llm", "memoire", "demande",
                                     "zorglubide"))

    # Passe 1 : la demande est remise à Mémoire, sa réponse RÉELLE est publiée.
    reponses, offset = nexus_agentos.router(nexus_bus, adaptateurs, 0)
    assert memoire.recus == [demande]
    assert len(reponses) == 1
    reponse = reponses[0]
    assert reponse["expediteur"] == "memoire"
    assert reponse["destinataire"] == "kily-llm"
    assert reponse["ref"] == demande["ts"]
    assert reponse["contenu"]["fiches"][0]["file"] == "rare.md"  # vrai recall

    # Passe 2 : l'agent LLM REÇOIT la réponse réelle de la mémoire.
    suite, offset = nexus_agentos.router(nexus_bus, adaptateurs, offset)
    assert llm.recus == [reponse]
    assert suite == []  # une réponse clôt l'échange : pas de ping-pong
    assert client.appels == []  # rien ne lui a été DEMANDÉ : client jamais appelé

    # Plus rien à router : offset stable.
    encore, offset2 = nexus_agentos.router(nexus_bus, adaptateurs, offset)
    assert encore == [] and offset2 == offset


# --------------------------------------------------------------------------- #
# 6) Frontière : zéro clé en dur, zéro réseau hors client réel, zéro écriture
# --------------------------------------------------------------------------- #
def _arbre_module():
    chemin = os.path.join(_organes(), "agentos_adaptateurs.py")
    with open(chemin, encoding="utf-8") as f:
        return ast.parse(f.read())


def _mode_ouverture(appel):
    if len(appel.args) >= 2 and isinstance(appel.args[1], ast.Constant):
        return appel.args[1].value
    for kw in appel.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            return kw.value.value
    return "r"


def test_frontiere_aucune_cle_en_dur_et_cle_seulement_depuis_env():
    """Verrou : aucune chaîne du module ne ressemble à une clé API, et le
    module ne touche l'environnement qu'en LECTURE (os.environ.get)."""
    arbre = _arbre_module()

    # (a) aucune constante chaîne au motif d'une clé/d'un secret connu.
    motifs_secrets = re.compile(
        r"(sk-[A-Za-z0-9]|sk-ant-|AKIA[0-9A-Z]|AIza[0-9A-Za-z_\-]"
        r"|ghp_[A-Za-z0-9]|xox[baprs]-|-----BEGIN)")
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
            assert not motifs_secrets.search(noeud.value), (
                f"chaîne au motif de secret dans le module : {noeud.value!r}")

    # (b) tout accès à os.environ est un .get (lecture) — jamais d'écriture.
    for noeud in ast.walk(arbre):
        for enfant in ast.iter_child_nodes(noeud):
            enfant._parent = noeud  # annotation des parents pour le contrôle
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Attribute)
                and isinstance(noeud.value, ast.Name)
                and noeud.value.id == "os" and noeud.attr == "environ"):
            parent = getattr(noeud, "_parent", None)
            assert (isinstance(parent, ast.Attribute)
                    and parent.attr == "get"), (
                "os.environ utilisé autrement qu'en lecture via .get")


def test_frontiere_imports_reseau_confines_au_client_reel():
    """Le SEUL chemin réseau du module vit dans _ClientHTTP.completer
    (import paresseux) : aucun import réseau au niveau module ni ailleurs."""
    arbre = _arbre_module()
    reseau = {"urllib", "http", "socket", "requests", "httpx",
              "aiohttp", "ftplib", "smtplib", "telnetlib"}
    hors_client = []

    def visiter(noeud, fonction):
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fonction = noeud.name
        if isinstance(noeud, ast.Import):
            for alias in noeud.names:
                if alias.name.split(".")[0] in reseau and fonction != "completer":
                    hors_client.append((fonction, alias.name))
        if isinstance(noeud, ast.ImportFrom) and noeud.module:
            if noeud.module.split(".")[0] in reseau and fonction != "completer":
                hors_client.append((fonction, noeud.module))
        for enfant in ast.iter_child_nodes(noeud):
            visiter(enfant, fonction)

    visiter(arbre, fonction=None)
    assert hors_client == [], (
        f"imports réseau hors du client réel : {hors_client}")


def test_frontiere_aucune_ecriture_de_fichier_dans_le_module():
    """Mémoire en LECTURE SEULE, structurellement : le module des adaptateurs
    ne contient AUCUN open() en écriture (publier sur le bus est le travail
    de nexus_bus, déjà verrouillé par son propre test AST)."""
    arbre = _arbre_module()
    ecritures = []
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Call)
                and isinstance(noeud.func, ast.Name)
                and noeud.func.id == "open"):
            mode = _mode_ouverture(noeud)
            if any(c in str(mode) for c in "wax+"):
                ecritures.append(mode)
    assert ecritures == [], (
        f"ouvertures en écriture dans agentos_adaptateurs : {ecritures}")


def test_frontiere_client_depuis_env_sans_cle_ni_reseau(monkeypatch):
    """Sans variable d'environnement, la fabrique refuse proprement (message
    SANS secret) ; un fournisseur inconnu est refusé aussi. La fabrique
    n'est JAMAIS appelée avec une vraie clé dans les tests (zéro réseau,
    garanti en plus par la fixture autouse qui bloque les sockets)."""
    for var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(RuntimeError):
        agentos_adaptateurs.client_depuis_env("openai")
    with pytest.raises(ValueError):
        agentos_adaptateurs.client_depuis_env("fournisseur-inconnu")
