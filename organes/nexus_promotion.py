#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEXUS — Promotion (passe de triage déterministe de la file en_attente).

en_attente n'est PAS un cimetière : c'est une file de transit. Cette passe la
TRIE, sans jamais rien détruire ni décider seule.

Propriétés de la passe :
  - EXHAUSTIVE par construction : chaque passe itère TOUT en_attente une fois.
    Itération FINIE, sans feedback, sans budget requis (dit explicitement) — mais
    la DURÉE de passe est journalisée et le COÛT O(candidats × fiches) est NOMMÉ
    comme marqueur observable.
  - SEUL écrivain du journal d'examens (append-only : id, numéro de passe,
    époque, verdict).
  - Trois verdicts :
      · doublon-de:slug  — par CONTAINMENT PONDÉRÉ IDF (masse IDF des tokens du
        candidat présents dans la fiche / masse IDF de tous ses tokens ; IDF
        importée de memory_api.idf_sur_corpus, CORPUS = structure : constante de
        conception). Là où le Jaccard symétrique raterait un candidat court noyé
        dans une fiche longue, le containment (asymétrique) le voit ; la
        pondération IDF empêche un candidat au vocabulaire banal de passer pour
        un doublon.
      · a-promouvoir     — ni doublon ni résidu : vrai candidat à structurer.
      · perime-eligible  — RÉSIDU : N examens FENÊTRÉS (comptés depuis la
        DERNIÈRE entrée du candidat en file ; un réactivé repart à ZÉRO). JAMAIS
        un timer : on n'archive pas l'ignorance, on archive ce qui a été examiné
        N fois.
  - Génère une PROPOSITION examinable en un coup d'œil : extrait du candidat,
    extrait de la fiche cible, score, DELTA (tokens du candidat absents de la
    fiche) et empreinte SHA-256 de la fiche cible.
  - DRY-RUN par défaut. apply() n'exécute QUE les ids confirmés et REVÉRIFIE
    avant chaque exécution : candidat absent = no-op tracé, empreinte cible
    changée = proposition périmée non exécutée, rejouer le même apply = no-op
    (idempotence).

LIMITE NOMMÉE (contrat de proposition) : l'empreinte garantit que la cible n'a
pas changé, PAS que le score serait identique au recalcul (l'IDF dépend du
corpus entier). Le score est un instantané d'aide ; la décision humaine porte
sur le contenu.

Usage :
  python3 nexus_promotion.py            # passe de triage (dry-run), propositions
"""
import os
import sys
import json
import time
import hashlib
import importlib.util

# --------------------------------------------------------------------------- #
# Constantes PROVISOIRES (v0.1) — valeur prudente + mesure + déclencheur chiffré.
# --------------------------------------------------------------------------- #
# SEUIL_CONTAINMENT_IDF : part MINIMALE de la masse IDF du candidat qui doit se
#   trouver dans une fiche pour proposer un doublon. 0.60 = valeur prudente :
#   assez haut pour qu'un candidat au vocabulaire banal (dont la masse IDF est
#   dominée par des tokens absents ou communs) ne franchisse pas le seuil, assez
#   bas pour qu'un extrait spécifique réellement contenu dans une fiche le
#   franchisse. Déclencheur de révision : recaler sur la distribution réelle des
#   scores de containment des doublons HISTORIQUES du runtime (les 66 tombes) dès
#   qu'elle est mesurée — première mesure disponible.
SEUIL_CONTAINMENT_IDF = 0.60   # PROVISOIRE

# N_EXAMENS_PERIME : nombre d'examens FENÊTRÉS au-delà duquel un candidat devient
#   résidu (perime-eligible). 3 = valeur prudente : trois passes de triage
#   consécutives sans qu'aucune décision humaine ne le sorte de la file. Assez
#   pour ne pas archiver un candidat à peine analysé, assez peu pour que le
#   résidu ne s'accumule pas. Déclencheur de révision : recaler sur la cadence
#   réelle des passes une fois ≥ 20 passes journalisées.
N_EXAMENS_PERIME = 3           # PROVISOIRE


def _load_mem():
    """Charge le module memory_api (skill mémoire-beta). Utilisé par défaut ;
    les tests injectent leur propre module `mem` redirigé vers un tmp."""
    here = os.path.dirname(os.path.abspath(__file__))
    racine = os.path.dirname(here)
    chemin = os.path.join(racine, ".claude", "skills", "memoire-beta",
                          "scripts", "memory_api.py")
    spec = importlib.util.spec_from_file_location("memory_api_promotion", chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# Journal des examens — nexus_promotion en est le SEUL écrivain.
# --------------------------------------------------------------------------- #
def _journal_examens(mem):
    return os.path.join(mem.ROOT, "promotion", "examens.jsonl")


def lire_examens(mem):
    """Lecture défensive du journal d'examens (append-only). Absent → []."""
    path = _journal_examens(mem)
    out = []
    if not os.path.exists(path):
        return out
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return out
    return out


def _append_examen(mem, entry):
    path = _journal_examens(mem)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# Empreintes SHA-256
# --------------------------------------------------------------------------- #
def empreinte_texte(texte):
    return hashlib.sha256((texte or "").encode("utf-8")).hexdigest()


def empreinte_fiche(mem, relpath):
    """SHA-256 du contenu d'une fiche (chemin relatif à ROOT). Absente → None."""
    if not relpath:
        return None
    try:
        with open(os.path.join(mem.ROOT, relpath), encoding="utf-8") as f:
            return empreinte_texte(f.read())
    except OSError:
        return None


# --------------------------------------------------------------------------- #
# Corpus = structure (constante de conception). Chaque fiche : tokens + empreinte.
# --------------------------------------------------------------------------- #
def charger_structure(mem):
    """Fiches structurées : {slug, path, tokens, texte, empreinte}, triées par
    slug (déterminisme du départage de la meilleure cible)."""
    fiches = []
    base = mem.STRUCT
    if not os.path.isdir(base):
        return fiches
    for dp, _dirs, files in os.walk(base):
        for fl in sorted(files):
            if not fl.endswith(".md") or fl == "_index.md":
                continue
            path = os.path.join(dp, fl)
            try:
                with open(path, encoding="utf-8") as f:
                    texte = f.read()
            except OSError:
                continue
            fiches.append({
                "slug": fl[:-3],
                "path": os.path.relpath(path, mem.ROOT),
                "tokens": set(mem._tokens(texte)),
                "texte": texte,
                "empreinte": empreinte_texte(texte),
            })
    fiches.sort(key=lambda f: f["slug"])
    return fiches


# --------------------------------------------------------------------------- #
# Containment pondéré IDF
# --------------------------------------------------------------------------- #
def containment_idf(cand_tokens, fiche_tokens, idf):
    """Σ idf(t) pour t ∈ candidat ∩ fiche  /  Σ idf(t) pour t ∈ candidat.

    Asymétrique (par rapport au Jaccard) : mesure la part du candidat contenue
    dans la fiche, indépendamment de la taille de la fiche. Pondéré IDF : un
    token banal (présent dans beaucoup de fiches structure) pèse ~1, un token
    distinctif pèse lourd — un candidat générique ne peut donc franchir le seuil
    en s'appuyant sur du vocabulaire commun."""
    total = sum(idf.get(t, 1.0) for t in cand_tokens)
    if total <= 0:
        return 0.0
    presents = sum(idf.get(t, 1.0) for t in cand_tokens if t in fiche_tokens)
    return presents / total


def meilleure_cible(cand_tokens, fiches, idf):
    """(fiche, score) de containment maximal, ou None si aucune fiche. Départage
    stable : fiches déjà triées par slug, on garde le premier maximum."""
    best = None
    for fiche in fiches:
        s = containment_idf(cand_tokens, fiche["tokens"], idf)
        if best is None or s > best[1]:
            best = (fiche, s)
    return best


# --------------------------------------------------------------------------- #
# Fenêtre d'examens (époque courante) — un réactivé repart à zéro.
# --------------------------------------------------------------------------- #
def epoch_candidat(mem, sid):
    """Époque d'entrée en file = meta['reactivations'] (0 si jamais réactivé).
    memory_api l'incrémente à chaque réactivation : la fenêtre d'examens se
    compte dans cette époque."""
    path = os.path.join(mem.EN_ATTENTE, sid + ".md")
    try:
        meta = mem._read_meta(path)
    except (OSError, ValueError):
        return 0
    try:
        return int(meta.get("reactivations", 0))
    except (TypeError, ValueError):
        return 0


def examens_fenetres(mem, sid, epoch=None, examens=None):
    """Nombre d'examens SUBIS par le candidat dans son ÉPOQUE COURANTE (fenêtre).
    Les examens d'une époque antérieure (avant une réactivation) ne comptent PAS
    — c'est ce qui fait « repartir à zéro » un réactivé."""
    if epoch is None:
        epoch = epoch_candidat(mem, sid)
    if examens is None:
        examens = lire_examens(mem)
    n = 0
    for e in examens:
        try:
            if e.get("id") == sid and int(e.get("epoch", 0)) == epoch:
                n += 1
        except (TypeError, ValueError):
            continue
    return n


def _lister_en_attente(mem):
    """Tous les fichiers en_attente (y compris les tombes historiques : la passe
    est EXHAUSTIVE — c'est justement ce triage qui donne une sortie aux tombes).
    Renvoie [(sid, meta, tokens, contenu)]."""
    out = []
    base = mem.EN_ATTENTE
    if not os.path.isdir(base):
        return out
    for fl in sorted(os.listdir(base)):
        if not fl.endswith(".md"):
            continue
        path = os.path.join(base, fl)
        try:
            meta = mem._read_meta(path)
        except (OSError, ValueError):
            meta = {}
        try:
            with open(path, encoding="utf-8") as f:
                texte = f.read()
        except OSError:
            texte = ""
        contenu = meta.get("content") or texte
        tokens = set(mem._tokens((meta.get("title", "") + " " + contenu)))
        out.append((fl[:-3], meta, tokens, contenu))
    return out


def _proposition(sid, verdict, extrait_cand, cible, score, cand_tokens, subis):
    """Proposition examinable en un coup d'œil. Pour un doublon : extraits,
    score, DELTA (tokens du candidat absents de la fiche) et empreinte SHA-256
    de la cible + la LIMITE nommée du contrat."""
    prop = {"id": sid, "verdict": verdict, "examens_subis": subis,
            "extrait_candidat": (extrait_cand or "")[:300]}
    if verdict.startswith("doublon-de:") and cible is not None:
        delta = sorted(t for t in cand_tokens if t not in cible["tokens"])
        prop.update({
            "cible": cible["slug"],
            "cible_path": cible["path"],
            "score": round(score, 4),
            "extrait_cible": cible["texte"][:300],
            "delta": delta,
            "empreinte_cible": cible["empreinte"],
            "limite": ("l'empreinte garantit que la cible n'a pas changé, pas "
                       "que le score serait identique au recalcul (l'IDF dépend "
                       "du corpus entier) : le score est un instantané d'aide, "
                       "la décision humaine porte sur le contenu."),
        })
    return prop


# --------------------------------------------------------------------------- #
# LA PASSE
# --------------------------------------------------------------------------- #
def passe(mem=None):
    """Passe de triage déterministe et EXHAUSTIVE (dry-run : ne déplace RIEN).
    Journalise un examen pour CHAQUE candidat (id, passe, époque, verdict), sa
    durée et son coût O(candidats × fiches). Renvoie les propositions."""
    if mem is None:
        mem = _load_mem()
    t0 = time.monotonic()

    fiches = charger_structure(mem)
    fiche_token_sets = [f["tokens"] for f in fiches]
    examens = lire_examens(mem)
    numero = max([int(e.get("passe", 0)) for e in examens
                  if str(e.get("passe", "")).lstrip("-").isdigit()], default=0) + 1

    candidats = _lister_en_attente(mem)
    propositions = []
    for sid, meta, cand_tokens, contenu in candidats:
        try:
            epoch = int(meta.get("reactivations", 0))
        except (TypeError, ValueError):
            epoch = 0
        subis = examens_fenetres(mem, sid, epoch, examens) + 1   # + cet examen

        idf = mem.idf_sur_corpus(cand_tokens, fiche_token_sets)
        best = meilleure_cible(cand_tokens, fiches, idf) if fiches else None
        cible, score = (best[0], best[1]) if best else (None, 0.0)

        # Priorité de verdict : un candidat examiné N fois sans décision est un
        # RÉSIDU (perime-eligible), quel que soit son contenu — la boucle
        # automatique a fait son travail, l'humain n'a pas tranché N fois.
        if subis >= N_EXAMENS_PERIME:
            verdict = "perime-eligible"
        elif cible is not None and score >= SEUIL_CONTAINMENT_IDF:
            verdict = "doublon-de:%s" % cible["slug"]
        else:
            verdict = "a-promouvoir"

        _append_examen(mem, {"id": sid, "passe": numero, "epoch": epoch,
                             "verdict": verdict, "date": mem.now_iso()})
        propositions.append(
            _proposition(sid, verdict, contenu, cible, score, cand_tokens, subis))

    duree = time.monotonic() - t0
    return {
        "ok": True,
        "passe": numero,
        "mode": "dry-run",
        "n_candidats": len(candidats),
        "n_fiches": len(fiches),
        "cout": len(candidats) * len(fiches),
        "cout_formule": "candidats(%d) × fiches(%d)" % (len(candidats), len(fiches)),
        "duree_s": round(duree, 4),
        "propositions": propositions,
    }


# --------------------------------------------------------------------------- #
# APPLY — n'exécute QUE les propositions de doublon CONFIRMÉES, revérifiées.
# --------------------------------------------------------------------------- #
def apply(confirmes, mem=None):
    """Exécute UNIQUEMENT les ids confirmés (jamais toutes les propositions), en
    REVÉRIFIANT chacun avant d'agir :
      - candidat absent de en_attente → no-op tracé (clore trace le no-op) ;
      - empreinte de la cible changée/absente → proposition PÉRIMÉE, non exécutée ;
      - rejouer le même apply → no-op (le candidat a déjà quitté la file :
        idempotence).
    Chaque exécution passe par memory_api.clore (SEUL écrivain de en_attente/
    archive) avec raison 'doublon' et pointeur = cible."""
    if mem is None:
        mem = _load_mem()
    resultats = []
    for c in (confirmes or []):
        sid = (c.get("id") or "").strip()
        cible = c.get("cible")
        cible_path = c.get("cible_path")
        empreinte = c.get("empreinte_cible", c.get("empreinte"))
        src = os.path.join(mem.EN_ATTENTE, sid + ".md")

        if not os.path.exists(src):
            # Candidat absent (jamais présent, ou déjà clos = rejeu) : no-op tracé.
            r = mem.clore(sid, "doublon", pointeur=cible,
                          score=c.get("score"), examens=c.get("examens_subis"))
            resultats.append({"id": sid, "etat": "no-op-absent", "clore": r})
            continue

        if empreinte is not None:
            actuelle = empreinte_fiche(mem, cible_path)
            if actuelle != empreinte:
                resultats.append({"id": sid, "etat": "perimee",
                                  "raison": "empreinte cible changée ou cible absente"})
                continue

        r = mem.clore(sid, "doublon", pointeur=cible,
                      score=c.get("score"), examens=c.get("examens_subis"))
        resultats.append({"id": sid, "etat": "clos", "clore": r})
    return {"ok": True, "n_confirmes": len(confirmes or []), "resultats": resultats}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main():
    mem = _load_mem()
    rep = passe(mem)
    print("🔁 NEXUS — PROMOTION (passe de triage, dry-run)")
    print("   passe #%d · %d candidat(s) × %d fiche(s) · coût %s · %.4fs\n"
          % (rep["passe"], rep["n_candidats"], rep["n_fiches"],
             rep["cout_formule"], rep["duree_s"]))
    doublons = [p for p in rep["propositions"] if p["verdict"].startswith("doublon-de:")]
    perimes = [p for p in rep["propositions"] if p["verdict"] == "perime-eligible"]
    apromouvoir = [p for p in rep["propositions"] if p["verdict"] == "a-promouvoir"]
    print("   %d doublon(s) proposé(s) · %d périmé(s)-éligible(s) · %d à promouvoir"
          % (len(doublons), len(perimes), len(apromouvoir)))
    for p in doublons:
        print("     · %s  →  doublon-de:%s  (score %.3f)"
              % (p["id"], p["cible"], p["score"]))
    for p in perimes:
        print("     · %s  →  périmé-éligible (%d examens fenêtrés)"
              % (p["id"], p["examens_subis"]))
    print("\n   DRY-RUN : rien déplacé. apply(confirmes) exécute les ids confirmés,")
    print("   revérifiés (empreinte + présence) avant chaque clôture.")


if __name__ == "__main__":
    main()
