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

Aucune dépendance externe : bibliothèque standard uniquement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


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

    Le filtre conserve deux journaux : les écarts `admis` et les `archive`s,
    utiles pour l'audit (96 voit tout, n'escalade que l'essentiel vers 95).
    """

    seuil_base: float
    capacite_file: int
    budget_generation: int
    coef_saturation: float = 1.0
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
