# Backend NEXUS — amorce du « loop engineering »

Amorce du **backend de la boucle auto-mandatée** de l'écosystème NEXUS. Briques
posées :

1. un **orchestrateur de boucle reprenable** (la mécanique « loop engineering ») ;
2. un **filtre d'admission** pour l'organe **96** (la formule du conseil
   inter-systèmes) ;
3. un **moteur interchangeable** (Voie 5) — l'IA derrière les organes
   (Claude/Gemini/GPT/Kimi), branchée par **injection de dépendance** ;
4. une **transcription** optionnelle (Voie 6 / Whisper) — l'« oreille », avec
   **repli propre** si Whisper n'est pas installé.
5. un **processus de décision mesuré** — on ne tranche que sur du **réalisé ET
   mesuré** (meilleure valeur, pas l'avis ; override explicite du Créateur) ;
6. un **dosage d'intensité** — le palier **le moins cher qui suffit**
   (SOLO/DUO/CONSEIL), vérificateur **toujours** distinct du constructeur.
7. un **évaluateur de tâches ouvertes** — **filtre consultatif de 96** : agrège des
   préférences (Bradley-Terry + Copeland), **signale** séparation, cycles et
   divergences ; **recommande, ne décide jamais**.

> **Honnêteté technique.** Les organes 96/97/98 sont ici des **stubs** (amorces)
> destinés à être remplacés. Le vrai apport, c'est la **mécanique de boucle
> reprenable**, le **filtre d'admission** et les **points d'extension propres**
> (moteur, oreille) — pas une exécution autonome réelle. Cet esprit suit les
> principes NEXUS (« ne pas survendre » —
> `.claude/skills/expert-95/connaissances/architecture/principles.md`, P5
> simplicité et P8 honnêteté technique).

---

## 1. Les organes (rappel)

| Organe | Rôle | Dans ce backend |
| ------ | ---- | --------------- |
| **95** | pense / planifie | construit ou recharge le plan de tâches |
| **96** | analyse — « voit pour agir » | vérifie + **filtre d'admission** (auto-mandat) + **évaluateur consultatif** (propose, ne décide jamais) |
| **97** | agit | exécute une tâche **via un `Moteur` injecté** (IA interchangeable) |
| **98** | immunité / sécurité — **droit de veto** | bloque une action sensible non autorisée |
| **mémoire** | persistance | le fichier d'état **JSON** de la boucle |

> Le vocabulaire de référence de l'écosystème est défini dans
> `.claude/skills/expert-95/connaissances/architecture/` (SSOT — source unique).
> Ce README **n'y duplique pas** la philosophie : il décrit le **backend**.

---

## 2. Architecture du dossier

```
backend/
├── orchestrateur.py             # (a) boucle reprenable : planifie→exécute→vérifie→état JSON→reprise
├── filtre_admission.py          # (b) filtre d'admission de 96 (formule du conseil inter-systèmes)
├── moteur.py                    # (Voie 5) IA interchangeable : Moteur / MoteurMock / AdaptateurAPI
├── transcription.py             # (Voie 6) oreille Whisper, repli propre si absent
├── processus_decision.py        # (c) décision mesurée : ne tranche que sur réalisé+mesuré
├── orchestrateur_intensite.py   # (d) dosage d'intensité : SOLO/DUO/CONSEIL, le moins cher qui suffit
├── evaluateur_ouvert.py         # (e) filtre consultatif de 96 : Bradley-Terry + Copeland, signaux
├── tests/
│   ├── test_filtre_admission.py        # tests pytest du filtre d'admission
│   ├── test_moteur.py                  # tests pytest du moteur (mock déterministe, clé absente…)
│   ├── test_transcription.py           # tests pytest de la transcription (repli)
│   ├── test_processus_decision.py      # tests de la décision mesurée (+ garde-fous)
│   ├── test_orchestrateur_intensite.py # tests du dosage d'intensité (+ garde-fous)
│   └── test_evaluateur_ouvert.py       # tests de l'évaluateur (séparation, cycle, divergence)
├── README.md                    # ce fichier
├── conftest.py                  # rend backend/ importable par pytest
├── requirements-dev.txt         # dépendance de dev unique : pytest
└── .gitignore                   # ignore l'état généré + caches
```

**Zéro dépendance lourde** : les modules n'utilisent que la **bibliothèque
standard** (`json`, `dataclasses`, `enum`, `pathlib`, `argparse`, `datetime`,
`urllib`, `importlib`). `pytest` n'est requis **que** pour lancer les tests.
**Whisper est optionnel** : son absence ne casse rien (voir §6).

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

**97 agit via un Moteur injecté.** L'organe 97 n'appelle pas un fournisseur en
dur : il appelle un `Moteur` (cf. §5). Par défaut c'est `MoteurMock`
(déterministe, hors-ligne) — la boucle tourne **sans réseau ni clé d'API**.

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

## 5. Le moteur interchangeable (Voie 5)

But : rendre l'**IA derrière les organes interchangeable** sans toucher au reste
du backend. Les organes dépendent d'une **interface** `Moteur`, pas d'un
fournisseur.

| Classe | Rôle |
| ------ | ---- |
| `Moteur` (abstrait) | interface : `generer(prompt) -> str` |
| `MoteurMock` | **déterministe**, hors-ligne — tests et mode dégradé |
| `AdaptateurAPI` | **générique**, compatible « OpenAI Chat Completions » |

**Clé d'API : jamais en dur.** `AdaptateurAPI` lit la clé dans une **variable
d'environnement** ; si elle est absente, `generer` lève une `ErreurMoteur` au
message explicite (aucun appel réseau n'est tenté).

```python
from moteur import AdaptateurAPI
from orchestrateur import tourner
from pathlib import Path

# La clé vient de l'environnement (ex. export MOTEUR_API_CLE=sk-...).
moteur = AdaptateurAPI(base_url="https://api.openai.com/v1", modele="gpt-4o-mini")
tourner(Path("etat_boucle.json"), moteur=moteur)   # 97 utilisera ce moteur
```

Exemples de configuration (modèles/URL à **vérifier chez le fournisseur**) :

| Fournisseur | `base_url` (endpoint compatible OpenAI) | `modele` (exemple) | `cle_env` |
| ----------- | --------------------------------------- | ------------------ | --------- |
| OpenAI / GPT | `https://api.openai.com/v1` | `gpt-4o-mini` | `OPENAI_API_KEY` |
| Kimi / Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` | `MOONSHOT_API_KEY` |
| Gemini | endpoint compatible OpenAI de Google | `gemini-…` | `GEMINI_API_KEY` |
| Claude | endpoint compatible OpenAI d'Anthropic | `claude-opus-4-8` | `ANTHROPIC_API_KEY` |

> **Honnêteté (stub vs réel).** `AdaptateurAPI` parle le schéma **OpenAI Chat
> Completions** (`POST /chat/completions`, réponse `choices[0].message.content`).
> C'est un vrai appel HTTP, mais il n'est **pas testé contre une API en direct**
> ici (les tests couvrent la logique hors-ligne). Pour l'**API native** d'un
> fournisseur — p. ex. Anthropic : `POST /v1/messages`, en-têtes `x-api-key` +
> `anthropic-version: 2023-06-01`, réponse `content[0].text`, modèle actuel
> `claude-opus-4-8` — il faut une **petite sous-classe** de `Moteur` qui
> surcharge `generer`. Les paramètres `entete_cle` / `prefixe_cle` permettent
> déjà d'adapter l'en-tête d'authentification.

---

## 6. La transcription / oreille (Voie 6, Whisper)

`transcription.transcrire(chemin_audio) -> str` utilise **Whisper s'il est
installé**. Whisper est une **dépendance optionnelle** : son absence ne provoque
**aucun plantage**.

- `strict=False` (**défaut**) → renvoie un **message de repli clair** préfixé
  `[transcription indisponible]` (zéro plantage) ;
- `strict=True` → lève `TranscriptionIndisponible` (gestion par exception).

Un **fichier introuvable** lève toujours `FileNotFoundError` (vraie erreur, pas
un cas de repli). Pour activer l'oreille : `pip install openai-whisper` (+ `ffmpeg`).

```python
from transcription import transcrire, whisper_disponible

if whisper_disponible():
    texte = transcrire("memo.wav")          # transcription réelle
else:
    texte = transcrire("memo.wav")          # message de repli clair, pas de crash
```

---

## 7. Le processus de décision mesuré (`processus_decision.py`)

`decider(options)` tranche entre des options — `option = {label, valeur (0..1 ou
None = non mesuré), realise}` — sur une règle simple : **on ne tranche que sur du
réalisé ET mesuré**.

- **Rien de prêt → on ne tranche pas.** Si aucune option n'est *réalisée ET
  mesurée*, le statut est `incomplet`, message :
  « **processus incomplet : réaliser et mesurer d'abord** ».
- **La meilleure valeur gagne — pas l'avis.** Entre options prêtes, la plus haute
  `valeur` l'emporte (un éventuel champ « avis » est **ignoré**).
- **Activer / archiver, réversible.** Le gagnant est **activé**, les autres
  **archivés** — *rien n'est supprimé*, tout est réversible.
- **Droits.** Si la décision **touche l'écosystème**, l'autorité est le **système**
  (la valeur mesurée, pas l'opinion). Le **Créateur** peut **override
  explicitement** (couche méta) : honoré, **tracé** et réversible.

> **Canon (SSOT, non dupliqué).** P3 (excellence *mesurable*), P6 (réversibilité),
> P7 (autorisation) — `…/connaissances/architecture/principles.md`. **Honnêteté
> (P8) :** c'est une **logique de tranche**, pas un organe autonome ;
> « activer/archiver » = décisions, pas un effet matériel.

---

## 8. Le dosage d'intensité (`orchestrateur_intensite.py`)

`recommander(tache, difficulte, enjeu, reversible, nouveaute)` renvoie le **palier
le moins cher qui suffit**, son plan de ressources et un coût en **ordres de
grandeur** :

| Palier | Quand | Ressources | Orchestration |
| ------ | ----- | ---------- | ------------- |
| **SOLO** | facile **et** réversible **et** enjeu bas | bâtisseur + relecteur indépendant | **0** (aucun surcoût) |
| **DUO** | cas intermédiaire (par défaut) | bâtisseur + vérificateur pair | faible |
| **CONSEIL** | **dur ET** (enjeu haut **ou** irréversible **ou** nouveauté forte) | conseil (3) + arbitre indépendant | élevée |

- **Le vérificateur est TOUJOURS une ressource différente du constructeur**
  (garde-fou invariant, vérifié sur toute la grille d'entrées).
- **Coût séparé production / orchestration** : `production = base(difficulté) ×
  facteur_palier`, `orchestration` propre au palier. Ce sont des **ordres de
  grandeur relatifs**, **pas une facture**. À difficulté égale :
  **SOLO < DUO < CONSEIL** (« la moins chère qui suffit »).
- Entrées tolérantes : niveau par mot-clé (« facile / dur / haut »…), entier
  `1..3` ou flottant `[0,1]`.

> **Canon (SSOT, non dupliqué).** P5 (simplicité — le moins cher qui suffit), P3
> (vérificateur indépendant), P8 (analogies, pas d'agents parallèles réels) —
> `…/connaissances/architecture/principles.md`.

---

## 9. L'évaluateur de tâches ouvertes (`evaluateur_ouvert.py`)

**Filtre consultatif de l'organe 96.** À partir de comparaisons par paires
« gagnant > perdant », il **agrège des préférences** et **propose** — **96 propose,
ne décide jamais**. La sortie est une **recommandation** (`decide=False`), pas une
décision.

> **Axiome (gravé en docstring).** On **agrège des préférences**, on ne **mesure
> pas un réel** : « A > B » est un *jugement*, pas une mesure. Donc **baseline
> forte, jamais d'homme de paille** ; et on **refuse de chiffrer** ce qui n'existe
> pas (si le MLE diverge, on le **signale**). *(À distinguer de
> `processus_decision.py`, qui, lui, tranche sur de la **valeur mesurée**.)*

Trois lectures du même jeu de préférences :

| Lecture | Donne | Garde-fou |
| ------- | ----- | --------- |
| **Bradley-Terry** | force latente + `P(A>B)` | **séparation** détectée (condition de Ford : graphe de dominance fortement connexe) → sinon **divergence signalée**, `p=None` |
| **Copeland** | classement ordinal (`#battus − #perdants`) | robuste aux marges **et aux cycles** |
| **Cycles** | clusters intransitifs (A>B>C>A) | rapportés comme **SIGNAL**, pas du bruit |
| **Alerte** | désaccord **BT vs Copeland** en tête | `divergence.bt_vs_copeland = true` |

```python
from evaluateur_ouvert import recommander_par_preferences

comparaisons = [("A", "B"), ("A", "B"), ("B", "C"), ("A", "C")]  # gagnant > perdant
reco = recommander_par_preferences(["A", "B", "C"], comparaisons)
# reco = {nature:"recommandation", decide:False, verdict{classement,tete,confiance},
#         p, cycles, divergence{separation,bt_vs_copeland,…}, avertissements, …}
```

**Câblé dans 96 (stub levé).** L'organe 96 **appelle** réellement l'évaluateur via
`FiltreAdmission.remonter_decision(options, comparaisons)` : quand une décision
présente plusieurs options concurrentes **avec des comparaisons par paires**, 96
**intègre** la sortie de `recommander_par_preferences` comme **recommandation** dans
ce qu'il remonte à 95 (`decide=False` au niveau de 96 **et** de la recommandation).
**Sans comparaison**, 96 se comporte comme avant (rétro-compatible : aucun appel,
aucune recommandation).

```python
from filtre_admission import FiltreAdmission

f = FiltreAdmission(seuil_base=50, capacite_file=10, budget_generation=1)
sortie = f.remonter_decision(["A", "B", "C"], comparaisons)   # 96 consulte l'évaluateur
# sortie = {organe:"96", decide:False, consulte_evaluateur:True,
#           recommandation:{… decide:False …}, options, motif}
brut = f.remonter_decision(["A", "B", "C"])                   # rétro-compatible
# brut["consulte_evaluateur"] is False ; brut["recommandation"] is None
```

**Trace persistante (« compteur »).** À **chaque** appel, `remonter_decision` ajoute
une **ligne JSONL** au journal (`chemin_journal` / `JOURNAL_DEFAUT`) : horodatage,
décision, options, **classement rendu par l'évaluateur**, signaux, et `suivi` = ce qui
a été **réellement suivi** (None tant que 96 ne fait que recommander). Comparer plus
tard `tete_recommandee` et `suivi` permettra de **mesurer si consulter l'évaluateur
change une vraie décision**. 96 reste **strictement consultatif** : il **logue** la
reco, il **ne lui obéit pas** (`decide=False`, `suivi` jamais auto-rempli).

> **Canon (SSOT, non dupliqué).** P3 (n'affirmer que ce que les données
> permettent : séparation ⇒ on ne chiffre pas), P8 (agrégation **≠** mesure ;
> « évaluateur » = un calcul, pas un agent) — `…/architecture/principles.md`.

---

## 10. Comment lancer

### Lancer la boucle

```bash
# Depuis la racine du dépôt. MoteurMock par défaut : aucun réseau, aucune clé.
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

Options : `--etat <chemin>` (fichier d'état alternatif), `--reset` (efface
l'état), `--pas N` (limite le nombre de tâches d'un passage).

### Lancer les tests

```bash
pip install -r backend/requirements-dev.txt   # installe pytest (dev uniquement)
python3 -m pytest backend/tests -q
```

Résultat attendu : **`78 passed`**. Couverture : filtre d'admission
(périphérique rejeté, central retenu, file saturée, budget, coût nul, tri),
moteur (mock déterministe, interface abstraite, **clé absente → erreur claire**,
extraction OpenAI, injection dans l'orchestrateur), transcription (repli propre,
mode strict, fichier absent), **décision mesurée** (refus sur non-mesuré, meilleure
valeur ≠ avis, activer/archiver réversible, override Créateur tracé), **dosage
d'intensité** (SOLO/DUO/CONSEIL, vérificateur ≠ constructeur sur toute la grille,
SOLO sans surcoût, ordre SOLO < DUO < CONSEIL), **évaluateur consultatif**
(séparation signalée → `p=None`, cycle détecté comme signal, divergence BT/Copeland
signalée, transitif bruité concordant, recommandation jamais décision), **câblage
96 → évaluateur** (96 appelle l'évaluateur et expose la recommandation sans trancher,
cas sans comparaisons inchangé, signaux cycle/séparation remontés, **trace JSONL
écrite à chaque appel**, `suivi` renseignable, 96 logue mais n'obéit pas).

---

## 11. Ce qui reste à faire

- **Remplacer les stubs** 96/97/98 par les vrais organes (exécution réelle de
  97, vérification riche de 96, politique de veto de 98).
- **Sous-classes natives** de `Moteur` par fournisseur (ex. Anthropic
  `/v1/messages`), gestion du `max_tokens`, du streaming et des erreurs/refus.
- **Lever le veto de 98** sous **autorisation explicite** (et tracer qui/quand).
- **Détecteur d'écarts réel** pour 96 (les écarts sont pré-définis et semés une
  seule fois).
- **File d'attente vivante** : faire varier `taille_file` en cours d'exécution
  (le seuil dynamique réagirait en temps réel ; il est mesuré une fois par cycle).
- **Oreille réelle** : choix du modèle Whisper, langue, horodatage des segments.
- **Mémoire partagée** entre la boucle et la mémoire de l'écosystème.
- **Observabilité** : métriques (taux d'admission, budget consommé, vetos),
  rotation du journal.
- **Robustesse** : reprise après corruption, verrouillage multi-boucles.
- **Évaluateur câblé dans 96** ✅ + **trace JSONL écrite** ✅ : 96 appelle
  `evaluateur_ouvert` via `FiltreAdmission.remonter_decision` (recommandation,
  `decide=False`) et logue chaque décision (`journal_decisions.jsonl`). **Reste** à
  câbler `processus_decision` et `orchestrateur_intensite` dans la boucle 95→98, puis
  à faire remonter la sortie de 96 jusqu'à l'exécution réelle de 97.
- **Exploiter le « compteur »** : le journal logue `tete_recommandee` et `suivi` ;
  reste à **renseigner `suivi`** depuis la boucle décisionnelle réelle et à
  **analyser** le JSONL pour mesurer si/quand consulter l'évaluateur change une vraie
  décision (reco vs suivi).
- **Évaluateur** : intervalles de confiance sur les forces Bradley-Terry,
  pondération/décote temporelle des comparaisons, détecteur de préférences réel
  (aujourd'hui les comparaisons sont fournies en entrée).
