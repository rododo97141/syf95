"""Recall SÉMANTIQUE v0.1 — embarquer le TITRE de la fiche (au lieu du texte
complet tronqué) pour l'embedding.

POURQUOI (mesuré le 10/07, vrai embedder local, vraies fiches) :
`_texte_fiche` embarquait le texte COMPLET (`_search`, tronqué → ~128 tokens de
boilerplate → vecteur DILUÉ). Embarquer le TITRE SEUL fait passer les
reformulations synonymes de recall@3 2/10 → 3/10 (r@1 0 → 1) AU RÉGLAGE SÛR
alpha=0.5, contrôle « requêtes précises » INCHANGÉ à 10/10 (zéro régression).

PORTÉE (minimale, localisée à organes/nexus_force.py) :
  (1) helper `_titre_fiche(cand)` : 1re ligne de titre markdown de l'excerpt
      ('#'), '#' retirés, queue « — domaine: … / catégorie: … » COUPÉE ;
      fallbacks déterministes (nom de fichier dé-sluggé, puis _search/excerpt),
      JAMAIS vide, JAMAIS d'exception.
  (2) `_texte_fiche(cand)` retourne désormais le TITRE, pas le texte complet.

INVARIANT CLÉ : `_texte_fiche` n'est appelé QUE sur le chemin embedder → le
défaut lexical (embedder=None) DOIT rester BYTE-IDENTIQUE (golden).

Tests, avec les MUTATIONS qu'ils virent ROUGES :
  (a) plomberie `_titre_fiche` : extraction + coupe de queue, fallback robuste.
        MUTATION (ii) : ne pas couper la queue « — domaine: » → ROUGE.
        MUTATION (iii) : fallback rendant '' au lieu du nom de fichier → ROUGE.
  (b) le chemin sémantique embarque le TITRE, PAS le `_search`.
        MUTATION (i) : `_texte_fiche` revient à `_search` → ROUGE.
  (c) golden : défaut sans embedder strictement inchangé.
"""
import os
import sys
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
    spec = importlib.util.spec_from_file_location("memory_api_titre_test", chemin)
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


class _EmbedderEnregistreur:
    """SPY : enregistre CHAQUE texte reçu par embed() (prouve CE QUI est
    embarqué). Vecteur déterministe quelconque — seule la plomberie compte."""
    def __init__(self):
        self.textes = []

    def embed(self, text):
        self.textes.append(text)
        h = int(hashlib.md5((text or "").encode("utf-8")).hexdigest(), 16)
        return [float((h >> (8 * i)) & 0xFF) for i in range(4)]


# =========================================================================== #
# (a) PLOMBERIE de _titre_fiche : extraction, coupe de queue, fallback robuste
# =========================================================================== #
def test_titre_fiche_extrait_titre_et_coupe_queue_meta(nf):
    """MUTATION (ii) : ne pas couper la queue « — domaine: » → ROUGE.
    L'excerpt d'une fiche a la forme `# <Titre> — domaine: X / catégorie: Y` :
    _titre_fiche renvoie EXACTEMENT le titre, queue de métadonnées coupée."""
    cand = {
        "excerpt": "# Foo bar — domaine: nexus / catégorie: limites\n"
                   "> Créé le 21/06/2026\n\n## En bref\n",
        "file": "foo-bar.md",
        "_search": "# foo bar — domaine: nexus / catégorie: limites ...",
    }
    assert nf._titre_fiche(cand) == "Foo bar"          # queue coupée EXACTEMENT


def test_titre_fiche_fallback_nom_fichier_desslug_jamais_vide(nf):
    """MUTATION (iii) : un fallback qui rend '' au lieu du nom de fichier → ROUGE.
    Sans titre markdown, on retombe sur le nom de fichier dé-sluggé
    (tirets → espaces, sans .md) — JAMAIS une chaîne vide."""
    # Aucune ligne '#' dans l'excerpt → fallback nom de fichier dé-sluggé.
    sans_titre = {"excerpt": "pas de titre markdown ici\nseulement du texte",
                  "file": "mes-5-limites-honnetes.md", "_search": "peu importe"}
    assert nf._titre_fiche(sans_titre) == "mes 5 limites honnetes"

    # Même sans excerpt du tout : jamais vide tant qu'il reste un nom de fichier.
    vide = {"excerpt": "", "file": "france-groupe-i-j1.md", "_search": ""}
    assert nf._titre_fiche(vide) == "france groupe i j1"
    assert nf._titre_fiche(vide) != ""

    # Titre présent mais VIDE après coupe → fallback nom de fichier (jamais vide).
    titre_vide = {"excerpt": "# — domaine: x / catégorie: y\n",
                  "file": "ma-fiche.md", "_search": "s"}
    assert nf._titre_fiche(titre_vide) == "ma fiche"

    # Robustesse absolue : ni titre, ni fichier → jamais d'exception, jamais vide.
    assert nf._titre_fiche({"excerpt": "", "file": "", "_search": "reste"}) == "reste"


# =========================================================================== #
# (b) Le chemin SÉMANTIQUE embarque le TITRE, PAS le texte complet (_search)
# =========================================================================== #
def test_semantique_embarque_le_titre_pas_le_search(nf, mem):
    """MUTATION (i) : `_texte_fiche` revient à `_search` → ROUGE.
    Avec un embedder SPY qui enregistre les textes reçus, le texte embarqué pour
    une fiche == son TITRE, PAS son `_search` (texte complet dilué)."""
    contenu = ("# Guide de reformulation — domaine: dom / catégorie: cat\n"
               "> Créé le 21/06/2026\n\n## En bref\n"
               "beaucoup de boilerplate et de texte long qui dilue le vecteur\n")
    _fiche(mem, "dom", "cat", "cible", contenu)
    cands = mem._scan(mem.STRUCT, "reformulation", "structure")
    assert len(cands) == 1
    cand = cands[0]

    titre = "Guide de reformulation"
    assert nf._titre_fiche(cand) == titre               # ancrage plomberie
    assert "boilerplate" in cand["_search"]             # le _search PORTE le bruit

    spy = _EmbedderEnregistreur()
    nf.rank("reformuler une interrogation", cands, embedder=spy)

    # Le TITRE a bien été embarqué...
    assert titre in spy.textes
    # ...et JAMAIS le texte complet (_search), justement ce qu'on veut éviter.
    assert cand["_search"] not in spy.textes


# =========================================================================== #
# (c) GOLDEN : le défaut lexical (embedder=None) reste BYTE-IDENTIQUE
# =========================================================================== #
def test_golden_defaut_sans_embedder_byte_identique(nf, mem):
    """INVARIANT : `_texte_fiche` n'est utilisé QUE sur le chemin embedder ; le
    défaut lexical (embedder=None) reste STRICTEMENT identique à
    memory_api.rank_candidates (ordre, scores, clés) — zéro régression."""
    _fiche(mem, "dom", "cat", "a",
           "# Alpha — domaine: dom / catégorie: cat\nalpha beta gamma projet")
    _fiche(mem, "dom", "cat", "b",
           "# Beta — domaine: dom / catégorie: cat\nbeta gamma delta projet")
    _fiche(mem, "dom", "cat", "c",
           "# Gamma — domaine: dom / catégorie: cat\ngamma delta projet unique")
    query = "beta gamma"
    cands = mem._scan(mem.STRUCT, query.lower(), "structure")
    forces = {"a": 3.0, "b": 0.5}

    # Régime NOMINAL de la porte à seuil : la force pèse, sortie byte-identique.
    comptes = {"a": nf.SEUIL_FORCE_SLUG, "b": nf.SEUIL_FORCE_SLUG,
               "_total": nf.SEUIL_FORCE_GLOBAL}
    attendu = mem.rank_candidates(query, cands, forces=forces)
    obtenu = nf.rank(query, cands, forces=forces, comptes_force=comptes)  # embedder=None

    assert [r["file"] for r in obtenu] == [r["file"] for r in attendu]  # ordre
    for a, b in zip(attendu, obtenu):
        assert b["_score"] == a["_score"]
        assert b["_relevance"] == a["_relevance"]
        assert b["_force"] == a["_force"]
        assert b["_score"] == a["_relevance"] * a["_force"]   # bien × et pas +
    # aucune clé du chemin sémantique ne fuit dans le défaut lexical
    assert "_sem" not in obtenu[0] and "_pert" not in obtenu[0]
