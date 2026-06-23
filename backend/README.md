# Backend NEXUS — amorce du « loop engineering »

Amorce du **backend de la boucle auto-mandatée** de l'écosystème NEXUS. Cette
première brique pose deux choses :

1. un **orchestrateur de boucle reprenable** (la mécanique « loop engineering ») ;
2. un **filtre d'admission** pour l'organe **96** (la formule du conseil
   inter-systèmes).

> **Honnêteté technique.** Les organes 96/97/98 sont ici des **stubs** (amorces)
> destinés à être remplacés. Le vrai apport de ce backend, c'est la **mécanique
> de boucle reprenable** et le **filtre d'admission** — pas une exécution
> autonome réelle. Cet esprit suit les principes NEXUS (« ne pas survendre » —
> cf. `.claude/skills/expert-95/connaissances/architecture/principles.md`, P5
> simplicité et P8 honnêteté technique).

---

## 1. Les organes (rappel)

| Organe | Rôle | Dans ce backend |
| ------ | ---- | --------------- |
| **95** | pense / planifie | construit ou recharge le plan de tâches |
| **96** | analyse — « voit pour agir » | vérifie + **filtre d'admission** (auto-mandat) |
| **97** | agit | exécute une tâche (stub) |
| **98** | immunité / sécurité — **droit de veto** | bloque une action sensible non autorisée |
| **mémoire** | persistance | le fichier d'état **JSON** de la boucle |

> Le vocabulaire de référence de l'écosystème est défini dans
> `.claude/skills/expert-95/connaissances/architecture/` (SSOT — source unique).
> Ce README **n'y duplique pas** la philosophie : il décrit le **backend**.

---

## 2. Architecture du dossier

```
backend/
├── orchestrateur.py            # (a) boucle reprenable : planifie→exécute→vérifie→état JSON→reprise
├── filtre_admission.py         # (b) filtre d'admission de 96 (formule du conseil inter-systèmes)
├── tests/
│   └── test_filtre_admission.py# (c) tests pytest du filtre d'admission
├── README.md                   # (d) ce fichier
├── conftest.py                 # rend backend/ importable par pytest
├── requirements-dev.txt        # dépendance de dev unique : pytest
└── .gitignore                  # ignore l'état généré + caches
```

**Zéro dépendance lourde** : les modules n'utilisent que la **bibliothèque
standard** Python (`json`, `dataclasses`, `enum`, `pathlib`, `argparse`,
`datetime`). `pytest` n'est requis **que** pour lancer les tests.

---

## 3. L'orchestrateur de boucle (loop engineering)

La boucle auto-mandatée enchaîne, à chaque tâche :

```
        ┌─────────────────────────────────────────────────────────┐
        ▼                                                         │
   planifie (95) ─► exécute (97) ─► vérifie (96/98) ─► écrit l'état JSON
        ▲                                                         │
        └──────────────── reprend où elle s'est arrêtée ◄─────────┘
```

**Propriété clé — reprise.** L'état est sauvegardé (de façon **atomique**) après
**chaque** tâche dans `etat_boucle.json`. Si la boucle est interrompue, le
prochain lancement **repart exactement là où elle s'était arrêtée** : on ne
rejoue jamais une tâche déjà `fait`e ou `bloque`ée.

**Auto-mandat.** Avant de dérouler le plan, l'organe 96 détecte des « écarts »
et les passe au filtre d'admission : un écart **admis** qui est une **création**
devient une **nouvelle tâche** ajoutée au plan (la boucle se mandate
elle-même), dans la limite du **budget de génération**.

**Veto.** L'organe 98 peut **bloquer** une tâche sensible : elle passe à l'état
`bloque` et n'est pas rejouée (lever le veto demandera une autorisation
explicite — cf. « reste à faire »).

### Contrat d'état JSON (extrait réel)

```json
{
  "version": 1,
  "cycle": 6,
  "curseur": 6,
  "taches": [
    { "id": "t1", "libelle": "…", "etat": "fait",   "verifie": true,  "veto": false, "sensible": false },
    { "id": "t4", "libelle": "…", "etat": "bloque", "verifie": true,  "veto": true,  "sensible": true  },
    { "id": "t6", "libelle": "[auto-mandat 96] …", "etat": "fait", "verifie": true, "veto": false }
  ],
  "archive_96": [ { "ecart": "e-peripherique", "decision": "archive", "alerte_95": false } ],
  "journal": [ "… 96 ADMET e-central (priorité 2268.0 ≥ seuil 75.0) → nouvelle tâche t6" ]
}
```

---

## 4. Le filtre d'admission de 96

L'organe 96 voit beaucoup d'« écarts » ; sans filtre, 95 serait noyé. Chaque
écart reçoit une **priorité** selon la **formule du conseil inter-systèmes** :

```
Priorité = (Criticité × Fréquence_usage × Persistance × Impact_Utilisateur) / Coût
```

Règles appliquées :

- **Seuil dynamique.** `seuil = seuil_base × (1 + coef_saturation × taux_remplissage)`.
  Plus la file est saturée, plus le seuil **monte** → on devient **plus
  sélectif** sous charge.
- **Détection ≠ Création.** Observer un écart est libre ; le transformer en
  **création** (nouvelle tâche) consomme un **budget de génération** limité —
  garde-fou anti-emballement de la boucle.
- **Sous le seuil → archive.** Un écart de priorité insuffisante est **archivé
  sans alerter 95** (silencieux, mais tracé pour l'audit).

Trois issues possibles (`Decision`) : `ADMIS` (escaladé vers 95), `ARCHIVE`
(sous le seuil), `BUDGET_EPUISE` (au-dessus du seuil mais plus de budget de
création).

---

## 5. Comment lancer

### Lancer la boucle

```bash
# Depuis la racine du dépôt.
python3 backend/orchestrateur.py            # déroule la boucle jusqu'au bout
python3 backend/orchestrateur.py --reset    # repart de zéro (efface l'état)
```

### Démontrer la reprise (une tâche à la fois)

```bash
python3 backend/orchestrateur.py --reset --pas 1   # passage 1 : 1re tâche
python3 backend/orchestrateur.py --pas 1           # passage 2 : reprend à la 2e
python3 backend/orchestrateur.py --pas 1           # … et ainsi de suite
python3 backend/orchestrateur.py                   # termine le reste
```

Sortie attendue (résumé d'une ligne par passage) :

```
Cycle 1 · 1/6 faite(s) · 0 bloquée(s) par 98 · 5 en attente
Cycle 2 · 2/6 faite(s) · 0 bloquée(s) par 98 · 4 en attente
…
Cycle 5 · 5/6 faite(s) · 1 bloquée(s) par 98 · 0 en attente
```

Options : `--etat <chemin>` pour un fichier d'état alternatif, `--reset` pour
effacer l'état, `--pas N` pour limiter le nombre de tâches d'un passage.

### Lancer les tests

```bash
pip install -r backend/requirements-dev.txt   # installe pytest (dev uniquement)
python3 -m pytest backend/tests -q
```

Résultat attendu : `7 passed`. Cas couverts : écart périphérique rejeté, écart
central retenu, file saturée qui élève le seuil, budget de génération, coût nul,
tri du lot d'admis.

---

## 6. Ce qui reste à faire

- **Remplacer les stubs** 96/97/98 par les vrais organes (exécution réelle de
  97, vérification riche de 96, politique de veto de 98).
- **Lever le veto de 98** sous **autorisation explicite** (et tracer qui/quand).
- **Détecteur d'écarts réel** pour 96 (aujourd'hui les écarts sont pré-définis
  et semés une seule fois).
- **File d'attente vivante** : faire varier `taille_file` au fil de l'exécution
  (le seuil dynamique réagirait alors en temps réel ; pour l'instant la taille
  est mesurée une fois au démarrage du cycle).
- **Mémoire partagée** entre la boucle et la mémoire de l'écosystème (au-delà du
  seul fichier d'état local).
- **Observabilité** : métriques (taux d'admission, budget consommé, vetos),
  rotation du journal.
- **Robustesse** : reprise après corruption, verrouillage si plusieurs boucles
  écrivent le même état.
```
