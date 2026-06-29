# Fiche — « Loop Engineering » : arrêter de prompter, écrire des boucles (LA validation de NEXUS)

> Source : TikTok @bariqrifki (créateur rigoureux, sources citées),
> « La compétence IA que tout le monde apprend est déjà morte. Le créateur de Claude Code a
> arrêté de prompter » — https://www.tiktok.com/@bariqrifki/video/7654203019806002433
> Niveau de preuve : ÉLEVÉ — déclaration sourcée de Boris Cherny (chef de Claude Code), juin 2026,
> vérifiée (Fortune, The New Stack, etc.).
> Verdict grille : KEEPER MAJEUR.

## Le fait (vérifié)

Boris Cherny, chef de Claude Code chez Anthropic (juin 2026) :
« Je ne prompte plus Claude. J'ai des boucles qui tournent et qui promptent Claude et décident
quoi faire. Mon métier, c'est d'écrire des boucles. » Il gère des « armées d'agents » (des agents
qui promptent des agents, en arbres de milliers).

→ Le « loop engineering » : concevoir des workflows d'agents autonomes au lieu de prompter à la main.

## Les 4 composants canoniques d'une boucle = NEXUS, trait pour trait

| Composant loop engineering            | Organe / brique NEXUS              |
|---------------------------------------|------------------------------------|
| Exécution planifiée (schedule)        | boot / cycle                        |
| Espace de travail isolé               | le sandbox                          |
| **Agent vérificateur** (2ᵉ agent)     | **96 (analyste) + 98 (gardien)**    |
| Mémoire persistante (état → fichier)  | **memoire-beta** (reprend demain)   |

La boucle « découvre le travail sur planning → vérifie le résultat avec un 2ᵉ agent → écrit son
état dans un fichier pour reprendre demain ». C'est exactement la philosophie NEXUS (OODA / PDCA,
95→97→96→98, mémoire qui persiste).

## Démystification (filtre 2)

« Le prompting est mort » = titre hyperbolique. Faux au sens littéral : les boucles promptent
encore les agents en interne (un bon prompt compte toujours). Le vrai message, lui, est solide et
sourcé : la compétence à FORTE valeur n'est plus le prompt isolé, mais la CONCEPTION de boucles
autonomes (orchestration).

## Pourquoi c'est capital pour NEXUS

- **Validation stratégique au plus haut niveau** : le créateur de Claude Code décrit notre projet.
  NEXUS n'est pas une lubie — c'est la direction que prend le terrain.
- **Confirme la priorité du pilier 5** (décentralisation = orchestrateur qui fait tourner des
  boucles). Le backend à bâtir EST une « loop engine ».
- **Valide les organes vérificateurs séparés** (96/98) : la recherche les nomme « verifier agents ».

## Application concrète

- [ ] Backend (Claude Code) : construire la boucle minimale = planifier → exécuter (97) →
  vérifier (96/98) → écrire l'état (memoire-beta) → reprendre. On a déjà 3 briques sur 4.
- [ ] Inscrire « NEXUS = loop engine » dans l'identité/architecture du canon.
- [ ] Garder l'humilité du filtre 2 : à l'intérieur des boucles, les bons prompts comptent encore.

## Triplet du coffre

{ donnée : la compétence-clé passe du prompt isolé à la conception de boucles autonomes
  (loop engineering) · source : Boris Cherny / The New Stack / Fortune via @bariqrifki ·
  niveau de preuve : ÉLEVÉ }
