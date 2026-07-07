#!/usr/bin/env python3
"""
NEXUS — Agent OS : assemblage d'un LLM RÉEL (Anthropic) sur AdaptateurAnthropic
« Le hub connaît l'interface, jamais le fournisseur — la clé vit ici, pas là. »

AdaptateurAnthropic (nexus_adaptateur_llm.py, brique prouvée) reçoit son client
par INJECTION et ne lit JAMAIS l'environnement : un garde-fou AST dédié lui
interdit toute référence à os.environ / os.getenv. Ce fichier-ci est l'AUTRE
moitié du geste — le point d'assemblage où l'on lit la clé et où l'on fabrique
un VRAI client anthropic, puis où on l'injecte dans l'adaptateur.

Frontière respectée :
  - lire l'environnement est ATTENDU et AUTORISÉ ici (ce n'est pas l'adaptateur) ;
  - la clé ne vit QUE dans l'environnement : jamais de valeur par défaut, jamais
    de clé en dur, jamais loggée (le message d'erreur ne la contient pas — et
    pour cause, dans le cas d'erreur elle n'existe pas) ;
  - la colonne vertébrale (nexus_bus, nexus_agentos, nexus_orchestrateur) et
    l'adaptateur lui-même restent INCHANGÉS : on ne fait que les assembler.

router(bus, adaptateurs, ...) attend une simple LISTE d'objets NexusAdapter ;
construire_adaptateur_anthropic() en fabrique un, prêt à figurer dans cette
liste :

    from nexus_llm_reel import construire_adaptateur_anthropic
    adaptateurs = [construire_adaptateur_anthropic("claude")]
    router(bus, adaptateurs, ...)

Aucun test ne fabrique un VRAI client : en CI, la lib anthropic est stubbée et
la clé est une valeur factice (zéro réseau, zéro coût, zéro secret réel).
L'import de la lib anthropic est PARESSEUX (dans la fabrique) : le module
s'importe même quand anthropic n'est pas installé — seul l'assemblage d'un
vrai client l'exige.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
from nexus_adaptateur_llm import AdaptateurAnthropic  # l'adaptateur, inchangé

VARIABLE_CLE = "ANTHROPIC_API_KEY"  # nom de la variable, PAS une clé


def construire_adaptateur_anthropic(nom="claude", **kwargs):
    """Assemble un AdaptateurAnthropic branché sur un VRAI client Anthropic.

    Lit la clé dans la variable d'environnement ANTHROPIC_API_KEY (fournie par
    l'utilisateur, jamais codée ici), construit un client réel via la lib
    anthropic, puis l'injecte dans l'adaptateur. Les kwargs (roles,
    max_tentatives, backoff_base, timeout_global, sleep, maintenant…) sont
    transmis tels quels à AdaptateurAnthropic.

    Lève RuntimeError — message explicite, SANS la clé — si la variable est
    absente ou vide : jamais de valeur par défaut, jamais de repli silencieux.
    """
    cle = os.environ.get(VARIABLE_CLE, "").strip()
    if not cle:
        # Message SANS la clé (elle n'existe pas) et sans rien logger d'autre.
        raise RuntimeError(
            f"variable d'environnement {VARIABLE_CLE} absente ou vide : "
            f"impossible de fabriquer un client Anthropic réel pour {nom!r}")

    import anthropic  # import PARESSEUX : requis seulement pour un vrai client

    client = anthropic.Anthropic(api_key=cle)
    return AdaptateurAnthropic(nom, client, **kwargs)
