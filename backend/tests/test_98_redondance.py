"""Tests du gardien 98 — Signal 2 REDONDANCE honnête (couverture + sémantique opt-in).

CONTEXTE (mesuré le 11/07 sur 146 fiches réelles) : le Signal 2 de nexus_98.main()
était DOUBLEMENT aveugle —
  (1) un `break` ne mesurait qu'UNE catégorie par domaine (couverture partielle) ;
  (2) purement LEXICAL (jaccard des mots), il ratait les doublons de SENS.
Résultat : 98 comptait 0 redondance là où le lexical COMPLET en voyait 1 et le
sémantique complet (cos ≥ 0.80) en voyait 8 → l'alarme red_danger (≥3) ne se
déclenchait JAMAIS = FAUSSE SANTÉ.

Ce qu'on prouve ici :
  (a) compter_redondances (fonction PURE) : couverture COMPLÈTE (toutes catégories,
      plus de break), sémantique OPT-IN honnête (0 sans embedder), INTRA-catégorie
      only (jamais cross-cat) ;
  (b) main() sans embedder annonce le mode 'lexical seul'.

MUTATIONS ROUGES couvertes :
  (i)   réintroduire un break (ne compter qu'UNE catégorie) → test 'toutes catégories' ROUGE ;
  (ii)  compter une paire sémantique SANS embedder → test d'honnêteté ROUGE ;
  (iii) compter une paire CROSS-catégorie → test intra-cat ROUGE ;
  (iv)  écrire dans l'organe (perte de la lecture seule) → test verrou ROUGE.
"""
import os
import sys
import ast
import importlib.util

import pytest


ICI = os.path.dirname(os.path.abspath(__file__))              # backend/tests
RACINE = os.path.dirname(os.path.dirname(ICI))                # racine du dépôt
ORGANES = os.path.join(RACINE, "organes")
if ORGANES not in sys.path:
    sys.path.insert(0, ORGANES)


def _charger(nom, chemin):
    spec = importlib.util.spec_from_file_location(nom, chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def n98():
    return _charger("nexus_98_redondance_test", os.path.join(ORGANES, "nexus_98.py"))


def _fiche(file, excerpt, vecteur=None):
    d = {"file": file, "excerpt": excerpt}
    if vecteur is not None:
        d["vecteur"] = vecteur
    return d


# Embedder MOCK : simple sentinelle. compter_redondances ne l'appelle PAS (les
# vecteurs sont déjà portés par les fiches) — il sert de DRAPEAU « sémantique
# activé ». Un objet non-None suffit ; on lui donne un embed() réaliste inerte.
class EmbedderMock:
    def embed(self, text):  # pragma: no cover - non appelé par la fonction pure
        return [0.0]


# =========================================================================== #
# cosinus PUR borné [0,1], jamais d'exception.
# =========================================================================== #
def test_cosinus_pur_borne_et_robuste(n98):
    assert n98.cosinus([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert n98.cosinus([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert n98.cosinus([1.0, 0.0, 0.0], [1.0, 0.0]) == 0.0   # dims différentes → 0
    assert n98.cosinus([0.0, 0.0], [1.0, 0.0]) == 0.0        # norme nulle → 0
    assert n98.cosinus([], [1.0]) == 0.0                     # vide → 0
    # borné [0,1] : jamais négatif (deux fiches ne sont pas « moins que dissemblables »)
    assert n98.cosinus([1.0, 0.0], [-1.0, 0.0]) == 0.0


# =========================================================================== #
# (a) COUVERTURE COMPLÈTE : 2 catégories, chacune UNE paire lexicale → total=2.
#     Prouve l'ABSENCE de break (un break n'en compterait qu'une → total=1).
#     MUTATION (i) réintroduire un break → ce test passe au ROUGE.
# =========================================================================== #
def test_a_couverture_toutes_categories_pas_de_break(n98):
    lex = "budget calcul montant total"          # 4 mots > 3 lettres
    lex_proche = "budget calcul montant cout"     # jaccard = 3/5 = 0.6 ≥ 0.50
    groupes = {
        ("finance", "budgets"): [_fiche("a.md", lex), _fiche("b.md", lex_proche)],
        ("finance", "couts"):   [_fiche("c.md", lex), _fiche("d.md", lex_proche)],
    }
    r = n98.compter_redondances(groupes)
    assert r["total"] == 2, "les DEUX catégories doivent être comptées (pas de break)"
    assert r["lexical"] == 2
    assert r["semantique"] == 0


def test_a_une_seule_categorie_prouve_le_compte_par_cat(n98):
    # Une catégorie avec une paire lexicale → exactement 1 (référence pour (i)).
    groupes = {("finance", "budgets"): [
        _fiche("a.md", "budget calcul montant total"),
        _fiche("b.md", "budget calcul montant cout"),
    ]}
    assert n98.compter_redondances(groupes) == {"total": 1, "lexical": 1, "semantique": 0}


# =========================================================================== #
# (a) SÉMANTIQUE OPT-IN : une paire proche par le SENS (mots disjoints,
#     jaccard = 0) n'est comptée QUE si un embedder est fourni. Sans embedder →
#     semantique = 0 (honnêteté : jamais un faux score).
#     MUTATION (ii) compter la paire sémantique sans embedder → ROUGE.
# =========================================================================== #
def test_a_paire_par_le_sens_comptee_seulement_avec_embedder(n98):
    # "voiture/rapide" vs "automobile/veloce" : AUCUN mot commun (jaccard = 0),
    # mais vecteurs cos ≈ 0.97 (≥ 0.80).
    groupes = {("transport", "vehicules"): [
        _fiche("v.md", "voiture rapide", vecteur=[1.0, 0.0, 0.0]),
        _fiche("w.md", "automobile veloce", vecteur=[0.9, 0.2, 0.1]),
    ]}
    # Sans embedder : jaccard = 0 < 0.50 ET sémantique désactivé → RIEN.
    sans = n98.compter_redondances(groupes, embedder=None)
    assert sans == {"total": 0, "lexical": 0, "semantique": 0}
    # Avec embedder mock : la proximité de SENS est comptée (et SEULEMENT en sémantique).
    avec = n98.compter_redondances(groupes, embedder=EmbedderMock())
    assert avec == {"total": 1, "lexical": 0, "semantique": 1}


def test_a_sans_embedder_semantique_toujours_zero(n98):
    # Même avec des vecteurs identiques portés par les fiches, sans embedder le
    # sémantique reste 0 (le drapeau embedder=None le désactive intégralement).
    groupes = {("d", "c"): [
        _fiche("x.md", "alpha bravo", vecteur=[1.0, 0.0]),
        _fiche("y.md", "charlie delta", vecteur=[1.0, 0.0]),   # cos = 1, mots disjoints
    ]}
    r = n98.compter_redondances(groupes, embedder=None)
    assert r["semantique"] == 0 and r["total"] == 0


def test_a_pas_de_double_comptage_lexical_et_semantique(n98):
    # Une paire à la fois lexicale ET sémantiquement proche compte UNE fois, en
    # LEXICAL (partition non chevauchante : total = lexical + semantique).
    groupes = {("d", "c"): [
        _fiche("x.md", "budget calcul montant total", vecteur=[1.0, 0.0, 0.0]),
        _fiche("y.md", "budget calcul montant cout", vecteur=[0.99, 0.1, 0.0]),
    ]}
    r = n98.compter_redondances(groupes, embedder=EmbedderMock())
    assert r == {"total": 1, "lexical": 1, "semantique": 0}


# =========================================================================== #
# (a) INTRA-CATÉGORIE only : deux fiches proches dans DEUX catégories
#     DIFFÉRENTES ne forment PAS une paire → non comptées.
#     MUTATION (iii) compter une paire cross-cat → ce test passe au ROUGE.
# =========================================================================== #
def test_a_cross_categorie_jamais_comptee_lexical(n98):
    dup = "budget calcul montant total"
    groupes = {
        ("finance", "budgets"): [_fiche("a.md", dup)],   # 1 fiche → aucune paire interne
        ("finance", "couts"):   [_fiche("b.md", dup)],   # duplicata EXACT, autre catégorie
    }
    r = n98.compter_redondances(groupes)
    assert r == {"total": 0, "lexical": 0, "semantique": 0}, "cross-cat ne doit JAMAIS compter"


def test_a_cross_categorie_jamais_comptee_semantique(n98):
    groupes = {
        ("t", "a"): [_fiche("v.md", "voiture rapide", vecteur=[1.0, 0.0, 0.0])],
        ("t", "b"): [_fiche("w.md", "automobile veloce", vecteur=[0.9, 0.2, 0.1])],
    }
    # Vecteurs cos ≈ 0.97 MAIS catégories différentes → jamais une paire.
    assert n98.compter_redondances(groupes, embedder=EmbedderMock())["total"] == 0


# =========================================================================== #
# DÉFENSIF : compter_redondances ne lève JAMAIS sur entrées dégénérées.
# =========================================================================== #
def test_defensif_entrees_degradees_jamais_dexception(n98):
    assert n98.compter_redondances(None) == {"total": 0, "lexical": 0, "semantique": 0}
    assert n98.compter_redondances({}) == {"total": 0, "lexical": 0, "semantique": 0}
    # valeurs non-listes et fiches non-dict ignorées, pas d'exception
    groupes = {("d", "c1"): None, ("d", "c2"): ["pas un dict", 42, None]}
    assert n98.compter_redondances(groupes) == {"total": 0, "lexical": 0, "semantique": 0}
    # embedder présent mais vecteurs absents/incompatibles → retombe au lexical, jamais de crash
    groupes2 = {("d", "c"): [_fiche("a.md", "alpha bravo"), _fiche("b.md", "charlie delta")]}
    assert n98.compter_redondances(groupes2, embedder=EmbedderMock()) == {
        "total": 0, "lexical": 0, "semantique": 0}


# =========================================================================== #
# (b) main() SANS embedder → affiche le mode 'lexical seul' (honnêteté du mode).
# =========================================================================== #
def test_b_main_sans_embedder_mode_lexical_seul(n98, monkeypatch, capsys):
    domains = {"finance": {"budgets": [{}, {}]}}
    reponses = {
        "/stats": {"structure_fiches": 2, "cap": 200, "remplissage": 0.0},
        "/domains": {"domains": domains},
    }

    def fake_get(path):
        if path.startswith("/recall"):
            return {"results": [
                {"file": "a.md", "excerpt": "budget calcul montant total"},
                {"file": "b.md", "excerpt": "budget calcul montant cout"},
            ]}
        return reponses[path]

    monkeypatch.setattr(n98, "get", fake_get)
    monkeypatch.setattr(n98.nexus_sense, "lire", lambda: [])
    # Force l'ABSENCE d'embedder (déterministe, indépendant de l'install locale).
    import nexus_embedder
    monkeypatch.setattr(nexus_embedder, "charger_embedder", lambda *a, **k: None)

    n98.main()
    out = capsys.readouterr().out
    assert "lexical seul" in out
    assert "sémantique" not in out.split("Redondance")[1].split("\n")[0]  # mode annoncé sans sens
    # Le compte lexical complet (jaccard 0.6 ≥ 0.50) apparaît : 1 paire.
    assert "Redondance : 1 paire(s)" in out


# =========================================================================== #
# (iv) VERROU LECTURE SEULE : l'organe 98 n'ouvre AUCUN fichier en écriture, et
#      compter_redondances ne crée aucun fichier. MUTATION (iv) → ROUGE.
# =========================================================================== #
def _modes_open(source):
    modes = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            fn = node.func
            nom = getattr(fn, "id", None) or getattr(fn, "attr", None)
            if nom != "open":
                continue
            mode = "r"
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                mode = node.args[1].value
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = kw.value.value
            modes.append(mode or "")
    return modes


def test_iv_organe_98_reste_lecture_seule(n98):
    source = open(os.path.join(ORGANES, "nexus_98.py"), encoding="utf-8").read()
    ecritures = [m for m in _modes_open(source) if any(c in m for c in "wax+")]
    assert ecritures == [], f"98 doit rester lecture seule ; écritures trouvées : {ecritures}"


def test_iv_compter_redondances_ne_cree_aucun_fichier(n98, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    groupes = {("d", "c"): [
        _fiche("a.md", "budget calcul montant total"),
        _fiche("b.md", "budget calcul montant cout"),
    ]}
    n98.compter_redondances(groupes, embedder=EmbedderMock())
    assert os.listdir(tmp_path) == [], "compter_redondances (PURE) ne doit rien écrire"
