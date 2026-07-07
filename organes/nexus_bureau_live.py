#!/usr/bin/env python3
"""
NEXUS — Bureau 2D LIVE de l'Agent OS (brique 4, phase A « 2D temps réel »)
« Voir de VRAIS agents se parler EN DIRECT — sans jamais toucher au monde. »

Ce module est le mariage de deux briques DÉJÀ PROUVÉES et MERGÉES :
  - le SERVEUR LECTURE SEULE de la Ligue (nexus_ligue : http.server stdlib,
    transport PULL tail-since-offset O(1)) — on en reprend le patron exact ;
  - le RENDU du bureau agentos (nexus_bureau_agentos : cartes agents, fil de
    conversation, KPIs, tout ÉCHAPPÉ) — on en reprend synthese() et les
    fabriques de HTML (_STYLE, _carte_agent, _ligne_flux, _esc).

Ce qu'apporte cette brique par rapport au bureau statique : le TEMPS RÉEL. La
page embarque un petit script qui POLL /events toutes les ~1 s et met à jour
EN DIRECT les cartes agents (dernier message émis, force vivante) et le fil,
sans jamais recharger la page. Le transport est le tail-since-offset prouvé :
chaque poll ne relit QUE le delta du bus depuis l'offset précédent (O(1) vis-
à-vis de la taille totale — mesuré par test à 1 et 5000 messages).

Ce que la page montre (identique au bureau statique, mais vivant) :
  - les AGENTS en cartes : nom, force vivante (forces.json via nexus_force),
    et leur DERNIER message émis, rafraîchis à chaque poll ;
  - un FIL de conversation live : les derniers messages du bus, les plus
    récents en tête, complété au fil de l'eau ;
  - un bandeau KPIs : nombre d'agents, nombre de messages, répartition par type.

Endpoints (stdlib http.server, un seul thread par requête) :
  - GET /                        → la page Bureau LIVE (rendu initial du bureau
                                   agentos + script de poll + offset embarqué) ;
  - GET /events?since=OFFSET     → JSON {messages, offset, forces, flux_max} :
                                   les messages du bus publiés APRÈS l'offset
                                   (tail O(1) via nexus_bus.lire_depuis) et le
                                   nouvel offset ; since=0 renvoie tout.

Garanties par conception (le différenciateur assumé de la Ligue, tenu ici) :
  - LECTURE SEULE STRICTE : ce module ne fait AUCUNE écriture — ni le bus, ni
    la mémoire, ni les forces, ni aucun fichier. Il LIT et SERT, point. C'est
    un verrou STRUCTUREL (prouvé sur l'AST : ZÉRO ouverture en écriture, aucun
    appel à publier / ecrire_forces / ecrire_html / log_event), doublé d'une
    preuve d'exécution (empreintes binaires du bus et de la mémoire INCHANGÉES
    après une série de requêtes). La boucle ignore l'existence du dashboard.
  - Mêmes contrats env que le reste de l'organisme, relus à CHAQUE appel :
      agentos/bus.jsonl → AGENTOS_ROOT (via nexus_bus)
      forces.json       → MEMOIRE_ROOT (via nexus_force, LU seulement)
  - Front : UNE page HTML embarquée, CSS inline, ZÉRO CDN, ZÉRO dépendance.
    Le seul script est le poll ; tout texte dynamique est ÉCHAPPÉ (anti-
    injection) côté serveur ET côté client.
  - Robustesse : bus vide ou absent → page « aucun agent » propre, sans erreur.

Usage :
  python3 nexus_bureau_live.py                 # sert http://127.0.0.1:8079
  python3 nexus_bureau_live.py --port 9000
"""
import os
import sys
import json
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import nexus_bus              # bus append-only : lire_depuis (LECTURE SEULE)
import nexus_force           # forces vivantes (forces.json), en LECTURE seule
import nexus_bureau_agentos as bureau  # rendu prouvé : synthese + fabriques HTML

PORT_DEFAUT = 8079
# Poll côté client, en millisecondes. ~1 s : assez vif pour un « live » lisible,
# assez calme pour rester trivial (chaque poll ne lit que le delta du bus).
POLL_MS = 1000


# --------------------------------------------------------------------------- #
# Transport PULL : le delta du bus depuis un offset (tail O(1) prouvé)
# --------------------------------------------------------------------------- #
def evenements_depuis(offset):
    """Renvoie (messages, nouvel_offset) — les messages du bus publiés APRÈS
    l'offset, décodés. LECTURE SEULE : délègue au patron tail-since-offset
    PROUVÉ (nexus_bus.lire_depuis → nexus_ligue.tail_depuis), qui seek() à
    l'offset et ne lit QUE les octets nouveaux (O(1) vis-à-vis de la taille
    totale). Bus absent/vide → ([], 0). since=0 → tout le bus."""
    try:
        offset = max(0, int(offset))
    except (TypeError, ValueError):
        offset = 0
    return nexus_bus.lire_depuis(offset)


def _forces():
    """forces.json en LECTURE SEULE (map agent → multiplicateur), pour que les
    cartes affichent la force vivante à jour à chaque poll. Absent → {}."""
    return nexus_force._lire_forces_existantes()


# --------------------------------------------------------------------------- #
# Serveur HTTP (stdlib uniquement — patron nexus_ligue)
# --------------------------------------------------------------------------- #
class BureauLiveHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silencieux : le dashboard ne pollue pas la console
        pass

    def _json(self, obj, code=200):
        corps = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            corps = page_live().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(corps)))
            self.end_headers()
            self.wfile.write(corps)
        elif url.path == "/events":
            q = parse_qs(url.query)
            try:
                since = int(q.get("since", ["0"])[0])
            except ValueError:
                since = 0
            messages, offset = evenements_depuis(since)
            self._json({
                "messages": messages,
                "offset": offset,
                "forces": _forces(),
                "flux_max": bureau.FLUX_MAX_DEFAUT,
            })
        else:
            self._json({"erreur": "introuvable"}, code=404)


def creer_serveur(port=PORT_DEFAUT, hote="127.0.0.1"):
    """Instancie le serveur sans le lancer (port=0 → port libre, pour tests)."""
    return ThreadingHTTPServer((hote, port), BureauLiveHandler)


# --------------------------------------------------------------------------- #
# Front : rendu initial (bureau agentos prouvé) + script de poll + offset
# --------------------------------------------------------------------------- #
def _corps_initial(synth):
    """Rend le corps du bureau (KPIs + cartes agents + fil) depuis une
    synthese(), en RÉUTILISANT les fabriques prouvées et échappées de
    nexus_bureau_agentos. Sert de rendu initial (avant le premier poll) et de
    repli sans JavaScript. Chaque nœud dynamique porte un id pour que le script
    le mette à jour EN PLACE."""
    kpis = synth["kpis"]
    types_html = " &middot; ".join(
        f'{bureau._esc(t)}&nbsp;: {n}' for t, n in sorted(kpis["types"].items())
    ) or "&mdash;"

    if synth["agents"]:
        # Repli sans JavaScript : les cartes prouvées (échappées) de
        # nexus_bureau_agentos ; le script les remplace par la scène isométrique.
        cartes = '<div class="agents">' + "".join(
            bureau._carte_agent(a) for a in synth["agents"]) + '</div>'
    else:
        cartes = ('<p class="vide">Aucun agent : le bus agentos est vide ou '
                  'absent. La sc&egrave;ne appara&icirc;tra d&egrave;s que de '
                  'vrais agents auront parl&eacute;.</p>')

    if synth["flux"]:
        # Live : les plus récents en tête (le bureau statique les met dans
        # l'ordre du bus ; ici on inverse pour un fil qui « pousse » par le haut).
        fil = "".join(bureau._ligne_flux(m) for m in reversed(synth["flux"]))
    else:
        fil = '<li class="vide">Aucun message sur le bus.</li>'

    return (kpis, types_html, cartes, fil)


def page_live():
    """Assemble la page Bureau LIVE : rendu initial (RÉUTILISE synthese() +
    les fabriques de nexus_bureau_agentos, tout échappé) + script de poll
    /events + offset de départ embarqué. Recalculée à CHAQUE GET / (relit le
    bus), donc jamais figée. Aucune écriture : rendu pur → chaîne."""
    messages, offset = nexus_bus.lire_depuis(0)
    synth = bureau.synthese(messages)
    kpis, types_html, cartes, fil = _corps_initial(synth)

    # Le script démarre son poll À L'OFFSET COURANT : il n'ajoute que les
    # messages VRAIMENT nouveaux, sans redoubler le rendu initial ci-dessus.
    config = json.dumps({
        "offset": offset,
        "poll_ms": POLL_MS,
        "flux_max": bureau.FLUX_MAX_DEFAUT,
        "contenu_max": bureau.CONTENU_MAX,
        "force_defaut": nexus_force.FORCE_DEFAUT,
        "broadcast": nexus_bus.BROADCAST,
    }, ensure_ascii=False)

    return (
        '<!DOCTYPE html>\n'
        '<html lang="fr">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<title>Bureau NEXUS LIVE &mdash; Agent OS</title>\n'
        + bureau._STYLE + _STYLE_LIVE + '\n</head>\n<body>\n'
        '<h1><span class="badge">&#128421;</span> BUREAU NEXUS '
        '<span class="badge">LIVE</span></h1>\n'
        '<p class="sous">Vue <b>isom&eacute;trique temps r&eacute;el</b> du bus '
        'agentos (agentos/bus.jsonl), en lecture seule. La sc&egrave;ne, le fil '
        'et les KPIs se mettent &agrave; jour tout seuls &mdash; agents '
        'R&Eacute;ELS, rien n\'est simul&eacute;. <span id="live-etat" '
        'class="etat-live">connexion&hellip;</span></p>\n'
        '<div class="kpis">\n'
        f'  <div class="kpi"><span class="n" id="kpi-agents">{kpis["nb_agents"]}'
        '</span><span class="l">agents</span></div>\n'
        f'  <div class="kpi"><span class="n" id="kpi-messages">'
        f'{kpis["nb_messages"]}</span><span class="l">messages</span></div>\n'
        '  <div class="kpi kpi-types"><span class="n" id="kpi-types">'
        f'{types_html}</span><span class="l">types</span></div>\n'
        '</div>\n'
        '<div class="grille">\n'
        '  <section class="carte">\n'
        '    <h2>Bureau isom&eacute;trique &mdash; agents sur la grille '
        '(rang par force)</h2>\n'
        # #scene reçoit d'abord le rendu de repli (cartes prouvées, échappées,
        # lisibles sans JavaScript) ; le script remplace ce contenu par la
        # scène isométrique SVG dès le premier poll.
        f'    <div class="scene-wrap"><div class="scene" id="scene">{cartes}'
        '</div></div>\n'
        '  </section>\n'
        '  <section class="carte">\n'
        f'    <h2>Fil de conversation &mdash; live, {bureau.FLUX_MAX_DEFAUT} '
        'derniers messages</h2>\n'
        f'    <ul class="fil" id="fil">{fil}</ul>\n'
        '  </section>\n'
        '</div>\n'
        f'<script>\n"use strict";\nvar CFG = {config};\n' + _SCRIPT_LIVE +
        '\n</script>\n'
        '</body>\n</html>\n'
    )


# Complément de style : indicateur « live » + SCÈNE ISOMÉTRIQUE (le socle
# commun — KPIs, cartes de repli, fil — vient toujours de bureau._STYLE, non
# modifié). Ces règles s'ajoutent APRÈS bureau._STYLE, donc elles peuvent
# aussi surcharger la grille pour donner à la scène la colonne la plus large.
_STYLE_LIVE = """
<style>
  .etat-live { color:var(--sourd); font-size:11px; margin-left:6px; }
  .etat-live.ok { color:var(--vert); }
  .etat-live.ko { color:var(--rose); }
  ul.fil li.neuf { animation:apparait .8s ease; }
  @keyframes apparait { from { background:rgba(79,192,122,.18); } to { background:transparent; } }

  /* La scène prend la colonne large ; le fil + KPIs restent à côté. */
  .grille { grid-template-columns:minmax(320px,3fr) minmax(260px,2fr); }
  @media (max-width:820px){ .grille { grid-template-columns:1fr; } }

  /* Scène isométrique : une grille en losanges, agents en jetons élevés.
     TOUT est décoratif — la position d'un agent est une convention de
     visualisation (rang par force), pas une coordonnée venue du serveur. */
  .scene-wrap { background:radial-gradient(circle at 50% 36%,
                rgba(61,111,224,.12), transparent 70%);
                border-radius:8px; overflow:auto; padding:6px; }
  svg.iso { display:block; width:100%; height:auto; max-height:560px; }
  svg.iso .tuile { fill:rgba(61,111,224,.05); stroke:var(--ligne); stroke-width:1; }
  svg.iso .tuile-b { fill:rgba(61,111,224,.11); }
  svg.iso .ombre { fill:rgba(0,0,0,.30); }
  svg.iso .mat { stroke:var(--ligne); stroke-width:1.5; }
  svg.iso .jeton { stroke:#0f1420; stroke-width:2; }
  svg.iso .jeton.actif { stroke:var(--or); stroke-width:2.5;
                         animation:pulse-iso 1.3s ease-in-out infinite; }
  @keyframes pulse-iso { 0%,100% { opacity:1; } 50% { opacity:.55; } }
  svg.iso .rang { fill:#0f1420; font:700 11px system-ui, sans-serif; text-anchor:middle; }
  svg.iso .nom-iso { fill:var(--texte); font:600 12px system-ui, sans-serif; text-anchor:middle; }
  svg.iso .force-iso { fill:var(--or); font:700 10px system-ui, sans-serif; text-anchor:middle; }
  svg.iso g.agent-iso { cursor:default; }
  .scene .vide { color:var(--sourd); font-style:italic; }
</style>"""


# Script de poll : reconstruit la SCÈNE ISOMÉTRIQUE + fil + KPIs depuis les
# messages ACCUMULÉS (poll incrémental via tail-since-offset). Tout texte est
# ÉCHAPPÉ avant le DOM. La scène est bâtie en SVG vanilla (aucune dépendance) ;
# les positions des agents sont calculées ICI, côté client, comme une simple
# convention de visualisation (rang par force sur une grille en losanges) —
# aucune coordonnée réelle ni sémantique de position ne vient du serveur.
_SCRIPT_LIVE = r"""
var MSG = [];            /* tous les messages vus (rendu initial + deltas) */
var offset = CFG.offset; /* on démarre APRÈS le rendu initial de la page */
var premier = true;      /* au 1er poll on repart de 0 pour posséder l'état */
var forces = {};

function esc(s) {
  return String(s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
  });
}

function resumer(contenu) {
  var texte;
  if (typeof contenu === "string") texte = contenu;
  else if (contenu == null) texte = "";
  else texte = JSON.stringify(contenu);
  texte = texte.split(/\s+/).join(" ").trim();
  if (texte.length > CFG.contenu_max) texte = texte.slice(0, CFG.contenu_max - 1) + "…";
  return texte;
}

function forceDe(nom) {
  var v = forces[nom];
  if (typeof v === "number" && isFinite(v)) return Math.round(v * 10000) / 10000;
  return CFG.force_defaut;
}

/* Agents = expéditeurs ∪ destinataires nommés (le broadcast n'est pas un agent). */
function agentsDe() {
  var noms = {};
  MSG.forEach(function (m) {
    if (m.expediteur) noms[m.expediteur] = true;
    if (m.destinataire && m.destinataire !== CFG.broadcast) noms[m.destinataire] = true;
  });
  return Object.keys(noms);
}

/* Dernier message EMIS par un agent (couleur du jeton + infobulle). */
function dernierEmis(nom) {
  for (var i = MSG.length - 1; i >= 0; i--) {
    if (MSG[i].expediteur === nom) return MSG[i];
  }
  return null;
}

/* --- Rendu isometrique (SVG vanilla) ------------------------------------- */
/* Projection losange d'une cellule (col,row) vers un point ecran. La cellule
   est PUREMENT decorative : on range les agents (deja tries par force) ligne
   par ligne. Rien de ceci n'est une position reelle -- le serveur ne fournit
   ni x, ni y, ni rang ; on les DEDUIT ici de ce que /events renvoie deja. */
var ISO_TW = 190, ISO_TH = 96, ISO_LIFT = 46;

function isoCentre(col, row) {
  return { x: (col - row) * (ISO_TW / 2), y: (col + row) * (ISO_TH / 2) };
}

function couleurType(t) {
  return ({ demande: "#3d6fe0", reponse: "#4fc07a",
            proposition: "#9a7be0", capteur: "#e07ba8" })[t] || "#8b94ab";
}

function losange(cx, cy, w, h, cls) {
  var pts = [[cx, cy - h / 2], [cx + w / 2, cy], [cx, cy + h / 2], [cx - w / 2, cy]]
    .map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" ");
  return '<polygon points="' + pts + '" class="' + cls + '"/>';
}

function rendreScene(noms) {
  var zone = document.getElementById("scene");
  if (!noms.length) {
    zone.innerHTML = '<p class="vide">Aucun agent : le bus agentos est vide ou absent.</p>';
    return;
  }

  /* Grille aussi carree que possible, remplie ligne par ligne (decoratif). */
  var cols = Math.max(1, Math.ceil(Math.sqrt(noms.length)));
  var cellules = noms.map(function (nom, i) {
    var c = isoCentre(i % cols, Math.floor(i / cols));
    return { nom: nom, cx: c.x, cy: c.y, rang: i + 1 };
  });

  /* viewBox englobant : losanges du sol + elevation des jetons + etiquettes. */
  var minX = 1e9, maxX = -1e9, minY = 1e9, maxY = -1e9;
  cellules.forEach(function (k) {
    if (k.cx - ISO_TW / 2 < minX) minX = k.cx - ISO_TW / 2;
    if (k.cx + ISO_TW / 2 > maxX) maxX = k.cx + ISO_TW / 2;
    if (k.cy - ISO_TH / 2 - ISO_LIFT - 30 < minY) minY = k.cy - ISO_TH / 2 - ISO_LIFT - 30;
    if (k.cy + ISO_TH / 2 + 14 > maxY) maxY = k.cy + ISO_TH / 2 + 14;
  });
  var pad = 26, vbW = (maxX - minX) + 2 * pad, vbH = (maxY - minY) + 2 * pad;

  var dernierGlobal = MSG.length ? MSG[MSG.length - 1].expediteur : null;

  /* SVG inline SANS xmlns : injecte via innerHTML, le parseur HTML place les
     noeuds dans l'espace de noms SVG tout seul (aucune URL, zero dependance). */
  var svg = '<svg class="iso" viewBox="' + (minX - pad).toFixed(1) + " " +
    (minY - pad).toFixed(1) + " " + vbW.toFixed(1) + " " + vbH.toFixed(1) +
    '" preserveAspectRatio="xMidYMid meet" role="img" ' +
    'aria-label="Scene isometrique des agents">';

  /* 1) Le sol : une tuile en losange par cellule (damier discret). */
  cellules.forEach(function (k, i) {
    svg += losange(k.cx, k.cy, ISO_TW, ISO_TH, "tuile" + (i % 2 ? " tuile-b" : ""));
  });

  /* 2) Les agents : ombre au sol, mat, jeton eleve colore par le type du
        dernier message, rang par force, nom, force, infobulle ECHAPPEE. */
  cellules.forEach(function (k) {
    var dernier = dernierEmis(k.nom);
    var typ = dernier ? (dernier.type || "?") : null;
    var coul = typ ? couleurType(typ) : "#8b94ab";
    var f = forceDe(k.nom);
    var r = 13 + Math.min(11, Math.max(0, (f - CFG.force_defaut) * 6));
    var tx = k.cx, ty = k.cy - ISO_LIFT;
    var actif = dernier && k.nom === dernierGlobal;
    var infobulle = dernier
      ? esc(k.nom) + " - " + esc(typ) + " : " + esc(resumer(dernier.contenu))
      : esc(k.nom) + " - silencieux, aucun message emis";
    var fTxt = f.toFixed(4).replace(/\.?0+$/, "");
    svg += '<g class="agent-iso"><title>' + infobulle + '</title>';
    svg += losange(k.cx, k.cy, 40, 20, "ombre");
    svg += '<line x1="' + k.cx.toFixed(1) + '" y1="' + k.cy.toFixed(1) +
      '" x2="' + tx.toFixed(1) + '" y2="' + ty.toFixed(1) + '" class="mat"/>';
    svg += '<circle cx="' + tx.toFixed(1) + '" cy="' + ty.toFixed(1) + '" r="' +
      r.toFixed(1) + '" fill="' + coul + '" class="jeton' + (actif ? " actif" : "") + '"/>';
    svg += '<text x="' + tx.toFixed(1) + '" y="' + (ty + 4).toFixed(1) +
      '" class="rang">' + k.rang + '</text>';
    svg += '<text x="' + tx.toFixed(1) + '" y="' + (ty - r - 8).toFixed(1) +
      '" class="nom-iso">' + esc(k.nom) + '</text>';
    /* Force accrochee AU jeton (juste dessous) : elle suit l'elevation et
       n'empiete pas sur les tuiles voisines. */
    svg += '<text x="' + tx.toFixed(1) + '" y="' + (ty + r + 14).toFixed(1) +
      '" class="force-iso">x' + esc(fTxt) + '</text>';
    svg += '</g>';
  });

  svg += '</svg>';
  zone.innerHTML = svg;
}

function ligneFil(m, neuf) {
  var dest = m.destinataire === CFG.broadcast
    ? '<span class="qui">tous</span>'
    : '<span class="qui">' + esc(m.destinataire) + '</span>';
  var typ = m.type || "?";
  return '<li' + (neuf ? ' class="neuf"' : '') + '>' +
    '<span class="ts">' + esc(m.ts || "") + '</span> ' +
    '<span class="qui">' + esc(m.expediteur) + '</span>' +
    '<span class="fleche">&rarr;</span>' + dest +
    ' <span class="type t-' + esc(typ) + '">' + esc(typ) + '</span> ' +
    '<span class="contenu">' + esc(resumer(m.contenu)) + '</span></li>';
}

function rendre(nbNeufs) {
  /* Agents tries par force decroissante puis nom : cet ORDRE fixe le rang et
     donc la place de chacun sur la grille isometrique (decoratif). */
  var noms = agentsDe().sort(function (a, b) {
    var d = forceDe(b) - forceDe(a);
    return d !== 0 ? d : (a < b ? -1 : a > b ? 1 : 0);
  });
  rendreScene(noms);

  /* Fil : les CFG.flux_max derniers, les plus récents en tête. */
  var recents = MSG.slice(-CFG.flux_max);
  var zoneF = document.getElementById("fil"), html = "";
  for (var i = recents.length - 1; i >= 0; i--) {
    /* les nbNeufs derniers messages du bus sont « neufs » (surlignés). */
    var neuf = i >= recents.length - nbNeufs;
    html += ligneFil(recents[i], neuf);
  }
  zoneF.innerHTML = html || '<li class="vide">Aucun message sur le bus.</li>';

  /* KPIs. */
  var types = {};
  MSG.forEach(function (m) { var t = m.type || "?"; types[t] = (types[t] || 0) + 1; });
  document.getElementById("kpi-agents").textContent = noms.length;
  document.getElementById("kpi-messages").textContent = MSG.length;
  var tk = Object.keys(types).sort().map(function (t) {
    return esc(t) + " : " + types[t];
  }).join(" · ");
  document.getElementById("kpi-types").innerHTML = tk || "&mdash;";
}

function marquer(ok, texte) {
  var e = document.getElementById("live-etat");
  e.className = "etat-live " + (ok ? "ok" : "ko");
  e.textContent = texte;
}

function poll() {
  var depuis = premier ? 0 : offset;
  fetch("/events?since=" + depuis)
    .then(function (r) { return r.json(); })
    .then(function (j) {
      forces = j.forces || {};
      offset = j.offset;
      var neufs = j.messages || [];
      if (premier) { MSG = neufs.slice(); premier = false; }
      else if (neufs.length) { MSG = MSG.concat(neufs); }
      rendre(premier ? 0 : neufs.length);
      marquer(true, "en direct · " + MSG.length + " message(s) · offset " + offset);
    })
    .catch(function () { marquer(false, "serveur injoignable — nouvelle tentative…"); });
}

poll();
setInterval(poll, CFG.poll_ms);
"""


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main():
    p = argparse.ArgumentParser(
        description="NEXUS — Bureau 2D LIVE de l'Agent OS (lecture seule)")
    p.add_argument("--port", type=int, default=PORT_DEFAUT)
    a = p.parse_args()

    srv = creer_serveur(a.port)
    print(f"🖥️  Bureau NEXUS LIVE — http://127.0.0.1:{a.port}  "
          f"(lecture seule, Ctrl-C pour arrêter)")
    _, bus = nexus_bus._chemins()
    print(f"   bus     : {bus}")
    print(f"   forces  : {nexus_force._chemin_forces()}")
    print(f"   poll    : {POLL_MS} ms (tail-since-offset O(1))")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
