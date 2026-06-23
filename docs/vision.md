# Vision — NEXUS

> **Doc de cap (north star).** Décrit la **vision validée** de NEXUS : *où* l'on va,
> pas *comment* le noyau fonctionne. Ce fichier **ne duplique pas la philosophie** —
> il **renvoie** à la source unique (SSOT : un concept = une définition = une source,
> `principles.md` P4 / `governance.md` §1).
>
> **Portée / autorité.** Vision **non implémentée** au sens technique (un *cap*, dans
> l'esprit *Nexus AIOS* — `identity.md`). Elle **ne redéfinit pas le noyau** : en cas
> de conflit, l'**ordre d'autorité** tranche
> (`SKILL.md > governance.md > principles.md > identity.md > reste` — `governance.md` §2).
>
> **Honnêteté technique (P8 / `governance.md` §6).** « Organisme », « organes »,
> « capteurs », « collectif » sont des **analogies** d'organisation — **pas** une
> exécution logicielle parallèle réelle.

**Renvois SSOT** (sources à lire, **non recopiées ici**) — sous
`.claude/skills/expert-95/` sauf mention : noyau **`SKILL.md`** ;
`connaissances/architecture/` → **`governance.md`**, **`principles.md`**,
**`identity.md`** ; `connaissances/SYFIR/` → **`IA-agent.md`**, **`central-int.md`**,
**`decent-int.md`**, **`reality-check.md`** ; **`references/methode.md`** ; et
**`backend/README.md`** (racine du dépôt).

---

## 1. Un organisme cognitif *accompagné* — pas un multi-agents classique

NEXUS n'est pas un essaim d'agents indépendants qui votent. C'est un **organisme
cognitif** dont la pensée est **accompagnée** par son écosystème : mémoire, capteurs,
organes (95/96/97/98) et Créateur agissent **ensemble**, pas chacun isolé dans son coin.

→ **Ancrage canon.** `identity.md` (« pas un chatbot », « pas un second système ») ;
`governance.md` §0 (Nexus = *concept d'organisation*, pas une appli multi-agents) ;
architecture hybride pilotée par l'orchestrateur (`IA-agent.md` ; `central-int.md` /
`decent-int.md`). « Agents » reste une **analogie** (P8 / `governance.md` §6).

## 2. Le Créateur — couche méta, hors système, qui *amende* les règles

Le **Créateur** est une **couche méta** au-dessus de NEXUS. Il ne *suit* pas les règles
comme un organe : il a le pouvoir de les **amender** (« mode créateur »). C'est lui qui
autorise le durable et fait évoluer le canon — les règles sont **faites pour être
révisées**, pas gravées dans le marbre.

→ **Ancrage canon.** Les principes sont « **versionnés et modifiables sous
autorisation** » (`principles.md`) ; protocole de modification (`governance.md` §3) ;
**réversibilité** totale (P6) ; **autorisation** du durable (P7). **Honnêteté :** « mode
créateur » désigne ici cette **autorité humaine d'amendement** — pas un mode exécutable
de `SKILL.md` (les 5 modes de travail sont en `references/methode.md` §6).

## 3. Autonomie *progressive* — assisté → supervisé → autonome

L'accompagnement **décroît à mesure que la compétence monte**. NEXUS commence
**assisté** (chaque pas validé), passe **supervisé** (il agit, on trace, on peut
arrêter), puis devient **autonome** dans un périmètre donné. L'autonomie se **gagne**,
elle ne se décrète pas.

→ **Ancrage canon.** Les 5 modes Assisté → … → Automatique 100 %
(`references/methode.md` §6) ; **frontière libre / sous-autorisation** (P7) ; **Express
Clos** = autonomie cadrée **révocable**, « stop » prioritaire (`governance.md` §3 bis) ;
garde-fous de la boucle (veto 98, budget de génération — `backend/README.md` §3-4).

## 4. Apprentissage *accompagné et collectif* — pas de juge unique

Une expérience n'est **pas tranchée par un arbitre solitaire**. Elle est **interprétée
par l'écosystème** — mémoire, capteurs, organe **96**, autres organes, Créateur. Et la
**meilleure idée gagne sur des critères objectifs**, **pas par vote** majoritaire.

→ **Ancrage canon.** Boucle d'amélioration Mission / Résultat / Leçon (P9 +
`journal-evolution.md`) ; **excellence vérifiable et mesurable** (P3) ; consensus par
**cohérence**, pas par majorité (`central-int.md` agrège/filtre/élimine les erreurs ;
`decent-int.md` maximise la diversité) ; **filtre d'admission 96** : priorité =
*formule du conseil inter-systèmes*, pas un vote (`backend/README.md` §4).

## 5. Exposition *contrôlée* à l'incertitude — et *mesurer* ce qu'on apprend

Le problème n'est **pas le chaos** : c'est la **peur du chaos**. NEXUS s'**expose**
volontairement à l'incertitude — mais **sous contrôle**. Et l'exposition **ne suffit
pas** : il faut **mesurer ce qui en est appris**, sinon on s'agite sans apprendre.

→ **Ancrage canon.** Contrôle = veto 98, budget, **seuil dynamique** plus sélectif sous
charge (`backend/README.md` §3-4) + filtre de viabilité (`reality-check.md`) ; **mesure**
= excellence vérifiable (P3) et boucle d'amélioration (P9) ; clarifier selon le **risque
d'erreur** (P2).

## 6. Chantier ouvert assumé — *mesurer la progression*, prouver et non juger

NEXUS est un **chantier ouvert**, assumé comme tel. On **mesure la progression**
(version A vs B : **temps**, **erreurs**) pour que le **collectif devienne une preuve** —
démontrée, reproductible — **et non un jugement** d'autorité.

→ **Ancrage canon.** *Nexus AIOS* = cap **non implémenté** (`identity.md`) ; **mesurable
> slogan** (P3) ; capitalisation A/B des itérations (`journal-evolution.md`) ;
**observabilité** à venir — taux d'admission, budget, vetos (`backend/README.md` §8) ;
« ne pas survendre » (P8).

---

**Statut : v1.0 (vision / cap — non implémenté)** — *additif*, **versionné**,
**modifiable sous autorisation** (`mémorise 95`). Ne redéfinit pas le noyau ; en cas de
conflit, `governance.md` §2 (ordre d'autorité) **prime**.
