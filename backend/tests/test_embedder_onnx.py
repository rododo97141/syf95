"""Backend embedder ONNX LOCAL (recall sémantique v0.2).

POURQUOI (mesuré le 10/07) : un modèle 768d (mpnet) bat MiniLM-L12 sur le banc
(reformulations recall@3 3→4, contrôle 10/10 intact) ; sa variante ONNX
QUANTIFIÉE (≈279 Mo) capte le gain pour un poids ≈ MiniLM. Mais l'organe ne
savait charger un modèle QUE via sentence-transformers (torch, modèle plein). Ce
module ajoute un backend qui fabrique un embedder à partir d'un modèle ONNX +
tokenizer présents LOCALEMENT, INJECTÉ, RÉSEAU INTERDIT, sans changer le défaut
lexical ni la force.

PORTÉE (localisée à organes/nexus_embedder.py) :
  (1) `_mean_pool(last_hidden_state, attention_mask)` PUR (listes imbriquées,
      zéro numpy/onnx) : moyenne des tokens PONDÉRÉE par le masque (ignore le
      padding).
  (2) `_EmbedderOnnx(session, tokenizer, version)` : embed = tokenise (tronc.
      128) -> session.run('input_ids','attention_mask') -> `_mean_pool` ;
      session/tokenizer INJECTÉS ; version OBLIGATOIRE (clé de cache).
  (3) `charger_embedder_onnx(onnx_path, tokenizer_path, version=None)` : CHEMINS
      LOCAUX UNIQUEMENT ; fichiers/libs absents / échec -> None (ne LÈVE JAMAIS).
  (4) `charger_embedder` : env NEXUS_EMBED_ONNX + NEXUS_EMBED_TOKENIZER pointant
      des fichiers EXISTANTS -> backend ONNX (dans CacheEmbeddings) ; SINON défaut.

Tests, avec les MUTATIONS qu'ils virent ROUGES :
  (i)   `_mean_pool` ignore le masque (compte le padding) -> test pooling ROUGE.
  (ii)  `charger_embedder_onnx` lève au lieu de rendre None sur fichier absent
        -> test robustesse ROUGE.
  (iii) `_EmbedderOnnx` omet la version -> test cache-version ROUGE.
  (iv)  `charger_embedder(_onnx)` accepte un repo id au lieu d'un chemin local
        -> test « chemins locaux uniquement » ROUGE (aucune session construite).
  GOLDEN : `charger_embedder()` sans env ONNX ni modèle ST -> None (byte-ident.).
"""
import os
import sys
import types
import importlib

import pytest


# --------------------------------------------------------------------------- #
# Chargement de l'organe (organes/nexus_embedder.py)
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


@pytest.fixture
def nemb():
    return _charger_organe("nexus_embedder")


@pytest.fixture(autouse=True)
def _sans_env_onnx(monkeypatch):
    """Par défaut, AUCUNE config ONNX ne fuit de l'environnement de test : chaque
    test qui veut l'ONNX pose ses propres variables explicitement."""
    monkeypatch.delenv("NEXUS_EMBED_ONNX", raising=False)
    monkeypatch.delenv("NEXUS_EMBED_TOKENIZER", raising=False)


# --------------------------------------------------------------------------- #
# Faux session / tokenizer INJECTÉS (aucun onnxruntime réel requis)
# --------------------------------------------------------------------------- #
class _FauxEncoding:
    def __init__(self, ids, attention_mask):
        self.ids = ids
        self.attention_mask = attention_mask


class _FauxTokenizer:
    """Rend une Encoding canned ; enregistre les textes reçus (spy)."""
    def __init__(self, ids, mask):
        self._enc = _FauxEncoding(ids, mask)
        self.textes = []
        self.tronque_a = None

    def enable_truncation(self, max_length=None):
        self.tronque_a = max_length

    def encode(self, text):
        self.textes.append(text)
        return self._enc


class _FausseSession:
    """Enregistre les noms d'entrée reçus et rend un last_hidden_state canned.
    On lui passe le tenseur (n_tokens, dim) d'UNE séquence ; `run` rajoute la
    dimension de batch -> sortie de forme (1, n_tokens, dim), comme un vrai
    modèle ONNX (output[0] = last_hidden_state)."""
    def __init__(self, last_hidden_state):
        self._lhs = last_hidden_state
        self.feed = None
        self.output_names = "__non_appele__"

    def run(self, output_names, input_feed):
        self.output_names = output_names
        self.feed = input_feed
        return [[self._lhs]]                          # (1, n_tokens, dim)


# =========================================================================== #
# (1) _mean_pool PUR — moyenne pondérée par le masque, padding IGNORÉ
# =========================================================================== #
def test_mean_pool_masque_plein_moyenne_les_deux_tokens(nemb):
    """2 tokens, masque [1,1] -> moyenne des DEUX vecteurs (calcul à la main)."""
    lhs = [[1.0, 2.0, 3.0], [5.0, 6.0, 7.0]]
    assert nemb._mean_pool(lhs, [1, 1]) == [3.0, 4.0, 5.0]     # (1+5)/2, (2+6)/2 …


def test_mean_pool_masque_exclut_le_padding(nemb):
    """MUTATION (i) : `_mean_pool` qui IGNORE le masque (compte le padding) -> ROUGE.
    2 tokens, masque [1,0] : le 2e token est du PADDING -> la moyenne == le SEUL
    1er vecteur, JAMAIS la moyenne des deux."""
    lhs = [[1.0, 2.0, 3.0], [5.0, 6.0, 7.0]]
    assert nemb._mean_pool(lhs, [1, 0]) == [1.0, 2.0, 3.0]     # padding exclu
    # garde-fou anti-mutation : ce n'est SURTOUT pas la moyenne des deux
    assert nemb._mean_pool(lhs, [1, 0]) != [3.0, 4.0, 5.0]


def test_mean_pool_tout_padding_vecteur_nul_sans_division(nemb):
    """Masque tout à zéro : jamais de division par zéro -> vecteur nul de bonne dim."""
    assert nemb._mean_pool([[1.0, 2.0], [3.0, 4.0]], [0, 0]) == [0.0, 0.0]


# =========================================================================== #
# (2) _EmbedderOnnx.embed — bons noms d'entrée, _mean_pool appliqué, dim, version
# =========================================================================== #
def test_embedder_onnx_embed_plomberie_complete(nemb):
    """Avec FAUX session + FAUX tokenizer : embed appelle la session avec les
    entrées 'input_ids' ET 'attention_mask', applique `_mean_pool`, et rend un
    list[float] de la bonne dimension. La version injectée est posée."""
    tok = _FauxTokenizer(ids=[7, 8], mask=[1, 1])
    sess = _FausseSession([[1.0, 2.0], [3.0, 4.0]])           # (1, 2 tokens, dim 2)
    emb = nemb._EmbedderOnnx(sess, tok, version="mpnet-onnx-v2")

    vec = emb.embed("bonjour")

    # la session a bien reçu les DEUX entrées, aux bons noms
    assert set(sess.feed.keys()) == {"input_ids", "attention_mask"}
    # _mean_pool appliqué (masque [1,1] -> moyenne des deux tokens)
    assert vec == [2.0, 3.0]
    assert isinstance(vec, list) and all(isinstance(x, float) for x in vec)
    assert len(vec) == 2                                       # dim du modèle
    assert emb.version == "mpnet-onnx-v2"                      # version posée
    assert tok.textes == ["bonjour"]                          # le texte a été tokenisé


def test_embedder_onnx_troncature_128(nemb):
    """La troncature à 128 tokens est appliquée : au-delà, ids ET masque coupés,
    et le masque passé à `_mean_pool` reste aligné (128 éléments)."""
    ids = list(range(200))
    mask = [1] * 200
    tok = _FauxTokenizer(ids=ids, mask=mask)
    sess = _FausseSession([[float(i)] for i in range(128)])   # dim 1, 128 tokens
    emb = nemb._EmbedderOnnx(sess, tok, version="v")

    emb.embed("texte long")
    envoye = sess.feed["input_ids"]
    envoye = envoye.tolist() if hasattr(envoye, "tolist") else envoye
    assert len(envoye[0]) == 128                              # ids tronqués à 128


def test_embedder_onnx_version_obligatoire_dans_cache(nemb):
    """MUTATION (iii) : `_EmbedderOnnx` qui OMET la version -> ROUGE.
    La version DOIT être posée sur l'embedder ET se retrouver dans la clé du
    cache (sinon deux modèles collisionnent sur le même texte)."""
    tok = _FauxTokenizer(ids=[1], mask=[1])
    sess = _FausseSession([[9.0]])
    emb = nemb._EmbedderOnnx(sess, tok, version="modele-A")

    assert emb.version == "modele-A"                          # version posée
    cache = nemb.CacheEmbeddings(emb)
    cle = cache._cle("un texte")
    assert cle[1] == "modele-A"                               # version DANS la clé
    # un autre modèle (même texte) -> autre clé, jamais de collision
    autre = nemb.CacheEmbeddings(nemb._EmbedderOnnx(sess, tok, version="modele-B"))
    assert cache._cle("un texte") != autre._cle("un texte")
    assert cache._cle("un texte")[0] == autre._cle("un texte")[0]  # même hash texte


# =========================================================================== #
# (3) charger_embedder_onnx — chemins locaux uniquement, ne lève JAMAIS
# =========================================================================== #
def test_charger_onnx_fichier_absent_rend_none_sans_exception(nemb, monkeypatch):
    """MUTATION (ii) : lever (ou retomber sur un chargement) au lieu de rendre
    None sur fichier absent -> ROUGE.
    Fichiers inexistants -> None, JAMAIS d'exception, MÊME libs disponibles (on
    injecte de FAUX onnxruntime/tokenizers pour que le garde-fou « chemins locaux
    uniquement » soit la SEULE chose qui empêche un chargement fantôme)."""
    compteur = {"sessions": 0}
    _injecter_faux_libs(monkeypatch, compteur,
                        _FauxTokenizer([1], [1]), _FausseSession([[0.0]]))
    assert nemb.charger_embedder_onnx("/no/such/model.onnx",
                                      "/no/such/tok.json") is None
    # arguments vides / None : robustesse absolue, toujours None
    assert nemb.charger_embedder_onnx(None, None) is None
    assert nemb.charger_embedder_onnx("", "") is None
    # aucun chargement n'a été tenté sur un chemin inexistant
    assert compteur["sessions"] == 0


def test_charger_onnx_lib_absente_rend_none(nemb, tmp_path, monkeypatch):
    """Fichiers PRÉSENTS mais onnxruntime/tokenizers absents -> None (repli
    lexical), sans exception."""
    onnx = tmp_path / "m.onnx"
    tok = tmp_path / "t.json"
    onnx.write_bytes(b"stub")
    tok.write_text("{}", encoding="utf-8")
    # onnxruntime indisponible : l'import échoue
    monkeypatch.setitem(sys.modules, "onnxruntime", None)
    assert nemb.charger_embedder_onnx(str(onnx), str(tok)) is None


def _injecter_faux_libs(monkeypatch, compteur, tok_obj, sess_obj):
    """Injecte de faux modules onnxruntime + tokenizers dans sys.modules.
    `compteur['sessions']` compte les InferenceSession CONSTRUITES (une
    construction sur un repo id = tentative réseau interdite)."""
    ort = types.ModuleType("onnxruntime")

    class InferenceSession:
        def __init__(self, path, providers=None):
            compteur["sessions"] += 1
            compteur["path"] = path
            compteur["providers"] = providers
            self._s = sess_obj

        def run(self, names, feed):
            return self._s.run(names, feed)

    ort.InferenceSession = InferenceSession

    tkz = types.ModuleType("tokenizers")

    class Tokenizer:
        @staticmethod
        def from_file(path):
            compteur["tok_path"] = path
            return tok_obj

    tkz.Tokenizer = Tokenizer

    monkeypatch.setitem(sys.modules, "onnxruntime", ort)
    monkeypatch.setitem(sys.modules, "tokenizers", tkz)


def test_charger_onnx_succes_construit_embedder_et_version_par_defaut(
        nemb, tmp_path, monkeypatch):
    """Fichiers présents + libs (fausses) présentes -> _EmbedderOnnx fonctionnel,
    session construite avec le CPUExecutionProvider, version par défaut dérivée
    DÉTERMINISTIQUEMENT du nom de fichier onnx."""
    onnx = tmp_path / "all-mpnet-base-v2.quant.onnx"
    tok = tmp_path / "tokenizer.json"
    onnx.write_bytes(b"stub")
    tok.write_text("{}", encoding="utf-8")

    compteur = {"sessions": 0}
    faux_tok = _FauxTokenizer(ids=[3, 4], mask=[1, 1])
    faux_sess = _FausseSession([[2.0, 4.0], [4.0, 8.0]])
    _injecter_faux_libs(monkeypatch, compteur, faux_tok, faux_sess)

    emb = nemb.charger_embedder_onnx(str(onnx), str(tok))
    assert isinstance(emb, nemb._EmbedderOnnx)
    assert compteur["sessions"] == 1
    assert compteur["providers"] == ["CPUExecutionProvider"]
    assert emb.version == "onnx-all-mpnet-base-v2.quant"       # dérivée du nom
    assert faux_tok.tronque_a == 128                           # troncature 128 posée
    assert emb.embed("x") == [3.0, 6.0]                        # pipeline complet


def test_charger_onnx_version_explicite_prime(nemb, tmp_path, monkeypatch):
    """Une version explicite est prioritaire sur la version dérivée du nom."""
    onnx = tmp_path / "m.onnx"
    tok = tmp_path / "t.json"
    onnx.write_bytes(b"stub")
    tok.write_text("{}", encoding="utf-8")
    compteur = {"sessions": 0}
    _injecter_faux_libs(monkeypatch, compteur,
                        _FauxTokenizer([1], [1]), _FausseSession([[0.0]]))
    emb = nemb.charger_embedder_onnx(str(onnx), str(tok), version="perso-42")
    assert emb.version == "perso-42"


def test_charger_onnx_repo_id_refuse_aucune_session_construite(
        nemb, monkeypatch):
    """MUTATION (iv) : accepter un repo id au lieu d'un chemin local -> ROUGE.
    Un repo id HuggingFace (« org/modele ») n'est PAS un fichier local : la
    fabrique rend None et ne construit AUCUNE session (aucune tentative réseau),
    MÊME si onnxruntime/tokenizers sont disponibles."""
    compteur = {"sessions": 0}
    _injecter_faux_libs(monkeypatch, compteur,
                        _FauxTokenizer([1], [1]), _FausseSession([[0.0]]))
    emb = nemb.charger_embedder_onnx("sentence-transformers/all-mpnet-base-v2",
                                     "sentence-transformers/all-mpnet-base-v2")
    assert emb is None
    assert compteur["sessions"] == 0, \
        "un repo id ne doit JAMAIS déclencher la construction d'une session"


# =========================================================================== #
# (4) charger_embedder — opt-in ONNX par env, sinon défaut inchangé
# =========================================================================== #
def test_charger_embedder_optin_onnx_via_env(nemb, tmp_path, monkeypatch):
    """Env NEXUS_EMBED_ONNX + NEXUS_EMBED_TOKENIZER pointant des fichiers
    EXISTANTS -> backend ONNX enveloppé dans CacheEmbeddings."""
    onnx = tmp_path / "mpnet.onnx"
    tok = tmp_path / "tokenizer.json"
    onnx.write_bytes(b"stub")
    tok.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("NEXUS_EMBED_ONNX", str(onnx))
    monkeypatch.setenv("NEXUS_EMBED_TOKENIZER", str(tok))

    compteur = {"sessions": 0}
    faux_sess = _FausseSession([[1.0, 3.0], [3.0, 5.0]])
    _injecter_faux_libs(monkeypatch, compteur,
                        _FauxTokenizer([5, 6], [1, 1]), faux_sess)

    emb = nemb.charger_embedder()
    assert isinstance(emb, nemb.CacheEmbeddings)               # enveloppé dans le cache
    assert isinstance(emb.embedder, nemb._EmbedderOnnx)
    assert emb.version == "onnx-mpnet"                         # version dans la clé
    assert emb.embed("q") == [2.0, 4.0]                        # pipeline via cache


def test_charger_embedder_env_repo_id_ne_declenche_pas_onnx(nemb, monkeypatch):
    """MUTATION (iv, bis) : un repo id dans l'env ne doit PAS entrer dans le
    chemin ONNX (chemins locaux only). Aucune session construite ; on retombe sur
    le défaut (ST absent -> None)."""
    monkeypatch.setenv("NEXUS_EMBED_ONNX", "sentence-transformers/all-mpnet-base-v2")
    monkeypatch.setenv("NEXUS_EMBED_TOKENIZER", "sentence-transformers/all-mpnet-base-v2")
    compteur = {"sessions": 0}
    _injecter_faux_libs(monkeypatch, compteur,
                        _FauxTokenizer([1], [1]), _FausseSession([[0.0]]))
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)

    assert nemb.charger_embedder() is None
    assert compteur["sessions"] == 0                          # aucune tentative réseau


def test_charger_embedder_onnx_indispo_retombe_sur_defaut(nemb, tmp_path,
                                                          monkeypatch):
    """Env ONNX présent mais libs absentes : ne lève pas, retombe sur le chemin
    historique (ST absent ici) -> None -> lexical."""
    onnx = tmp_path / "m.onnx"
    tok = tmp_path / "t.json"
    onnx.write_bytes(b"stub")
    tok.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("NEXUS_EMBED_ONNX", str(onnx))
    monkeypatch.setenv("NEXUS_EMBED_TOKENIZER", str(tok))
    monkeypatch.setitem(sys.modules, "onnxruntime", None)      # ONNX indispo
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)  # ST indispo
    assert nemb.charger_embedder() is None


# =========================================================================== #
# GOLDEN : défaut SANS config ONNX ni modèle ST -> None (byte-identique)
# =========================================================================== #
def test_golden_charger_embedder_sans_onnx_ni_st_rend_none(nemb, monkeypatch):
    """GOLDEN : sans variables d'env ONNX ET sans sentence-transformers, la
    fabrique rend None -> repli LEXICAL PUR. Le défaut reste inchangé (les tests
    historiques restent verts)."""
    # (fixture _sans_env_onnx a déjà retiré les variables d'env)
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    assert nemb.charger_embedder() is None
