"""
BUDGETS DE BOUCLE — tests (T1..T8 + T-COMPO).
« La boucle porte son couteau ; 98 garde les yeux. »

Ce qui est prouvé ici :
  T1  coupure exacte au plafond + coupure à la FRONTIÈRE d'une opération atomique
      (l'opération admise se termine entière, celle au-delà n'est jamais
      entamée : jamais d'état intermédiaire) ;
  T2  auto-mandat au plafond → file à-valider (rien de perdu, plan actif borné) ;
      98 voit profondeur ET tendance ;
  T3  fil par chaîne de refs à travers 2 cycles (corpus GOLDEN auto-validant :
      il ASSERTE que tout son corpus remonte au MÊME ts racine), repli EXCLUSIF,
      cas MIXTE (refs posés puis omis = UN seul compteur), message sans ref
      APRÈS coupure (rattaché au fil coupé, REJETÉ, pas de nouveau compteur),
      paire NON ordonnée ;
  T-COMPO budgets emboîtés (conversation vs tâche : coupure attribuée à la
      conversation, tâche NEUTRE, compteurs indépendants, aucun event échec) ;
  T4  stagnation : les DEUX chemins (identique coupé tôt / reformulé au plafond) ;
  T5  98 : consommé/plafond, ok-inerte vs taux, bilan-budget cassé = 98 debout ;
  T6  marqueur iteration-92 compté (statut neutre documenté) ;
  T7  lecture seule (SHA-256 des fichiers voisins inchangés) + routage
      byte-identique sous budget ;
  T8  intégration bout-en-bout (le reste de la suite prouve « zéro régression »).

Isolation : CAPTEURS_ROOT (conftest, autouse) + AGENTOS_ROOT (fixture locale).
"""
import hashlib
import json
import os
import sys

import pytest


def _organes():
    ici = os.path.dirname(os.path.abspath(__file__))       # backend/tests
    return os.path.join(os.path.dirname(os.path.dirname(ici)), "organes")


if _organes() not in sys.path:
    sys.path.insert(0, _organes())

import nexus_budget          # noqa: E402
import nexus_sense           # noqa: E402
import nexus_bus             # noqa: E402
import nexus_agentos         # noqa: E402
import nexus_98              # noqa: E402
from nexus_adaptateur import AdaptateurLoopback  # noqa: E402

import orchestrateur         # noqa: E402
from filtre_admission import Ecart, FiltreAdmission  # noqa: E402


@pytest.fixture(autouse=True)
def _agentos_isole(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTOS_ROOT", str(tmp_path / "_agentos"))


def _m(exp, dst, contenu, ts, ref=None, type="demande"):
    """Un message du schéma bus, forgé à la main pour maîtriser ts/ref."""
    return {"ts": ts, "expediteur": exp, "destinataire": dst,
            "type": type, "contenu": contenu, "ref": ref}


def _coupures_captees():
    """Nombre de capteurs de coupure budget écrits (isolés par le conftest)."""
    return nexus_98.taux_coupures(nexus_sense.lire())


# =========================================================================== #
# T1 — coupure exacte au plafond + frontière d'opération atomique
# =========================================================================== #
def test_t1_coupure_exacte_au_plafond():
    b = nexus_budget.BudgetFils(plafond=3, n_stagnation=99)
    o = "O"
    chaine = [
        _m("A", "B", "c1", o),
        _m("B", "A", "c2", "t2", ref=o),
        _m("A", "B", "c3", "t3", ref=o),
        _m("B", "A", "c4", "t4", ref=o),   # le 4e dépasse le plafond de 3
    ]
    d1, d2, d3 = (b.admettre(chaine[i]) for i in range(3))
    assert (d1.admis, d2.admis, d3.admis) == (True, True, True)
    assert (d1.consomme, d2.consomme, d3.consomme) == (1, 2, 3)

    d4 = b.admettre(chaine[3])
    assert d4.admis is False
    assert d4.coupure is True and d4.raison == "plafond"
    assert d4.consomme == 3 == d4.plafond           # consommé RÉEL == plafond
    assert d4.statut_fil == "coupe"
    assert b.consomme(("fil", o)) == 3              # pas de sur-comptage
    assert _coupures_captees() == 1                 # UN capteur de coupure, pas plus


def test_t1_coupure_a_la_frontiere_jamais_etat_intermediaire():
    """Injectée « en milieu d'opération » : la coupure prend effet à la FRONTIÈRE
    du message suivant. Le message admis se termine ENTIER (réponse publiée),
    celui au-delà du budget n'est JAMAIS entamé (ni reçu, ni répondu, ni
    compté) : aucun état intermédiaire."""
    budget = nexus_budget.BudgetFils(plafond=2, n_stagnation=99)
    b = AdaptateurLoopback("B", {"c1": "r1", "c2": "r2", "c3": "r3"})

    # 3 demandes A→B sans ref → même fil (repli : la paire {A,B}).
    for i, c in enumerate(("c1", "c2", "c3")):
        nexus_bus.publier(_m("A", "B", c, f"o{i}"))
    reponses, _ = nexus_agentos.router(nexus_bus, [b], 0, budget=budget)

    contenus_recus = [m["contenu"] for m in b.recus]
    assert contenus_recus == ["c1", "c2"]           # c3 JAMAIS remis (frontière)
    assert [r["contenu"] for r in reponses] == ["r1", "r2"]  # opérations entières
    # Aucun état intermédiaire pour c3 : compteur == nb réellement remis.
    cle = next(iter(budget.cles_comptees()))
    assert budget.consomme(cle) == 2
    assert _coupures_captees() == 1


# =========================================================================== #
# T2 — auto-mandat au plafond → file à-valider ; 98 profondeur + tendance
# =========================================================================== #
def test_t2_auto_mandat_au_plafond_va_en_file_a_valider(tmp_path):
    etat = orchestrateur.planifier(tmp_path / "etat.json")
    n_taches_avant = len(etat["taches"])
    # 5 créations toutes fortement prioritaires → toutes ADMISES par le filtre.
    ecarts = [Ecart(f"e{i}", criticite=9, frequence_usage=8, persistance=7,
                    impact_utilisateur=9, cout=2, creation=True,
                    libelle=f"création {i}") for i in range(5)]
    filtre = FiltreAdmission(seuil_base=50, capacite_file=10, budget_generation=99)

    orchestrateur.detecter_et_filtrer(etat, filtre, plafond_cycle=3, ecarts=ecarts)

    ajoutees_plan = len(etat["taches"]) - n_taches_avant
    assert ajoutees_plan == 3                        # plan actif BORNÉ au plafond
    assert len(etat["a_valider"]) == 2               # surplus en file à-valider
    assert ajoutees_plan + len(etat["a_valider"]) == 5  # RIEN de perdu
    # Aucun id de tâche dupliqué entre plan actif et file à-valider.
    ids = [t["id"] for t in etat["taches"]] + [t["id"] for t in etat["a_valider"]]
    assert len(ids) == len(set(ids))


def test_t2_98_voit_profondeur_et_tendance():
    croissant = {"a_valider": [1, 2], "a_valider_historique": [0, 1, 2]}
    assert nexus_98.profondeur_a_valider(croissant) == 2
    assert nexus_98.tendance_a_valider(croissant, k=3) is True
    assert nexus_98.signal_a_valider(croissant, k=3) is not None
    # Non monotone → PAS de tendance (pas de faux signal).
    plat = {"a_valider": [1, 2], "a_valider_historique": [2, 2, 3]}
    assert nexus_98.tendance_a_valider(plat, k=3) is False
    assert nexus_98.signal_a_valider(plat, k=3) is None
    # Série trop courte → prudence (False).
    assert nexus_98.tendance_a_valider({"a_valider_historique": [1, 2]}, k=3) is False


# =========================================================================== #
# T3 — fil par refs à travers 2 cycles (corpus GOLDEN auto-validant)
# =========================================================================== #
def _racine_corpus(msg, par_ts):
    """Remonte la chaîne de refs DANS LE CORPUS jusqu'au ts racine (auto-validant :
    prouve que le corpus du test est bien un fil à racine partagée)."""
    cur = msg
    vus = set()
    while cur.get("ref") is not None and cur["ref"] in par_ts and cur["ts"] not in vus:
        vus.add(cur["ts"])
        cur = par_ts[cur["ref"]]
    return cur["ts"]


def test_t3_fil_par_refs_a_travers_deux_cycles_golden():
    o = "O"
    cycle1 = [_m("A", "B", "d1", o),
              _m("B", "A", "r1", "t2", ref=o)]
    cycle2 = [_m("A", "B", "d2", "t3", ref="t2"),
              _m("B", "A", "r2", "t4", ref="t3")]
    corpus = cycle1 + cycle2
    par_ts = {m["ts"]: m for m in corpus}

    # GOLDEN auto-validant : TOUT le corpus remonte au MÊME ts racine.
    assert all(_racine_corpus(m, par_ts) == o for m in corpus)

    # Budget PAR VIE (une seule instance, deux cycles) : le compteur ACCUMULE.
    b = nexus_budget.BudgetFils(plafond=99)
    for m in cycle1:
        assert b.admettre(m).admis
    assert b.consomme(("fil", o)) == 2               # après cycle 1
    for m in cycle2:
        assert b.admettre(m).admis
    assert b.consomme(("fil", o)) == 4               # ACCUMULÉ au cycle 2 (pas remis à zéro)
    # Un budget « par cycle » (clé par ref immédiat / ts propre) éclaterait en
    # plusieurs compteurs : ici UN seul, car remonté à la racine.
    assert b.cles_comptees() == {("fil", o)}


def test_t3_persistance_router_par_vie_a_travers_deux_passes():
    """Même propriété au niveau routeur : un budget PERSISTANT compte à travers
    les passes ; un budget frais par passe (mutation « par cycle ») remettrait à
    zéro."""
    budget = nexus_budget.BudgetFils(plafond=99)
    b = AdaptateurLoopback("B", {"q": "r"})
    a = AdaptateurLoopback("A", {})
    dem = nexus_bus.publier(_m("A", "B", "q", "O"))
    _, off = nexus_agentos.router(nexus_bus, [a, b], 0, budget=budget)  # passe 1 : demande
    nexus_agentos.router(nexus_bus, [a, b], off, budget=budget)          # passe 2 : réponse
    cle = ("fil", dem["ts"])
    assert budget.consomme(cle) == 2                 # demande + réponse, MÊME fil


def test_t3_repli_exclusif_cas_mixte_un_seul_compteur():
    """Refs posés puis omis : UN seul compteur (repli EXCLUSIF du fil)."""
    b = nexus_budget.BudgetFils(plafond=99)
    o = "O"
    assert b.admettre(_m("A", "B", "d1", o)).admis                    # ouvre le fil
    d2 = b.admettre(_m("B", "A", "r1", "t2", ref=o))                  # ref posé
    assert d2.cle == ("fil", o) and d2.via_repli is False
    d3 = b.admettre(_m("A", "B", "d2", "t3"))                         # ref OMIS → repli
    assert d3.via_repli is True and d3.cle == ("fil", o)
    assert b.consomme(("fil", o)) == 3
    assert b.cles_comptees() == {("fil", o)}          # JAMAIS deux compteurs


def test_t3_paire_non_ordonnee():
    """Le sans-ref se rattache quel que soit le SENS (frozenset, pas tuple)."""
    b = nexus_budget.BudgetFils(plafond=99)
    o = "O2"
    assert b.admettre(_m("A", "B", "ouvre", o)).admis                # A→B ouvre
    d = b.admettre(_m("B", "A", "suite", "s2"))                      # B→A sans ref
    assert d.via_repli is True and d.cle == ("fil", o)
    assert b.cles_comptees() == {("fil", o)}          # pair non ordonnée → 1 compteur


def test_t3_sans_ref_apres_coupure_rejete_sans_nouveau_compteur():
    """Un fil coupé RESTE la clé de rattachement : un message sans ref APRÈS
    coupure est rattaché au fil coupé, REJETÉ, sans nouveau compteur ni nouvel
    event (bloqué jusqu'au reset explicite)."""
    b = nexus_budget.BudgetFils(plafond=2, n_stagnation=99)
    o = "O"
    b.admettre(_m("A", "B", "d1", o))                 # 1
    b.admettre(_m("B", "A", "r1", "t2", ref=o))       # 2 (== plafond)
    coupe = b.admettre(_m("A", "B", "d2", "t3", ref=o))  # 3 → COUPÉ
    assert coupe.coupure is True and b.est_coupe(("fil", o))
    n_events_avant = _coupures_captees()

    apres = b.admettre(_m("A", "B", "sans_ref", "t4"))   # sans ref, APRÈS coupure
    assert apres.admis is False and apres.raison == "deja_coupe"
    assert apres.cle == ("fil", o)                    # rattaché au fil coupé
    assert apres.coupure is False                     # pas de NOUVELLE coupure
    assert b.cles_comptees() == {("fil", o)}          # AUCUN nouveau compteur
    assert _coupures_captees() == n_events_avant      # pas de 2e event

    # RESET explicite : la paire se rouvre.
    b.reinitialiser_paire("A", "B")
    rouvert = b.admettre(_m("A", "B", "neuf", "t5"))
    assert rouvert.admis is True


# =========================================================================== #
# T-COMPO — budgets emboîtés (conversation vs tâche)
# =========================================================================== #
def test_compo_budgets_emboites_attribution_et_neutralite():
    bc = nexus_budget.BudgetCycle(plafond=3)          # budget d'auto-mandat (tâche)
    bf = nexus_budget.BudgetFils(plafond=2, n_stagnation=99)  # budget conversation

    # Une tâche auto-mandatée est comptée par SON budget (indépendant).
    assert bc.compter() is True
    assert bc.consomme == 1

    # Cette tâche déclenche une conversation qui atteint SON plafond → coupure.
    o = "conv"
    bf.admettre(_m("X", "Y", "c1", o))                # 1
    bf.admettre(_m("Y", "X", "c2", "t2", ref=o))      # 2 (== plafond)
    coupe = bf.admettre(_m("X", "Y", "c3", "t3", ref=o))  # 3 → COUPÉ
    assert coupe.coupure is True and coupe.raison == "plafond"

    # La coupure est attribuée à la CONVERSATION, pas à la tâche.
    assert bc.consomme == 1                           # budget tâche INTACT
    assert bf.consomme(("fil", o)) == 2               # budget conversation au plafond

    # Aucun event ÉCHEC au journal capteurs ; la coupure est NEUTRE ('ok').
    cap = nexus_sense.lire()
    assert all(e.get("statut") != "echec" for e in cap)
    evs = nexus_98.evenements_coupure(cap)
    assert len(evs) == 1                              # zéro double comptage côté 98
    assert evs[0]["raison"] == "plafond"
    assert evs[0]["consomme"] == 2 and evs[0]["plafond"] == 2  # ceux de la CONVERSATION

    # La tâche se termine en état NEUTRE « coupee » (jamais échec).
    tache = {"id": "t", "etat": "coupee"}
    assert tache["etat"] == "coupee"
    bilan = nexus_98.bilan_budget(cap)
    assert bilan["n_coupures"] == 1                   # une coupure, comptée une fois


# =========================================================================== #
# T4 — stagnation : les DEUX chemins
# =========================================================================== #
def test_t4_stagnation_identique_coupe_tot():
    b = nexus_budget.BudgetFils(plafond=40, n_stagnation=3)
    o = "O"
    b.admettre(_m("A", "B", "meme", o))                       # 1
    b.admettre(_m("B", "A", "meme", "t2", ref=o))            # 2
    d3 = b.admettre(_m("A", "B", "meme", "t3", ref=o))       # 3e identique → coupé TÔT
    assert d3.coupure is True and d3.raison == "stagnation"
    assert d3.consomme == 2 < d3.plafond                      # bien AVANT le plafond dur


def test_t4_reformulation_echappe_et_tombe_au_plafond_dur():
    b = nexus_budget.BudgetFils(plafond=3, n_stagnation=5)
    o = "O"
    contenus = ["v1", "v2", "v3", "v4"]                       # tous DIFFÉRENTS
    refs = [None, o, o, o]
    tss = [o, "t2", "t3", "t4"]
    dec = [b.admettre(_m("A", "B", contenus[i], tss[i], ref=refs[i])) for i in range(4)]
    assert [d.admis for d in dec] == [True, True, True, False]
    assert dec[-1].coupure is True and dec[-1].raison == "plafond"  # PAS stagnation


# =========================================================================== #
# T5 — 98 : consommé/plafond, ok-inerte vs taux, bilan cassé = 98 debout
# =========================================================================== #
def test_t5_98_consomme_plafond_reels():
    nexus_budget.emettre_coupure(("fil", "O"), "plafond", 3, 3)
    bb = nexus_98.bilan_budget(nexus_sense.lire())
    assert bb["n_coupures"] == 1
    (fil,) = bb["fils_coupes"].values()
    assert fil["consomme"] == 3 and fil["plafond"] == 3      # RÉELS


def test_t5_coupure_isolee_ok_inerte_seule_la_recurrence_alerte():
    assert nexus_98.signal_coupures(1) is None                # isolée = RIEN
    assert "SAIN" in nexus_98.calc_verdict([], n_coupures=1)  # ok-inerte
    assert nexus_98.signal_coupures(nexus_98.BUDGET_COUPURES_VIGILANCE) is not None
    assert "VIGILANCE" in nexus_98.calc_verdict(
        [], n_coupures=nexus_98.BUDGET_COUPURES_VIGILANCE)
    assert "ALERTE" in nexus_98.calc_verdict(
        [], n_coupures=nexus_98.BUDGET_COUPURES_ALERTE)


def test_t5_bilan_budget_casse_98_reste_debout():
    # Capteur de coupure au note ILLISIBLE + capteur mal typé : rien ne doit lever.
    nexus_sense.log_event(tache=nexus_budget.TACHE_COUPURE, statut="ok",
                          note="{ceci n'est pas du json")
    cap = nexus_sense.lire() + [{"tache": 123}, {"note": None}, "pas un dict"]
    bb = nexus_98.bilan_budget(cap, etat_boucle={"a_valider_historique": "cassé"})
    assert bb["n_coupures"] == 1                              # l'event est compté quand même
    assert bb["tendance_a_valider"] is False                 # avalé, pas propagé
    # 98 rend quand même son verdict.
    assert nexus_98.calc_verdict([], n_coupures=bb["n_coupures"]) is not None
    assert nexus_98.bilan_budget(None, None)["n_coupures"] == 0   # entrées None → neutre


# =========================================================================== #
# T6 — marqueur iteration-92 compté (statut neutre documenté)
# =========================================================================== #
def test_t6_marqueur_iteration_92_compte_et_neutre():
    ev = nexus_budget.marquer_iteration_92("raffinement expert-92")
    assert ev is not None and ev["statut"] == "ok"           # NEUTRE, jamais échec
    cap = nexus_sense.lire()
    assert nexus_98.iterations_92(cap) == 1
    assert nexus_98.bilan_budget(cap)["iterations_92"] == 1
    # Un marqueur ne crée AUCune coupure (comptes distincts).
    assert nexus_98.taux_coupures(cap) == 0


# =========================================================================== #
# T7 — lecture seule (SHA-256 voisins inchangés) + routage byte-identique
# =========================================================================== #
def _sha256(chemin):
    with open(chemin, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_t7_lecture_seule_ne_touche_aucun_fichier_voisin():
    org = _organes()
    racine = os.path.dirname(org)
    voisins = [os.path.join(org, f) for f in (
        "nexus_bus.py", "nexus_force.py", "nexus_orchestrateur.py",
        "agentos_adaptateurs.py", "nexus_sense.py", "nexus_adaptateur.py")]
    voisins += [os.path.join(racine, "backend", "moteur.py"),
                os.path.join(racine, ".claude", "skills", "memoire-beta",
                             "scripts", "memory_api.py")]
    avant = {p: _sha256(p) for p in voisins if os.path.exists(p)}

    # Opérations d'OBSERVATION/coupure (écrivent seulement dans les capteurs isolés).
    b = nexus_budget.BudgetFils(plafond=1, n_stagnation=99)
    b.admettre(_m("A", "B", "x", "O"))
    b.admettre(_m("B", "A", "y", "t2", ref="O"))      # coupe → capteur
    nexus_98.bilan_budget(nexus_sense.lire())
    nexus_budget.marquer_iteration_92("doc")

    apres = {p: _sha256(p) for p in avant}
    assert apres == avant, "un fichier voisin a été modifié (doit rester lecture seule)"


def test_t7_routage_byte_identique_sous_budget():
    """Sous le budget, le routage nommé est STRICTEMENT byte-identique au verbatim
    de l'adaptateur (aucun champ ajouté/retiré/modifié), et AUCUNE coupure."""
    contenu = {"reponse": "midi", "confiance": 0.9}
    # Vérité terrain : la réponse verbatim de l'adaptateur en SOLO.
    verite = AdaptateurLoopback("B", {"q": contenu}).sur_message(
        _m("A", "B", "q", "O"))

    b = AdaptateurLoopback("B", {"q": contenu})
    budget = nexus_budget.BudgetFils(plafond=99)       # large : rien n'est coupé
    nexus_bus.publier(_m("A", "B", "q", "O"))
    reponses, _ = nexus_agentos.router(nexus_bus, [b], 0, budget=budget)

    assert len(reponses) == 1
    assert reponses[0]["contenu"] == contenu           # contenu VERBATIM
    # même enveloppe que le verbatim (hors ts d'émission).
    sans_ts = lambda mmm: {k: v for k, v in mmm.items() if k != "ts"}
    assert sans_ts(reponses[0]) == sans_ts(verite)
    sur_bus, _ = nexus_bus.lire_depuis(0)
    assert sur_bus[-1] == reponses[0]                  # publié tel quel
    assert _coupures_captees() == 0                    # sous budget → zéro coupure


# =========================================================================== #
# T8 — intégration bout-en-bout (la suite complète prouve « zéro régression »)
# =========================================================================== #
def test_t8_integration_bout_en_bout(tmp_path):
    # La boucle tourne et expose les nouveaux champs de budget d'auto-mandat.
    etat = orchestrateur.tourner(tmp_path / "etat.json")
    for cle in ("a_valider", "a_valider_historique", "auto_mandat_cycle"):
        assert cle in etat
    assert isinstance(etat["a_valider_historique"], list) and etat["a_valider_historique"]

    # Une conversation bornée par le routeur, puis 98 rend un bilan cohérent.
    budget = nexus_budget.BudgetFils(plafond=2, n_stagnation=99)
    b = AdaptateurLoopback("B", {"q": "r"})
    for i in range(3):
        nexus_bus.publier(_m("A", "B", f"q{i}", f"o{i}"))
    nexus_agentos.router(nexus_bus, [b], 0, budget=budget)
    bb = nexus_98.bilan_budget(nexus_sense.lire(), etat)
    assert bb["n_coupures"] >= 1
    assert nexus_98.calc_verdict([], n_coupures=bb["n_coupures"]) is not None
