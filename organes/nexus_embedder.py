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

Usage :
    from nexus_embedder import charger_embedder
    emb = charger_embedder()          # embedder local, ou None (repli lexical)
    if emb is not None:
        recall(params, embedder=emb)  # mode sémantique opt-in
"""
import hashlib

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


def charger_embedder(nom=None, avec_cache=True):
    """FABRIQUE l'embedder local injectable, ou renvoie `None`.

    `None` <=> aucun modèle local disponible <=> côté recall, FALLBACK LEXICAL PUR
    (jamais de repli n-grammes : ce module ne fabrique PAS de pseudo-sémantique).

    Ne lève JAMAIS : toute défaillance (import, poids absents, chargement) devient
    un `None` propre. Le sémantique est un BONUS opt-in ; son absence ne casse
    rien, elle rend simplement le recall lexical (le défaut historique)."""
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
