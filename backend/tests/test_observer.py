"""Autonomie du déclencheur HITL — étape 1 : LA VISIBILITÉ.
« Automatiser la CLÔTURE, jamais le JUGEMENT. »

Ligne rouge de doctrine (non négociable) : aucun chemin MÉCANIQUE ne peut
atteindre appliquer — le système ne se récompense JAMAIS lui-même. La force reste
un signal de JUGEMENT HUMAIN externe (jeton). Modèle de menace nommé :
le-code-s-auto-récompense (Goodhart interne). PAS un-attaquant-a-le-disque (hors
périmètre — un tel attaquant réécrirait de toute façon n'importe quel fichier).

Couvre, sur état/mémoire/capteurs/leçons ISOLÉS (jamais le vrai memoire_data/) :

  T1    la boucle passe par consulter (chaque tâche avec fiche = UNE consultation
        journalisée à fiche unique).
  T2    rappel DÉFENSIF : consulter qui lève = la boucle continue.
  T3    clôture auto : fin de cycle = AUCUNE consultation de boucle ouverte, et
        AUCUN event succes/echec issu de la boucle (journal capteurs).
  T3bis échec de clôture TRACÉ : clore qui lève (simulé) = tâche terminée + échec
        journalisé + consultation OUVERTE au bilan (mutation avale-en-silence : rouge).
  T4    jeton : appliquer sans jeton lève ; jeton valide = comportement PR 64
        identique ; jeton rejoué lève ; clore_sans_dette sans jeton RÉUSSIT.
  T5    multi-fiches → clore_sans_dette, JAMAIS appliquer (et garde AST).
  T6    98 jointure unique (event sans jeton = alerte ; jeton inconnu = alerte ;
        DEUX events même jeton = alerte) ; registre cassé = 98 debout.
  T7    log_event sans jeton BYTE-IDENTIQUE (ajout pur) + rétrocompat tourner
        (mêmes tâches mêmes états hormis consultations) + voisins SHA-256.
  T8    smoke complet + garde AST (observer n'importe/n'appelle JAMAIS la fabrique
        de jetons ni appliquer).
"""
import os
import ast
import sys
import json
import hashlib
import importlib

import pytest


# --------------------------------------------------------------------------- #
# Chargement / isolation
# --------------------------------------------------------------------------- #
def _racine_depot():
    ici = os.path.dirname(os.path.abspath(__file__))          # backend/tests
    return os.path.dirname(os.path.dirname(ici))              # racine du dépôt


def _organes():
    org = os.path.join(_racine_depot(), "organes")
    if org not in sys.path:
        sys.path.insert(0, org)
    return org


class _Ctx:
    pass


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    _organes()
    racine_memoire = tmp_path / "memoire_data"
    monkeypatch.setenv("MEMOIRE_ROOT", str(racine_memoire))   # relu à chaque appel

    import nexus_force
    import nexus_sense
    import nexus_lecons
    import nexus_capital
    import nexus_observer
    import nexus_98
    importlib.reload(nexus_force)

    # journaux de leçons isolés (appliquer → nexus_lecons.appliquer écrit ici).
    dl = tmp_path / "lecons"
    monkeypatch.setattr(nexus_lecons, "DIR", str(dl))
    monkeypatch.setattr(nexus_lecons, "JOURNAL", str(dl / "journal.jsonl"))
    monkeypatch.setattr(nexus_lecons, "TRANSFERT", str(dl / "transfert.jsonl"))

    import orchestrateur

    c = _Ctx()
    c.nf = nexus_force
    c.sense = nexus_sense
    c.lecons = nexus_lecons
    c.cap = nexus_capital
    c.obs = nexus_observer
    c.n98 = nexus_98
    c.orch = orchestrateur
    c.tmp = tmp_path
    c.racine_memoire = racine_memoire
    c.capteurs_journal = os.path.join(os.environ["CAPTEURS_ROOT"], "capteurs", "journal.jsonl")
    return c


def _capteurs(c):
    if not os.path.exists(c.capteurs_journal):
        return []
    return [json.loads(l) for l in open(c.capteurs_journal, encoding="utf-8") if l.strip()]


def _consultations(c):
    chemin = c.cap._chemin_consultations()
    if not os.path.exists(chemin):
        return []
    return [json.loads(l) for l in open(chemin, encoding="utf-8") if l.strip()]


class _FakeMemoire:
    """Mémoire injectable : recall renvoie une fiche contrôlée (ou rien, ou lève)."""
    def __init__(self, fiche=None, leve=False):
        self.fiche = fiche
        self.leve = leve
        self.appels = 0

    def recall(self, payload):
        self.appels += 1
        if self.leve:
            raise RuntimeError("recall cassé (simulation)")
        return {"results": [self.fiche] if self.fiche else []}


def _etat(taches):
    return {
        "version": 1, "cree_le": "2026-01-01T00:00:00+00:00",
        "maj_le": "2026-01-01T00:00:00+00:00", "cycle": 0, "curseur": 0,
        "taches": taches, "ecarts_semes": True,   # pas d'auto-mandat (bruit hors-sujet)
        "archive_96": [], "journal": [],
    }


def _tache(tid, libelle, sensible=False):
    return {"id": tid, "libelle": libelle, "etat": "a_faire", "resultat": None,
            "verifie": False, "veto": False, "sensible": sensible}


# =========================================================================== #
# T1 — la boucle passe par consulter : une consultation fiche-unique par tâche.
# =========================================================================== #
def test_t1_boucle_passe_par_consulter_une_consultation_fiche_unique_par_tache(ctx):
    mem = _FakeMemoire(fiche={"file": "fiche_boucle.md", "excerpt": "contenu utile"})
    etat_path = ctx.tmp / "etat.json"
    ctx.orch.sauver_etat(etat_path, _etat([
        _tache("t1", "Analyser la mission alpha"),
        _tache("t2", "Analyser la mission beta"),
    ]))
    from moteur import MoteurMock
    ctx.orch.tourner(etat_path, moteur=MoteurMock(), memoire=mem)

    cons = [r for r in _consultations(ctx) if r.get("type") == "consultation"]
    assert len(cons) == 2                                     # une consultation par tâche…
    for r in cons:
        assert len(r["slugs_retournes"]) == 1                # …à FICHE UNIQUE
        assert r["slugs_retournes"][0] == "fiche_boucle"
    assert mem.appels == 2                                    # recall bien consulté par tâche


# =========================================================================== #
# T2 — rappel DÉFENSIF : consulter qui lève ⇒ la boucle continue.
# =========================================================================== #
def test_t2_rappel_defensif_consulter_qui_leve_boucle_continue(ctx):
    mem = _FakeMemoire(leve=True)                             # recall casse à chaque appel
    etat_path = ctx.tmp / "etat.json"
    ctx.orch.sauver_etat(etat_path, _etat([
        _tache("t1", "Tâche A"), _tache("t2", "Tâche B"),
    ]))
    from moteur import MoteurMock
    etat = ctx.orch.tourner(etat_path, moteur=MoteurMock(), memoire=mem)

    # la boucle a continué : les deux tâches sont traitées (fait), rien n'a crashé.
    assert [t["etat"] for t in etat["taches"]] == ["fait", "fait"]
    # recall a levé AVANT toute journalisation : aucune consultation ouverte.
    assert [r for r in _consultations(ctx) if r.get("type") == "consultation"] == []


# =========================================================================== #
# T3 — clôture auto : aucune consultation ouverte, aucun event de force de boucle.
# =========================================================================== #
def test_t3_cloture_auto_aucune_ouverte_aucun_event_de_force(ctx):
    mem = _FakeMemoire(fiche={"file": "fiche_boucle.md", "excerpt": "x"})
    etat_path = ctx.tmp / "etat.json"
    ctx.orch.sauver_etat(etat_path, _etat([
        _tache("t1", "Mission un"), _tache("t2", "Mission deux"),
    ]))
    from moteur import MoteurMock
    ctx.orch.tourner(etat_path, moteur=MoteurMock(), memoire=mem)

    # (a) AUCUN event succes/echec issu de la boucle sur le journal capteurs.
    forces = [e for e in _capteurs(ctx)
              if e.get("fiche") and e.get("statut") in ("succes", "echec")]
    assert forces == []

    # (b) AUCUNE consultation de boucle ouverte : toutes closes-sans-dette.
    b = ctx.cap.bilan()
    assert b["n_ouvertes"] == 0 and b["n_dette"] == 0
    clos = [r for r in _consultations(ctx) if r.get("type") == "cloture_sans_dette"]
    assert len(clos) == 2
    assert all(r["raison"] == ctx.obs.RAISON_CLOTURE_BOUCLE for r in clos)


# =========================================================================== #
# T3bis — échec de clôture TRACÉ (mutation avale-en-silence : rouge).
# =========================================================================== #
def test_t3bis_echec_de_cloture_trace_consultation_reste_ouverte(ctx, monkeypatch):
    mem = _FakeMemoire(fiche={"file": "fiche_boucle.md", "excerpt": "x"})
    etat_path = ctx.tmp / "etat.json"
    ctx.orch.sauver_etat(etat_path, _etat([_tache("t1", "Mission qui n'arrive pas à clore")]))

    # la clôture LÈVE (simulée) : l'observer doit AVALER (tâche continue) mais TRACER.
    def _clore_qui_casse(cid, raison):
        raise RuntimeError("clôture cassée (simulation)")
    monkeypatch.setattr(ctx.cap, "clore_sans_dette", _clore_qui_casse)

    from moteur import MoteurMock
    etat = ctx.orch.tourner(etat_path, moteur=MoteurMock(), memoire=mem)

    # la tâche est terminée QUAND MÊME (la boucle ne casse jamais).
    assert etat["taches"][0]["etat"] == "fait"
    # l'échec est JOURNALISÉ (jamais silencieux → cette assertion tue la mutation
    # « avale-en-silence sans tracer »).
    echecs = ctx.obs.echecs_cloture()
    assert len(echecs) == 1
    assert echecs[0]["type"] == "echec_cloture"
    assert echecs[0]["raison"] == ctx.obs.RAISON_CLOTURE_BOUCLE
    # la consultation N'A PAS été close → elle reste OUVERTE, donc visible au bilan.
    b = ctx.cap.bilan()
    assert b["n_ouvertes"] == 1


# =========================================================================== #
# T4 — jeton : sans jeton lève / valide identique / rejoué lève / clore libre.
# =========================================================================== #
def _fiche_criteres(ctx, question, token):
    """Capitalise une fiche criteres-kily et renvoie (slug, consultation fiche-unique)."""
    slug = ctx.cap.capitaliser(question, "r", "ctx", "nexus")
    rec = ctx.cap.consulter(token, "tâche")                  # chemin CAPITAL (rank)
    return slug, rec


def test_t4_jeton_sans_leve_valide_identique_rejoue_leve_clore_libre(ctx):
    slug, rec = _fiche_criteres(ctx, "Critères jetontokenalpha à trancher", "jetontokenalpha")
    assert rec["slugs_retournes"] == [slug]                  # fiche-unique

    # (1) appliquer SANS jeton ⇒ lève (aucun capteur de force).
    n_avant = len([e for e in _capteurs(ctx) if e.get("fiche")])
    with pytest.raises(ValueError):
        ctx.cap.appliquer(rec["id"], slug, "succes", "tâche")
    assert len([e for e in _capteurs(ctx) if e.get("fiche")]) == n_avant

    # (2) jeton VALIDE ⇒ comportement PR 64 identique (capteur émis + force montée).
    jid = ctx.cap.generer_jeton_confirmation(rec["id"])
    app = ctx.cap.appliquer(rec["id"], slug, "succes", "tâche", jeton=jid)
    assert app["statut"] == "succes" and app["jeton"] == jid
    caps = [e for e in _capteurs(ctx) if e.get("fiche") == slug]
    assert len(caps) == 1 and caps[0]["jeton"] == jid        # id du jeton dans l'event
    forces = ctx.nf.calculer_forces()
    assert forces.get(slug, 1.0) > 1.0                       # sémantique PR 64 intacte

    # (3) jeton REJOUÉ (le même) ⇒ lève, aucun nouveau capteur.
    n_apres = len([e for e in _capteurs(ctx) if e.get("fiche")])
    with pytest.raises(ValueError):
        ctx.cap.appliquer(rec["id"], slug, "succes", "tâche", jeton=jid)
    assert len([e for e in _capteurs(ctx) if e.get("fiche")]) == n_apres

    # (3bis) jeton INCONNU ⇒ lève aussi.
    with pytest.raises(ValueError):
        ctx.cap.appliquer(rec["id"], slug, "succes", "tâche", jeton="jeton-inexistant")

    # (4) DISSYMÉTRIE : clore_sans_dette n'exige RIEN — réussit sans jeton.
    _slug2, rec2 = _fiche_criteres(ctx, "Critères jetontokenbeta administratif", "jetontokenbeta")
    clo = ctx.cap.clore_sans_dette(rec2["id"], "administratif")
    assert clo["type"] == "cloture_sans_dette"


# =========================================================================== #
# T5 — multi-fiches → clore_sans_dette, JAMAIS appliquer.
# =========================================================================== #
def test_t5_multi_fiches_route_clore_jamais_appliquer(ctx):
    ctx.cap.capitaliser("Critères multitokenX première fiche", "r", "ctx", "nexus")
    ctx.cap.capitaliser("Critères multitokenX seconde fiche", "r", "ctx", "nexus")
    multi = ctx.cap.consulter("multitokenX", "tâche multi")
    assert len(multi["slugs_retournes"]) >= 2                # multi-fiches

    # appliquer REFUSE le multi MÊME avec un jeton valide (jamais de force sur multi).
    jid = ctx.cap.generer_jeton_confirmation(multi["id"])
    n_avant = len([e for e in _capteurs(ctx) if e.get("fiche")])
    with pytest.raises(ValueError):
        ctx.cap.appliquer(multi["id"], multi["slugs_retournes"][0], "succes",
                          "tâche multi", jeton=jid)
    assert len([e for e in _capteurs(ctx) if e.get("fiche")]) == n_avant   # rien émis

    # le chemin de clôture ADMINISTRATIVE, lui, accepte le multi (route clore).
    clo = ctx.obs.cloturer_consultation_boucle(multi["id"])
    assert clo["type"] == "cloture_sans_dette"
    b = ctx.cap.bilan()
    assert b["n_multi_fiches"] >= 1 and b["n_dette"] == 0     # multi jamais en dette


def test_t5_garde_ast_observer_n_importe_ni_n_appelle_la_fabrique(ctx):
    """Garde AST (2e rideau) : le nom `appliquer` et `generer_jeton_confirmation`
    n'apparaissent JAMAIS comme appel/attribut/nom dans l'observer. Mutation
    « observer appelle appliquer » ou « importe la fabrique » ⇒ rouge."""
    chemin = os.path.join(_organes(), "nexus_observer.py")
    arbre = ast.parse(open(chemin, encoding="utf-8").read())
    interdits = {"appliquer", "generer_jeton_confirmation"}
    trouves = set()
    for node in ast.walk(arbre):
        if isinstance(node, ast.Attribute) and node.attr in interdits:
            trouves.add(node.attr)
        if isinstance(node, ast.Name) and node.id in interdits:
            trouves.add(node.id)
    assert trouves == set(), "l'observer ne doit NI appeler NI référencer : %s" % sorted(trouves)


# =========================================================================== #
# T6 — 98 : jointure unique jeton ↔ event de force ; registre cassé = 98 debout.
# =========================================================================== #
def _ev_force(fiche, statut="succes", jeton=None):
    e = {"fiche": fiche, "statut": statut}
    if jeton is not None:
        e["jeton"] = jeton
    return e


def test_t6_98_jointure_unique_et_registre_casse_98_debout(ctx, monkeypatch):
    n98 = ctx.n98

    # (a) event de force SANS jeton ⇒ alerte + verdict non-SAIN.
    alertes = n98.signaux_jointure([_ev_force("f1")], {})
    assert alertes and "SANS jeton" in alertes[0]
    assert "SAIN" not in n98.calc_verdict([], jointure_alertes=len(alertes))

    # (b) jeton INCONNU du registre ⇒ alerte.
    alertes = n98.signaux_jointure([_ev_force("f1", jeton="jeton-0009")], registre={})
    assert alertes and "INCONNU" in alertes[0]

    # (c) DEUX events de force référençant le MÊME jeton ⇒ alerte (copie d'id).
    reg = {"jeton-0001": {"id": "jeton-0001"}}
    alertes = n98.signaux_jointure(
        [_ev_force("f1", jeton="jeton-0001"), _ev_force("f2", jeton="jeton-0001")], reg)
    assert any("doublon" in a for a in alertes)

    # (d) cas SAIN : un jeton connu référencé UNE fois ⇒ aucune alerte.
    assert n98.signaux_jointure([_ev_force("f1", jeton="jeton-0001")], reg) == []
    assert "SAIN" in n98.calc_verdict([], jointure_alertes=0)

    # (e) registre CASSÉ (jetons_emis lève) ⇒ jetons_registre None, 98 DEBOUT :
    #     la lecture ne tombe pas, et l'event sans jeton reste détecté.
    def _emis_qui_casse():
        raise RuntimeError("registre corrompu")
    monkeypatch.setattr(ctx.cap, "jetons_emis", _emis_qui_casse)
    assert n98.jetons_registre() is None                     # avalé, pas propagé
    assert n98.signaux_jointure([_ev_force("f1")], None)      # sans-jeton toujours vu


# =========================================================================== #
# T7 — log_event byte-identique + rétrocompat tourner + voisins SHA-256.
# =========================================================================== #
_CLES_HISTORIQUES = ["ts", "tache", "statut", "mode", "duree_min", "feedback",
                     "qualite", "tokens", "impact", "difficulte", "tier", "note", "fiche"]


def test_t7_log_event_sans_jeton_byte_identique(ctx):
    ev = ctx.sense.log_event(tache="essai", statut="ok", mode="auto", tier="DUO")
    # AJOUT PUR : sans jeton, la clé n'existe pas ⇒ jeu de clés + ordre HISTORIQUES.
    assert "jeton" not in ev
    assert list(ev.keys()) == _CLES_HISTORIQUES
    # avec jeton : la clé structurée apparaît (jamais dans du texte libre).
    ev2 = ctx.sense.log_event(tache="essai", statut="succes", fiche="f", jeton="jeton-0001")
    assert ev2["jeton"] == "jeton-0001" and list(ev2.keys())[-1] == "jeton"


def test_t7_retrocompat_tourner_memes_taches_memes_etats_hormis_consultations(ctx):
    """Rétrocompat : sans fiche rappelée, tourner produit EXACTEMENT les mêmes
    états de tâches qu'avant (la 4e, sensible, bloquée par 98) et AUCUNE
    consultation (rien de fantôme). Plan fixe (ecarts_semes) pour un état
    déterministe, sans bruit d'auto-mandat."""
    from moteur import MoteurMock
    mem = _FakeMemoire(fiche=None)                           # recall ne trouve rien
    etat_path = ctx.tmp / "etat.json"
    ctx.orch.sauver_etat(etat_path, _etat([
        _tache("t1", "Tâche A"), _tache("t2", "Tâche B"), _tache("t3", "Tâche C"),
        _tache("t4", "Action sensible", sensible=True), _tache("t5", "Tâche E"),
    ]))
    etat = ctx.orch.tourner(etat_path, moteur=MoteurMock(), memoire=mem)
    etats = {t["id"]: t["etat"] for t in etat["taches"]}
    assert etats == {"t1": "fait", "t2": "fait", "t3": "fait",
                     "t4": "bloque", "t5": "fait"}           # états classiques inchangés
    assert [r for r in _consultations(ctx) if r.get("type") == "consultation"] == []


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_t7_voisins_sha256_inchanges(ctx):
    """Les organes GELÉS (NE MODIFIE PAS) ne sont touchés par AUCUN geste de la
    chaîne observer/capital : empreintes SHA-256 identiques avant/après."""
    org = _organes()
    skill = os.path.join(_racine_depot(), ".claude", "skills", "memoire-beta", "scripts")
    geles = [os.path.join(org, f) for f in
             ("nexus_force.py", "nexus_budget.py", "nexus_bus.py", "nexus_lecons.py")]
    geles.append(os.path.join(skill, "memory_api.py"))       # rank/recall/sas (comportement gelé)
    avant = {p: _sha(p) for p in geles}

    # chaîne complète : capitaliser → consulter → jeton → appliquer → clore → observer → bilan → 98.
    slug, rec = _fiche_criteres(ctx, "Critères shatoken à mesurer", "shatoken")
    jid = ctx.cap.generer_jeton_confirmation(rec["id"])
    ctx.cap.appliquer(rec["id"], slug, "succes", "tâche", jeton=jid)
    _s2, rec2 = _fiche_criteres(ctx, "Critères shadeux administrative", "shadeux")
    ctx.obs.cloturer_consultation_boucle(rec2["id"])
    ctx.cap.bilan()
    ctx.n98.signaux_jointure(_capteurs(ctx), ctx.n98.jetons_registre())

    apres = {p: _sha(p) for p in geles}
    assert avant == apres                                    # aucun octet gelé modifié


# =========================================================================== #
# T8 — smoke complet.
# =========================================================================== #
def test_t8_smoke_brique_observer(ctx):
    for fn in (ctx.cap.consulter, ctx.cap.appliquer, ctx.cap.clore_sans_dette,
               ctx.cap.generer_jeton_confirmation, ctx.cap.jetons_emis, ctx.cap.bilan,
               ctx.obs.cloturer_consultation_boucle, ctx.obs.echecs_cloture,
               ctx.n98.signaux_jointure, ctx.n98.jetons_registre,
               ctx.n98.evenements_force):
        assert callable(fn)
