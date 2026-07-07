"""SAS mémoire — format opt-in `format=sas` de recall() (mémoire-beta).

Le sas ÉTIQUETTE, il ne cache ni ne décote : le classement reste GLOBAL et
INCHANGÉ (un seul rank_candidates), puis REGROUPÉ à la présentation en trois
blocs étiquetés — structure / en_attente / brut. Le chemin par défaut (sans
`format=sas`) reste BYTE-IDENTIQUE : c'est la protection des consommateurs
transitifs.

Tests :
  T1    identité byte-pour-byte du défaut (golden pris sur main), corpus aux
        TROIS étages, avec un non-promu DANS le résultat par défaut (asserté).
  T2    séparation pure : une brute ultra-pertinente n'entre JAMAIS dans le bloc
        structure ; chaque bloc ne contient que son étage.
  T3    comparabilité : partition concaténée = ordre du défaut ; scores exposés
        = scores du classement global.
  T3bis invariant à la source : UN seul appel à rank_candidates par recall, quel
        que soit le format.
  T4    alerte, six cas.
  T4f   brut top + en_attente juste derrière + structure faible : l'alerte
        expose LES DEUX entrées (l'alerte n'oublie aucun étage).
  T5    chaque réponse sas validée contre le SCHÉMA du contrat.
  T6    énumération des appelants directs de recall (rougit si un nouvel
        appelant apparaît sans décision).
  T7    lecture seule (empreintes SHA-256).
  T8    miroir PR 57 : rank_candidates au comportement inchangé.
"""
import os
import json
import hashlib
import importlib.util

import pytest


ICI = os.path.dirname(os.path.abspath(__file__))            # backend/tests
RACINE = os.path.dirname(os.path.dirname(ICI))              # racine du dépôt


def _charger_memory_api():
    """Recharge un module memory_api frais (pas d'état partagé entre tests)."""
    chemin = os.path.join(RACINE, ".claude", "skills", "memoire-beta",
                          "scripts", "memory_api.py")
    spec = importlib.util.spec_from_file_location("memory_api_sas_test", chemin)
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
    for d in (m.STRUCT, m.EN_ATTENTE, m.BRUT, m.ARCHIVE):
        os.makedirs(d, exist_ok=True)
    return m


# --- Écriture de corpus (contenu figé -> recall déterministe) --------------- #
def _struct(m, dom, cat, nom, contenu):
    d = os.path.join(m.STRUCT, dom, cat)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, nom + ".md"), "w", encoding="utf-8") as f:
        f.write(contenu)


def _attente(m, nom, contenu):
    with open(os.path.join(m.EN_ATTENTE, nom + ".md"), "w", encoding="utf-8") as f:
        f.write(contenu)


def _brut(m, nom, contenu):
    with open(os.path.join(m.BRUT, nom + ".md"), "w", encoding="utf-8") as f:
        f.write(contenu)


def _forces(m, dico):
    with open(os.path.join(m.ROOT, "forces.json"), "w", encoding="utf-8") as f:
        json.dump(dico, f)


# =========================================================================== #
# Corpus « laboratoire » : un seul token « kily » présent dans CHAQUE fiche
# -> pertinence identique (= 1.0) partout, donc _score == force. Les forces.json
#    fixent alors des scores EXACTS et des ordres/égalités contrôlés.
# =========================================================================== #
def _labo_kily(m, avec=("structure", "en_attente", "brut")):
    if "structure" in avec:
        _struct(m, "dom", "cat", "valide", "critere kily validé")
    if "en_attente" in avec:
        _attente(m, "cand-attente", "analyse kily en attente")
    if "brut" in avec:
        _brut(m, "note-brute", "note kily capturée vite")


def _sas(m, query="kily", scope="all"):
    return m.recall({"query": [query], "scope": [scope], "format": ["sas"]})


# =========================================================================== #
# T1 — identité byte-pour-byte du défaut + corpus non trivial
# =========================================================================== #
def _corpus_golden(m):
    _struct(m, "travail", "methodes", "struct-forte",
            "# fiche forte\nprojet zorglubide budget equipe planning\n")
    _struct(m, "travail", "methodes", "struct-faible",
            "# fiche faible\nprojet budget divers rangement\n")
    _attente(m, "20260101-000000-candidat-non-promu",
             "# (en attente) candidat\nanalyse zorglubide en attente de validation\n")
    _brut(m, "2026-01-01",
          "# Notes brutes\nnote rapide budget zorglubide capturee vite\n")


def test_T1_defaut_byte_identique_au_golden(mem):
    _corpus_golden(mem)
    res = mem.recall({"query": ["zorglubide budget"], "scope": ["all"]})
    obtenu = json.dumps(res, ensure_ascii=False, indent=2)

    with open(os.path.join(ICI, "test_recall_sas_golden.json"), encoding="utf-8") as f:
        golden = f.read()
    assert obtenu == golden, "le chemin par défaut a divergé du golden pris sur main"

    # Le corpus n'est PAS trivial : un non-promu (en_attente ET brut) est bien
    # DANS le résultat par défaut, mêlé aux fiches structure. Si le corpus
    # devenait trivial (plus de mélange), cette assertion rougit.
    etages = [r["etage"] for r in res["results"]]
    assert "en_attente" in etages and "brut" in etages and "structure" in etages
    assert res["count"] >= 4


# =========================================================================== #
# T2 — séparation pure
# =========================================================================== #
def test_T2_separation_pure_brute_ultra_pertinente(mem):
    # La brute contient un token rare EN PLUS -> ultra-pertinente -> top global.
    _struct(mem, "dom", "cat", "valide", "sujet commun rangement")
    _attente(mem, "cand", "sujet commun analyse")
    _brut(mem, "note", "sujet commun zorglubide singulier distinctif")

    sas = _sas(mem, query="sujet zorglubide")
    blocs = sas["blocs"]

    # La brute ultra-pertinente est le top de SON bloc, et n'est nulle part ailleurs.
    brute_path = "brut/note.md"
    assert blocs["brut"][0]["path"] == brute_path
    assert brute_path not in [c["path"] for c in blocs["structure"]]
    assert brute_path not in [c["path"] for c in blocs["en_attente"]]

    # Chaque bloc ne contient QUE son étage.
    for etage, cands in blocs.items():
        assert all(c["etage"] == etage for c in cands), etage


# =========================================================================== #
# T3 — comparabilité : partition concaténée = ordre du défaut ; scores = global
# =========================================================================== #
def test_T3_comparabilite_ordre_et_scores(mem):
    _corpus_golden(mem)                          # corpus entrelacé (3 étages)
    query = "zorglubide budget"

    defaut = mem.recall({"query": [query], "scope": ["all"]})
    D = defaut["results"]

    sas = _sas(mem, query=query)
    blocs = sas["blocs"]

    # Partition stable du défaut par étage == concaténation des trois blocs.
    partition = ([d["path"] for d in D if d["etage"] == "structure"]
                 + [d["path"] for d in D if d["etage"] == "en_attente"]
                 + [d["path"] for d in D if d["etage"] == "brut"])
    concat = ([c["path"] for c in blocs["structure"]]
              + [c["path"] for c in blocs["en_attente"]]
              + [c["path"] for c in blocs["brut"]])
    assert concat == partition

    # Scores exposés == scores du classement GLOBAL (recalculés indépendamment).
    cands = (mem._scan(mem.STRUCT, query, "structure")
             + mem._scan(mem.EN_ATTENTE, query, "en_attente")
             + mem._scan(mem.BRUT, query, "brut"))
    ranked = mem.rank_candidates(query, cands)
    global_par_path = {r["path"]: r for r in ranked}
    for etage in ("structure", "en_attente", "brut"):
        for c in blocs[etage]:
            g = global_par_path[c["path"]]
            assert c["_score"] == g["_score"]
            assert c["_relevance"] == g["_relevance"]
            assert c["_force"] == g["_force"]


# =========================================================================== #
# T3bis — invariant à la source : UN seul rank_candidates par recall
# =========================================================================== #
def test_T3bis_un_seul_appel_rank_candidates(mem):
    _corpus_golden(mem)
    orig = mem.rank_candidates
    compteur = {"n": 0}

    def espion(*a, **k):
        compteur["n"] += 1
        return orig(*a, **k)

    mem.rank_candidates = espion
    try:
        mem.recall({"query": ["zorglubide budget"], "scope": ["all"]})
        assert compteur["n"] == 1, "défaut : exactement un rank_candidates attendu"

        compteur["n"] = 0
        _sas(mem, query="zorglubide budget")
        assert compteur["n"] == 1, "sas : exactement un rank_candidates attendu"
    finally:
        mem.rank_candidates = orig


# =========================================================================== #
# T4 — alerte, six cas
# =========================================================================== #
def test_T4_top_structure_donne_null(mem):
    _labo_kily(mem)
    _forces(mem, {"valide": 5.0, "cand-attente": 2.0, "note-brute": 1.0})
    assert _sas(mem)["alerte"] is None


def test_T4_top_en_attente_avec_structure_ecart_correct(mem):
    _labo_kily(mem)
    _forces(mem, {"valide": 2.0, "cand-attente": 5.0, "note-brute": 1.0})
    alerte = _sas(mem)["alerte"]
    assert alerte == [{"etage": "en_attente",
                       "path": "en_attente/cand-attente.md",
                       "ecart": 3.0}]  # 5.0 - 2.0


def test_T4_aucun_structure_ne_matche_ecart_null(mem):
    # Une structure EXISTE mais ne matche pas la requête (aucun token « kily »).
    _struct(mem, "dom", "cat", "hors-sujet", "rien a voir ici du tout")
    _attente(mem, "cand-attente", "analyse kily en attente")
    _brut(mem, "note-brute", "note kily capturée vite")
    _forces(mem, {"cand-attente": 5.0, "note-brute": 1.0})

    sas = _sas(mem)
    assert sas["blocs"]["structure"] == []       # aucun structure ne matche
    # top = en_attente ; ecart null car aucun structure de référence.
    assert {"etage": "en_attente", "path": "en_attente/cand-attente.md",
            "ecart": None} in sas["alerte"]


def test_T4_egalite_inter_etages_le_valide_gagne(mem):
    # structure et en_attente au MÊME score (force 3.0 chacun) -> valide gagne.
    _labo_kily(mem, avec=("structure", "en_attente"))
    _forces(mem, {"valide": 3.0, "cand-attente": 3.0})
    sas = _sas(mem)
    # Les deux sont bien présents à égalité de score...
    assert sas["blocs"]["structure"][0]["_score"] == sas["blocs"]["en_attente"][0]["_score"]
    # ...et pourtant AUCUNE alerte : à égalité, le validé tient la tête.
    assert sas["alerte"] is None


def test_T4_top_brut_donne_etage_brut(mem):
    _labo_kily(mem)
    _forces(mem, {"valide": 2.0, "cand-attente": 1.0, "note-brute": 5.0})
    alerte = _sas(mem)["alerte"]
    etages = {e["etage"] for e in alerte}
    assert "brut" in etages
    entree_brut = next(e for e in alerte if e["etage"] == "brut")
    assert entree_brut["path"] == "brut/note-brute.md"
    assert entree_brut["ecart"] == 3.0           # 5.0 - 2.0


def test_T4f_brut_top_en_attente_derriere_structure_faible_DEUX_entrees(mem):
    # brut (5) > en_attente (4) > structure (1) : les DEUX hors-structure battent
    # le validé -> l'alerte doit exposer LES DEUX étages (elle n'oublie personne).
    _labo_kily(mem)
    _forces(mem, {"valide": 1.0, "cand-attente": 4.0, "note-brute": 5.0})
    alerte = _sas(mem)["alerte"]

    par_etage = {e["etage"]: e for e in alerte}
    assert set(par_etage) == {"en_attente", "brut"}, "l'alerte oublie un étage"
    assert par_etage["en_attente"]["ecart"] == 3.0     # 4.0 - 1.0
    assert par_etage["brut"]["ecart"] == 4.0           # 5.0 - 1.0
    assert par_etage["en_attente"]["path"] == "en_attente/cand-attente.md"
    assert par_etage["brut"]["path"] == "brut/note-brute.md"


# =========================================================================== #
# T5 — chaque réponse sas validée contre le SCHÉMA du contrat
# =========================================================================== #
def _valider_schema(resp):
    """Encode la partie machine-vérifiable du contrat CONTRAT_recall_sas.md.
    Lève AssertionError à la moindre divergence code/contrat."""
    assert resp["ok"] is True
    assert isinstance(resp["scope"], str)
    assert resp["format"] == "sas"
    assert isinstance(resp["count"], int) and resp["count"] >= 0

    blocs = resp["blocs"]
    assert set(blocs.keys()) == {"structure", "en_attente", "brut"}
    total = 0
    for etage, cands in blocs.items():
        assert isinstance(cands, list)
        total += len(cands)
        for c in cands:
            # INVARIANT DE SÉPARATION : l'étage du candidat == la clé du bloc.
            assert c["etage"] == etage
            assert isinstance(c["file"], str) and isinstance(c["path"], str)
            assert isinstance(c["excerpt"], str)
            assert c["domain"] is None or isinstance(c["domain"], str)
            assert c["category"] is None or isinstance(c["category"], str)
            for k in ("_relevance", "_force", "_score"):
                assert isinstance(c[k], (int, float)) and not isinstance(c[k], bool)
    assert resp["count"] == total

    alerte = resp["alerte"]
    if alerte is not None:
        assert isinstance(alerte, list) and len(alerte) >= 1
        assert len(alerte) <= 2                       # au plus une par étage hors-structure
        vus = set()
        for e in alerte:
            assert set(e.keys()) == {"etage", "path", "ecart"}
            assert e["etage"] in ("en_attente", "brut")   # JAMAIS structure
            assert e["etage"] not in vus                   # au plus une par étage
            vus.add(e["etage"])
            assert isinstance(e["path"], str)
            assert e["ecart"] is None or isinstance(e["ecart"], (int, float))
    return True


def test_T5_reponses_sas_conformes_au_schema(mem):
    # Plusieurs corpus -> plusieurs formes d'alerte, toutes validées.
    _labo_kily(mem)
    _forces(mem, {"valide": 5.0, "cand-attente": 2.0, "note-brute": 1.0})
    assert _valider_schema(_sas(mem))

    _forces(mem, {"valide": 1.0, "cand-attente": 4.0, "note-brute": 5.0})
    assert _valider_schema(_sas(mem))

    # corpus entrelacé « réel »
    m2 = _remonter_corpus_golden(mem)
    assert _valider_schema(_sas(m2, query="zorglubide budget"))


def _remonter_corpus_golden(m):
    # nettoie et repeuple avec le corpus golden (entrelacé)
    import shutil
    for d in (m.STRUCT, m.EN_ATTENTE, m.BRUT):
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d, exist_ok=True)
    if os.path.exists(os.path.join(m.ROOT, "forces.json")):
        os.remove(os.path.join(m.ROOT, "forces.json"))
    _corpus_golden(m)
    return m


# =========================================================================== #
# T6 — énumération des appelants directs de recall
# =========================================================================== #
def test_T6_enumeration_des_appelants_de_recall():
    """Rougit si un NOUVEL appelant de rec()/`/recall` apparaît sans décision.
    Chaque appelant connu est protégé par le DÉFAUT byte-identique (aucun ne
    passe format=sas). nexus_capital.consulter est ABSENT à dessein : il scanne
    STRUCT directement (fiches nées structurelles), il ne passe pas par recall."""
    import re
    pat = re.compile(r"\.recall\(|/recall")
    trouves = set()
    for sous in ("organes", "backend", ".claude/skills"):
        base = os.path.join(RACINE, sous)
        for dp, _d, files in os.walk(base):
            if os.sep + "tests" in dp + os.sep:
                continue
            for fl in files:
                if not fl.endswith(".py"):
                    continue
                p = os.path.join(dp, fl)
                if p.endswith(os.path.join("memoire-beta", "scripts", "memory_api.py")):
                    continue  # la définition + le serveur, pas un appelant
                with open(p, encoding="utf-8") as f:
                    if pat.search(f.read()):
                        trouves.add(os.path.relpath(p, RACINE))

    connus = {
        # --- appels réels (tous en scope par défaut, protégés byte-identique) ---
        "backend/orchestrateur.py",                      # recall scope=all (top-1)
        "organes/agentos_adaptateurs.py",                # recall scope injecté
        "organes/nexus_98.py",                           # /recall?domain=&category= (structure)
        ".claude/skills/expert-98/scripts/nexus_98.py",  # idem (miroir skill)
        "organes/nexus_consolidate.py",                  # /recall?domain=&category= (structure)
        "organes/nexus_organize.py",                     # /recall?scope=brut
        # --- mentions en docstring seulement (pas des appels) ---
        "organes/friday_ecrivain.py",                    # docstring : décrit recall
        "organes/nexus_force.py",                        # docstring : décrit recall
    }
    nouveaux = trouves - connus
    disparus = connus - trouves
    assert not nouveaux, "NOUVEL appelant de recall sans décision : %s" % sorted(nouveaux)
    assert not disparus, "appelant connu disparu (mettre à jour la liste) : %s" % sorted(disparus)


# =========================================================================== #
# T7 — lecture seule (empreintes SHA-256)
# =========================================================================== #
def _empreintes(base):
    emp = {}
    for dp, _d, files in os.walk(base):
        for fl in sorted(files):
            p = os.path.join(dp, fl)
            with open(p, "rb") as f:
                emp[os.path.relpath(p, base)] = hashlib.sha256(f.read()).hexdigest()
    return emp


def test_T7_recall_ne_modifie_rien(mem):
    _corpus_golden(mem)
    avant = _empreintes(mem.ROOT)
    mem.recall({"query": ["zorglubide budget"], "scope": ["all"]})
    _sas(mem, query="zorglubide budget")
    apres = _empreintes(mem.ROOT)
    assert avant == apres


# =========================================================================== #
# T8 — miroir PR 57 : rank_candidates au comportement inchangé
# =========================================================================== #
def test_T8_rank_candidates_comportement_inchange(mem):
    """Le sas ne touche pas au classement : rank_candidates rend exactement le
    même ordre et les mêmes scores qu'avant (golden de comportement). Le test
    de rétrocompat exacte de PR 57 (test_recall_multisignaux) reste par ailleurs
    vert : rank_candidates est absent du diff."""
    _struct(mem, "dom", "cat", "commun_a", "projet equipe reunion budget")
    _struct(mem, "dom", "cat", "commun_b", "projet planning budget client")
    _struct(mem, "dom", "cat", "rare", "projet zorglubide singulier")
    _struct(mem, "dom", "cat", "boostee", "projet budget zorglubide")

    forces = {"boostee": 5.0, "rare": 0.2}
    query = "zorglubide budget"
    cands = mem._scan(mem.STRUCT, query, "structure")
    ranked = mem.rank_candidates(query, cands, forces=forces)

    # Ordre et relation _score == _relevance × _force (× et pas +) : pinés.
    assert [r["file"] for r in ranked] == ["boostee.md", "commun_a.md",
                                           "commun_b.md", "rare.md"]
    for r in ranked:
        assert r["_score"] == r["_relevance"] * r["_force"]
