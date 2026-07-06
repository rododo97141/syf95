#!/usr/bin/env python3
"""
NEXUS — Friday · brique 1 : lecteur (exécuteur LECTURE SEULE PAR CONSTRUCTION)
« Des yeux, pas de mains. »

VERROU STRUCTUREL, pas un if : ce module ne CONTIENT et n'IMPORTE aucun
chemin d'écriture. Imports fermés : os et ast, rien d'autre. L'unique porte
de lecture est _texte() / open(..., "r") — aucun open en écriture, aucun
append, aucun makedirs/remove/rename, aucun subprocess. nexus_sense n'est
PAS importé ici : log_event ÉCRIT, la force vivante est donc câblée dans
friday_coeur, de l'autre côté de la frontière. Le verrou est PROUVÉ par
tests : inspection AST du module, exécution sur répertoire chmod lecture
seule (zéro tentative, zéro erreur), empreintes binaires avant/après.

Actions (sortie = texte prêt à être lu par un TTS, phrases simples) :
  chercher(nom)   — où est un fichier / une fonction dans le dépôt
  montrer(nom)    — lire un extrait (premières lignes) d'un fichier
  expliquer(nom)  — renvoyer le docstring / l'en-tête d'un module ou d'une fonction
  statut()        — état via FICHIERS LOCAUX seulement : branche (.git/HEAD),
                    nombre de fichiers de tests, d'organes, d'événements capteurs
"""
import os, ast

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RACINE_DEFAUT = os.path.dirname(SCRIPT_DIR)

DOSSIERS_EXCLUS = {".git", "__pycache__", ".claude", "node_modules", ".pytest_cache"}
# Articles retirés en tête d'argument (« montre le moteur » → « moteur »).
# Table déclarée, fermée — même doctrine que le routeur : pas de fuzzy.
ARTICLES = ("le", "la", "les", "l", "un", "une", "du", "de", "d", "mon", "ma", "mes")
LIGNES_EXTRAIT = 20
MAX_RESULTATS = 8


def _racine(racine=None):
    return os.path.abspath(racine) if racine else RACINE_DEFAUT


def _texte(chemin):
    """Porte de lecture UNIQUE du module — mode "r" explicite, jamais autre chose."""
    with open(chemin, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _fichiers(racine):
    for dossier, sous, noms in os.walk(racine):
        sous[:] = sorted(s for s in sous if s not in DOSSIERS_EXCLUS)
        for nom in sorted(noms):
            yield os.path.join(dossier, nom)


def _rel(chemin, racine):
    return os.path.relpath(chemin, racine)


def _candidats(nom):
    """Variantes déclarées du nom demandé : sans articles de tête, et la même
    chose avec des tirets bas (« friday routeur » ↔ « friday_routeur »)."""
    mots = (nom or "").lower().split()
    while mots and mots[0] in ARTICLES:
        mots = mots[1:]
    if not mots:
        return []
    plein = " ".join(mots)
    return list(dict.fromkeys([plein, "_".join(mots)]))


def _trouver_fichier(nom, racine):
    """Meilleur fichier pour un nom : correspondance exacte d'abord (avec ou
    sans extension .py/.md), sinon premier nom de fichier qui contient le nom."""
    candidats = _candidats(nom)
    exact, partiel = None, None
    for chemin in _fichiers(racine):
        base = os.path.basename(chemin).lower()
        for c in candidats:
            if base in (c, c + ".py", c + ".md"):
                exact = exact or chemin
            elif c in base:
                partiel = partiel or chemin
    return exact or partiel


def chercher(nom, racine=None):
    """« Où est Y » — fichiers dont le nom correspond, fonctions/classes
    définies dans les .py. Texte prêt pour un TTS."""
    racine = _racine(racine)
    candidats = _candidats(nom)
    if not candidats:
        return "Je n'ai rien à chercher : la commande ne contient pas de nom."
    fichiers, fonctions = [], []
    for chemin in _fichiers(racine):
        base = os.path.basename(chemin).lower()
        if any(c in base for c in candidats):
            fichiers.append(_rel(chemin, racine))
        if chemin.endswith(".py"):
            for numero, ligne in enumerate(_texte(chemin).splitlines(), 1):
                depouillee = ligne.strip()
                if any(depouillee.startswith(mot + c)
                       for c in candidats for mot in ("def ", "class ")):
                    tete = depouillee.split("(")[0].split(":")[0]
                    fonctions.append(f"{tete} dans {_rel(chemin, racine)}, ligne {numero}")
    fichiers, fonctions = fichiers[:MAX_RESULTATS], fonctions[:MAX_RESULTATS]
    if not fichiers and not fonctions:
        return f"Je n'ai pas trouvé {nom} dans le dépôt."
    phrases = [f"Pour {nom}, j'ai trouvé {len(fichiers)} fichier et {len(fonctions)} définition."]
    phrases += [f"Fichier {f}." for f in fichiers]
    phrases += [f"{fn}." for fn in fonctions]
    return " ".join(phrases)


def montrer(nom, racine=None):
    """« Montre X » — extrait (premières lignes) du fichier correspondant."""
    racine = _racine(racine)
    chemin = _trouver_fichier(nom, racine)
    if chemin is None:
        return f"Je n'ai pas trouvé de fichier pour {nom}."
    lignes = _texte(chemin).splitlines()
    extrait = lignes[:LIGNES_EXTRAIT]
    tete = f"Extrait de {_rel(chemin, racine)}, lignes 1 à {len(extrait)} sur {len(lignes)}."
    return tete + "\n" + "\n".join(extrait)


def _docstring_ou_entete(chemin):
    """Docstring du module s'il existe, sinon les commentaires d'en-tête."""
    source = _texte(chemin)
    if chemin.endswith(".py"):
        try:
            doc = ast.get_docstring(ast.parse(source))
            if doc:
                return doc.strip()
        except SyntaxError:
            pass
        entete = []
        for ligne in source.splitlines():
            if ligne.strip().startswith("#"):
                entete.append(ligne.strip().lstrip("#").strip())
            elif entete:
                break
        return "\n".join(entete) if entete else None
    premieres = [l for l in source.splitlines() if l.strip()][:5]
    return "\n".join(premieres) if premieres else None


def expliquer(nom, racine=None):
    """« Explique Z » — docstring/en-tête d'un module, ou docstring d'une
    fonction/classe portant ce nom."""
    racine = _racine(racine)
    chemin = _trouver_fichier(nom, racine)
    if chemin is not None:
        doc = _docstring_ou_entete(chemin)
        if doc:
            return f"{_rel(chemin, racine)} : {doc}"
    candidats = _candidats(nom)
    for fichier in _fichiers(racine):
        if not fichier.endswith(".py"):
            continue
        try:
            arbre = ast.parse(_texte(fichier))
        except SyntaxError:
            continue
        for noeud in ast.walk(arbre):
            if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                    and noeud.name.lower() in candidats:
                doc = ast.get_docstring(noeud) or "pas de docstring"
                return f"{noeud.name}, dans {_rel(fichier, racine)} : {doc.strip()}"
    return f"Je n'ai pas trouvé d'explication pour {nom}."


def statut(racine=None):
    """« Statut » — état du dépôt via fichiers locaux uniquement : branche
    courante (celle de la PR en cours) lue dans .git/HEAD, comptes de tests,
    d'organes et d'événements capteurs (chemin CAPTEURS_ROOT respecté, en
    lecture seule)."""
    racine = _racine(racine)
    branche = "inconnue"
    head = os.path.join(racine, ".git", "HEAD")
    if os.path.exists(head):
        contenu = _texte(head).strip()
        branche = contenu.split("refs/heads/")[-1] if "refs/heads/" in contenu else "détachée"
    dossier_tests = os.path.join(racine, "backend", "tests")
    nb_tests = len([n for n in os.listdir(dossier_tests)
                    if n.startswith("test_") and n.endswith(".py")]) \
        if os.path.isdir(dossier_tests) else 0
    dossier_organes = os.path.join(racine, "organes")
    nb_organes = len([n for n in os.listdir(dossier_organes) if n.endswith(".py")]) \
        if os.path.isdir(dossier_organes) else 0
    base = os.environ.get("CAPTEURS_ROOT") or os.path.join(racine, "organes", "memoire_data")
    journal = os.path.join(base, "capteurs", "journal.jsonl")
    nb_evenements = len([l for l in _texte(journal).splitlines() if l.strip()]) \
        if os.path.exists(journal) else 0
    return (f"Statut du dépôt. Branche courante : {branche}. "
            f"{nb_tests} fichiers de tests. {nb_organes} organes. "
            f"{nb_evenements} événements capteurs enregistrés.")
