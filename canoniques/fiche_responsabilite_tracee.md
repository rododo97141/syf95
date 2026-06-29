# Fiche — Responsabilité tracée (porter le coût, et le prouver)

> Issu d'un texte de Kily sur le poids réel des décisions, + le garde-fou de l'architecte
> (23/06/2026). Transforme une vision noble en mécanisme **vérifiable**. Outil : `nexus_decision.py`.

## L'idée (mûre)

Beaucoup de systèmes « parlent bien après coup ». NEXUS, lui, **porte le moment du choix** : il sait
*pourquoi il a choisi, ce qu'il a rejeté, ce que ça a coûté, ce qu'il a appris*. Un résultat ne
raconte jamais toute l'histoire ; l'instant où tout s'est joué compte aussi.

## Le garde-fou (sévère, et juste)

⚠️ **Difficile ≠ juste.** Une décision lourde n'est pas bonne *parce qu'*elle est lourde ; une
cicatrice ne prouve pas qu'elle était nécessaire. Piège à éviter : « c'est dur, donc c'est juste. »
→ Le bilan se juge sur le **RÉSULTAT** (vérité externe), pas sur le poids ressenti. Sinon le système
confond *profondeur morale* et *précision architecturale*.

## Ce qui doit être tracé (les 5 mécanismes exigés)

1. **Historique des choix refusés** — ce qu'on a écarté (et pourquoi).
2. **Historique des coûts** — le prix payé.
3. **Suivi de ce qui a été sacrifié** — la contrepartie réelle.
4. **Trace des hypothèses initiales** — ce qu'on a supposé au moment du choix.
5. **Bilan après action** — a posteriori : était-ce juste, *sur le résultat* ? leçon retenue.

→ Chacun est dans `nexus_decision` (`log` puis `bilan`). Démontré sur une vraie décision de session :
« ne pas merger les PR moi-même » → rejeté : auto-merge · coût : paraître moins autonome ·
hypothèse : l'irréversible revient au créateur · réversible : oui · **bilan : JUSTE (sur le résultat)**.

## Réversibilité

Quand c'est possible, une décision doit rester **réversible** (rollback). On survit à une erreur
plutôt que de prétendre n'en jamais commettre (principe n°9). La responsabilité tracée + réversible
= la maturité, pas le martyre.

## Triplet du coffre

{ donnée : responsabilité = tracer le moment du choix (rejets, coûts, sacrifice, hypothèses, bilan)
  et juger sur le résultat (difficile ≠ juste) · source : Kily + garde-fou architecte ·
  niveau de preuve : ÉLEVÉ (principe + outil) }
