# -*- coding: utf-8 -*-
"""
nexus_liens — la PORTE À SEUIL DES LIENS.

Contexte : la promotion « par résonance » calculait des liens entre fiches
de la mémoire structurée puis les JETAIT (n'écrivait que « N fiches
reliées », sans dire lesquelles) — mesure du 19/07 : 165 nœuds, 0 arête
persistée. nexus_liens.construire_liens() donne à ce calcul une SORTIE : des
liens ÉPROUVÉS (poids ≥ min_poids), au plus top_k par fiche, avec leur
« pourquoi ».

Fixture (6 fiches, structure/DOMAINE/categorie/fiche.md) :
  - 3 fiches de SENS (api, moteur, writepath) qui partagent 3 termes RARES
    du corpus (« appels », « persistance », « survit ») — le sens.
  - 1 PAIRE DE BRUIT (bruit_a « Jardin », bruit_b « Cuisine») qui ne partage
    que 2 mots génériques (« remplissage », « générique ») noyés dans ~18
    mots privés chacune — le bruit : IDF les traite en RARES (partagés
    seulement par ces deux fiches), le cosinus IDF reste sous le seuil, mais
    en pondération BRUTE (chaque token = poids 1, quelle que soit sa
    rareté) le même partage remonte au-dessus.
  - 1 _index (faux carrefour : résume le vocabulaire des 3 fiches de sens).

Ce que ces tests VERROUILLENT (et les MUTATIONS ROUGE qu'ils détectent) :
  - déterminisme (deux builds identiques) ;
  - golden : exactement les 3 liens de sens au défaut ;
  - la porte À SEUIL bloque la paire de bruit (poids < min_poids par défaut) ;
  - aucun lien _index par défaut (basename exclu = pas un nœud) ;
  - chaque lien garde un « pourquoi » (≤5 termes rares) ;
  - un lien inter-domaine existe (api/moteur au dossier « moteur »,
    writepath au dossier « ecriture ») ;
  MUTATIONS (chacune DOIT faire échouer sa propre assertion) :
    (i)   min_poids=0        -> le bruit passe (porte grande ouverte) ;
    (ii)  exclure=()         -> _index revient comme nœud/lien ;
    (iii) ponderation="brute"-> le bruit remonte au-dessus du seuil ;
    (iv)  garder_pourquoi=False -> un lien existe sans « pourquoi ».
"""
import os
import sys

ORGANES = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "organes")
if ORGANES not in sys.path:
    sys.path.insert(0, ORGANES)
import nexus_liens as nl  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixture — 6 fiches, struct_root/DOMAINE/categorie/fiche.md
# --------------------------------------------------------------------------- #
def _ecrire(chemin, texte):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(texte)


def _construire_fixture(tmp_path):
    root = str(tmp_path / "structure")

    _ecrire(os.path.join(root, "moteur", "persistance", "api.md"), """\
# API

L'API garantit que la persistance survit aux appels successifs du client,
même après un redémarrage complet du processus applicatif propre.
""")

    _ecrire(os.path.join(root, "moteur", "coeur", "moteur.md"), """\
# Moteur

Le moteur interne assure que la persistance survit aux appels internes,
indépendamment de la charge ou de la latence du réseau interne profond.
""")

    _ecrire(os.path.join(root, "ecriture", "chemin", "writepath.md"), """\
# Writepath

Le chemin d'écriture writepath certifie que la persistance survit aux appels
concurrents, en verrouillant chaque transaction avant toute validation finale.
""")

    _ecrire(os.path.join(root, "moteur", "persistance", "_index.md"), """\
# Index

Sommaire : la persistance survit aux appels dans l'API, le moteur et le
chemin d'écriture writepath, comme détaillé dans chacune de ces fiches
associées.
""")

    _ecrire(os.path.join(root, "general", "notes", "bruit_a.md"), """\
# Jardin

Ceci est un remplissage générique : azalee bougie casserole datte etoile
flanelle guitare hublot ivoire jonquille kermesse lilas myrtille nenuphar
oseille pruneau quetsche rutabaga.
""")

    _ecrire(os.path.join(root, "general", "notes", "bruit_b.md"), """\
# Cuisine

Ceci est un remplissage générique : kaolin lentille mimosa nectar orchidee
pagode quinoa ruban sequoia tulipe ambroisie basilic ciboulette estragon
fenouil girofle houblon iris.
""")

    return root


def _paire(e):
    return frozenset((e["a"], e["b"]))


def _edge(graphe, a, b):
    cible = frozenset((a, b))
    for e in graphe["aretes"]:
        if _paire(e) == cible:
            return e
    return None


# --------------------------------------------------------------------------- #
# CŒUR
# --------------------------------------------------------------------------- #
def test_determinisme_deux_builds_identiques(tmp_path):
    root = _construire_fixture(tmp_path)
    g1 = nl.construire_liens(root)
    g2 = nl.construire_liens(root)
    assert g1 == g2


def test_golden_trois_liens_de_sens_au_defaut(tmp_path):
    root = _construire_fixture(tmp_path)
    g = nl.construire_liens(root)

    assert g["noeuds"] == 5                       # _index exclu par défaut
    assert g["aretes_total"] == 3
    assert g["isoles"] == 2                        # bruit_a, bruit_b : sans lien

    attendues = {frozenset(("api", "moteur")),
                 frozenset(("api", "writepath")),
                 frozenset(("moteur", "writepath"))}
    obtenues = {_paire(e) for e in g["aretes"]}
    assert obtenues == attendues

    for e in g["aretes"]:
        assert e["poids"] >= g["min_poids"]


def test_porte_bloque_la_paire_de_bruit_au_defaut(tmp_path):
    root = _construire_fixture(tmp_path)
    g = nl.construire_liens(root)
    assert _edge(g, "bruit_a", "bruit_b") is None


def test_aucun_lien_index_par_defaut(tmp_path):
    root = _construire_fixture(tmp_path)
    g = nl.construire_liens(root)
    ids = {e["a"] for e in g["aretes"]} | {e["b"] for e in g["aretes"]}
    assert "_index" not in ids
    assert g["noeuds"] == 5


def test_chaque_lien_a_un_pourquoi(tmp_path):
    root = _construire_fixture(tmp_path)
    g = nl.construire_liens(root)
    assert g["aretes"]                              # au moins un lien à vérifier
    for e in g["aretes"]:
        assert e["pourquoi"]                        # non vide
        assert len(e["pourquoi"]) <= 5


def test_lien_inter_domaine_existe(tmp_path):
    root = _construire_fixture(tmp_path)
    g = nl.construire_liens(root)
    assert g["aretes_inter_domaine"] >= 1
    assert any(e["inter_domaine"] for e in g["aretes"])
    e = _edge(g, "api", "writepath")
    assert e is not None
    assert e["a_dom"] != e["b_dom"]
    assert e["inter_domaine"] is True


def test_voisins_lit_le_graphe_sans_le_recalculer(tmp_path):
    root = _construire_fixture(tmp_path)
    g = nl.construire_liens(root)
    v = nl.voisins(g, "api")
    assert {item["voisin"] for item in v} == {"moteur", "writepath"}
    assert v == sorted(v, key=lambda it: (-it["poids"], it["voisin"]))
    assert nl.voisins(g, "bruit_a") == []            # isolée


def test_persister_ecrit_et_relit_le_meme_graphe(tmp_path):
    root = _construire_fixture(tmp_path)
    g = nl.construire_liens(root)
    out = str(tmp_path / "sortie" / "liens.json")
    chemin = nl.persister(g, out)
    assert chemin == out
    assert os.path.exists(out)
    import json
    with open(out, encoding="utf-8") as f:
        relu = json.load(f)
    assert relu["aretes_total"] == g["aretes_total"]


# --------------------------------------------------------------------------- #
# MUTATIONS — chacune DOIT être détectée (assertion qui casse si le
# comportement de la porte régresse).
# --------------------------------------------------------------------------- #
def test_mutation_min_poids_zero_laisse_passer_le_bruit(tmp_path):
    root = _construire_fixture(tmp_path)
    g = nl.construire_liens(root, min_poids=0.0)
    assert _edge(g, "bruit_a", "bruit_b") is not None, (
        "MUTATION ROUGE : min_poids=0 doit laisser passer la paire de bruit")


def test_mutation_exclure_vide_fait_revenir_index(tmp_path):
    root = _construire_fixture(tmp_path)
    g = nl.construire_liens(root, exclure=())
    assert g["noeuds"] == 6, (
        "MUTATION ROUGE : exclure=() doit faire revenir _index comme nœud")
    ids = {e["a"] for e in g["aretes"]} | {e["b"] for e in g["aretes"]}
    assert "_index" in ids, (
        "MUTATION ROUGE : exclure=() doit faire revenir un lien _index")


def test_mutation_ponderation_brute_fait_remonter_le_bruit(tmp_path):
    root = _construire_fixture(tmp_path)
    g_idf = nl.construire_liens(root, ponderation="idf")
    g_brute = nl.construire_liens(root, ponderation="brute")
    assert _edge(g_idf, "bruit_a", "bruit_b") is None
    e = _edge(g_brute, "bruit_a", "bruit_b")
    assert e is not None, (
        'MUTATION ROUGE : ponderation="brute" doit faire remonter le bruit')
    assert e["poids"] >= g_brute["min_poids"]


def test_mutation_garder_pourquoi_false_lien_sans_pourquoi(tmp_path):
    root = _construire_fixture(tmp_path)
    g = nl.construire_liens(root, garder_pourquoi=False)
    assert g["aretes"]
    assert all("pourquoi" not in e for e in g["aretes"]), (
        'MUTATION ROUGE : garder_pourquoi=False doit produire des liens '
        'SANS "pourquoi"')


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
