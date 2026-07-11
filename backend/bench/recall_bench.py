#!/usr/bin/env python3
"""Banc de qualité recall REPRODUCTIBLE — outil de MESURE, LECTURE SEULE.

POURQUOI
    Le gain recall (v0 → titre embarqué → ONNX local) a été mesuré à la main
    plusieurs fois, sans laisser de trace. Ce banc rend la mesure
    REPRODUCTIBLE : pour tout futur essai de modèle/réglage, il chiffre le
    recall@1 / recall@3 en LEXICAL et (si un embedder local est disponible) en
    SÉMANTIQUE, sur un corpus figé.

    Ce n'est PAS un test de qualité bloquant. La CI n'a pas de modèle local :
    le banc y tourne en LEXICAL seul (informatif). Le sémantique est un BONUS
    opt-in ; son absence n'est jamais un échec, seulement un « indisponible »
    honnête.

GARDE-FOUS
    • LECTURE SEULE : le banc IMPORTE recall / rank / embedder, il n'en
      MODIFIE aucun. Il n'écrit QUE dans un dossier temporaire jetable (le
      corpus-fixture), jamais dans la vraie mémoire ni dans un organe.
    • DÉTERMINISTE sur la fixture : corpus + requêtes figés, tmpdir isolé,
      zéro réseau. Le classement lexical (IDF × force, départage stable par
      chemin) rend l'ordre reproductible quel que soit l'ordre de parcours.
    • HONNÊTETÉ : embedder absent ⇒ « sémantique indisponible », JAMAIS un
      faux score sémantique (le lexical n'est jamais rebaptisé sémantique).

PÉRIMÈTRE (hors périmètre)
    Pas de vrais logs d'usage (les requêtes sont construites), pas de
    conversion/pose de modèle, aucune modification de recall/rank/embedder,
    pas de MRR/nDCG (r@1/r@3 suffit).

USAGE
    python -m bench.recall_bench           # corpus-fixture (défaut)
    MEMOIRE_ROOT=/chemin python -m bench.recall_bench   # corpus RÉEL
"""
import contextlib
import os
import sys
import tempfile
import importlib
import importlib.util


# --------------------------------------------------------------------------- #
# Chargement des organes — même stratégie de sys.path que le recall lui-même :
# organes/ pour nexus_force / nexus_embedder, et le skill memoire-beta pour
# memory_api (chargé par chemin de fichier, hors des packages Python).
# --------------------------------------------------------------------------- #
def _racine():
    ici = os.path.dirname(os.path.abspath(__file__))          # backend/bench
    return os.path.dirname(os.path.dirname(ici))              # racine du dépôt


def _ajouter_organes_au_path():
    org = os.path.join(_racine(), "organes")
    if org not in sys.path:
        sys.path.insert(0, org)
    return org


def _charger_memory_api():
    """Charge memory_api depuis le skill (par chemin de fichier). Le recall du
    banc passe par memory_api.recall — la source de vérité du rappel."""
    chemin = os.path.join(_racine(), ".claude", "skills", "memoire-beta",
                          "scripts", "memory_api.py")
    spec = importlib.util.spec_from_file_location("memory_api_bench", chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _charger_embedder():
    """Fabrique l'embedder LOCAL via nexus_embedder, ou None (pas de modèle).
    None ⇒ sémantique indisponible ⇒ banc en lexical seul (jamais n-grammes)."""
    _ajouter_organes_au_path()
    import nexus_embedder
    return nexus_embedder.charger_embedder()


# --------------------------------------------------------------------------- #
# (1) CORPUS_FIXTURE — ~13 fiches synthétiques FR. Chaque fiche porte un VRAI
# titre au format « # Titre — domaine: X / catégorie: Y ». Six fiches sont des
# CIBLES récupérables par reformulation ; les autres sont du BRUIT du même
# domaine (partage partiel de vocabulaire, jamais les tokens distinctifs).
# --------------------------------------------------------------------------- #
CORPUS_FIXTURE = [
    # --- CIBLES ------------------------------------------------------------ #
    {
        "domain": "cuisine", "category": "boulangerie", "nom": "pain-levain-maison",
        "titre": "Réussir le pain au levain maison",
        "corps": ("La fermentation lente de la pâte à pain développe les arômes. "
                  "Un levain naturel bien nourri, une farine complète et une "
                  "bonne hydratation font la mie. On façonne dans un banneton, "
                  "on pratique l'autolyse, on incise la grigne avant cuisson."),
        "cible": True,
    },
    {
        "domain": "jardinage", "category": "potager", "nom": "tomates-arrosage",
        "titre": "Arroser les tomates du potager",
        "corps": ("Un arrosage régulier au pied évite le stress hydrique des "
                  "tomates. Le paillage garde l'humidité, le tuteurage soutient "
                  "les pieds, et un goutte-à-goutte limite le mildiou sur le "
                  "feuillage exposé au soleil."),
        "cible": True,
    },
    {
        "domain": "informatique", "category": "reseau", "nom": "vpn-securite",
        "titre": "Sécuriser sa connexion avec un VPN",
        "corps": ("Un VPN protège la connexion chiffrée en créant un tunnel "
                  "vers un serveur distant. Le chiffrement masque l'adresse IP "
                  "et préserve la confidentialité. Le protocole wireguard et la "
                  "protection contre la fuite DNS renforcent l'ensemble."),
        "cible": True,
    },
    {
        "domain": "sante", "category": "sommeil", "nom": "insomnie-conseils",
        "titre": "Mieux dormir et vaincre l'insomnie",
        "corps": ("Contre les réveils nocturnes, un rituel de coucher régulier "
                  "aide l'endormissement. On limite la caféine et les écrans "
                  "bleus le soir ; la mélatonine peut soutenir un sommeil "
                  "réparateur quand l'insomnie s'installe."),
        "cible": True,
    },
    {
        "domain": "finance", "category": "epargne", "nom": "livret-epargne",
        "titre": "Choisir un livret d'épargne",
        "corps": ("Comparer un livret d'épargne, c'est peser le rendement, le "
                  "plafond de dépôt et la fiscalité. La disponibilité immédiate "
                  "des fonds et la régularité des versements comptent autant que "
                  "le taux d'intérêt affiché."),
        "cible": True,
    },
    {
        "domain": "cuisine", "category": "dessert", "nom": "tarte-citron-meringuee",
        "titre": "La tarte au citron meringuée",
        "corps": ("Sur une pâte sablée, une crème acidulée au citron et des "
                  "zestes. La meringue italienne, montée avec des blancs "
                  "d'œufs, est dorée au four pour un dessert acidulé et léger."),
        "cible": True,
    },
    # --- BRUIT (même domaine, vocabulaire partiel, jamais les tokens rares) - #
    {
        "domain": "cuisine", "category": "dessert", "nom": "mousse-chocolat",
        "titre": "La mousse au chocolat classique",
        "corps": ("Le chocolat fondu, incorporé à des jaunes puis à des blancs "
                  "montés en neige avec un peu de sucre, donne une mousse "
                  "aérienne à laisser prendre au frais."),
        "cible": False,
    },
    {
        "domain": "cuisine", "category": "boulangerie", "nom": "baguette-tradition",
        "titre": "La baguette de tradition",
        "corps": ("Une baguette croustillante demande un bon pétrissage, un "
                  "repos suffisant et une cuisson à four très chaud avec de la "
                  "buée pour dorer la croûte."),
        "cible": False,
    },
    {
        "domain": "jardinage", "category": "potager", "nom": "courgettes-culture",
        "titre": "Cultiver des courgettes",
        "corps": ("Les courgettes aiment un sol riche et un arrosage suivi. "
                  "Semis au chaud, repiquage après les gelées, récolte régulière "
                  "des fruits jeunes pour prolonger la production."),
        "cible": False,
    },
    {
        "domain": "jardinage", "category": "fleurs", "nom": "roses-taille",
        "titre": "Tailler les rosiers",
        "corps": ("Une taille de fin d'hiver au sécateur, au-dessus d'un œil "
                  "vers l'extérieur, favorise une floraison généreuse et un "
                  "port aéré du rosier."),
        "cible": False,
    },
    {
        "domain": "informatique", "category": "materiel", "nom": "ssd-choix",
        "titre": "Choisir un disque SSD",
        "corps": ("Un SSD accélère le démarrage grâce à sa vitesse de lecture. "
                  "On regarde la capacité de stockage, l'interface et "
                  "l'endurance selon l'usage."),
        "cible": False,
    },
    {
        "domain": "informatique", "category": "reseau", "nom": "wifi-config",
        "titre": "Configurer son wifi domestique",
        "corps": ("Placer le routeur au centre du logement améliore le débit. "
                  "Un mot de passe robuste et le bon canal réduisent les "
                  "interférences du réseau sans fil."),
        "cible": False,
    },
    {
        "domain": "finance", "category": "budget", "nom": "gerer-budget",
        "titre": "Gérer son budget mensuel",
        "corps": ("Lister les dépenses et les revenus, distinguer le fixe du "
                  "variable, puis dégager une part d'économies : un budget "
                  "mensuel clair évite les mauvaises surprises."),
        "cible": False,
    },
]


# --------------------------------------------------------------------------- #
# (2) REQUETES — (requête, cible_nom, famille), famille ∈ {reformulation,
# controle}. Une REFORMULATION dit la cible avec d'autres mots (test du vrai
# rappel). Un CONTROLE est fait des tokens RARES de la cible (vocabulaire
# apparié) : il DOIT être facile — c'est l'ancre haute du harnais.
# --------------------------------------------------------------------------- #
REFORMULATION = "reformulation"
CONTROLE = "controle"

REQUETES = [
    # pain-levain-maison — reformulation qui garde des tokens distinctifs (hit).
    ("réussir la fermentation d'une pâte à pain", "pain-levain-maison", REFORMULATION),
    ("banneton autolyse grigne", "pain-levain-maison", CONTROLE),
    # tomates-arrosage — reformulation partageant des tokens distinctifs (hit).
    ("quelle fréquence d'arrosage pour les tomates", "tomates-arrosage", REFORMULATION),
    ("mildiou tuteurage paillage", "tomates-arrosage", CONTROLE),
    # tarte-citron-meringuee — reformulation partageant citron/dessert (hit).
    ("recette de dessert acidulé au citron", "tarte-citron-meringuee", REFORMULATION),
    ("meringue italienne zestes sablée", "tarte-citron-meringuee", CONTROLE),
    # vpn-securite — reformulation FIDÈLE mais lexicalement pauvre : le sens y
    # est ("rester anonyme sur le web") mais aucun token exact de la cible → le
    # lexical la manque. C'est justement le cas où le sémantique aiderait.
    ("rester anonyme sur le web", "vpn-securite", REFORMULATION),
    ("wireguard tunnel fuite dns", "vpn-securite", CONTROLE),
    # insomnie-conseils — reformulation FIDÈLE mais sans token exact de la cible.
    ("je n'arrive pas à m'assoupir la nuit", "insomnie-conseils", REFORMULATION),
    ("mélatonine endormissement caféine", "insomnie-conseils", CONTROLE),
    # livret-epargne — reformulation FIDÈLE dont les mots (« économies ») pointent
    # ailleurs : le lexical part sur une autre fiche → la cible est manquée.
    ("où mettre mes économies à l'abri", "livret-epargne", REFORMULATION),
    ("fiscalité versement disponibilité", "livret-epargne", CONTROLE),
]

FAMILLES = (REFORMULATION, CONTROLE)


# --------------------------------------------------------------------------- #
# (3) _corpus_temporaire — écrit le corpus dans un MEMOIRE_ROOT temporaire, sous
# structure/<domaine>/<catégorie>/<nom>.md (comme le _fiche des tests). Zéro
# réseau, tmpdir jetable auto-nettoyé. Rien n'est écrit hors du tmpdir.
# --------------------------------------------------------------------------- #
def _contenu_fiche(fiche):
    """Rend le contenu markdown : un VRAI titre au format attendu, puis le corps.
    Le format « # Titre — domaine: X / catégorie: Y » est exactement celui que
    `nexus_force._titre_fiche` sait extraire et dont il coupe la queue méta."""
    return ("# %s — domaine: %s / catégorie: %s\n\n%s\n"
            % (fiche["titre"], fiche["domain"], fiche["category"], fiche["corps"]))


@contextlib.contextmanager
def _corpus_temporaire(corpus):
    """Contexte : écrit `corpus` dans un MEMOIRE_ROOT temporaire et cède la
    racine. Structure structure/<dom>/<cat>/<nom>.md. Auto-nettoyé en sortie."""
    with tempfile.TemporaryDirectory(prefix="recall_bench_") as root:
        struct = os.path.join(root, "structure")
        for fiche in corpus:
            d = os.path.join(struct, fiche["domain"], fiche["category"])
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, fiche["nom"] + ".md"), "w",
                      encoding="utf-8") as f:
                f.write(_contenu_fiche(fiche))
        yield root


# --------------------------------------------------------------------------- #
# (4) mesurer — fonction PURE de mesure. Par requête, appelle memory_api.recall
# (sémantique si embedder ≠ None, sinon lexical), trouve la position 1-indexée
# de la cible dans les résultats, agrège r@1 / r@3 PAR FAMILLE. Aucune écriture
# hors du memoire_root fourni (elle ne fait que LIRE).
# --------------------------------------------------------------------------- #
def _configurer_memory_api(m, memoire_root):
    """Pointe les globales de memory_api sur `memoire_root` (lecture seule pour
    le recall). Ne crée rien : le corpus est déjà en place (fixture ou réel)."""
    m.ROOT = str(memoire_root)
    m.STRUCT = os.path.join(str(memoire_root), "structure")
    m.EN_ATTENTE = os.path.join(str(memoire_root), "en_attente")
    m.BRUT = os.path.join(str(memoire_root), "brut")
    m.ARCHIVE = os.path.join(str(memoire_root), "archive")


def _position_cible(results, cible_nom):
    """Position 1-INDEXÉE de la cible dans `results` (1 = premier), ou None si
    absente. La cible est le fichier « <nom>.md ». 1-indexé : c'est l'invariant
    qu'une mutation 0-indexée casserait."""
    fichier = cible_nom + ".md"
    for i, r in enumerate(results):
        if r.get("file") == fichier:
            return i + 1                      # 1-indexé : premier = 1, jamais 0
    return None


def _r_at_k(positions, k):
    """Recall@k : fraction des requêtes dont la cible est dans le top-k.
    <= k (inclusif) et 1-indexé : une cible en position k COMPTE. Passer à < k
    ou au 0-index fausserait ce chiffre (mutation vue rouge)."""
    if not positions:
        return 0.0
    touches = sum(1 for p in positions if p is not None and p <= k)
    return touches / len(positions)


def _recall(m, query, embedder):
    """Appelle memory_api.recall en mode sémantique si un embedder est injecté,
    sinon en lexical. Scope « structure » : le corpus vit entièrement là."""
    params = {"query": [query], "scope": ["structure"]}
    if embedder is not None:
        params["mode"] = ["semantique"]
        return m.recall(params, embedder=embedder)
    return m.recall(params)


def mesurer(embedder, memoire_root):
    """Mesure r@1 / r@3 par famille sur REQUETES contre `memoire_root`.

    Fonction PURE de mesure : elle configure memory_api sur la racine fournie,
    LIT via recall, et n'écrit rien. Renvoie
    {famille: {"r@1": float, "r@3": float, "n": int, "positions": [...]}}.
    """
    m = _charger_memory_api()
    _configurer_memory_api(m, memoire_root)

    positions = {famille: [] for famille in FAMILLES}
    for query, cible_nom, famille in REQUETES:
        rep = _recall(m, query, embedder)
        pos = _position_cible(rep.get("results", []), cible_nom)
        positions[famille].append(pos)

    rapport = {}
    for famille in FAMILLES:
        pos = positions[famille]
        rapport[famille] = {
            "r@1": _r_at_k(pos, 1),
            "r@3": _r_at_k(pos, 3),
            "n": len(pos),
            "positions": pos,
        }
    return rapport


# --------------------------------------------------------------------------- #
# Rapport — assemble lexical (TOUJOURS) et sémantique (SEULEMENT si embedder).
# HONNÊTETÉ : sans embedder, `semantique` reste None et `semantique_disponible`
# False — jamais un score sémantique fabriqué à partir du lexical.
# --------------------------------------------------------------------------- #
def construire_rapport(memoire_root, embedder=None, embedder_version=None):
    """Rapport complet pour `memoire_root`. Lexical toujours mesuré ; sémantique
    mesuré UNIQUEMENT si `embedder` est fourni. Sinon, honnêtement indisponible."""
    lexical = mesurer(None, memoire_root)
    if embedder is not None:
        semantique = mesurer(embedder, memoire_root)
        version = embedder_version or getattr(embedder, "version", "inconnue")
        dispo = True
    else:
        semantique = None                     # JAMAIS un faux score sémantique
        version = None
        dispo = False
    return {
        "familles": list(FAMILLES),
        "lexical": lexical,
        "semantique": semantique,
        "semantique_disponible": dispo,
        "embedder_version": version,
    }


def formater_rapport(rapport):
    """Rend le TABLEAU (familles × {lexical, sémantique} × {r@1, r@3}) + la
    version de l'embedder, ou la mention d'indisponibilité. Sans embedder, la
    colonne sémantique affiche « indispo » — jamais un chiffre."""
    dispo = rapport["semantique_disponible"]
    lignes = []
    lignes.append("Banc recall — r@1 / r@3 par famille")
    if dispo:
        lignes.append("embedder : %s" % rapport["embedder_version"])
    else:
        lignes.append("lexical seul, sémantique indisponible")
    lignes.append("")
    entete = "%-16s | %-15s | %-15s" % ("famille", "lexical", "sémantique")
    lignes.append(entete)
    lignes.append("-" * len(entete))
    for famille in rapport["familles"]:
        lex = rapport["lexical"][famille]
        cell_lex = "r@1=%.2f r@3=%.2f" % (lex["r@1"], lex["r@3"])
        if dispo:
            sem = rapport["semantique"][famille]
            cell_sem = "r@1=%.2f r@3=%.2f" % (sem["r@1"], sem["r@3"])
        else:
            cell_sem = "indispo"
        lignes.append("%-16s | %-15s | %-15s" % (famille, cell_lex, cell_sem))
    return "\n".join(lignes)


# --------------------------------------------------------------------------- #
# (5) main — corpus RÉEL si $MEMOIRE_ROOT défini, sinon la FIXTURE. Lexical
# TOUJOURS ; sémantique SEULEMENT si charger_embedder() rend un embedder.
# --------------------------------------------------------------------------- #
def main():
    embedder = _charger_embedder()            # None si aucun modèle local
    racine_env = os.environ.get("MEMOIRE_ROOT")
    if racine_env:
        print("Corpus RÉEL : %s\n" % racine_env)
        rapport = construire_rapport(racine_env, embedder=embedder)
        print(formater_rapport(rapport))
    else:
        print("Corpus FIXTURE (%d fiches, %d requêtes)\n"
              % (len(CORPUS_FIXTURE), len(REQUETES)))
        with _corpus_temporaire(CORPUS_FIXTURE) as root:
            rapport = construire_rapport(root, embedder=embedder)
            print(formater_rapport(rapport))
    return 0


if __name__ == "__main__":
    sys.exit(main())
