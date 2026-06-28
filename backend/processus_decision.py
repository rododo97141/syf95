"""backend/processus_decision.py — Processus de décision *mesuré*.

On NE tranche QUE sur du **réalisé ET mesuré**. Entre options *prêtes*, la
**meilleure valeur mesurée gagne** — jamais l'avis. Le gagnant est **activé**,
les autres **archivés** (réversible, **rien supprimé**). Si la décision **touche
l'écosystème**, le système tranche par la valeur ; le **Créateur** peut
**override explicitement** (couche méta, tracée et réversible).

Canon (SSOT — *référencé, non dupliqué* ;
`.claude/skills/expert-95/connaissances/architecture/principles.md`) :
  - **P3** excellence vérifiable / mesurable → on décide sur la **mesure**, pas l'avis.
  - **P6** réversibilité                     → *archiver ≠ supprimer* ; tout est réversible.
  - **P7** autorisation                      → l'override est l'**autorité explicite** du Créateur.

Honnêteté technique (**P8**) : ceci est une **logique de tranche**, pas un organe
autonome réel ; « activer / archiver » décrivent des **décisions**, pas un effet
de bord matériel.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Union

#: Message renvoyé quand aucune option n'est réalisée ET mesurée.
MSG_INCOMPLET = "processus incomplet : réaliser et mesurer d'abord"


@dataclass
class Option:
    """Une option à départager.

    - ``valeur`` : score objectif dans ``[0, 1]`` ; ``None`` = **non mesuré**.
    - ``realise`` : l'option a-t-elle été **réellement réalisée** (vs projetée) ?
    Un éventuel champ « avis » est **ignoré** : on ne décide pas sur l'avis.
    """

    label: str
    valeur: Optional[float] = None
    realise: bool = False

    @property
    def prete(self) -> bool:
        """Prête à départager = **réalisée ET mesurée**."""
        return bool(self.realise) and self.valeur is not None


@dataclass
class Decision:
    """Résultat d'un :func:`decider`."""

    statut: str  # "tranché" | "incomplet"
    gagnant: Optional[str]
    par_override: bool
    autorite: str
    actions: list  # [{"action": "activer"|"archiver", "label": ...}]
    reversible: bool
    pretes: list  # labels prêts (réalisés ET mesurés)
    non_pretes: list  # labels non prêts
    message: str
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "statut": self.statut,
            "gagnant": self.gagnant,
            "par_override": self.par_override,
            "autorite": self.autorite,
            "actions": self.actions,
            "reversible": self.reversible,
            "pretes": self.pretes,
            "non_pretes": self.non_pretes,
            "message": self.message,
            "note": self.note,
        }


def _coerce(opt: Union[Option, dict]) -> Option:
    """Normalise une option (dict ou ``Option``) et valide ses invariants."""
    if isinstance(opt, Option):
        label, valeur, realise = opt.label, opt.valeur, opt.realise
    elif isinstance(opt, dict):
        label = opt.get("label")
        valeur = opt.get("valeur")
        realise = opt.get("realise", False)
    else:
        raise TypeError(f"option invalide (dict ou Option attendu) : {opt!r}")

    if not isinstance(label, str) or not label.strip():
        raise ValueError("chaque option doit avoir un 'label' non vide")
    if valeur is not None:
        if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
            raise ValueError(f"valeur de « {label} » : nombre dans [0,1] ou None")
        if not (0.0 <= float(valeur) <= 1.0):
            raise ValueError(f"valeur de « {label} » hors [0,1] : {valeur}")
    return Option(label=label, valeur=valeur, realise=bool(realise))


def _trouver(opts: list, label: str) -> Option:
    for o in opts:
        if o.label == label:
            return o
    raise ValueError(f"option introuvable pour l'override : {label!r}")


def _autorite(touche_ecosysteme: bool) -> str:
    return "système (valeur mesurée)" if touche_ecosysteme else "local (valeur mesurée)"


def _actions(gagnant: Optional[Option], opts: list) -> list:
    """Activer le gagnant, archiver les autres. Réversible, rien supprimé."""
    if gagnant is None:
        return []
    actions = [{"action": "activer", "label": gagnant.label}]
    for o in opts:
        if o is not gagnant:
            actions.append({"action": "archiver", "label": o.label})
    return actions


def decider(
    options,
    *,
    touche_ecosysteme: bool = False,
    override_createur: Optional[str] = None,
) -> Decision:
    """Tranche entre ``options`` sur la **valeur mesurée**.

    Règles :
      1. On ne tranche **que** sur du **réalisé ET mesuré**. Si **aucune** option
         n'est prête → ``statut="incomplet"`` et ``message=MSG_INCOMPLET``.
      2. Entre options prêtes, la **plus haute valeur** gagne (1ʳᵉ en cas d'égalité,
         déterministe par ordre d'entrée).
      3. Actions : **activer** le gagnant, **archiver** les autres (réversible).
      4. ``touche_ecosysteme=True`` → l'autorité est le **système** (valeur, pas avis).
      5. ``override_createur=<label>`` → le **Créateur** impose explicitement ce
         gagnant (couche méta) ; honoré même si l'option n'est pas prête, mais
         **tracé** (``note``) et **réversible**.

    :raises ValueError: liste vide, option mal formée, ou label d'override absent.
    """
    opts = [_coerce(o) for o in options]
    if not opts:
        raise ValueError("aucune option à départager")

    pretes = [o for o in opts if o.prete]
    non_pretes = [o for o in opts if not o.prete]
    labels_p = [o.label for o in pretes]
    labels_np = [o.label for o in non_pretes]

    # 5. Override explicite du Créateur — autorité méta au-dessus du système.
    if override_createur is not None:
        cible = _trouver(opts, override_createur)
        note = ""
        if not cible.prete:
            note = (
                "override sur une option non réalisée/mesurée — choix explicite "
                "du Créateur, tracé et réversible"
            )
        return Decision(
            statut="tranché",
            gagnant=cible.label,
            par_override=True,
            autorite="créateur (override explicite)",
            actions=_actions(cible, opts),
            reversible=True,
            pretes=labels_p,
            non_pretes=labels_np,
            message=f"tranché par override du Créateur : « {cible.label} »",
            note=note,
        )

    # 1. Voie système : refus tant que rien n'est réalisé ET mesuré.
    if not pretes:
        return Decision(
            statut="incomplet",
            gagnant=None,
            par_override=False,
            autorite=_autorite(touche_ecosysteme),
            actions=[],
            reversible=True,
            pretes=labels_p,
            non_pretes=labels_np,
            message=MSG_INCOMPLET,
            note=MSG_INCOMPLET,
        )

    # 2. La meilleure valeur mesurée gagne (max → 1er max = déterministe).
    gagnant = max(pretes, key=lambda o: o.valeur)
    return Decision(
        statut="tranché",
        gagnant=gagnant.label,
        par_override=False,
        autorite=_autorite(touche_ecosysteme),
        actions=_actions(gagnant, opts),
        reversible=True,
        pretes=labels_p,
        non_pretes=labels_np,
        message=f"tranché sur la valeur mesurée : « {gagnant.label} » (valeur={gagnant.valeur})",
    )
