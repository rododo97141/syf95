"""Vue Bureau 2D de l'Agent OS (nexus_bureau_agentos) — LECTURE SEULE.

Exigences vérifiées ici (spec brique 3, phase RI, à la lettre) :
  1) HTML non vide généré depuis un bus.jsonl de test (isolé via AGENTOS_ROOT) ;
  2) agents listés = EXACTEMENT les expéditeurs/destinataires distincts du bus
     de test (le broadcast "*" n'est pas un agent) ;
  3) fil dans le bon ordre + contenu tronqué + ÉCHAPPEMENT HTML (anti-injection) ;
  4) LECTURE SEULE prouvée : empreintes binaires de bus.jsonl et des fichiers
     mémoire INCHANGÉES après génération (la seule écriture est le HTML) ;
  5) robustesse : bus absent/vide → HTML « aucun agent » sans erreur ;
  6) verrou STRUCTUREL sur l'AST : la seule ouverture en écriture vit dans
     ecrire_html, et le module n'appelle JAMAIS publier / ecrire_forces.

Isolation : CAPTEURS_ROOT vient du conftest (autouse) ; AGENTOS_ROOT et
MEMOIRE_ROOT sont posés par la fixture locale — les modules relisent les
contrats env à chaque appel.
"""
import ast
import json
import os
import sys

import pytest


def _organes():
    ici = os.path.dirname(os.path.abspath(__file__))       # backend/tests
    racine = os.path.dirname(os.path.dirname(ici))          # racine du dépôt
    return os.path.join(racine, "organes")


if _organes() not in sys.path:
    sys.path.insert(0, _organes())
import nexus_bus  # noqa: E402
import nexus_force  # noqa: E402
import nexus_bureau_agentos as bureau  # noqa: E402


@pytest.fixture(autouse=True)
def _isole(tmp_path, monkeypatch):
    """Bus + mémoire isolés par test dans des dossiers temporaires jetables."""
    monkeypatch.setenv("AGENTOS_ROOT", str(tmp_path / "_agentos"))
    monkeypatch.setenv("MEMOIRE_ROOT", str(tmp_path / "memoire_data"))
    # CAPTEURS_ROOT : déjà posé par le conftest autouse (tmp_path/_capteurs).


def _pub(exp, dest, type="demande", contenu="ping", ref=None):
    """Publie un vrai message sur le bus de test (construit un bus réaliste)."""
    return nexus_bus.publier(
        nexus_bus.creer_message(exp, dest, type, contenu, ref=ref))


def _ecrire_forces(tmp_path, forces):
    d = tmp_path / "memoire_data"
    d.mkdir(parents=True, exist_ok=True)
    (d / "forces.json").write_text(
        json.dumps(forces, ensure_ascii=False), encoding="utf-8")
    return d / "forces.json"


# --------------------------------------------------------------------------- #
# 1) HTML non vide depuis un bus.jsonl de test
# --------------------------------------------------------------------------- #
def test_html_non_vide_depuis_bus_de_test():
    _pub("agentA", "agentB", "demande", "bonjour, une question ?")
    _pub("agentB", "agentA", "reponse", "voici la réponse")
    html = bureau.generer_html(bureau.synthese())
    assert html.strip()                       # non vide
    assert "<!DOCTYPE html>" in html          # page HTML complète
    assert "Bureau NEXUS" in html
    # Les agents et le contenu réels apparaissent dans la page.
    assert "agentA" in html and "agentB" in html
    assert "voici la réponse" in html
    # Autonome : aucune dépendance externe (ni CDN, ni URL absolue, ni script).
    assert "cdn" not in html.lower()
    assert "http://" not in html and "https://" not in html
    assert "<script" not in html.lower()


# --------------------------------------------------------------------------- #
# 2) agents listés = exactement les expéditeurs/destinataires distincts
# --------------------------------------------------------------------------- #
def test_agents_egaux_aux_expediteurs_destinataires_distincts():
    _pub("A", "B", "demande", "x")
    _pub("B", "A", "reponse", "y")
    _pub("C", "*", "proposition", "annonce à tous")   # broadcast
    _pub("A", "D", "demande", "z")                    # D : jamais expéditeur

    msgs = bureau.lire_bus()
    assert bureau.agents(msgs) == ["A", "B", "C", "D"]
    # Le broadcast "*" n'est JAMAIS listé comme agent.
    assert "*" not in bureau.agents(msgs)

    synth = bureau.synthese(msgs)
    assert {a["nom"] for a in synth["agents"]} == {"A", "B", "C", "D"}
    assert synth["kpis"]["nb_agents"] == 4
    assert synth["kpis"]["nb_messages"] == 4
    assert synth["kpis"]["types"] == {"demande": 2, "reponse": 1,
                                      "proposition": 1}


def test_force_et_dernier_message_dans_les_cartes(tmp_path):
    _ecrire_forces(tmp_path, {"champion": 3.5})
    _pub("champion", "public", "proposition", "je gagne")
    _pub("champion", "public", "demande", "et maintenant ?")

    synth = bureau.synthese()
    par_nom = {a["nom"]: a for a in synth["agents"]}
    # Force lue dans forces.json ; agent sans entrée = défaut assumé.
    assert par_nom["champion"]["force"] == 3.5
    assert par_nom["public"]["force"] == nexus_force.FORCE_DEFAUT
    # Dernier message ÉMIS (le plus récent où l'agent est expéditeur).
    assert par_nom["champion"]["dernier"] == "et maintenant ?"
    # 'public' n'a jamais émis : silencieux.
    assert par_nom["public"]["dernier"] is None
    # Tri par force décroissante : champion (3.5) avant public (1.0).
    assert [a["nom"] for a in synth["agents"]] == ["champion", "public"]


# --------------------------------------------------------------------------- #
# 3) fil : bon ordre + troncature + échappement HTML (anti-injection)
# --------------------------------------------------------------------------- #
def test_flux_ordre_troncature_et_echappement_anti_injection():
    _pub("A", "B", "demande", "premier")
    _pub("B", "A", "reponse", "deuxieme")
    injection = "<script>alert('xss')</script>"
    long = "z" * 300
    _pub("A", "B", "demande", injection + long)

    synth = bureau.synthese()
    # Ordre du bus préservé : le fil suit la chronologie de publication.
    contenus = [m["contenu"] for m in synth["flux"]]
    assert contenus[0] == "premier"
    assert contenus[1] == "deuxieme"
    # Troncature effective du message long.
    assert len(synth["flux"][-1]["contenu"]) <= bureau.CONTENU_MAX
    assert synth["flux"][-1]["contenu"].endswith("…")

    html = bureau.generer_html(synth)
    # Anti-injection : le <script> du contenu n'apparaît JAMAIS brut...
    assert "<script>alert" not in html
    # ... mais bien dans sa forme ÉCHAPPÉE.
    assert "&lt;script&gt;alert" in html


def test_flux_borne_aux_n_derniers_messages():
    for i in range(bureau.FLUX_MAX_DEFAUT + 15):
        _pub("A", "B", "demande", f"message {i}")
    synth = bureau.synthese()
    # Le fil ne montre que les FLUX_MAX_DEFAUT derniers, dans l'ordre.
    assert len(synth["flux"]) == bureau.FLUX_MAX_DEFAUT
    assert synth["flux"][-1]["contenu"] == \
        f"message {bureau.FLUX_MAX_DEFAUT + 14}"
    # Mais les KPIs comptent TOUS les messages, pas seulement l'extrait.
    assert synth["kpis"]["nb_messages"] == bureau.FLUX_MAX_DEFAUT + 15


# --------------------------------------------------------------------------- #
# 4) LECTURE SEULE prouvée : empreintes binaires inchangées
# --------------------------------------------------------------------------- #
def test_lecture_seule_empreintes_inchangees(tmp_path):
    _pub("A", "B", "demande", "une trace réelle")
    _pub("B", "A", "reponse", "reçu")
    chemin_forces = _ecrire_forces(tmp_path, {"A": 2.0, "B": 1.4})
    _, bus_journal = nexus_bus._chemins()

    def empreinte(p):
        with open(p, "rb") as f:
            return f.read()

    cibles = [bus_journal, str(chemin_forces)]
    avant = {p: empreinte(p) for p in cibles}
    fichiers_avant = {str(p) for p in tmp_path.rglob("*") if p.is_file()}

    # On sollicite TOUT : lecture, synthèse, rendu ET écriture du HTML.
    bureau.lire_bus()
    bureau.synthese()
    bureau.generer_html(bureau.synthese())
    sortie = tmp_path / "sortie.html"
    ecrit = bureau.ecrire_html(str(sortie))

    # Aucune source touchée : empreintes binaires identiques.
    for p, contenu in avant.items():
        assert empreinte(p) == contenu, f"source modifiée : {p}"
    # Le SEUL fichier nouveau est le HTML de sortie.
    nouveaux = {str(p) for p in tmp_path.rglob("*")
                if p.is_file()} - fichiers_avant
    assert nouveaux == {str(sortie)}
    assert ecrit == str(sortie)
    assert sortie.read_text(encoding="utf-8").strip()


# --------------------------------------------------------------------------- #
# 5) robustesse : bus absent/vide → HTML « aucun agent » sans erreur
# --------------------------------------------------------------------------- #
def test_bus_absent_donne_html_aucun_agent():
    # Aucun message publié : le journal du bus n'existe même pas.
    _, bus_journal = nexus_bus._chemins()
    assert not os.path.exists(bus_journal)

    synth = bureau.synthese()
    assert synth["kpis"] == {"nb_agents": 0, "nb_messages": 0, "types": {}}
    assert synth["agents"] == [] and synth["flux"] == []

    html = bureau.generer_html(synth)
    assert "<!DOCTYPE html>" in html          # page valide malgré le vide
    assert "aucun agent" in html.lower()      # message « aucun agent »


def test_ecrire_html_sur_bus_vide_ne_leve_pas(tmp_path):
    sortie = tmp_path / "vide.html"
    chemin = bureau.ecrire_html(str(sortie))  # ne doit pas lever
    contenu = open(chemin, encoding="utf-8").read()
    assert "aucun agent" in contenu.lower()


# --------------------------------------------------------------------------- #
# 6) verrou STRUCTUREL : seule écriture = le HTML ; jamais de publier/ecrire
# --------------------------------------------------------------------------- #
def _mode_ouverture(call):
    if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
        return call.args[1].value
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            return kw.value.value
    return "r"


def test_verrou_structurel_seule_ecriture_est_le_html():
    """Verrou STRUCTUREL (prouvé sur l'AST, pas par un if) : la SEULE
    ouverture en écriture du module vit dans ecrire_html ; aucun appel à
    publier / ecrire_forces / appliquer / log_event (donc ni bus, ni mémoire,
    ni forces ne sont jamais écrits) ; aucun import réseau/exécution."""
    source = open(os.path.join(_organes(), "nexus_bureau_agentos.py"),
                  encoding="utf-8").read()
    arbre = ast.parse(source)

    ecritures = []       # (fonction englobante, mode) des open() en écriture
    appels_attr = set()  # noms d'attributs appelés : m.publier(...), etc.
    interdits = set()    # modules importés

    def visiter(noeud, fonction):
        if isinstance(noeud, ast.FunctionDef):
            fonction = noeud.name
        if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
                and noeud.func.id == "open"):
            mode = _mode_ouverture(noeud)
            if any(c in str(mode) for c in "wax+"):
                ecritures.append((fonction, mode))
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute):
            appels_attr.add(noeud.func.attr)
        if isinstance(noeud, ast.Import):
            interdits.update(a.name.split(".")[0] for a in noeud.names)
        if isinstance(noeud, ast.ImportFrom) and noeud.module:
            interdits.add(noeud.module.split(".")[0])
        for enfant in ast.iter_child_nodes(noeud):
            visiter(enfant, fonction)

    visiter(arbre, fonction=None)

    # (a) UNE seule ouverture en écriture, dans ecrire_html, en mode "w".
    assert ecritures == [("ecrire_html", "w")], (
        f"chemins d'écriture inattendus : {ecritures}")

    # (b) le module n'appelle JAMAIS de mutateur du monde.
    mutateurs = {"publier", "ecrire_forces", "appliquer", "log_event",
                 "ecrire_html_"}  # (ecrire_html est notre propre sortie)
    assert not (appels_attr & mutateurs), (
        f"appel mutateur interdit : {sorted(appels_attr & mutateurs)}")
    assert "publier" not in appels_attr, "le bureau ne doit JAMAIS publier"

    # (c) aucun module d'exécution / réseau / destruction n'est importé.
    dangereux = {"subprocess", "socket", "urllib", "http", "requests",
                 "shutil", "ctypes"}
    assert not (interdits & dangereux), (
        f"imports interdits : {sorted(interdits & dangereux)}")

    # (d) aucun appel os destructeur.
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Attribute)
                and isinstance(noeud.value, ast.Name)
                and noeud.value.id == "os"):
            assert noeud.attr not in ("system", "remove", "rename", "unlink",
                                      "rmdir", "truncate"), (
                f"appel destructeur : os.{noeud.attr}")
