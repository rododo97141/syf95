"""Promotion — en_attente redevient une FILE DE TRANSIT, pas un cimetière.

Chaque candidat a un cycle de vie FINI avec QUATRE sorties, toutes tracées,
AUCUNE destructive : promu (existant) / doublon (proposition machine +
confirmation humaine) / rejeté (décision du superviseur) / périmé (résidu du
triage : N examens journalisés sans décision).

  T1  clore : les QUATRE raisons (promu byte-identique, doublon, rejeté, périmé),
      déplacement + trace complète, JAMAIS de suppression, no-op tracé sur absent.
  T2  reactiver : retour en file tracé + compteur d'examens REPART À ZÉRO.
  T3  triage : exhaustivité/fairness + jumeaux containment (spécifique contenu =
      proposé ; générique banal = PAS proposé) + perime-eligible EXACTEMENT à N.
  T4  dry-run : rien déplacé sans apply ; proposition complète ; apply revérifie
      (no-op absent, périmée sur empreinte changée, idempotence, jamais tout-sans-
      confirmation).
  T5  l'archive quitte le scan DÉFAUT du recall (scope=all ne la voit plus,
      scope=archive la voit) et sort du bloc en_attente du format sas.
  T6  98 : replie le journal (clos-puis-réactivé pas compté), profondeur/tendance/
      âge-en-examens, bilan cassé = 98 debout.
  T7  lecture seule (SHA-256 hors fichiers propres), promote() byte-identique,
      extraction-pure de l'IDF.
  T8  cohabitation : promotion + mémoire importent proprement (la suite complète
      verte est la garde de non-régression — retrocompat PR57, golden PR66).

Mutations OBLIGATOIRES vues ROUGES au bon endroit (cf. rapport de PR) :
  suppression au lieu d'archive (T1) ; historique complet au lieu de fenêtre (T2/T3
  perime) ; saut de candidat (T3 exhaustivité) ; containment brut sans IDF (T3
  jumeaux) ; apply sans confirmation (T4) ; compte d'archives sans repli (T6).
"""
import os
import json
import hashlib
import importlib.util

import pytest


ICI = os.path.dirname(os.path.abspath(__file__))            # backend/tests
RACINE = os.path.dirname(os.path.dirname(ICI))              # racine du dépôt


# --------------------------------------------------------------------------- #
# Chargement des modules (skill pour memory_api, organes pour nexus_promotion)
# --------------------------------------------------------------------------- #
def _charger(nom, chemin):
    spec = importlib.util.spec_from_file_location(nom, chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _charger_memory_api():
    return _charger("memory_api_promo_test",
                    os.path.join(RACINE, ".claude", "skills", "memoire-beta",
                                 "scripts", "memory_api.py"))


def _charger_promotion():
    return _charger("nexus_promotion_test",
                    os.path.join(RACINE, "organes", "nexus_promotion.py"))


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


@pytest.fixture
def promo():
    return _charger_promotion()


# --------------------------------------------------------------------------- #
# Helpers de corpus
# --------------------------------------------------------------------------- #
def _struct(m, dom, cat, nom, contenu):
    d = os.path.join(m.STRUCT, dom, cat)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, nom + ".md"), "w", encoding="utf-8") as f:
        f.write(contenu)


def _stage(m, contenu, titre=None, dom="d", cat="c"):
    return m.stage({"content": contenu, "domain": dom, "category": cat,
                    "title": titre})["id"]


def _archive_ids(m):
    d = os.path.join(m.ARCHIVE, "en_attente")
    return sorted(f[:-3] for f in os.listdir(d)) if os.path.isdir(d) else []


def _en_attente_ids(m):
    return sorted(f[:-3] for f in os.listdir(m.EN_ATTENTE) if f.endswith(".md"))


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# =========================================================================== #
# T1 — clore : les QUATRE sorties, déplacement + trace, JAMAIS de suppression
# =========================================================================== #
def test_T1_promu_reste_byte_identique(mem):
    """La sortie « promu » est l'existant, INCHANGÉ : promote écrit en structure
    exactement ce que _write_struct produit (byte pour byte)."""
    sid = _stage(mem, "contenu a promouvoir specifique", titre="titre promu")
    res = mem.promote({"id": sid})
    chemin = os.path.join(mem.ROOT, res["path"])
    with open(chemin, encoding="utf-8") as f:
        obtenu = f.read()
    # Reconstruit indépendamment via _write_struct (même chemin de code) : la
    # fiche promue est byte-identique à l'écriture structurée directe.
    m2 = _charger_memory_api()
    m2.ROOT = mem.ROOT + "_bis"
    m2.STRUCT = os.path.join(m2.ROOT, "structure")
    os.makedirs(m2.STRUCT, exist_ok=True)
    ref = m2._write_struct("d", "c", "titre promu",
                           "contenu a promouvoir specifique", "", "")
    with open(os.path.join(m2.ROOT, ref["path"]), encoding="utf-8") as f:
        attendu = f.read()
    assert obtenu == attendu
    assert sid not in _en_attente_ids(mem)      # a bien quitté la file


@pytest.mark.parametrize("raison", ["doublon", "rejete", "perime"])
def test_T1_clore_deplace_et_trace_jamais_supprime(mem, raison):
    """doublon / rejeté / périmé : le candidat est DÉPLACÉ vers archive/en_attente/
    (il EXISTE encore : jamais de suppression) et la trace est complète."""
    sid = _stage(mem, "candidat %s a clore" % raison)
    res = mem.clore(sid, raison, pointeur="fiche-cible", score=0.77, examens=4)
    assert res["ok"]
    # Déplacement (pas suppression) : plus en file, MAIS présent en archive.
    assert sid not in _en_attente_ids(mem)
    assert sid in _archive_ids(mem)             # MUTATION suppression → ce fichier
    #                                             manque → rouge
    assert os.path.exists(os.path.join(mem.ARCHIVE, "en_attente", sid + ".md"))
    # Trace complète et append-only.
    clo = mem.lire_clotures()
    assert len(clo) == 1
    e = clo[0]
    assert e["id"] == sid and e["event"] == "clore" and e["raison"] == raison
    assert e["pointeur"] == "fiche-cible" and e["score"] == 0.77 and e["examens"] == 4
    assert e["noop"] is False and "date" in e


def test_T1_clore_id_absent_est_un_no_op_trace(mem):
    """clore sur un id absent = NO-OP TRACÉ : jamais d'erreur, jamais d'action
    sur archive, mais l'événement est journalisé."""
    res = mem.clore("inconnu-xyz", "rejete")
    assert res["ok"] and res.get("noop") is True and "error" not in res
    assert _archive_ids(mem) == []              # aucune action sur archive
    clo = mem.lire_clotures()
    assert len(clo) == 1 and clo[0]["noop"] is True and clo[0]["id"] == "inconnu-xyz"


def test_T1_clore_raison_invalide_refusee(mem):
    sid = _stage(mem, "x")
    assert "error" in mem.clore(sid, "poubelle")
    assert sid in _en_attente_ids(mem)          # rien déplacé sur raison invalide


# =========================================================================== #
# T2 — reactiver : retour en file + trace + compteur d'examens REPART À ZÉRO
# =========================================================================== #
def test_T2_reactiver_ramene_en_file_et_trace(mem):
    sid = _stage(mem, "candidat a reactiver")
    mem.clore(sid, "rejete")
    res = mem.reactiver(sid)
    assert res["ok"] and sid in _en_attente_ids(mem) and sid not in _archive_ids(mem)
    events = [(e["event"], e.get("noop")) for e in mem.lire_clotures()]
    assert events == [("clore", False), ("reactiver", False)]


def test_T2_reactiver_remet_le_compteur_examens_a_zero(mem, promo):
    """Le compteur d'examens est FENÊTRÉ : compté depuis la dernière entrée en
    file. Un réactivé repart à ZÉRO — les examens de l'époque précédente ne
    comptent plus. MUTATION « historique complet » (ignorer l'époque) → rouge."""
    sid = _stage(mem, "candidat fenetre unique")     # structure vide → a-promouvoir
    promo.passe(mem)
    promo.passe(mem)
    assert promo.examens_fenetres(mem, sid) == 2     # deux examens à l'époque 0

    mem.clore(sid, "rejete")
    mem.reactiver(sid)                               # époque 1 : fenêtre remise à 0
    assert promo.examens_fenetres(mem, sid) == 0     # MUTATION full-history → 2 → rouge

    rep = promo.passe(mem)                           # premier examen de l'époque 1
    prop = {p["id"]: p for p in rep["propositions"]}[sid]
    assert prop["examens_subis"] == 1                # PAS 3 : pas de perime prématuré
    assert prop["verdict"] == "a-promouvoir"


# =========================================================================== #
# T3 — triage : exhaustivité, jumeaux containment, perime-eligible à N
# =========================================================================== #
def test_T3_exhaustivite_tout_candidat_examine(mem, promo):
    """Une passe est EXHAUSTIVE : après elle, TOUT id en file a un examen de
    cette passe. MUTATION « saute un candidat » → un id manque → rouge."""
    ids = {_stage(mem, "candidat un alpha"),
           _stage(mem, "candidat deux beta"),
           _stage(mem, "candidat trois gamma")}
    rep = promo.passe(mem)
    exs = promo.lire_examens(mem)
    vus = {e["id"] for e in exs if e["passe"] == rep["passe"]}
    assert vus == ids                                # aucun candidat sauté
    assert {p["id"] for p in rep["propositions"]} == ids


# --- corpus jumeaux : commun/alpha/beta dans TOUTES les fiches génériques, tokens
#     rares (zorglubide/singulier) uniquement dans la fiche cible longue -------- #
def _corpus_jumeaux(m):
    for i, extra in enumerate(("planning", "client", "notes", "divers")):
        _struct(m, "t", "m", "gen%d" % i,
                "commun alpha beta %s contexte general" % extra)
    _struct(m, "t", "m", "cible-longue",
            "zorglubide singulier distinctif rarissime beaucoup de contexte "
            "autour et details varies pour une fiche vraiment longue et etendue")


def _containment_brut(cand_tokens, fiche_tokens):
    """Containment NON pondéré (la MUTATION) : |cand ∩ fiche| / |cand|."""
    if not cand_tokens:
        return 0.0
    return len(cand_tokens & fiche_tokens) / len(cand_tokens)


def test_T3_jumeaux_containment_specifique_propose(mem, promo):
    _corpus_jumeaux(mem)
    sid = _stage(mem, "zorglubide singulier")        # court, rare, contenu dans cible
    rep = promo.passe(mem)
    prop = {p["id"]: p for p in rep["propositions"]}[sid]
    assert prop["verdict"] == "doublon-de:cible-longue"
    assert prop["score"] >= promo.SEUIL_CONTAINMENT_IDF


def test_T3_jumeaux_containment_generique_PAS_propose(mem, promo):
    """Candidat au vocabulaire BANAL : le containment PONDÉRÉ IDF le rejette, là
    où le containment BRUT le proposerait à tort. MUTATION containment-sans-IDF
    → ce test rougit (c'est tout son objet)."""
    _corpus_jumeaux(mem)
    sid = _stage(mem, "commun alpha beta gammaxinconnu")
    rep = promo.passe(mem)
    prop = {p["id"]: p for p in rep["propositions"]}[sid]
    assert prop["verdict"] == "a-promouvoir"          # PAS doublon

    # Preuve que le test EST discriminant : sous containment BRUT, le générique
    # franchirait le seuil (→ proposé) ; sous IDF, non. La bascule tient à l'IDF.
    fiches = promo.charger_structure(mem)
    cand_tokens = set(mem._tokens("commun alpha beta gammaxinconnu"))
    idf = mem.idf_sur_corpus(cand_tokens, [f["tokens"] for f in fiches])
    pondere = max(promo.containment_idf(cand_tokens, f["tokens"], idf) for f in fiches)
    brut = max(_containment_brut(cand_tokens, f["tokens"]) for f in fiches)
    assert pondere < promo.SEUIL_CONTAINMENT_IDF <= brut


def test_T3_perime_eligible_exactement_a_N_examens(mem, promo):
    """perime-eligible EXACTEMENT à N examens fenêtrés : N-1 passes → pas encore ;
    la N-ième → perime-eligible. (Structure vide : jamais doublon, on isole le
    compteur.)"""
    N = promo.N_EXAMENS_PERIME
    sid = _stage(mem, "candidat qui traine sans decision")
    for i in range(1, N):
        rep = promo.passe(mem)
        prop = {p["id"]: p for p in rep["propositions"]}[sid]
        assert prop["verdict"] == "a-promouvoir", "examen %d ne doit pas périmer" % i
    rep = promo.passe(mem)                            # N-ième examen
    prop = {p["id"]: p for p in rep["propositions"]}[sid]
    assert prop["examens_subis"] == N
    assert prop["verdict"] == "perime-eligible"


# =========================================================================== #
# T4 — dry-run par défaut ; apply revérifie
# =========================================================================== #
def test_T4_passe_est_dry_run_rien_deplace(mem, promo):
    _corpus_jumeaux(mem)
    sid = _stage(mem, "zorglubide singulier")
    promo.passe(mem)
    assert sid in _en_attente_ids(mem)                # toujours en file
    assert _archive_ids(mem) == []                    # rien déplacé
    assert promo.passe(mem)["mode"] == "dry-run"


def test_T4_proposition_complete(mem, promo):
    """Proposition examinable en un coup d'œil : extraits, score, DELTA (tokens du
    candidat absents de la fiche) et empreinte SHA-256 de la cible."""
    _corpus_jumeaux(mem)
    sid = _stage(mem, "zorglubide singulier commun")  # 'commun' absent de la cible
    rep = promo.passe(mem)
    prop = {p["id"]: p for p in rep["propositions"]}[sid]
    assert prop["verdict"].startswith("doublon-de:")
    for cle in ("extrait_candidat", "extrait_cible", "score", "delta",
                "empreinte_cible", "cible_path", "limite"):
        assert cle in prop
    assert "commun" in prop["delta"]                  # token du candidat absent
    assert prop["empreinte_cible"] == promo.empreinte_fiche(mem, prop["cible_path"])
    # coût nommé (marqueur observable), pas une borne
    assert rep["cout"] == rep["n_candidats"] * rep["n_fiches"]


def test_T4_apply_execute_le_confirme_et_est_idempotent(mem, promo):
    _corpus_jumeaux(mem)
    sid = _stage(mem, "zorglubide singulier")
    prop = {p["id"]: p for p in promo.passe(mem)["propositions"]}[sid]

    r1 = promo.apply([prop], mem)
    assert r1["resultats"][0]["etat"] == "clos"
    assert sid in _archive_ids(mem) and sid not in _en_attente_ids(mem)
    # pointeur = cible dans la trace de clôture
    assert mem.lire_clotures()[-1]["pointeur"] == prop["cible"]

    r2 = promo.apply([prop], mem)                     # rejeu → no-op (idempotence)
    assert r2["resultats"][0]["etat"] == "no-op-absent"


def test_T4_apply_empreinte_changee_est_perimee(mem, promo):
    """Empreinte de la cible changée entre proposition et apply → PÉRIMÉE, non
    exécutée (revérification obligatoire)."""
    _corpus_jumeaux(mem)
    sid = _stage(mem, "zorglubide singulier")
    prop = {p["id"]: p for p in promo.passe(mem)["propositions"]}[sid]
    # la cible change après la proposition
    with open(os.path.join(mem.ROOT, prop["cible_path"]), "a", encoding="utf-8") as f:
        f.write("\nmodification posterieure a la proposition\n")
    r = promo.apply([prop], mem)
    assert r["resultats"][0]["etat"] == "perimee"
    assert sid in _en_attente_ids(mem)                # NON exécuté


def test_T4_apply_id_absent_est_no_op(mem, promo):
    _corpus_jumeaux(mem)
    r = promo.apply([{"id": "jamais-en-file", "cible": "cible-longue",
                      "cible_path": "structure/t/m/cible-longue.md",
                      "empreinte_cible": None}], mem)
    assert r["resultats"][0]["etat"] == "no-op-absent"


def test_T4_apply_ne_touche_que_les_confirmes(mem, promo):
    """apply n'exécute QUE les ids confirmés. Un candidat NON confirmé reste en
    file. MUTATION « execute-tout-sans-confirmation » → il partirait → rouge."""
    _corpus_jumeaux(mem)
    sid_conf = _stage(mem, "zorglubide singulier")
    sid_autre = _stage(mem, "zorglubide singulier distinctif")
    props = {p["id"]: p for p in promo.passe(mem)["propositions"]}
    promo.apply([props[sid_conf]], mem)               # un seul confirmé
    assert sid_conf in _archive_ids(mem)
    assert sid_autre in _en_attente_ids(mem)          # l'autre est INTACT


# =========================================================================== #
# T5 — l'archive quitte le scan DÉFAUT du recall et le bloc en_attente du sas
# =========================================================================== #
def test_T5_archive_hors_scan_defaut_mais_visible_en_scope_archive(mem):
    sid = _stage(mem, "zorglubide singulier archive test")
    mem.clore(sid, "doublon", pointeur="x")
    rel = "archive/en_attente/" + sid + ".md"

    # scope=all (défaut) : ne voit PLUS l'archivé.
    tout = mem.recall({"query": ["zorglubide"], "scope": ["all"]})
    assert rel not in [r["path"] for r in tout["results"]]
    # scope=archive : le voit.
    arch = mem.recall({"query": ["zorglubide"], "scope": ["archive"]})
    assert rel in [r["path"] for r in arch["results"]]
    # format sas : l'archivé n'est dans AUCUN des trois blocs (dont en_attente).
    sas = mem.recall({"query": ["zorglubide"], "scope": ["all"], "format": ["sas"]})
    for etage in ("structure", "en_attente", "brut"):
        assert rel not in [c["path"] for c in sas["blocs"][etage]]


# =========================================================================== #
# T6 — nexus_98 : repli du journal, profondeur/tendance/âge, jamais tomber
# =========================================================================== #
@pytest.fixture
def g98(tmp_path, monkeypatch):
    org = os.path.join(RACINE, "organes")
    import sys
    if org not in sys.path:
        sys.path.insert(0, org)
    monkeypatch.setenv("CAPTEURS_ROOT", str(tmp_path / "cap"))
    import importlib
    import nexus_98
    nexus_98 = importlib.reload(nexus_98)
    nexus_98.ROOT = str(tmp_path / "memoire_data")
    os.makedirs(nexus_98.ROOT, exist_ok=True)
    return nexus_98


def test_T6_archives_par_raison_replie_le_journal(g98):
    """État COURANT par id (dernier événement effectif gagne) : un id clos PUIS
    réactivé n'est PAS compté comme archive. MUTATION « compte sans repli » →
    rouge."""
    evenements = [
        {"id": "a", "event": "clore", "raison": "doublon", "noop": False},
        {"id": "b", "event": "clore", "raison": "rejete", "noop": False},
        {"id": "c", "event": "clore", "raison": "perime", "noop": False},
        {"id": "c", "event": "reactiver", "noop": False},   # c revient en file
        {"id": "d", "event": "clore", "raison": "doublon", "noop": False},
        {"id": "z", "event": "clore", "raison": "rejete", "noop": True},  # no-op ignoré
    ]
    comptes = g98.archives_par_raison(evenements)
    assert comptes == {"doublon": 2, "rejete": 1}       # c (réactivé) et z (no-op) exclus


def test_T6_profondeur_tendance_age(g98):
    examens = [
        {"id": "a", "passe": 1, "epoch": 0}, {"id": "b", "passe": 1, "epoch": 0},
        {"id": "a", "passe": 2, "epoch": 0}, {"id": "b", "passe": 2, "epoch": 0},
        {"id": "c", "passe": 2, "epoch": 0},
        {"id": "a", "passe": 3, "epoch": 0}, {"id": "b", "passe": 3, "epoch": 0},
        {"id": "c", "passe": 3, "epoch": 0}, {"id": "e", "passe": 3, "epoch": 0},
    ]
    assert g98.profondeur_par_passe(examens) == [(1, 2), (2, 3), (3, 4)]
    assert g98.tendance_en_attente(examens, k=3) is True   # 2<3<4 monotone
    # âge-en-examens : 'a' présent en file, 3 examens époque 0 → 3.
    en = os.path.join(g98.ROOT, "en_attente")
    os.makedirs(en, exist_ok=True)
    open(os.path.join(en, "a.md"), "w").close()
    assert g98.age_examens_plus_vieux(examens) == 3


def test_T6_bilan_casse_98_reste_debout(g98):
    """Journaux absents / corrompus → bilan_promotion neutre, JAMAIS d'exception :
    le gardien rend quand même son verdict."""
    # journaux corrompus
    os.makedirs(os.path.join(g98.ROOT, "archive"), exist_ok=True)
    os.makedirs(os.path.join(g98.ROOT, "promotion"), exist_ok=True)
    with open(os.path.join(g98.ROOT, "archive", "clotures.jsonl"), "w") as f:
        f.write("{ ceci n'est pas du json\n")
    with open(os.path.join(g98.ROOT, "promotion", "examens.jsonl"), "w") as f:
        f.write("garbage\x00\n")
    bp = g98.bilan_promotion()                          # ne lève pas
    assert bp["profondeur"] == 0 and bp["archives_par_raison"] == {}
    # verdict rendu malgré tout
    assert "SAIN" in g98.calc_verdict([])


# =========================================================================== #
# T7 — lecture seule (SHA-256), promote byte-identique, extraction-pure IDF
# =========================================================================== #
def test_T7_passe_ne_modifie_ni_structure_ni_en_attente(mem, promo):
    _corpus_jumeaux(mem)
    _stage(mem, "zorglubide singulier")
    cibles = []
    for base in (mem.STRUCT, mem.EN_ATTENTE):
        for dp, _d, files in os.walk(base):
            for fl in files:
                cibles.append(os.path.join(dp, fl))
    avant = {p: _sha(p) for p in cibles}
    promo.passe(mem)                                    # écrit SEULEMENT son journal
    apres = {p: _sha(p) for p in cibles}
    assert avant == apres                               # aucun fichier « étranger » touché


def test_T7_idf_extraction_pure_memes_entrees_memes_sorties(mem):
    """idf_sur_corpus est PURE (déterministe) et rank_candidates l'utilise : la
    pertinence d'un candidat == somme des IDF des q-tokens présents."""
    cands = [{"_search": "alpha beta gamma"}, {"_search": "beta gamma delta"},
             {"_search": "gamma delta zorglubide"}]
    corpus = [set(mem._tokens(c["_search"])) for c in cands]
    i1 = mem.idf_sur_corpus(["beta", "zorglubide", "beta"], corpus)
    i2 = mem.idf_sur_corpus(["beta", "zorglubide", "beta"], corpus)
    assert i1 == i2                                     # même entrée → même sortie
    assert set(i1) == {"beta", "zorglubide"}           # dédup interne

    query = "beta zorglubide"
    ranked = mem.rank_candidates(query, cands)
    qtokens = list(dict.fromkeys(mem._tokens(query)))
    idf = mem.idf_sur_corpus(qtokens, corpus)
    par_search = {r["_search"]: r for r in ranked}
    for c, toks in zip(cands, corpus):
        attendu = sum(idf[t] for t in qtokens if t in toks)
        assert par_search[c["_search"]]["_relevance"] == attendu


def test_T7_promote_reste_lecture_du_candidat_puis_ecriture_structure(mem):
    """promote() : le candidat est copié en structure PUIS retiré de la file
    (comportement existant, non modifié par ce chantier)."""
    sid = _stage(mem, "matiere a structurer distinctif", titre="fiche p")
    res = mem.promote({"id": sid})
    assert res["ok"] and res.get("promu_depuis") == sid
    assert os.path.exists(os.path.join(mem.ROOT, res["path"]))
    assert sid not in _en_attente_ids(mem)


# =========================================================================== #
# T8 — cohabitation propre (la suite complète verte est la garde de non-régression)
# =========================================================================== #
def test_T8_modules_importent_et_cohabitent(mem, promo):
    # memory_api : les nouvelles fonctions ET les anciennes coexistent.
    for nom in ("idf_sur_corpus", "rank_candidates", "clore", "reactiver",
                "promote", "recall"):
        assert callable(getattr(mem, nom))
    for nom in ("passe", "apply", "containment_idf", "idf_sur_corpus"):
        assert hasattr(promo, nom) or nom == "idf_sur_corpus"
    assert callable(promo.passe) and callable(promo.apply)
    # une passe sur file vide ne lève pas et coûte 0.
    rep = promo.passe(mem)
    assert rep["n_candidats"] == 0 and rep["cout"] == 0
