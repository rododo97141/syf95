"""Supersession Scout (proposition DIRECTIONNELLE datée, JAMAIS d'action) —
nexus_supersession_scout.

CONTEXTE. Le dédup sémantique (PR#77) a révélé une redondance TEMPORELLE : des
résumés « auto-decouverte-* » où le plus RÉCENT PÉRIME les anciens (même sujet,
snapshots successifs). Ce n'est pas un doublon à FUSIONNER — c'est une
SUPERSESSION (le neuf remplace l'ancien). memory_api porte le geste humain
`POST /superseder {path, superseded_par, date_validite}` mais aucune détection de
CANDIDATS (trou reporté PR#71). Ce scout LECTURE SEULE comble ce trou : il PROPOSE
des candidats directionnels datés, prêts pour le geste humain. Jamais d'action.

Ce que ces tests VERROUILLENT (et les MUTATIONS qu'ils virent ROUGES) :
  (a) `_date_fiche` : « > Créé le 30/06/2026 … » -> date(2026,6,30) ; sans date -> None.
  (b) `candidats_supersession` SANS embedder -> AUCUN candidat.
  (c) avec embedder MOCK déterministe :
        • paire cos >= seuil + dates DIFFÉRENTES -> PROPOSÉE, ORIENTÉE
          récent-supèrsede-ancien  → MUT. (i) direction inversée ROUGE ;
        • paire de MÊME date -> NON proposée  → MUT. (ii) même date proposée ROUGE ;
        • paire sans date (une manquante) -> NON proposée ;
        • paire cos < seuil -> NON proposée.
  (c') HONNÊTETÉ : embedder None -> AUCUN candidat  → MUT. (iii) « propose quand même » ROUGE.
  (d) « AUCUNE ACTION » : l'organe n'écrit RIEN, n'appelle JAMAIS superseder, aucun
      POST  → MUT. (iv) l'organe appelle superseder / écrit ROUGE.
"""
import os
import sys
import datetime
import importlib

import pytest


# --------------------------------------------------------------------------- #
# Chargement du module organe (organes/nexus_supersession_scout.py)
# --------------------------------------------------------------------------- #
def _racine():
    ici = os.path.dirname(os.path.abspath(__file__))          # backend/tests
    return os.path.dirname(os.path.dirname(ici))              # racine du dépôt


@pytest.fixture
def ss():
    org = os.path.join(_racine(), "organes")
    if org not in sys.path:
        sys.path.insert(0, org)
    import nexus_supersession_scout
    return importlib.reload(nexus_supersession_scout)


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


def _fiche(file, vecteur=None, date=None):
    return {"file": file, "vecteur": vecteur, "date": date}


D = datetime.date


# =========================================================================== #
# (a) _date_fiche : PUR, comparable, ne lève jamais
# =========================================================================== #
def test_date_fiche_extrait_la_premiere_date(ss):
    """« > Créé le 30/06/2026 · Dernière mise à jour le 05/07/2026 » -> la 1re date
    (création) en objet date COMPARABLE. On veut la date de CRÉATION (en-tête)."""
    texte = ("# Une fiche — domaine: x / catégorie: y\n"
             "> Créé le 30/06/2026 · Dernière mise à jour le 05/07/2026\n\n## En bref\n")
    assert ss._date_fiche(texte) == D(2026, 6, 30)


def test_date_fiche_tolere_consolide_le(ss):
    """La date peut être introduite par « Consolidé le » : même extraction."""
    assert ss._date_fiche("> Consolidé le 12/01/2026\n") == D(2026, 1, 12)


def test_date_fiche_sans_date_est_none(ss):
    """Aucune date -> None (direction indéterminable, jamais d'exception)."""
    assert ss._date_fiche("# Titre sans date\n\ndu corps sans date\n") is None
    assert ss._date_fiche("") is None
    assert ss._date_fiche(None) is None


def test_date_fiche_date_impossible_est_none(ss):
    """Une date syntaxiquement DD/MM/YYYY mais impossible (32/13/2026) -> None,
    jamais d'exception (ne casse pas le scout)."""
    assert ss._date_fiche("> Créé le 32/13/2026\n") is None


def test_date_fiche_borne_200_caracteres(ss):
    """Seuls les 200 PREMIERS caractères sont regardés : une date enfouie plus loin
    (corps) est ignorée (on vise la date de création de l'en-tête)."""
    texte = "# Titre sans date\n" + ("x" * 250) + " 01/01/2020 "
    assert ss._date_fiche(texte) is None


def test_date_fiche_retourne_un_objet_date_comparable(ss):
    """Le retour est un datetime.date -> comparable (< / >), socle de la DIRECTION."""
    recent = ss._date_fiche("> Créé le 10/07/2026\n")
    ancien = ss._date_fiche("> Créé le 30/06/2026\n")
    assert isinstance(recent, datetime.date) and isinstance(ancien, datetime.date)
    assert recent > ancien


# =========================================================================== #
# (b) SANS embedder -> AUCUN candidat
# =========================================================================== #
def test_candidats_sans_embedder_aucun(ss):
    """candidats_supersession(embedder=None) -> [] même sur une paire qui SERAIT
    parfaite (cos élevé + dates différentes). Honnêteté : jamais un faux candidat."""
    emb = EmbedderMock()
    fa = _fiche("recent.md", emb.embed("alpha"),  D(2026, 7, 10))
    fb = _fiche("ancien.md", emb.embed("alpha'"), D(2026, 6, 30))
    assert ss.candidats_supersession([fa, fb], embedder=None) == []


# =========================================================================== #
# (c) avec embedder MOCK : proposé, ORIENTÉ ; même date / sans date / cos bas exclus
# =========================================================================== #
def test_paire_proposee_orientee_recent_supersede_ancien(ss):
    """cos >= seuil + dates DIFFÉRENTES -> PROPOSÉE et ORIENTÉE : le RÉCENT
    supèrsede l'ANCIEN. MUTATION (i) direction inversée -> ROUGE."""
    emb = EmbedderMock()
    recent = _fiche("auto-decouverte-3.md", emb.embed("alpha"),  D(2026, 7, 10))
    ancien = _fiche("auto-decouverte-1.md", emb.embed("alpha'"), D(2026, 6, 30))

    # sanity : proches par le sens.
    assert ss.cosinus(recent["vecteur"], ancien["vecteur"]) >= ss.SEUIL_SEM

    cands = ss.candidats_supersession([recent, ancien], embedder=emb)
    assert len(cands) == 1
    cos, recent_file, ancien_file, date_recent, date_ancien = cands[0]
    # DIRECTION : le fichier le plus récent est en position « recent » (supèrsede).
    assert recent_file == "auto-decouverte-3.md"
    assert ancien_file == "auto-decouverte-1.md"
    assert date_recent == D(2026, 7, 10)
    assert date_ancien == D(2026, 6, 30)
    assert date_recent > date_ancien           # récent-supèrsede-ancien, invariant fort
    assert cos >= ss.SEUIL_SEM


def test_direction_independante_de_l_ordre_d_entree(ss):
    """La direction dépend de la DATE, jamais de l'ordre des combinaisons : en
    inversant l'ordre d'entrée, le récent reste le supersédant."""
    emb = EmbedderMock()
    recent = _fiche("neuf.md",  emb.embed("alpha"),  D(2026, 7, 10))
    ancien = _fiche("vieux.md", emb.embed("alpha'"), D(2026, 6, 30))
    # ancien EN PREMIER dans la liste :
    cands = ss.candidats_supersession([ancien, recent], embedder=emb)
    assert len(cands) == 1
    _, recent_file, ancien_file, dr, da = cands[0]
    assert recent_file == "neuf.md" and ancien_file == "vieux.md"
    assert dr > da


def test_paire_meme_date_non_proposee(ss):
    """MÊME date -> NON proposée (c'est du dédup, pas de la supersession).
    MUTATION (ii) paire de même date proposée -> ROUGE."""
    emb = EmbedderMock()
    fa = _fiche("a.md", emb.embed("alpha"),  D(2026, 6, 30))
    fb = _fiche("b.md", emb.embed("alpha'"), D(2026, 6, 30))   # MÊME date
    assert ss.cosinus(fa["vecteur"], fb["vecteur"]) >= ss.SEUIL_SEM  # proche par le sens
    assert ss.candidats_supersession([fa, fb], embedder=emb) == []


def test_paire_sans_date_non_proposee(ss):
    """Date manquante sur l'UNE -> NON proposée (direction indéterminable)."""
    emb = EmbedderMock()
    fa = _fiche("a.md", emb.embed("alpha"),  D(2026, 7, 10))
    fb = _fiche("b.md", emb.embed("alpha'"), None)             # date absente
    assert ss.cosinus(fa["vecteur"], fb["vecteur"]) >= ss.SEUIL_SEM
    assert ss.candidats_supersession([fa, fb], embedder=emb) == []
    # les DEUX dates absentes -> idem.
    fc = _fiche("c.md", emb.embed("alpha"),  None)
    fd = _fiche("d.md", emb.embed("alpha'"), None)
    assert ss.candidats_supersession([fc, fd], embedder=emb) == []


def test_paire_cos_bas_non_proposee(ss):
    """cos < seuil -> NON proposée (probablement PAS le même sujet), même dates
    présentes et différentes."""
    emb = EmbedderMock()
    fa = _fiche("a.md", emb.embed("beta"),  D(2026, 7, 10))
    fb = _fiche("b.md", emb.embed("gamma"), D(2026, 6, 30))    # cos = 0
    assert ss.cosinus(fa["vecteur"], fb["vecteur"]) < ss.SEUIL_SEM
    assert ss.candidats_supersession([fa, fb], embedder=emb) == []


def test_vecteur_manquant_non_propose(ss):
    """Vecteur absent sur l'une -> on ne devine pas le « même sujet » -> exclue."""
    emb = EmbedderMock()
    fa = _fiche("a.md", None,               D(2026, 7, 10))
    fb = _fiche("b.md", emb.embed("alpha"), D(2026, 6, 30))
    assert ss.candidats_supersession([fa, fb], embedder=emb) == []


def test_candidats_ne_modifie_pas_les_fiches(ss):
    """PURETÉ : candidats_supersession ne mute pas ses entrées (propose, ne touche rien)."""
    emb = EmbedderMock()
    fa = _fiche("a.md", emb.embed("alpha"),  D(2026, 7, 10))
    fb = _fiche("b.md", emb.embed("alpha'"), D(2026, 6, 30))
    avant = (dict(fa), dict(fb))
    ss.candidats_supersession([fa, fb], embedder=emb)
    assert fa == avant[0] and fb == avant[1]


# =========================================================================== #
# (c') HONNÊTETÉ dans main() : embedder None -> « semantique indisponible »
# =========================================================================== #
def _fake_get_deux_fiches(path):
    """Fausse API mémoire : un domaine, une catégorie, deux snapshots du même sujet
    à des dates DIFFÉRENTES (le récent supèrsede l'ancien). Aucun réseau réel."""
    if path.startswith("/domains"):
        return {"domains": {"tech": ["notes"]}}
    if path.startswith("/recall"):
        return {"results": [
            {"file": "auto-decouverte-3.md", "path": "structure/tech/notes/auto-decouverte-3.md",
             "excerpt": "# Auto découverte\n> Créé le 10/07/2026\nsnapshot recent\n"},
            {"file": "auto-decouverte-1.md", "path": "structure/tech/notes/auto-decouverte-1.md",
             "excerpt": "# Auto découverte\n> Créé le 30/06/2026\nsnapshot ancien\n"},
        ]}
    return {}


def test_main_embedder_none_annonce_indisponible(ss, monkeypatch, capsys):
    """main() sans embedder local ANNONCE « semantique indisponible » et ne propose
    AUCUN candidat. MUTATION (iii) « propose quand même » -> ROUGE."""
    monkeypatch.setattr(ss, "_charger_embedder", lambda: None)
    monkeypatch.setattr(ss, "get", _fake_get_deux_fiches)
    ss.main()
    out = capsys.readouterr().out.lower()
    assert "semantique indisponible" in out
    assert "superseder path=" not in out          # aucun candidat proposé


def test_main_avec_embedder_propose_le_geste_pret(ss, monkeypatch, capsys):
    """main() AVEC embedder propose le candidat orienté ET les paramètres du geste
    PRÊTS : « superseder path=<ancien> superseded_par=<recent> date_validite=<date_ancien> »."""
    emb = EmbedderMock()

    def faux_titre(f):
        return "alpha" if "3" in f.get("file", "") else "alpha'"

    monkeypatch.setattr(ss, "_charger_embedder", lambda: emb)
    monkeypatch.setattr(ss, "_titre_fiche", faux_titre)
    monkeypatch.setattr(ss, "get", _fake_get_deux_fiches)
    ss.main()
    out = capsys.readouterr().out
    # Le geste est affiché prêt, ORIENTÉ ancien<-récent, daté à la date de l'ancien.
    assert ("superseder path=structure/tech/notes/auto-decouverte-1.md "
            "superseded_par=structure/tech/notes/auto-decouverte-3.md "
            "date_validite=30/06/2026") in out


# =========================================================================== #
# (d) « AUCUNE ACTION » : DRY-RUN strict — aucune écriture, aucun superseder, aucun POST
# =========================================================================== #
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


def _interdit_reseau_ecrivant(monkeypatch, ss):
    """Toute requête POST (ou tout appel superseder-like) DOIT lever : l'organe est
    LECTURE SEULE. On garde `get` (lecture API) mais on piège urlopen sur POST."""
    import urllib.request
    vrai_urlopen = urllib.request.urlopen

    def urlopen_garde(req, *a, **k):
        # Un Request avec data (POST) ou une URL /superseder = ACTION interdite.
        methode = getattr(req, "get_method", lambda: "GET")()
        url = getattr(req, "full_url", req if isinstance(req, str) else "")
        if methode == "POST" or "superseder" in str(url):
            raise AssertionError(f"POST/superseder INTERDIT (DRY-RUN) : {url}")
        return vrai_urlopen(req, *a, **k)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen_garde)


def test_main_aucune_action_ni_ecriture_ni_superseder(ss, monkeypatch, capsys):
    """main() (passe active, un candidat) n'écrit RIEN et n'appelle JAMAIS
    superseder ni aucun POST. MUTATION (iv) l'organe appelle superseder / écrit -> ROUGE."""
    emb = EmbedderMock()

    def faux_titre(f):
        return "alpha" if "3" in f.get("file", "") else "alpha'"

    monkeypatch.setattr(ss, "_charger_embedder", lambda: emb)
    monkeypatch.setattr(ss, "_titre_fiche", faux_titre)
    monkeypatch.setattr(ss, "get", _fake_get_deux_fiches)
    _open_lecture_seule(monkeypatch)
    _interdit_reseau_ecrivant(monkeypatch, ss)

    ss.main()  # ne doit RIEN écrire, RIEN superséder (sinon AssertionError des gardes)

    out = capsys.readouterr().out
    # Le candidat est bien proposé, et l'organe RAPPELLE que c'est un geste humain.
    assert "superseder path=" in out
    assert "geste humain" in out.lower()
    assert "Aucune supersession appliquee" in out


def test_organe_n_importe_pas_superseder(ss):
    """L'organe scout ne référence AUCUNE fonction d'action : `superseder` /
    `desuperseder` n'apparaissent pas comme attributs appelables du module."""
    assert not hasattr(ss, "superseder")
    assert not hasattr(ss, "desuperseder")
