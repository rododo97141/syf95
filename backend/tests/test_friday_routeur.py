"""Friday brique 1 — routeur : règles pures sur vocabulaire fermé, pas de LLM.
Jeu FIXE de commandes → routage correct ; bruit ambiant réaliste → REFUS
explicite (aucune intention, aucun argument)."""
import os, sys


def _organes():
    ici = os.path.dirname(os.path.abspath(__file__))          # backend/tests
    racine = os.path.dirname(os.path.dirname(ici))            # racine du repo
    return os.path.join(racine, "organes")


org = _organes()
if org not in sys.path:
    sys.path.insert(0, org)
import friday_routeur


# Jeu FIXE : (ligne transcrite, intention attendue, argument attendu)
CAS_FIXES = [
    ("montre nexus_sense.py", "montre", "nexus_sense.py"),
    ("Montre-moi le moteur", "montre", "le moteur"),
    ("affiche valeurs_nexus.md", "montre", "valeurs_nexus.md"),
    ("où est le routeur", "ou_est", "le routeur"),
    ("ou est nexus_force", "ou_est", "nexus_force"),
    ("Où se trouve la mémoire ?", "ou_est", "la memoire"),
    ("explique nexus_pont", "explique", "nexus_pont"),
    ("Explique-moi log_event", "explique", "log_event"),
    ("statut", "statut", None),
    ("Statut ?", "statut", None),
    ("état", "statut", None),
]

# Bruit : conversation ambiante réaliste autour du micro → zéro déclenchement.
BRUIT = [
    "il fait beau aujourd'hui",
    "tu peux baisser la musique s'il te plaît",
    "on mange à quelle heure ce soir",
    "je crois que le facteur est passé",
    "attends deux secondes j'arrive",
    "le statut de la réunion n'est pas clair",   # mot-clé pas seul sur la ligne
    "elle explique toujours tout très bien",     # mot-clé pas en tête de ligne
    "montre",                                    # commande sans argument
    "affiche",
    "où est",
    "",
    "   ",
]


def test_jeu_fixe_route_correctement():
    for texte, intention, argument in CAS_FIXES:
        resultat = friday_routeur.router(texte)
        assert resultat == {"intention": intention, "argument": argument}, texte


def test_bruit_ambiant_refus_explicite():
    for texte in BRUIT:
        resultat = friday_routeur.router(texte)
        assert resultat == {"intention": friday_routeur.REFUS, "argument": None}, texte


def test_vocabulaire_ferme_tables_et_intentions_alignees():
    # La table EST la règle : toute intention servie vient des tables déclarées,
    # et les tables ne servent que les intentions annoncées.
    servies = set(friday_routeur.PREFIXES.values()) | set(friday_routeur.EXACTS.values())
    assert servies == set(friday_routeur.INTENTIONS)
