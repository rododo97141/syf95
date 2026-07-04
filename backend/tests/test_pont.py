"""Tests du pont capteurs → leçons (nexus_pont) : génération + promotion.
Isolés : capteurs via CAPTEURS_ROOT, leçons/brouillons via LECONS_ROOT, tmp jetable.
Ne touchent jamais le vrai memoire_data/."""
import os, sys, json, hashlib


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


# ------------- LIAISON SOURCE → LEÇON (chantier « remplace_par ») -------------
def _rempli(cle, lecon, ts="2026-06-30T10:00:00", contexte="ctx"):
    return {"ts": ts, "type": "methode", "contexte": contexte,
            "lecon": lecon, "correctif": "C", "pourquoi": "P",
            "_source": {"cle": cle}, "_origine": "pont", "_etat": "brouillon"}


def test_promotion_ecrit_la_liaison_cle_source_lecon_ref(tmp_path, monkeypatch):
    sense, pont = _setup(tmp_path, monkeypatch)
    dir_lecons = _dir_lecons(tmp_path)
    _ecrire_brouillons(str(dir_lecons), [_rempli("k1", "Mesurer avant de conclure")])

    assert pont.promouvoir_brouillons()["promus"] == 1
    lignes = _lire(str(dir_lecons / "brouillons_promus.jsonl"))
    assert len(lignes) == 1
    l = lignes[0]
    assert set(l.keys()) == {"cle_source", "lecon_ref", "promu_le"}
    assert l["cle_source"] == "k1"
    assert l["promu_le"]


def test_lecon_ref_correct_et_stable(tmp_path, monkeypatch):
    """lecon_ref = ts de la leçon + '#' + sha1 court (8 hex) du champ lecon,
    recalculable à l'identique de l'extérieur — et STABLE : deux sources promues
    avec la même leçon partagent la même lecon_ref (N-N : 1 leçon → 2 plaies)."""
    sense, pont = _setup(tmp_path, monkeypatch)
    dir_lecons = _dir_lecons(tmp_path)
    lecon = "Mesurer avant de conclure"
    _ecrire_brouillons(str(dir_lecons), [_rempli("k1", lecon), _rempli("k2", lecon)])

    assert pont.promouvoir_brouillons()["promus"] == 2
    lignes = _lire(str(dir_lecons / "brouillons_promus.jsonl"))
    attendu = "2026-06-30T10:00:00#" + hashlib.sha1(lecon.encode("utf-8")).hexdigest()[:8]
    assert [l["lecon_ref"] for l in lignes] == [attendu, attendu]
    assert {l["cle_source"] for l in lignes} == {"k1", "k2"}


def test_lecon_ref_differencie_deux_lecons_distinctes(tmp_path, monkeypatch):
    sense, pont = _setup(tmp_path, monkeypatch)
    dir_lecons = _dir_lecons(tmp_path)
    _ecrire_brouillons(str(dir_lecons),
                       [_rempli("k1", "Leçon A"), _rempli("k2", "Leçon B")])
    pont.promouvoir_brouillons()
    refs = [l["lecon_ref"] for l in _lire(str(dir_lecons / "brouillons_promus.jsonl"))]
    assert len(set(refs)) == 2


def test_retrocompat_ancienne_ligne_bloque_la_repromotion(tmp_path, monkeypatch):
    """Une trace ancienne {cle, promu_le} (sans lecon_ref) reste valide pour
    l'idempotence : le brouillon correspondant n'est PAS repromu."""
    sense, pont = _setup(tmp_path, monkeypatch)
    dir_lecons = _dir_lecons(tmp_path)
    _ecrire_brouillons(str(dir_lecons), [_rempli("k1", "Leçon A")])
    os.makedirs(str(dir_lecons), exist_ok=True)
    with open(str(dir_lecons / "brouillons_promus.jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"cle": "k1", "promu_le": "2026-06-01T08:00:00"}) + "\n")

    s = pont.promouvoir_brouillons()
    assert s["promus"] == 0 and s["deja_promus"] == 1
    assert not (dir_lecons / "journal.jsonl").exists()   # rien réécrit
    lignes = _lire(str(dir_lecons / "brouillons_promus.jsonl"))
    assert lignes == [{"cle": "k1", "promu_le": "2026-06-01T08:00:00"}]   # intacte


def test_journal_reste_6_champs_canoniques_malgre_la_liaison(tmp_path, monkeypatch):
    """La liaison vit dans brouillons_promus.jsonl, PAS dans le journal :
    la vraie leçon garde ses 6 champs canoniques, sans lecon_ref ni cle_source."""
    sense, pont = _setup(tmp_path, monkeypatch)
    dir_lecons = _dir_lecons(tmp_path)
    _ecrire_brouillons(str(dir_lecons), [_rempli("k1", "Leçon A")])
    pont.promouvoir_brouillons()
    l = _lire(str(dir_lecons / "journal.jsonl"))[0]
    assert set(l.keys()) == {"ts", "type", "contexte", "lecon", "correctif", "pourquoi"}


def test_promotion_zero_mutation_empreintes_binaires(tmp_path, monkeypatch):
    """APPEND-ONLY strict, vérifié au bit près : les journaux existants ne sont
    jamais mutés — brouillons et capteurs identiques ; journal.jsonl et
    brouillons_promus.jsonl conservent leur contenu d'avant comme PRÉFIXE binaire."""
    sense, pont = _setup(tmp_path, monkeypatch)
    dir_lecons = _dir_lecons(tmp_path)
    sense.log_event(tache="tache ratee", statut="echec")   # un capteur, témoin
    _ecrire_brouillons(str(dir_lecons), [_rempli("k1", "Leçon A")])
    with open(str(dir_lecons / "journal.jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"ts": "t0", "type": "echec", "contexte": "vieux",
                            "lecon": "L0", "correctif": "", "pourquoi": ""}) + "\n")
    with open(str(dir_lecons / "brouillons_promus.jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"cle": "k-ancienne", "promu_le": "t0"}) + "\n")

    _, chemin_capteurs = sense._chemins()
    fixes = [str(dir_lecons / "brouillons.jsonl"), chemin_capteurs]
    accrus = [str(dir_lecons / "journal.jsonl"),
              str(dir_lecons / "brouillons_promus.jsonl")]
    avant_fixes = [open(c, "rb").read() for c in fixes]
    avant_accrus = [open(c, "rb").read() for c in accrus]

    assert pont.promouvoir_brouillons()["promus"] == 1

    for c, avant in zip(fixes, avant_fixes):               # identiques au bit près
        assert open(c, "rb").read() == avant
    for c, avant in zip(accrus, avant_accrus):             # append-only strict
        apres = open(c, "rb").read()
        assert apres.startswith(avant) and len(apres) > len(avant)


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
