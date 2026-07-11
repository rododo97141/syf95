#!/usr/bin/env python3
"""
[Utilitaire interne — scout LECTURE SEULE. Ne pas lancer à la main pour AGIR :
il ne fait que PROPOSER, jamais superséder.]
NEXUS Supersession Scout — le chaînon manquant entre le dédup sémantique (PR#77)
et le geste humain de supersession (POST /superseder, PR#70/#71).

POURQUOI. Le dédup sémantique a révélé une redondance non pas de DOUBLON mais
TEMPORELLE : des résumés « auto-decouverte-* » où le plus RÉCENT PÉRIME les plus
anciens (même sujet, snapshots successifs). Ce n'est pas un doublon à fusionner :
c'est une SUPERSESSION (le neuf remplace l'ancien). memory_api porte déjà le
GESTE humain `POST /superseder {path, superseded_par, date_validite}` mais AUCUNE
détection de CANDIDATS — ce trou « même sujet / auto-proposition » avait été
reporté (PR#71). Ce scout comble EXACTEMENT ce trou, et RIEN de plus.

CE QU'IL FAIT. Il PROPOSE des candidats DIRECTIONNELS DATÉS, prêts pour le geste
humain : pour chaque paire proche par le sens dont les DEUX dates sont connues et
DIFFÉRENTES, il oriente « le RÉCENT supèrsede l'ANCIEN » et affiche les paramètres
du geste, prêts à copier :
    superseder path=<ancien> superseded_par=<recent> date_validite=<date_ancien>

CE QU'IL NE FAIT JAMAIS (« la supersession est un geste HUMAIN »).
  • Il n'appelle JAMAIS superseder, n'écrit RIEN, ne fait AUCUN POST — DRY-RUN strict.
  • Paires de MÊME date -> EXCLUES : c'est du dédup (PR#77), pas de la supersession.
  • Date manquante sur l'une -> EXCLUE : direction indéterminable, on ne devine pas.
  • Sans embedder local -> AUCUN candidat, et on le DIT (« semantique indisponible ») :
    jamais un faux candidat (honnêteté, comme nexus_consolidate).

RÉSEAU JAMAIS dans l'organe hors la lecture de l'API mémoire LOCALE déjà présente
(comme nexus_consolidate) ; l'embedder est LOCAL et INJECTÉ
(nexus_embedder.charger_embedder()). Modèle : organes/nexus_consolidate.py.

Usage : python3 nexus_supersession_scout.py
"""
import json, urllib.request, itertools, re, os, sys, datetime

BASE = "http://127.0.0.1:8077"
SEUIL_SEM = 0.80  # seuil SÉMANTIQUE (cosinus des titres) : « même sujet » probable

# 1re date DD/MM/YYYY (la ligne « > Créé le DD/MM/YYYY · … », parfois « Consolidé le »).
_DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as r:
        return json.loads(r.read().decode())


def cosinus(a, b):
    """Cosinus PUR borné [0,1] (repris de nexus_consolidate : aucune dépendance,
    aucun réseau). Vecteurs vides, de dimensions différentes ou de norme nulle
    -> 0.0 (jamais d'exception : le sémantique est un signal, il ne doit jamais
    casser ni inventer un score sur des vecteurs incomparables)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0.0 or nb == 0.0:
        return 0.0
    c = dot / (na * nb)
    if c < 0.0:
        return 0.0
    if c > 1.0:
        return 1.0
    return c


def _date_fiche(text):
    """helper PUR : 1re date DD/MM/YYYY des 200 PREMIERS caractères de `text`
    (2e ligne type « > Créé le DD/MM/YYYY · Dernière mise à jour le … », parfois
    « Consolidé le DD/MM/YYYY ») -> `datetime.date` COMPARABLE.

    Aucune date, ou date invalide (30/02, 99/99…) -> None. Ne lève JAMAIS : la
    date est le signal qui DONNE la direction ; son absence retire la paire, elle
    ne casse pas le scout. On borne à 200 caractères pour viser l'en-tête (date de
    création) et ignorer d'éventuelles dates dans le corps."""
    tete = (text or "")[:200]
    m = _DATE_RE.search(tete)
    if not m:
        return None
    jour, mois, annee = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return datetime.date(annee, mois, jour)
    except ValueError:
        return None  # ex. 32/13/2026 : date impossible -> pas de direction, jamais d'exception


def candidats_supersession(fiches, embedder=None, seuil_sem=SEUIL_SEM):
    """Fonction PURE : compare des fiches deux à deux et PROPOSE des candidats
    DIRECTIONNELS DATÉS à la supersession. Ne touche RIEN, n'écrit RIEN, n'appelle
    aucun réseau — elle ne fait que retourner des propositions pour le geste humain.

    `fiches` : liste de dicts {file, date (date|None), vecteur (optionnel: list[float])}.
    Retourne une liste de tuples DIRECTIONNELS :
        (cos, recent_file, ancien_file, date_recent, date_ancien)
    où le plus RÉCENT supèrsede l'ANCIEN (date_recent > date_ancien).

    Une paire n'est proposée QUE si TOUTES ces conditions tiennent :
      • embedder is not None (sinon AUCUN candidat — honnêteté, jamais un faux) ;
      • cos(vecteur_a, vecteur_b) >= seuil_sem (« même sujet » probable) ;
      • les DEUX dates sont présentes (sinon direction indéterminable -> EXCLUE) ;
      • date_a != date_b (MÊME date -> EXCLUE : c'est du dédup, pas de la supersession).

    GARDE-FOUS testés (mutations rouges) :
      • embedder None -> AUCUN candidat (mut. « propose quand même » ROUGE) ;
      • direction TOUJOURS récent-supèrsede-ancien (mut. « ancien supèrsede récent » ROUGE) ;
      • même date -> jamais proposée (mut. « paire de même date proposée » ROUGE) ;
      • date manquante -> jamais proposée (direction indéterminable).
    """
    candidats = []
    if embedder is None:
        # Honnêteté : pas d'embedder local -> AUCUN candidat, jamais un faux. Sans
        # signal « même sujet », proposer une direction serait deviner.
        return candidats
    for fa, fb in itertools.combinations(fiches, 2):
        va, vb = fa.get("vecteur"), fb.get("vecteur")
        if va is None or vb is None:
            continue  # vecteur manquant -> on ne devine pas le « même sujet »
        if cosinus(va, vb) < seuil_sem:
            continue  # pas assez proche par le sens -> probablement pas le même sujet
        da, db = fa.get("date"), fb.get("date")
        if da is None or db is None:
            continue  # date manquante sur l'une -> direction indéterminable -> EXCLUE
        if da == db:
            continue  # MÊME date -> dédup (PR#77), pas de la supersession -> EXCLUE
        cos = round(cosinus(va, vb), 2)
        # DIRECTION : le plus RÉCENT supèrsede l'ANCIEN. On ordonne explicitement
        # par la date pour ne JAMAIS dépendre de l'ordre des combinaisons.
        if da > db:
            recent_f, recent_d, ancien_f, ancien_d = fa["file"], da, fb["file"], db
        else:
            recent_f, recent_d, ancien_f, ancien_d = fb["file"], db, fa["file"], da
        candidats.append((cos, recent_f, ancien_f, recent_d, ancien_d))
    return candidats


def _charger_embedder():
    """Récupère l'embedder LOCAL injecté (nexus_embedder.charger_embedder()), ou
    None. Ne lève JAMAIS : toute défaillance (module absent, poids introuvables)
    -> None -> « semantique indisponible » honnête. RÉSEAU JAMAIS ici —
    charger_embedder applique lui-même l'invariant « local_files_only »."""
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        from nexus_embedder import charger_embedder
        return charger_embedder()
    except Exception:
        return None


def _titre_fiche(f):
    """Titre embarqué d'une fiche recall, via nexus_force._titre_fiche (le MÊME
    signal que le recall mergé et que nexus_consolidate : titre dense, pas le texte
    complet dilué). Repli déterministe si nexus_force est indisponible."""
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        from nexus_force import _titre_fiche as titre_force
        return titre_force(f)
    except Exception:
        return (f.get("file", "") or "") + " " + (f.get("excerpt", "") or "")


def main():
    try:
        domains = get("/domains").get("domains", {})
    except Exception as e:
        print(f"🔴 API injoignable : {e}. Lance d'abord nexus_boot.sh.")
        return

    # RÉSEAU JAMAIS dans l'organe : l'embedder est LOCAL et injecté. None = pas de
    # modèle local -> AUCUN candidat, honnêtement annoncé (jamais un faux candidat).
    embedder = _charger_embedder()
    if embedder is None:
        print("🌐 Semantique indisponible (aucun embedder local injecte) — "
              "aucun candidat a la supersession (jamais un faux).")
        return

    candidats = []  # (cos, domaine, cat, recent, ancien, date_recent, date_ancien)
    total = 0
    for domaine, cats in domains.items():
        for cat in cats:
            res = get(f"/recall?domain={domaine}&category={cat}").get("results", [])
            total += len(res)
            fiches = []
            for f in res:
                fiche = {
                    # `path` (relatif à ROOT) est le paramètre attendu par le geste
                    # superseder ; fallback sur `file` si absent.
                    "file": f.get("path") or f.get("file", "?"),
                    "date": _date_fiche(f.get("excerpt", "") or f.get("_search", "")),
                }
                try:
                    fiche["vecteur"] = embedder.embed(_titre_fiche(f))
                except Exception:
                    fiche["vecteur"] = None  # dégrade proprement -> paire ignorée
                fiches.append(fiche)
            for cos, recent, ancien, d_rec, d_anc in candidats_supersession(
                    fiches, embedder, SEUIL_SEM):
                candidats.append((cos, domaine, cat, recent, ancien, d_rec, d_anc))

    print(f"📊 {total} fiches analysees sur "
          f"{sum(len(c) for c in domains.values())} categories.")

    if not candidats:
        print("✅ Aucun candidat a la supersession : aucune paire « meme sujet » "
              "datee et orientee. Rien a proposer.")
        return

    print(f"\n🕰️  {len(candidats)} candidat(s) DIRECTIONNEL(s) a la supersession "
          f"(DRY-RUN, RIEN n'est touche) — le RECENT supèrsede l'ANCIEN :\n")
    for cos, d, c, recent, ancien, d_rec, d_anc in sorted(candidats, reverse=True):
        print(f"  • [proche par le sens, cos={cos:.2f}] {d} › {c}")
        print(f"      ↳ RECENT   {recent}  ({d_rec.strftime('%d/%m/%Y')})")
        print(f"      ↳ ANCIEN   {ancien}  ({d_anc.strftime('%d/%m/%Y')})")
        # Paramètres du geste HUMAIN, prêts à copier. On n'exécute RIEN.
        print(f"      → superseder path={ancien} "
              f"superseded_par={recent} date_validite={d_anc.strftime('%d/%m/%Y')}")
    print("\n🛡️  Aucune supersession appliquee. La supersession est un GESTE HUMAIN : "
          "a toi de valider chaque proposition.")


if __name__ == "__main__":
    main()
