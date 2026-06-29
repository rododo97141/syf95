# Fiche — Voies d'amélioration de NEXUS (feuille de route priorisée)

> Source : synthèse interne (état NEXUS + acquis du jour) + scan état de l'art « self-improving
> agents 2026 » (Reflexion, ExpeL, Voyager skill-library, multi-agent reflection, harness eng.).
> Niveau de preuve : MOYEN. Priorisé par impact × faisabilité. Gardien de la réalité : on vise le
> progrès MESURABLE, pas l'activité.

## Correspondance état-de-l'art ↔ NEXUS (ce qu'on a déjà)

- **Experience store / ExpeL** (extraire des leçons des trajectoires, les rappeler) → c'est notre
  **memoire-beta + journal des capteurs**. ✅ en germe.
- **Skill library / Voyager** (réutiliser au lieu de réécrire) → nos **organes + nexus_organize**. 🟡
- **Multi-agent Reflexion** (plusieurs agents réfléchissent sous des angles différents) → exactement
  le **conseil inter-systèmes** validé aujourd'hui (Gemini conçoit, ChatGPT red-team). ✅ prouvé.
- **Harness / loop engineering** → la boucle NEXUS. 🟡 (voir [[fiche_loop_engineering]]).

## À FAIRE MAINTENANT (Cowork — faible coût, fort effet)

1. **Capteur « Impact_Utilisateur » (anti-Goodhart) — PRIORITÉ 1.**
   On a déjà le signal 👍/👎 de Kily. Le muscler comme **KPI externe** qui pondère la valeur d'une
   tâche → empêche NEXUS d'optimiser ses métriques internes au lieu du réel. C'est le correctif n°1
   de ChatGPT *et* notre gardien de la réalité. Mesurable, direct.
2. **Méthode « Conseil inter-systèmes » — formaliser.**
   Pour toute décision/design important : un modèle **construit**, un autre **red-team**, NEXUS
   tranche. Validé aujourd'hui (design robuste obtenu). Gratuit, gain de qualité immédiat.
3. **Journal de leçons (Reflexion light).**
   Après chaque tâche : 1 ligne « ce qui a marché / échoué / méthode » → lue par 96. On a déjà les
   `note` des capteurs ; en faire un usage systématique.

## À BÂTIR AU BACKEND (pilier 5 — fort effet, plus de travail)

4. **La boucle auto-mandatée** (spec robuste déjà prête, voir [[fiche_boucle_auto_mandatee]]).
5. **Moteur d'IA interchangeable** — à moitié prouvé : NEXUS a dialogué Gemini + ChatGPT aujourd'hui.
   Formaliser la consultation multi-moteurs (Claude ↔ Gemini ↔ GPT ↔ Kimi).
6. **Whisper (oreille universelle)** — corrige la limite réelle rencontrée : les vidéos « talking-head »
   illisibles. Transcription = accès au contenu parlé.

## Le filtre d'honnêteté (gardien de la réalité)

Le vrai risque commun à toutes ces voies : confondre **activité** et **progrès**. Toute amélioration
doit se prouver par une **hausse mesurée** (fiabilité, satisfaction, autonomie réelle), pas par « on
a ajouté un truc ». La voie n°1 (Impact_Utilisateur) existe précisément pour garder ce cap.

## Recommandation à 95 (96 propose, 95 décide)

Démarrer par **la voie n°1** (capteur Impact_Utilisateur) : c'est faisable ici, ça touche notre
risque le plus profond (auto-illusion / Goodhart), et c'est mesurable. Les voies 4-6 attendent le
backend.

## Triplet du coffre

{ donnée : feuille de route d'auto-amélioration priorisée (3 voies Cowork + 3 backend), pivot =
  mesurer l'impact réel · source : synthèse interne + état de l'art 2026 · niveau de preuve : MOYEN }
