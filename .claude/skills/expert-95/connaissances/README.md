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
└── SYFIR/               ← cas d'usage SYFIR (chargé à la demande)
    ├── profil-dirigeant.md   ← gouvernance + vue d'ensemble de l'écosystème
    ├── brandco.md            ← entité BrandCo
    ├── districo.md           ← entité DistriCo
    ├── crypto.md             ← entité Crypto
    └── nexus-ai.md           ← entité Nexus-AI
```

> Les fichiers d'entités (`brandco.md`, `districo.md`, `crypto.md`,
> `nexus-ai.md`) seront créés ultérieurement. Aucune **donnée sensible** n'est
> stockée ici : on se limite à des descriptions de haut niveau utiles à
> l'orchestration.

## Lecture / écriture

- **Lecture :** libre, à la demande du Hub.
- **Écriture / mise à jour :** durable → **sous autorisation** (via `mémorise 95`).
