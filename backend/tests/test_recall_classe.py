"""Non-régression du CLASSEMENT de recall() (mémoire-beta).

recall() ne filtre plus par sous-chaîne : il classe les fiches par
pertinence(IDF) × force (ROOT/forces.json, défaut 1.0). On vérifie ici les
trois propriétés du classement, sans toucher au vrai memoire_data/ (module
rechargé et racine redirigée vers un dossier temporaire jetable) :

  1. top-1 sur un token distinctif ;
  2. pas de faux gagnant confiant sur un token commun à beaucoup de fiches
     (présence binaire : le bourrage de mots-clés n'élève pas le score) ;
  3. à pertinence égale, un multiplicateur élevé dans forces.json fait
     remonter la fiche en tête.

On vérifie aussi que la forme de retour reste EXACTEMENT
etage/domain/category/file/path/excerpt (aucune fuite de clé interne).
"""
import os
import json
import importlib.util

import pytest


def _charger_memory_api():
    """Recharge un module memory_api frais (pas d'état partagé entre tests)."""
    ici = os.path.dirname(os.path.abspath(__file__))          # backend/tests
    racine = os.path.dirname(os.path.dirname(ici))            # racine du dépôt
    chemin = os.path.join(racine, ".claude", "skills", "memoire-beta",
                          "scripts", "memory_api.py")
    spec = importlib.util.spec_from_file_location("memory_api_test", chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mem(tmp_path):
    m = _charger_memory_api()
    root = tmp_path / "memoire_data"
    m.ROOT = str(root)
    m.STRUCT = str(root / "structure")
    m.EN_ATTENTE = str(root / "en_attente")
    m.BRUT = str(root / "brut")
    m.ARCHIVE = str(root / "archive")
    os.makedirs(m.STRUCT, exist_ok=True)
    return m


def _fiche(m, domain, category, nom, contenu):
    d = os.path.join(m.STRUCT, domain, category)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, nom + ".md"), "w", encoding="utf-8") as f:
        f.write(contenu)


def _recall(m, token):
    return m.recall({"query": [token], "scope": ["structure"]})


# --------------------------------------------------------------------------- #
# 1. top-1 sur un token distinctif
# --------------------------------------------------------------------------- #
def test_top1_token_distinctif(mem):
    _fiche(mem, "dom", "cat", "commun_a", "projet équipe réunion budget")
    _fiche(mem, "dom", "cat", "commun_b", "projet planning budget client")
    _fiche(mem, "dom", "cat", "rare", "projet zorglubide singulier")

    res = _recall(mem, "zorglubide")

    assert res["ok"] is True
    assert res["count"] == 1
    assert res["results"][0]["file"] == "rare.md"

    # forme de retour préservée, aucune clé interne ne fuit
    top = res["results"][0]
    assert set(top.keys()) == {"etage", "domain", "category",
                               "file", "path", "excerpt"}
    assert top["domain"] == "dom" and top["category"] == "cat"


# --------------------------------------------------------------------------- #
# 2. pas de faux gagnant confiant sur un token commun
# --------------------------------------------------------------------------- #
def test_pas_de_faux_gagnant_token_commun(mem):
    for i in range(5):
        _fiche(mem, "dom", "cat", "f%d" % i, "commun contexte mot%d" % i)
    # décoy qui « bourre » le token commun de nombreuses fois
    _fiche(mem, "dom", "cat", "decoy", "commun commun commun commun commun")

    res = _recall(mem, "commun")

    # classement non destructif : les 6 fiches contenant le token sont là
    assert res["count"] == 6

    # white-box : à token présent partout, pertinences toutes égales -> aucun
    # gagnant confiant, et le bourrage de mots-clés n'élève pas le score.
    cands = mem._scan(mem.STRUCT, "commun", "structure")
    ranked = mem.rank_candidates("commun", cands, forces={})
    relevances = [r["_relevance"] for r in ranked]
    assert max(relevances) == min(relevances)          # tous à égalité

    scores = [r["_score"] for r in ranked]
    decoy = next(r for r in ranked if r["file"] == "decoy.md")
    assert decoy["_score"] == max(scores)              # pas STRICTEMENT au-dessus
    assert decoy["_score"] == min(scores)


# --------------------------------------------------------------------------- #
# 3. forces.json départage à pertinence égale
# --------------------------------------------------------------------------- #
def test_force_departage_a_egalite(mem):
    _fiche(mem, "dom", "cat", "alpha", "projet distinctifxyz contenu")
    _fiche(mem, "dom", "cat", "beta",  "projet distinctifxyz contenu")

    # sans forces.json : pertinence égale -> ordre stable (par chemin/nom)
    res0 = _recall(mem, "distinctifxyz")
    assert [r["file"] for r in res0["results"]] == ["alpha.md", "beta.md"]

    # forces.json boost sur beta -> beta remonte en tête à pertinence égale
    with open(os.path.join(mem.ROOT, "forces.json"), "w", encoding="utf-8") as f:
        json.dump({"beta": 5.0}, f)

    res1 = _recall(mem, "distinctifxyz")
    assert res1["results"][0]["file"] == "beta.md"
    assert [r["file"] for r in res1["results"]] == ["beta.md", "alpha.md"]


def test_forces_absent_multiplicateur_defaut(mem):
    # forces.json absent -> load_forces() renvoie {} et le multiplicateur = 1.0
    _fiche(mem, "dom", "cat", "seule", "projet distinctifabc contenu")
    assert mem.load_forces() == {}
    assert mem._force_for({}, "seule.md", "structure/dom/cat/seule.md") == 1.0

    res = _recall(mem, "distinctifabc")
    assert res["count"] == 1 and res["results"][0]["file"] == "seule.md"
