#!/usr/bin/env python3
"""
[Utilitaire interne — orchestré par nexus_organize. Ne pas lancer à la main.]
NEXUS Consolidate — prototype de la "boucle manquante" de la memoire vivante.
Inspire du "Dreaming" (Anthropic) et des approches PREMem / TiM : reperer les
fiches semantiquement redondantes et PROPOSER leur fusion.

Garde-fou de securite : DRY-RUN par defaut. Ne supprime, ne modifie, ne fusionne
RIEN. Il se contente de lister les candidats a consolidation pour decision humaine.
« Un doublon est toujours confirme par l'humain » : on PROPOSE, jamais on ne fusionne.

Deux signaux, PROPOSES SEPAREMENT (jamais fusionnes automatiquement) :

  • LEXICAL (toujours) — Jaccard des sacs de mots >= SEUIL. Detecte les doublons
    de SURFACE (memes mots). INCHANGE.

  • SEMANTIQUE (OPT-IN, seulement si un embedder LOCAL est injecte) — cosinus des
    TITRES embarques >= SEUIL_SEM, ET SEULEMENT pour les paires que le lexical
    RATE (Jaccard < SEUIL). Detecte les quasi-doublons « proches par le sens »
    dont les mots different (mesure du 10/07 : resumes auto-decouverte-* cos
    0,92-0,98 mais mots differents ; resume-session vs session-complete cos 0,93
    lex 0,16). Un cos eleve mele doublons, snapshots temporels et cousins : c'est
    l'HUMAIN qui tranche, jamais l'organe.

HONNETETE : sans embedder local, on le DIT (« semantique indisponible ») et on
retombe sur le lexical seul — jamais un faux score. RESEAU JAMAIS dans l'organe :
l'embedder est LOCAL et INJECTE (nexus_embedder.charger_embedder()), comme le
recall merge.

Usage : python3 nexus_consolidate.py
"""
import json, urllib.request, itertools, re, math, os, sys

BASE = "http://127.0.0.1:8077"
SEUIL = 0.50      # seuil LEXICAL relevé (cohérent avec 98) : ne signaler que les VRAIS doublons
SEUIL_SEM = 0.80  # seuil SÉMANTIQUE (cosinus des titres) : proche par le sens, mots différents

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as r:
        return json.loads(r.read().decode())

def mots(txt):
    txt = (txt or "").lower()
    return {w for w in re.findall(r"[a-zà-ÿ0-9]+", txt) if len(w) > 3}

def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)

def cosinus(a, b):
    """Cosinus PUR borné [0,1]. Aucune dépendance externe, aucun réseau.

    Vecteurs vides, de dimensions différentes, ou de norme nulle -> 0.0 (jamais
    d'exception : le sémantique est un BONUS, il ne doit jamais casser le lexical
    ni inventer un score sur des vecteurs incomparables)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    c = dot / (na * nb)
    if c < 0.0:
        return 0.0
    if c > 1.0:
        return 1.0
    return c

def libelle(score, type_):
    """Libellé HUMAIN d'une paire candidate. Une paire SÉMANTIQUE est TOUJOURS
    marquée « proche par le sens, cos=X » (jamais un simple pourcentage nu qui la
    ferait passer pour un doublon lexical) ; une paire lexicale garde le
    pourcentage historique."""
    if type_ == "semantique":
        return "proche par le sens, cos=%.2f" % score
    return "%.0f%%" % (score * 100)

def paires_candidates(fiches, embedder=None, seuil_lex=SEUIL, seuil_sem=SEUIL_SEM):
    """Fonction PURE : compare des fiches deux à deux et PROPOSE des paires
    candidates à la consolidation. Ne touche RIEN, n'écrit RIEN, n'appelle aucun
    réseau — elle ne fait que retourner des propositions pour décision humaine.

    `fiches` : liste de dicts {file, mots (set), vecteur (optionnel: list[float])}.
    Retourne une liste de tuples (score, type, fa, fb), type ∈ {lexical, semantique} :
      • score : Jaccard (lexical) ou cosinus (sémantique), arrondi 2 décimales ;
      • fa, fb : les deux dicts fiche de la paire (ordre des combinaisons).

    LEXICAL (toujours) : jaccard(mots_a, mots_b) >= seuil_lex. INCHANGÉ — c'est
      exactement l'ancien signal ; sans embedder la sortie est byte-identique.

    SÉMANTIQUE (seulement si `embedder is not None`) : cos(vecteur_a, vecteur_b)
      >= seuil_sem ET jaccard < seuil_lex. STRICTEMENT les paires que le lexical
      RATE — une paire déjà lexicale (jaccard >= seuil_lex) n'est JAMAIS
      re-proposée en sémantique (anti double comptage). Signal « proche par le
      sens » : mots différents mais titres proches.

    GARDE-FOUS testés (mutations rouges) :
      • embedder None -> AUCUNE paire sémantique (honnêteté : jamais un faux score) ;
      • une paire sous le seuil lexical mais pas sous le seuil sémantique -> ignorée ;
      • une paire lexicale n'apparaît QU'UNE fois, en lexical (pas de double comptage).
    """
    paires = []
    for fa, fb in itertools.combinations(fiches, 2):
        ma, mb = fa.get("mots") or set(), fb.get("mots") or set()
        jac = jaccard(ma, mb)
        if jac >= seuil_lex:
            # Doublon de SURFACE : signal lexical. On s'arrête là pour cette paire —
            # jamais de re-proposition sémantique (anti double comptage).
            paires.append((round(jac, 2), "lexical", fa, fb))
            continue
        if embedder is None:
            # Honnêteté : pas d'embedder local -> AUCUN signal sémantique, jamais
            # un faux score. La paire sous le seuil lexical est simplement ignorée.
            continue
        va, vb = fa.get("vecteur"), fb.get("vecteur")
        if va is None or vb is None:
            continue  # vecteur manquant -> on ne devine pas (dégrade proprement)
        cos = cosinus(va, vb)
        if cos >= seuil_sem:
            # Proche par le SENS alors que le lexical l'a raté (jaccard < seuil_lex) :
            # exactement le trou que cette passe comble, sans double comptage.
            paires.append((round(cos, 2), "semantique", fa, fb))
    return paires

def _charger_embedder():
    """Récupère l'embedder LOCAL injecté (nexus_embedder.charger_embedder()), ou
    None. Ne lève JAMAIS : toute défaillance (module absent, poids introuvables)
    -> None -> lexical seul honnête. RÉSEAU JAMAIS ici — charger_embedder applique
    lui-même l'invariant « local_files_only »."""
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
    signal que le recall mergé : titre dense, pas le texte complet dilué). Repli
    déterministe si nexus_force est indisponible."""
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
    # modèle local -> lexical seul, honnêtement annoncé (jamais un faux score).
    embedder = _charger_embedder()

    lexical = []   # (score, domaine, cat, fa_file, fb_file) — signal de SURFACE
    semant = []    # (score, domaine, cat, fa_file, fb_file) — signal « par le sens »
    total = 0
    for domaine, cats in domains.items():
        for cat in cats:
            res = get(f"/recall?domain={domaine}&category={cat}").get("results", [])
            total += len(res)
            # signature = titre + extrait, reduit en sac de mots (LEXICAL, INCHANGÉ) ;
            # + TITRE embarqué comme vecteur (SÉMANTIQUE) seulement si embedder dispo.
            fiches = []
            for f in res:
                fiche = {
                    "file": f.get("file", "?"),
                    "mots": mots(f.get("file", "") + " " + f.get("excerpt", "")),
                }
                if embedder is not None:
                    try:
                        fiche["vecteur"] = embedder.embed(_titre_fiche(f))
                    except Exception:
                        fiche["vecteur"] = None  # dégrade proprement vers lexical
                fiches.append(fiche)
            for score, type_, fa, fb in paires_candidates(fiches, embedder, SEUIL, SEUIL_SEM):
                row = (score, domaine, cat, fa["file"], fb["file"])
                (semant if type_ == "semantique" else lexical).append(row)

    print(f"📊 {total} fiches analysees sur {sum(len(c) for c in domains.values())} categories.")

    # --- Classe LEXICALE (doublons de surface) — sortie BYTE-IDENTIQUE au défaut ---
    if not lexical:
        print("✅ Aucune redondance au-dessus du seuil. Memoire saine, rien a consolider.")
    else:
        print(f"🔎 {len(lexical)} paire(s) candidate(s) a la consolidation (DRY-RUN, rien n'est touche) :\n")
        for s, d, c, fa, fb in sorted(lexical, reverse=True):
            print(f"  • [{s:.0%}] {d} › {c}")
            print(f"      ↳ {fa}")
            print(f"      ↳ {fb}")
        print("\n🛡️  Aucune fusion appliquee. A toi de valider les rapprochements pertinents.")

    # --- Classe SÉMANTIQUE (proche par le sens) — SÉPARÉE, opt-in, honnête ---
    if embedder is None:
        # Honnêteté : pas de modèle local -> on le DIT, jamais un faux score.
        print("\n🌐 Semantique indisponible (aucun embedder local injecte) — proposition lexicale seule.")
    elif not semant:
        print("\n🧠 Signal semantique actif : aucune paire proche par le sens sous le seuil lexical.")
    else:
        print(f"\n🧠 {len(semant)} paire(s) proche(s) PAR LE SENS que le lexical rate (DRY-RUN, rien n'est touche) :\n")
        for s, d, c, fa, fb in sorted(semant, reverse=True):
            print(f"  • [{libelle(s, 'semantique')}] {d} › {c}")
            print(f"      ↳ {fa}")
            print(f"      ↳ {fb}")
        print("\n🛡️  Aucune fusion appliquee. Doublon, snapshot ou cousin ? A l'humain de trancher.")

if __name__ == "__main__":
    main()
