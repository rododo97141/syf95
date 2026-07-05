#!/usr/bin/env python3
"""
NEXUS — Pont de consolidation (capteurs → leçons)
« Ce qu'on a senti ne sert que si on en tire une leçon. »

LE chaînon manquant de la boucle vivante : le capteur (nexus_sense) enregistre ce
qui s'est passé ; le journal de leçons (nexus_lecons) garde ce qu'on en retient —
mais RIEN ne reliait les deux. Ce pont ferme la boucle sentir → retenir → réutiliser.

DEUX temps, tous les deux SANS IA (déterministe, ta doctrine : simple d'abord) :
  1) GÉNÉRER — repère les événements notables (échec/partiel/👎 → à corriger ;
     réussite validée 👍 → méthode) et dépose un BROUILLON de leçon (type + contexte
     pré-remplis ; lecon/correctif/pourquoi VIDES, à toi de les écrire).
  2) PROMOUVOIR — une fois un brouillon rempli, le fait passer en VRAIE leçon dans
     journal.jsonl (le fichier que 96 rappelle à 95). C'est le dernier maillon.

Garde-fous :
  - N'ÉCRIT JAMAIS le vrai journal tant que TU n'as pas rempli ET lancé --promouvoir.
    Les brouillons vont dans un fichier séparé (lecons/brouillons.jsonl).
  - Append-only, idempotent (aucun doublon : dédup par source, et promotion tracée
    dans lecons/brouillons_promus.jsonl). Ne supprime, ne modifie, ne fusionne rien.
    Ce fichier de trace sert aussi de TABLE DE LIAISON source → leçon :
    {cle_source, lecon_ref, promu_le} (lue par nexus_vie ; anciennes lignes
    {cle, promu_le} toujours valides = source non remplacée).
  - N'appelle PAS nexus_lecons et ne le modifie pas : écrit les 6 champs canoniques
    directement, dans le MÊME fichier (car même dossier organes/memoire_data/lecons).

Usage :
  python3 nexus_pont.py               # génère / complète les brouillons (capteurs → brouillons)
  python3 nexus_pont.py --montrer     # affiche les brouillons en attente (hors déjà promus)
  python3 nexus_pont.py --promouvoir  # brouillons REMPLIS → vraies leçons (journal.jsonl)

Voir aussi : `nexus_force.py`, le pont sœur capteurs → forces.json (mémoire-beta),
qui lit les mêmes capteurs mais isole ceux porteurs d'un champ `fiche` (recall
utilisé par la boucle orchestrateur) pour faire vivre le classement `recall`.
"""
import os, sys, json, argparse, datetime, hashlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import nexus_sense  # source UNIQUE de lecture des capteurs (respecte CAPTEURS_ROOT)


def _horodatage():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _dir_lecons():
    """Dossier des leçons/brouillons.
    Défaut : memoire_data/lecons (relatif au script) = MÊME chemin que nexus_lecons.py
    et nexus_96.py (même dossier organes/) → en prod, c'est bien le fichier que 96 lit.
    Override LECONS_ROOT (même logique que CAPTEURS_ROOT) → isole les tests."""
    base = os.environ.get("LECONS_ROOT")
    root = base if base else os.path.join(SCRIPT_DIR, "memoire_data")
    return os.path.join(root, "lecons")


def _chemin_brouillons():
    return os.path.join(_dir_lecons(), "brouillons.jsonl")


# ---------- utilitaires JSONL (append-only, tolérants) ----------
def _lire_jsonl(chemin):
    out = []
    if not os.path.exists(chemin):
        return out
    for l in open(chemin, encoding="utf-8"):
        l = l.strip()
        if l:
            try:
                out.append(json.loads(l))
            except Exception:
                pass
    return out


def _append_jsonl(chemin, obj):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


# ========================= 1) GÉNÉRER =========================
def _cle(ev):
    """Identité d'un événement capteur, pour la déduplication (anti-doublon)."""
    return f"{ev.get('ts','')}|{ev.get('tache','')}"


def _est_notable(ev):
    """v1 déterministe : quels événements méritent une leçon ?
      - échec / partiel  → quelque chose à corriger
      - feedback négatif → l'utilisateur n'était pas satisfait
      - réussite + 👍     → une méthode qui a marché, à garder
    Le reste (ok sans signal) n'encombre pas."""
    statut, fb = ev.get("statut"), ev.get("feedback")
    if statut in ("echec", "partiel"):
        return True
    if fb == "neg":
        return True
    if statut == "ok" and fb == "pos":
        return True
    return False


def _type_lecon(ev):
    """Type déduit (sans IA) : méthode si succès validé, sinon échec (à corriger)."""
    if ev.get("statut") == "ok" and ev.get("feedback") == "pos":
        return "methode"
    return "echec"


def _cles_deja_traitees():
    """Clés des événements déjà transformés en brouillon (pour ne pas dupliquer)."""
    cles = set()
    for b in _lire_jsonl(_chemin_brouillons()):
        c = (b.get("_source") or {}).get("cle", "")
        if c:
            cles.add(c)
    return cles


def construire_brouillons():
    """Lit les capteurs, crée UN brouillon par événement notable non déjà traité.
    N'écrit que dans brouillons.jsonl (jamais les vraies leçons). Renvoie des stats."""
    events = nexus_sense.lire()
    notables = [e for e in events if _est_notable(e)]
    deja = _cles_deja_traitees()

    chemin = _chemin_brouillons()
    os.makedirs(_dir_lecons(), exist_ok=True)

    nouveaux = 0
    with open(chemin, "a", encoding="utf-8") as f:
        for ev in notables:
            cle = _cle(ev)
            if cle in deja:
                continue
            brouillon = {
                "ts": _horodatage(),
                "type": _type_lecon(ev),          # pré-rempli (déduit)
                "contexte": ev.get("tache", ""),   # pré-rempli (la tâche)
                "lecon": "",                       # À COMPLÉTER par toi
                "correctif": "",                   # À COMPLÉTER par toi
                "pourquoi": "",                    # À COMPLÉTER par toi
                "_source": {
                    "cle": cle,
                    "ts": ev.get("ts"),
                    "statut": ev.get("statut"),
                    "feedback": ev.get("feedback"),
                    "tache": ev.get("tache"),
                },
                "_origine": "pont",
                "_etat": "brouillon",
            }
            f.write(json.dumps(brouillon, ensure_ascii=False) + "\n")
            deja.add(cle)
            nouveaux += 1

    return {
        "captes": len(events),
        "notables": len(notables),
        "nouveaux": nouveaux,
        "deja_traites": len(notables) - nouveaux,
        "chemin": chemin,
    }


# ======================== 2) PROMOUVOIR ========================
# Cœur conçu par Cowork, intégré ici et branché sur _dir_lecons() du pont.
def _cle_brouillon(b):
    """Identité stable d'un brouillon, pour l'idempotence de la promotion."""
    src = b.get("_source") or {}
    return src.get("cle") or b.get("ts") or json.dumps(b, ensure_ascii=False, sort_keys=True)


def _cles_promues():
    """Clés déjà promues. Deux formats de ligne coexistent dans la table :
    ancien {cle, promu_le} et nouveau {cle_source, lecon_ref, promu_le}."""
    chemin = os.path.join(_dir_lecons(), "brouillons_promus.jsonl")
    return {r.get("cle_source") or r.get("cle")
            for r in _lire_jsonl(chemin) if r.get("cle_source") or r.get("cle")}


def _lecon_ref(vraie):
    """Référence stable vers une leçon promue : ts de la leçon + hash court
    (sha1, 8 hex) du champ lecon. Permet à nexus_vie de retrouver quelle leçon
    remplace quelle source (relation N-N) sans jamais relire le journal."""
    empreinte = hashlib.sha1((vraie.get("lecon") or "").encode("utf-8")).hexdigest()[:8]
    return f"{vraie.get('ts','')}#{empreinte}"


def promouvoir_brouillons():
    """Promeut les brouillons REMPLIS (lecon non vide) et NON déjà promus en vraies
    leçons, appendées dans journal.jsonl (le fichier que relit 96). Idempotent via
    brouillons_promus.jsonl. Append-only : n'efface rien, ne touche pas nexus_lecons."""
    dir_lecons = _dir_lecons()
    chemin_brouillons = os.path.join(dir_lecons, "brouillons.jsonl")
    chemin_journal = os.path.join(dir_lecons, "journal.jsonl")
    chemin_promus = os.path.join(dir_lecons, "brouillons_promus.jsonl")

    brouillons = _lire_jsonl(chemin_brouillons)
    promus = _cles_promues()
    stats = {"remplis": 0, "promus": 0, "deja_promus": 0, "ignores_vides": 0}

    for b in brouillons:
        lecon = (b.get("lecon") or "").strip()
        if not lecon:
            stats["ignores_vides"] += 1
            continue
        stats["remplis"] += 1
        cle = _cle_brouillon(b)
        if cle in promus:
            stats["deja_promus"] += 1
            continue
        vraie = {                                   # 6 champs canoniques UNIQUEMENT
            "ts": b.get("ts") or _horodatage(),
            "type": b.get("type"),
            "contexte": b.get("contexte", ""),
            "lecon": lecon,
            "correctif": b.get("correctif", ""),
            "pourquoi": b.get("pourquoi", ""),
        }
        _append_jsonl(chemin_journal, vraie)
        # Table de liaison source → leçon (lue par nexus_vie, jamais écrite par lui).
        # Anciennes lignes {cle, promu_le} toujours valides (pas de lecon_ref = non remplacée).
        _append_jsonl(chemin_promus, {"cle_source": cle,
                                      "lecon_ref": _lecon_ref(vraie),
                                      "promu_le": _horodatage()})
        promus.add(cle)
        stats["promus"] += 1
    return stats


# ============================ CLI ============================
ICON = {"echec": "❌", "methode": "🛠️", "succes": "✅"}


def montrer():
    chemin = _chemin_brouillons()
    rows = _lire_jsonl(chemin)
    promus = _cles_promues()
    rows = [r for r in rows if _cle_brouillon(r) not in promus]   # masque les déjà promus
    if not rows:
        print("📭 Aucun brouillon en attente.")
        return
    a_completer = [r for r in rows if not r.get("lecon")]
    print(f"📝 Brouillons de leçons : {len(rows)} (dont {len(a_completer)} à compléter)\n")
    for r in rows[-20:]:
        src = r.get("_source", {})
        etat = "à compléter" if not r.get("lecon") else "complété (à promouvoir)"
        print(f"   {ICON.get(r.get('type'), '•')} [{r.get('type')}] {r.get('contexte')}  ·  {etat}")
        print(f"      déclencheur : statut={src.get('statut')} feedback={src.get('feedback')}  ({src.get('ts')})")


def run(args):
    if args.promouvoir:
        s = promouvoir_brouillons()
        print("🎓 NEXUS — Promotion : brouillons remplis → vraies leçons")
        print(f"   ➕ {s['promus']} promue(s) · {s['remplis']} rempli(s) · "
              f"{s['deja_promus']} déjà promue(s) · {s['ignores_vides']} vide(s) ignoré(s)")
        if s["promus"]:
            print("   → Elles entrent dans le journal que 96 rappelle à 95. La boucle se ferme.")
        return
    if args.montrer:
        montrer()
        return
    s = construire_brouillons()
    print("🌉 NEXUS — Pont capteurs → leçons (v1, sans IA)")
    print(f"   {s['captes']} événements captés · {s['notables']} notables")
    if s["nouveaux"]:
        print(f"   ➕ {s['nouveaux']} nouveau(x) brouillon(s) de leçon (type + contexte pré-remplis)")
    else:
        print("   ✅ Aucun nouveau brouillon (tout le notable est déjà traité)")
    if s["deja_traites"]:
        print(f"   ↪︎ {s['deja_traites']} déjà traité(s), ignoré(s) — pas de doublon")
    print(f"\n   📄 Brouillons : {s['chemin']}")
    print("   → À toi d'écrire lecon / correctif / pourquoi, puis : python3 nexus_pont.py --promouvoir")
    print("   🛡️  Rien n'a été écrit dans le vrai journal de leçons.")


def main():
    p = argparse.ArgumentParser(description="NEXUS — pont capteurs → leçons (v1, déterministe)")
    p.add_argument("--montrer", action="store_true",
                   help="afficher les brouillons en attente (hors déjà promus), sans rien écrire")
    p.add_argument("--promouvoir", action="store_true",
                   help="promouvoir les brouillons remplis en vraies leçons (journal.jsonl)")
    p.set_defaults(func=run)
    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
