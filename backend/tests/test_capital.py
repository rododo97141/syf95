"""Brique HITL capitalisante — organes/nexus_capital.py.

Couvre le mandat point par point (isolation TOTALE : MEMOIRE_ROOT, CAPTEURS_ROOT
et les journaux de nexus_lecons sont redirigés vers des dossiers jetables ; on ne
touche JAMAIS le vrai memoire_data/ ni le vrai journal des leçons) :

  T1  capitaliser conforme au format du corpus réel + slug dérivé UNE fois +
      non-duplication en INVARIANT (éditer la fiche .md → consulter reflète le
      changement ; le pointeur de leçon n'a AUCUNE copie divergente).
  T2  consulter : délégation PURE à rank() + journalisation + une fiche
      criteres-kily dans le VRAI emplacement corpus retrouvée top-3 en
      vocabulaire apparié + reformulation synonyme en xfail STRICT.
  T3  appliquer : capteur bien formé avec statut vérifié CONTRE calculer_forces
      réel (succes|echec, les seuls comptés) + transfert + REFUS si multi-fiches.
  T4  chaîne complète sans valeurs en dur : k applications mixtes → calculer_forces
      non-vide et borné, rank() départage à pertinence égale en faveur du slug valide.
  T5  les DEUX successeurs du garde-fou retiré de test_recall_multisignaux.py :
      (a) forces distinctes discriminent le classement (RED→GREEN prouvé) ;
      (b) force bornée NON dominante AU VRAI PLAFOND (chaîne réelle jusqu'à
          saturation FORCE_MAX/FORCE_MIN, ratio 25×, la pertinence gagne).
  T6  bilan : fiche-unique oubliée > N jours DANS la dette ; appliquée ou
      close-sans-dette HORS dette ; multi-fiches JAMAIS dedans ; verdict 98
      non-SAIN au-delà du seuil ; bilan cassé mais 98 debout.
  T7  empreintes SHA-256 identiques sur tout ce qui n'est PAS les fichiers
      propres de nexus_capital (les organes gelés + une fiche corpus étrangère).
  T8  = la suite complète verte (zéro régression) — vérifiée par l'exécution
      pytest, cf. corps de PR.
  T9  secret de confirmation optionnel (capital/jeton_secret.json, hash SHA-256
      SEUL — jamais le secret en clair) : sans configuration, comportement
      HISTORIQUE inchangé ; configuré, REFUS sans secret ET avec un mauvais
      secret, ACCEPTE avec le bon secret et le jeton fonctionne normalement
      avec appliquer().
"""
import os
import sys
import json
import types
import hashlib
import datetime
import importlib
import importlib.util

import pytest


# --------------------------------------------------------------------------- #
# Chargement des modules
# --------------------------------------------------------------------------- #
def _racine_depot():
    ici = os.path.dirname(os.path.abspath(__file__))          # backend/tests
    return os.path.dirname(os.path.dirname(ici))              # racine du dépôt


def _organes():
    org = os.path.join(_racine_depot(), "organes")
    if org not in sys.path:
        sys.path.insert(0, org)
    return org


def _charger_memory_api():
    chemin = os.path.join(_racine_depot(), ".claude", "skills", "memoire-beta",
                          "scripts", "memory_api.py")
    spec = importlib.util.spec_from_file_location("memory_api_capital_test", chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Cap:
    """Contexte de test : modules chargés + racines isolées."""


@pytest.fixture
def cap(tmp_path, monkeypatch):
    _organes()
    racine_memoire = tmp_path / "memoire_data"
    monkeypatch.setenv("MEMOIRE_ROOT", str(racine_memoire))   # relu à chaque appel

    import nexus_force
    import nexus_sense
    import nexus_lecons
    import nexus_capital
    nexus_force = importlib.reload(nexus_force)
    # journaux de leçons isolés (nexus_lecons n'a pas d'override d'env : on patche
    # ses globales, comme les autres tests patchent memory_api).
    dl = tmp_path / "lecons"
    monkeypatch.setattr(nexus_lecons, "DIR", str(dl))
    monkeypatch.setattr(nexus_lecons, "JOURNAL", str(dl / "journal.jsonl"))
    monkeypatch.setattr(nexus_lecons, "TRANSFERT", str(dl / "transfert.jsonl"))

    c = _Cap()
    c.nf = nexus_force
    c.sense = nexus_sense
    c.lecons = nexus_lecons
    c.cap = nexus_capital
    c.tmp = tmp_path
    c.racine_memoire = racine_memoire
    c.capteurs_journal = os.path.join(os.environ["CAPTEURS_ROOT"], "capteurs", "journal.jsonl")
    return c


def _capteurs(c):
    if not os.path.exists(c.capteurs_journal):
        return []
    return [json.loads(l) for l in open(c.capteurs_journal, encoding="utf-8") if l.strip()]


class _EmbedderConstant:
    """Même vecteur pour tout → sem constant, qui s'annule dans le classement :
    ISOLE l'effet force vs pertinence (comme le garde-fou d'origine)."""
    def embed(self, text):
        return [1.0, 0.0, 0.0]


# =========================================================================== #
# T1 — capitaliser : format corpus réel, slug une fois, non-duplication invariant
# =========================================================================== #
def test_t1_capitaliser_format_corpus_slug_unique_non_duplication(cap):
    q = "Quels critères pour juger une synthèse ouverte"
    slug = cap.cap.capitaliser(q, "reponse ORIGINALE verbatim de Kily",
                               "tâche subjective de synthèse", "nexus",
                               pourquoi="la concision prime")
    chemin = cap.cap._chemin_fiche("nexus", slug)
    texte = open(chemin, encoding="utf-8").read()

    # --- format du corpus réel (miroir de _write_struct) ---
    lignes = texte.splitlines()
    assert lignes[0] == "# %s — domaine: nexus / catégorie: criteres-kily" % q
    assert lignes[1].startswith("> Créé le ") and "Dernière mise à jour le" in lignes[1]
    assert "## En bref" in texte and "## Détail" in texte
    assert "### Réponse (verbatim)" in texte
    assert "reponse ORIGINALE verbatim de Kily" in texte      # verbatim présent
    assert "tâche subjective de synthèse" in texte            # contexte présent
    assert "### Pourquoi" in texte and "la concision prime" in texte

    # --- slug dérivé UNE fois : recapitaliser le même intitulé → MÊME fichier ---
    slug2 = cap.cap.capitaliser(q, "reponse ORIGINALE verbatim de Kily",
                                "tâche subjective de synthèse", "nexus")
    assert slug2 == slug
    fiches = [f for f in os.listdir(cap.cap._dir_fiches("nexus")) if f.endswith(".md")]
    assert fiches == [slug + ".md"]                            # pas de doublon

    # --- INVARIANT non-duplication : la fiche est la SOURCE unique. Éditer la
    #     fiche → consulter reflète le changement ; le pointeur de leçon n'a
    #     aucune copie divergente de la réponse. ---
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(texte.replace("reponse ORIGINALE verbatim de Kily",
                              "reponse EDITEE editedtokenxyz"))
    # consulter lit la fiche À CHAUD : un token présent SEULEMENT dans la version
    # éditée la retrouve → aucune copie figée en amont.
    rec = cap.cap.consulter("editedtokenxyz", "tâche")
    assert slug in rec["slugs_retournes"]

    lecons_txt = open(cap.lecons.JOURNAL, encoding="utf-8").read()
    assert "reponse ORIGINALE" not in lecons_txt              # jamais copié…
    assert "editedtokenxyz" not in lecons_txt                 # …ni l'édition
    assert slug in lecons_txt                                 # seulement la RÉFÉRENCE

    # contexte obligatoire : sans lui, on lève (pas de fiche muette).
    with pytest.raises(ValueError):
        cap.cap.capitaliser("Q sans contexte", "r", "", "nexus")


# =========================================================================== #
# T2 — consulter : délégation pure + journalisation + top-3 + xfail synonyme
# =========================================================================== #
def test_t2_consulter_delegation_pure_journalisation_et_top3(cap, monkeypatch):
    cible = cap.cap.capitaliser("Critères qualité pour un rapport zorglubide détaillé",
                                "réponse cible", "revue de rapport", "nexus")
    cap.cap.capitaliser("Critères pour une relecture orthographique", "r2", "ctx", "nexus")
    cap.cap.capitaliser("Critères pour un choix de librairie technique", "r3", "ctx", "nexus")

    # --- délégation PURE : rank() est appelé, et l'ordre de consulter EST le sien ---
    vrai_rank = cap.nf.rank
    appels = {"n": 0}

    def _spy(query, cands, **kw):
        appels["n"] += 1
        return vrai_rank(query, cands, **kw)
    monkeypatch.setattr(cap.nf, "rank", _spy)

    rec = cap.cap.consulter("rapport zorglubide qualité", "nouvelle revue")
    assert appels["n"] == 1                                    # a bien délégué à rank()

    # ordre attendu = celui de rank() sur les mêmes candidats (aucun tri maison)
    cands = cap.cap._candidats()
    attendu = [c["file"][:-3] for c in vrai_rank("rapport zorglubide qualité", cands,
                                                 forces=cap.nf.calculer_forces())
               if c.get("_relevance", 0.0) > 0.0][:3]
    assert rec["slugs_retournes"] == attendu
    assert cible in rec["slugs_retournes"][:3]                # cible en top-3

    # --- journalisation conforme ---
    chemin = cap.cap._chemin_consultations()
    ligne = [json.loads(l) for l in open(chemin, encoding="utf-8") if l.strip()][-1]
    assert ligne["type"] == "consultation"
    assert set(("ts", "requete", "slugs_retournes", "fiche_retenue", "tache")) <= set(ligne)
    assert ligne["requete"] == "rapport zorglubide qualité"
    assert ligne["tache"] == "nouvelle revue"
    assert ligne["fiche_retenue"] is None                     # provisoire
    assert "id" in ligne

    # --- VRAI emplacement corpus : memory_api.recall (portée par défaut) la trouve ---
    mem = _charger_memory_api()
    root = str(cap.racine_memoire)
    mem.ROOT = root
    mem.STRUCT = os.path.join(root, "structure")
    mem.EN_ATTENTE = os.path.join(root, "en_attente")
    mem.BRUT = os.path.join(root, "brut")
    mem.ARCHIVE = os.path.join(root, "archive")
    res = mem.recall({"query": ["zorglubide"], "scope": ["structure"]})
    assert cible + ".md" in [r["file"] for r in res["results"]]
    assert res["results"][0]["category"] == "criteres-kily"


@pytest.mark.xfail(
    strict=True,
    reason="consulter délègue à rank() SANS embedder (lexical pur, chemin de "
           "production). Une reformulation par SYNONYME sans token partagé "
           "('voiture'/'automobile') a une pertinence lexicale nulle : la fiche "
           "est INVISIBLE par construction. Passera au vert le jour d'un vrai "
           "embedder sémantique branché dans consulter (xpass strict → retirer).",
)
def test_t2_reformulation_synonyme_invisible_xfail(cap):
    slug = cap.cap.capitaliser("Automobile berline familiale",
                               "regarder le moteur", "transport routier", "nexus")
    # reformulation par SYNONYMES, zéro token partagé (voiture≠automobile, etc.).
    rec = cap.cap.consulter("comment jauger un vehicule", "achat")
    assert slug in rec["slugs_retournes"]     # échoue : aucun token/synonyme partagé


# =========================================================================== #
# T3 — appliquer : capteur bien formé (statut vérifié) + transfert + REFUS multi
# =========================================================================== #
def test_t3_appliquer_capteur_statut_verifie_transfert_et_refus_multi(cap):
    slug = cap.cap.capitaliser("Critères tokenunique alpha pour tri", "r", "ctx", "nexus")
    rec = cap.cap.consulter("tokenunique", "tâche T3")
    assert rec["slugs_retournes"] == [slug]                   # fiche-unique

    jid = cap.cap.generer_jeton_confirmation(rec["id"])       # LE geste humain (jeton)
    app = cap.cap.appliquer(rec["id"], slug, "succes", "tâche T3", jeton=jid)

    # --- capteur bien formé : fiche=slug, statut ∈ {succes, echec} ---
    caps = [e for e in _capteurs(cap) if e.get("fiche")]
    assert len(caps) == 1
    assert caps[0]["fiche"] == slug
    assert caps[0]["statut"] in ("succes", "echec")
    assert app["statut"] == "succes"

    # --- statut VÉRIFIÉ contre calculer_forces RÉEL : le statut émis est bien
    #     COMPTÉ (la force monte au-dessus du défaut 1.0). C'est la preuve directe
    #     que 'ok' aurait laissé la force plate. ---
    forces = cap.nf.calculer_forces()
    assert slug in forces and forces[slug] > 1.0

    # --- transfert journalisé (référence au slug réappliquée) ---
    tr = [json.loads(l) for l in open(cap.lecons.TRANSFERT, encoding="utf-8") if l.strip()]
    assert tr[-1]["lecon_cle"] == slug and tr[-1]["tache_nouvelle"] == "tâche T3"

    # --- 'ok'/'partiel' REJETÉS (ne bougent pas la force → capteur inerte interdit).
    #     Jeton VALIDE fourni : le REFUS vient bien du statut, pas du verrou jeton. ---
    rec_ok = cap.cap.consulter("tokenunique", "tâche T3 bis")
    jok = cap.cap.generer_jeton_confirmation(rec_ok["id"])
    with pytest.raises(ValueError):
        cap.cap.appliquer(rec_ok["id"], slug, "ok", "tâche T3 bis", jeton=jok)

    # --- REFUS si multi-fiches : aucun capteur de force émis. Jeton VALIDE fourni :
    #     le REFUS vient du multi-fiches, pas du verrou jeton. ---
    cap.cap.capitaliser("Critères tokenunique beta redondant", "r", "ctx", "nexus")
    multi = cap.cap.consulter("tokenunique", "tâche multi")   # matche les 2 fiches
    assert len(multi["slugs_retournes"]) >= 2
    jmulti = cap.cap.generer_jeton_confirmation(multi["id"])
    n_avant = len([e for e in _capteurs(cap) if e.get("fiche")])
    with pytest.raises(ValueError):
        cap.cap.appliquer(multi["id"], multi["slugs_retournes"][0], "succes",
                          "tâche multi", jeton=jmulti)
    assert len([e for e in _capteurs(cap) if e.get("fiche")]) == n_avant   # rien émis


# =========================================================================== #
# T4 — chaîne complète sans valeurs en dur : k applications mixtes
# =========================================================================== #
def _appliquer_n(cap, question, token, statut, n):
    """Capitalise `question` puis applique `n` fois le résultat `statut`, chaque
    application passant par une consultation fiche-unique (requête = `token`
    distinctif de cette seule fiche). Aucune force posée à la main."""
    slug = cap.cap.capitaliser(question, "r", "ctx", "nexus")
    for _ in range(n):
        rec = cap.cap.consulter(token, "boucle")
        assert rec["slugs_retournes"] == [slug], rec["slugs_retournes"]
        jid = cap.cap.generer_jeton_confirmation(rec["id"])   # un jeton par application
        cap.cap.appliquer(rec["id"], slug, statut, "boucle", jeton=jid)
    return slug


def test_t4_chaine_complete_sans_valeurs_en_dur(cap):
    valide = _appliquer_n(cap, "Critères motclealpha à réutiliser", "motclealpha", "succes", 3)
    rate = _appliquer_n(cap, "Critères motclebeta à éviter", "motclebeta", "echec", 3)

    forces = cap.nf.calculer_forces()
    assert forces, "calculer_forces ne doit plus être vide (fin du {} permanent)"
    assert valide in forces and rate in forces
    # bornes respectées, AUCUNE valeur posée à la main : tout vient de la chaîne.
    for f in forces.values():
        assert cap.nf.FORCE_MIN <= f <= cap.nf.FORCE_MAX
    assert forces[valide] > forces[rate]

    # rank() départage à pertinence ÉGALE en faveur du slug valide (force plus haute).
    cands = cap.cap._candidats()
    # requête au vocabulaire PARTAGÉ par les deux fiches → pertinence égale.
    r = cap.nf.rank("critères", cands, forces=forces, embedder=_EmbedderConstant())
    par_fichier = {it["file"][:-3]: it for it in r}
    assert par_fichier[valide]["_rel_n"] == par_fichier[rate]["_rel_n"]   # égalité
    ordre = [it["file"][:-3] for it in r]
    assert ordre.index(valide) < ordre.index(rate)                       # valide devant


# =========================================================================== #
# T5 — les DEUX successeurs du garde-fou retiré (transition)
# =========================================================================== #
def test_successeur_a_forces_distinctes_discriminent_le_classement(cap):
    """(a) RED→GREEN : de vraies forces distinctes — montées par la CHAÎNE réelle
    appliquer→calculer_forces, aucune valeur à la main — départagent enfin le
    classement à pertinence égale. RED si appliquer() émettait 'ok' (force plate,
    départage par ordre alphabétique → le témoin 'aaa' gagnerait) ; GREEN parce
    qu'appliquer() émet 'succes' (compté) → la fiche boostée passe DEVANT malgré
    son nom alphabétiquement défavorable. Prouvé RED→GREEN dans la passe
    adversariale (cf. corps de PR)."""
    temoin = cap.cap.capitaliser("Critères partage aaatemoin", "r", "ctx", "nexus")
    boostee = cap.cap.capitaliser("Critères partage zzzboostee", "r", "ctx", "nexus")
    assert temoin < boostee                        # 'aaa…' < 'zzz…' : sans force, témoin gagne

    for _ in range(3):                             # chaîne réelle : 3 succès sur la boostée
        rec = cap.cap.consulter("zzzboostee", "boucle")
        assert rec["slugs_retournes"] == [boostee]
        jid = cap.cap.generer_jeton_confirmation(rec["id"])
        cap.cap.appliquer(rec["id"], boostee, "succes", "boucle", jeton=jid)

    forces = cap.nf.calculer_forces()
    assert forces.get(boostee, 1.0) > forces.get(temoin, 1.0)   # forces DISTINCTES

    cands = cap.cap._candidats()
    r = cap.nf.rank("partage", cands, forces=forces, embedder=_EmbedderConstant())
    par = {it["file"][:-3]: it for it in r}
    assert par[boostee]["_rel_n"] == par[temoin]["_rel_n"]      # pertinence ÉGALE
    ordre = [it["file"][:-3] for it in r]
    assert ordre[0] == boostee                                 # la force a DÉPARTAGÉ


def test_successeur_b_force_bornee_non_dominante_au_vrai_plafond(cap):
    """(b) Poussée par la CHAÎNE réelle jusqu'à SATURATION : une fiche à FORCE_MAX
    (succès répétés), une autre à FORCE_MIN (échecs répétés), pertinences
    OPPOSÉES, ratio 25× au VRAI plafond — la pertinence gagne quand même. Aucune
    force posée à la main : la chaîne complète ou rien. Cible de MUTATION TESTING
    (cf. corps de PR : plafond beta muté → ce test rougit)."""
    # sat_max : peu pertinente sur la requête finale (SEULEMENT le token commun).
    sat_max = cap.cap.capitaliser("Critères maxtoken commun", "r", "ctx", "nexus")
    # sat_min : TRÈS pertinente (token rare distinctif) + le token commun.
    sat_min = cap.cap.capitaliser("Critères mintoken zorglubidedistinct commun", "r", "ctx", "nexus")
    # décoys RÉALISTES : rendent 'commun' vraiment commun (idf bas), comme le vrai
    # corpus — sinon l'idf de 'commun' serait artificiellement gonflé.
    for i in range(12):
        cap.cap.capitaliser("Critères decoy%02d commun contexte" % i, "r", "ctx", "nexus")

    # SATURATION par la chaîne : 20 succès → FORCE_MAX ; 8 échecs → FORCE_MIN.
    for _ in range(20):
        rec = cap.cap.consulter("maxtoken", "b")
        assert rec["slugs_retournes"] == [sat_max]
        jid = cap.cap.generer_jeton_confirmation(rec["id"])
        cap.cap.appliquer(rec["id"], sat_max, "succes", "b", jeton=jid)
    for _ in range(8):
        rec = cap.cap.consulter("mintoken", "b")
        assert rec["slugs_retournes"] == [sat_min]
        jid = cap.cap.generer_jeton_confirmation(rec["id"])
        cap.cap.appliquer(rec["id"], sat_min, "echec", "b", jeton=jid)

    forces = cap.nf.calculer_forces()
    assert forces[sat_max] == cap.nf.FORCE_MAX     # vrai plafond, atteint par la chaîne
    assert forces[sat_min] == cap.nf.FORCE_MIN     # vrai plancher, atteint par la chaîne
    assert forces[sat_max] / forces[sat_min] == pytest.approx(25.0)   # ratio 25×, non tronqué

    cands = cap.cap._candidats()
    r = cap.nf.rank("zorglubidedistinct commun", cands, forces=forces,
                    embedder=_EmbedderConstant())
    par = {it["file"][:-3]: it for it in r}
    # vrai écart de pertinence (> 0.5), pas un écart doux.
    assert par[sat_max]["_rel_n"] < 0.5 < par[sat_min]["_rel_n"]
    # la force MAXIMALE (ratio 25×) ne renverse PAS le vrai écart de pertinence.
    assert r[0]["file"][:-3] == sat_min
    assert par[sat_min]["_score"] > par[sat_max]["_score"]
    # l'écart de pertinence dépasse ce que la force peut AU PLUS ajouter (beta).
    assert (par[sat_min]["_pert"] - par[sat_max]["_pert"]) > \
        0.5 * (1.0 - cap.nf.POIDS_SEMANTIQUE_DEFAUT)


# =========================================================================== #
# T6 — bilan : dette / hors-dette / multi jamais dedans / verdict 98 / 98 debout
# =========================================================================== #
def test_t6_bilan_dette_et_verdict_98(cap, monkeypatch):
    # fiche-unique OUBLIÉE : consultée, jamais close.
    oubli = cap.cap.capitaliser("Critères oublialpha à ne pas appliquer", "r", "ctx", "nexus")
    r_oubli = cap.cap.consulter("oublialpha", "t-oubli")

    # fiche-unique APPLIQUÉE.
    appl = cap.cap.capitaliser("Critères applibeta bien utilisée", "r", "ctx", "nexus")
    r_appl = cap.cap.consulter("applibeta", "t-appl")
    j_appl = cap.cap.generer_jeton_confirmation(r_appl["id"])
    cap.cap.appliquer(r_appl["id"], appl, "succes", "t-appl", jeton=j_appl)

    # fiche-unique CLOSE-SANS-DETTE.
    close = cap.cap.capitaliser("Critères closegamma sans critère finalement", "r", "ctx", "nexus")
    r_close = cap.cap.consulter("closegamma", "t-close")
    cap.cap.clore_sans_dette(r_close["id"], "sans-critère")

    # MULTI-fiches oubliée (2 fiches partageant un token) : ne doit JAMAIS être en dette.
    cap.cap.capitaliser("Critères multishared un", "r", "ctx", "nexus")
    cap.cap.capitaliser("Critères multishared deux", "r", "ctx", "nexus")
    cap.cap.consulter("multishared", "t-multi")

    # « au-delà de N jours » : on interroge le bilan depuis un futur > N_JOURS_DETTE.
    futur = datetime.datetime.now() + datetime.timedelta(days=cap.cap.N_JOURS_DETTE + 1)
    b = cap.cap.bilan(now=futur)

    ids_dette = {d["id"] for d in b["dette"]}
    assert r_oubli["id"] in ids_dette                 # fiche-unique oubliée → DETTE
    assert r_appl["id"] not in ids_dette              # appliquée → HORS dette
    assert r_close["id"] not in ids_dette             # close-sans-dette → HORS dette
    assert b["n_multi_fiches"] == 1                   # la multi comptée à part…
    for d in b["dette"]:                              # …et JAMAIS dans la dette
        assert d["slug"] != "multishared"
    assert b["n_dette"] == 1

    # même bilan « à l'instant » (avant N jours) : l'oubli n'est pas encore en dette.
    b_now = cap.cap.bilan()
    assert r_oubli["id"] not in {d["id"] for d in b_now["dette"]}

    # --- verdict 98 non-SAIN au-delà du seuil ---
    import nexus_98
    nexus_98 = importlib.reload(nexus_98)
    seuil = nexus_98.BACKLOG_VIGILANCE
    verdict = nexus_98.calc_verdict([], n_dette=seuil)
    assert "SAIN" not in verdict                      # le backlog fait bouger le verdict
    assert nexus_98.signal_backlog({"n_dette": seuil}) is not None
    # au seuil d'ALERTE, ALERTE même en solo.
    assert "ALERTE" in nexus_98.calc_verdict([], n_dette=nexus_98.BACKLOG_ALERTE)

    # --- bilan CASSÉ mais 98 DEBOUT (lecture ne peut jamais faire tomber 98) ---
    def _bilan_qui_casse():
        raise RuntimeError("bilan corrompu")
    monkeypatch.setattr(cap.cap, "bilan", _bilan_qui_casse)
    assert nexus_98.backlog_capital() is None         # avalé, pas propagé
    assert nexus_98.n_dette_backlog(nexus_98.backlog_capital()) == 0
    assert "SAIN" in nexus_98.calc_verdict([], n_dette=0)   # verdict rendu quand même


# =========================================================================== #
# T7 — empreintes SHA-256 : nexus_capital ne touche QUE ses propres fichiers
# =========================================================================== #
def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_t7_empreintes_inchangees_hors_fichiers_propres(cap):
    org = os.path.join(_racine_depot(), "organes")
    skill = os.path.join(_racine_depot(), ".claude", "skills", "memoire-beta", "scripts")
    geles = {                                         # organes que le mandat INTERDIT de modifier
        os.path.join(org, "nexus_force.py"): None,
        os.path.join(org, "nexus_sense.py"): None,
        os.path.join(org, "nexus_lecons.py"): None,
        os.path.join(skill, "memory_api.py"): None,
    }
    # + une fiche corpus ÉTRANGÈRE (autre catégorie) déjà présente : capitaliser
    # ne doit jamais y toucher.
    etrangere = os.path.join(str(cap.racine_memoire), "structure", "nexus", "insights", "x.md")
    os.makedirs(os.path.dirname(etrangere), exist_ok=True)
    with open(etrangere, "w", encoding="utf-8") as f:
        f.write("# fiche étrangère — domaine: nexus / catégorie: insights\ncontenu")
    geles[etrangere] = None
    avant = {p: _sha(p) for p in geles}

    # chaîne complète : capitaliser → consulter → appliquer → clore → bilan.
    slug = cap.cap.capitaliser("Critères empreinte à mesurer", "r", "ctx", "nexus")
    rec = cap.cap.consulter("empreinte", "t7")
    jid = cap.cap.generer_jeton_confirmation(rec["id"])
    cap.cap.appliquer(rec["id"], slug, "succes", "t7", jeton=jid)
    rec2 = cap.cap.capitaliser("Critères deuxieme empreinte", "r", "ctx", "nexus")
    m = cap.cap.consulter("empreinte", "t7")          # matche 2 → multi
    cap.cap.clore_sans_dette(m["id"], "multi-fiches")
    cap.cap.bilan()

    apres = {p: _sha(p) for p in geles}
    assert avant == apres                             # aucun octet modifié hors périmètre propre


# =========================================================================== #
# T8 — la suite complète verte : validée par l'exécution pytest (cf. corps de PR).
#   Un test-sentinelle qui échoue si un import de la brique casse (fumée rapide).
# =========================================================================== #
def test_t8_smoke_imports_brique(cap):
    assert callable(cap.cap.capitaliser)
    assert callable(cap.cap.consulter)
    assert callable(cap.cap.appliquer)
    assert callable(cap.cap.clore_sans_dette)
    assert callable(cap.cap.bilan)
    import nexus_98
    assert callable(nexus_98.backlog_capital)
    assert callable(nexus_98.calc_verdict)


# =========================================================================== #
# T9 — secret de confirmation optionnel (barrière technique, capital/jeton_secret.json)
#   Sans configuration : rétrocompat TOTALE (regression). Configuré : REFUS sans
#   secret ET avec un mauvais secret, ACCEPTE avec le bon secret (fonctionne
#   ensuite normalement avec appliquer()).
# =========================================================================== #
def test_t9_sans_configuration_generer_jeton_confirmation_inchange(cap):
    slug = cap.cap.capitaliser("Critères secretalpha sans configuration", "r", "ctx", "nexus")
    rec = cap.cap.consulter("secretalpha", "tâche T9a")
    assert rec["slugs_retournes"] == [slug]

    # capital/jeton_secret.json ABSENT : secret ignoré, comportement HISTORIQUE.
    jid = cap.cap.generer_jeton_confirmation(rec["id"])
    app = cap.cap.appliquer(rec["id"], slug, "succes", "tâche T9a", jeton=jid)
    assert app["statut"] == "succes"


def test_t9_secret_configure_refuse_sans_secret_et_avec_mauvais_secret(cap):
    slug = cap.cap.capitaliser("Critères secretbeta mal confirmee", "r", "ctx", "nexus")
    rec = cap.cap.consulter("secretbeta", "tâche T9b")
    assert rec["slugs_retournes"] == [slug]

    chemin = cap.cap._chemin_secret_jeton()
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump({"hash": cap.cap._hash_secret("un-secret-de-test")}, f)

    with pytest.raises(ValueError):
        cap.cap.generer_jeton_confirmation(rec["id"])                          # sans secret
    with pytest.raises(ValueError):
        cap.cap.generer_jeton_confirmation(rec["id"], secret="mauvais-secret")  # mauvais secret


def test_t9_secret_configure_accepte_bon_secret_et_fonctionne_avec_appliquer(cap):
    slug = cap.cap.capitaliser("Critères secretgamma bien confirmee", "r", "ctx", "nexus")
    rec = cap.cap.consulter("secretgamma", "tâche T9c")
    assert rec["slugs_retournes"] == [slug]

    chemin = cap.cap._chemin_secret_jeton()
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump({"hash": cap.cap._hash_secret("un-secret-de-test")}, f)

    jid = cap.cap.generer_jeton_confirmation(rec["id"], secret="un-secret-de-test")
    app = cap.cap.appliquer(rec["id"], slug, "succes", "tâche T9c", jeton=jid)
    assert app["statut"] == "succes"
