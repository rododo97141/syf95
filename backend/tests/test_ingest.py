"""Ingestion externe — NOURRIR NEXUS DU MONDE EXTÉRIEUR (canal d'entrée sous garde).

Le run autonome a mesuré le solipsisme à 93,9 % : aucun canal d'entrée externe
n'existait. Cette suite couvre l'ouverture de ce canal ET ses gardes, point par
point du mandat. Chaque test NOMME la mutation qu'il fait rougir (défense
adversariale : on prouve que la garde MORD, pas seulement qu'elle existe).

  T1  ingerer : hors-allowlist=lève (mut. ingere-quand-meme), source=='interne'
      =lève (mut. accepte-interne), réseau INJECTÉ jamais appelé (zéro appel dans
      l'organe), écrit BRUT avec source correct.
  T2  rétro-tag N fiches en source='interne' EXACT, single-writer, baseline N/N.
  T3  le champ source VOYAGE brut->en_attente->structure (mut. perd-source-a-la-
      promotion).
  T4  contrat sas étendu + GOLDEN du format sas avant/après (seule différence =
      source+verifie ajoutés PAR candidat ; ordre blocs/candidats/alerte/scores
      identiques, mut. reordonne-format-sas) + défaut byte-identique (golden PR66)
      + inventaire des consommateurs de format=sas.
  T5  externe promu en structure reste verifie=non ET source non blanchie au
      recall (mut. blanchit-a-la-promotion).
  T6  binaire solipsisme dérivé de source=='interne' EXACT ; 'interne-x' compte
      EXTERNE (mut. startswith).
  T7  GARDE FORCE sur CHAÎNE COMPLÈTE : capitaliser externe verifie=non →
      consulter → generer_jeton → appliquer(succes) → calculer_forces ⇒ force
      RESTE 1.0 (succes retrogradé en ok) ; appliquer(echec) ⇒ descend sous 1.0 ;
      jamais de statut posé à la main (mut. retrogradation-retiree : force monte).
  T8  98 : ratio observé (diagnostic), digue zéro-hors-allowlist, couverture
      étiquetage 100 %, bilan cassé = 98 debout.
  T9  proposition allowlist examinable (source+frequence+echantillon+pourquoi) ;
      le système n'écrit JAMAIS l'allowlist (mut. systeme-ecrit-allowlist).
  T10 lecture seule SHA-256 hors fichiers propres + rétrocompat + smoke.
"""
import os
import ast
import sys
import json
import hashlib
import importlib
import importlib.util

import pytest


ICI = os.path.dirname(os.path.abspath(__file__))              # backend/tests
RACINE = os.path.dirname(os.path.dirname(ICI))                # racine du dépôt
ORGANES = os.path.join(RACINE, "organes")
SKILL = os.path.join(RACINE, ".claude", "skills", "memoire-beta", "scripts")
if ORGANES not in sys.path:
    sys.path.insert(0, ORGANES)


def _charger(nom, chemin):
    spec = importlib.util.spec_from_file_location(nom, chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _charger_memory_api():
    return _charger("memory_api_ingest_test", os.path.join(SKILL, "memory_api.py"))


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def mem(tmp_path):
    """memory_api frais, racines redirigées vers un dossier jetable."""
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


@pytest.fixture
def ingest():
    return _charger("nexus_ingest_test", os.path.join(ORGANES, "nexus_ingest.py"))


@pytest.fixture
def n98():
    return _charger("nexus_98_ingest_test", os.path.join(ORGANES, "nexus_98.py"))


@pytest.fixture
def capital(tmp_path, monkeypatch):
    """nexus_capital + force + sense + lecons, racines TOUTES isolées (jamais le
    vrai memoire_data ni le vrai journal des leçons). Réplique de test_capital."""
    racine_memoire = tmp_path / "memoire_data"
    monkeypatch.setenv("MEMOIRE_ROOT", str(racine_memoire))       # relu à chaque appel
    monkeypatch.setenv("CAPTEURS_ROOT", str(tmp_path / "cap"))    # (déjà isolé par conftest)

    import nexus_force
    import nexus_sense
    import nexus_lecons
    import nexus_capital
    nexus_force = importlib.reload(nexus_force)
    dl = tmp_path / "lecons"
    monkeypatch.setattr(nexus_lecons, "DIR", str(dl))
    monkeypatch.setattr(nexus_lecons, "JOURNAL", str(dl / "journal.jsonl"))
    monkeypatch.setattr(nexus_lecons, "TRANSFERT", str(dl / "transfert.jsonl"))

    class _C:
        pass
    c = _C()
    c.cap = nexus_capital
    c.force = nexus_force
    c.sense = nexus_sense
    return c


# --------------------------------------------------------------------------- #
# Corpus golden (miroir EXACT de test_recall_sas._corpus_golden) : le golden
# PR66 est pris sur CE corpus, requête « zorglubide budget ».
# --------------------------------------------------------------------------- #
def _corpus_golden(m):
    def _struct(dom, cat, nom, contenu):
        d = os.path.join(m.STRUCT, dom, cat)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, nom + ".md"), "w", encoding="utf-8") as f:
            f.write(contenu)
    _struct("travail", "methodes", "struct-forte",
            "# fiche forte\nprojet zorglubide budget equipe planning\n")
    _struct("travail", "methodes", "struct-faible",
            "# fiche faible\nprojet budget divers rangement\n")
    with open(os.path.join(m.EN_ATTENTE, "20260101-000000-candidat-non-promu.md"),
              "w", encoding="utf-8") as f:
        f.write("# (en attente) candidat\nanalyse zorglubide en attente de validation\n")
    with open(os.path.join(m.BRUT, "2026-01-01.md"), "w", encoding="utf-8") as f:
        f.write("# Notes brutes\nnote rapide budget zorglubide capturee vite\n")


# =========================================================================== #
# T1 — ingerer : gardes qui MORDENT + réseau injecté jamais appelé + BRUT correct
# =========================================================================== #
def test_T1_ingerer_gardes_reseau_et_brut(mem, ingest):
    allow = {"wikipedia"}

    # (a) hors-allowlist => LÈVE  (mutation « ingere-quand-meme » => rouge)
    with pytest.raises(ValueError):
        ingest.ingerer("du texte", source="reddit-non-approuve", memoire=mem, allowlist=allow)
    # (b) source == 'interne' => LÈVE (mutation « accepte-interne » => rouge) :
    #     l'organe externe ne produit JAMAIS d'interne.
    with pytest.raises(ValueError):
        ingest.ingerer("du texte", source="interne", memoire=mem, allowlist=allow)
    # (c) source vide => LÈVE
    with pytest.raises(ValueError):
        ingest.ingerer("du texte", source="  ", memoire=mem, allowlist=allow)
    # Aucune de ces gardes n'a rien écrit : l'organe ne produit RIEN s'il lève.
    assert [f for f in os.listdir(mem.BRUT) if f.endswith(".md")] == []

    # (d) réseau INJECTÉ, JAMAIS appelé DANS l'organe (le fetch est à l'appelant).
    class Reseau:
        def __init__(self):
            self.appels = 0

        def __call__(self, *a, **k):
            self.appels += 1
            return "NE DOIT JAMAIS ÊTRE APPELÉ"

        def get(self, *a, **k):
            self.appels += 1
            return "NE DOIT JAMAIS ÊTRE APPELÉ"

    reseau = Reseau()
    res = ingest.ingerer("  un fait venu du dehors  ", source="wikipedia",
                         url="https://ex.org/x", memoire=mem, allowlist=allow, reseau=reseau)
    assert reseau.appels == 0, "réseau appelé DANS l'organe : ligne rouge franchie"

    # (e) écrit BRUT avec la source correcte, provenance relisible.
    assert res["etage"] == "brut" and res["source"] == "wikipedia"
    bruts = [f for f in os.listdir(mem.BRUT) if f.endswith(".md")]
    assert bruts, "aucune fiche brut écrite"
    texte = open(os.path.join(mem.BRUT, bruts[0]), encoding="utf-8").read()
    source, verifie = mem._lire_provenance(texte, "brut")
    assert source == "wikipedia" and verifie == "non"
    assert "un fait venu du dehors" in texte


# =========================================================================== #
# T2 — rétro-tag : N fiches en source='interne' EXACT, single-writer, N/N
# =========================================================================== #
def test_T2_retro_tag_interne_exact_single_writer(mem):
    N = 9
    for i in range(N):
        mem._write_struct("dom", "cat", "fiche-%02d" % i, "contenu interne numero %d" % i)

    # single-writer memory_api : le rétro-tag stampe toutes les fiches.
    rep = mem.retro_tag_source()
    assert rep["total"] == N and rep["etiquetees"] == N

    # baseline N/N : chaque fiche est lue source == 'interne' EXACT.
    scan = mem._scan(mem.STRUCT, "", "structure")
    assert len(scan) == N
    assert all(c["source"] == "interne" for c in scan)     # EXACT, pas un préfixe
    assert all(c["verifie"] == "non" for c in scan)

    # idempotent : re-taguer ne réécrit rien (memory_api reste seul écrivain).
    rep2 = mem.retro_tag_source()
    assert rep2["etiquetees"] == 0 and rep2["deja"] == N


# =========================================================================== #
# T3 — le champ source VOYAGE brut -> en_attente -> structure
# =========================================================================== #
def test_T3_source_voyage_tout_le_pipeline(mem):
    src = "wikipedia"

    # brut
    mem.add_note({"content": "fait externe capturé", "source": src})
    brut = mem._scan(mem.BRUT, "", "brut")
    assert brut and brut[0]["source"] == src

    # en_attente
    r = mem.stage({"content": "fait externe analysé", "domain": "d", "category": "c",
                   "title": "fait-externe", "source": src, "verifie": "non"})
    att = mem._scan(mem.EN_ATTENTE, "", "en_attente")
    assert att and att[0]["source"] == src and att[0]["verifie"] == "non"

    # structure (promotion) — mutation « perd-source-a-la-promotion » => rouge
    mem.promote({"id": r["id"]})
    st = mem._scan(mem.STRUCT, "", "structure")
    assert st and st[0]["source"] == src, "source blanchie à la promotion"
    assert st[0]["verifie"] == "non"


# =========================================================================== #
# T4 — contrat sas étendu + golden du format sas + défaut byte-identique
# =========================================================================== #
_ATTENDU_CAND = ("etage", "domain", "category", "file", "path", "excerpt",
                 "_relevance", "_force", "_score")


def test_T4_sas_etendu_golden_et_defaut_byte_identique(mem):
    _corpus_golden(mem)
    q = "zorglubide budget"
    sas = mem.recall({"query": [q], "scope": ["all"], "format": ["sas"]})

    # (a) ÉTIQUETAGE : chaque candidat porte source + verifie (couverture 100 %).
    for etage, cands in sas["blocs"].items():
        for c in cands:
            assert isinstance(c["source"], str) and c["source"]
            assert c["verifie"] in ("oui", "non")

    # (b) GOLDEN avant/après : la SEULE différence autorisée = source+verifie
    #     ajoutés PAR candidat. Le reste (clés + valeurs) et l'ordre sont
    #     byte-identiques au classement global. mut. « reordonne-format-sas ».
    cands_ref = (mem._scan(mem.STRUCT, q, "structure")
                 + mem._scan(mem.EN_ATTENTE, q, "en_attente")
                 + mem._scan(mem.BRUT, q, "brut"))
    ranked = [r for r in mem.rank_candidates(q, cands_ref) if r["_relevance"] > 0]
    par_path = {r["path"]: r for r in ranked}

    # ordre : concaténation des blocs == partition stable du classement global.
    partition = ([r["path"] for r in ranked if r["etage"] == "structure"]
                 + [r["path"] for r in ranked if r["etage"] == "en_attente"]
                 + [r["path"] for r in ranked if r["etage"] == "brut"])
    concat = ([c["path"] for c in sas["blocs"]["structure"]]
              + [c["path"] for c in sas["blocs"]["en_attente"]]
              + [c["path"] for c in sas["blocs"]["brut"]])
    assert concat == partition, "ordre du format sas modifié par l'étiquetage"

    for etage in ("structure", "en_attente", "brut"):
        for c in sas["blocs"][etage]:
            g = par_path[c["path"]]
            for k in _ATTENDU_CAND:
                assert c[k] == g[k], "champ %s divergent (format sas altéré)" % k
            # les seules clés en plus : source et verifie.
            assert set(c.keys()) - set(_ATTENDU_CAND) == {"source", "verifie"}

    # (c) DÉFAUT (sans format=sas) reste BYTE-IDENTIQUE au golden PR66.
    defaut = mem.recall({"query": [q], "scope": ["all"]})
    obtenu = json.dumps(defaut, ensure_ascii=False, indent=2)
    with open(os.path.join(ICI, "test_recall_sas_golden.json"), encoding="utf-8") as f:
        golden = f.read()
    assert obtenu == golden, "le défaut a divergé du golden PR66"


def test_T4_inventaire_consommateurs_format_sas():
    """VÉRIFICATION PRÉALABLE : recense les consommateurs de format=sas. AUCUN
    code ne consomme format=sas (seule memory_api le DÉFINIT ; friday_ecrivain ne
    fait que le mentionner en docstring). L'ajout de source+verifie est donc
    rétrocompatible par construction : aucun appelant à casser. Ce test rougit si
    un NOUVEL appelant apparaît sans décision (comme T6 de test_recall_sas)."""
    import re
    pat = re.compile(r"format\W+sas|format=sas")
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
                with open(p, encoding="utf-8") as f:
                    txt = f.read()
                # on ne compte QUE les vrais passages de paramètre, pas les
                # commentaires/docstrings : présence de la chaîne "sas" dans un
                # appel recall/params.
                if pat.search(txt):
                    trouves.add(os.path.relpath(p, RACINE))
    connus = {
        # DÉFINITION + serveur (pas un consommateur) :
        ".claude/skills/memoire-beta/scripts/memory_api.py",
    }
    nouveaux = trouves - connus
    assert not nouveaux, "NOUVEAU consommateur de format=sas sans décision : %s" % sorted(nouveaux)


# =========================================================================== #
# T5 — externe promu reste verifie=non ET source non blanchie au recall
# =========================================================================== #
def test_T5_externe_promu_reste_non_blanchi(mem):
    # verifie='non' (défaut externe) et source externe : les deux VOYAGENT.
    r = mem.stage({"content": "fait externe non confirmé", "domain": "d",
                   "category": "c", "title": "externe-non", "source": "wikipedia",
                   "verifie": "non"})
    mem.promote({"id": r["id"]})
    st = [c for c in mem._scan(mem.STRUCT, "", "structure") if "externe-non" in c["file"]]
    assert st and st[0]["source"] == "wikipedia"        # mut. blanchit-source
    assert st[0]["verifie"] == "non"                    # reste non-vérifié

    # via le recall sas aussi : l'étiquette suit la fiche promue.
    sas = mem.recall({"query": ["fait externe"], "scope": ["structure"], "format": ["sas"]})
    c = next(x for x in sas["blocs"]["structure"] if "externe-non" in x["file"])
    assert c["source"] == "wikipedia" and c["verifie"] == "non"

    # Cas verifie='oui' (Kily certifie) : le champ verifie VOYAGE aussi, non figé
    # à 'non' — mut. blanchit-a-la-promotion (verifie perdu => relu 'non' => rouge).
    r2 = mem.stage({"content": "fait externe confirmé par Kily", "domain": "d",
                    "category": "c", "title": "externe-oui", "source": "wikipedia",
                    "verifie": "oui"})
    mem.promote({"id": r2["id"]})
    st2 = [c for c in mem._scan(mem.STRUCT, "", "structure") if "externe-oui" in c["file"]]
    assert st2 and st2[0]["verifie"] == "oui" and st2[0]["source"] == "wikipedia"


# =========================================================================== #
# T6 — binaire solipsisme dérivé de source=='interne' EXACT
# =========================================================================== #
def test_T6_solipsisme_exact_pas_startswith(n98):
    # mutation « startswith » : 'interne-x' NE DOIT PAS compter interne.
    assert n98.est_interne("interne") is True
    assert n98.est_interne("interne-x") is False
    assert n98.est_interne("wikipedia") is False
    assert n98.est_interne(None) is False

    cands = [{"source": "interne"}, {"source": "interne-x"},
             {"source": "wikipedia"}, {"source": "interne"}]
    r = n98.ratio_solipsisme(cands)
    assert r["total"] == 4
    assert r["interne"] == 2                 # 'interne-x' exclu => EXTERNE
    assert r["externe"] == 2
    assert r["ratio_interne"] == 0.5


# =========================================================================== #
# T7 — GARDE FORCE sur CHAÎNE COMPLÈTE
# =========================================================================== #
def test_T7_garde_force_chaine_complete(capital):
    cap, force = capital.cap, capital.force

    # fiche EXTERNE non vérifiée, écrite par la chaîne (capitaliser), pas à la main.
    slug = cap.capitaliser("Critère venu du dehors du web", "réponse", "contexte",
                           "nexus", source="wikipedia", verifie="non")
    assert cap._provenance_fiche(slug) == ("wikipedia", "non")

    # consulter (fiche-unique) -> generer_jeton -> appliquer(succes)
    rec = cap.consulter("dehors web", "t7")
    assert rec["slugs_retournes"] == [slug]
    jid = cap.generer_jeton_confirmation(rec["id"])
    app = cap.appliquer(rec["id"], slug, "succes", "t7", jeton=jid)

    # succes RETROGRADÉ en 'ok' : jeton consommé, mais crédit-force retenu.
    assert app["statut_juge"] == "succes"
    assert app["retrograde"] is True
    assert app["statut"] == "ok"

    # calculer_forces : la force RESTE 1.0 ('ok' ignoré). mut. retrogradation-
    # retiree : un 'succes' émis donnerait 1.2 (> 1.0) => rouge.
    forces = force.calculer_forces()
    assert forces.get(slug, 1.0) == 1.0

    # appliquer(echec) => descend sous 1.0 (l'échec, lui, n'est jamais retrogradé).
    rec2 = cap.consulter("dehors web", "t7-echec")
    jid2 = cap.generer_jeton_confirmation(rec2["id"])
    app2 = cap.appliquer(rec2["id"], slug, "echec", "t7-echec", jeton=jid2)
    assert app2["retrograde"] is False and app2["statut"] == "echec"
    forces2 = force.calculer_forces()
    assert forces2.get(slug, 1.0) < 1.0

    # Contre-preuve : une fiche INTERNE certifiée par le geste normal monte bien.
    slug_i = cap.capitaliser("Critère interne du système", "réponse", "contexte", "nexus")
    assert cap._provenance_fiche(slug_i) == ("interne", "non")
    rec3 = cap.consulter("interne système", "t7-interne")
    assert rec3["slugs_retournes"][0] == slug_i or slug_i in rec3["slugs_retournes"]


def test_T7_interne_succes_monte_bien(capital):
    """Symétrie : sur une fiche INTERNE, un succes N'EST PAS retrogradé — la force
    monte (1.2). Prouve que la garde vise l'EXTERNE non vérifié, pas tout succes."""
    cap, force = capital.cap, capital.force
    slug = cap.capitaliser("Critère purement interne", "réponse", "contexte", "nexus")
    rec = cap.consulter("purement interne", "t7i")
    assert rec["slugs_retournes"] == [slug]
    jid = cap.generer_jeton_confirmation(rec["id"])
    app = cap.appliquer(rec["id"], slug, "succes", "t7i", jeton=jid)
    assert app["retrograde"] is False and app["statut"] == "succes"
    forces = force.calculer_forces()
    assert forces.get(slug) == 1.2


# =========================================================================== #
# T8 — 98 : diagnostics lecture seule, jamais objectif, 98 ne tombe jamais
# =========================================================================== #
def test_T8_98_diagnostics_lecture_seule(n98):
    cands = [{"source": "interne"}, {"source": "wikipedia"}, {"source": "interne"}]

    # ratio OBSERVÉ (diagnostic) — pas un objectif (note anti-Goodhart présente).
    r = n98.ratio_solipsisme(cands)
    assert r["interne"] == 2 and r["externe"] == 1
    assert "Goodhart" in r["_note"]

    # DIGUE : zéro hors-allowlist.
    d = n98.digue_ingestion(cands, {"wikipedia"})
    assert d["digue_ok"] is True and d["hors_allowlist"] == 0
    d2 = n98.digue_ingestion(cands + [{"source": "pirate"}], {"wikipedia"})
    assert d2["digue_ok"] is False and d2["hors_allowlist"] == 1 and "pirate" in d2["exemples"]

    # COUVERTURE d'étiquetage : 100 % des externes étiquetés.
    c = n98.couverture_etiquetage(cands)
    assert c["complete"] is True and c["couverture"] == 1.0
    # un externe sans étiquette (source vide) => couverture incomplète (fuite vue).
    c2 = n98.couverture_etiquetage(cands + [{"source": ""}])
    assert c2["complete"] is False and c2["couverture"] < 1.0

    # BILAN CASSÉ = 98 DEBOUT : entrées pourries ne font jamais tomber le gardien.
    assert n98.ratio_solipsisme(None)["total"] == 0
    assert n98.ratio_solipsisme("pas une liste")["total"] == 0
    assert n98.digue_ingestion(None, None)["digue_ok"] is True
    assert n98.couverture_etiquetage(None)["couverture"] == 1.0


# =========================================================================== #
# T9 — proposition examinable ; le système n'écrit JAMAIS l'allowlist
# =========================================================================== #
def test_T9_proposition_examinable_systeme_ne_touche_pas_allowlist(tmp_path, ingest):
    prop_path = str(tmp_path / "propositions.jsonl")

    # la proposition est EXAMINABLE : source + frequence + echantillon + pourquoi.
    p = ingest.proposer_source("reddit", frequence=12,
                               echantillon="« ... extrait rencontré ... »",
                               pourquoi="revient souvent, à arbitrer par Kily",
                               chemin=prop_path)
    assert {"source", "frequence", "echantillon", "pourquoi"} <= set(p.keys())
    assert p["source"] == "reddit" and p["frequence"] == 12

    lignes = ingest.lire_propositions(prop_path)
    assert lignes and lignes[0]["source"] == "reddit"
    assert lignes[0]["echantillon"] and lignes[0]["pourquoi"]

    # Le système n'ÉCRIT JAMAIS l'allowlist (mut. systeme-ecrit-allowlist).
    # (a) empreinte du VRAI fichier allowlist inchangée après proposer.
    avant = hashlib.sha256(open(ingest.ALLOWLIST_PATH, "rb").read()).hexdigest()
    ingest.proposer_source("hn", frequence=3, echantillon="x", pourquoi="y", chemin=prop_path)
    apres = hashlib.sha256(open(ingest.ALLOWLIST_PATH, "rb").read()).hexdigest()
    assert avant == apres, "proposer a touché l'allowlist"

    # (b) preuve STRUCTURELLE : aucun open() en écriture ne vise ALLOWLIST_PATH
    #     dans nexus_ingest. Si une mutation ajoutait open(ALLOWLIST_PATH,'w'),
    #     ce test rougirait.
    src = open(os.path.join(ORGANES, "nexus_ingest.py"), encoding="utf-8").read()
    arbre = ast.parse(src)
    for node in ast.walk(arbre):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "open":
            mode = ""
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                mode = str(node.args[1].value)
            if any(x in mode for x in ("w", "a", "x")):
                cible = ast.dump(node.args[0]) if node.args else ""
                assert "ALLOWLIST" not in cible, "écriture de l'allowlist par le système"


# =========================================================================== #
# T10 — lecture seule (SHA hors fichiers propres) + rétrocompat + smoke
# =========================================================================== #
def _sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_T10_lecture_seule_hors_fichiers_propres(mem, ingest, tmp_path):
    # organes que le mandat INTERDIT de modifier : ingerer ne les touche jamais.
    geles = {p: _sha(p) for p in (
        os.path.join(ORGANES, "nexus_force.py"),
        os.path.join(ORGANES, "nexus_bus.py"),
        os.path.join(ORGANES, "nexus_budget.py"),
        ingest.ALLOWLIST_PATH,
    )}
    prop_path = str(tmp_path / "props.jsonl")

    # cycle complet d'ingestion + proposition.
    ingest.ingerer("fait du dehors", source="wikipedia", memoire=mem, allowlist={"wikipedia"})
    ingest.proposer_source("reddit", 1, "e", "p", chemin=prop_path)

    apres = {p: _sha(p) for p in geles}
    assert apres == geles, "un fichier gelé (hors périmètre propre) a été modifié"


def test_T10_retrocompat_et_smoke(mem, ingest, n98):
    # rétrocompat : rank_candidates au comportement inchangé (source hors _search).
    _corpus_golden(mem)
    q = "zorglubide budget"
    d1 = mem.recall({"query": [q], "scope": ["all"]})
    d2 = mem.recall({"query": [q], "scope": ["all"]})
    assert d1 == d2                                   # déterministe
    # aucune clé de provenance ne fuit dans le DÉFAUT (byte-identique golden).
    for r in d1["results"]:
        assert "source" not in r and "verifie" not in r

    # smoke : la brique s'importe et expose ses gestes.
    assert callable(ingest.ingerer) and callable(ingest.proposer_source)
    assert callable(ingest.charger_allowlist)
    assert callable(n98.ratio_solipsisme) and callable(n98.est_interne)
    assert callable(mem.retro_tag_source)
