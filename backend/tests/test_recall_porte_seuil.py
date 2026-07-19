"""PORTE À SEUIL doctrinale de la force — nexus_force (compter_events_force + rank).

Doctrine : la force d'une fiche n'influence rank() QUE si le SIGNAL RÉEL jugé est
suffisant. Sinon la force est NEUTRE — ni bonus, ni pénalité : elle ne peut NI
monter NI descendre la fiche. Auto-levante (aucun flag, aucun état, aucune
migration) : la porte s'ouvre d'elle-même quand deux seuils sont atteints —

  • SEUIL_FORCE_GLOBAL : total d'événements de force jugés (toutes fiches) ;
  • SEUIL_FORCE_SLUG   : événements jugés pour LA fiche.

Couvre, point par point :
  1. compter_events_force : filtre EXACT de calculer_forces (fiche non vide ET
     statut ∈ {succes, echec}), repli LEGACY statut_juge→statut (comme le garde
     98), 'ok'/'partiel' ignorés, {_total} exact, lecture seule / non-mutant.
  2. RÉGIME NOMINAL (deux seuils atteints) : sortie BYTE-IDENTIQUE à l'historique
     — légataire (× force) ET additif (+ beta·f(force)).
  3. SOUS SEUIL : force NEUTRE — légataire force_eff = 1.0 ; additif f(force) = 0
     (beta·f = 0). Order & scores IDENTIQUES à un monde SANS force.
  4. Les DEUX seuils, indépendamment : la porte GLOBALE (via _total) et la porte
     par fiche (SLUG) ferment chacune, isolément.
  5. Injection : les comptes sont calculés UNE FOIS par appel et injectables.
"""
import os
import sys
import importlib

import pytest


def _racine():
    ici = os.path.dirname(os.path.abspath(__file__))          # backend/tests
    return os.path.dirname(os.path.dirname(ici))              # racine du dépôt


@pytest.fixture
def nf():
    org = os.path.join(_racine(), "organes")
    if org not in sys.path:
        sys.path.insert(0, org)
    import nexus_force
    return importlib.reload(nexus_force)


class _EmbedderConstant:
    """Même vecteur pour tout → sem constant, qui s'annule dans le classement :
    ISOLE l'effet de la force vs pertinence (chemin additif)."""
    def embed(self, text):
        return [1.0, 0.0, 0.0]


def _cand(nom, texte):
    """Candidat minimal tel que rank/_rank_lexical le consomme."""
    return {"file": nom + ".md", "path": "dom/cat/" + nom + ".md",
            "_search": texte, "excerpt": ""}


# Deux fiches à pertinence STRICTEMENT égale (même texte), noms choisis pour que
# l'ordre alphabétique (départage à force neutre) DÉFAVORISE la fiche forte : si
# la forte remonte quand même, c'est que la force a bien agi.
def _paire():
    return [_cand("aaa_faible", "projet distinctifxyz contenu"),
            _cand("zzz_forte", "projet distinctifxyz contenu")]


_FORCES = {"zzz_forte": 5.0, "aaa_faible": 0.2}
_QUERY = "distinctifxyz"


def _nominal(nf):
    return {"zzz_forte": nf.SEUIL_FORCE_SLUG, "aaa_faible": nf.SEUIL_FORCE_SLUG,
            "_total": nf.SEUIL_FORCE_GLOBAL}


# --------------------------------------------------------------------------- #
# 1. compter_events_force — filtre, repli LEGACY, inertes ignorés, _total
# --------------------------------------------------------------------------- #
def test_compter_events_force_filtre_repli_et_total(nf):
    events = [
        {"fiche": "a", "statut": "succes"},                       # +1 a
        {"fiche": "a", "statut": "echec"},                        # +1 a
        {"fiche": "b", "statut_juge": "succes", "statut": "ok"},  # juge PRIORITAIRE → +1 b
        {"fiche": "c", "statut": "ok"},                           # inerte → ignoré
        {"fiche": "c", "statut": "partiel"},                      # inerte → ignoré
        {"fiche": "", "statut": "succes"},                        # fiche vide → ignoré
        {"statut": "succes"},                                     # pas de fiche → ignoré
        {"fiche": "d", "statut_juge": "echec"},                   # LEGACY juge → +1 d
    ]
    c = nf.compter_events_force(events)
    assert c["a"] == 2 and c["b"] == 1 and c["d"] == 1
    assert "c" not in c                                           # inertes jamais comptés
    assert c["_total"] == 4                                       # 2 + 1 + 1


def test_compter_events_force_vide_et_non_mutant(nf):
    assert nf.compter_events_force([]) == {"_total": 0}
    # LECTURE SEULE : l'entrée n'est pas modifiée.
    events = [{"fiche": "a", "statut": "succes"}]
    avant = [dict(e) for e in events]
    nf.compter_events_force(events)
    assert events == avant


# --------------------------------------------------------------------------- #
# 2. RÉGIME NOMINAL : sortie byte-identique (les deux chemins)
# --------------------------------------------------------------------------- #
def test_nominal_legataire_byte_identique(nf):
    cands = _paire()
    nom = _nominal(nf)
    r = nf.rank(_QUERY, cands, forces=_FORCES, comptes_force=nom)  # embedder=None
    # la forte remonte MALGRÉ l'ordre alphabétique défavorable : force appliquée.
    assert r[0]["file"] == "zzz_forte.md"
    for it in r:
        # score = pertinence × force RÉELLE (multiplicatif, historique).
        force_reelle = _FORCES.get(it["file"][:-3], 1.0)
        assert it["_force"] == force_reelle
        assert it["_score"] == it["_relevance"] * force_reelle


def test_nominal_additif_byte_identique(nf):
    cands = _paire()
    nom = _nominal(nf)
    r = nf.rank(_QUERY, cands, forces=_FORCES, embedder=_EmbedderConstant(),
                comptes_force=nom)
    assert r[0]["file"] == "zzz_forte.md"                         # f=1 remonte
    par = {it["file"]: it for it in r}
    # f(force) == normalisation réelle (aucune neutralisation au nominal).
    assert par["zzz_forte.md"]["_f_force"] == nf.f_force(5.0)
    assert par["aaa_faible.md"]["_f_force"] == nf.f_force(0.2)


# --------------------------------------------------------------------------- #
# 3. SOUS SEUIL : force NEUTRE — ni monter ni descendre (vs monde SANS force)
# --------------------------------------------------------------------------- #
def test_sous_seuil_legataire_force_neutre_comme_sans_force(nf):
    cands = _paire()
    sous = {"_total": 0}                                          # aucun signal
    gated = nf.rank(_QUERY, cands, forces=_FORCES, comptes_force=sous)
    sans = nf.rank(_QUERY, cands, forces={}, comptes_force=sous)  # monde sans force
    # multiplicateur NEUTRE, et classement/scores IDENTIQUES au monde sans force :
    # la force ne peut NI monter NI descendre une fiche.
    assert all(it["_force"] == nf.FORCE_DEFAUT for it in gated)
    assert [it["file"] for it in gated] == [it["file"] for it in sans]
    assert [it["_score"] for it in gated] == [it["_score"] for it in sans]
    # départage par ordre alpha (force inerte) : la faible passe DEVANT la forte.
    assert gated[0]["file"] == "aaa_faible.md"


def test_sous_seuil_additif_f_force_nul(nf):
    cands = _paire()
    sous = {"_total": 0}
    gated = nf.rank(_QUERY, cands, forces=_FORCES, embedder=_EmbedderConstant(),
                    comptes_force=sous)
    sans = nf.rank(_QUERY, cands, forces={}, embedder=_EmbedderConstant(),
                   comptes_force=sous)
    # f(force) forcé à 0 → beta·f = 0 : aucun bonus ni pénalité.
    assert all(it["_f_force"] == 0.0 for it in gated)
    assert [it["file"] for it in gated] == [it["file"] for it in sans]
    assert [it["_score"] for it in gated] == [it["_score"] for it in sans]
    assert gated[0]["file"] == "aaa_faible.md"


# --------------------------------------------------------------------------- #
# 4. Les DEUX seuils ferment INDÉPENDAMMENT
# --------------------------------------------------------------------------- #
def test_porte_globale_ferme_via_total_meme_si_slug_suffisant(nf):
    cands = _paire()
    # comptes par fiche largement au-dessus du seuil SLUG, mais _total sous le
    # seuil GLOBAL : la porte globale (lue sur _total) ferme TOUT.
    comptes = {"zzz_forte": 99, "aaa_faible": 99, "_total": nf.SEUIL_FORCE_GLOBAL - 1}
    r = nf.rank(_QUERY, cands, forces=_FORCES, comptes_force=comptes)
    assert all(it["_force"] == nf.FORCE_DEFAUT for it in r)       # force neutre partout
    assert r[0]["file"] == "aaa_faible.md"                        # ordre alpha (inerte)


def test_porte_slug_ferme_pour_la_seule_fiche_sous_seuil(nf):
    cands = _paire()
    # global atteint ; forte ≥ seuil slug (sa force pèse), faible SOUS le seuil
    # slug (sa force reste neutre) — la porte est PAR FICHE.
    comptes = {"zzz_forte": nf.SEUIL_FORCE_SLUG,
               "aaa_faible": nf.SEUIL_FORCE_SLUG - 1,
               "_total": nf.SEUIL_FORCE_GLOBAL}
    r = nf.rank(_QUERY, cands, forces=_FORCES, comptes_force=comptes)
    par = {it["file"]: it for it in r}
    assert par["zzz_forte.md"]["_force"] == 5.0                   # porte ouverte
    assert par["aaa_faible.md"]["_force"] == nf.FORCE_DEFAUT      # porte fermée (slug)
    assert r[0]["file"] == "zzz_forte.md"                         # la forte départage


# --------------------------------------------------------------------------- #
# 5. Instrumentation — seuils épinglés (le provisoire ne dérive pas en silence)
# --------------------------------------------------------------------------- #
def test_seuils_epingles(nf):
    assert nf.SEUIL_FORCE_GLOBAL == 15
    assert nf.SEUIL_FORCE_SLUG == 3
