"""backend/evaluateur_ouvert.py — Évaluateur de tâches ouvertes (filtre **consultatif** de 96).

AXIOME (à inscrire au fer rouge) — **on AGRÈGE des préférences, on ne MESURE PAS
un réel.** Une comparaison « A > B » est un *jugement*, pas une mesure physique.
Donc : (1) on compare toujours à une **baseline forte**, **jamais à un homme de
paille** ; (2) on **refuse de prétendre mesurer** quand le modèle ne le permet
pas — si le MLE Bradley-Terry **diverge** (séparation), on le **signale** au lieu
d'inventer des nombres.

Rôle : **filtre consultatif de l'organe 96**. Il **propose** un classement et des
signaux ; **96 propose, ne décide JAMAIS**. La sortie de
:func:`recommander_par_preferences` est une **RECOMMANDATION**, pas une décision
(``decide=False``). La *décision* mesurée, elle, relève de `processus_decision.py`
(valeur mesurée) ou du Créateur — pas d'ici.

Trois lectures complémentaires du même jeu de préférences :
  - **Bradley-Terry** — force latente + ``P(A>B)``, *quand* le MLE existe (graphe de
    dominance fortement connexe, condition de Ford). Sinon → **divergence signalée**.
  - **Copeland** — score ordinal robuste (``#battus − #perdants`` en face-à-face),
    insensible aux marges et aux cycles.
  - **Cycles de préférence** (A>B>C>A) — rapportés comme **SIGNAL** d'intransitivité,
    *pas* comme du bruit à lisser.
  - **Alerte** explicite si Bradley-Terry et Copeland **divergent** en tête.

Canon (SSOT — *référencé, non dupliqué* ;
`.claude/skills/expert-95/connaissances/architecture/principles.md`) :
  - **P3** excellence vérifiable → on n'affirme **pas plus** que ce que les données
    permettent (séparation = on ne chiffre pas).
  - **P8** honnêteté technique  → agrégation de préférences **≠** mesure d'un réel ;
    « évaluateur » est un calcul, **pas** un agent autonome.

Dépendances : **bibliothèque standard uniquement** (aucune dépendance lourde).
"""
from __future__ import annotations

from collections import deque
from typing import Any, Iterable, Union

Comparaison = Union[tuple, list, dict]


# --------------------------------------------------------------------------
# Compilation / validation des entrées
# --------------------------------------------------------------------------
def _paire(comp: Comparaison):
    """Normalise une comparaison en couple ``(gagnant, perdant)``."""
    if isinstance(comp, dict):
        if "gagnant" in comp and "perdant" in comp:
            return comp["gagnant"], comp["perdant"]
        raise ValueError(f"comparaison dict attend 'gagnant'/'perdant' : {comp!r}")
    if isinstance(comp, (tuple, list)) and len(comp) == 2:
        return comp[0], comp[1]
    raise ValueError(f"comparaison invalide (couple gagnant>perdant attendu) : {comp!r}")


def _compiler(options: Iterable, comparaisons: Iterable):
    """Valide et compile les entrées.

    :returns: ``(beat, wins, opts, n_comparaisons)`` où ``beat[a][b]`` = nombre de
        fois où *a* a battu *b*, ``wins[a]`` = victoires de *a*, ``opts`` = options
        (ordre préservé), ``n_comparaisons`` = nombre de comparaisons retenues.
    :raises ValueError: option dupliquée, label inconnu, ou auto-comparaison.
    """
    opts = list(options)
    if not opts:
        raise ValueError("aucune option fournie")
    if len(set(opts)) != len(opts):
        raise ValueError("options en double interdites")
    su = set(opts)

    beat = {a: {b: 0 for b in opts if b != a} for a in opts}
    wins = {a: 0 for a in opts}
    n = 0
    for comp in comparaisons:
        g, p = _paire(comp)
        if g not in su or p not in su:
            raise ValueError(f"comparaison hors options : {g!r} > {p!r}")
        if g == p:
            raise ValueError(f"auto-comparaison interdite : {g!r} > {p!r}")
        beat[g][p] += 1
        wins[g] += 1
        n += 1
    return beat, wins, opts, n


# --------------------------------------------------------------------------
# Composantes fortement connexes (Kosaraju, itératif) — outil partagé
# --------------------------------------------------------------------------
def _scc(noeuds: list, adj: dict) -> list:
    """Composantes fortement connexes d'un graphe orienté (``adj`` : nœud → set)."""
    visite = set()
    ordre = []
    for depart in noeuds:
        if depart in visite:
            continue
        pile = [(depart, iter(adj[depart]))]
        visite.add(depart)
        while pile:
            noeud, it = pile[-1]
            avance = False
            for suiv in it:
                if suiv not in visite:
                    visite.add(suiv)
                    pile.append((suiv, iter(adj[suiv])))
                    avance = True
                    break
            if not avance:
                ordre.append(noeud)
                pile.pop()

    radj = {n: set() for n in noeuds}
    for u in noeuds:
        for v in adj[u]:
            radj[v].add(u)

    vus = set()
    comps = []
    for noeud in reversed(ordre):
        if noeud in vus:
            continue
        pile = [noeud]
        vus.add(noeud)
        comp = []
        while pile:
            x = pile.pop()
            comp.append(x)
            for y in radj[x]:
                if y not in vus:
                    vus.add(y)
                    pile.append(y)
        comps.append(comp)
    return comps


def _ordre_domination(noeuds: list, adj: dict) -> list:
    """Groupes (SCC) ordonnés du dominant au dominé (tri topologique du condensé)."""
    comps = _scc(noeuds, adj)
    cid = {n: i for i, c in enumerate(comps) for n in c}
    cadj = {i: set() for i in range(len(comps))}
    indeg = {i: 0 for i in range(len(comps))}
    for u in noeuds:
        for v in adj[u]:
            iu, iv = cid[u], cid[v]
            if iu != iv and iv not in cadj[iu]:
                cadj[iu].add(iv)
                indeg[iv] += 1
    file = deque(sorted(i for i in indeg if indeg[i] == 0))
    ordre = []
    while file:
        i = file.popleft()
        ordre.append(i)
        for j in sorted(cadj[i]):
            indeg[j] -= 1
            if indeg[j] == 0:
                file.append(j)
    return [sorted(comps[i], key=str) for i in ordre]


def _exemple_cycle(comp: list, adj: dict) -> list:
    """Extrait un cycle représentatif d'une SCC (pour lisibilité humaine)."""
    membres = set(comp)
    cur = sorted(comp, key=str)[0]
    chemin = [cur]
    pos = {cur: 0}
    aretes_vues = set()
    while True:
        for s in sorted((s for s in adj[cur] if s in membres), key=str):
            if s in pos:  # on referme un cycle
                return chemin[pos[s]:] + [s]
            if (cur, s) not in aretes_vues:
                aretes_vues.add((cur, s))
                pos[s] = len(chemin)
                chemin.append(s)
                cur = s
                break
        else:  # aucun successeur exploitable → repli
            base = sorted(comp, key=str)
            return base + [base[0]]


# --------------------------------------------------------------------------
# Briques publiques
# --------------------------------------------------------------------------
def detecter_separation(options, comparaisons) -> dict:
    """Détecte la **séparation** (condition de Ford) : le graphe de dominance
    (``a→b`` si *a* a battu *b* au moins une fois) est-il **fortement connexe** ?

    Non fortement connexe ⇒ le MLE Bradley-Terry **n'existe pas** (forces non
    finies) : on le **signale**. ``groupes_domination`` ordonne les groupes du
    dominant au dominé.
    """
    beat, wins, opts, _ = _compiler(options, comparaisons)
    adj = {a: {b for b in beat[a] if beat[a][b] >= 1} for a in opts}
    comps = _scc(opts, adj)
    separation = len(comps) > 1
    return {
        "separation": separation,
        "n_composantes": len(comps),
        "groupes_domination": _ordre_domination(opts, adj) if separation else [list(opts)],
    }


def detecter_cycles(options, comparaisons) -> list:
    """Cycles de préférence au sens **majoritaire** (``a→b`` si *a* bat *b* en
    face-à-face). Toute SCC de taille ≥ 2 est un cycle → renvoyé comme **SIGNAL**.
    """
    beat, wins, opts, _ = _compiler(options, comparaisons)
    adj = {a: {b for b in beat[a] if beat[a][b] > beat[b][a]} for a in opts}
    cycles = []
    for c in _scc(opts, adj):
        if len(c) >= 2:
            cycles.append({"membres": sorted(c, key=str), "exemple": _exemple_cycle(c, adj)})
    return cycles


def copeland(options, comparaisons) -> dict:
    """Score de Copeland : ``#adversaires battus − #adversaires perdants`` (majorité
    face-à-face). Ordinal, **robuste aux marges et aux cycles**.
    """
    beat, wins, opts, _ = _compiler(options, comparaisons)
    scores = {o: 0 for o in opts}
    for i in range(len(opts)):
        for j in range(i + 1, len(opts)):
            a, b = opts[i], opts[j]
            na, nb = beat[a][b], beat[b][a]
            if na == nb:  # pas de comparaison, ou égalité stricte → 0
                continue
            if na > nb:
                scores[a] += 1
                scores[b] -= 1
            else:
                scores[b] += 1
                scores[a] -= 1
    classement = sorted(opts, key=lambda o: (-scores[o], str(o)))
    return {"scores": scores, "classement": classement}


def bradley_terry(options, comparaisons, *, max_iter: int = 10000, tol: float = 1e-10) -> dict:
    """Estime le modèle de Bradley-Terry par l'algorithme MM (Zermelo/Ford).

    ``P(i>j) = π_i / (π_i + π_j)``. Renvoie les forces ``π`` (normalisées, somme 1)
    et la matrice ``p``. **Si séparation** (MLE non fini) → ``convergence=False``,
    ``diverge=True``, ``forces=None``, ``p=None`` : **on ne chiffre pas** ce qui
    n'existe pas.
    """
    beat, wins, opts, _ = _compiler(options, comparaisons)
    if len(opts) < 2:
        seul = {opts[0]: 1.0} if opts else {}
        return {"convergence": True, "diverge": False, "forces": seul, "p": {}, "iterations": 0}

    if detecter_separation(options, comparaisons)["separation"]:
        return {
            "convergence": False,
            "diverge": True,
            "forces": None,
            "p": None,
            "iterations": 0,
            "raison": "séparation : le MLE Bradley-Terry n'existe pas (forces non finies)",
        }

    pi = {o: 1.0 for o in opts}
    iters = 0
    converge = False
    for iters in range(1, max_iter + 1):
        nouveau = {}
        for i in opts:
            denom = 0.0
            for j in opts:
                if j == i:
                    continue
                nij = beat[i][j] + beat[j][i]
                if nij:
                    denom += nij / (pi[i] + pi[j])
            # Séparation écartée ⇒ graphe fortement connexe ⇒ wins[i] > 0 et denom > 0.
            nouveau[i] = wins[i] / denom
        s = sum(nouveau.values())
        for i in opts:
            nouveau[i] /= s
        diff = max(abs(nouveau[i] - pi[i]) for i in opts)
        pi = nouveau
        if diff < tol:
            converge = True
            break

    p = {i: {j: pi[i] / (pi[i] + pi[j]) for j in opts if j != i} for i in opts}
    return {"convergence": converge, "diverge": False, "forces": pi, "p": p, "iterations": iters}


# --------------------------------------------------------------------------
# Fonction appelée par 96 — RECOMMANDATION, jamais une décision
# --------------------------------------------------------------------------
def recommander_par_preferences(options, comparaisons) -> dict:
    """Agrège les préférences et **recommande** (sans jamais décider) pour 96.

    :returns: dict ``{nature, decide, appelant, verdict, p, cycles, divergence,
        avertissements, bradley_terry, copeland}``. ``decide`` est **toujours**
        ``False`` : **96 propose, ne décide jamais.**
    """
    beat, wins, opts, n_comp = _compiler(options, comparaisons)

    sep = detecter_separation(options, comparaisons)
    cyc = detecter_cycles(options, comparaisons)
    cop = copeland(options, comparaisons)
    bt = bradley_terry(options, comparaisons)

    cop_rank, cop_scores = cop["classement"], cop["scores"]
    top = cop_scores[cop_rank[0]] if cop_rank else None
    tetes_cop = [o for o in opts if cop_scores[o] == top]
    tete_cop = cop_rank[0] if len(tetes_cop) == 1 else None

    avert = []
    if sep["separation"]:
        avert.append(
            "séparation détectée : le MLE Bradley-Terry diverge (forces non finies) "
            "— P(A>B) non calculable honnêtement ; recommandation ordinale (Copeland) "
            "seulement."
        )
    if cyc:
        membres = ", ".join("{" + ", ".join(map(str, c["membres"])) + "}" for c in cyc)
        avert.append(
            f"cycle(s) de préférence détecté(s) {membres} — SIGNAL d'intransitivité "
            "réelle des préférences, pas du bruit à lisser."
        )

    bt_vs_cop = False
    tete_bt = None
    if bt["convergence"] and bt["forces"] is not None:
        bt_rank = sorted(opts, key=lambda o: (-bt["forces"][o], str(o)))
        tete_bt = bt_rank[0]
        if tete_cop is not None and tete_bt != tete_cop:
            bt_vs_cop = True
            avert.append(
                f"divergence Bradley-Terry / Copeland en tête : « {tete_bt} » (BT) vs "
                f"« {tete_cop} » (Copeland) — méthodes en désaccord, prudence accrue."
            )

    if n_comp == 0 or len(opts) < 2:
        confiance = "indéterminée"
    elif cyc or bt_vs_cop:
        confiance = "faible"
    elif sep["separation"]:
        confiance = "moyenne"
    else:
        confiance = "forte"

    if tete_cop is None and not cyc and n_comp > 0:
        avert.append("pas de tête nette (égalité Copeland) — recommandation non tranchée.")

    concordant = bool(bt["convergence"] and not bt_vs_cop and not sep["separation"] and not cyc)
    verdict = {
        "classement": cop_rank,
        "tete": tete_cop,
        "confiance": confiance,
        "source": "Copeland (ordinal robuste)"
        + (" — concordant avec Bradley-Terry" if concordant else ""),
    }
    divergence = {
        "separation": sep["separation"],
        "bradley_terry_diverge": bt["diverge"],
        "groupes_domination": sep["groupes_domination"] if sep["separation"] else None,
        "bt_vs_copeland": bt_vs_cop,
        "tete_bt": tete_bt,
        "tete_copeland": tete_cop,
    }
    return {
        "nature": "recommandation",
        "decide": False,  # 96 propose, ne décide JAMAIS
        "appelant": "organe 96 — filtre consultatif (96 propose, ne décide jamais)",
        "verdict": verdict,
        "p": bt["p"],  # None en cas de séparation : on ne chiffre pas l'inexistant
        "cycles": cyc,
        "divergence": divergence,
        "avertissements": avert,
        "bradley_terry": {
            "convergence": bt["convergence"],
            "forces": bt["forces"],
            "iterations": bt.get("iterations", 0),
        },
        "copeland": cop,
    }
