#!/usr/bin/env python3
"""
NEXUS — Budgets de boucle (le COUTEAU que la boucle porte elle-même)
« La boucle porte son couteau ; 98 garde les yeux. »

Deux boucles de l'écosystème peuvent tourner sans borne à coût LLM réel :
  (a) backend/orchestrateur.py `tourner()` — 96 auto-mandate des tâches via le
      filtre d'admission : le plan peut croître sans borne ;
  (b) organes/nexus_agentos.py `router()` — les réponses publiées sont remises à
      la passe suivante : deux adaptateurs pair-à-pair peuvent se répondre
      indéfiniment.

Ce module fournit la LIMITE STRUCTURELLE, compilée localement, réutilisable par
les deux boucles :
  - un PLAFOND (compté par clé de conversation) ;
  - un COMPTEUR (par vie de la conversation, traverse les cycles) ;
  - une COUPURE (au plafond, ou anticipée sur STAGNATION) ;
  - un ÉVÉNEMENT capteur de coupure via nexus_sense — statut NEUTRE ('ok'),
    JAMAIS 'echec'. Un garde-fou mécanique qui fonctionne n'est PAS une faute :
    coupure = ok-inerte, jamais de pénalité de force (fiche=None ⇒ nexus_force
    ne s'applique pas).

DOCTRINE : ce module ne PILOTE rien et ne TOMBE jamais l'organe qui l'emploie.
Il porte le couteau ; 98 (hors boucle) observe en LECTURE SEULE le consommé,
le plafond, le taux de coupures et la profondeur/tendance de la file à-valider.

────────────────────────────────────────────────────────────────────────────
CLÉ DE CONVERSATION — le FIL
────────────────────────────────────────────────────────────────────────────
Le FIL = la chaîne de refs remontée jusqu'au ts RACINE (champ `ref` du bus,
vérifié : cf. rapport de PR). Le budget est compté par VIE du fil et traverse
les cycles. Concrètement, un message qui porte `ref` remonte parent→parent
(ts → ref → ref-du-ref …) jusqu'au message sans parent : ce ts racine EST la
clé.

REPLI si `ref` absent : paire NON ordonnée `frozenset({A, B})`, cumulative. Le
repli est EXCLUSIF du fil :
  - un message SANS ref se rattache au fil (OUVERT **ou** COUPÉ) le plus récent
    de la paire s'il en existe un ;
  - un fil COUPÉ RESTE la clé de rattachement jusqu'au RESET explicite. Prix
    nommé : une nouvelle conversation sans ref entre A et B APRÈS coupure est
    BLOQUÉE jusqu'au reset (`reinitialiser_paire`) ;
  - JAMAIS deux compteurs pour la même conversation ;
  - deux fils parallèles entre A et B : le sans-ref va au PLUS RÉCENT (compromis
    dégradé, documenté — le repli ne sait pas distinguer deux fils simultanés).

VÉRIFICATION PRÉALABLE (qui pose `ref`, cf. rapport de PR) : dans
`agentos_adaptateurs.py` (comme dans `nexus_adaptateur.py`), la SEULE pose de
`ref` est `ref=msg.get("ts")` sur CHAQUE réponse produite (`_repondre`). Donc :
les RÉPONSES portent `ref` à ~100 % ; les demandes d'OUVERTURE (créées via
`nexus_bus.creer_message`, ref=None par défaut) ne le portent pas (~0 %). Le
cas repli ne sert donc qu'à l'OUVERTURE d'un fil (et à tout message publié
ref=None) ; dès la 1re réponse, la chaîne de refs prend le relais.

────────────────────────────────────────────────────────────────────────────
CONSTANTES PROVISOIRES — points de départ PRUDENTS ET LARGES (pas dérivés des
mocks : les tests tournent en mock, le trafic réel différera). Voir le tableau
valeur / mesure / déclencheur de recalibrage dans le rapport de PR.
────────────────────────────────────────────────────────────────────────────
NOMMÉ dans la PR : ces budgets LOCAUX ne bornent PAS le coût GLOBAL (le coût est
un PRODUIT, pas une somme : chaque fil est borné, le nombre de fils ne l'est
pas). 98 affiche le consommé/plafond RÉEL par budget ; le budget-tokens est un
chantier DISTINCT, marqué.
"""
import json
import os
import sys
from collections import namedtuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# --------------------------------------------------------------------------- #
# CONSTANTES PROVISOIRES (4) — valeurs de départ prudentes et larges.
# --------------------------------------------------------------------------- #
PLAFOND_ECHANGES_FIL = 40      # échanges/fil : au plafond, le message n'est plus remis.
N_STAGNATION = 5               # contenu identique répété N fois → coupure anticipée.
PLAFOND_AUTOMANDAT_CYCLE = 3   # créations auto-mandatées/cycle au plan actif ; surplus → file à-valider.

# Préfixes STABLES des capteurs (source unique — 98 filtre dessus, LECTURE SEULE).
TACHE_COUPURE = "budget:coupure"        # capteur de coupure (statut 'ok', neutre).
TACHE_ITERATION_92 = "iteration-92"     # marqueur pour le futur runner d'expert-92.


# --------------------------------------------------------------------------- #
# Capteur (nexus_sense) — import paresseux, JAMAIS bloquant (comme la boucle).
# --------------------------------------------------------------------------- #
def _sense():
    """Import paresseux de nexus_sense (respecte CAPTEURS_ROOT). Renvoie None si
    indisponible : émettre un capteur ne doit JAMAIS casser la boucle."""
    try:
        import nexus_sense
        return nexus_sense
    except Exception:
        return None


def emettre_coupure(cle, raison, consomme, plafond, capteur=None):
    """Émet UN capteur de coupure — statut NEUTRE ('ok'), JAMAIS 'echec' (une
    coupure est un garde-fou qui a fonctionné, pas un dommage). fiche=None : la
    force vivante (nexus_force) ne s'y applique PAS — aucune pénalité de force.
    Le `note` porte le consommé/plafond RÉELS que 98 lira. Ne lève JAMAIS."""
    cap = capteur or _sense()
    if cap is None:
        return None
    try:
        note = json.dumps(
            {"cle": _cle_lisible(cle), "raison": raison,
             "consomme": consomme, "plafond": plafond},
            ensure_ascii=False,
        )
        return cap.log_event(
            tache=TACHE_COUPURE,
            statut="ok",          # NEUTRE — jamais 'echec' (ok-inerte)
            mode="auto",
            feedback=None,        # aucun jugement de valeur (anti-Goodhart)
            impact=None,
            fiche=None,           # AUCUNE pénalité de force (fiche vide)
            note=note,
        )
    except Exception:
        return None


def marquer_iteration_92(detail="", statut="ok", capteur=None):
    """Marqueur d'itération pour le FUTUR runner d'expert-92 (raffinement).

    L'organe 92 est une skill SANS runner codé : HORS périmètre code. Ce marqueur
    NEUTRE ('ok', jamais 'echec') est déposé pour qu'un futur runner le compte,
    et 98 le tient au compteur avec un statut VISIBLE-SI-LA-SUPERVISION-TRACE
    (affiché seulement s'il existe des marqueurs — même logique que le ratio
    HITL). Une coupure codée (`emettre_coupure`) sert AUSSI de marqueur au futur
    runner de 92. Ne lève JAMAIS."""
    cap = capteur or _sense()
    if cap is None:
        return None
    try:
        tache = TACHE_ITERATION_92 if not detail else f"{TACHE_ITERATION_92} {detail}"
        return cap.log_event(tache=tache, statut=statut, mode="auto",
                             feedback=None, impact=None, fiche=None)
    except Exception:
        return None


def _cle_lisible(cle):
    """Rend une clé de fil sérialisable JSON (les frozenset ne le sont pas)."""
    try:
        if isinstance(cle, tuple) and len(cle) == 2:
            genre, val = cle
            if isinstance(val, frozenset):
                return [genre, sorted(map(str, val))]
            return [genre, val]
    except Exception:
        pass
    return str(cle)


# --------------------------------------------------------------------------- #
# Décision d'admission d'un message dans son fil.
# --------------------------------------------------------------------------- #
Decision = namedtuple(
    "DecisionBudget",
    ["admis", "cle", "via_repli", "coupure", "raison",
     "consomme", "plafond", "statut_fil"],
)


class BudgetFils:
    """Budget d'échanges par VIE du fil (traverse les cycles).

    Une instance PERSISTE d'une passe/cycle à l'autre (comme la politique
    d'exploration du routeur) : c'est ce qui rend le budget « par vie » et non
    « par cycle ». Chaque message observé via `admettre(msg)` est rattaché à SON
    fil (chaîne de refs, ou repli frozenset), compté, et coupé au plafond ou sur
    stagnation. La coupure émet un capteur NEUTRE (jamais échec) et ne pilote
    rien : `admettre` renvoie seulement une Decision, l'appelant décide de ne
    plus remettre le message.
    """

    def __init__(self, plafond=PLAFOND_ECHANGES_FIL, n_stagnation=N_STAGNATION,
                 capteur=None):
        self.plafond = plafond
        self.n_stagnation = n_stagnation
        self._capteur = capteur            # injectable pour les tests
        self._parent = {}                  # ts -> ref (chaîne remontée)
        self._compteurs = {}               # cle_fil -> nb de messages ADMIS (vie du fil)
        self._coupes = set()               # cle_fil coupés (restent clé de rattachement)
        self._stagnation = {}              # cle_fil -> {empreinte_contenu: occurrences}
        self._dernier_fil_paire = {}       # frozenset(A,B) -> cle_fil le plus récent

    # -- lectures (aussi utiles à 98 et aux tests) ------------------------- #
    def consomme(self, cle):
        return self._compteurs.get(cle, 0)

    def est_coupe(self, cle):
        return cle in self._coupes

    def statut(self, cle):
        return "coupe" if cle in self._coupes else (
            "ouvert" if cle in self._compteurs else "inconnu")

    def cles_comptees(self):
        """Ensemble des clés de fils ayant AU MOINS un message compté. Sert à
        prouver l'invariant « jamais deux compteurs pour la même conversation »."""
        return set(self._compteurs)

    # -- cœur -------------------------------------------------------------- #
    def admettre(self, msg):
        """Observe UN message, met à jour la chaîne et le compteur de SON fil,
        et tranche. La coupure prend effet à la FRONTIÈRE d'un message (avant
        toute remise) : une opération admise se termine entière, une opération
        au-delà du budget n'est jamais entamée — jamais d'état intermédiaire.
        """
        exp = msg.get("expediteur")
        dst = msg.get("destinataire")
        ref = msg.get("ref")
        ts = msg.get("ts")
        contenu = msg.get("contenu")

        # 1) Enregistrer le lien de chaîne (ts -> parent), pour les remontées.
        if ts is not None and ts not in self._parent:
            self._parent[ts] = ref

        # 2) Clé du fil (chaîne de refs, sinon repli frozenset).
        cle, via_repli = self._resoudre_cle(exp, dst, ref, ts)

        # 3) La clé devient le fil LE PLUS RÉCENT de la paire (ouvert OU coupé).
        self._dernier_fil_paire[frozenset((exp, dst))] = cle

        # 4) Fil déjà coupé → rejet SEC : pas de 2e compteur, pas de 2e event.
        if cle in self._coupes:
            return Decision(False, cle, via_repli, False, "deja_coupe",
                            self._compteurs.get(cle, 0), self.plafond, "coupe")

        # 5) STAGNATION (coupure anticipée, exact match seulement) : la
        #    reformulation légère échappe et n'est rattrapée que par le plafond
        #    dur (défense en profondeur documentée).
        if self._stagne(cle, contenu):
            return self._couper(cle, "stagnation", via_repli)

        # 6) PLAFOND dur.
        if self._compteurs.get(cle, 0) >= self.plafond:
            return self._couper(cle, "plafond", via_repli)

        # 7) ADMIS : on incrémente le compteur du fil (par vie).
        self._compteurs[cle] = self._compteurs.get(cle, 0) + 1
        return Decision(True, cle, via_repli, False, None,
                        self._compteurs[cle], self.plafond, "ouvert")

    def _couper(self, cle, raison, via_repli):
        """Coupe le fil : marque coupé, émet le capteur NEUTRE, renvoie la
        Decision. Le consommé RÉEL est le compteur au moment de la coupure
        (= plafond pour un plafond dur ; < plafond pour une stagnation)."""
        self._coupes.add(cle)
        consomme = self._compteurs.get(cle, 0)
        emettre_coupure(cle, raison, consomme, self.plafond, capteur=self._capteur)
        return Decision(False, cle, via_repli, True, raison,
                        consomme, self.plafond, "coupe")

    def _stagne(self, cle, contenu):
        """True quand un contenu EXACT atteint N occurrences dans le fil."""
        empreinte = self._empreinte(contenu)
        if empreinte is None:
            return False
        table = self._stagnation.setdefault(cle, {})
        table[empreinte] = table.get(empreinte, 0) + 1
        return table[empreinte] >= self.n_stagnation

    @staticmethod
    def _empreinte(contenu):
        """Empreinte stable d'un contenu pour la stagnation (exact match)."""
        try:
            hash(contenu)
            return ("h", contenu)
        except TypeError:
            try:
                return ("j", json.dumps(contenu, sort_keys=True, ensure_ascii=False))
            except Exception:
                return None

    def _resoudre_cle(self, exp, dst, ref, ts):
        """Renvoie (cle_fil, via_repli). Fil par chaîne de refs si `ref` présent ;
        sinon repli EXCLUSIF sur la paire non ordonnée."""
        if ref is not None:
            return ("fil", self._racine(ts)), False
        paire = frozenset((exp, dst))
        if paire in self._dernier_fil_paire:
            # Repli : rattachement au fil le plus récent (OUVERT ou COUPÉ) de la
            # paire — jamais un 2e compteur pour la même conversation.
            return self._dernier_fil_paire[paire], True
        if ts is not None:
            # Aucun fil connu pour la paire : ce message SANS ref OUVRE un fil
            # dont la racine est son propre ts (les réponses y remonteront).
            return ("fil", ts), False
        return ("paire", paire), True   # ultime repli défensif (ts absent)

    def _racine(self, ts):
        """Remonte parent→parent jusqu'au ts racine (parent None ou inconnu).
        Garde-fou anti-cycle : un ts déjà vu arrête la remontée."""
        vus = set()
        courant = ts
        while courant is not None and courant not in vus:
            vus.add(courant)
            parent = self._parent.get(courant)
            if parent is None:
                break
            courant = parent
        return courant

    def reinitialiser_paire(self, a, b):
        """RESET explicite d'une paire : oublie le fil de rattachement et
        découpe/remet à zéro le fil associé. C'est le SEUL moyen de rouvrir une
        conversation sans ref entre A et B après une coupure."""
        paire = frozenset((a, b))
        cle = self._dernier_fil_paire.pop(paire, None)
        if cle is not None:
            self._coupes.discard(cle)
            self._compteurs.pop(cle, None)
            self._stagnation.pop(cle, None)
        return cle


class BudgetCycle:
    """Budget d'auto-mandat PAR CYCLE (compteur borné, remis à zéro chaque
    cycle). Ce n'est PAS une coupure : au plafond, l'appelant redirige vers la
    file à-valider (rien de perdu, plan actif borné) — d'où l'absence de capteur
    de coupure ici. Compteur INDÉPENDANT du BudgetFils (aucun double comptage)."""

    def __init__(self, plafond=PLAFOND_AUTOMANDAT_CYCLE):
        self.plafond = plafond
        self._n = 0

    @property
    def consomme(self):
        return self._n

    def nouvelle_periode(self):
        """Ouvre un nouveau cycle : le budget par cycle repart à zéro."""
        self._n = 0

    def place_disponible(self):
        return self._n < self.plafond

    def compter(self):
        """Compte une unité si de la place reste. Renvoie True si l'unité entre
        dans le budget (→ plan actif), False si le plafond est atteint
        (→ file à-valider)."""
        if self._n >= self.plafond:
            return False
        self._n += 1
        return True
