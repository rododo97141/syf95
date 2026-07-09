"""Organe d'OUBLI v1 — supersession TOTALE (mémoire-beta).

BUT : une fiche jugée fausse par l'humain CESSE de remonter en tête du recall
SANS être détruite. Elle est ROUTÉE dans un 4e bloc `superseded` du format sas
(hors des blocs structure/en_attente/brut) et reste sur disque, réversible.

Trois champs de provenance VOYAGENT brut -> en_attente -> structure comme
source/verifie (PR#70) : superseded (défaut 'non'), superseded_par, date_validite.
Marqueurs HTML en fin de fiche, écrits UNIQUEMENT hors défaut (byte-identique si
superseded='non'). Posés uniquement par GESTE HUMAIN (superseder()), jamais auto.

Chaque test NOMME la mutation qu'il fait rougir (défense adversariale) :

  T1  superseded='non' (défaut) => AUCUN marqueur, byte-identique + le défaut de
      recall ne fuit AUCUN champ de supersession (protection transitive).
  T2  les 3 champs VOYAGENT brut->en_attente->structure ; superseded_par ET
      date_validite SURVIVENT à la promotion (mut. perdre-superseded_par/date).
  T3  superseded posé UNIQUEMENT par geste humain : les écritures automatiques
      (memorize/promote/note) laissent superseded='non' (mut. posé-sans-geste).
  T4  BINAIRE 3 CLAUSES : une supersédée (a) n'est plus dans le bloc principal,
      (b) est dans le bloc superseded, (c) EXISTE toujours (mut. supprimer-routage,
      mut. détruire-au-lieu-de-séparer) + réversibilité byte-identique.
  T5  GOLDEN COMPORTEMENT type ForgetEval : jeu de cas (fait + requête qui le
      faisait remonter) — avant/après, la requête ne le ramène plus en tête du
      bloc principal mais le trouve dans le bloc superseded.
  T6  une supersédée n'est JAMAIS struct_top ni dans l'alerte (mut. supprimer-
      routage : la fausse-forte reprend la tête).
  T7  ordre des blocs + des champs du format sas FIGÉ : le 4e bloc s'ajoute en
      DERNIER sans réordonner aucun champ (mut. ajout-4e-bloc-réordonne-un-champ).
  T8  lecture seule (SHA-256) : recall/sas ne modifient rien ; superseder ne
      touche QUE la fiche visée.
"""
import os
import json
import hashlib
import shutil
import importlib.util

import pytest


ICI = os.path.dirname(os.path.abspath(__file__))            # backend/tests
RACINE = os.path.dirname(os.path.dirname(ICI))              # racine du dépôt


def _charger_memory_api():
    chemin = os.path.join(RACINE, ".claude", "skills", "memoire-beta",
                          "scripts", "memory_api.py")
    spec = importlib.util.spec_from_file_location("memory_api_supersession_test", chemin)
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


# --- helpers d'écriture directe (contenu figé -> recall déterministe) ------- #
def _struct(m, dom, cat, nom, contenu):
    d = os.path.join(m.STRUCT, dom, cat)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, nom + ".md"), "w", encoding="utf-8") as f:
        f.write(contenu)


def _forces(m, dico):
    with open(os.path.join(m.ROOT, "forces.json"), "w", encoding="utf-8") as f:
        json.dump(dico, f)


def _sas(m, query="kily", scope="all"):
    return m.recall({"query": [query], "scope": [scope], "format": ["sas"]})


def _corpus_golden(m):
    """Miroir du corpus golden par défaut (aucune fiche supersédée)."""
    _struct(m, "travail", "methodes", "struct-forte",
            "# fiche forte\nprojet zorglubide budget equipe planning\n")
    _struct(m, "travail", "methodes", "struct-faible",
            "# fiche faible\nprojet budget divers rangement\n")
    with open(os.path.join(m.EN_ATTENTE, "20260101-000000-candidat-non-promu.md"),
              "w", encoding="utf-8") as f:
        f.write("# (en attente) candidat\nanalyse zorglubide en attente de validation\n")
    with open(os.path.join(m.BRUT, "2026-01-01.md"), "w", encoding="utf-8") as f:
        f.write("# Notes brutes\nnote rapide budget zorglubide capturee vite\n")


# =========================================================================== #
# T1 — défaut : superseded='non' byte-identique + aucune fuite dans le défaut
# =========================================================================== #
def test_T1_defaut_byte_identique_et_pas_de_fuite(mem):
    # (a) memorize SANS supersession : AUCUN marqueur superseded écrit.
    res = mem.memorize({"content": "contenu neutre specifique", "domain": "d",
                        "category": "c", "title": "neutre"})
    text = open(os.path.join(mem.ROOT, res["path"]), encoding="utf-8").read()
    assert "superseded" not in text, "marqueur écrit au défaut : byte-identité rompue"

    # (b) le DÉFAUT de recall (sans format=sas) ne fuit AUCUN champ de supersession
    #     (protection des consommateurs transitifs, comme source/verifie).
    _corpus_golden(mem)
    d = mem.recall({"query": ["zorglubide budget"], "scope": ["all"]})
    for r in d["results"]:
        assert "superseded" not in r
        assert "superseded_par" not in r
        assert "date_validite" not in r

    # (c) le golden par défaut reste byte-identique (aucune fiche supersédée).
    obtenu = json.dumps(d, ensure_ascii=False, indent=2)
    with open(os.path.join(ICI, "test_recall_sas_golden.json"), encoding="utf-8") as f:
        golden = f.read()
    assert obtenu == golden, "le défaut a divergé du golden"


# =========================================================================== #
# T2 — les 3 champs VOYAGENT brut->en_attente->structure (survie à la promotion)
# =========================================================================== #
def test_T2_supersession_voyage_et_survit_a_la_promotion(mem):
    # en_attente : la supersession vit dans le meta (relisible).
    r = mem.stage({"content": "fait perime analyse", "domain": "d", "category": "c",
                   "title": "perime-cand", "superseded": "oui",
                   "superseded_par": "fiche-successeur", "date_validite": "01/01/2026"})
    a = next(c for c in mem._scan(mem.EN_ATTENTE, "", "en_attente")
             if "perime-cand" in c["file"])
    assert a["superseded"] == "oui"
    assert a["superseded_par"] == "fiche-successeur"
    assert a["date_validite"] == "01/01/2026"

    # promotion : superseded ET superseded_par ET date_validite SURVIVENT.
    # mutation « perdre-superseded_par/date-a-la-promotion » => rouge.
    mem.promote({"id": r["id"]})
    st = next(c for c in mem._scan(mem.STRUCT, "", "structure")
              if "perime-cand" in c["file"])
    assert st["superseded"] == "oui"
    assert st["superseded_par"] == "fiche-successeur", "superseded_par blanchi à la promotion"
    assert st["date_validite"] == "01/01/2026", "date_validite blanchie à la promotion"

    # et le brut aussi porte les 3 champs quand la capture les fournit.
    mem.add_note({"content": "capture supersédée", "superseded": "oui",
                  "superseded_par": "successeur-x", "date_validite": "02/02/2026"})
    b = mem._scan(mem.BRUT, "", "brut")
    assert b and b[0]["superseded"] == "oui" and b[0]["superseded_par"] == "successeur-x"


# =========================================================================== #
# T3 — superseded posé UNIQUEMENT par geste humain (jamais un effet de bord)
# =========================================================================== #
def test_T3_superseded_seulement_par_geste_humain(mem):
    # (1) écritures AUTOMATIQUES (sans geste) => superseded='non'.
    mem.memorize({"content": "fait auto memorize", "domain": "d",
                  "category": "c", "title": "auto"})
    st = next(c for c in mem._scan(mem.STRUCT, "", "structure") if "auto" in c["file"])
    assert st["superseded"] == "non", "supersession posée sans geste humain (memorize)"

    r = mem.stage({"content": "cand auto stage", "domain": "d",
                   "category": "c", "title": "cand"})
    mem.promote({"id": r["id"]})
    st2 = next(c for c in mem._scan(mem.STRUCT, "", "structure") if "cand" in c["file"])
    # mutation « superseded-posé-sans-geste-humain » (promote invente l'oubli) => rouge.
    assert st2["superseded"] == "non", "supersession posée sans geste humain (promotion)"

    mem.add_note({"content": "note auto capture"})
    b = next(c for c in mem._scan(mem.BRUT, "", "brut") if "note auto" in c["excerpt"])
    assert b["superseded"] == "non", "supersession posée sans geste humain (note)"

    # (2) SEUL le geste humain superseder() pose 'oui'.
    mem.superseder({"path": st["path"], "superseded_par": "fiche-x",
                    "date_validite": "01/01/2026"})
    st3 = next(c for c in mem._scan(mem.STRUCT, "", "structure") if "auto" in c["file"])
    assert st3["superseded"] == "oui" and st3["superseded_par"] == "fiche-x"


# =========================================================================== #
# T4 — TEST BINAIRE 3 CLAUSES (a) hors bloc principal (b) dans bloc superseded
#      (c) existe toujours (non détruite, réversible)
# =========================================================================== #
def test_T4_binaire_supersession_trois_clauses(mem):
    _struct(mem, "travail", "methodes", "fiche-fausse",
            "critere kily faux mais tres pertinent")
    _forces(mem, {"fiche-fausse": 9.0})
    path = "structure/travail/methodes/fiche-fausse.md"
    abspath = os.path.join(mem.ROOT, path)
    origine = open(abspath, encoding="utf-8").read()

    # AVANT : la fiche est bien dans le bloc principal (structure), en tête.
    avant = _sas(mem)
    assert path in [c["path"] for c in avant["blocs"]["structure"]]
    assert avant["blocs"]["structure"][0]["path"] == path

    # GESTE HUMAIN : Kily la juge fausse.
    mem.superseder({"path": path, "superseded_par": "fiche-vraie",
                    "date_validite": "09/07/2026"})
    apres = _sas(mem)

    # (a) N'EST PLUS dans le bloc principal — ni dans aucun bloc d'étage.
    #     mutation « supprimer-le-routage-superseded » (reste dans structure) => rouge.
    assert path not in [c["path"] for c in apres["blocs"]["structure"]]
    assert path not in [c["path"] for c in apres["blocs"]["en_attente"]]
    assert path not in [c["path"] for c in apres["blocs"]["brut"]]

    # (b) EST dans le bloc superseded, avec son étiquette (successeur + date).
    sup = [c for c in apres["blocs"]["superseded"] if c["path"] == path]
    assert sup, "la supersédée n'est pas dans le bloc superseded"
    assert sup[0]["superseded_par"] == "fiche-vraie"
    assert sup[0]["date_validite"] == "09/07/2026"

    # (c) EXISTE toujours (NON détruite) + contenu préservé.
    #     mutation « détruire-au-lieu-de-séparer » (os.remove) => rouge.
    assert os.path.exists(abspath), "fiche détruite : clause (c) violée"
    contenu = open(abspath, encoding="utf-8").read()
    assert "critere kily faux mais tres pertinent" in contenu, "contenu perdu"

    # RÉVERSIBLE : desuperseder la ramène, byte-identique à l'origine.
    mem.desuperseder({"path": path})
    assert open(abspath, encoding="utf-8").read() == origine
    rev = _sas(mem)
    assert path in [c["path"] for c in rev["blocs"]["structure"]]
    assert rev["blocs"]["superseded"] == []


# =========================================================================== #
# T5 — GOLDEN COMPORTEMENT RECALL type ForgetEval (avant/après par cas)
# =========================================================================== #
_FORGETEVAL = [
    {"nom": "fait-obsolete", "dom": "travail", "cat": "faits",
     "contenu": "critere kily obsolete a remplacer",
     "query": "kily obsolete", "successeur": "fait-a-jour",
     "date_validite": "01/06/2026"},
    {"nom": "chiffre-faux", "dom": "nexus", "cat": "mesures",
     "contenu": "mesure kily erronee corrigee depuis",
     "query": "mesure erronee", "successeur": "mesure-corrigee",
     "date_validite": "15/03/2026"},
]


def test_T5_golden_comportement_forgeteval(mem):
    """Pour chaque cas (un fait + une requête qui le faisait remonter) : AVANT la
    supersession la requête place la fiche EN TÊTE du bloc principal (structure) ;
    APRÈS le geste humain, la MÊME requête ne la ramène PLUS en tête du bloc
    principal — elle est dans le bloc superseded, et demeure retrouvable."""
    for cas in _FORGETEVAL:
        for d in (mem.STRUCT, mem.EN_ATTENTE, mem.BRUT):
            shutil.rmtree(d, ignore_errors=True)
            os.makedirs(d, exist_ok=True)
        # la fiche visée + une concurrente structure sans rapport (non pertinente).
        _struct(mem, cas["dom"], cas["cat"], cas["nom"], cas["contenu"])
        _struct(mem, cas["dom"], cas["cat"], "autre-fiche", "sujet distinct sans rapport")
        path = "structure/%s/%s/%s.md" % (cas["dom"], cas["cat"], cas["nom"])
        query = cas["query"]

        # AVANT : en tête du bloc principal.
        avant = mem.recall({"query": [query], "scope": ["all"], "format": ["sas"]})
        assert avant["blocs"]["structure"], "cas %s : rien en structure" % cas["nom"]
        assert avant["blocs"]["structure"][0]["path"] == path, \
            "cas %s : la fiche ne remontait pas en tête AVANT" % cas["nom"]
        assert avant["blocs"]["superseded"] == []

        # GESTE HUMAIN.
        mem.superseder({"path": path, "superseded_par": cas["successeur"],
                        "date_validite": cas["date_validite"]})

        # APRÈS : ne remonte PLUS en tête du bloc principal, mais retrouvable.
        apres = mem.recall({"query": [query], "scope": ["all"], "format": ["sas"]})
        tops = [c["path"] for c in apres["blocs"]["structure"]]
        assert path not in tops, "cas %s : encore dans le bloc principal APRÈS" % cas["nom"]
        sup = [c for c in apres["blocs"]["superseded"] if c["path"] == path]
        assert sup, "cas %s : introuvable dans le bloc superseded" % cas["nom"]
        assert sup[0]["superseded_par"] == cas["successeur"]
        assert sup[0]["date_validite"] == cas["date_validite"]


# =========================================================================== #
# T6 — une supersédée n'est JAMAIS struct_top ni dans l'alerte
# =========================================================================== #
def test_T6_supersedee_jamais_struct_top(mem):
    # la fausse a le score le PLUS FORT : sans routage elle serait struct_top.
    _struct(mem, "d", "c", "fausse-forte", "critere kily")
    _struct(mem, "d", "c", "vraie-faible", "critere kily")
    _forces(mem, {"fausse-forte": 9.0, "vraie-faible": 1.0})
    mem.superseder({"path": "structure/d/c/fausse-forte.md",
                    "superseded_par": "x", "date_validite": "01/01/2026"})

    sas = _sas(mem)
    struct_paths = [c["path"] for c in sas["blocs"]["structure"]]
    assert "structure/d/c/fausse-forte.md" not in struct_paths
    # mutation « supprimer-le-routage-superseded » : la fausse reprend la tête => rouge.
    assert sas["blocs"]["structure"][0]["path"] == "structure/d/c/vraie-faible.md"
    # la validée tient la tête -> aucune alerte ; la supersédée ne concourt pas.
    assert sas["alerte"] is None
    assert [c["path"] for c in sas["blocs"]["superseded"]] == ["structure/d/c/fausse-forte.md"]


# =========================================================================== #
# T7 — ordre des blocs + des champs du format sas FIGÉ (4e bloc en dernier)
# =========================================================================== #
_ORDRE_CAND_SAS = ("etage", "domain", "category", "file", "path", "excerpt",
                   "source", "verifie", "superseded", "superseded_par",
                   "date_validite", "_relevance", "_force", "_score")


def test_T7_ordre_blocs_et_champs_fige(mem):
    _struct(mem, "d", "c", "valide", "critere kily")
    _struct(mem, "d", "c", "oubliee", "critere kily faux")
    mem.superseder({"path": "structure/d/c/oubliee.md",
                    "superseded_par": "valide", "date_validite": "01/01/2026"})
    sas = _sas(mem)

    # ordre des BLOCS : le 4e bloc `superseded` s'ajoute en DERNIER, aucun autre
    # n'est réordonné. mutation « ajout-4e-bloc-réordonne-un-autre-champ » => rouge.
    assert tuple(sas["blocs"].keys()) == ("structure", "en_attente", "brut", "superseded")
    # ordre des CLÉS racine figé.
    assert tuple(sas.keys()) == ("ok", "scope", "format", "count", "blocs", "alerte")
    # ordre des CHAMPS de chaque candidat figé (dans TOUS les blocs).
    for cands in sas["blocs"].values():
        for c in cands:
            assert tuple(c.keys()) == _ORDRE_CAND_SAS, "champ du format sas réordonné"


# =========================================================================== #
# T8 — lecture seule : recall/sas ne modifient rien ; superseder ne touche que
#      la fiche visée
# =========================================================================== #
def _empreintes(base):
    emp = {}
    for dp, _d, files in os.walk(base):
        for fl in sorted(files):
            p = os.path.join(dp, fl)
            with open(p, "rb") as f:
                emp[os.path.relpath(p, base)] = hashlib.sha256(f.read()).hexdigest()
    return emp


def test_T8_lecture_seule_et_superseder_cible(mem):
    _struct(mem, "d", "c", "a", "critere kily un")
    _struct(mem, "d", "c", "b", "critere kily deux")

    # recall + sas ne modifient RIEN.
    avant = _empreintes(mem.ROOT)
    mem.recall({"query": ["kily"], "scope": ["all"]})
    _sas(mem)
    assert _empreintes(mem.ROOT) == avant

    # superseder ne modifie QUE la fiche visée (b), jamais a.
    emp_a = hashlib.sha256(open(os.path.join(mem.STRUCT, "d", "c", "a.md"), "rb").read()).hexdigest()
    mem.superseder({"path": "structure/d/c/b.md", "superseded_par": "a",
                    "date_validite": "01/01/2026"})
    emp_a2 = hashlib.sha256(open(os.path.join(mem.STRUCT, "d", "c", "a.md"), "rb").read()).hexdigest()
    assert emp_a == emp_a2, "superseder a touché une autre fiche que la cible"
