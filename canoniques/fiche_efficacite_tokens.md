# Fiche — Efficacité & économie de tokens (extrait de la vidéo @shubhamnocode / plugin Caveman)

> Source : TikTok @shubhamnocode, « Économisez 75% de vos tokens sur Claude grâce à ce plugin »
> (https://www.tiktok.com/@shubhamnocode/video/7633936136389397782) — outil cité : **Caveman**
> (skill open-source Claude Code, JuliusBrussee). Analysée avec la grille « utile ou pas ».
> Niveau de preuve : MOYEN (outil réel, vérifiable sur GitHub ; chiffre « 75% » = marketing).

## Démystification (le gardien de la réalité)

« –75% de tokens » est survendu. Caveman compresse **uniquement la SORTIE** du modèle
(~65% en moyenne, 22-87% selon les cas) en le faisant « parler comme un homme des cavernes ».
Il ne touche PAS aux tokens d'ENTRÉE — or NEXUS recharge à chaque appel ses canoniques + sa
mémoire, qui sont de l'entrée. Donc gain réel < promesse. Utile, pas magique.

## Le noyau utile (ce qui passe les 4 filtres)

1. **Principe : le token est une ressource à concevoir.**
   → Muscle notre 5ᵉ capteur (*efficacité*) : mesurer la **verbosité / tokens par tâche**,
   pas seulement la durée.

2. **Discipline de sortie.** Les organes peuvent être plus secs sans perdre en rigueur
   (esprit « caveman-lite »). Aligné avec la préférence de Kily : concis.

3. **Cavekit = boucle spec-driven** `grill → spec → research → review → build` sur un seul
   `SPEC.md`. C'est notre chaîne 95→97 / PDCA, confirmée. Idée à voler : **un artefact SPEC
   unique partagé entre les organes** (95 écrit le spec, 97 l'exécute, 96 le vérifie).

## Application concrète pour développer le système

- [ ] **Capteur efficacité** : ajouter une dimension « tokens/verbosité » (proxy : longueur
  de sortie) au journal des capteurs, pour mesurer si on devient plus efficace, pas juste plus actif.
- [ ] **Backend (pilier 5, Claude Code — atelier de Kily)** : tester Caveman comme skill réel,
  en gardant l'œil ouvert (sortie only). Compresser l'ENTRÉE reste NOTRE levier : c'est déjà le
  rôle de memoire-beta (tri 3 étages + consolidation) — à pousser plus loin.
- [ ] **Norme de sortie** : adopter un mode « sec par défaut » pour les organes.

## Triplet du coffre

{ donnée : la compression de sortie économise des tokens (~65% sortie, pas la facture totale) ·
  source : @shubhamnocode + GitHub JuliusBrussee/caveman · niveau de preuve : MOYEN }
