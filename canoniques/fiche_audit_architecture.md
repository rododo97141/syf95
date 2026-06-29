# Fiche — Audit sévère de l'architecture (bloc par bloc)

> Audit en rôle d'architecte-auditeur externe (23/06/2026), sur le schéma « écosystème cognitif
> vivant » (version finale théorie). Verdict : carte très convaincante (vision), mais pas encore
> une architecture d'exécution robuste. Il manque le **sol dur**. Scores : lisibilité 8,5 ·
> cohérence 8 · pertinence 9 · robustesse d'implémentation 5,5 · **falsifiabilité 4,5**.

## Verdicts bloc par bloc

| Bloc | Verdict | Raison / action |
|---|---|---|
| **Vérité externe** | ➕ **AJOUTER** | *Manque n°1.* Bloc qui valide/invalide depuis l'extérieur (résultats réels, ablation, comparaison à conditions égales, falsifiabilité, jugement du monde). Sans lui, le système semble se suffire. |
| **96 — Réacteur** | ✂️ SCINDER | Trop chargé = goulot épistémique (si 96 dérive, tout dérive avec cohérence). Garder analyse/sens ; **comparaison → ZÉRO** ; **détection biais/menaces → 98**. |
| **ZÉRO — Arène** | 🎯 RESSERRER | Rôle ambigu. Un seul mandat tranché : *confronter → trier par valeur → sélectionner*. Absorbe la comparaison de 96. |
| **Mémoire · Capteurs · SOURCE-1** | 🧱 FRONTIÈRES DURES | Chevauchement. Mémoire = passé (conserve+relie) · Capteurs = présent (mesure le réel) · SOURCE-1 = puissance (calcule/simule, **ne juge pas**). |
| **Systèmes passagers** | 🧩 COMPLÉTER | Manque le cycle de vie : création → **qui autorise** → mesure du succès → retrait → ce qui est conservé en mémoire. |
| **92 — Perfectionneur** | ⚠️ SURVEILLER | Risque de doublon avec la boucle d'évolution. Rôle strict : peaufiner un *livrable*, pas faire évoluer le *système*. |
| Créateur · Utilisateur · Constitution · 95 · 97 · cycle 9 temps · principes · méta-évolution | ✅ GARDER | Solides. La stratification est le point fort. |

**Rien à supprimer purement** : le problème n'est pas l'excès de blocs, mais des **responsabilités
diffuses** + un **bloc manquant**.

## Le bloc à ajouter : VÉRITÉ EXTERNE (le banc d'épreuve)

Ce qui tranche entre « ça SEMBLE bon » et « ça EST bon ». Non négociable, visible, externe :
- **résultats réels** mesurés (pas l'impression) — `nexus_compare` ;
- **ablation** : avec vs sans mémoire, à conditions égales — étalon-or (backend) ;
- **causalité contrôlée** : écarter les confusions — `nexus_cause` ;
- **impact utilisateur** : le signal externe de Kily — capteur `impact` ;
- **falsifiabilité** : un critère qui peut dire « le système s'est trompé ».
→ NEXUS possède déjà les briques ; il manquait de les ériger en **bloc de premier rang**. C'est fait
dans [[architecture]].

## La phrase à retenir

« Tu as une carte très convaincante de l'écosystème. Il manque encore le **sol dur** qui prouve que
la carte correspond à la réalité. » C'est exactement le rôle du bloc Vérité externe.
