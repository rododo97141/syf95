"""Tests du gardien 98 — solipsisme INFALSIFIABLE en fausse-santé.

CONTEXTE (mesuré le 11/07 sur 146 fiches réelles) : un run parallèle a rapporté
ratio_solipsisme=0 % (fausse mémoire « diverse »). Vérifié : via _scan (défaut de
lecture absent→'interne' résolu) = 95,2 % (CORRECT) ; via tag BRUT (sans défaut)
= 0 %. Donc est_interne / ratio_solipsisme sont JUSTES sur sources résolues ; le
faux 0 % vient d'un appelant (hors dépôt) qui lit les tags bruts non résolus.

Un gardien qui rapporte 0 % de danger sur input non résolu = pire échec d'un
système immunitaire. On ajoute donc une VUE opt-in « solipsisme sur toute la
mémoire » (est_interne_ou_defaut) qui ne peut plus lire ce faux 0 %.

PIÈGE ÉVITÉ ET PROUVÉ ICI : durcir est_interne GLOBALEMENT casserait la détection
de fuites. couverture_etiquetage / digue_ingestion DOIVENT compter un EXTERNE
sans tag (source None / '') comme une FUITE, pas comme un interne. Elles restent
STRICTES et n'exposent aucun mode defaut_interne (le fail-safe ne peut y fuir).

FAIL-SAFE prouvé : defaut_interne=True ne peut que MONTER le solipsisme
(absent→interne), JAMAIS le baisser (jamais de fausse diversité).

Défaut BYTE-IDENTIQUE prouvé : sans le flag, la sortie est inchangée et NE porte
PAS le champ 'defaut_interne' (golden préservé).
"""
import os
import sys
import importlib.util

import pytest


ICI = os.path.dirname(os.path.abspath(__file__))              # backend/tests
RACINE = os.path.dirname(os.path.dirname(ICI))                # racine du dépôt
ORGANES = os.path.join(RACINE, "organes")
if ORGANES not in sys.path:
    sys.path.insert(0, ORGANES)


def _charger(nom, chemin):
    spec = importlib.util.spec_from_file_location(nom, chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def n98():
    return _charger("nexus_98_failsafe_test", os.path.join(ORGANES, "nexus_98.py"))


# =========================================================================== #
# (a) est_interne_ou_defaut : PUR — absent vaut le défaut 'interne', reste EXACT
#     MUTATION (i) startswith ('interne-x'→True) → doit être ROUGE.
# =========================================================================== #
def test_a_est_interne_ou_defaut(n98):
    assert n98.est_interne_ou_defaut(None) is True         # absent → défaut interne
    assert n98.est_interne_ou_defaut("") is True           # vide → défaut interne
    assert n98.est_interne_ou_defaut("interne") is True    # exact
    # source NON VIDE : EXACTE, JAMAIS un startswith
    assert n98.est_interne_ou_defaut("interne-x") is False
    assert n98.est_interne_ou_defaut("web") is False


def test_a_est_interne_reste_strict(n98):
    # est_interne NON modifié : reste STRICT (garant de la détection de fuites).
    assert n98.est_interne("interne") is True
    assert n98.est_interne(None) is False                  # absent = EXTERNE (fuite)
    assert n98.est_interne("") is False
    assert n98.est_interne("interne-x") is False
    assert n98.est_interne("web") is False


# =========================================================================== #
# (b) ratio_solipsisme DÉFAUT (sans flag) sur sources None → 0 % (byte-identique)
#     ET pas de champ 'defaut_interne' dans le retour.
#     MUTATION (iv) défaut non byte-identique → doit être ROUGE.
# =========================================================================== #
def test_b_defaut_byte_identique_sur_none(n98):
    cands = [{"source": None}, {"source": None}, {"source": None}]
    r = n98.ratio_solipsisme(cands)
    assert r["total"] == 3
    assert r["interne"] == 0                # None compte EXTERNE (strict) → 0 %
    assert r["externe"] == 3
    assert r["ratio_interne"] == 0.0
    # Le défaut NE DOIT PAS porter le champ (golden strictement inchangé).
    assert "defaut_interne" not in r


def test_b_defaut_flag_explicite_false_identique(n98):
    # defaut_interne=False explicite == défaut implicite : byte-identique.
    cands = [{"source": None}, {"source": "web"}]
    assert n98.ratio_solipsisme(cands) == n98.ratio_solipsisme(cands, defaut_interne=False)
    assert "defaut_interne" not in n98.ratio_solipsisme(cands, defaut_interne=False)


# =========================================================================== #
# (c) ratio_solipsisme(defaut_interne=True) sur sources None → 100 % interne
#     + champ 'defaut_interne': True.
# =========================================================================== #
def test_c_flag_true_absent_compte_interne(n98):
    cands = [{"source": None}, {"source": None}, {"source": None}]
    r = n98.ratio_solipsisme(cands, defaut_interne=True)
    assert r["total"] == 3
    assert r["interne"] == 3                # None → interne (vue toute-mémoire)
    assert r["externe"] == 0
    assert r["ratio_interne"] == 1.0
    assert r["defaut_interne"] is True      # champ présent SEULEMENT en mode True


# =========================================================================== #
# (d) mélange (139 None + 7 'web') avec defaut_interne=True → ~95 % interne
#     (reproduit le cas réel des 146 fiches : _scan lit 95,2 %, tag brut 0 %).
# =========================================================================== #
def test_d_melange_146_fiches_reelles(n98):
    cands = [{"source": None}] * 139 + [{"source": "web"}] * 7
    r = n98.ratio_solipsisme(cands, defaut_interne=True)
    assert r["total"] == 146
    assert r["interne"] == 139              # les 139 None → interne
    assert r["externe"] == 7               # les 7 'web' restent EXTERNES (exact)
    assert 0.94 <= r["ratio_interne"] <= 0.96
    assert r["defaut_interne"] is True


# =========================================================================== #
# FAIL-SAFE : defaut_interne=True ne peut que MONTER le solipsisme, JAMAIS baisser.
# MUTATION (ii) le flag BAISSE le solipsisme (absent→externe) → doit être ROUGE.
# =========================================================================== #
def test_failsafe_flag_monte_jamais_baisse(n98):
    # Un panachage arbitraire : le mode True donne toujours >= le mode défaut.
    for cands in (
        [{"source": None}, {"source": "web"}, {"source": "interne"}],
        [{"source": None}] * 5,
        [{"source": "web"}] * 3,
        [{"source": ""}, {"source": "interne"}, {"source": "web"}],
    ):
        base = n98.ratio_solipsisme(cands)["interne"]
        haut = n98.ratio_solipsisme(cands, defaut_interne=True)["interne"]
        assert haut >= base, f"le flag a BAISSÉ le solipsisme sur {cands}"


# =========================================================================== #
# (e) couverture_etiquetage / digue : détection de fuites INCHANGÉE et STRICTE.
#     PRINCIPE IMMUNITAIRE (garde-fou + mutation iii) : un EXTERNE SANS TAG
#     (source None / '') DOIT rester une FUITE ici — JAMAIS absorbé en interne.
#     Le fail-safe de solipsisme (defaut_interne) ne touche PAS ces organes ;
#     ils n'ont aucun paramètre du genre et gardent est_interne STRICT.
#     MUTATION (iii) le mode defaut_interne fuit ici (None absorbé en interne,
#     donc sorti des externes) → ces tests passent au ROUGE.
# =========================================================================== #
def test_e_couverture_web_etiquete_none_est_fuite(n98):
    # 'web' (étiqueté) ET None (externe SANS tag) sont tous deux EXTERNES.
    # Le None non étiqueté = une FUITE d'étiquetage → couverture < 100 %.
    cands = [{"source": "web"}, {"source": None}]
    c = n98.couverture_etiquetage(cands)
    assert c["externes"] == 2               # 'web' ET None → externes (strict)
    assert c["etiquetes"] == 1              # seul 'web' est étiqueté
    assert c["couverture"] == 0.5           # None = fuite → couverture partielle
    assert c["complete"] is False


def test_e_couverture_externe_sans_etiquette_est_fuite(n98):
    # Un externe SANS étiquette ('' = vide) DOIT rester une fuite d'étiquetage.
    cands = [{"source": ""}]
    c = n98.couverture_etiquetage(cands)
    assert c["externes"] == 1               # '' compte EXTERNE (est_interne strict)
    assert c["etiquetes"] == 0              # non étiqueté → fuite
    assert c["couverture"] == 0.0
    assert c["complete"] is False


def test_e_digue_web_hors_allowlist_et_none_sont_des_fuites(n98):
    cands = [{"source": "web"}, {"source": None}]
    d = n98.digue_ingestion(cands, {"wikipedia"})
    # 'web' hors allowlist ET None (externe sans tag) = FUITES (comportement
    # INCHANGÉ, strict). None n'est JAMAIS blanchi en interne.
    assert d["hors_allowlist"] == 2
    assert d["digue_ok"] is False
    assert "web" in d["exemples"] and None in d["exemples"]


def test_e_digue_web_dans_allowlist_none_reste_fuite(n98):
    cands = [{"source": "web"}, {"source": None}]
    d = n98.digue_ingestion(cands, {"web"})
    # 'web' permis, mais None reste un externe hors allowlist = fuite (strict).
    assert d["hors_allowlist"] == 1
    assert d["exemples"] == [None]
    assert d["digue_ok"] is False


def test_e_digue_couverture_nont_pas_de_mode_defaut_interne(n98):
    # Garde-fou STRUCTUREL : ces organes n'exposent AUCUN paramètre
    # defaut_interne — le fail-safe ne peut structurellement pas y fuir.
    import inspect
    assert "defaut_interne" not in inspect.signature(n98.couverture_etiquetage).parameters
    assert "defaut_interne" not in inspect.signature(n98.digue_ingestion).parameters
    # Et un externe sans tag y reste bien une fuite (jamais absorbé en interne).
    cands = [{"source": None}, {"source": "web"}]
    assert n98.couverture_etiquetage(cands)["externes"] == 2
    assert n98.digue_ingestion(cands, {"wikipedia"})["hors_allowlist"] == 2
