# Dossier `connaissances/` — expert-95

## Rôle

Ce dossier est l'**espace de capitalisation des savoirs spécifiques à un cas
d'usage**. Ici, il héberge les connaissances liées à **SYFIR**.

Il est **distinct du noyau universel** du skill (`SKILL.md` + `references/`) :
le noyau décrit *comment* le système travaille dans **n'importe quel** domaine ;
`connaissances/` stocke des *savoirs particuliers* à un contexte donné.

## Principe d'universalité

**Expert 95 reste universel.** SYFIR n'est qu'un **cas d'usage parmi d'autres**.
En conséquence :

- Ces connaissances **ne sont pas chargées par défaut**.
- Elles ne sont consultées **qu'à la demande**, **quand le contexte le justifie**
  (le Hub décide au Handshake si le cas d'usage courant concerne SYFIR).
- D'autres cas d'usage pourront avoir leur propre sous-dossier, selon le même
  modèle, sans toucher au noyau.

## Arborescence prévue

```
connaissances/
├── README.md            ← ce fichier
├── SYFIR/               ← cas d'usage SYFIR (chargé à la demande)
│   ├── profil-dirigeant.md   ← gouvernance + vue d'ensemble de l'écosystème
│   ├── brandco.md            ← entité BrandCo
│   ├── districo.md           ← entité DistriCo
│   ├── crypto.md             ← entité Crypto (principes uniquement)
│   ├── nexus-ai.md           ← entité Nexus-AI (pôle IA)
│   ├── IA-agent.md           ← orchestrateur-arbitre central
│   ├── central-int.md        ← centralisation intelligente
│   ├── decent-int.md         ← décentralisation intelligente
│   ├── eco-burst.md          ← gestion énergie & puissance ciblée
│   ├── mem-clean.md          ← optimisation contextuelle
│   ├── reality-check.md      ← filtre de viabilité
│   └── jimmy-ia.md           ← paquet de transfert de contexte
└── architecture/        ← architecture Nexus (gouvernance interne)
    ├── governance.md         ← SSOT, ordre d'autorité, nommage
    ├── identity.md           ← identité du système
    └── principles.md         ← 9 principes versionnés
```

> Ces fichiers existent et sont chargés à la demande. Aucune **donnée sensible** :
> descriptions de haut niveau utiles à l'orchestration.

## Lecture / écriture

- **Lecture :** libre, à la demande du Hub.
- **Écriture / mise à jour :** durable → **sous autorisation** (via `mémorise 95`).
