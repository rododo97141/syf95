#!/usr/bin/env python3
"""
NEXUS — Vue Bureau 2D de l'Agent OS (brique 3, phase RI), LECTURE SEULE
« Voir de VRAIS agents se parler — pas une simulation, une lecture du réel. »

Rend VISIBLE le bureau agentos : on lit le journal du bus (agentos/bus.jsonl,
la colonne vertébrale des briques 1 & 2) et on en génère UNE page HTML 2D,
autonome et régénérable — NEXUS_bureau_agentos.html. Différence de fond avec
un bureau d'agents fictifs (type SAMS) : ici chaque carte et chaque ligne du
fil vient de messages RÉELLEMENT publiés par de vrais adaptateurs
(AdaptateurMemoire, AdaptateurLLM, …). Rien n'est simulé ; on mesure.

Ce que la page montre :
  - les AGENTS en cartes : nom, force vivante (forces.json via nexus_force),
    et leur DERNIER message émis ;
  - un FIL de conversation : les N derniers messages (qui → qui, type,
    contenu tronqué, ts), dans l'ordre du bus ;
  - un bandeau KPIs : nombre d'agents, nombre de messages, répartition par
    type.

Garanties par conception (le différenciateur assumé de la Ligue, repris ici) :
  - LECTURE SEULE du monde : on lit le bus via le patron tail-since-offset
    PROUVÉ (nexus_bus.lire_depuis → nexus_ligue.tail_depuis, O(1) sur le
    delta) et les forces via nexus_force — jamais on ne PUBLIE, jamais on
    n'écrit le bus, la mémoire ou les forces. La SEULE écriture du module est
    le fichier HTML de sortie. C'est un verrou STRUCTUREL (prouvé sur l'AST :
    aucune ouverture en écriture hors ecrire_html, aucun appel à
    nexus_bus.publier / nexus_force.ecrire_forces), pas un simple `if`.
  - Mêmes contrats env que le reste de l'organisme, relus à CHAQUE appel :
      agentos/bus.jsonl → AGENTOS_ROOT (via nexus_bus)
      forces.json       → MEMOIRE_ROOT (via nexus_force)
  - Front : UNE page HTML statique embarquée, CSS inline, ZÉRO CDN, ZÉRO
    script — donc rien à exécuter côté navigateur, rien à injecter. Tout le
    texte dynamique est ÉCHAPPÉ (anti-injection).
  - Robustesse : bus absent ou vide → une page « aucun agent » propre, sans
    erreur.

Usage :
  python3 nexus_bureau_agentos.py               # écrit NEXUS_bureau_agentos.html
  python3 nexus_bureau_agentos.py --sortie /tmp/bureau.html
  python3 nexus_bureau_agentos.py --console     # résumé console, n'écrit rien
"""
import os
import sys
import json
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import nexus_bus    # bus append-only : lire_depuis (LECTURE SEULE), BROADCAST
import nexus_force  # forces vivantes des agents (forces.json), en lecture

# Fil de conversation : combien de messages récents afficher au plus.
FLUX_MAX_DEFAUT = 40
# Longueur max d'un contenu affiché (carte ou fil) avant troncature.
CONTENU_MAX = 90


# --------------------------------------------------------------------------- #
# Lecture des sources — LECTURE SEULE, jamais de publication ni d'écriture
# --------------------------------------------------------------------------- #
def lire_bus():
    """Renvoie TOUS les messages du bus, décodés — LECTURE SEULE.

    Délègue au patron tail-since-offset PROUVÉ (nexus_bus.lire_depuis, qui
    s'appuie sur nexus_ligue.tail_depuis) : on lit à partir de l'offset 0,
    on ne PUBLIE jamais. Bus absent ou vide → liste vide (robustesse)."""
    messages, _ = nexus_bus.lire_depuis(0)
    return messages


def _forces():
    """forces.json en LECTURE SEULE (nexus_force ne l'écrit que sur --apply,
    jamais appelé ici) : {agent: multiplicateur}. Absent → {}."""
    return nexus_force._lire_forces_existantes()


# --------------------------------------------------------------------------- #
# Déductions : agents, forces, dernier message, fil, KPIs
# --------------------------------------------------------------------------- #
def _resumer_contenu(contenu, limite=CONTENU_MAX):
    """Texte affichable d'un contenu de message : les dicts (proposition,
    fiches mémoire…) sont sérialisés en JSON compact ; les sauts de ligne
    aplatis ; le tout tronqué à `limite` caractères (ellipse comprise)."""
    if isinstance(contenu, str):
        texte = contenu
    elif contenu is None:
        texte = ""
    else:
        texte = json.dumps(contenu, ensure_ascii=False)
    texte = " ".join(texte.split())
    if len(texte) > limite:
        texte = texte[: limite - 1] + "…"
    return texte


def agents(messages):
    """Liste triée des agents DISTINCTS du bus = tous les expéditeurs ∪ tous
    les destinataires NOMMÉS. Le destinataire de broadcast ("*") n'est PAS un
    agent : c'est une adresse « à tous », on l'exclut."""
    noms = set()
    for m in messages:
        exp = m.get("expediteur")
        dest = m.get("destinataire")
        if exp:
            noms.add(exp)
        if dest and dest != nexus_bus.BROADCAST:
            noms.add(dest)
    return sorted(noms)


def _force_de(forces, nom):
    """Force vivante d'un agent depuis forces.json, ou le défaut assumé si
    l'agent n'a pas (encore) d'entrée."""
    valeur = forces.get(nom)
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
        return round(float(valeur), 4)
    return nexus_force.FORCE_DEFAUT


def synthese(messages=None, flux_max=FLUX_MAX_DEFAUT):
    """Tout ce que la page affiche, dérivé du bus (LECTURE SEULE) :
      - agents : cartes {nom, force, dernier message émis (résumé/type/ts)},
        triées par force décroissante puis nom ;
      - flux   : les `flux_max` derniers messages dans l'ordre du bus, chacun
        {ts, expediteur, destinataire, type, contenu tronqué} ;
      - kpis   : {nb_agents, nb_messages, types: {type: compte}}.
    """
    if messages is None:
        messages = lire_bus()
    forces = _forces()

    dernier_emis = {}  # agent -> dernier message dont il est l'expéditeur
    for m in messages:
        exp = m.get("expediteur")
        if exp:
            dernier_emis[exp] = m

    fiches = []
    for nom in agents(messages):
        m = dernier_emis.get(nom)
        fiches.append({
            "nom": nom,
            "force": _force_de(forces, nom),
            "dernier": _resumer_contenu(m.get("contenu")) if m else None,
            "dernier_type": m.get("type") if m else None,
            "dernier_ts": m.get("ts") if m else None,
        })
    fiches.sort(key=lambda a: (-a["force"], a["nom"]))

    types = {}
    for m in messages:
        t = m.get("type") or "?"
        types[t] = types.get(t, 0) + 1

    flux = [{
        "ts": m.get("ts"),
        "expediteur": m.get("expediteur"),
        "destinataire": m.get("destinataire"),
        "type": m.get("type"),
        "contenu": _resumer_contenu(m.get("contenu")),
    } for m in messages[-flux_max:]]

    return {
        "agents": fiches,
        "flux": flux,
        "flux_max": flux_max,
        "kpis": {
            "nb_agents": len(fiches),
            "nb_messages": len(messages),
            "types": types,
        },
    }


# --------------------------------------------------------------------------- #
# Rendu HTML : une page statique, autonome, sans CDN, sans script, TOUT échappé
# --------------------------------------------------------------------------- #
def _esc(s):
    """Échappe le texte destiné au HTML (anti-injection) : &, <, >, ".
    Tout ce qui vient du bus passe OBLIGATOIREMENT par ici."""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


_STYLE = """<style>
  :root { --fond:#0f1420; --carte:#171e2e; --ligne:#232c42; --texte:#e8ecf5;
          --sourd:#8b94ab; --or:#e8b93c; --vert:#4fc07a; --bleu:#3d6fe0;
          --violet:#9a7be0; --rose:#e07ba8; }
  * { box-sizing:border-box; margin:0; }
  body { background:var(--fond); color:var(--texte);
         font:14px/1.5 system-ui, sans-serif; padding:20px; max-width:1100px;
         margin:0 auto; }
  h1 { font-size:20px; letter-spacing:.06em; }
  h1 .badge { color:var(--or); }
  .sous { color:var(--sourd); font-size:12px; margin:2px 0 14px; }
  .kpis { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:18px; }
  .kpi { background:var(--carte); border:1px solid var(--ligne);
         border-radius:10px; padding:10px 16px; min-width:96px; }
  .kpi .n { display:block; font-size:22px; font-weight:700; }
  .kpi .l { display:block; font-size:11px; text-transform:uppercase;
            letter-spacing:.1em; color:var(--sourd); }
  .kpi-types .n { font-size:13px; font-weight:600; line-height:1.4; }
  .grille { display:grid;
            grid-template-columns:minmax(300px,2fr) minmax(280px,3fr);
            gap:16px; align-items:start; }
  @media (max-width:820px){ .grille { grid-template-columns:1fr; } }
  .carte { background:var(--carte); border:1px solid var(--ligne);
           border-radius:10px; padding:14px 16px; }
  .carte h2 { font-size:13px; text-transform:uppercase; letter-spacing:.1em;
              color:var(--sourd); margin-bottom:12px; }
  .agents { display:flex; flex-direction:column; gap:10px; }
  .agent { border:1px solid var(--ligne); border-radius:8px; padding:10px 12px;
           background:rgba(61,111,224,.06); }
  .agent-tete { display:flex; justify-content:space-between; align-items:center;
                margin-bottom:4px; }
  .agent .nom { font-weight:700; font-size:15px; }
  .agent .force { color:var(--or); font-weight:700; font-size:13px;
                  border:1px solid var(--or); border-radius:20px;
                  padding:1px 9px; }
  .agent .dernier { font-size:12.5px; color:var(--texte); }
  .agent .dernier.vide, .vide { color:var(--sourd); font-style:italic; }
  .agent .ts { font-size:10.5px; color:var(--sourd); margin-top:2px; }
  ul.fil { list-style:none; max-height:560px; overflow-y:auto; }
  ul.fil li { border-bottom:1px solid var(--ligne); padding:7px 2px;
              font-size:12.5px; }
  ul.fil .ts { color:var(--sourd); }
  ul.fil .qui { font-weight:700; }
  ul.fil .fleche { color:var(--sourd); margin:0 4px; }
  .type { display:inline-block; border-radius:5px; padding:0 7px;
          font-size:11px; font-weight:600; margin:0 3px; }
  .t-demande { background:rgba(61,111,224,.18); color:#8fb0ff; }
  .t-reponse { background:rgba(79,192,122,.18); color:#7fe0a2; }
  .t-proposition { background:rgba(154,123,224,.20); color:#c3aef0; }
  .t-capteur { background:rgba(224,123,168,.18); color:#f0aecb; }
</style>"""


def _carte_agent(a):
    if a["dernier"]:
        typ = a["dernier_type"] or "?"
        det = (
            f'<p class="dernier"><span class="type t-{_esc(typ)}">'
            f'{_esc(typ)}</span> {_esc(a["dernier"])}</p>'
            f'<p class="ts">{_esc(a["dernier_ts"])}</p>'
        )
    else:
        det = '<p class="dernier vide">silencieux &mdash; aucun message &eacute;mis</p>'
    return (
        '<div class="agent">'
        '<div class="agent-tete">'
        f'<span class="nom">{_esc(a["nom"])}</span>'
        f'<span class="force">&times;{a["force"]}</span>'
        '</div>'
        + det +
        '</div>'
    )


def _ligne_flux(m):
    dest = m["destinataire"]
    dest_html = ('<span class="qui">tous</span>'
                 if dest == nexus_bus.BROADCAST
                 else f'<span class="qui">{_esc(dest)}</span>')
    typ = m["type"] or "?"
    return (
        '<li>'
        f'<span class="ts">{_esc(m["ts"])}</span> '
        f'<span class="qui">{_esc(m["expediteur"])}</span>'
        '<span class="fleche">&rarr;</span>'
        + dest_html +
        f' <span class="type t-{_esc(typ)}">{_esc(typ)}</span> '
        f'<span class="contenu">{_esc(m["contenu"])}</span>'
        '</li>'
    )


def generer_html(synth):
    """Assemble la page HTML complète (statique, autonome) depuis une
    synthese(). Aucune écriture ici : rendu pur → chaîne de caractères."""
    kpis = synth["kpis"]
    types_html = " &middot; ".join(
        f'{_esc(t)}&nbsp;: {n}' for t, n in sorted(kpis["types"].items())
    ) or "&mdash;"

    if synth["agents"]:
        cartes = '<div class="agents">' + "".join(
            _carte_agent(a) for a in synth["agents"]) + '</div>'
    else:
        cartes = ('<p class="vide">Aucun agent : le bus agentos est vide ou '
                  'absent. R&eacute;g&eacute;n&eacute;rez cette page quand de '
                  'vrais agents auront parl&eacute;.</p>')

    if synth["flux"]:
        fil = '<ul class="fil">' + "".join(
            _ligne_flux(m) for m in synth["flux"]) + '</ul>'
    else:
        fil = '<p class="vide">Aucun message sur le bus.</p>'

    return (
        '<!DOCTYPE html>\n'
        '<html lang="fr">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<title>Bureau NEXUS &mdash; Agent OS</title>\n'
        + _STYLE + '\n</head>\n<body>\n'
        '<h1><span class="badge">&#128421;</span> BUREAU NEXUS '
        '<span class="badge">Agent OS</span></h1>\n'
        '<p class="sous">Vue 2D lecture seule du bus agentos '
        '(agentos/bus.jsonl). Agents R&Eacute;ELS : chaque carte et chaque '
        'ligne vient de messages r&eacute;ellement publi&eacute;s &mdash; '
        'rien n\'est simul&eacute;.</p>\n'
        '<div class="kpis">\n'
        f'  <div class="kpi"><span class="n">{kpis["nb_agents"]}</span>'
        '<span class="l">agents</span></div>\n'
        f'  <div class="kpi"><span class="n">{kpis["nb_messages"]}</span>'
        '<span class="l">messages</span></div>\n'
        f'  <div class="kpi kpi-types"><span class="n">{types_html}</span>'
        '<span class="l">types</span></div>\n'
        '</div>\n'
        '<div class="grille">\n'
        '  <section class="carte">\n'
        '    <h2>Agents &mdash; nom, force vivante, dernier message</h2>\n'
        f'    {cartes}\n'
        '  </section>\n'
        '  <section class="carte">\n'
        f'    <h2>Fil de conversation &mdash; {synth["flux_max"]} derniers '
        'messages</h2>\n'
        f'    {fil}\n'
        '  </section>\n'
        '</div>\n'
        '</body>\n</html>\n'
    )


# --------------------------------------------------------------------------- #
# Écriture : le SEUL point d'écriture du module — le fichier HTML de sortie
# --------------------------------------------------------------------------- #
def _chemin_sortie_defaut():
    """NEXUS_bureau_agentos.html à la racine du dépôt (organes/ -> racine)."""
    return os.path.join(os.path.dirname(SCRIPT_DIR), "NEXUS_bureau_agentos.html")


def ecrire_html(chemin=None, messages=None):
    """Génère le bureau et l'écrit dans le SEUL fichier de sortie (le HTML).
    N'écrit RIEN d'autre : ni le bus, ni la mémoire, ni les forces — celles-ci
    ne sont que LUES. Renvoie le chemin écrit."""
    html = generer_html(synthese(messages))
    chemin = chemin or _chemin_sortie_defaut()
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(html)
    return chemin


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main():
    p = argparse.ArgumentParser(
        description="NEXUS — Vue Bureau 2D de l'Agent OS (lecture seule)")
    p.add_argument("--sortie", default=None,
                   help="chemin du HTML (défaut : NEXUS_bureau_agentos.html "
                        "à la racine du dépôt)")
    p.add_argument("--console", action="store_true",
                   help="afficher un résumé en console sans écrire de fichier")
    a = p.parse_args()

    synth = synthese()
    kpis = synth["kpis"]
    if a.console:
        print("🖥️  NEXUS — Bureau Agent OS (lecture seule)\n")
        if not synth["agents"]:
            print("📭 Aucun agent : le bus agentos est vide ou absent.")
            return
        print(f"   {kpis['nb_agents']} agent(s), {kpis['nb_messages']} "
              f"message(s) — types : "
              f"{', '.join(f'{t}×{n}' for t, n in sorted(kpis['types'].items()))}\n")
        for a_ in synth["agents"]:
            dernier = a_["dernier"] or "(silencieux)"
            print(f"   • {a_['nom']:<20} ×{a_['force']:<5}  {dernier}")
        return

    chemin = ecrire_html(a.sortie)
    print(f"🖥️  Bureau agentos écrit : {chemin}")
    print(f"   {kpis['nb_agents']} agent(s), {kpis['nb_messages']} message(s).")


if __name__ == "__main__":
    main()
