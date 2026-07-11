"""Dédup SÉMANTIQUE (proposition, JAMAIS de fusion) — nexus_consolidate.

CONTEXTE (mesuré le 10/07 sur 146 fiches réelles) : le dédup LEXICAL (Jaccard des
mots) rate de vrais quasi-doublons SÉMANTIQUES dont les mots diffèrent (résumés
auto-decouverte-* cos 0,92-0,98 ; resume-session vs session-complete cos 0,93 mais
Jaccard 0,16). On ajoute un SIGNAL SÉMANTIQUE OPT-IN qui PROPOSE EN PLUS les paires
que le lexical rate — sans JAMAIS fusionner (« un doublon est toujours confirmé par
l'humain »).

Ce que ces tests VERROUILLENT (et les MUTATIONS qu'ils virent ROUGES) :
  (a) `paires_candidates` SANS embedder = lexical pur, BYTE-IDENTIQUE à l'ancien
      signal (paires Jaccard attendues, types tous « lexical »).
  (b) avec embedder MOCK déterministe :
        • une paire Jaccard < seuil_lex mais cos >= seuil_sem est PROPOSÉE et
          MARQUÉE « proche par le sens »  → MUTATION (i) paire non marquée ROUGE ;
        • une paire sous les DEUX seuils n'est PAS proposée ;
        • une paire déjà lexicale (Jaccard >= seuil_lex) n'est PAS re-proposée en
          sémantique  → MUTATION (ii) double comptage ROUGE.
  (c) HONNÊTETÉ : embedder None -> AUCUNE paire sémantique, jamais un faux score
        → MUTATION (iii) embedder None rapporté comme sémantique ROUGE.
  (d) DRY-RUN STRICT : l'organe n'écrit / ne fusionne RIEN
        → MUTATION (iv) l'organe écrit au lieu de proposer ROUGE.
"""
import os
import sys
import importlib

import pytest


# --------------------------------------------------------------------------- #
# Chargement du module organe (organes/nexus_consolidate.py)
# --------------------------------------------------------------------------- #
def _racine():
    ici = os.path.dirname(os.path.abspath(__file__))          # backend/tests
    return os.path.dirname(os.path.dirname(ici))              # racine du dépôt


@pytest.fixture
def nc():
    org = os.path.join(_racine(), "organes")
    if org not in sys.path:
        sys.path.insert(0, org)
    import nexus_consolidate
    return importlib.reload(nexus_consolidate)


# --------------------------------------------------------------------------- #
# Embedder MOCK déterministe : mappe un mot-clé de titre -> vecteur fixe. Aucun
# réseau, aucun modèle : le test contrôle EXACTEMENT chaque cosinus.
# --------------------------------------------------------------------------- #
class EmbedderMock:
    TABLE = {
        "alpha":  [1.0, 0.0, 0.0],
        "alpha'": [0.9, 0.2, 0.1],   # cos ≈ 0.97 avec « alpha » (>= 0.80)
        "beta":   [0.0, 1.0, 0.0],
        "gamma":  [0.0, 0.0, 1.0],   # cos(beta, gamma) = 0 (< 0.80)
    }

    def embed(self, text):
        return list(self.TABLE.get((text or "").strip(), [0.0, 0.0, 0.0]))


def _fiche(file, mots_iter, vecteur=None):
    d = {"file": file, "mots": set(mots_iter)}
    if vecteur is not None:
        d["vecteur"] = vecteur
    return d


# =========================================================================== #
# (a) SANS embedder = lexical pur, byte-identique
# =========================================================================== #
def test_cosinus_pur_borne_et_robuste(nc):
    """Cosinus PUR borné [0,1] ; dimensions incompatibles ou vecteur nul -> 0.0
    (jamais d'exception : le sémantique ne doit jamais casser le lexical)."""
    assert nc.cosinus([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert nc.cosinus([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert nc.cosinus([1.0, 0.0, 0.0], [1.0, 0.0]) == 0.0   # dims différentes
    assert nc.cosinus([0.0, 0.0], [1.0, 0.0]) == 0.0        # norme nulle
    assert nc.cosinus([], [1.0]) == 0.0                     # vide


def test_paires_sans_embedder_lexical_pur(nc):
    """paires_candidates(embedder=None) = SEULEMENT du lexical Jaccard >= seuil,
    byte-identique à l'ancien signal. Reproduit l'ancien algorithme et compare."""
    fiches = [
        _fiche("a.md", {"budget", "calcul", "montant", "total"}),
        _fiche("b.md", {"budget", "calcul", "montant", "cout"}),   # jac(a,b)=3/5=0.6
        _fiche("c.md", {"rouge", "vert", "bleu"}),                 # jac vs a,b = 0
    ]
    # Oracle indépendant : l'ANCIEN algorithme (Jaccard >= SEUIL, itertools.combinations).
    import itertools
    attendu = []
    for fa, fb in itertools.combinations(fiches, 2):
        s = nc.jaccard(fa["mots"], fb["mots"])
        if s >= nc.SEUIL:
            attendu.append((round(s, 2), "lexical", fa["file"], fb["file"]))

    obtenu = [(sc, ty, fa["file"], fb["file"])
              for sc, ty, fa, fb in nc.paires_candidates(fiches, embedder=None)]

    assert obtenu == attendu
    assert obtenu == [(0.6, "lexical", "a.md", "b.md")]
    assert all(ty == "lexical" for _, ty, _, _ in obtenu)


def test_paires_sans_embedder_ignore_vecteurs(nc):
    """Byte-identique : même si les fiches PORTENT des vecteurs proches, sans
    embedder (None) AUCUN sémantique n'est produit — sortie lexicale intacte."""
    fiches = [
        _fiche("x.md", {"decouverte", "auto"}, vecteur=[1.0, 0.0, 0.0]),
        _fiche("y.md", {"session", "complete"}, vecteur=[0.9, 0.2, 0.1]),  # cos élevé
    ]
    assert nc.paires_candidates(fiches, embedder=None) == []


# =========================================================================== #
# (b) avec embedder MOCK : sémantique proposé, marqué, sans double comptage
# =========================================================================== #
def test_paire_semantique_proposee_et_marquee(nc):
    """Jaccard < seuil_lex MAIS cos >= seuil_sem -> PROPOSÉE, type « semantique »,
    et son libellé porte « proche par le sens ». MUTATION (i) non-marquée ROUGE."""
    emb = EmbedderMock()
    fa = _fiche("auto-decouverte-1.md", {"decouverte", "essai"}, emb.embed("alpha"))
    fb = _fiche("resume-session-3.md", {"session", "complete"}, emb.embed("alpha'"))
    # sanity : le lexical RATE bien cette paire, le sémantique la voit.
    assert nc.jaccard(fa["mots"], fb["mots"]) < nc.SEUIL
    assert nc.cosinus(fa["vecteur"], fb["vecteur"]) >= nc.SEUIL_SEM

    paires = nc.paires_candidates([fa, fb], embedder=emb)
    assert len(paires) == 1
    score, type_, pa, pb = paires[0]
    assert type_ == "semantique"
    assert score >= nc.SEUIL_SEM
    # MARQUAGE explicite « proche par le sens » (mutation (i) : libellé nu -> ROUGE).
    assert "proche par le sens" in nc.libelle(score, type_)


def test_paire_sous_les_deux_seuils_non_proposee(nc):
    """Jaccard < seuil_lex ET cos < seuil_sem -> RIEN (ni lexical ni sémantique)."""
    emb = EmbedderMock()
    fa = _fiche("f1.md", {"rouge", "vert"}, emb.embed("beta"))
    fb = _fiche("f2.md", {"bleu", "jaune"}, emb.embed("gamma"))
    assert nc.jaccard(fa["mots"], fb["mots"]) < nc.SEUIL
    assert nc.cosinus(fa["vecteur"], fb["vecteur"]) < nc.SEUIL_SEM
    assert nc.paires_candidates([fa, fb], embedder=emb) == []


def test_paire_lexicale_pas_de_double_comptage(nc):
    """Jaccard >= seuil_lex -> proposée UNE fois (lexical). Même si son cos est
    >= seuil_sem, elle n'est PAS re-proposée en sémantique. MUTATION (ii) ROUGE."""
    emb = EmbedderMock()
    fa = _fiche("d1.md", {"budget", "calcul", "montant", "total"}, emb.embed("alpha"))
    fb = _fiche("d2.md", {"budget", "calcul", "montant", "cout"}, emb.embed("alpha'"))
    # La paire est lexicale ET son cos dépasse le seuil sémantique : piège à double comptage.
    assert nc.jaccard(fa["mots"], fb["mots"]) >= nc.SEUIL
    assert nc.cosinus(fa["vecteur"], fb["vecteur"]) >= nc.SEUIL_SEM

    paires = nc.paires_candidates([fa, fb], embedder=emb)
    assert len(paires) == 1
    assert paires[0][1] == "lexical"
    assert not any(ty == "semantique" for _, ty, _, _ in paires)


def test_libelle_lexical_reste_pourcentage(nc):
    """Une paire lexicale garde le pourcentage historique (pas de faux « sens »)."""
    assert nc.libelle(0.6, "lexical") == "60%"
    assert "proche par le sens" not in nc.libelle(0.6, "lexical")


# =========================================================================== #
# (c) HONNÊTETÉ : embedder None -> aucune paire sémantique
# =========================================================================== #
def test_embedder_none_aucune_paire_semantique(nc):
    """Même sur une paire qui SERAIT sémantique (jac < seuil, cos >= seuil), un
    embedder None ne produit AUCUN sémantique. MUTATION (iii) ROUGE."""
    emb = EmbedderMock()
    fa = _fiche("a.md", {"decouverte", "essai"}, emb.embed("alpha"))
    fb = _fiche("b.md", {"session", "complete"}, emb.embed("alpha'"))
    # avec embedder -> sémantique ; sans -> rien.
    assert any(ty == "semantique"
               for _, ty, _, _ in nc.paires_candidates([fa, fb], embedder=emb))
    assert nc.paires_candidates([fa, fb], embedder=None) == []


def test_main_annonce_semantique_indisponible(nc, monkeypatch, capsys):
    """main() sans embedder local ANNONCE « semantique indisponible » (honnêteté),
    et garde le signal lexical. Jamais un faux score."""
    monkeypatch.setattr(nc, "_charger_embedder", lambda: None)
    monkeypatch.setattr(nc, "get", _fake_get_deux_fiches)
    nc.main()
    out = capsys.readouterr().out.lower()
    assert "semantique indisponible" in out


# =========================================================================== #
# (d) DRY-RUN STRICT : aucune écriture, aucune fusion — l'organe PROPOSE seulement
# =========================================================================== #
def _fake_get_deux_fiches(path):
    """Fausse API mémoire : un domaine, une catégorie, deux fiches quasi-doublons
    par le sens (mots différents). Aucun réseau réel."""
    if path.startswith("/domains"):
        return {"domains": {"tech": ["notes"]}}
    if path.startswith("/recall"):
        return {"results": [
            {"file": "auto-decouverte-1.md",
             "excerpt": "# Auto découverte un\nrésumé essai\n"},
            {"file": "resume-session-3.md",
             "excerpt": "# Résumé session trois\nbilan complet\n"},
        ]}
    return {}


def _open_lecture_seule(monkeypatch):
    """Remplace builtins.open : toute ouverture en ÉCRITURE (w/a/x/+) LÈVE. La
    lecture (imports, fixtures) reste permise. Rend visible toute écriture disque."""
    import builtins
    vrai_open = builtins.open

    def open_garde(file, mode="r", *a, **k):
        if any(c in mode for c in ("w", "a", "x", "+")):
            raise AssertionError(f"ÉCRITURE INTERDITE (DRY-RUN) : open({file!r}, {mode!r})")
        return vrai_open(file, mode, *a, **k)

    monkeypatch.setattr(builtins, "open", open_garde)


def test_dry_run_aucune_ecriture_sans_embedder(nc, monkeypatch, capsys):
    """main() (embedder None) ne fait AUCUNE écriture disque. MUTATION (iv) ROUGE."""
    monkeypatch.setattr(nc, "_charger_embedder", lambda: None)
    monkeypatch.setattr(nc, "get", _fake_get_deux_fiches)
    _open_lecture_seule(monkeypatch)
    nc.main()  # ne doit RIEN écrire (sinon AssertionError du garde open)
    out = capsys.readouterr().out
    assert "Aucune fusion appliquee" in out or "Aucune redondance" in out


def test_dry_run_aucune_ecriture_avec_embedder(nc, monkeypatch, capsys):
    """main() AVEC embedder (passe sémantique active) ne fusionne / n'écrit RIEN.
    Les deux fiches sont proches par le sens -> proposées, jamais fusionnées."""
    emb = EmbedderMock()

    # Les deux titres embarqués mappent vers des vecteurs à cos élevé.
    def faux_titre(f):
        return "alpha" if "decouverte" in f.get("file", "") else "alpha'"

    monkeypatch.setattr(nc, "_charger_embedder", lambda: emb)
    monkeypatch.setattr(nc, "_titre_fiche", faux_titre)
    monkeypatch.setattr(nc, "get", _fake_get_deux_fiches)
    _open_lecture_seule(monkeypatch)
    nc.main()  # passe sémantique + DRY-RUN : aucune écriture
    out = capsys.readouterr().out
    # La proposition sémantique apparaît, marquée, et rien n'est fusionné.
    assert "proche par le sens" in out.lower()
    assert "Aucune fusion appliquee" in out


def test_paires_candidates_ne_modifie_pas_les_fiches(nc):
    """PURETÉ : paires_candidates ne mute pas ses entrées (propose, ne touche rien)."""
    emb = EmbedderMock()
    fa = _fiche("a.md", {"x", "y"}, emb.embed("alpha"))
    fb = _fiche("b.md", {"z", "w"}, emb.embed("alpha'"))
    avant = (dict(fa), set(fa["mots"]), list(fa["vecteur"]),
             dict(fb), set(fb["mots"]), list(fb["vecteur"]))
    nc.paires_candidates([fa, fb], embedder=emb)
    assert fa["mots"] == avant[1] and fa["vecteur"] == avant[2]
    assert fb["mots"] == avant[4] and fb["vecteur"] == avant[5]
