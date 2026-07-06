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
        cartes = "".join(bureau._carte_agent(a) for a in synth["agents"])
    else:
        cartes = ('<p class="vide">Aucun agent : le bus agentos est vide ou '
                  'absent. Les cartes appara&icirc;tront d&egrave;s que de '
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
        '<p class="sous">Vue 2D <b>temps r&eacute;el</b> du bus agentos '
        '(agentos/bus.jsonl), en lecture seule. Le fil et les cartes se '
        'mettent &agrave; jour tout seuls &mdash; agents R&Eacute;ELS, rien '
        'n\'est simul&eacute;. <span id="live-etat" class="etat-live">'
        'connexion&hellip;</span></p>\n'
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
        '    <h2>Agents &mdash; nom, force vivante, dernier message</h2>\n'
        f'    <div class="agents" id="agents">{cartes}</div>\n'
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


# Complément de style pour l'indicateur « live » (le reste vient de bureau._STYLE).
_STYLE_LIVE = """
<style>
  .etat-live { color:var(--sourd); font-size:11px; margin-left:6px; }
  .etat-live.ok { color:var(--vert); }
  .etat-live.ko { color:var(--rose); }
  ul.fil li.neuf { animation:apparait .8s ease; }
  @keyframes apparait { from { background:rgba(79,192,122,.18); } to { background:transparent; } }
</style>"""


# Script de poll : reconstruit cartes + fil + KPIs depuis les messages ACCUMULÉS
# (poll incrémental via tail-since-offset). Tout texte est ÉCHAPPÉ avant le DOM.
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

function carteAgent(nom) {
  var dernier = null;
  for (var i = MSG.length - 1; i >= 0; i--) {
    if (MSG[i].expediteur === nom) { dernier = MSG[i]; break; }
  }
  var f = forceDe(nom).toFixed(4).replace(/\.?0+$/, "");
  var det;
  if (dernier) {
    var typ = dernier.type || "?";
    det = '<p class="dernier"><span class="type t-' + esc(typ) + '">' + esc(typ) +
          '</span> ' + esc(resumer(dernier.contenu)) + '</p>' +
          '<p class="ts">' + esc(dernier.ts || "") + '</p>';
  } else {
    det = '<p class="dernier vide">silencieux &mdash; aucun message émis</p>';
  }
  return '<div class="agent"><div class="agent-tete">' +
    '<span class="nom">' + esc(nom) + '</span>' +
    '<span class="force">&times;' + esc(f) + '</span></div>' + det + '</div>';
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
  /* Cartes : triées par force décroissante puis nom. */
  var noms = agentsDe().sort(function (a, b) {
    var d = forceDe(b) - forceDe(a);
    return d !== 0 ? d : (a < b ? -1 : a > b ? 1 : 0);
  });
  var zoneA = document.getElementById("agents");
  zoneA.innerHTML = noms.length
    ? noms.map(carteAgent).join("")
    : '<p class="vide">Aucun agent : le bus agentos est vide ou absent.</p>';

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
