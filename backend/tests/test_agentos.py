"""Agent OS de NEXUS — brique 1 (phase SHU) : la colonne vertébrale.

Exigences vérifiées ici (spec brique 1, à la lettre) :
  1) round-trip : publier → lire_depuis(0) rend les messages INTACTS ;
  2) tail O(1) MESURÉ à 1 et 5000 messages (délai du delta indépendant de
     la taille totale du bus) ;
  3) append-only PROUVÉ par empreinte binaire : l'ancien contenu du journal
     est un préfixe BINAIRE du nouveau — zéro mutation ;
  4) dual-mode : le même AdaptateurLoopback répond PAREIL en solo
     (sur_message sans bus) et en branché (pomper sur le bus) ;
  5) dialogue pair-à-pair A→B via le bus (destinataire nommé) : B répond,
     A reçoit ;
  6) broadcast "*" : atteint TOUS les abonnés (sauf l'expéditeur) ;
  7) chaque message publié apparaît AUSSI dans les capteurs
     (nexus_sense.log_event — force vivante sur les agents) ;
  8) frontière STRUCTURELLE : le bus ne contient aucun chemin d'écriture
     hors de son journal (vérifié sur l'AST du module, pas par un if) ;
  9) (CI) la suite complète reste verte — tests.yml sur la PR.

Isolation : CAPTEURS_ROOT vient du conftest (autouse) ; AGENTOS_ROOT est
posé ici par une fixture autouse locale — nexus_bus relit les deux à
chaque appel.
"""
import ast
import json
import os
import sys
import time

import pytest


def _organes():
    ici = os.path.dirname(os.path.abspath(__file__))       # backend/tests
    racine = os.path.dirname(os.path.dirname(ici))          # racine du dépôt
    return os.path.join(racine, "organes")


if _organes() not in sys.path:
    sys.path.insert(0, _organes())
import nexus_sense  # noqa: E402
import nexus_bus  # noqa: E402
import nexus_agentos  # noqa: E402
from nexus_adaptateur import AdaptateurLoopback  # noqa: E402


@pytest.fixture(autouse=True)
def _agentos_isole(tmp_path, monkeypatch):
    """Bus isolé par test : AGENTOS_ROOT → dossier temporaire jetable."""
    monkeypatch.setenv("AGENTOS_ROOT", str(tmp_path / "_agentos"))


def _msg(expediteur="A", destinataire="B", type="demande",
         contenu="ping", ref=None):
    return nexus_bus.creer_message(expediteur, destinataire, type,
                                   contenu, ref=ref)


# --------------------------------------------------------------------------- #
# 1) round-trip : publier → lire_depuis(0) intact
# --------------------------------------------------------------------------- #
def test_round_trip_publier_lire_depuis_intact():
    publies = [
        nexus_bus.publier(_msg("A", "B", "demande", "quelle heure ?")),
        nexus_bus.publier(_msg("B", "A", "reponse", "midi", ref="t0")),
        nexus_bus.publier(_msg("C", "*", "proposition",
                               {"idee": "jouer", "priorite": 1})),
        nexus_bus.publier(_msg("D", "*", "capteur", "température : 21 °C")),
    ]
    lus, offset = nexus_bus.lire_depuis(0)
    assert lus == publies  # INTACT, champ pour champ, y compris contenu dict
    # offset stable : rien de neuf → rien à lire, même offset
    encore, offset2 = nexus_bus.lire_depuis(offset)
    assert encore == [] and offset2 == offset


def test_publier_refuse_hors_schema():
    with pytest.raises(ValueError):
        nexus_bus.publier(_msg(type="ordre"))  # type hors demande/reponse/proposition/capteur
    with pytest.raises(ValueError):
        nexus_bus.publier({"expediteur": "A", "destinataire": "B",
                           "type": "demande", "contenu": "x", "extra": 1})
    with pytest.raises(ValueError):
        nexus_bus.publier(_msg(expediteur=""))  # expéditeur vide


# --------------------------------------------------------------------------- #
# 2) tail O(1) mesuré à 1 et 5000 messages
# --------------------------------------------------------------------------- #
def _mesurer_delta(repetitions=30):
    """Publie UN message puis chronomètre la lecture du delta depuis
    l'offset de fin. min() sur N répétitions = mesure stable (écrase le
    bruit d'OS) — même patron que le test prouvé de nexus_ligue."""
    _, journal = nexus_bus._chemins()
    mesures = []
    for _ in range(repetitions):
        offset = os.path.getsize(journal)
        nexus_bus.publier(_msg(contenu="delta"))
        t0 = time.perf_counter()
        messages, _ = nexus_bus.lire_depuis(offset)
        mesures.append(time.perf_counter() - t0)
        assert len(messages) == 1  # on lit bien LE delta, pas le fichier
    return min(mesures)


def test_tail_o1_mesure_a_1_et_5000_messages():
    N_GROS = 5000
    nexus_bus.publier(_msg(contenu="premier"))  # bus à 1 message
    t_petit = _mesurer_delta()
    _, journal = nexus_bus._chemins()
    taille_petite = os.path.getsize(journal)

    ligne = json.dumps(_msg(contenu="lest"), ensure_ascii=False) + "\n"
    with open(journal, "a", encoding="utf-8") as f:  # gonflage à 5000 messages
        f.write(ligne * (N_GROS - 100))
    t_gros = _mesurer_delta()
    taille_grosse = os.path.getsize(journal)

    print(f"\n[tail O(1) bus] petit bus (départ à 1 message) : "
          f"{taille_petite} octets → delta lu en "
          f"{t_petit * 1e6:.1f} µs ; {N_GROS} messages : {taille_grosse} octets "
          f"→ delta lu en {t_gros * 1e6:.1f} µs "
          f"(ratio ×{t_gros / t_petit:.2f} pour "
          f"×{taille_grosse / taille_petite:.0f} en taille).")
    # O(1) à bruit d'ordonnanceur près : plancher absolu de 2 ms pour ne pas
    # transformer un aléa d'OS en faux rouge (même contrat que nexus_ligue).
    assert t_gros < max(t_petit * 10, 0.002), (
        f"le delta croît avec la taille totale : {t_petit * 1e6:.1f} µs → "
        f"{t_gros * 1e6:.1f} µs")


# --------------------------------------------------------------------------- #
# 3) append-only prouvé par empreinte binaire
# --------------------------------------------------------------------------- #
def test_append_only_ancien_contenu_prefixe_binaire():
    for i in range(5):
        nexus_bus.publier(_msg(contenu=f"vague-1 n°{i}"))
    _, journal = nexus_bus._chemins()
    with open(journal, "rb") as f:
        avant = f.read()

    for i in range(5):
        nexus_bus.publier(_msg(contenu=f"vague-2 n°{i}"))
    with open(journal, "rb") as f:
        apres = f.read()

    assert len(apres) > len(avant)
    assert apres[: len(avant)] == avant, (
        "mutation détectée : l'ancien contenu n'est plus un préfixe binaire")


# --------------------------------------------------------------------------- #
# 4) dual-mode : même AdaptateurLoopback, même réponse en solo et en branché
# --------------------------------------------------------------------------- #
def _sans_ts(msg):
    return {k: v for k, v in msg.items() if k != "ts"}


def test_dual_mode_solo_et_branche_repondent_pareil():
    regles = {"quelle heure ?": "midi"}
    entrant = _msg("A", "echo", "demande", "quelle heure ?")

    # SOLO : traite le message SANS bus.
    solo = AdaptateurLoopback("echo", regles)
    r_solo = solo.sur_message(dict(entrant))

    # BRANCHÉ : le MÊME message passe par le bus, l'adaptateur pompe et publie.
    branche = AdaptateurLoopback("echo", regles)
    nexus_bus.publier(dict(entrant))
    publiees = branche.pomper(nexus_bus)
    assert len(publiees) == 1
    # ... et la réponse est bien SUR le bus (dernier message du journal).
    sur_bus, _ = nexus_bus.lire_depuis(0)
    assert sur_bus[-1] == publiees[0]

    # Même réponse dans les deux modes (seul le ts d'émission diffère).
    assert r_solo is not None
    assert _sans_ts(r_solo) == _sans_ts(publiees[0]) == {
        "expediteur": "echo", "destinataire": "A",
        "type": "reponse", "contenu": "midi", "ref": entrant["ts"],
    }

    # Silence identique aussi : contenu hors règles → None en solo,
    # zéro publication en branché.
    inconnu = _msg("A", "echo", "demande", "hors règles")
    assert solo.sur_message(dict(inconnu)) is None
    nexus_bus.publier(dict(inconnu))
    assert branche.pomper(nexus_bus) == []


# --------------------------------------------------------------------------- #
# 5) dialogue A→B via le bus (destinataire nommé) : B répond, A reçoit
# --------------------------------------------------------------------------- #
def test_dialogue_pair_a_pair_a_vers_b_et_retour():
    a = AdaptateurLoopback("A", {})
    b = AdaptateurLoopback("B", {"quelle heure ?": "midi"})
    adaptateurs = [a, b]

    demande = nexus_bus.publier(_msg("A", "B", "demande", "quelle heure ?"))

    # Passe 1 : la demande est remise à B, sa réponse est publiée.
    reponses, offset = nexus_agentos.router(nexus_bus, adaptateurs, 0)
    assert b.recus == [demande]
    assert len(reponses) == 1
    assert _sans_ts(reponses[0]) == {
        "expediteur": "B", "destinataire": "A", "type": "reponse",
        "contenu": "midi", "ref": demande["ts"],
    }

    # Passe 2 (non bloquant : le neuf de la passe 1) : A REÇOIT la réponse.
    suite, offset = nexus_agentos.router(nexus_bus, adaptateurs, offset)
    assert a.recus == reponses
    assert suite == []  # une réponse clôt l'échange : pas de ping-pong

    # Plus rien à router : offset stable, personne ne reçoit rien de neuf.
    encore, offset2 = nexus_agentos.router(nexus_bus, adaptateurs, offset)
    assert encore == [] and offset2 == offset


def test_router_n_altere_pas_le_contenu():
    """L'orchestrateur route ; la réponse publiée est VERBATIM celle de
    l'adaptateur (aucun champ ajouté, retiré ou modifié)."""
    contenu = {"reponse": "midi", "confiance": 0.9}
    b = AdaptateurLoopback("B", {"quelle heure ?": contenu})
    nexus_bus.publier(_msg("A", "B", "demande", "quelle heure ?"))
    reponses, _ = nexus_agentos.router(nexus_bus, [b], 0)
    assert reponses[0]["contenu"] == contenu
    sur_bus, _ = nexus_bus.lire_depuis(0)
    assert sur_bus[-1] == reponses[0]


# --------------------------------------------------------------------------- #
# 6) broadcast "*" atteint tous les abonnés
# --------------------------------------------------------------------------- #
def test_broadcast_atteint_tous_les_abonnes():
    a = AdaptateurLoopback("A", {})
    b = AdaptateurLoopback("B", {})
    c = AdaptateurLoopback("C", {})

    annonce = nexus_bus.publier(_msg("A", "*", "proposition", "on joue ?"))
    nexus_agentos.router(nexus_bus, [a, b, c], 0)

    assert b.recus == [annonce]
    assert c.recus == [annonce]
    assert a.recus == []  # jamais remis à son propre expéditeur


# --------------------------------------------------------------------------- #
# 7) chaque message publié apparaît dans les capteurs
# --------------------------------------------------------------------------- #
def test_chaque_message_publie_apparait_dans_les_capteurs():
    assert nexus_sense.lire() == []  # capteurs isolés et vierges (conftest)
    publies = [
        nexus_bus.publier(_msg("A", "B", "demande", "un")),
        nexus_bus.publier(_msg("B", "A", "reponse", "deux")),
        nexus_bus.publier(_msg("C", "*", "capteur", "trois")),
    ]
    capteurs = nexus_sense.lire()
    assert len(capteurs) == len(publies)  # UN capteur par message publié
    for msg, evt in zip(publies, capteurs):
        assert evt["tache"] == (f"bus:{msg['type']} "
                                f"{msg['expediteur']}→{msg['destinataire']}")
        assert evt["fiche"] == msg["expediteur"]  # force vivante sur l'AGENT
        assert evt["statut"] == "ok" and evt["mode"] == "auto"


# --------------------------------------------------------------------------- #
# 8) frontière structurelle : aucun chemin d'écriture hors du journal du bus
# --------------------------------------------------------------------------- #
def _mode_ouverture(call):
    """Mode d'un appel open() dans l'AST : 2e positionnel ou mot-clé mode."""
    if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
        return call.args[1].value
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            return kw.value.value
    return "r"


def test_frontiere_structurelle_le_bus_n_ecrit_que_son_journal():
    """Verrou STRUCTUREL, pas un if : on prouve sur l'AST de nexus_bus que
    (a) la SEULE ouverture en écriture du module vit dans publier() — le
    journal du bus ; (b) aucun module d'exécution/réseau/destruction n'est
    importé (pas de fonds, pas de credentials, pas de publication externe :
    le code n'en contient pas le chemin)."""
    source = open(os.path.join(_organes(), "nexus_bus.py"),
                  encoding="utf-8").read()
    arbre = ast.parse(source)

    ecritures = []  # (fonction englobante, mode) des open() en écriture
    interdits = set()

    def visiter(noeud, fonction):
        if isinstance(noeud, ast.FunctionDef):
            fonction = noeud.name
        if (isinstance(noeud, ast.Call)
                and isinstance(noeud.func, ast.Name)
                and noeud.func.id == "open"):
            mode = _mode_ouverture(noeud)
            if any(c in str(mode) for c in "wax+"):
                ecritures.append((fonction, mode))
        if isinstance(noeud, ast.Import):
            interdits.update(alias.name.split(".")[0] for alias in noeud.names)
        if isinstance(noeud, ast.ImportFrom) and noeud.module:
            interdits.add(noeud.module.split(".")[0])
        for enfant in ast.iter_child_nodes(noeud):
            visiter(enfant, fonction)

    visiter(arbre, fonction=None)

    # (a) UNE seule ouverture en écriture, dans publier(), en APPEND.
    assert ecritures == [("publier", "a")], (
        f"chemins d'écriture inattendus dans nexus_bus : {ecritures}")

    # (b) aucun chemin d'exécution / réseau / suppression n'est importé.
    dangereux = {"subprocess", "socket", "urllib", "http", "requests",
                 "shutil", "ctypes"}
    assert not (interdits & dangereux), (
        f"imports interdits dans nexus_bus : {sorted(interdits & dangereux)}")
    # (c) et aucun appel os.system / os.remove / os.rename / os.unlink.
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Attribute)
                and isinstance(noeud.value, ast.Name)
                and noeud.value.id == "os"):
            assert noeud.attr not in ("system", "remove", "rename", "unlink",
                                      "rmdir", "truncate"), (
                f"appel destructeur dans nexus_bus : os.{noeud.attr}")
