#!/usr/bin/env python3
"""
NEXUS — Ligue visible (bureau 2D « Ligue NEXUS », lecture seule)
« Voir l'organisme jouer, sans jamais toucher au ballon. »

Petit serveur local (stdlib http.server, port 8078) qui affiche :
  - le CLASSEMENT DE LIGUE : chaque fiche mémoire = un JOUEUR, sa force
    (forces.json) = ses points ; flèche promotion/relégation selon
    l'évolution récente des capteurs porteurs d'une fiche ;
  - l'ACTIVITÉ DE LA BOUCLE en fil live : capteurs/journal.jsonl et
    lecons/journal.jsonl, suivis en PULL tail-since-offset (le front
    polle /events?source=…&since=<offset> toutes les 500 ms).

Garanties par conception :
  - LECTURE SEULE : ce module n'ouvre les sources qu'en lecture ; il
    n'écrit rien, ne crée rien, ne verrouille rien. La boucle ne dépend
    jamais du dashboard (elle ignore son existence).
  - Mêmes contrats env que la boucle, relus à CHAQUE appel :
      forces.json           → MEMOIRE_ROOT   (via nexus_force)
      capteurs/journal.jsonl → CAPTEURS_ROOT (via nexus_sense)
      lecons/journal.jsonl   → LECONS_ROOT   (même logique que nexus_pont)
  - Front : UNE page HTML embarquée dans ce module (SVG simple, zéro CDN).

Usage :
  python3 nexus_ligue.py                # sert http://127.0.0.1:8078
  python3 nexus_ligue.py --port 9000
  python3 nexus_ligue.py --classement   # affiche le classement en console et sort
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
import nexus_sense  # source UNIQUE du chemin capteurs (respecte CAPTEURS_ROOT)
import nexus_force  # source UNIQUE du chemin forces.json (respecte MEMOIRE_ROOT)

PORT_DEFAUT = 8078
# « Évolution récente » = les N derniers événements porteurs d'une fiche.
# Petit par choix : une flèche doit refléter la forme du moment, pas la saison.
FENETRE_RECENTE = 5


# --------------------------------------------------------------------------- #
# Chemins des sources (relus à CHAQUE appel — jamais figés à l'import)
# --------------------------------------------------------------------------- #
def _chemin_capteurs():
    return nexus_sense._chemins()[1]


def _chemin_lecons():
    """Même contrat que nexus_pont._dir_lecons : LECONS_ROOT sinon
    memoire_data/ relatif à organes/ (le fichier que nexus_lecons écrit)."""
    base = os.environ.get("LECONS_ROOT")
    root = base if base else os.path.join(SCRIPT_DIR, "memoire_data")
    return os.path.join(root, "lecons", "journal.jsonl")


SOURCES = {"capteurs": _chemin_capteurs, "lecons": _chemin_lecons}


# --------------------------------------------------------------------------- #
# Tail-since-offset (transport PULL)
# --------------------------------------------------------------------------- #
def tail_depuis(chemin, offset):
    """Renvoie (nouvelles_lignes, nouvel_offset) — LECTURE SEULE.

    - fichier absent            → ([], 0)
    - offset > taille du fichier (recréé/tronqué entre deux polls) → repart de 0
    - dernière ligne incomplète (pas de \\n final : écriture en cours) →
      laissée de côté, l'offset ne la dépasse pas ; elle sera servie entière
      au poll suivant. Aucune ligne ne peut donc être perdue ni coupée.
    """
    offset = max(0, int(offset))
    try:
        taille = os.path.getsize(chemin)
    except OSError:
        return [], 0
    if offset > taille:
        offset = 0
    if offset == taille:
        return [], offset
    with open(chemin, "rb") as f:
        f.seek(offset)
        data = f.read(taille - offset)
    fin = data.rfind(b"\n")
    if fin < 0:  # que du partiel : rien de complet à livrer
        return [], offset
    lignes = [
        l.decode("utf-8", "replace")
        for l in data[: fin + 1].split(b"\n")
        if l.strip()
    ]
    return lignes, offset + fin + 1


def evenements_depuis(source, offset):
    """Tail d'une source nommée ('capteurs' | 'lecons')."""
    if source not in SOURCES:
        raise KeyError(source)
    return tail_depuis(SOURCES[source](), offset)


# --------------------------------------------------------------------------- #
# Classement de ligue (forces = points ; flèches = évolution récente)
# --------------------------------------------------------------------------- #
def classement():
    """Liste de joueurs triée par points décroissants.
    points     = force actuelle dans forces.json (l'état écrit par la boucle) ;
    tendance   = comparaison entre la force recalculée sur TOUT l'historique
                 capteurs et celle recalculée SANS les FENETRE_RECENTE derniers
                 événements porteurs d'une fiche :
                 'promotion' (↑), 'relegation' (↓) ou 'stable' (=).
    Tout est recalculé à chaque appel, rien n'est écrit (calculer_forces est
    un pur dry-run tant qu'on n'appelle pas ecrire_forces/appliquer)."""
    forces_fichier = nexus_force._lire_forces_existantes()
    evts = [e for e in nexus_sense.lire() if e.get("fiche")]
    anciens = evts[:-FENETRE_RECENTE] if len(evts) > FENETRE_RECENTE else []
    maintenant = nexus_force.calculer_forces(evts)
    avant = nexus_force.calculer_forces(anciens)

    joueurs = []
    for fiche in set(forces_fichier) | set(maintenant):
        points = forces_fichier.get(fiche, maintenant.get(fiche, nexus_force.FORCE_DEFAUT))
        delta = round(
            maintenant.get(fiche, nexus_force.FORCE_DEFAUT)
            - avant.get(fiche, nexus_force.FORCE_DEFAUT), 4)
        tendance = ("promotion" if delta > 0
                    else "relegation" if delta < 0 else "stable")
        joueurs.append({"fiche": fiche, "points": points,
                        "tendance": tendance, "delta": delta})
    joueurs.sort(key=lambda j: (-j["points"], j["fiche"]))
    for rang, j in enumerate(joueurs, 1):
        j["rang"] = rang
    return joueurs


# --------------------------------------------------------------------------- #
# Serveur HTTP (stdlib uniquement)
# --------------------------------------------------------------------------- #
class LigueHandler(BaseHTTPRequestHandler):
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
            corps = PAGE_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corps)))
            self.end_headers()
            self.wfile.write(corps)
        elif url.path == "/classement":
            self._json({"joueurs": classement(),
                        "fenetre_recente": FENETRE_RECENTE})
        elif url.path == "/events":
            q = parse_qs(url.query)
            source = q.get("source", ["capteurs"])[0]
            try:
                since = int(q.get("since", ["0"])[0])
            except ValueError:
                since = 0
            try:
                lignes, offset = evenements_depuis(source, since)
            except KeyError:
                self._json({"erreur": f"source inconnue : {source}",
                            "sources": sorted(SOURCES)}, code=400)
                return
            self._json({"source": source, "lignes": lignes, "offset": offset})
        else:
            self._json({"erreur": "introuvable"}, code=404)


def creer_serveur(port=PORT_DEFAUT, hote="127.0.0.1"):
    """Instancie le serveur sans le lancer (port=0 → port libre, pour tests)."""
    return ThreadingHTTPServer((hote, port), LigueHandler)


# --------------------------------------------------------------------------- #
# Front : UNE page, embarquée, SVG simple, zéro dépendance externe
# --------------------------------------------------------------------------- #
PAGE_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ligue NEXUS</title>
<style>
  :root { --fond:#0f1420; --carte:#171e2e; --ligne:#232c42; --texte:#e8ecf5;
          --sourd:#8b94ab; --or:#e8b93c; --vert:#4fc07a; --rouge:#e06060;
          --barre:#3d6fe0; }
  * { box-sizing:border-box; margin:0; }
  body { background:var(--fond); color:var(--texte);
         font:14px/1.5 system-ui, sans-serif; padding:20px; }
  h1 { font-size:20px; letter-spacing:.06em; }
  h1 .badge { color:var(--or); }
  .sous { color:var(--sourd); font-size:12px; margin:2px 0 16px; }
  .grille { display:grid; grid-template-columns:minmax(420px,3fr) minmax(300px,2fr);
            gap:16px; align-items:start; }
  @media (max-width:900px){ .grille { grid-template-columns:1fr; } }
  .carte { background:var(--carte); border:1px solid var(--ligne);
           border-radius:10px; padding:14px 16px; }
  .carte h2 { font-size:13px; text-transform:uppercase; letter-spacing:.1em;
              color:var(--sourd); margin-bottom:10px; }
  svg text { font:12px system-ui, sans-serif; fill:var(--texte); }
  svg .rang { fill:var(--sourd); }
  svg .pts { font-weight:600; }
  svg .fleche-haut { fill:var(--vert); font-weight:700; }
  svg .fleche-bas { fill:var(--rouge); font-weight:700; }
  svg .fleche-egal { fill:var(--sourd); }
  #fil { list-style:none; max-height:480px; overflow-y:auto; }
  #fil li { border-bottom:1px solid var(--ligne); padding:6px 2px;
            font-size:12.5px; }
  #fil .src-capteurs { color:var(--barre); font-weight:600; }
  #fil .src-lecons { color:var(--or); font-weight:600; }
  #fil .ts { color:var(--sourd); margin-left:6px; }
  #etat { font-size:11px; color:var(--sourd); margin-top:8px; }
  .vide { color:var(--sourd); font-style:italic; padding:8px 0; }
</style>
</head>
<body>
<h1><span class="badge">&#9917;</span> LIGUE NEXUS <span class="badge">v2.5</span></h1>
<p class="sous">Bureau visible &mdash; lecture seule. Les fiches m&eacute;moire sont les joueurs,
leur force fait leurs points ; la boucle joue, la ligue regarde.</p>
<div class="grille">
  <div class="carte">
    <h2>Classement de ligue</h2>
    <div id="classement"><p class="vide">Chargement&hellip;</p></div>
  </div>
  <div class="carte">
    <h2>Activit&eacute; de la boucle (fil live)</h2>
    <ul id="fil"></ul>
    <p id="etat">en attente du premier poll&hellip;</p>
  </div>
</div>
<script>
"use strict";
var offsets = { capteurs: 0, lecons: 0 };
var nbEvts = 0;

function esc(s) {
  return String(s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
  });
}

function dessinerClassement(joueurs) {
  var zone = document.getElementById("classement");
  if (!joueurs.length) {
    zone.innerHTML = '<p class="vide">Aucun joueur : forces.json vide et aucun capteur porteur de fiche.</p>';
    return;
  }
  var H = 34, PAD = 6, largeur = 640;
  var maxPts = Math.max.apply(null, joueurs.map(function (j) { return j.points; }).concat([1]));
  var svg = '<svg viewBox="0 0 ' + largeur + ' ' + (joueurs.length * H + PAD) +
            '" width="100%" role="img" aria-label="classement">';
  joueurs.forEach(function (j, i) {
    var y = i * H + PAD;
    var barre = Math.max(4, (j.points / maxPts) * 300);
    var fleche = j.tendance === "promotion" ? ["&#9650;", "fleche-haut"]
               : j.tendance === "relegation" ? ["&#9660;", "fleche-bas"]
               : ["&#61;", "fleche-egal"];
    svg += '<text class="rang" x="4" y="' + (y + 18) + '">' + j.rang + '</text>' +
      '<text x="30" y="' + (y + 18) + '">' + esc(j.fiche) + '</text>' +
      '<rect x="230" y="' + (y + 6) + '" width="' + barre.toFixed(1) +
      '" height="16" rx="3" fill="var(--barre)" opacity="0.85"></rect>' +
      '<text class="pts" x="545" y="' + (y + 18) + '" text-anchor="end">' +
      j.points.toFixed(2) + ' pts</text>' +
      '<text class="' + fleche[1] + '" x="560" y="' + (y + 18) + '">' + fleche[0] + '</text>';
  });
  zone.innerHTML = svg + "</svg>";
}

function resumer(source, brut) {
  var e;
  try { e = JSON.parse(brut); } catch (err) { return esc(brut); }
  var ts = e.ts ? '<span class="ts">' + esc(e.ts) + "</span>" : "";
  if (source === "capteurs") {
    var fiche = e.fiche ? " &middot; fiche " + esc(e.fiche) : "";
    return '<span class="src-capteurs">capteur</span> [' + esc(e.statut || "?") +
           "] " + esc(e.tache || "") + fiche + ts;
  }
  return '<span class="src-lecons">le&ccedil;on</span> [' + esc(e.type || "?") +
         "] " + esc(e.lecon || "") + ts;
}

function ajouterAuFil(source, lignes) {
  if (!lignes.length) return;
  var fil = document.getElementById("fil");
  lignes.forEach(function (l) {
    var li = document.createElement("li");
    li.innerHTML = resumer(source, l);
    fil.insertBefore(li, fil.firstChild);
    nbEvts += 1;
  });
  while (fil.children.length > 200) fil.removeChild(fil.lastChild);
}

function pollEvents(source) {
  fetch("/events?source=" + source + "&since=" + offsets[source])
    .then(function (r) { return r.json(); })
    .then(function (j) {
      offsets[source] = j.offset;
      ajouterAuFil(source, j.lignes);
      document.getElementById("etat").innerHTML =
        nbEvts + " &eacute;v&eacute;nement(s) re&ccedil;u(s) &mdash; poll 500 ms (capteurs@" +
        offsets.capteurs + ", le&ccedil;ons@" + offsets.lecons + ")";
    })
    .catch(function () { /* serveur absent : on retentera au prochain tick */ });
}

function pollClassement() {
  fetch("/classement")
    .then(function (r) { return r.json(); })
    .then(function (j) { dessinerClassement(j.joueurs); })
    .catch(function () {});
}

setInterval(function () { pollEvents("capteurs"); pollEvents("lecons"); }, 500);
setInterval(pollClassement, 1000);
pollEvents("capteurs"); pollEvents("lecons"); pollClassement();
</script>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main():
    p = argparse.ArgumentParser(description="NEXUS — Ligue visible (lecture seule)")
    p.add_argument("--port", type=int, default=PORT_DEFAUT)
    p.add_argument("--classement", action="store_true",
                   help="afficher le classement en console et sortir (pas de serveur)")
    a = p.parse_args()

    if a.classement:
        joueurs = classement()
        print("⚽ NEXUS — Ligue (forces = points)\n")
        if not joueurs:
            print("📭 Aucun joueur : forces.json vide et aucun capteur porteur de fiche.")
        for j in joueurs:
            fleche = {"promotion": "▲", "relegation": "▼", "stable": "="}[j["tendance"]]
            print(f"   {j['rang']:>2}. {j['fiche']:<30} {j['points']:>5.2f} pts  {fleche}")
        return

    srv = creer_serveur(a.port)
    print(f"⚽ Ligue NEXUS — http://127.0.0.1:{a.port}  (lecture seule, Ctrl-C pour arrêter)")
    print(f"   forces   : {nexus_force._chemin_forces()}")
    print(f"   capteurs : {_chemin_capteurs()}")
    print(f"   leçons   : {_chemin_lecons()}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
