"""Recall SÉMANTIQUE v0 — mode OPT-IN, embedder LOCAL injecté (mémoire-beta).

Le sémantique COMPLÈTE le lexical, il ne le remplace pas : le DÉFAUT (sans flag)
reste lexical byte-identique ; le mode opt-in rouvre le jeu candidat par le SENS,
EXPOSE la décomposition du score et MARQUE les fiches remontées par le sens. La
fusion vit dans nexus_force.rank (inchangée). L'embedder est INJECTÉ comme le
client LLM ; à défaut de modèle local, la fabrique rend None -> LEXICAL PUR
(jamais un pseudo-sémantique n-grammes).

Structure :
  A. FABRIQUE + CACHE (nexus_embedder)
       - fabrique absente -> None (jamais n-grammes)          [MUTATION]
       - cache : clé = (hash, VERSION) ; version dans la clé   [MUTATION]
       - cache : contenu changé -> invalidation ; froid==chaud (golden)
  B. RECALL opt-in (plomberie, embedder MOCK déterministe)
       - défaut sans flag ignore l'embedder : byte-identique   [MUTATION]
       - le hook appelle l'embedder ; fusion combinée exposée
       - fiche remontée par le SENS : ajoutée ET marquée       [MUTATION]
       - alpha <= 0.5 ; le recall n'écrit JAMAIS dans la force [MUTATION]
       - embedder absent + flag -> repli lexical pur (jamais n-grammes)
  C. BANC QUALITÉ (skippé si aucun embedder local) : voiture~automobile.
"""
import os
import sys
import json
import hashlib
import importlib
import importlib.util

import pytest


# --------------------------------------------------------------------------- #
# Chargement des modules
# --------------------------------------------------------------------------- #
def _racine():
    ici = os.path.dirname(os.path.abspath(__file__))          # backend/tests
    return os.path.dirname(os.path.dirname(ici))              # racine du dépôt


def _charger_organe(nom):
    org = os.path.join(_racine(), "organes")
    if org not in sys.path:
        sys.path.insert(0, org)
    mod = importlib.import_module(nom)
    return importlib.reload(mod)


def _charger_memory_api():
    chemin = os.path.join(_racine(), ".claude", "skills", "memoire-beta",
                          "scripts", "memory_api.py")
    spec = importlib.util.spec_from_file_location("memory_api_sem_test", chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def nemb():
    return _charger_organe("nexus_embedder")


@pytest.fixture
def nf():
    return _charger_organe("nexus_force")


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


def _fiche(m, dom, cat, nom, contenu):
    d = os.path.join(m.STRUCT, dom, cat)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, nom + ".md"), "w", encoding="utf-8") as f:
        f.write(contenu)


# Embedder MOCK déterministe (n-grammes de surface) — teste la PLOMBERIE, PAS la
# qualité sémantique. Un spy compte les appels pour prouver que le hook l'appelle.
class _EmbedderSpy:
    def __init__(self, inner):
        self.inner = inner
        self.version = getattr(inner, "version", "spy-v1")
        self.appels = 0

    def embed(self, text):
        self.appels += 1
        return self.inner.embed(text)


# Embedder versionné : le vecteur dépend d'une « génération » (simule un
# changement de MODÈLE sans changer le texte) — sert aux tests de cache.
class _EmbedderVersionne:
    def __init__(self, gen, version):
        self.gen = gen
        self.version = version

    def embed(self, text):
        h = int(hashlib.md5(("%d:%s" % (self.gen, text)).encode()).hexdigest(), 16)
        return [float((h >> (8 * i)) & 0xFF) for i in range(4)]


# =========================================================================== #
# A. FABRIQUE + CACHE (nexus_embedder)
# =========================================================================== #
def test_A1_fabrique_absente_rend_none_jamais_ngrammes(nemb, nf, monkeypatch):
    """MUTATION : un repli n-grammes au lieu du lexical -> ROUGE.
    Sans modèle local (sentence-transformers indisponible), la fabrique DOIT
    rendre None (= recall lexical pur), JAMAIS un embedder de secours n-grammes."""
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)  # import échoue
    emb = nemb.charger_embedder()
    assert emb is None, "fabrique sans modèle local doit rendre None (repli LEXICAL)"

    # Et si par mutation elle rendait quelque chose, ce ne serait JAMAIS l'embedder
    # n-grammes de test (qui, lui, vit dans nexus_force pour la seule plomberie).
    assert not isinstance(emb, nf.EmbedderFake)


def test_A2_cache_cle_inclut_la_version(nemb):
    """MUTATION : cache sans version dans la clé -> ROUGE.
    La clé est (hash_texte, VERSION). Retirer la version ferait collisionner deux
    modèles : même texte, même clé, vecteur d'un autre modèle servi."""
    emb_v1 = _EmbedderVersionne(gen=1, version="modele-v1")
    emb_v2 = _EmbedderVersionne(gen=2, version="modele-v2")
    c1 = nemb.CacheEmbeddings(emb_v1)
    c2 = nemb.CacheEmbeddings(emb_v2)

    cle = c1._cle("bonjour")
    assert isinstance(cle, tuple) and len(cle) == 2
    assert cle[1] == "modele-v1"                      # la VERSION est dans la clé
    # Même texte, versions différentes -> clés différentes (jamais de collision).
    assert c1._cle("bonjour") != c2._cle("bonjour")
    # Le composant hash, lui, ne dépend QUE du texte.
    assert c1._cle("bonjour")[0] == c2._cle("bonjour")[0]
    assert c1._cle("bonjour")[0] != c1._cle("adieu")[0]


def test_A3_cache_invalide_au_changement_de_contenu_et_transparent(nemb):
    """Contenu changé -> hash changé -> RECALCUL. Froid == chaud (golden) : le
    cache accélère sans jamais changer le vecteur (embedder pur enveloppé)."""
    spy = _EmbedderSpy(_EmbedderVersionne(gen=1, version="v"))
    cache = nemb.CacheEmbeddings(spy)

    froid = cache.embed("texte A")
    assert spy.appels == 1
    chaud = cache.embed("texte A")                    # HIT : pas de recalcul
    assert spy.appels == 1
    assert chaud == froid                             # cache froid == cache chaud

    autre = cache.embed("texte A modifié")            # contenu changé -> MISS
    assert spy.appels == 2
    assert autre != froid


def _faux_sentence_transformers(constructeur):
    """Faux module `sentence_transformers` injectable via sys.modules, dont
    l'attribut SentenceTransformer est `constructeur`."""
    import types
    mod = types.ModuleType("sentence_transformers")
    mod.SentenceTransformer = constructeur
    mod.__version__ = "test-9.9"
    return mod


def test_A4_chargement_local_files_only_applique(nemb, monkeypatch):
    """GARDIEN de l'invariant « réseau jamais dans l'organe ».
    MUTATION : retirer local_files_only=True (ou le mettre à False) -> ROUGE.
    Le chargement du modèle DOIT passer local_files_only=True."""
    vu = {}

    class FauxST:
        def __init__(self, nom, **kwargs):
            vu["nom"] = nom
            vu["kwargs"] = kwargs

        def encode(self, text, **k):
            return [0.0, 1.0, 0.0]

    monkeypatch.setitem(sys.modules, "sentence_transformers",
                        _faux_sentence_transformers(FauxST))
    emb = nemb.charger_embedder()
    assert emb is not None                            # modèle « présent » -> embedder
    assert vu["kwargs"].get("local_files_only") is True, \
        "SentenceTransformer doit être chargé avec local_files_only=True"


def test_A5_modele_absent_en_local_leve_renvoie_none_sans_reseau(nemb, monkeypatch):
    """Un modèle ABSENT localement (le chargement local_files_only=True LÈVE) fait
    renvoyer None -> repli lexical, JAMAIS une tentative réseau. Toute construction
    SANS local_files_only compterait comme une tentative réseau interdite."""
    compte = {"reseau": 0}

    class FauxSTabsent:
        def __init__(self, nom, **kwargs):
            if kwargs.get("local_files_only"):
                raise OSError("modèle introuvable en local")   # absent -> LÈVE
            # une construction sans local_files_only = bascule réseau interdite
            compte["reseau"] += 1

    monkeypatch.setitem(sys.modules, "sentence_transformers",
                        _faux_sentence_transformers(FauxSTabsent))
    emb = nemb.charger_embedder()
    assert emb is None                                # repli LEXICAL PUR
    assert compte["reseau"] == 0                      # AUCUNE tentative réseau


# =========================================================================== #
# B. RECALL opt-in — plomberie avec embedder MOCK déterministe
# =========================================================================== #
def _corpus_sens(m):
    """Une cible récupérable par le SENS (zéro token commun avec la requête, mais
    proche par n-grammes) + une fiche lexicale + du bruit lointain."""
    _fiche(m, "dom", "cat", "cible",
           "Guide de reformulation des interrogations complexes")
    _fiche(m, "dom", "cat", "lexicale",
           "reformuler une interrogation rapidement projet")
    _fiche(m, "dom", "cat", "bruit",
           "recette de cuisine tarte aux pommes sucre")


def test_B1_defaut_sans_flag_ignore_embedder_byte_identique(mem, nf):
    """MUTATION : défaut non byte-identique -> ROUGE.
    Passer un embedder SANS le flag ne doit RIEN changer : le mode sémantique est
    gardé par le flag opt-in, pas par la simple présence d'un embedder."""
    _corpus_sens(mem)
    q = "reformuler une interrogation"
    base = mem.recall({"query": [q], "scope": ["all"]})
    avec_emb = mem.recall({"query": [q], "scope": ["all"]}, embedder=nf.EmbedderFake())
    assert base == avec_emb                           # sans flag -> embedder ignoré
    assert "mode" not in base                          # aucune clé du mode ne fuit


def test_B2_hook_appelle_embedder_et_expose_la_fusion(mem, nf):
    """Le hook APPELLE l'embedder ; la réponse EXPOSE la décomposition du score
    (rel_n, sem, alpha, pert) — jamais une boîte noire."""
    _corpus_sens(mem)
    spy = _EmbedderSpy(nf.EmbedderFake())
    res = mem.recall({"query": ["reformuler une interrogation"],
                      "scope": ["all"], "semantique": ["1"]}, embedder=spy)

    assert res["mode"] == "semantique"
    assert spy.appels > 0                             # l'embedder a bien été appelé
    assert res["alpha"] == pytest.approx(min(0.5, nf.POIDS_SEMANTIQUE_DEFAUT))
    for c in res["results"]:
        for k in ("_relevance", "_rel_n", "_sem", "alpha", "_pert", "_score"):
            assert k in c                             # décomposition TOUJOURS exposée
            assert 0.0 <= c["_rel_n"] <= 1.0 and 0.0 <= c["_sem"] <= 1.0


def test_B3_fiche_par_le_sens_ajoutee_ET_marquee(mem, nf):
    """MUTATION : une fiche ajoutée par le sens NON marquée -> ROUGE.
    L'élargissement récupère la cible (zéro mot commun) et le résultat la MARQUE
    « remontée par le sens, cos=…, aucun mot commun » (étiqueter, jamais décoter)."""
    _corpus_sens(mem)
    q = "reformuler une interrogation"

    # Baseline lexicale : la cible est INVISIBLE (aucun token commun).
    lex = mem.recall({"query": [q], "scope": ["all"]})
    assert "cible.md" not in [r["file"] for r in lex["results"]]

    sem = mem.recall({"query": [q], "scope": ["all"], "semantique": ["oui"]},
                     embedder=nf.EmbedderFake())
    par_fichier = {r["file"]: r for r in sem["results"]}

    # La cible est RÉCUPÉRÉE par le sens...
    assert "cible.md" in par_fichier
    cible = par_fichier["cible.md"]
    assert cible["_relevance"] == 0.0                 # ...sans aucun lexical...
    assert cible["_sem"] >= sem["seuil_elargissement"]
    assert cible["remontee_par_le_sens"] is True
    # ...ET MARQUÉE explicitement (jamais cachée ni décotée).
    assert "marque" in cible
    assert cible["marque"].startswith("remontée par le sens")
    assert "aucun mot commun" in cible["marque"]

    # Une fiche lexicale n'est PAS marquée « par le sens » (elle a des mots communs).
    if "lexicale.md" in par_fichier:
        assert par_fichier["lexicale.md"]["remontee_par_le_sens"] is False
        assert "marque" not in par_fichier["lexicale.md"]
    # Le bruit lointain (sous le seuil) n'est pas remonté (pas de flood).
    assert "bruit.md" not in par_fichier


def test_B4_alpha_borne_a_0_5_le_sens_complete(mem, nf):
    """alpha <= 0.5 : le sémantique COMPLÈTE la pertinence lexicale, il ne la
    remplace pas (constante PROVISOIRE, à recalibrer sur le banc synonymes)."""
    _corpus_sens(mem)
    res = mem.recall({"query": ["reformuler"], "scope": ["all"], "mode": ["semantique"]},
                     embedder=nf.EmbedderFake())
    assert res["alpha"] <= 0.5


def test_B5_recall_semantique_n_ecrit_jamais_dans_la_force(mem, nf):
    """MUTATION : le recall écrit dans la force -> ROUGE.
    Empreintes SHA-256 inchangées + aucun forces.json créé après un recall
    sémantique (le recall LIT la force, ne l'écrit jamais)."""
    _corpus_sens(mem)

    def emp(base):
        out = {}
        for dp, _d, files in os.walk(base):
            for fl in sorted(files):
                p = os.path.join(dp, fl)
                with open(p, "rb") as f:
                    out[p] = hashlib.sha256(f.read()).hexdigest()
        return out

    avant = emp(mem.ROOT)
    mem.recall({"query": ["reformuler une interrogation"], "scope": ["all"],
                "semantique": ["1"]}, embedder=nf.EmbedderFake())
    apres = emp(mem.ROOT)
    assert avant == apres                             # aucun octet modifié
    assert not os.path.exists(os.path.join(mem.ROOT, "forces.json"))


def test_B6_repli_lexical_pur_si_embedder_absent(mem):
    """Flag posé mais AUCUN embedder injecté -> REPLI LEXICAL PUR : résultats
    IDENTIQUES au lexical (jamais un pseudo-sémantique), enveloppe honnête."""
    _corpus_sens(mem)
    q = "reformuler une interrogation"
    lex = mem.recall({"query": [q], "scope": ["all"]})
    repli = mem.recall({"query": [q], "scope": ["all"], "semantique": ["1"]},
                       embedder=None)

    assert repli["mode"] == "semantique"
    assert repli["embedder"] == "absent"
    assert repli["fallback"] == "lexical"
    # Mêmes fiches, mêmes scores que le lexical pur (aucune fiche « par le sens »).
    assert [r["path"] for r in repli["results"]] == [r["path"] for r in lex["results"]]
    for r in repli["results"]:
        assert "marque" not in r                      # jamais de sémantique de façade


def test_B7_forces_lues_departagent_sans_dominer(mem, nf):
    """La force LUE (forces.json) départage à pertinence sémantique égale, sans
    écraser la pertinence : score = pert + beta·f(force), jamais pert × force."""
    _fiche(mem, "dom", "cat", "faible", "projet distinctifxyz contenu")
    _fiche(mem, "dom", "cat", "forte", "projet distinctifxyz contenu")
    with open(os.path.join(mem.ROOT, "forces.json"), "w", encoding="utf-8") as f:
        json.dump({"forte": 5.0, "faible": 0.2}, f)

    res = mem.recall({"query": ["distinctifxyz"], "scope": ["structure"],
                      "semantique": ["1"]}, embedder=nf.EmbedderFake())
    ordre = [r["file"] for r in res["results"]]
    assert ordre[0] == "forte.md"                     # la force départage
    assert res["results"][0]["_score"] != res["results"][0]["_pert"] * \
        res["results"][0]["_force"]                   # additif, jamais multiplicatif


# =========================================================================== #
# C. BANC QUALITÉ — voiture ~ automobile (NON bloquant : skip sans modèle local)
# =========================================================================== #
def test_C1_banc_qualite_synonymes_si_embedder_local(nemb):
    """Banc de QUALITÉ sémantique (pas de plomberie). Le mock n-grammes ne peut
    PAS le passer (cf. xfail voiture~automobile de PR#57, resté xfail). Ici : si
    un VRAI embedder local est disponible, la synonymie doit être captée ; sinon
    on SKIP (jamais un test CI bloquant)."""
    emb = nemb.charger_embedder()
    if emb is None:
        pytest.skip("aucun embedder local : banc qualité sémantique non applicable")
    a, b = emb.embed("voiture"), emb.embed("automobile")
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    cos = dot / (na * nb) if na and nb else 0.0
    assert cos > 0.5, "un vrai embedder doit rapprocher voiture~automobile"
