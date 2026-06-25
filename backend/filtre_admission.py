"""
Filtre d'admission de l'organe 96 — écosystème NEXUS.

L'organe 96 « voit pour agir » : il observe en continu des « écarts »
(signaux, anomalies, opportunités) et décide lesquels méritent de remonter
à l'organe 95 (qui pense / planifie). Sans filtre, 95 serait noyé sous le
bruit. Ce module applique la « formule du conseil inter-systèmes » :

    Priorité = (Criticité × Fréquence_usage × Persistance × Impact_Utilisateur) / Coût

Règles posées par le conseil inter-systèmes :
  1. Un écart est ADMIS (escaladé vers 95) si sa priorité atteint le SEUIL.
  2. Le seuil est DYNAMIQUE : il monte quand la file d'attente se sature
     (sous forte charge, on devient plus sélectif).
  3. Détection ≠ Création : observer un écart est libre, mais le transformer
     en CRÉATION (nouvelle tâche générée) consomme un BUDGET DE GÉNÉRATION
     limité — garde-fou anti-emballement de la boucle auto-mandatée.
  4. Sous le seuil → l'écart est ARCHIVÉ sans alerter 95 (silencieux).

Chemin consultatif (96 → évaluateur) : lorsqu'une décision présente plusieurs
options concurrentes avec des comparaisons par paires, 96 appelle l'évaluateur
consultatif (`evaluateur_ouvert.recommander_par_preferences`) et INTÈGRE sa sortie
comme RECOMMANDATION — 96 propose, ne décide jamais (`decide=False`). Sans
comparaison, le comportement est inchangé (rétro-compatible). Voir
`FiltreAdmission.remonter_decision`.

Dépendances : bibliothèque standard uniquement (l'évaluateur est un module local du backend).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from evaluateur_ouvert import recommander_par_preferences

#: Journal JSONL par défaut : une ligne par décision remontée (future « ligne du
#: compteur » servant à mesurer si l'évaluateur change une vraie décision).
JOURNAL_DEFAUT = Path(__file__).resolve().parent / "journal_decisions.jsonl"


def _horodatage() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Decision(Enum):
    """Issue possible de l'évaluation d'un écart par le filtre."""

    ADMIS = "admis"                  # priorité ≥ seuil → escaladé vers 95
    ARCHIVE = "archive"              # priorité < seuil → archivé SANS alerter 95
    BUDGET_EPUISE = "budget_epuise"  # ≥ seuil mais création refusée (budget épuisé)


@dataclass
class Ecart:
    """
    Un « écart » = un signal repéré par l'organe 96 (« voit pour agir »).

    Les quatre premiers facteurs tirent la priorité vers le haut ; le coût la
    tire vers le bas (c'est le dénominateur de la formule). On reste sur des
    nombres simples (échelles libres, p. ex. 0–10) : seule compte la priorité
    relative au seuil.
    """

    identifiant: str
    criticite: float            # Criticité : gravité si on n'agit pas
    frequence_usage: float      # Fréquence d'usage : combien de fois cela ressort
    persistance: float          # Persistance : depuis combien de temps cela dure
    impact_utilisateur: float   # Impact Utilisateur : effet ressenti côté usager
    cout: float                 # Coût de traitement (dénominateur, > 0)
    creation: bool = False      # True si l'admettre déclenche une CRÉATION
    libelle: str = ""           # Description lisible (facultative)

    def priorite(self) -> float:
        """
        Applique la formule du conseil inter-systèmes :

            Priorité = (Criticité × Fréquence_usage × Persistance
                        × Impact_Utilisateur) / Coût

        Le coût doit être strictement positif (division).
        """
        if self.cout <= 0:
            raise ValueError(
                f"Coût invalide pour l'écart « {self.identifiant} » : "
                f"doit être strictement positif (reçu {self.cout})."
            )
        numerateur = (
            self.criticite
            * self.frequence_usage
            * self.persistance
            * self.impact_utilisateur
        )
        return numerateur / self.cout


@dataclass
class Resultat:
    """Trace lisible d'une décision d'admission (pour 96 et pour l'audit)."""

    ecart: Ecart
    priorite: float
    seuil_effectif: float
    decision: Decision
    alerte_95: bool             # True uniquement si l'écart est ADMIS
    motif: str

    def en_dict(self) -> dict:
        """Représentation JSON-sérialisable (utilisée par l'orchestrateur)."""
        return {
            "ecart": self.ecart.identifiant,
            "libelle": self.ecart.libelle,
            "priorite": round(self.priorite, 3),
            "seuil_effectif": round(self.seuil_effectif, 3),
            "decision": self.decision.value,
            "alerte_95": self.alerte_95,
            "motif": self.motif,
        }


@dataclass
class FiltreAdmission:
    """
    Filtre d'admission de l'organe 96.

    Paramètres :
      - seuil_base        : seuil de priorité quand la file est vide.
      - capacite_file     : taille de file considérée comme « pleine ».
      - budget_generation : nombre de CRÉATIONS encore autorisées.
      - coef_saturation   : intensité de la montée du seuil sous charge.
      - chemin_journal    : fichier JSONL où tracer les décisions remontées
                            (défaut : `JOURNAL_DEFAUT`). Voir `remonter_decision`.

    Le filtre conserve deux journaux : les écarts `admis` et les `archive`s,
    utiles pour l'audit (96 voit tout, n'escalade que l'essentiel vers 95).
    """

    seuil_base: float
    capacite_file: int
    budget_generation: int
    coef_saturation: float = 1.0
    chemin_journal: Optional[Path] = None  # journal JSONL des décisions (défaut : JOURNAL_DEFAUT)
    admis: list = field(default_factory=list)
    archive: list = field(default_factory=list)

    def seuil_effectif(self, taille_file: int) -> float:
        """
        Seuil DYNAMIQUE : il monte avec le taux de remplissage de la file.

            seuil = seuil_base × (1 + coef_saturation × taux_remplissage)

        File vide  → seuil = seuil_base.
        File pleine→ seuil = seuil_base × (1 + coef_saturation).
        Plus la file est saturée, plus on devient sélectif.
        """
        if self.capacite_file <= 0:
            raise ValueError("capacite_file doit être strictement positive.")
        taux = max(0.0, taille_file / self.capacite_file)  # 0 = vide, 1 = plein
        return self.seuil_base * (1.0 + self.coef_saturation * taux)

    def evaluer(self, ecart: Ecart, taille_file: int = 0) -> Resultat:
        """
        Évalue un écart et tranche : ADMIS, ARCHIVE ou BUDGET_EPUISE.

        `taille_file` = nombre d'éléments déjà en attente (sert au seuil dynamique).
        """
        priorite = ecart.priorite()
        seuil = self.seuil_effectif(taille_file)

        # 1) Sous le seuil → archivé sans alerter 95.
        if priorite < seuil:
            resultat = Resultat(
                ecart, priorite, seuil, Decision.ARCHIVE, False,
                "Sous le seuil → archivé sans alerter 95.",
            )
            self.archive.append(resultat)
            return resultat

        # 2) Au-dessus du seuil mais création sans budget → différé (Détection ≠ Création).
        if ecart.creation and self.budget_generation <= 0:
            resultat = Resultat(
                ecart, priorite, seuil, Decision.BUDGET_EPUISE, False,
                "Au-dessus du seuil mais budget de génération épuisé "
                "(Détection ≠ Création) → différé, 95 non alerté.",
            )
            self.archive.append(resultat)
            return resultat

        # 3) Admis → escaladé vers 95 (et budget consommé si c'est une création).
        if ecart.creation:
            self.budget_generation -= 1
            motif = "Admis (création) → budget consommé, escaladé vers 95."
        else:
            motif = "Admis (détection) → escaladé vers 95."
        resultat = Resultat(ecart, priorite, seuil, Decision.ADMIS, True, motif)
        self.admis.append(resultat)
        return resultat

    def filtrer(self, ecarts, taille_file: int = 0) -> list:
        """
        Évalue un lot d'écarts et renvoie les ADMIS triés par priorité
        décroissante (la liste prête à remonter à 95).
        """
        resultats = [self.evaluer(e, taille_file) for e in ecarts]
        admis = [r for r in resultats if r.decision is Decision.ADMIS]
        admis.sort(key=lambda r: r.priorite, reverse=True)
        return admis

    def remonter_decision(
        self,
        options,
        comparaisons=None,
        *,
        identifiant: str = "decision",
        libelle: str = "",
        suivi: Any = None,
        journal=None,
    ) -> dict:
        """
        96 remonte vers 95 une DÉCISION à options concurrentes — sans jamais trancher.

        Chemin consultatif : si des `comparaisons` par paires (« gagnant > perdant »)
        sont fournies, 96 appelle `recommander_par_preferences(options, comparaisons)`
        et INTÈGRE sa sortie comme RECOMMANDATION. **96 propose, ne décide jamais**
        (`decide=False`) et **n'obéit pas automatiquement** à l'évaluateur : il **logue**
        la reco, il ne la suit pas.

        Rétro-compatibilité : sans comparaison (None / liste vide), 96 se comporte
        comme avant — pas d'appel à l'évaluateur, pas de recommandation.

        **Trace persistante (à CHAQUE appel).** Une ligne JSONL est ajoutée au journal
        (`journal` > `self.chemin_journal` > `JOURNAL_DEFAUT`) : c'est la future ligne
        du « compteur » pour mesurer si l'évaluateur change une vraie décision. Elle
        logue la décision, les options, le **classement rendu par l'évaluateur**, et
        `suivi` = ce qui a été **réellement suivi** (None tant que 96 ne fait que
        recommander ; renseigné plus tard par la boucle décisionnelle).

        :returns: dict prêt à remonter à 95 (inclut `trace` = la ligne écrite et
            `journal` = le chemin du journal).
        """
        options = list(options)
        sortie = {
            "organe": "96",
            "type": "decision_multi_options",
            "identifiant": identifiant,
            "libelle": libelle,
            "options": options,
            "decide": False,            # 96 propose, ne décide JAMAIS
            "consulte_evaluateur": False,
            "recommandation": None,
            "motif": "",
        }
        if comparaisons:  # chemin consultatif : 96 APPELLE l'évaluateur
            recommandation = recommander_par_preferences(options, comparaisons)
            # Invariant : l'évaluateur ne décide jamais non plus.
            assert recommandation.get("decide") is False
            sortie["consulte_evaluateur"] = True
            sortie["recommandation"] = recommandation
            sortie["motif"] = (
                "Comparaisons fournies → 96 a consulté l'évaluateur et remonte sa "
                "RECOMMANDATION à 95 (96 logue, n'obéit pas : decide=False)."
            )
        else:  # rétro-compatible : comportement strictement inchangé
            sortie["motif"] = (
                "Aucune comparaison → 96 remonte les options brutes à 95 "
                "(comportement inchangé, sans recommandation)."
            )

        # TRACE persistante JSONL — écrite à chaque appel (le « compteur »).
        chemin = Path(journal) if journal else (self.chemin_journal or JOURNAL_DEFAUT)
        sortie["trace"] = self._tracer(sortie, suivi=suivi, chemin=chemin)
        sortie["journal"] = str(chemin)
        return sortie

    def _tracer(self, sortie: dict, *, suivi: Any, chemin: Path) -> dict:
        """Construit la ligne de trace d'une décision et l'ÉCRIT (append JSONL)."""
        reco = sortie.get("recommandation")
        verdict = reco["verdict"] if reco else None
        entree = {
            "horodatage": _horodatage(),
            "identifiant": sortie["identifiant"],
            "libelle": sortie["libelle"],
            "decide": False,  # 96 ne décide jamais (même si 'suivi' est renseigné ensuite)
            "consulte_evaluateur": sortie["consulte_evaluateur"],
            "options": sortie["options"],
            "classement": verdict["classement"] if verdict else None,
            "tete_recommandee": verdict["tete"] if verdict else None,
            "confiance": verdict["confiance"] if verdict else None,
            "signaux": {
                "cycles": len(reco["cycles"]) if reco else 0,
                "separation": reco["divergence"]["separation"] if reco else False,
                "bt_vs_copeland": reco["divergence"]["bt_vs_copeland"] if reco else False,
            },
            "suivi": suivi,  # ce qui a été RÉELLEMENT suivi (None = pas encore renseigné)
        }
        chemin.parent.mkdir(parents=True, exist_ok=True)
        with chemin.open("a", encoding="utf-8") as flux:
            flux.write(json.dumps(entree, ensure_ascii=False) + "\n")
        return entree
