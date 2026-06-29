#!/usr/bin/env python3
"""
[Utilitaire interne — orchestré par nexus_organize. Ne pas lancer à la main.]
NEXUS Reconcile — passe de réconciliation en_attente <-> structure.

Problème traité (le vrai foyer de redondance) : quand un candidat est promu
(en_attente -> structure), l'original en_attente n'est PAS transformé en
pierre tombale (bug "compteur en_attente non vide après promote" + contrainte
mount qui interdit la suppression). Résultat : la file en_attente se gonfle de
doublons de fiches déjà structurées.

Cette passe : pour chaque candidat en_attente non-tombé, vérifie s'il existe
DÉJÀ une fiche structurée équivalente (même domaine/catégorie + même titre).
Si oui -> pose une pierre tombale (ÉCRASEMENT, jamais suppression : compatible
mount Cowork). Si non -> laisse intact (vrai candidat à traiter).

Garde-fous :
  - DRY-RUN par défaut (n'écrit rien). --apply pour exécuter.
  - Ne touche QUE les en_attente déjà subsumés par une fiche structurée.
  - Jamais de suppression : on écrase le fichier par une tombe (promu:true).
  - Vérifie que le contenu structuré n'est pas vide avant de tomber l'original.

Usage : python3 nexus_reconcile.py [--apply]
"""
import os, re, json, sys, glob

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoire_data")
EN_ATTENTE = os.path.join(ROOT, "en_attente")
STRUCT = os.path.join(ROOT, "structure")

def lire_meta(path):
    """Retourne le dict meta d'un fichier en_attente, ou None si tombe/illisible."""
    try:
        with open(path, encoding="utf-8") as f:
            first = f.readline()
    except Exception:
        return None
    m = re.search(r"<!--\s*meta:\s*(\{.*\})\s*-->", first)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None

def titre_structure(path):
    """Extrait le titre (avant le ' — domaine:') d'une fiche structurée."""
    try:
        with open(path, encoding="utf-8") as f:
            line = f.readline().strip()
    except Exception:
        return ""
    line = line.lstrip("# ").strip()
    line = re.sub(r"^\((?:fusionné|réconcilié|promu)\)\s*", "", line)
    # Couper sur le marqueur d'en-tête " — domaine:" uniquement, pour ne pas
    # tronquer les titres qui contiennent eux-mêmes un tiret cadratin.
    line = re.split(r"\s—\s*domaine\s*:", line)[0]
    return line.strip().lower()

def corps_non_vide(path):
    """Vrai si la fiche structurée a un vrai corps (pas une coquille)."""
    try:
        with open(path, encoding="utf-8") as f:
            txt = f.read()
    except Exception:
        return False
    return len(txt.strip()) > 80

def main():
    apply = "--apply" in sys.argv
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"🧹 NEXUS Reconcile — mode {mode}\n")

    a_tomber, intacts, deja_tombes = [], [], 0

    for path in sorted(glob.glob(os.path.join(EN_ATTENTE, "*.md"))):
        meta = lire_meta(path)
        if meta is None or meta.get("promu"):
            deja_tombes += 1
            continue
        domain = meta.get("domain", "")
        category = meta.get("category", "")
        titre = (meta.get("title", "") or "").strip().lower()
        cat_dir = os.path.join(STRUCT, domain, category)
        match = None
        if os.path.isdir(cat_dir):
            for sf in glob.glob(os.path.join(cat_dir, "*.md")):
                if titre_structure(sf) == titre and corps_non_vide(sf):
                    match = sf
                    break
        if match:
            a_tomber.append((os.path.basename(path), meta.get("title"), domain, category, path))
        else:
            intacts.append((os.path.basename(path), meta.get("title"), domain, category))

    print(f"📊 {deja_tombes} déjà tombé(s) · {len(a_tomber)} à réconcilier · {len(intacts)} vrai(s) candidat(s) restant(s)\n")

    if a_tomber:
        print("✅ Déjà subsumés par une fiche structurée → pierre tombale :")
        for fn, t, d, c, _ in a_tomber:
            print(f"   • {d}›{c} : {t}")
    if intacts:
        print("\n⏳ Vrais candidats laissés intacts (pas encore en structure) :")
        for fn, t, d, c in intacts:
            print(f"   • {d}›{c} : {t}")

    if not apply:
        print(f"\n🛡️  DRY-RUN : rien écrit. Relancer avec --apply pour poser {len(a_tomber)} tombe(s).")
        return

    n = 0
    for fn, t, d, c, path in a_tomber:
        tombe = json.dumps({"promu": True, "title": t}, ensure_ascii=False)
        contenu = f"<!-- meta: {tombe} -->\n# (réconcilié) {t}\n> Déjà présent en structure ({d}/{c}). Doublon en_attente neutralisé le 21/06/2026.\n"
        with open(path, "w", encoding="utf-8") as f:  # ÉCRASEMENT, pas suppression
            f.write(contenu)
        n += 1
    print(f"\n🪦 {n} pierre(s) tombale(s) posée(s) par écrasement (aucune suppression).")

if __name__ == "__main__":
    main()
