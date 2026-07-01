"""Tests du pont capteurs → leçons (nexus_pont) : génération + promotion.
Isolés : capteurs via CAPTEURS_ROOT, leçons/brouillons via LECONS_ROOT, tmp jetable.
Ne touchent jamais le vrai memoire_data/."""
import os, sys, json


def _organes():
    ici = os.path.dirname(os.path.abspath(__file__))      # backend/tests
    racine = os.path.dirname(os.path.dirname(ici))         # racine du repo
    return os.path.join(racine, "organes")


def _setup(tmp_path, monkeypatch):
    org = _organes()
    if org not in sys.path:
        sys.path.insert(0, org)
    monkeypatch.setenv("CAPTEURS_ROOT", str(tmp_path))
    monkeypatch.setenv("LECONS_ROOT", str(tmp_path / "lec"))
    import nexus_sense, nexus_pont
    return nexus_sense, nexus_pont


def _dir_lecons(tmp_path):
    return tmp_path / "lec" / "lecons"


def _ecrire_brouillons(dir_lecons, brouillons):
    os.makedirs(dir_lecons, exist_ok=True)
    with open(os.path.join(dir_lecons, "brouillons.jsonl"), "w", encoding="utf-8") as f:
        for b in brouillons:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")


def _lire(chemin):
    if not os.path.exists(chemin):
        return []
    return [json.loads(l) for l in open(chemin, encoding="utf-8") if l.strip()]


# ---------------------- GÉNÉRATION ----------------------
def test_pont_cree_brouillons_pour_evenements_notables(tmp_path, monkeypatch):
    sense, pont = _setup(tmp_path, monkeypatch)
    sense.log_event(tache="tache ratee", statut="echec")
    sense.log_event(tache="tache reussie", statut="ok", feedback="pos")
    sense.log_event(tache="tache banale", statut="ok")            # PAS notable
    sense.log_event(tache="tache critiquee", statut="ok", feedback="neg")

    s = pont.construire_brouillons()
    assert s["captes"] == 4
    assert s["notables"] == 3          # la banale est exclue
    assert s["nouveaux"] == 3

    rows = _lire(str(_dir_lecons(tmp_path) / "brouillons.jsonl"))
    assert len(rows) == 3
    for r in rows:                     # type + contexte pré-remplis ; le reste VIDE
        assert r["type"] in ("echec", "methode")
        assert r["contexte"]
        assert r["lecon"] == "" and r["correctif"] == "" and r["pourquoi"] == ""
    par_contexte = {r["contexte"]: r["type"] for r in rows}
    assert par_contexte["tache reussie"] == "methode"
    assert par_contexte["tache ratee"] == "echec"
    assert par_contexte["tache critiquee"] == "echec"


def test_pont_est_idempotent(tmp_path, monkeypatch):
    sense, pont = _setup(tmp_path, monkeypatch)
    sense.log_event(tache="ratee", statut="echec")
    s1 = pont.construire_brouillons()
    s2 = pont.construire_brouillons()          # 2e passage : aucun doublon
    assert s1["nouveaux"] == 1
    assert s2["nouveaux"] == 0
    assert s2["deja_traites"] == 1
    rows = _lire(str(_dir_lecons(tmp_path) / "brouillons.jsonl"))
    assert len(rows) == 1


def test_pont_ne_touche_pas_les_vraies_lecons(tmp_path, monkeypatch):
    sense, pont = _setup(tmp_path, monkeypatch)
    sense.log_event(tache="ratee", statut="echec")
    pont.construire_brouillons()
    vrai_journal = _dir_lecons(tmp_path) / "journal.jsonl"
    assert not vrai_journal.exists()            # la génération n'écrit jamais le vrai journal


def test_pont_sans_capteurs_ne_plante_pas(tmp_path, monkeypatch):
    sense, pont = _setup(tmp_path, monkeypatch)
    s = pont.construire_brouillons()
    assert s["captes"] == 0 and s["nouveaux"] == 0


# ---------------------- PROMOTION ----------------------
def test_promouvoir_ecrit_les_remplis_et_ignore_les_vides(tmp_path, monkeypatch):
    sense, pont = _setup(tmp_path, monkeypatch)
    dir_lecons = _dir_lecons(tmp_path)
    rempli = {"ts": "2026-06-30T10:00:00", "type": "methode", "contexte": "ctx-A",
              "lecon": "Mesurer avant de conclure", "correctif": "ajouter un capteur",
              "pourquoi": "sans mesure pas de preuve",
              "_source": {"cle": "k1"}, "_origine": "pont", "_etat": "brouillon"}
    vide = {"ts": "2026-06-30T10:05:00", "type": "echec", "contexte": "ctx-B",
            "lecon": "", "correctif": "", "pourquoi": "",
            "_source": {"cle": "k2"}, "_origine": "pont", "_etat": "brouillon"}
    _ecrire_brouillons(str(dir_lecons), [rempli, vide])

    stats = pont.promouvoir_brouillons()
    assert stats["promus"] == 1
    assert stats["ignores_vides"] == 1

    lecons = _lire(str(dir_lecons / "journal.jsonl"))
    assert len(lecons) == 1
    l = lecons[0]
    assert (l["type"], l["contexte"], l["lecon"], l["correctif"], l["pourquoi"]) == \
           ("methode", "ctx-A", "Mesurer avant de conclure", "ajouter un capteur",
            "sans mesure pas de preuve")
    # 6 champs canoniques UNIQUEMENT — aucun champ interne du brouillon
    assert set(l.keys()) == {"ts", "type", "contexte", "lecon", "correctif", "pourquoi"}


def test_promouvoir_est_idempotent(tmp_path, monkeypatch):
    sense, pont = _setup(tmp_path, monkeypatch)
    dir_lecons = _dir_lecons(tmp_path)
    rempli = {"ts": "2026-06-30T10:00:00", "type": "methode", "contexte": "ctx",
              "lecon": "L", "correctif": "C", "pourquoi": "P",
              "_source": {"cle": "k1"}, "_origine": "pont", "_etat": "brouillon"}
    _ecrire_brouillons(str(dir_lecons), [rempli])

    s1 = pont.promouvoir_brouillons()
    s2 = pont.promouvoir_brouillons()          # 2e passage : rien de nouveau
    assert s1["promus"] == 1
    assert s2["promus"] == 0 and s2["deja_promus"] == 1
    assert len(_lire(str(dir_lecons / "journal.jsonl"))) == 1   # pas de doublon


def test_pont_puis_promouvoir_bout_en_bout(tmp_path, monkeypatch):
    """Chaîne complète : capteur échec → brouillon → on le remplit → promotion → vraie leçon."""
    sense, pont = _setup(tmp_path, monkeypatch)
    sense.log_event(tache="tache ratee", statut="echec")
    pont.construire_brouillons()

    chemin_b = _dir_lecons(tmp_path) / "brouillons.jsonl"
    rows = _lire(str(chemin_b))
    assert len(rows) == 1 and rows[0]["lecon"] == ""

    rows[0]["lecon"] = "verifier l'etat avant de lancer"      # Kily remplit
    rows[0]["correctif"] = "reset etat_boucle"
    rows[0]["pourquoi"] = "un etat epuise fausse le run"
    with open(chemin_b, "w", encoding="utf-8") as f:
        f.write(json.dumps(rows[0], ensure_ascii=False) + "\n")

    s = pont.promouvoir_brouillons()
    assert s["promus"] == 1
    lecons = _lire(str(_dir_lecons(tmp_path) / "journal.jsonl"))
    assert len(lecons) == 1 and lecons[0]["lecon"] == "verifier l'etat avant de lancer"
