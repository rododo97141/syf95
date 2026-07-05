#!/usr/bin/env python3
"""
NEXUS — Bus de messagerie (colonne vertébrale de l'Agent OS, brique 1)
« Un seul fil, jamais réécrit : tout le monde peut se parler dessus. »

Le bus est un journal APPEND-ONLY (agentos/bus.jsonl) sur lequel les
adaptateurs (nexus_adaptateur) publient et lisent des messages. C'est la
colonne vertébrale sur laquelle tout l'Agent OS se branchera.

Message = {ts, expediteur, destinataire, type, contenu, ref}
  - type ∈ demande / reponse / proposition / capteur ;
  - destinataire = nom d'un adaptateur, ou "*" pour un broadcast ;
  - ref = référence libre vers un message antérieur (ts du message
    d'origine pour une réponse), ou None.

Garanties par conception :
  - APPEND-ONLY : publier() ajoute UNE ligne JSONL en fin de fichier,
    jamais de mutation, un seul écrivain/flux (prouvé par test : l'ancien
    contenu reste un préfixe BINAIRE du nouveau) ;
  - tail O(1) : lire_depuis(offset) délègue au patron PROUVÉ de
    nexus_ligue.tail_depuis (seek + lecture du delta seulement — délai
    indépendant de la taille totale, mesuré par test à 1 et 5000 messages) ;
  - chaque message publié est AUSSI journalisé comme capteur via
    nexus_sense.log_event, fiche = expéditeur → la force vivante
    (nexus_force) s'applique aux agents comme aux fiches ;
  - AUCUN chemin d'exécution : ce module lit/écrit SON journal uniquement —
    pas de fonds, pas de credentials, pas de publication externe. C'est un
    verrou STRUCTUREL (le code n'en contient pas le chemin), pas un if ;
    un test AST vérifie que la seule ouverture en écriture vit dans
    publier() et vise bus.jsonl.

Contrat env (même style que CAPTEURS_ROOT / LECONS_ROOT, relu à CHAQUE
appel) : AGENTOS_ROOT défini → <AGENTOS_ROOT>/agentos/bus.jsonl ; sinon
memoire_data/agentos/bus.jsonl relatif à organes/.
"""
import os
import sys
import json
import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import nexus_sense  # source UNIQUE de l'écriture capteurs (CAPTEURS_ROOT)
from nexus_ligue import tail_depuis  # patron tail-since-offset PROUVÉ O(1)

TYPES = ("demande", "reponse", "proposition", "capteur")
BROADCAST = "*"
CHAMPS = ("ts", "expediteur", "destinataire", "type", "contenu", "ref")


def _chemins():
    """Chemin du journal du bus, relu à CHAQUE appel (jamais figé à l'import).
    AGENTOS_ROOT défini → <AGENTOS_ROOT>/agentos/bus.jsonl ; sinon
    memoire_data/agentos/bus.jsonl relatif au script — même contrat que les
    capteurs, pour que les tests s'isolent sans monkeypatch."""
    base = os.environ.get("AGENTOS_ROOT")
    root = base if base else os.path.join(SCRIPT_DIR, "memoire_data")
    d = os.path.join(root, "agentos")
    return d, os.path.join(d, "bus.jsonl")


def creer_message(expediteur, destinataire, type, contenu, ref=None):
    """Fabrique un message au schéma EXACT de la brique 1 (ts horodaté en
    microsecondes : ordonnancement fin + ref utilisable comme référence)."""
    return {
        "ts": datetime.datetime.now().isoformat(timespec="microseconds"),
        "expediteur": expediteur,
        "destinataire": destinataire,
        "type": type,
        "contenu": contenu,
        "ref": ref,
    }


def _valider(msg):
    """Refuse tout message hors schéma — le bus ne transporte qu'UN format."""
    if not isinstance(msg, dict):
        raise ValueError(f"message non-dict : {type(msg).__name__}")
    inconnus = set(msg) - set(CHAMPS)
    if inconnus:
        raise ValueError(f"champs hors schéma : {sorted(inconnus)}")
    manquants = [c for c in CHAMPS if c not in msg]
    if manquants:
        raise ValueError(f"champs requis manquants : {manquants}")
    if not msg["expediteur"] or not msg["destinataire"]:
        raise ValueError("expediteur et destinataire doivent être non vides")
    if msg["type"] not in TYPES:
        raise ValueError(f"type invalide : {msg.get('type')!r} (attendu {TYPES})")


def publier(msg):
    """Publie UN message : APPEND d'une ligne JSONL en fin de bus.jsonl.
    JAMAIS de mutation — c'est la SEULE ouverture en écriture du module
    (vérifiée par test AST). Complète ts/ref si absents, valide le schéma,
    journalise AUSSI l'événement comme capteur (nexus_sense.log_event,
    fiche = expéditeur : force vivante sur les agents) et renvoie le
    message publié."""
    msg = dict(msg)
    msg.setdefault("ts", datetime.datetime.now().isoformat(timespec="microseconds"))
    msg.setdefault("ref", None)
    _valider(msg)
    d, journal = _chemins()
    os.makedirs(d, exist_ok=True)
    with open(journal, "a", encoding="utf-8") as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")
    nexus_sense.log_event(
        tache=f"bus:{msg['type']} {msg['expediteur']}→{msg['destinataire']}",
        statut="ok",
        mode="auto",
        fiche=msg["expediteur"],  # la force vivante s'applique à l'AGENT
        note="message publié sur le bus agentos",
    )
    return msg


def lire_depuis(offset):
    """Renvoie (messages, nouvel_offset) — les messages publiés APRÈS
    l'offset, décodés. Délègue le tail au patron prouvé de nexus_ligue :
    seek + lecture du delta uniquement, O(1) vis-à-vis de la taille totale ;
    ligne incomplète (écriture en cours) laissée pour le prochain appel."""
    _, journal = _chemins()
    lignes, nouvel_offset = tail_depuis(journal, offset)
    messages = []
    for ligne in lignes:
        try:
            messages.append(json.loads(ligne))
        except ValueError:
            pass  # ligne corrompue : ignorée, jamais réécrite (append-only)
    return messages, nouvel_offset
