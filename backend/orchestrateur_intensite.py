"""backend/orchestrateur_intensite.py — Dosage d'intensité (*la moins chère qui suffit*).

:func:`recommander` choisit le **palier le moins cher qui suffit**
(``SOLO`` < ``DUO`` < ``CONSEIL``), assigne un **constructeur** et un
**vérificateur toujours distincts**, et chiffre le coût en **ordres de grandeur**
(production vs orchestration) — **pas une facture**.

Règles de palier :
  - ``SOLO``    si **facile ET réversible ET enjeu bas**.
  - ``CONSEIL`` si **dur ET (enjeu haut OU irréversible OU nouveauté forte)**.
  - sinon       ``DUO``.

Canon (SSOT — *référencé, non dupliqué* ;
`.claude/skills/expert-95/connaissances/architecture/principles.md`) :
  - **P5** simplicité d'abord  → le moins cher qui suffit, pas de surdimensionnement.
  - **P3** excellence vérifiable → un **vérificateur indépendant**, toujours ≠ constructeur.
  - **P8** honnêteté technique  → « constructeur / vérificateur / conseil » sont des
    **analogies** de dosage de l'effort (pas des agents parallèles réels) ; les coûts
    sont des **ordres de grandeur relatifs**, pas un devis.
"""
from __future__ import annotations

from enum import IntEnum
from typing import Union


class Niveau(IntEnum):
    FAIBLE = 1
    MOYEN = 2
    FORT = 3


# Synonymes tolérés pour les niveaux (entrées « humaines »).
_SYNONYMES = {
    "faible": Niveau.FAIBLE, "faibles": Niveau.FAIBLE, "bas": Niveau.FAIBLE,
    "basse": Niveau.FAIBLE, "facile": Niveau.FAIBLE, "légère": Niveau.FAIBLE,
    "legere": Niveau.FAIBLE, "léger": Niveau.FAIBLE, "leger": Niveau.FAIBLE,
    "moyen": Niveau.MOYEN, "moyenne": Niveau.MOYEN, "modéré": Niveau.MOYEN,
    "modere": Niveau.MOYEN, "intermédiaire": Niveau.MOYEN,
    "fort": Niveau.FORT, "forte": Niveau.FORT, "haut": Niveau.FORT,
    "haute": Niveau.FORT, "dur": Niveau.FORT, "difficile": Niveau.FORT,
    "élevé": Niveau.FORT, "eleve": Niveau.FORT, "élevée": Niveau.FORT,
}


def niveau(x: Union[Niveau, int, float, str]) -> Niveau:
    """Normalise une entrée en :class:`Niveau`.

    Accepte un ``Niveau``, un entier ``1|2|3``, un flottant ``[0,1]`` (≤⅓ faible,
    ≥⅔ fort, sinon moyen) ou un mot-clé (« facile », « dur », « haut »…).
    """
    if isinstance(x, Niveau):
        return x
    if isinstance(x, bool):  # bool est un int : on l'écarte explicitement.
        raise TypeError("un booléen n'est pas un niveau (utiliser 'reversible' à part)")
    if isinstance(x, int):
        if x in (1, 2, 3):
            return Niveau(x)
        raise ValueError(f"niveau entier hors 1..3 : {x}")
    if isinstance(x, float):
        if 0.0 <= x <= 1.0:
            if x < 1 / 3:
                return Niveau.FAIBLE
            if x >= 2 / 3:
                return Niveau.FORT
            return Niveau.MOYEN
        raise ValueError(f"niveau flottant hors [0,1] : {x}")
    if isinstance(x, str):
        key = x.strip().lower()
        if key in _SYNONYMES:
            return _SYNONYMES[key]
        raise ValueError(f"niveau inconnu : {x!r}")
    raise TypeError(f"niveau non interprétable : {x!r}")


# Plan de chaque palier. ``mult_prod`` = facteur de production ; ``orchestration``
# = surcoût de coordination (ordre de grandeur). Le vérificateur est, par
# construction, une ressource **distincte** du constructeur.
_PLANS = {
    "SOLO": {
        "constructeur": "bâtisseur",
        "verificateur": "relecteur indépendant",
        "ressources": ["bâtisseur", "relecteur indépendant"],
        "mult_prod": 1,
        "orchestration": 0,  # aucun surcoût d'orchestration
    },
    "DUO": {
        "constructeur": "bâtisseur",
        "verificateur": "vérificateur pair",
        "ressources": ["bâtisseur", "vérificateur pair"],
        "mult_prod": 2,
        "orchestration": 1,
    },
    "CONSEIL": {
        "constructeur": "conseil (3 bâtisseurs)",
        "verificateur": "arbitre indépendant",
        "ressources": ["bâtisseur A", "bâtisseur B", "bâtisseur C", "arbitre indépendant"],
        "mult_prod": 3,
        "orchestration": 3,
    },
}


def cout_palier(tier: str, difficulte) -> dict:
    """Coût (ordre de grandeur) d'un palier pour une difficulté donnée.

    ``production = base(difficulté) × mult_prod`` ; ``orchestration`` dépend du
    seul palier. Exposé pour rendre vérifiable le principe « la moins chère qui
    suffit » (SOLO < DUO < CONSEIL à difficulté égale).
    """
    if tier not in _PLANS:
        raise ValueError(f"palier inconnu : {tier!r}")
    base = int(niveau(difficulte))  # 1..3
    plan = _PLANS[tier]
    production = base * plan["mult_prod"]
    orchestration = plan["orchestration"]
    return {
        "production": production,
        "orchestration": orchestration,
        "total": production + orchestration,
        "unite": "ordre de grandeur relatif (pas une facture)",
    }


def _choisir_tier(d: Niveau, e: Niveau, r: bool, n: Niveau):
    facile = d == Niveau.FAIBLE
    dur = d == Niveau.FORT
    enjeu_bas = e == Niveau.FAIBLE
    enjeu_haut = e == Niveau.FORT
    nouv_forte = n == Niveau.FORT

    if facile and r and enjeu_bas:
        return "SOLO", "facile + réversible + enjeu bas → le moins cher suffit"
    if dur and (enjeu_haut or not r or nouv_forte):
        motifs = [
            m for m, cond in (
                ("enjeu haut", enjeu_haut),
                ("irréversible", not r),
                ("nouveauté forte", nouv_forte),
            ) if cond
        ]
        return "CONSEIL", "dur ET (" + " ou ".join(motifs) + ") → délibération nécessaire"
    return "DUO", "ni trivial ni à haut risque → construire + vérifier en binôme"


def recommander(tache: str, difficulte, enjeu, reversible, nouveaute) -> dict:
    """Recommande le palier le **moins cher qui suffit** et son plan de ressources.

    :returns: ``{tache, tier, constructeur, verificateur, ressources,
        cout_estime{production, orchestration, total, unite}, raison, entrees}``.

    Garanties (garde-fous) :
      - ``verificateur`` est **toujours** une ressource **différente** du
        ``constructeur`` ;
      - le palier ``SOLO`` n'a **aucun surcoût d'orchestration**
        (``cout_estime["orchestration"] == 0``).
    """
    d, e, n = niveau(difficulte), niveau(enjeu), niveau(nouveaute)
    r = bool(reversible)

    tier, raison = _choisir_tier(d, e, r, n)
    plan = _PLANS[tier]
    constructeur = plan["constructeur"]
    verificateur = plan["verificateur"]
    # Invariant dur : le vérificateur n'est jamais le constructeur.
    assert verificateur != constructeur, "vérificateur == constructeur (interdit)"

    return {
        "tache": tache,
        "tier": tier,
        "constructeur": constructeur,
        "verificateur": verificateur,
        "ressources": list(plan["ressources"]),
        "cout_estime": cout_palier(tier, d),
        "raison": raison,
        "entrees": {
            "difficulte": d.name,
            "enjeu": e.name,
            "reversible": r,
            "nouveaute": n.name,
        },
    }
