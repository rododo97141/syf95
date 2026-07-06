"""Agent OS de NEXUS — brique 4 : orchestrateur ACTIF (routage par force vivante).

Exigences vérifiées ici, à la lettre du mandat (feu vert conditionné à ces
tests) :

  1) RÉTROCOMPAT TOTALE des destinataires nommé et étoile — "role:" est un
     ajout pur, le reste ne bouge pas d'un bit ;
  2) CHOIX PAR FORCE RÉELLE : 2 agents même rôle, forces différentes déjà dans
     forces.json de test → le plus fort gagne (ε mis hors jeu, testé à part) ;
  3) ROUND-ROBIN MESURÉ : 2 agents fictifs même rôle, égalité PROVOQUÉE, sur
     40 appels chacun ~ la moitié, alternance STRICTE vérifiée ; sans cette
     injection à 2 agents, le mécanisme ne se déclenche jamais (solo → constant) ;
  4) AUCUN agent pour le rôle → ERREUR claire (ValueError nommant le rôle),
     jamais un crash muet ni un silence ;
  5) BOUT-EN-BOUT RÉEL : "role:memoire" route vers le VRAI AdaptateurMemoire
     (déjà mergé), réponse RÉELLE de recall obtenue ;
  6) VERROU ANTI-RÉGRESSION : faire varier la fiabilité journalisée d'un agent
     de « parfait » à « catastrophique » ne change PAS d'un bit la séquence de
     routage — ce test ROUGIT si quelqu'un rebranche un jour la fiabilité dans
     choisir_agent (pas juste un instantané) ; et la fiabilité ne touche pas
     forces.json (empreinte binaire inchangée après l'appel) ;
  7) CHANCE AU NOUVEAU MESURÉE : 1 agent au plafond de force + 1 nouveau (force
     par défaut, jamais appelé), même rôle → sur ~1/ε appels, le nouveau reçoit
     AU MOINS 1 appel (borne quantitative) ;
  8) ANTI-INVENTION DE VALEUR : sans donnée de force, force neutre 1.0 héritée
     de nexus_force (testée explicitement ici aussi) ;
  9) STRUCTUREL : nexus_orchestrateur.py n'écrit jamais dans forces.json, et
     choisir_agent n'a pas de paramètre fiabilité (inspection de signature +
     AST) ;
 10) suite complète VERTE, zéro régression Shu/Ha/Ri (garanti par la CI sur la
     PR + le run local complet).

Isolation : CAPTEURS_ROOT vient du conftest (autouse) ; MEMOIRE_ROOT (forces
+ fiabilité + mémoire-beta) et AGENTOS_ROOT (bus) sont posés ici par une
fixture autouse — les modules relisent ces ROOT à chaque appel, sans
monkeypatch de code.
"""
import ast
import hashlib
import inspect
import json
import os
import sys

import pytest


def _racine():
    ici = os.path.dirname(os.path.abspath(__file__))        # backend/tests
    return os.path.dirname(os.path.dirname(ici))             # racine du dépôt


def _organes():
    return os.path.join(_racine(), "organes")


if _organes() not in sys.path:
    sys.path.insert(0, _organes())
import nexus_bus            # noqa: E402
import nexus_force          # noqa: E402
import nexus_sense          # noqa: E402
import nexus_agentos        # noqa: E402
import nexus_orchestrateur  # noqa: E402
from nexus_adaptateur import AdaptateurLoopback  # noqa: E402
from agentos_adaptateurs import AdaptateurMemoire  # noqa: E402


# --------------------------------------------------------------------------- #
# Isolation (bus + forces + fiabilité + mémoire → dossiers jetables par test)
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _racines_isolees(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTOS_ROOT", str(tmp_path / "_agentos"))
    monkeypatch.setenv("MEMOIRE_ROOT", str(tmp_path / "_memoire"))


# --------------------------------------------------------------------------- #
# Aides
# --------------------------------------------------------------------------- #
def _msg(expediteur, destinataire, type="demande", contenu="", ref=None):
    return nexus_bus.creer_message(expediteur, destinataire, type, contenu, ref=ref)


def _ecrire_forces(dico):
    """Pose un forces.json de test dans MEMOIRE_ROOT (là où nexus_force lit)."""
    racine = os.environ["MEMOIRE_ROOT"]
    os.makedirs(racine, exist_ok=True)
    with open(os.path.join(racine, "forces.json"), "w", encoding="utf-8") as f:
        json.dump(dico, f, ensure_ascii=False)


def _chemin_forces():
    return os.path.join(os.environ["MEMOIRE_ROOT"], "forces.json")


def _empreinte_forces():
    """Empreinte binaire de forces.json (b'' si absent) — pour prouver qu'un
    appel ne l'a pas touché."""
    try:
        with open(_chemin_forces(), "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return "<absent>"


def _reset_fiabilite():
    chemin = os.path.join(os.environ["MEMOIRE_ROOT"], "fiabilite_agents.json")
    if os.path.exists(chemin):
        os.remove(chemin)


def _fiche(domaine, categorie, nom, contenu):
    """Écrit une vraie fiche .md dans la mémoire isolée (pour le e2e recall)."""
    dossier = os.path.join(os.environ["MEMOIRE_ROOT"], "structure",
                           domaine, categorie)
    os.makedirs(dossier, exist_ok=True)
    with open(os.path.join(dossier, nom + ".md"), "w", encoding="utf-8") as f:
        f.write(contenu)


# --------------------------------------------------------------------------- #
# 1) RÉTROCOMPAT : nommé et étoile inchangés ; roles() défaut [] (ajout pur)
# --------------------------------------------------------------------------- #
def test_retrocompat_destinataire_nomme_inchange():
    a = AdaptateurLoopback("A", {"ping": "pong"})
    b = AdaptateurLoopback("B", {})
    demande = nexus_bus.publier(_msg("B", "A", "demande", "ping"))

    reponses, offset = nexus_agentos.router(nexus_bus, [a, b], 0)
    assert len(reponses) == 1
    r = reponses[0]
    assert r["expediteur"] == "A" and r["destinataire"] == "B"
    assert r["contenu"] == "pong" and r["ref"] == demande["ts"]
    assert a.recus == [demande]  # A a reçu la demande verbatim

    # Passe suivante : B reçoit la réponse (échange nommé complet, inchangé).
    suite, offset = nexus_agentos.router(nexus_bus, [a, b], offset)
    assert suite == [] and b.recus == [r]


def test_retrocompat_broadcast_etoile_inchange():
    a = AdaptateurLoopback("A", {"hello": "ackA"})
    b = AdaptateurLoopback("B", {"hello": "ackB"})
    nexus_bus.publier(_msg("Z", "*", "demande", "hello"))

    reponses, _ = nexus_agentos.router(nexus_bus, [a, b], 0)
    assert {r["expediteur"] for r in reponses} == {"A", "B"}
    assert all(r["destinataire"] == "Z" for r in reponses)


def test_retrocompat_roles_defaut_vide_ajout_pur():
    # Un adaptateur d'avant la brique 4 ne déclare aucun rôle : ajout pur.
    assert AdaptateurLoopback("x", {}).roles() == []
    from nexus_adaptateur import NexusAdapter
    assert NexusAdapter().roles() == []
    # Un agent réel sans rôle explicite reste invisible au routage par rôle,
    # mais parfaitement routable en nommé (rétrocompat de la brique 2/HA).


# --------------------------------------------------------------------------- #
# 2) CHOIX PAR FORCE RÉELLE : le plus fort gagne (ε hors jeu, testé à part)
# --------------------------------------------------------------------------- #
def test_choix_par_force_reelle_le_plus_fort_gagne():
    _ecrire_forces({"faible": 1.4, "fort": 3.2})  # déjà dans forces.json de test
    faible = AdaptateurLoopback("faible", {}, roles=["calcul"])
    fort = AdaptateurLoopback("fort", {}, roles=["calcul"])
    forces = nexus_orchestrateur.charger_forces()
    compteur = nexus_orchestrateur.CompteurExploration(epsilon=0.0)  # ε hors jeu

    empreinte = _empreinte_forces()
    for _ in range(10):
        choisi = nexus_orchestrateur.choisir_agent(
            "calcul", [faible, fort], forces, compteur)
        assert choisi.nom() == "fort"
    # Lecture seule prouvée : la force réelle n'a pas bougé.
    assert _empreinte_forces() == empreinte


def test_choix_par_force_via_le_bus_bout_en_bout():
    """Même vérité, mais par le routeur "role:" complet."""
    _ecrire_forces({"faible": 1.4, "fort": 3.2})
    faible = AdaptateurLoopback("faible", {"q": "r-faible"}, roles=["calcul"])
    fort = AdaptateurLoopback("fort", {"q": "r-fort"}, roles=["calcul"])
    compteur = nexus_orchestrateur.CompteurExploration(epsilon=0.0)
    nexus_bus.publier(_msg("kily", "role:calcul", "demande", "q"))

    reponses, _ = nexus_agentos.router(
        nexus_bus, [faible, fort], 0, exploration=compteur)
    assert len(reponses) == 1
    assert reponses[0]["expediteur"] == "fort"       # le plus fort a répondu
    assert reponses[0]["contenu"] == "r-fort"


# --------------------------------------------------------------------------- #
# 3) ROUND-ROBIN MESURÉ : égalité provoquée → alternance stricte, ~ moitié/moitié
# --------------------------------------------------------------------------- #
def test_round_robin_egalite_repartition_mesuree():
    _ecrire_forces({"ag1": 2.0, "ag2": 2.0})  # ÉGALITÉ provoquée
    ag1 = AdaptateurLoopback("ag1", {}, roles=["r"])
    ag2 = AdaptateurLoopback("ag2", {}, roles=["r"])
    forces = nexus_orchestrateur.charger_forces()
    compteur = nexus_orchestrateur.CompteurExploration(epsilon=0.0)

    sequence = [nexus_orchestrateur.choisir_agent("r", [ag1, ag2], forces, compteur).nom()
                for _ in range(40)]

    # Chacun reçoit exactement la moitié, alternance STRICTE vérifiée.
    assert sequence.count("ag1") == 20 and sequence.count("ag2") == 20
    assert sequence == ["ag1", "ag2"] * 20

    # Sans l'injection à 2 agents, le round-robin ne se déclenche jamais :
    # un seul candidat → toujours le même (pas d'alternance à mesurer).
    solo = nexus_orchestrateur.CompteurExploration(epsilon=0.0)
    seul = [nexus_orchestrateur.choisir_agent("r", [ag1], forces, solo).nom()
            for _ in range(6)]
    assert seul == ["ag1"] * 6


# --------------------------------------------------------------------------- #
# 4) AUCUN agent pour le rôle → erreur claire, jamais silence
# --------------------------------------------------------------------------- #
def test_aucun_agent_pour_le_role_erreur_claire():
    a = AdaptateurLoopback("A", {}, roles=["autre"])
    compteur = nexus_orchestrateur.CompteurExploration()
    with pytest.raises(ValueError) as exc:
        nexus_orchestrateur.choisir_agent("memoire", [a], {}, compteur)
    assert "memoire" in str(exc.value)  # message clair : nomme le rôle manquant

    # Liste vide aussi : erreur, jamais None silencieux.
    with pytest.raises(ValueError):
        nexus_orchestrateur.choisir_agent("memoire", [], {}, compteur)


# --------------------------------------------------------------------------- #
# 5) BOUT-EN-BOUT RÉEL : role:memoire → VRAI AdaptateurMemoire → recall réel
# --------------------------------------------------------------------------- #
def test_bout_en_bout_role_memoire_vrai_adaptateur():
    _fiche("nexus", "methodes", "rare", "projet zorglubide singulier")
    memoire = AdaptateurMemoire("memoire")
    assert "memoire" in memoire.roles()  # le vrai agent déclare bien le rôle

    demande = nexus_bus.publier(_msg("kily", "role:memoire", "demande", "zorglubide"))
    reponses, _ = nexus_agentos.router(nexus_bus, [memoire], 0)

    assert len(reponses) == 1
    r = reponses[0]
    assert r["expediteur"] == "memoire" and r["destinataire"] == "kily"
    assert r["ref"] == demande["ts"]
    assert r["contenu"]["fiches"][0]["file"] == "rare.md"  # VRAI recall classé


# --------------------------------------------------------------------------- #
# 6) VERROU ANTI-RÉGRESSION : la fiabilité ne change PAS le routage, ni forces.json
# --------------------------------------------------------------------------- #
def _sequence_de_routage(nb_exceptions_ag1):
    """Journalise `nb_exceptions_ag1` exceptions pour ag1 (fiabilité EXTRÊME),
    puis produit une séquence de routage déterministe. Les 2 agents ont la MÊME
    force : la décision passe donc par le départage entre égaux (round-robin) —
    l'endroit EXACT où l'on rebrancherait naturellement la fiabilité. Si
    quelqu'un le faisait, la fiabilité catastrophique d'ag1 changerait l'ordre
    des égaux → la séquence divergerait (le verrou ROUGIT)."""
    for _ in range(nb_exceptions_ag1):
        nexus_orchestrateur.journaliser_fiabilite("ag1", "exception")
    ag1 = AdaptateurLoopback("ag1", {}, roles=["r"])
    ag2 = AdaptateurLoopback("ag2", {}, roles=["r"])
    forces = nexus_orchestrateur.charger_forces()
    compteur = nexus_orchestrateur.CompteurExploration(epsilon=0.1)
    return [nexus_orchestrateur.choisir_agent("r", [ag1, ag2], forces, compteur).nom()
            for _ in range(30)]


def test_verrou_fiabilite_ne_change_ni_routage_ni_forces():
    _ecrire_forces({"ag1": 2.0, "ag2": 2.0})  # ÉGALITÉ : le départage est exposé
    empreinte_avant = _empreinte_forces()

    _reset_fiabilite()
    seq_parfait = _sequence_de_routage(0)    # ag1 parfait (0 exception)
    _reset_fiabilite()
    seq_pourri = _sequence_de_routage(50)    # ag1 catastrophique (50 exceptions)

    # Pas UN bit de différence : la fiabilité n'entre jamais dans le routage.
    assert seq_parfait == seq_pourri
    # La variation a bien EU LIEU (sinon le test ne prouverait rien).
    assert nexus_orchestrateur.lire_fiabilite("ag1")["exception"] == 50
    # Et la force réelle n'a pas été touchée : forces.json binairement identique.
    assert _empreinte_forces() == empreinte_avant


# --------------------------------------------------------------------------- #
# 7) CHANCE AU NOUVEAU MESURÉE : sur ~1/ε appels, le nouveau reçoit ≥ 1 appel
# --------------------------------------------------------------------------- #
def test_chance_au_nouveau_mesuree():
    epsilon = 0.1
    # "vieux" au plafond de force ; "neuf" absent de forces.json → défaut 1.0.
    _ecrire_forces({"vieux": nexus_force.FORCE_MAX})
    vieux = AdaptateurLoopback("vieux", {}, roles=["r"])
    neuf = AdaptateurLoopback("neuf", {}, roles=["r"])
    forces = nexus_orchestrateur.charger_forces()
    compteur = nexus_orchestrateur.CompteurExploration(epsilon=epsilon)

    n = round(1 / epsilon)  # ~ 1/ε appels simulés
    choix = [nexus_orchestrateur.choisir_agent("r", [vieux, neuf], forces, compteur).nom()
             for _ in range(n)]

    assert choix.count("neuf") >= 1  # borne QUANTITATIVE, pas juste qualitative
    # Le nouveau n'a bien aucune force propre : c'est le défaut neutre 1.0.
    assert nexus_orchestrateur._force_de(forces, "neuf") == nexus_force.FORCE_DEFAUT


# --------------------------------------------------------------------------- #
# 8) ANTI-INVENTION DE VALEUR : force neutre 1.0 héritée de nexus_force
# --------------------------------------------------------------------------- #
def test_anti_invention_force_neutre_heritee_de_nexus_force():
    assert nexus_force.FORCE_DEFAUT == 1.0
    # Sans donnée de force : on hérite le neutre de nexus_force, jamais inventé.
    assert nexus_orchestrateur._force_de({}, "inconnu") == nexus_force.FORCE_DEFAUT
    # Valeur non numérique (bool, texte…) → défaut aussi (garde-fou du pattern).
    assert nexus_orchestrateur._force_de({"x": True}, "x") == nexus_force.FORCE_DEFAUT
    assert nexus_orchestrateur._force_de({"x": "fort"}, "x") == nexus_force.FORCE_DEFAUT

    # Et via le routage : un seul agent sans entrée de force → choisi, pas d'erreur.
    solo = AdaptateurLoopback("solo", {}, roles=["r"])
    compteur = nexus_orchestrateur.CompteurExploration(epsilon=0.0)
    assert nexus_orchestrateur.choisir_agent("r", [solo], {}, compteur).nom() == "solo"


# --------------------------------------------------------------------------- #
# 9) STRUCTUREL : jamais d'écriture forces.json ; pas de paramètre fiabilité
# --------------------------------------------------------------------------- #
def _source_orchestrateur():
    with open(os.path.join(_organes(), "nexus_orchestrateur.py"), encoding="utf-8") as f:
        return f.read()


def _mode_ouverture(appel):
    if len(appel.args) >= 2 and isinstance(appel.args[1], ast.Constant):
        return appel.args[1].value
    for kw in appel.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            return kw.value.value
    return "r"


def _noeud_fonction(arbre, nom):
    for n in ast.walk(arbre):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(f"fonction introuvable : {nom}")


def test_structurel_signature_choisir_agent_sans_fiabilite():
    params = list(inspect.signature(nexus_orchestrateur.choisir_agent).parameters)
    assert "fiabilite" not in params
    assert params == ["role", "adaptateurs", "forces", "rng_ou_compteur"]


def test_structurel_aucune_ecriture_dans_forces_json():
    source = _source_orchestrateur()
    arbre = ast.parse(source)

    # (a) aucun appel vers un écrivain de force (ecrire_forces / appliquer).
    for n in ast.walk(arbre):
        if isinstance(n, ast.Attribute):
            assert n.attr not in ("ecrire_forces", "appliquer"), (
                f"appel interdit vers un écrivain de force : {n.attr}")

    # (b) toute ouverture en ÉCRITURE ne vit que dans journaliser_fiabilite
    #     (fichier SÉPARÉ) — jamais ailleurs, jamais sur la force. Combiné à
    #     charger_forces() qui ne fait QUE lire (via nexus_force), forces.json
    #     n'est structurellement jamais écrit par ce module.
    ouvertures_ecriture = []

    def visiter(noeud, fonction):
        if isinstance(noeud, ast.FunctionDef):
            fonction = noeud.name
        if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
                and noeud.func.id == "open"):
            mode = _mode_ouverture(noeud)
            if any(c in str(mode) for c in "wax+"):
                ouvertures_ecriture.append(fonction)
        for enfant in ast.iter_child_nodes(noeud):
            visiter(enfant, fonction)

    visiter(arbre, None)
    assert ouvertures_ecriture == ["journaliser_fiabilite"], (
        f"écritures hors du journal de fiabilité : {ouvertures_ecriture}")


def test_structurel_choisir_agent_ne_touche_pas_la_fiabilite():
    """Verrou de conception : le corps de choisir_agent ne référence AUCUN nom
    lié à la fiabilité — impossible d'y relire la fiabilité par accident."""
    arbre = ast.parse(_source_orchestrateur())
    fn = _noeud_fonction(arbre, "choisir_agent")
    noms = {x.id for x in ast.walk(fn) if isinstance(x, ast.Name)}
    attrs = {x.attr for x in ast.walk(fn) if isinstance(x, ast.Attribute)}
    interdits = {"journaliser_fiabilite", "lire_fiabilite", "_lire_fiabilite_brut",
                 "_chemin_fiabilite", "observer", "fiabilite"}
    assert not (interdits & (noms | attrs))


# --------------------------------------------------------------------------- #
# Boucle d'observation : la fiabilité mécanique se journalise dans un fichier
# SÉPARÉ (réponse / exception / timeout) — vérif de complétude du dispositif.
# --------------------------------------------------------------------------- #
def test_observation_journalise_les_trois_issues_dans_fichier_separe():
    empreinte_forces = _empreinte_forces()  # <absent> ici : pas de forces.json

    issue, val = nexus_orchestrateur.observer("ag", lambda: "ok")
    assert issue == "reponse" and val == "ok"

    def _boom():
        raise RuntimeError("boum")
    issue, exc = nexus_orchestrateur.observer("ag", _boom)
    assert issue == "exception" and isinstance(exc, RuntimeError)

    def _lent():
        raise TimeoutError()
    issue, _ = nexus_orchestrateur.observer("ag", _lent)
    assert issue == "timeout"

    compteur = nexus_orchestrateur.lire_fiabilite("ag")
    assert compteur == {"reponse": 1, "exception": 1, "timeout": 1}

    # Le journal de fiabilité est un fichier SÉPARÉ ; forces.json n'a jamais été
    # créé/touché par l'observation.
    chemin_fiab = os.path.join(os.environ["MEMOIRE_ROOT"], "fiabilite_agents.json")
    assert os.path.exists(chemin_fiab)
    assert _empreinte_forces() == empreinte_forces == "<absent>"


# --------------------------------------------------------------------------- #
# LOGGER AUTO-CÂBLÉ : observer() miroite CHAQUE issue vers le capteur JSONL
# général (nexus_sense) — visible à 96/98 — SANS jamais influencer la force
# vivante. Deuxième journalisation, en plus de la fiabilité mécanique (INCHANGÉE).
# --------------------------------------------------------------------------- #
def _actions_des_trois_issues():
    """Les trois issues mécaniques, sous forme d'action() à observer :
    réponse normale, TimeoutError, Exception générique."""
    def _reponse():
        return "ok"

    def _timeout():
        raise TimeoutError()

    def _exception():
        raise RuntimeError("boum")

    return [("reponse", _reponse), ("timeout", _timeout), ("exception", _exception)]


def test_observer_capte_les_trois_issues_sans_toucher_la_fiabilite():
    """Pour les 3 issues : journaliser_fiabilite est TOUJOURS appelé comme avant
    (régression interdite) ET un événement capteur est écrit avec statut="ok",
    mode="auto", fiche=<nom>, tache="observer:<nom>", sans champ note (note=None)."""
    for issue_attendue, action in _actions_des_trois_issues():
        issue, _ = nexus_orchestrateur.observer("ag", action)
        assert issue == issue_attendue

    # (1) Fiabilité mécanique INCHANGÉE : chaque issue journalisée exactement 1×.
    assert nexus_orchestrateur.lire_fiabilite("ag") == {
        "reponse": 1, "exception": 1, "timeout": 1}

    # (2) Le capteur général a reçu UN événement par issue (3 au total), tous
    #     statut="ok" (jamais succes/echec), mode="auto", fiche=l'agent observé.
    evs = [e for e in nexus_sense.lire() if e.get("tache") == "observer:ag"]
    assert len(evs) == 3
    for e in evs:
        assert e["statut"] == "ok"        # jamais "succes"/"echec" (réservés HITL)
        assert e["mode"] == "auto"
        assert e["fiche"] == "ag"         # l'AGENT (comme fiche=expediteur du bus)
        assert e.get("note") is None      # aucun détail dupliqué depuis la fiabilité


def test_observer_capteur_defaillant_ne_casse_pas_la_boucle(monkeypatch):
    """Si nexus_sense.log_event() lève, observer() ne casse pas et renvoie quand
    même le résultat normal (issue, valeur) — l'échec du logger ne remonte JAMAIS
    à l'appelant (même doctrine que nexus_force.appliquer, qui ne lève jamais)."""
    def _log_qui_explose(*a, **k):
        raise RuntimeError("capteur en panne")

    monkeypatch.setattr(nexus_sense, "log_event", _log_qui_explose)

    # Les 3 issues restent observées normalement malgré le logger défaillant.
    issue, val = nexus_orchestrateur.observer("ag", lambda: "resultat")
    assert issue == "reponse" and val == "resultat"

    def _timeout():
        raise TimeoutError()
    issue, exc = nexus_orchestrateur.observer("ag", _timeout)
    assert issue == "timeout" and isinstance(exc, TimeoutError)

    def _boom():
        raise RuntimeError("boum")
    issue, exc = nexus_orchestrateur.observer("ag", _boom)
    assert issue == "exception" and isinstance(exc, RuntimeError)

    # Et la fiabilité mécanique, elle, a bien été journalisée (logger ≠ fiabilité).
    assert nexus_orchestrateur.lire_fiabilite("ag") == {
        "reponse": 1, "exception": 1, "timeout": 1}


def test_observer_ok_laisse_calculer_forces_inerte():
    """Extension du garde-fou « force plate == force inerte » aux événements
    observer() : un lot d'observations (statut="ok" uniquement) ne fait bouger
    AUCUNE force — aucune fiche/agent n'obtient une force ≠ FORCE_DEFAUT. La
    frontière capteur→force tient parce que calculer_forces() n'agrège QUE
    succes/echec, jamais "ok"."""
    # Pas de forces.json préexistant : l'état de production reproduit ici.
    assert nexus_force.calculer_forces() == {}

    # Un vrai lot d'observations réelles, sur plusieurs agents, les 3 issues.
    for nom in ("alpha", "beta", "gamma"):
        for _issue, action in _actions_des_trois_issues():
            nexus_orchestrateur.observer(nom, action)

    # Le capteur a bien enregistré ces événements (le lot n'est pas vide)...
    captes = [e for e in nexus_sense.lire() if e["tache"].startswith("observer:")]
    assert len(captes) == 9
    assert {e["statut"] for e in captes} == {"ok"}  # UNIQUEMENT "ok"

    # ... et pourtant calculer_forces() reste INERTE : aucune force distincte du
    # défaut n'apparaît (ni pour les agents observés, ni pour personne).
    forces = nexus_force.calculer_forces()
    assert all(v == nexus_force.FORCE_DEFAUT for v in forces.values())
    for nom in ("alpha", "beta", "gamma"):
        assert nexus_orchestrateur._force_de(forces, nom) == nexus_force.FORCE_DEFAUT
