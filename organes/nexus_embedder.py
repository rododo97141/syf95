#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEXUS — Fabrique d'embedder LOCAL injecté (recall sémantique v0).

« Le sens vient d'un modèle LOCAL, injecté comme le client LLM — jamais embarqué
dans l'organe, jamais un appel réseau de notre part. »

Cet organe NE contient AUCUN modèle neuronal et ne fait AUCUN appel réseau. Il
FABRIQUE un embedder : si un modèle de phrases LOCAL est présent dans
l'environnement (sentence-transformers, poids déjà sur disque), `charger_embedder`
renvoie un embedder prêt à injecter dans `nexus_force.rank(..., embedder=...)`.

L'invariant NEXUS « réseau JAMAIS dans l'organe » est APPLIQUÉ, pas seulement
affirmé : le chargement passe `local_files_only=True`. Un modèle absent en local
LÈVE (jamais un téléchargement HuggingFace furtif) -> attrapé -> None -> repli
lexical. Impossible, même bibliothèque installée sans cache, qu'un premier recall
sémantique déclenche un appel réseau.

SINON — bibliothèque absente, poids introuvables, chargement en échec — il renvoie
`None`. `None` veut dire UNE seule chose côté recall : FALLBACK = LEXICAL PUR.

    JAMAIS un pseudo-sémantique à base de n-grammes de caractères. Un tel repli
    aurait l'AIR de marcher (il rendrait un vecteur, un cosinus non nul) tout en
    dégradant le SENS en silence : « voiture » et « automobile » resteraient
    étrangers, et l'utilisateur croirait pourtant tenir du sémantique. Mieux vaut
    un lexical honnête et prévisible qu'un sémantique de façade. L'EmbedderFake
    n-grammes existe UNIQUEMENT dans nexus_force pour la PLOMBERIE des tests ; il
    n'a rien à faire ici.

Contrat d'un embedder injectable : une méthode `embed(text) -> list[float]` et un
attribut `version` (str) qui identifie le modèle. La `version` entre dans la CLÉ
du cache d'embeddings — deux modèles différents ne partagent jamais un vecteur.

Backend ONNX LOCAL (recall sémantique v0.2) — OPT-IN par variables d'env :
un modèle 768d quantifié en ONNX capte le gain sémantique pour un poids ≈ MiniLM.
Si `NEXUS_EMBED_ONNX` et `NEXUS_EMBED_TOKENIZER` pointent des FICHIERS LOCAUX
existants, `charger_embedder` fabrique un embedder à partir d'eux
(`onnxruntime.InferenceSession` + `tokenizers.Tokenizer.from_file`) — CHEMINS
LOCAUX UNIQUEMENT, jamais un repo id HuggingFace, jamais de download : le réseau
est impossible PAR CONSTRUCTION, cohérent avec `local_files_only=True`. SANS ces
variables (le DÉFAUT), rien ne change : sentence-transformers local, ou None ->
lexical BYTE-IDENTIQUE.

Usage :
    from nexus_embedder import charger_embedder
    emb = charger_embedder()          # embedder local, ou None (repli lexical)
    if emb is not None:
        recall(params, embedder=emb)  # mode sémantique opt-in
"""
import hashlib
import os

# Modèle de phrases LOCAL par défaut. Léger, multilingue de base. PROVISOIRE : le
# choix du modèle (et donc la qualité sémantique) reste à calibrer sur le banc
# synonymes (cf. le xfail voiture~automobile). Ce module ne le télécharge JAMAIS :
# il ne charge que ce qui est DÉJÀ présent localement.
MODELE_DEFAUT = "sentence-transformers/all-MiniLM-L6-v2"


def _version_modele(nom):
    """Identifiant de version du modèle = nom + version de la bibliothèque. Entre
    dans la clé du cache : un changement de modèle OU de bibliothèque invalide
    proprement les vecteurs mis en cache (jamais de vecteur d'un autre modèle
    servi pour un texte identique)."""
    try:
        import sentence_transformers as _st
        lib = getattr(_st, "__version__", "inconnue")
    except Exception:
        lib = "inconnue"
    return "%s@st-%s" % (nom, lib)


class CacheEmbeddings:
    """Cache d'embeddings TRANSPARENT enveloppant un embedder pur (déterministe).

    CLÉ = (hash_texte, VERSION_du_modèle). Deux conséquences voulues :
      • le contenu d'une fiche change  -> le hash change -> RECALCUL (invalidation
        automatique, aucune purge à gérer) ;
      • le modèle (ou sa version) change -> la version change -> RECALCUL (jamais
        un vecteur périmé d'un autre modèle servi pour le même texte).

    TRANSPARENT au résultat : l'embedder enveloppé étant PUR, un cache FROID rend
    exactement le même vecteur qu'un cache CHAUD (golden). Le cache n'accélère,
    il ne modifie rien.
    """

    def __init__(self, embedder, version=None):
        self.embedder = embedder
        # La version est OBLIGATOIRE dans la clé : à défaut sur l'embedder, on
        # prend une sentinelle explicite plutôt que de l'omettre (omettre la
        # version ferait collisionner deux modèles — cf. les tests de mutation).
        self.version = version or getattr(embedder, "version", None) or "inconnue"
        self._store = {}

    def _cle(self, text):
        """(hash_texte, version). La VERSION fait PARTIE de la clé — la retirer
        ferait servir le vecteur d'un modèle pour un autre : mutation rouge."""
        h = hashlib.sha256((text or "").encode("utf-8")).hexdigest()
        return (h, self.version)

    def embed(self, text):
        cle = self._cle(text)
        if cle in self._store:
            return self._store[cle]
        vec = self.embedder.embed(text)
        self._store[cle] = vec
        return vec


class _EmbedderLocal:
    """Adaptateur d'un modèle de phrases sentence-transformers vers le contrat
    d'embedder (`embed`, `version`). Aucun réseau : le modèle est déjà chargé."""

    def __init__(self, modele, version):
        self._modele = modele
        self.version = version

    def embed(self, text):
        vec = self._modele.encode(text or "", normalize_embeddings=False)
        return [float(x) for x in vec]


# --------------------------------------------------------------------------- #
# Backend ONNX LOCAL (v0.2) — mean pooling PUR + adaptateur injecté + fabrique
# --------------------------------------------------------------------------- #
def _mean_pool(last_hidden_state, attention_mask):
    """Moyenne des vecteurs de tokens PONDÉRÉE par le masque d'attention — le
    padding (masque 0) est IGNORÉ. Fonction PURE écrite en Python pur (listes
    imbriquées), SANS aucune dépendance numpy/onnx : elle est donc testable sans
    rien installer.

    `last_hidden_state` : list[list[float]] de forme (n_tokens, dim) — les
    vecteurs cachés du DERNIER étage pour UNE séquence (dimension de batch déjà
    retirée). `attention_mask` : list de 0/1 de longueur n_tokens.

    Renvoie list[float] de longueur `dim` : somme(masque_t * vecteur_t) / somme
    des masques. Le masque EXCLUT le padding — le compter (mutation) déplacerait
    la moyenne vers le vecteur de padding et fausserait le sens."""
    if not last_hidden_state:
        return []
    dim = len(last_hidden_state[0])
    somme = [0.0] * dim
    poids = 0.0
    for vecteur, m in zip(last_hidden_state, attention_mask):
        w = float(m)
        if w == 0.0:
            continue                       # padding IGNORÉ (le masque l'exclut)
        poids += w
        for i in range(dim):
            somme[i] += w * float(vecteur[i])
    if poids == 0.0:
        return [0.0] * dim                 # tout est padding : vecteur nul, jamais /0
    return [s / poids for s in somme]


def _en_listes(x):
    """Rend un objet (tableau numpy ou déjà une liste) sous forme de listes
    imbriquées Python, pour que `_mean_pool` reste PUR. Aucune dépendance dure à
    numpy : on n'utilise `.tolist()` que s'il existe."""
    if hasattr(x, "tolist"):
        return x.tolist()
    return x


def _lot_entier(ids):
    """Construit l'entrée d'un modèle ONNX à partir d'une liste d'ids : un lot de
    taille 1, forme (1, n_tokens). Utilise numpy (int64) s'il est présent — le
    vrai chemin onnxruntime l'amène toujours ; à défaut (tests avec faux
    session), une liste imbriquée suffit, la fausse session s'en accommode."""
    try:
        import numpy as _np
        return _np.array([list(ids)], dtype=_np.int64)
    except Exception:
        return [list(ids)]


class _EmbedderOnnx:
    """Adaptateur d'un modèle ONNX + tokenizer vers le contrat d'embedder
    (`embed`, `version`). `session` et `tokenizer` sont INJECTÉS : l'organe est
    testable avec des faux, sans onnxruntime réel. `version` est OBLIGATOIRE —
    elle entre dans la clé du cache (deux modèles ne partagent jamais un vecteur).

    embed = tokenise (troncature 128) -> session.run avec les entrées 'input_ids'
    et 'attention_mask' -> `_mean_pool` sur le dernier état caché. Aucun réseau :
    la session et le tokenizer sont déjà chargés depuis des fichiers locaux."""

    def __init__(self, session, tokenizer, version):
        self._session = session
        self._tokenizer = tokenizer
        # OBLIGATOIRE : pas de défaut silencieux. Omettre la version ferait
        # collisionner deux modèles dans le cache (mutation cache-version rouge).
        self.version = version

    def embed(self, text):
        enc = self._tokenizer.encode(text or "")
        ids = list(enc.ids)[:128]                     # TRONCATURE 128
        mask = list(enc.attention_mask)[:128]         # masque aligné sur les ids
        entrees = {
            "input_ids": _lot_entier(ids),
            "attention_mask": _lot_entier(mask),
        }
        sorties = self._session.run(None, entrees)    # None -> toutes les sorties
        # sorties[0] = last_hidden_state, forme (1, n_tokens, dim) -> [0] enlève
        # le batch. _mean_pool est PUR : on passe des listes imbriquées.
        last_hidden_state = _en_listes(sorties[0])[0]
        return _mean_pool(last_hidden_state, mask)


def _version_onnx(onnx_path):
    """Version par défaut DÉTERMINISTE dérivée du NOM DE FICHIER onnx (jamais un
    horodatage, jamais un hash de contenu) : le même fichier donne toujours la
    même version, donc la même clé de cache."""
    base = os.path.basename(onnx_path or "")
    if base.endswith(".onnx"):
        base = base[:-len(".onnx")]
    return "onnx-%s" % (base or "modele")


def _fichier_local(chemin):
    """True SEULEMENT si `chemin` désigne un FICHIER existant sur disque. Ne lève
    jamais (entrée None/vide/exotique -> False). C'est le garde-fou « chemins
    locaux uniquement » : un repo id HuggingFace (« org/modele ») n'est pas un
    fichier -> False -> aucune tentative de chargement (donc aucun réseau)."""
    try:
        return bool(chemin) and os.path.isfile(chemin)
    except Exception:
        return False


def charger_embedder_onnx(onnx_path, tokenizer_path, version=None):
    """FABRIQUE un embedder à partir d'un modèle ONNX + tokenizer LOCAUX, ou None.

    CHEMINS LOCAUX UNIQUEMENT : `onnx_path` et `tokenizer_path` doivent être des
    FICHIERS existant sur disque. Jamais un repo id HuggingFace, jamais de
    download — le réseau est impossible PAR CONSTRUCTION. Un repo id (« org/mod »)
    n'est pas un fichier -> None (garde-fou « chemins locaux uniquement »).

    Ne LÈVE JAMAIS : fichiers absents, bibliothèques absentes (onnxruntime /
    tokenizers), ou échec de chargement -> None -> repli lexical. `version` par
    défaut est dérivée du nom de fichier onnx (déterministe)."""
    # Garde-fou « chemins locaux uniquement » — HORS try/except pour qu'une
    # régression (renvoyer autre chose que None, ou lever) soit visible aux tests.
    if not _fichier_local(onnx_path) or not _fichier_local(tokenizer_path):
        return None                        # fichier absent / repo id -> None
    try:
        import onnxruntime
        from tokenizers import Tokenizer
    except Exception:
        return None                        # libs absentes -> None (jamais lève)
    try:
        session = onnxruntime.InferenceSession(
            onnx_path, providers=["CPUExecutionProvider"])
        tokenizer = Tokenizer.from_file(tokenizer_path)
    except Exception:
        return None                        # chargement en échec -> None
    try:
        tokenizer.enable_truncation(max_length=128)   # troncature 128 (au cas où)
    except Exception:
        pass
    return _EmbedderOnnx(session, tokenizer, version or _version_onnx(onnx_path))


def charger_embedder(nom=None, avec_cache=True):
    """FABRIQUE l'embedder local injectable, ou renvoie `None`.

    `None` <=> aucun modèle local disponible <=> côté recall, FALLBACK LEXICAL PUR
    (jamais de repli n-grammes : ce module ne fabrique PAS de pseudo-sémantique).

    Ne lève JAMAIS : toute défaillance (import, poids absents, chargement) devient
    un `None` propre. Le sémantique est un BONUS opt-in ; son absence ne casse
    rien, elle rend simplement le recall lexical (le défaut historique).

    OPT-IN ONNX : si `NEXUS_EMBED_ONNX` et `NEXUS_EMBED_TOKENIZER` pointent des
    FICHIERS existants, on tente le backend ONNX LOCAL (enveloppé dans
    CacheEmbeddings). SINON — pas de config ONNX, ou échec — comportement ACTUEL
    (sentence-transformers, local_files_only=True). SINON None. Le défaut SANS
    config ONNX ni modèle ST reste BYTE-IDENTIQUE (None -> lexical)."""
    onnx_path = os.environ.get("NEXUS_EMBED_ONNX")
    tok_path = os.environ.get("NEXUS_EMBED_TOKENIZER")
    if (onnx_path and tok_path
            and os.path.isfile(onnx_path) and os.path.isfile(tok_path)):
        emb = charger_embedder_onnx(onnx_path, tok_path)
        if emb is not None:
            return CacheEmbeddings(emb) if avec_cache else emb
        # ONNX configuré mais indisponible (libs absentes) : on ne lève pas, on
        # RETOMBE sur le chemin historique ci-dessous (puis None -> lexical).
    nom = nom or MODELE_DEFAUT
    try:
        from sentence_transformers import SentenceTransformer
    except Exception:
        return None  # bibliothèque absente -> LEXICAL PUR (jamais n-grammes)
    try:
        # local_files_only=True APPLIQUE l'invariant « réseau jamais dans l'organe » :
        # un modèle ABSENT localement LÈVE (pas de repli sur un téléchargement
        # HuggingFace) -> attrapé ici -> None -> repli lexical. Le réseau ne peut
        # PAS s'inviter dans le chemin de chargement, même lib installée sans cache.
        modele = SentenceTransformer(nom, local_files_only=True)
    except Exception:
        return None  # poids absents en local / chargement en échec -> LEXICAL PUR
    emb = _EmbedderLocal(modele, _version_modele(nom))
    return CacheEmbeddings(emb) if avec_cache else emb
