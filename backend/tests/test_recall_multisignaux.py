"""Recall MULTI-SIGNAUX (lexical + sémantique + force vivante) — nexus_force.rank().

Couvre le mandat de la brique, point par point :

  1. RÉTROCOMPAT EXACTE : rank() sans embedder == comportement historique
     (memory_api.rank_candidates : score = pertinence(IDF) × force), à la
     virgule et à l'ordre près.
  2. GAIN sémantique : sur une requête reformulée à ZÉRO token commun mais
     proche par n-grammes, EmbedderFake + semantique_ouvre_candidats=True
     récupère la fiche (élargissement, pas seulement reclassement).
  3. NON-DOMINATION : la force départage à pertinence égale, mais une fiche peu
     pertinente à force plafond 5.0 ne bat PAS une fiche très pertinente à force
     plancher 0.2 — testé au pire cas du ratio 25×.
  4. LIMITE d'EmbedderFake (xfail strict) : une vraie synonymie sans proximité
     de n-grammes (voiture/automobile) échoue par construction ; passera au vert
     le jour d'un vrai embedder.
  5. BORNES : rel_n, sem, pert et f(force) tous dans [0,1], même forces hors plage.
  6. ROBUSTESSE : embedder qui lève / renvoie une mauvaise dimension → dégradation
     propre vers le lexical seul, jamais de crash.
  7. LECTURE SEULE : empreintes binaires des fichiers mémoire inchangées après rank().
  8. INSTRUMENTATION : les trois paramètres provisoires (alpha, distribution des
     forces, seuil d'élargissement) sont épinglés — un changement silencieux
     casse un test (le provisoire ne devient pas permanent par défaut).
"""
import os
import sys
import json
import hashlib
import importlib
import importlib.util

import pytest


# --------------------------------------------------------------------------- #
# Chargement des modules (organes/ pour nexus_force, skill pour memory_api)
# --------------------------------------------------------------------------- #
def _racine():
    ici = os.path.dirname(os.path.abspath(__file__))          # backend/tests
    return os.path.dirname(os.path.dirname(ici))              # racine du dépôt


def _charger_nexus_force():
    org = os.path.join(_racine(), "organes")
    if org not in sys.path:
        sys.path.insert(0, org)
    import nexus_force
    return importlib.reload(nexus_force)


def _charger_memory_api():
    chemin = os.path.join(_racine(), ".claude", "skills", "memoire-beta",
                          "scripts", "memory_api.py")
    spec = importlib.util.spec_from_file_location("memory_api_multisig_test", chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def nf():
    return _charger_nexus_force()


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


def _cands(m, query):
    """Candidats lexicaux tels que recall() les fabrique (via _scan)."""
    return m._scan(m.STRUCT, query.lower(), "structure")


# Embedders de test contrôlés ------------------------------------------------ #
class _EmbedderConstant:
    """Renvoie le MÊME vecteur pour tout : sem constant → s'annule dans le
    classement, ce qui ISOLE l'effet force vs pertinence (test 3)."""
    def embed(self, text):
        return [1.0, 0.0, 0.0]


class _EmbedderZero:
    """Vecteur nul → cosinus 0 partout : la cible de dégradation « lexical seul »."""
    def embed(self, text):
        return [0.0, 0.0, 0.0]


class _EmbedderExplose:
    def embed(self, text):
        raise RuntimeError("embedder en panne")


class _EmbedderMauvaiseDim:
    """Dimension variable selon le texte → cosinus incalculable (mismatch)."""
    def embed(self, text):
        return [1.0] * (1 + (len(text) % 4))


# --------------------------------------------------------------------------- #
# 1. RÉTROCOMPAT EXACTE de rank() sans embedder
# --------------------------------------------------------------------------- #
def test_retrocompat_exacte_sans_embedder(nf, mem):
    _fiche(mem, "dom", "cat", "commun_a", "projet equipe reunion budget")
    _fiche(mem, "dom", "cat", "commun_b", "projet planning budget client")
    _fiche(mem, "dom", "cat", "rare", "projet zorglubide singulier")
    _fiche(mem, "dom", "cat", "boostee", "projet budget zorglubide")

    forces = {"boostee": 5.0, "rare": 0.2}
    query = "zorglubide budget"
    cands = _cands(mem, query)

    attendu = mem.rank_candidates(query, cands, forces=forces)
    obtenu = nf.rank(query, cands, forces=forces)                 # embedder=None

    # ordre STRICTEMENT identique
    assert [r["file"] for r in obtenu] == [r["file"] for r in attendu]
    # scores STRICTEMENT identiques (score = pertinence × force)
    for a, b in zip(attendu, obtenu):
        assert b["_score"] == a["_score"]
        assert b["_relevance"] == a["_relevance"]
        assert b["_force"] == a["_force"]
        assert b["_score"] == a["_relevance"] * a["_force"]       # bien × et pas +
    # aucune clé de fusion multi-signaux ne fuit dans le chemin rétrocompat
    assert "_sem" not in obtenu[0] and "_pert" not in obtenu[0]


def test_retrocompat_defaut_embedder_none(nf, mem):
    _fiche(mem, "dom", "cat", "a", "alpha beta gamma")
    _fiche(mem, "dom", "cat", "b", "beta gamma delta")
    cands = _cands(mem, "alpha")
    # appel sans préciser embedder → chemin historique
    r = nf.rank("alpha", cands)
    assert r[0]["file"] == "a.md"
    assert r[0]["_score"] == r[0]["_relevance"] * r[0]["_force"]


# --------------------------------------------------------------------------- #
# 2. GAIN sémantique : requête reformulée, zéro token commun, proche par n-grammes
# --------------------------------------------------------------------------- #
def test_gain_semantique_elargit_les_candidats(nf, mem):
    # fiche cible : AUCUN token entier partagé avec la requête, mais très proche
    # par n-grammes de caractères (reformulation/reformuler, interrogations/-tion).
    # Recall v0.1 embarque le TITRE : le signal sémantique vit dans la ligne '#'.
    _fiche(mem, "dom", "cat", "cible",
           "# Guide de reformulation des interrogations complexes — "
           "domaine: dom / catégorie: cat\n> Créé le 21/06/2026\n\ncorps\n")
    # bruit : ni lexical ni proche par n-grammes
    _fiche(mem, "dom", "cat", "bruit",
           "# recette de cuisine tarte aux pommes sucre — "
           "domaine: dom / catégorie: cat\n> Créé le 21/06/2026\n\ncorps\n")

    query = "reformuler une interrogation"
    corpus = _cands(mem, query)

    # zéro recouvrement lexical → la cible n'est PAS un candidat lexical
    lexicaux = nf.rank(query, corpus)          # embedder=None
    assert all(r["_relevance"] == 0.0 for r in lexicaux)   # rien de pertinent lex.

    emb = nf.EmbedderFake()

    # sans élargissement : le sémantique reclasse mais n'AJOUTE rien de nouveau
    sans = nf.rank(query, [], embedder=emb,
                   semantique_ouvre_candidats=True, corpus=None)
    assert sans == []

    # avec élargissement : la cible est RÉCUPÉRÉE (ajoutée, pas juste reclassée)
    avec = nf.rank(query, [], embedder=emb,
                   semantique_ouvre_candidats=True, corpus=corpus)
    fichiers = [r["file"] for r in avec]
    assert "cible.md" in fichiers
    assert "bruit.md" not in fichiers          # sous le seuil → pas de flood
    cible = next(r for r in avec if r["file"] == "cible.md")
    assert cible["_relevance"] == 0.0          # aucun lexical…
    assert cible["_sem"] >= nf.SEUIL_ELARGISSEMENT_DEFAUT   # …récupérée par le sem
    assert cible["_score"] > 0.0


# --------------------------------------------------------------------------- #
# 3. NON-DOMINATION de la force (pire cas ratio 25×)
# --------------------------------------------------------------------------- #
def test_force_departage_a_pertinence_egale(nf, mem):
    # pertinence STRICTEMENT égale (même contenu) ; sem constant (annulé).
    _fiche(mem, "dom", "cat", "faible", "projet distinctifxyz contenu")
    _fiche(mem, "dom", "cat", "forte", "projet distinctifxyz contenu")
    forces = {"forte": 5.0, "faible": 0.2}
    cands = _cands(mem, "distinctifxyz")

    r = nf.rank("distinctifxyz", cands, forces=forces, embedder=_EmbedderConstant())
    # à pertinence égale, la force plus haute remonte : la force est INFLUENTE.
    assert r[0]["file"] == "forte.md"
    assert r[0]["_rel_n"] == r[1]["_rel_n"]    # bien la même pertinence


def test_force_ne_domine_pas_la_pertinence_pire_cas_25x(nf, mem):
    # très pertinente (token rare distinctif) MAIS force plancher 0.2 (f=0).
    _fiche(mem, "dom", "cat", "tres_pertinente", "zorglubide singulier distinctif")
    # peu pertinente (SEULEMENT un token commun) MAIS force plafond 5.0 (f=1).
    _fiche(mem, "dom", "cat", "peu_pertinente", "commun commun commun commun")
    # corpus RÉALISTE : le token commun est vraiment commun (idf bas), comme sur
    # le corpus réel (~100 fiches). Un petit corpus gonflerait artificiellement
    # l'idf du token « commun » et rendrait le test plus doux que la réalité.
    for i in range(12):
        _fiche(mem, "dom", "cat", "decoy%02d" % i, "commun contexte mot%d" % i)

    forces = {"peu_pertinente": 5.0, "tres_pertinente": 0.2}   # ratio 25×
    query = "zorglubide commun"
    cands = _cands(mem, query)

    r = nf.rank(query, cands, forces=forces, embedder=_EmbedderConstant())
    gagnant = r[0]
    tp = next(x for x in r if x["file"] == "tres_pertinente.md")
    pp = next(x for x in r if x["file"] == "peu_pertinente.md")

    # domaine de la garantie : écart de pertinence normalisée franc (> 0.5),
    # c.-à-d. un VRAI écart, pas un écart doux.
    assert pp["_rel_n"] < 0.5 < tp["_rel_n"]
    # la force MAXIMALE (f=1, ratio 25×) ne renverse PAS ce vrai écart.
    assert gagnant["file"] == "tres_pertinente.md"
    assert tp["_score"] > pp["_score"]
    # l'écart de pertinence dépasse bien ce que la force peut ajouter au plus (beta).
    assert (tp["_pert"] - pp["_pert"]) > 0.5 * (1.0 - nf.POIDS_SEMANTIQUE_DEFAUT)


# --------------------------------------------------------------------------- #
# 4. LIMITE d'EmbedderFake — xfail STRICT (vert le jour d'un vrai embedder)
# --------------------------------------------------------------------------- #
@pytest.mark.xfail(
    strict=True,
    reason="EmbedderFake ne capte que la proximité de SURFACE (n-grammes de "
           "caractères). 'voiture' et 'automobile' ne partagent aucun n-gramme "
           "→ sem ≈ 0 : la vraie synonymie est INVISIBLE par construction. Ce "
           "test passera au vert quand un vrai embedder sémantique remplacera "
           "EmbedderFake (xpass strict → il faudra alors retirer ce xfail).",
)
def test_synonymie_vraie_invisible_pour_embedderfake(nf):
    emb = nf.EmbedderFake()
    sim = nf._cosine(emb.embed("voiture"), emb.embed("automobile"))
    # ce qu'on ATTENDRAIT d'un vrai embedder ; échoue avec EmbedderFake (sim≈0).
    assert sim > 0.5


# --------------------------------------------------------------------------- #
# 5. BORNES : rel_n, sem, pert, f(force) tous dans [0,1]
# --------------------------------------------------------------------------- #
def test_bornes_tous_signaux_dans_0_1(nf, mem):
    _fiche(mem, "dom", "cat", "a", "reformulation interrogation budget projet")
    _fiche(mem, "dom", "cat", "b", "projet budget equipe")
    _fiche(mem, "dom", "cat", "c", "sujet totalement different xyz")
    # forces VOLONTAIREMENT hors plage [0.2, 5.0] pour éprouver le bornage.
    forces = {"a": 99.0, "b": -3.0, "c": 0.001}
    query = "reformuler le projet"
    cands = _cands(mem, query)

    r = nf.rank(query, cands, forces=forces, embedder=nf.EmbedderFake())
    for it in r:
        assert 0.0 <= it["_rel_n"] <= 1.0
        assert 0.0 <= it["_sem"] <= 1.0
        assert 0.0 <= it["_pert"] <= 1.0
        assert 0.0 <= it["_f_force"] <= 1.0

    # f(force) bornée aux extrêmes réels du module.
    assert nf.f_force(nf.FORCE_MIN) == 0.0
    assert nf.f_force(nf.FORCE_MAX) == 1.0
    assert nf.f_force(1000.0) == 1.0 and nf.f_force(-5.0) == 0.0


# --------------------------------------------------------------------------- #
# 6. ROBUSTESSE : embedder cassé → dégradation propre vers le lexical seul
# --------------------------------------------------------------------------- #
def test_robustesse_embedder_defaillant_degrade_sans_crash(nf, mem):
    # Recall v0.1 embarque le TITRE : chaque fiche porte sa ligne '#' réelle.
    _fiche(mem, "dom", "cat", "a",
           "# alpha beta gamma projet — domaine: dom / catégorie: cat\ncorps\n")
    _fiche(mem, "dom", "cat", "b",
           "# beta gamma delta budget — domaine: dom / catégorie: cat\ncorps\n")
    _fiche(mem, "dom", "cat", "c",
           "# projet budget final — domaine: dom / catégorie: cat\ncorps\n")
    query = "projet budget"
    cands = _cands(mem, query)

    # cible de dégradation : sem = 0 partout (embedder nul).
    ref = nf.rank(query, cands, embedder=_EmbedderZero())

    for casse in (_EmbedderExplose(), _EmbedderMauvaiseDim()):
        r = nf.rank(query, cands, embedder=casse)               # ne doit PAS lever
        assert len(r) == len(cands)
        assert all(it["_sem"] == 0.0 for it in r)               # dégradé vers lexical
        assert [x["file"] for x in r] == [x["file"] for x in ref]
        assert [x["_score"] for x in r] == [x["_score"] for x in ref]

    # même un élargissement demandé avec un embedder cassé ne crashe pas.
    r2 = nf.rank(query, cands, embedder=_EmbedderExplose(),
                 semantique_ouvre_candidats=True, corpus=cands)
    assert len(r2) == len(cands)                                # rien d'ajouté, pas de crash


# --------------------------------------------------------------------------- #
# 6bis. TRANSITION du garde-fou « force plate == force inerte ».
#   L'ancien test test_force_plate_est_inerte_tant_quaucun_capteur_nalimente
#   GARDAIT la limite honnête « tant qu'AUCUN capteur n'alimente de fiche,
#   calculer_forces()=={} et la force ne départage rien ». La brique HITL
#   capitalisante (organes/nexus_capital.py) rend ce postulat FAUX par
#   conception : appliquer() émet enfin des capteurs statut=succes|echec avec
#   fiche=<slug> → de vraies forces distinctes existent.
#
#   Le garde-fou a donc été RETIRÉ ici et REMPLACÉ par ses DEUX successeurs, dans
#   backend/tests/test_capital.py (mêmes contraintes que le mandat) :
#     (a) test_successeur_a_forces_distinctes_discriminent_le_classement
#         — de vraies forces (montées par la chaîne réelle) départagent enfin ;
#     (b) test_successeur_b_force_bornee_non_dominante_au_vrai_plafond
#         — poussée jusqu'à saturation (FORCE_MAX vs FORCE_MIN, ratio 25×), la
#         pertinence gagne quand même : force vivante MAIS non dominante.
#   La non-domination testée ici (tests 3) reste vraie : la force DÉPARTAGE sans
#   ÉCRASER. C'est ce que (b) prouve désormais au vrai plafond, via la chaîne.
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# 7. LECTURE SEULE prouvée par empreintes binaires
# --------------------------------------------------------------------------- #
def _empreintes(racine):
    emp = {}
    for dp, _dirs, files in os.walk(racine):
        for fl in files:
            p = os.path.join(dp, fl)
            with open(p, "rb") as f:
                emp[p] = hashlib.sha256(f.read()).hexdigest()
    return emp


def test_lecture_seule_empreintes_inchangees(nf, mem):
    _fiche(mem, "dom", "cat", "a", "reformulation projet budget zorglubide")
    _fiche(mem, "dom", "cat", "b", "projet budget equipe planning")
    _fiche(mem, "dom", "cat", "c", "sujet different interrogation")
    query = "reformuler le projet zorglubide"
    cands = _cands(mem, query)

    avant = _empreintes(mem.ROOT)
    # les deux chemins : rétrocompat ET fusion multi-signaux avec élargissement.
    nf.rank(query, cands)
    nf.rank(query, cands, forces={"a": 5.0}, embedder=nf.EmbedderFake(),
            semantique_ouvre_candidats=True, corpus=cands)
    apres = _empreintes(mem.ROOT)

    assert avant == apres                                       # aucun octet modifié
    # rank() n'a créé aucun forces.json (contrairement au pont appliquer()).
    assert not os.path.exists(os.path.join(mem.ROOT, "forces.json"))


# --------------------------------------------------------------------------- #
# 8. INSTRUMENTATION — épingle les trois paramètres provisoires
# --------------------------------------------------------------------------- #
def test_instrumentation_parametres_provisoires_epingles(nf):
    # alpha : valeur provisoire testée, dans un intervalle défendable.
    assert nf.POIDS_SEMANTIQUE_DEFAUT == 0.5
    assert 0.0 <= nf.POIDS_SEMANTIQUE_DEFAUT <= 1.0

    # beta (force) : plafonné pour ne jamais dominer la pertinence.
    assert nf.POIDS_FORCE_DEFAUT == 0.25
    assert nf.POIDS_FORCE_DEFAUT <= 0.5 * (1.0 - nf.POIDS_SEMANTIQUE_DEFAUT)

    # seuil d'élargissement : sépare un vrai rapprochement (~0.6) du bruit (~0.1).
    assert nf.SEUIL_ELARGISSEMENT_DEFAUT == 0.35

    # constantes réelles de la force (celles du module, pas inventées).
    assert (nf.FORCE_MIN, nf.FORCE_MAX) == (0.2, 5.0)


def test_instrumentation_histogramme_forces(nf):
    # distribution réelle des forces via calculer_forces() (histogramme simple).
    h = nf.histogramme_forces()
    assert "n_fiches" in h and "tranches" in h
    assert h["n_fiches"] == sum(h["tranches"].values())

    # histogramme sur une distribution connue → comptage correct.
    faux = {"a": 0.2, "b": 1.0, "c": 1.0, "d": 5.0}
    hh = nf.histogramme_forces(forces=faux)
    assert hh["n_fiches"] == 4
