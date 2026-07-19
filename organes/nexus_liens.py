#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEXUS — nexus_liens : la PORTE À SEUIL DES LIENS.

« Une promotion "par résonance" calcule des liens entre fiches de la mémoire
structurée puis les JETTE (n'écrit que "N fiches reliées", sans dire
lesquelles) — mesure du 19/07 : 165 nœuds, 0 arête persistée. » Ce module
donne à ce calcul une SORTIE : des liens ÉPROUVÉS, gardés, nommés.

MÊME PATRON que la porte à seuil de la force (nexus_force) : un signal
faiblement éprouvé ne pilote pas le résultat.
  - force : trop peu d'événements  → le multiplicateur reste au défaut.
  - lien  : vocabulaire commun     → aucun lien n'est retenu.

Poids d'un lien = cosinus TF-IDF BINAIRE sur les tokens (≥4 lettres, hors
stopwords fr) de deux fiches : chaque token présent pèse son IDF (rare =
lourd, commun = ~1), la présence est binaire (le bourrage ne gonfle rien).
Des termes RARES partagés = du SENS. `ponderation="brute"` met le poids de
chaque token à 1 (ignore l'IDF) : le vocabulaire commun DOMINE alors le
cosinus — c'est le réglage qui laisse le bruit remonter, gardé ici pour
INSTRUMENTER la porte (cf. tests de mutation), jamais pour un usage réel.

PORTE À SEUIL : un lien n'est gardé que si poids ≥ min_poids. Au-delà, au
plus `top_k` liens par fiche (les plus forts) — un signal faible ne pilote
jamais le graphe, même sous le seuil il ne peut pas s'accumuler en masse.

Garde-fous :
  - PUR et LECTURE SEULE : construire_liens/voisins ne touchent jamais le
    disque en écriture ; seul persister() écrit, et uniquement le fichier
    demandé.
  - DÉTERMINISTE : tri stable partout (poids décroissant puis ids), aucune
    dépendance à l'ordre du système de fichiers.
  - Les basenames de `exclure` (défaut : "_index.md") ne sont même pas des
    nœuds du graphe — un sommaire partage du vocabulaire avec tout, un faux
    carrefour n'est pas un lien.
  - Honnête = protégé du BRUIT (vocabulaire commun), pas du FAUSSAIRE (une
    fiche peut mentir sur son contenu et rester sous le seuil, ou l'inverse :
    la porte ne juge que la friction lexicale, jamais la véracité).

Usage bibliothèque :
    graphe = construire_liens(struct_root)
    voisins(graphe, "api")
    persister(graphe, "/chemin/vers/liens.json")
"""
import os
import re
import math
import json

_TOKEN_RE = re.compile(r"[0-9a-zà-ÿ_]+", re.IGNORECASE)
_MIN_LEN_TOKEN = 4

# Stopwords fr COURANTS (mots grammaticaux) de ≥4 lettres. Les mots plus courts
# (le, la, de, un, et, ou...) sont déjà éliminés par _MIN_LEN_TOKEN. Ce filtre
# retire la GRAMMAIRE ; le vocabulaire commun mais lexical (« système »,
# « fonction »...) reste — c'est l'IDF, pas ce filtre, qui le fait peser peu.
FR_STOPWORDS = frozenset({
    "dans", "pour", "avec", "sans", "sous", "vers", "chez", "entre",
    "cette", "cettui", "leur", "leurs", "nous", "vous", "elle", "elles",
    "être", "etre", "avoir", "fait", "faire", "sont", "était", "etait",
    "avait", "avaient", "étaient", "etaient", "tout", "tous", "toute",
    "toutes", "autre", "autres", "comme", "aussi", "alors", "donc", "mais",
    "plus", "moins", "très", "tres", "peut", "peuvent", "doit", "doivent",
    "cela", "ceci", "celui", "celle", "ceux", "celles", "ainsi", "quand",
    "quel", "quelle", "quels", "quelles", "lequel", "laquelle", "notre",
    "votre", "nos", "vos", "même", "meme", "voici", "voilà", "voila",
    "ici", "chaque", "certains", "certaines", "certain", "certaine",
})

DEFAULT_TOP_K = 3
DEFAULT_EXCLURE = ("_index.md",)
DEFAULT_MIN_POIDS = 0.08
DEFAULT_PONDERATION = "idf"
MAX_POURQUOI = 5


# --------------------------------------------------------------------------- #
# Tokenisation
# --------------------------------------------------------------------------- #
def _tokens(texte):
    bruts = _TOKEN_RE.findall((texte or "").lower())
    return [t for t in bruts if len(t) >= _MIN_LEN_TOKEN and t not in FR_STOPWORDS]


# --------------------------------------------------------------------------- #
# Lecture de la mémoire structurée — PUR, LECTURE SEULE
# --------------------------------------------------------------------------- #
def _lister_fiches(struct_root, exclure):
    """Fiches .md de struct_root (récursif), hors basenames de `exclure`.
    Triées par chemin relatif : déterminisme indépendant de l'ordre renvoyé
    par le système de fichiers. `dom` = dossier 2 niveaux au-dessus du
    fichier (struct_root/DOMAINE/categorie/fiche.md)."""
    exclues = set(exclure or ())
    fiches = []
    if not struct_root or not os.path.isdir(struct_root):
        return fiches
    for dp, _dirs, files in os.walk(struct_root):
        for fl in files:
            if not fl.endswith(".md") or fl in exclues:
                continue
            chemin = os.path.join(dp, fl)
            rel = os.path.relpath(chemin, struct_root)
            dom = os.path.basename(os.path.dirname(os.path.dirname(chemin)))
            fiches.append({"id": fl[:-3], "chemin": chemin, "rel": rel, "dom": dom})
    fiches.sort(key=lambda f: f["rel"])
    return fiches


def _corpus_tokens(fiches):
    """{id: set(tokens)} — un jeu de tokens PRÉSENTS (TF binaire) par fiche."""
    out = {}
    for f in fiches:
        try:
            with open(f["chemin"], encoding="utf-8") as fh:
                texte = fh.read()
        except OSError:
            texte = ""
        out[f["id"]] = set(_tokens(texte))
    return out


def _idf(token_sets):
    """IDF lissé sur le corpus des fiches GARDÉES (exclues déjà retirées en
    amont) : log((N+1)/(df+1)) + 1 — ~1 pour un token présent partout (le
    vocabulaire commun), élevé pour un token rare (le sens)."""
    n = len(token_sets) or 1
    tous = set()
    for toks in token_sets.values():
        tous |= toks
    idf = {}
    for t in tous:
        df = sum(1 for toks in token_sets.values() if t in toks)
        idf[t] = math.log((n + 1) / (df + 1)) + 1.0
    return idf


def _poids_token(t, idf, ponderation):
    """Poids d'un token dans le vecteur d'une fiche. `ponderation="idf"` :
    son IDF (rare = lourd). `ponderation="brute"` : 1 pour tout token présent
    — le vocabulaire commun pèse alors AUTANT que le rare, donc domine le
    cosinus dès qu'il est plus abondant (c'est le réglage-bruit)."""
    return idf.get(t, 1.0) if ponderation == "idf" else 1.0


def _cosinus(a_toks, b_toks, idf, ponderation):
    """Cosinus TF-IDF BINAIRE entre deux fiches : composante d'un token
    présent = son poids (même poids des deux côtés, cohérent avec un
    dictionnaire IDF unique de corpus), absent = 0."""
    partages = a_toks & b_toks
    if not partages:
        return 0.0
    dot = sum(_poids_token(t, idf, ponderation) ** 2 for t in partages)
    norme_a = math.sqrt(sum(_poids_token(t, idf, ponderation) ** 2 for t in a_toks))
    norme_b = math.sqrt(sum(_poids_token(t, idf, ponderation) ** 2 for t in b_toks))
    if norme_a == 0.0 or norme_b == 0.0:
        return 0.0
    return dot / (norme_a * norme_b)


def _pourquoi(a_toks, b_toks, idf):
    """Jusqu'à MAX_POURQUOI termes RARES partagés : tri par IDF décroissant
    (le plus rare d'abord) puis alphabétique (déterminisme). TOUJOURS basé
    sur l'IDF réel, même en `ponderation="brute"` — le "pourquoi" documente
    ce qui fait sens, indépendamment du réglage qui a produit le poids."""
    partages = a_toks & b_toks
    tries = sorted(partages, key=lambda t: (-idf.get(t, 1.0), t))
    return tries[:MAX_POURQUOI]


# --------------------------------------------------------------------------- #
# LA PORTE
# --------------------------------------------------------------------------- #
def construire_liens(struct_root, top_k=DEFAULT_TOP_K, exclure=DEFAULT_EXCLURE,
                      min_poids=DEFAULT_MIN_POIDS, ponderation=DEFAULT_PONDERATION,
                      garder_pourquoi=True):
    """Construit le graphe de liens ÉPROUVÉS de la mémoire structurée.
    PUR, LECTURE SEULE — n'écrit jamais rien (cf. persister()).

    Un lien candidat existe entre deux fiches si son poids (cosinus TF-IDF
    binaire) ≥ min_poids (LA PORTE). Parmi ses candidats, chaque fiche ne
    RETIENT que ses top_k plus forts (déterminisme : poids décroissant puis
    id du partenaire). L'arête finale est gardée si AU MOINS une des deux
    fiches l'a retenue dans son top_k (union, pas intersection) — un lien
    fort dans un seul sens reste un lien réel.

    Renvoie {noeuds, top_k_par_noeud, min_poids, aretes_total,
    aretes_inter_domaine, isoles, aretes:[{a,a_dom,b,b_dom,poids,
    inter_domaine,pourquoi?}]}."""
    fiches = _lister_fiches(struct_root, exclure)
    ids = [f["id"] for f in fiches]
    dom_de = {f["id"]: f["dom"] for f in fiches}
    token_sets = _corpus_tokens(fiches)
    idf = _idf(token_sets)

    poids_paire = {}     # (min_id, max_id) -> poids, calculé une fois par paire
    candidats = {}       # id -> [(poids, autre_id), ...] (côté de chaque fiche)
    for i in range(len(fiches)):
        for j in range(i + 1, len(fiches)):
            a, b = fiches[i]["id"], fiches[j]["id"]
            poids = _cosinus(token_sets[a], token_sets[b], idf, ponderation)
            if poids < min_poids:
                continue
            paire = tuple(sorted((a, b)))
            poids_paire[paire] = poids
            candidats.setdefault(a, []).append((poids, b))
            candidats.setdefault(b, []).append((poids, a))

    selectionnees = set()
    for fid in ids:
        cands = sorted(candidats.get(fid, []), key=lambda pa: (-pa[0], pa[1]))
        for poids, autre in cands[:top_k]:
            selectionnees.add(tuple(sorted((fid, autre))))

    aretes = []
    for (a, b) in selectionnees:
        poids = poids_paire[(a, b)]
        dom_a, dom_b = dom_de[a], dom_de[b]
        entree = {
            "a": a, "a_dom": dom_a,
            "b": b, "b_dom": dom_b,
            "poids": round(poids, 6),
            "inter_domaine": dom_a != dom_b,
        }
        if garder_pourquoi:
            entree["pourquoi"] = _pourquoi(token_sets[a], token_sets[b], idf)
        aretes.append(entree)
    aretes.sort(key=lambda e: (-e["poids"], e["a"], e["b"]))

    degre = {fid: 0 for fid in ids}
    for e in aretes:
        degre[e["a"]] += 1
        degre[e["b"]] += 1

    return {
        "noeuds": len(ids),
        "top_k_par_noeud": top_k,
        "min_poids": min_poids,
        "aretes_total": len(aretes),
        "aretes_inter_domaine": sum(1 for e in aretes if e["inter_domaine"]),
        "isoles": sum(1 for fid in ids if degre[fid] == 0),
        "aretes": aretes,
    }


def voisins(graphe, fiche_id):
    """Voisins de `fiche_id` dans un graphe déjà construit — LECTURE SEULE,
    ne recalcule rien. Triés (poids décroissant puis id du voisin)."""
    out = []
    for e in graphe.get("aretes", []):
        if e["a"] == fiche_id:
            autre, dom_autre = e["b"], e["b_dom"]
        elif e["b"] == fiche_id:
            autre, dom_autre = e["a"], e["a_dom"]
        else:
            continue
        item = {
            "voisin": autre, "voisin_dom": dom_autre,
            "poids": e["poids"], "inter_domaine": e["inter_domaine"],
        }
        if "pourquoi" in e:
            item["pourquoi"] = e["pourquoi"]
        out.append(item)
    out.sort(key=lambda it: (-it["poids"], it["voisin"]))
    return out


def persister(graphe, out_path):
    """SEUL point d'écriture du module. Écrit `graphe` (JSON, déterministe :
    clés triées) dans out_path, crée les dossiers manquants. Renvoie out_path."""
    dossier = os.path.dirname(out_path)
    if dossier:
        os.makedirs(dossier, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(graphe, f, ensure_ascii=False, indent=2, sort_keys=True)
    return out_path


# --------------------------------------------------------------------------- #
# CLI — dry-run par défaut (n'écrit que si --persister CHEMIN est fourni)
# --------------------------------------------------------------------------- #
def _racine_structure():
    base = os.environ.get("MEMOIRE_ROOT")
    if not base:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        racine_depot = os.path.dirname(script_dir)
        base = os.path.join(racine_depot, ".claude", "skills", "memoire-beta",
                             "scripts", "memoire_data")
    return os.path.join(base, "structure")


def main():
    import sys
    argv = sys.argv[1:]
    struct_root = _racine_structure()
    graphe = construire_liens(struct_root)
    print("🔗 NEXUS — nexus_liens (porte à seuil des liens)\n")
    print("   %d nœud(s) · min_poids=%.2f · top_k=%d"
          % (graphe["noeuds"], graphe["min_poids"], graphe["top_k_par_noeud"]))
    print("   %d arête(s) gardée(s) (%d inter-domaine) · %d fiche(s) isolée(s)"
          % (graphe["aretes_total"], graphe["aretes_inter_domaine"], graphe["isoles"]))
    for e in graphe["aretes"]:
        print("     · %s (%s)  ↔  %s (%s)  poids=%.3f%s"
              % (e["a"], e["a_dom"], e["b"], e["b_dom"], e["poids"],
                 "  [inter-domaine]" if e["inter_domaine"] else ""))
    if "--persister" in argv:
        idx = argv.index("--persister")
        if idx + 1 < len(argv):
            chemin = persister(graphe, argv[idx + 1])
            print("\n✅ Écrit dans %s" % chemin)
        else:
            print("\n⚠️  --persister requiert un chemin.")
    else:
        print("\n🛡️  DRY-RUN : rien écrit. Relancer avec --persister CHEMIN pour écrire.")


if __name__ == "__main__":
    main()
