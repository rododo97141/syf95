"""Tests de nexus_vie (vie des sources, chantier « remplace_par »).
Une source est REMPLACÉE si sa clé figure dans la table de liaison
(brouillons_promus.jsonl) avec au moins une lecon_ref (relation N-N).
La récence est une HORLOGE D'ACTIVITÉ (nombre de runs, pas de jours).
Le module LIT la table, ne l'écrit jamais.
Isolés : LECONS_ROOT → tmp jetable, jamais le vrai memoire_data/."""
import os, sys, json, hashlib


def _organes():
    ici = os.path.dirname(os.path.abspath(__file__))      # backend/tests
    racine = os.path.dirname(os.path.dirname(ici))         # racine du repo
    return os.path.join(racine, "organes")


def _setup(tmp_path, monkeypatch):
    org = _organes()
    if org not in sys.path:
        sys.path.insert(0, org)
    monkeypatch.setenv("LECONS_ROOT", str(tmp_path / "lec"))
    import nexus_vie
    return nexus_vie


def _chemin_liaisons(tmp_path):
    return tmp_path / "lec" / "lecons" / "brouillons_promus.jsonl"


def _ecrire_liaisons(tmp_path, lignes):
    chemin = _chemin_liaisons(tmp_path)
    os.makedirs(os.path.dirname(str(chemin)), exist_ok=True)
    with open(str(chemin), "w", encoding="utf-8") as f:
        for l in lignes:
            f.write(json.dumps(l, ensure_ascii=False) + "\n")


# ---------------------- CLÉ DE SOURCE ----------------------
def test_cle_source_accepte_evenement_et_chaine(tmp_path, monkeypatch):
    vie = _setup(tmp_path, monkeypatch)
    ev = {"ts": "2026-07-01T09:00:00", "tache": "analyse video", "statut": "echec"}
    assert vie.cle_source(ev) == "2026-07-01T09:00:00|analyse video"
    assert vie.cle_source("deja|une-cle") == "deja|une-cle"


# ---------------------- REMPLACÉE (N-N) ----------------------
def test_source_sans_liaison_n_est_pas_remplacee(tmp_path, monkeypatch):
    vie = _setup(tmp_path, monkeypatch)
    liaisons = [{"cle_source": "autre", "lecon_ref": "t#aaaaaaaa", "promu_le": "t"}]
    assert vie.est_remplacee("k1", liaisons) is False
    assert vie.lecons_remplacantes("k1", liaisons) == []


def test_source_avec_lecon_ref_est_remplacee(tmp_path, monkeypatch):
    vie = _setup(tmp_path, monkeypatch)
    liaisons = [{"cle_source": "k1", "lecon_ref": "2026-07-01T10:00:00#ab12cd34",
                 "promu_le": "2026-07-01T10:00:00"}]
    assert vie.est_remplacee("k1", liaisons) is True
    assert vie.lecons_remplacantes("k1", liaisons) == ["2026-07-01T10:00:00#ab12cd34"]


def test_retrocompat_ancienne_ligne_sans_lecon_ref_ne_remplace_pas(tmp_path, monkeypatch):
    """Ancien format {cle, promu_le} : la ligne reste valide mais, sans lecon_ref,
    la source n'est PAS considérée comme remplacée."""
    vie = _setup(tmp_path, monkeypatch)
    liaisons = [{"cle": "k1", "promu_le": "2026-06-01T08:00:00"}]
    assert vie.est_remplacee("k1", liaisons) is False
    assert vie.lecons_remplacantes("k1", liaisons) == []


def test_retrocompat_melange_ancien_et_nouveau_format(tmp_path, monkeypatch):
    """Les deux formats coexistent dans la même table : la clé ancienne (cle)
    et la nouvelle (cle_source) sont toutes deux reconnues."""
    vie = _setup(tmp_path, monkeypatch)
    liaisons = [
        {"cle": "k1", "promu_le": "t0"},                               # ancien, sans ref
        {"cle_source": "k1", "lecon_ref": "t1#11111111", "promu_le": "t1"},
        {"cle": "k2", "promu_le": "t0"},                               # ancien seul
    ]
    assert vie.est_remplacee("k1", liaisons) is True
    assert vie.est_remplacee("k2", liaisons) is False


def test_nn_une_lecon_remplace_deux_plaies(tmp_path, monkeypatch):
    vie = _setup(tmp_path, monkeypatch)
    ref = "2026-07-01T10:00:00#ab12cd34"
    liaisons = [
        {"cle_source": "plaie-1", "lecon_ref": ref, "promu_le": "t"},
        {"cle_source": "plaie-2", "lecon_ref": ref, "promu_le": "t"},
    ]
    assert vie.est_remplacee("plaie-1", liaisons) is True
    assert vie.est_remplacee("plaie-2", liaisons) is True
    assert vie.lecons_remplacantes("plaie-1", liaisons) == [ref]
    assert vie.lecons_remplacantes("plaie-2", liaisons) == [ref]


def test_nn_deux_lecons_remplacent_une_plaie(tmp_path, monkeypatch):
    vie = _setup(tmp_path, monkeypatch)
    liaisons = [
        {"cle_source": "plaie-1", "lecon_ref": "t1#11111111", "promu_le": "t1"},
        {"cle_source": "plaie-1", "lecon_ref": "t2#22222222", "promu_le": "t2"},
    ]
    assert vie.est_remplacee("plaie-1", liaisons) is True
    assert vie.lecons_remplacantes("plaie-1", liaisons) == ["t1#11111111", "t2#22222222"]


def test_lecons_remplacantes_dedoublonne_en_gardant_l_ordre(tmp_path, monkeypatch):
    vie = _setup(tmp_path, monkeypatch)
    liaisons = [
        {"cle_source": "k1", "lecon_ref": "t1#11111111", "promu_le": "t1"},
        {"cle_source": "k1", "lecon_ref": "t1#11111111", "promu_le": "t1"},   # doublon
        {"cle_source": "k1", "lecon_ref": "t2#22222222", "promu_le": "t2"},
    ]
    assert vie.lecons_remplacantes("k1", liaisons) == ["t1#11111111", "t2#22222222"]


# ---------------- HORLOGE D'ACTIVITÉ (récence en runs) ----------------
def test_est_recent_sous_le_seuil(tmp_path, monkeypatch):
    vie = _setup(tmp_path, monkeypatch)
    assert vie.SEUIL_RECENCE_RUNS == 7            # défaut INTERIMAIRE
    assert vie.est_recent(0) is True
    assert vie.est_recent(6) is True


def test_horloge_activite_7_runs_propres_non_recent(tmp_path, monkeypatch):
    vie = _setup(tmp_path, monkeypatch)
    assert vie.est_recent(7) is False
    assert vie.est_recent(12) is False


def test_est_recent_seuil_parametrable(tmp_path, monkeypatch):
    vie = _setup(tmp_path, monkeypatch)
    assert vie.est_recent(5, seuil=3) is False
    assert vie.est_recent(2, seuil=3) is True


# ---------------------- EST_VIVANT ----------------------
def test_est_vivant_source_fraiche_non_remplacee(tmp_path, monkeypatch):
    vie = _setup(tmp_path, monkeypatch)
    assert vie.est_vivant("k1", [], runs_propres=0) is True
    assert vie.est_vivant("k1", [], runs_propres=6) is True


def test_est_vivant_source_remplacee_meme_recente(tmp_path, monkeypatch):
    vie = _setup(tmp_path, monkeypatch)
    liaisons = [{"cle_source": "k1", "lecon_ref": "t#ab12cd34", "promu_le": "t"}]
    assert vie.est_vivant("k1", liaisons, runs_propres=0) is False


def test_est_vivant_eteinte_par_7_runs_propres(tmp_path, monkeypatch):
    vie = _setup(tmp_path, monkeypatch)
    assert vie.est_vivant("k1", [], runs_propres=7) is False


def test_est_vivant_seuil_parametrable(tmp_path, monkeypatch):
    vie = _setup(tmp_path, monkeypatch)
    assert vie.est_vivant("k1", [], runs_propres=7, seuil=10) is True
    assert vie.est_vivant("k1", [], runs_propres=2, seuil=2) is False


def test_est_vivant_retrocompat_ancienne_ligne_reste_vivante(tmp_path, monkeypatch):
    """Ancienne ligne {cle, promu_le} = non remplacée → la source reste vivante
    tant que l'horloge d'activité ne l'a pas éteinte."""
    vie = _setup(tmp_path, monkeypatch)
    liaisons = [{"cle": "k1", "promu_le": "t0"}]
    assert vie.est_vivant("k1", liaisons, runs_propres=0) is True
    assert vie.est_vivant("k1", liaisons, runs_propres=7) is False


# ---------------------- LECTURE SEULE ----------------------
def test_lire_liaisons_lit_la_table_sans_jamais_l_ecrire(tmp_path, monkeypatch):
    vie = _setup(tmp_path, monkeypatch)
    lignes = [
        {"cle": "ancienne", "promu_le": "t0"},
        {"cle_source": "k1", "lecon_ref": "t1#11111111", "promu_le": "t1"},
    ]
    _ecrire_liaisons(tmp_path, lignes)
    chemin = str(_chemin_liaisons(tmp_path))
    avant = hashlib.sha256(open(chemin, "rb").read()).hexdigest()

    liaisons = vie.lire_liaisons()
    assert liaisons == lignes
    vie.est_vivant("k1", liaisons, runs_propres=0)
    vie.lecons_remplacantes("ancienne", liaisons)

    apres = hashlib.sha256(open(chemin, "rb").read()).hexdigest()
    assert avant == apres                       # zéro mutation, au bit près


def test_lire_liaisons_table_absente_ne_cree_rien(tmp_path, monkeypatch):
    vie = _setup(tmp_path, monkeypatch)
    chemin = _chemin_liaisons(tmp_path)
    assert vie.lire_liaisons() == []
    assert not chemin.exists()                  # la lecture n'a rien créé


# ---------------------- BOUT EN BOUT (pont → vie) ----------------------
def test_bout_en_bout_promotion_rend_la_source_remplacee(tmp_path, monkeypatch):
    """La promotion (nexus_pont) écrit la liaison ; nexus_vie la voit :
    la source promue n'est plus vivante, une autre source fraîche l'est encore."""
    vie = _setup(tmp_path, monkeypatch)
    import nexus_pont
    rempli = {"ts": "2026-06-30T10:00:00", "type": "methode", "contexte": "ctx",
              "lecon": "Mesurer avant de conclure", "correctif": "C", "pourquoi": "P",
              "_source": {"cle": "k1"}, "_origine": "pont", "_etat": "brouillon"}
    dir_lecons = tmp_path / "lec" / "lecons"
    os.makedirs(str(dir_lecons), exist_ok=True)
    with open(str(dir_lecons / "brouillons.jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps(rempli, ensure_ascii=False) + "\n")

    assert nexus_pont.promouvoir_brouillons()["promus"] == 1
    liaisons = vie.lire_liaisons()
    assert vie.est_remplacee("k1", liaisons) is True
    assert vie.est_vivant("k1", liaisons, runs_propres=0) is False
    assert vie.est_vivant("k-autre", liaisons, runs_propres=0) is True
