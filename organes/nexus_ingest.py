#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEXUS — Organe d'INGESTION EXTERNE (« nourrir NEXUS du monde extérieur »)

ORIGINE : le run autonome a mesuré le solipsisme à 93,9 % (l'écrasante majorité
des fiches parlent du système lui-même) — aucun canal d'entrée externe n'existait.
Cet organe OUVRE ce canal, sous garde.

MODÈLE DE MENACE (nommé) :
  (1) le-faux-externe-qui-s-auto-renforce : du contenu produit par le système,
      réinjecté comme s'il venait du dehors → l'organe REFUSE source == 'interne'
      (il ne produit JAMAIS d'interne : c'est une entrée du DEHORS, par définition).
  (2) le-faux-externe-servi-à-parité-comme-fiable : une source non approuvée qui
      s'installerait au même rang que le vérifié → l'organe REFUSE toute source
      HORS allowlist (digue close par défaut), et l'étiquetage garde verifie='non'
      (« source fiable, fait non confirmé ») tant que Kily ne certifie pas.
  (hors périmètre : l'attaquant-disque — un tiers qui écrit directement le disque.)

DEUX LIGNES ROUGES structurelles :
  • RÉSEAU INJECTÉ, jamais d'appel réseau DANS l'organe. Le fetch (aller chercher
    le texte sur le web) est le GESTE DE L'APPELANT. `ingerer` reçoit un texte
    DÉJÀ récupéré ; s'il reçoit une capacité réseau (`reseau`), il ne l'appelle
    JAMAIS. Ainsi l'organe reste pur, testable, et sans surface d'exfiltration.
  • Le système PROPOSE, il n'APPROUVE pas. `proposer_source` écrit une PROPOSITION
    examinable (source, fréquence, échantillon, pourquoi) dans propositions_sources
    .jsonl ; il n'écrit JAMAIS allowlist_sources.json (édité par Kily SEUL).

Écriture : normalise le texte et l'écrit en BRUT via `memory_api.add_note` (usage
bibliothèque), en posant le champ `source`. La provenance voyage ensuite tout le
pipeline brut -> en_attente -> structure (cf. memory_api).

Usage bibliothèque uniquement (pas de serveur ici) :
    import nexus_ingest
    nexus_ingest.ingerer(texte_recupere, source="wikipedia", url="https://...")
"""
import os
import re
import sys
import json
import unicodedata
import importlib.util

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RACINE_DEPOT = os.path.dirname(SCRIPT_DIR)

# DONNÉES co-écrites (jamais des constantes) — l'allowlist EST une donnée.
ALLOWLIST_PATH = os.path.join(RACINE_DEPOT, "allowlist_sources.json")
PROPOSITIONS_PATH = os.path.join(RACINE_DEPOT, "propositions_sources.jsonl")

# Chemin du module memory_api (hors sys.path : chargé par emplacement).
_MEMORY_API_PATH = os.path.join(
    RACINE_DEPOT, ".claude", "skills", "memoire-beta", "scripts", "memory_api.py")


def _charger_memory_api():
    """Charge le module memory_api par emplacement (il n'est pas sur sys.path).
    Utilisé comme écrivain BRUT par défaut ; injectable dans `ingerer`."""
    spec = importlib.util.spec_from_file_location("memory_api_ingest", _MEMORY_API_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def charger_allowlist(chemin=None):
    """Lit l'allowlist (DONNÉE co-écrite) et renvoie l'ENSEMBLE des noms de
    sources autorisées. Lecture DÉFENSIVE : fichier absent/illisible → set vide
    (digue close : rien ne passe). Accepte des entrées str (nom direct) ou
    objet {nom: ...}. 'interne' est expurgé s'il s'y trouve (jamais externe)."""
    chemin = chemin or ALLOWLIST_PATH
    noms = set()
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return noms
    entrees = data.get("sources") if isinstance(data, dict) else data
    if not isinstance(entrees, list):
        return noms
    for e in entrees:
        nom = e if isinstance(e, str) else (e.get("nom") if isinstance(e, dict) else None)
        if isinstance(nom, str):
            nom = nom.strip()
            if nom and nom != "interne":
                noms.add(nom)
    return noms


def _normaliser(texte):
    """Normalise un texte brut récupéré du dehors : NFC, fins de ligne unifiées,
    espaces de fin de ligne retirés, runs de lignes vides ramenés à une, bords
    rognés. Transformation PURE (aucune I/O, aucun réseau)."""
    texte = unicodedata.normalize("NFC", str(texte or ""))
    texte = texte.replace("\r\n", "\n").replace("\r", "\n")
    lignes = [l.rstrip() for l in texte.split("\n")]
    texte = "\n".join(lignes)
    texte = re.sub(r"\n{3,}", "\n\n", texte)
    return texte.strip()


def ingerer(source_texte, source, url=None, tag=None,
            memoire=None, reseau=None, allowlist=None):
    """Ingère un texte EXTERNE déjà récupéré et l'écrit en BRUT, en posant la
    provenance `source`. Renvoie le résultat de l'écriture (dict memory_api).

    GARDES (lève ValueError, l'organe ne produit RIEN si l'une échoue) :
      - `source` vide            → REFUS (une entrée du dehors a toujours un nom) ;
      - `source` == 'interne'    → REFUS (l'organe externe ne produit JAMAIS
                                    d'interne : menace le-faux-externe-qui-s-auto
                                    -renforce) ;
      - `source` HORS allowlist  → REFUS (digue close ; menace le-faux-externe
                                    -servi-à-parité).

    RÉSEAU INJECTÉ, JAMAIS APPELÉ : `reseau` (capacité de fetch) peut être fourni
    pour la symétrie d'appel, mais cet organe ne l'invoque JAMAIS — le fetch est
    le geste de l'APPELANT. Le texte arrive déjà récupéré dans `source_texte`.

    `memoire` (défaut : module memory_api) est l'écrivain BRUT ; `allowlist`
    (défaut : ensemble lu du fichier) est injectable pour les tests. La fiche est
    écrite verifie='non' (« source fiable, fait non confirmé ») : seule Kily,
    par fiche, pose verifie='oui'."""
    source = (source or "").strip()
    if not source:
        raise ValueError("ingerer: 'source' est OBLIGATOIRE (une entrée externe a "
                         "toujours un nom de provenance).")
    if source == "interne":
        raise ValueError("ingerer: REFUS — 'interne' n'est pas une source externe. "
                         "L'organe d'ingestion ne produit JAMAIS d'interne "
                         "(menace : le-faux-externe-qui-s-auto-renforce).")
    permises = allowlist if allowlist is not None else charger_allowlist()
    if source not in permises:
        raise ValueError(
            "ingerer: REFUS — source %r HORS allowlist (digue close). Une source "
            "non approuvée par Kily ne peut pas entrer (menace : le-faux-externe-"
            "servi-à-parité). Propose-la via proposer_source ; Kily seul édite "
            "l'allowlist." % (source,))

    # Le réseau n'est JAMAIS appelé ici : le fetch est le geste de l'appelant.
    # (reseau est accepté puis ignoré : sa non-invocation est vérifiée par test.)
    _ = reseau

    mem = memoire if memoire is not None else _charger_memory_api()
    contenu = _normaliser(source_texte)
    note = {"content": contenu, "source": source, "verifie": "non"}
    if tag:
        note["tag"] = tag
    if url:
        # l'URL voyage dans le contenu (traçabilité), pas dans un canal caché.
        note["content"] = "%s\n\n[source: %s — %s]" % (contenu, source, url)
    res = dict(mem.add_note(note))
    res["source"] = source
    res["url"] = url
    return res


def proposer_source(source, frequence, echantillon, pourquoi, chemin=None):
    """PROPOSE une source à l'examen de Kily (patron clos-doublon PR68 : le
    système propose, l'humain tranche). Ajoute UNE ligne à propositions_sources
    .jsonl (append-only, examinable) et renvoie la proposition.

    Le système n'écrit JAMAIS l'allowlist : proposer n'est pas approuver. Une
    proposition porte de quoi décider : source, fréquence rencontrée, échantillon,
    et pourquoi elle mériterait d'entrer."""
    source = (source or "").strip()
    if not source:
        raise ValueError("proposer_source: 'source' est requise.")
    chemin = chemin or PROPOSITIONS_PATH
    prop = {
        "source": source,
        "frequence": frequence,
        "echantillon": echantillon,
        "pourquoi": pourquoi,
    }
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "a", encoding="utf-8") as f:
        f.write(json.dumps(prop, ensure_ascii=False) + "\n")
    return prop


def lire_propositions(chemin=None):
    """Vue LECTURE SEULE des propositions (append-only). Absent/corrompu → []."""
    chemin = chemin or PROPOSITIONS_PATH
    out = []
    if not os.path.exists(chemin):
        return out
    try:
        with open(chemin, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return out
    return out
