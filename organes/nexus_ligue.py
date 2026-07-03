#!/usr/bin/env python3
"""
NEXUS — Ligue visible v2.6 (bureau 2D « Ligue NEXUS », lecture seule)
« Voir l'organisme jouer, sans jamais toucher au ballon. »

Petit serveur local (stdlib http.server, port 8078) qui affiche :
  - la VUE LIGUE : chaque fiche mémoire = un JOUEUR, sa force (forces.json)
    = ses points ; flèche ▲/▼/= selon l'évolution récente des capteurs ;
    deux divisions (Ligue 1 / Ligue 2) séparées par un SEUIL paramétrable
    (--seuil, défaut 1.0 — décision Kily en attente, affiché « défaut ») ;
    promotion/relégation = franchissement du seuil entre les deux lectures
    (force recalculée sans la fenêtre récente vs. avec) ;
  - le MUR DES LÉGENDES : fiches marquées legende=true dans le
    force_journal, ou dont le multiplicateur atteint FORCE_MAX ;
  - la VUE BUREAU : les 4 organes NEXUS (95 tête pensante, 96 analyste,
    97 exécutant, 98 gardien) en personnages 2D SVG à leur poste, dont
    l'état reflète les DERNIERS capteurs RÉELS (pas d'agents fictifs) ;
  - l'ACTIVITÉ DE LA BOUCLE en fil live : capteurs/journal.jsonl et
    lecons/journal.jsonl, suivis en PULL tail-since-offset (le front
    polle /events?source=…&since=<offset> toutes les 500 ms).

Garanties par conception :
  - LECTURE SEULE : ce module n'ouvre les sources qu'en lecture ; il
    n'écrit rien, ne crée rien, ne verrouille rien. La boucle ne dépend
    jamais du dashboard (elle ignore son existence).
  - Mêmes contrats env que la boucle, relus à CHAQUE appel :
      forces.json + force_journal.jsonl → MEMOIRE_ROOT (via nexus_force)
      capteurs/journal.jsonl            → CAPTEURS_ROOT (via nexus_sense)
      lecons/journal.jsonl              → LECONS_ROOT (comme nexus_pont)
  - Front : UNE page HTML embarquée dans ce module (SVG simple, zéro CDN).

Usage :
  python3 nexus_ligue.py                 # sert http://127.0.0.1:8078
  python3 nexus_ligue.py --port 9000 --seuil 1.5
  python3 nexus_ligue.py --classement    # classement en console et sort
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
# Seuil Ligue 1 / Ligue 2. La valeur définitive est une décision Kily encore
# en attente : 1.0 est un DÉFAUT assumé, affiché comme tel dans l'interface.
SEUIL_DEFAUT = 1.0
# « Évolution récente » = les N derniers événements porteurs d'une fiche.
# Petit par choix : une flèche doit refléter la forme du moment, pas la saison.
FENETRE_RECENTE = 5
# Vue bureau : un organe sans événement dans les N derniers capteurs = au repos.
FENETRE_BUREAU = 10

# Les 4 organes du bureau. Leurs états viennent des capteurs RÉELS de la
# boucle — c'est toute la différence avec les bureaux d'agents fictifs.
ORGANES = {
    "95": {"nom": "Tête pensante", "role": "décide"},
    "96": {"nom": "Analyste", "role": "mesure"},
    "97": {"nom": "Exécutant", "role": "fait"},
    "98": {"nom": "Gardien", "role": "protège"},
}


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


def _chemin_force_journal():
    """Journal des forces, À CÔTÉ de forces.json (MEMOIRE_ROOT). Contrat
    DÉFENSIF : aucun organe n'écrit encore ce fichier dans le dépôt — le
    mur des légendes le lit s'il existe (entrées {"fiche":…, "legende":true})
    et l'ignore sinon."""
    return os.path.join(nexus_force._racine_memoire(), "force_journal.jsonl")


SOURCES = {"capteurs": _chemin_capteurs, "lecons": _chemin_lecons}


# --------------------------------------------------------------------------- #
# Tail-since-offset (transport PULL)
# --------------------------------------------------------------------------- #
def tail_depuis(chemin, offset):
    """Renvoie (nouvelles_lignes, nouvel_offset) — LECTURE SEULE, O(delta) :
    on seek() à l'offset et on ne lit QUE les octets nouveaux, jamais le
    fichier entier (prouvé par test : délai indépendant de la taille totale).

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
# Classement de ligue (forces = points ; flèches = forme ; seuil = division)
# --------------------------------------------------------------------------- #
def classement(seuil=SEUIL_DEFAUT):
    """Liste de joueurs triée par points décroissants.
    points   = force actuelle dans forces.json (l'état écrit par la boucle) ;
    tendance = comparaison entre la force recalculée sur TOUT l'historique
               capteurs et celle recalculée SANS les FENETRE_RECENTE derniers
               événements porteurs d'une fiche ('promotion'/'relegation'/
               'stable') — la « forme récente » ;
    division = 'Ligue 1' si points >= seuil, sinon 'Ligue 2' ;
    mouvement= franchissement du SEUIL entre les deux lectures (avant/
               maintenant) : 'monte' (passe en Ligue 1), 'descend' (passe en
               Ligue 2) ou None — le contrat tête pensante, en PLUS des
               flèches de forme.
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
        pts_avant = avant.get(fiche, nexus_force.FORCE_DEFAUT)
        pts_apres = maintenant.get(fiche, nexus_force.FORCE_DEFAUT)
        delta = round(pts_apres - pts_avant, 4)
        tendance = ("promotion" if delta > 0
                    else "relegation" if delta < 0 else "stable")
        if pts_avant < seuil <= pts_apres:
            mouvement = "monte"
        elif pts_apres < seuil <= pts_avant:
            mouvement = "descend"
        else:
            mouvement = None
        joueurs.append({
            "fiche": fiche, "points": points, "tendance": tendance,
            "delta": delta,
            "division": "Ligue 1" if points >= seuil else "Ligue 2",
            "mouvement": mouvement,
        })
    joueurs.sort(key=lambda j: (-j["points"], j["fiche"]))
    for rang, j in enumerate(joueurs, 1):
        j["rang"] = rang
    return joueurs


# --------------------------------------------------------------------------- #
# Mur des légendes
# --------------------------------------------------------------------------- #
def _lire_force_journal():
    chemin = _chemin_force_journal()
    out = []
    try:
        with open(chemin, encoding="utf-8") as f:
            for l in f:
                l = l.strip()
                if l:
                    try:
                        out.append(json.loads(l))
                    except ValueError:
                        pass
    except OSError:
        pass
    return out


def legendes():
    """Fiches légendaires : marquées legende=true dans le force_journal, OU
    dont le multiplicateur a atteint le plafond FORCE_MAX dans forces.json."""
    forces = nexus_force._lire_forces_existantes()
    murs = {}
    for rec in _lire_force_journal():
        fiche = rec.get("fiche")
        if fiche and rec.get("legende") is True:
            murs[fiche] = {"fiche": fiche, "points": forces.get(fiche),
                           "source": "journal"}
    for fiche, mult in forces.items():
        if (fiche not in murs and isinstance(mult, (int, float))
                and mult >= nexus_force.FORCE_MAX):
            murs[fiche] = {"fiche": fiche, "points": mult, "source": "force_max"}
    return sorted(murs.values(), key=lambda m: m["fiche"])


# --------------------------------------------------------------------------- #
# Vue bureau : 4 organes, états tirés des DERNIERS capteurs réels
# --------------------------------------------------------------------------- #
def _organe_pour(evt):
    """HEURISTIQUE v1, ASSUMÉE : les capteurs ne portent pas (encore) de champ
    « organe », on infère donc le poste depuis les champs existants, dans cet
    ordre (le premier critère qui matche gagne) :
      1. tier CONSEIL ou DUO           → 95 (orchestration = la tête pensante)
      2. note contenant analyse/mesure → 96 (l'analyste)
      3. note contenant sante/garde    → 98 (le gardien)
      4. défaut                        → 97 (l'exécutant fait le reste)
    À remplacer par un champ explicite quand la boucle en émettra un."""
    tier = (evt.get("tier") or "").upper()
    note = (evt.get("note") or "").lower()
    if tier in ("CONSEIL", "DUO"):
        return "95"
    if "analyse" in note or "mesure" in note:
        return "96"
    if "sante" in note or "santé" in note or "garde" in note:
        return "98"
    return "97"


def vue_bureau():
    """État des 4 postes du bureau, dérivé des FENETRE_BUREAU derniers
    capteurs réels : dernier événement mappé sur l'organe →
      statut echec           → 'alerte'   (rouge)
      tout autre statut      → 'travaille' (vert — ok/succes/partiel)
      aucun événement récent → 'repos'    (gris)"""
    recents = nexus_sense.lire()[-FENETRE_BUREAU:]
    postes = {
        code: {"code": code, "nom": info["nom"], "role": info["role"],
               "etat": "repos", "tache": None, "statut": None, "ts": None}
        for code, info in ORGANES.items()
    }
    for ev in recents:  # ordre chronologique : le dernier événement l'emporte
        p = postes[_organe_pour(ev)]
        p["etat"] = "alerte" if ev.get("statut") == "echec" else "travaille"
        p["tache"] = ev.get("tache")
        p["statut"] = ev.get("statut")
        p["ts"] = ev.get("ts")
    return [postes[c] for c in ("95", "96", "97", "98")]


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
            seuil = getattr(self.server, "seuil", SEUIL_DEFAUT)
            self._json({
                "joueurs": classement(seuil=seuil),
                "legendes": legendes(),
                "seuil": seuil,
                "seuil_est_defaut": getattr(self.server, "seuil_est_defaut", True),
                "fenetre_recente": FENETRE_RECENTE,
            })
        elif url.path == "/bureau":
            self._json({"organes": vue_bureau(), "fenetre": FENETRE_BUREAU})
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


def creer_serveur(port=PORT_DEFAUT, hote="127.0.0.1", seuil=None):
    """Instancie le serveur sans le lancer (port=0 → port libre, pour tests).
    seuil=None → SEUIL_DEFAUT, marqué « défaut » dans l'interface (la valeur
    définitive est une décision Kily en attente)."""
    srv = ThreadingHTTPServer((hote, port), LigueHandler)
    srv.seuil = SEUIL_DEFAUT if seuil is None else float(seuil)
    srv.seuil_est_defaut = seuil is None
    return srv


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
          --gris:#6a7386; --barre:#3d6fe0; }
  * { box-sizing:border-box; margin:0; }
  body { background:var(--fond); color:var(--texte);
         font:14px/1.5 system-ui, sans-serif; padding:20px; }
  h1 { font-size:20px; letter-spacing:.06em; }
  h1 .badge { color:var(--or); }
  .sous { color:var(--sourd); font-size:12px; margin:2px 0 12px; }
  .onglets { margin-bottom:14px; }
  .onglets button { background:var(--carte); color:var(--sourd);
    border:1px solid var(--ligne); border-radius:8px 8px 0 0;
    padding:8px 22px; font:600 13px system-ui; cursor:pointer; }
  .onglets button.actif { color:var(--texte); border-bottom-color:var(--or); }
  .grille { display:grid; grid-template-columns:minmax(420px,3fr) minmax(300px,2fr);
            gap:16px; align-items:start; }
  @media (max-width:900px){ .grille { grid-template-columns:1fr; } }
  .carte { background:var(--carte); border:1px solid var(--ligne);
           border-radius:10px; padding:14px 16px; margin-bottom:16px; }
  .carte h2 { font-size:13px; text-transform:uppercase; letter-spacing:.1em;
              color:var(--sourd); margin-bottom:10px; }
  .carte.doree { border-color:var(--or); }
  .carte.doree h2 { color:var(--or); }
  #legendes span { display:inline-block; background:rgba(232,185,60,.12);
    border:1px solid var(--or); color:var(--or); border-radius:6px;
    padding:2px 10px; margin:2px 6px 2px 0; font-size:12.5px; }
  svg text { font:12px system-ui, sans-serif; fill:var(--texte); }
  svg .rang { fill:var(--sourd); }
  svg .pts { font-weight:600; }
  svg .fleche-haut { fill:var(--vert); font-weight:700; }
  svg .fleche-bas { fill:var(--rouge); font-weight:700; }
  svg .fleche-egal { fill:var(--sourd); }
  svg .seuil { fill:var(--or); font-size:11px; }
  svg .mouv-haut { fill:var(--vert); font-size:10.5px; }
  svg .mouv-bas { fill:var(--rouge); font-size:10.5px; }
  svg .poste-nom { font-weight:700; }
  svg .poste-detail { fill:var(--sourd); font-size:10.5px; }
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
<h1><span class="badge">&#9917;</span> LIGUE NEXUS <span class="badge">v2.6</span></h1>
<p class="sous">Bureau visible &mdash; lecture seule. Agents R&Eacute;ELS : chaque &eacute;tat vient
des capteurs de la boucle, rien n'est simul&eacute;.</p>
<nav class="onglets">
  <button id="ong-ligue" class="actif">Ligue</button>
  <button id="ong-bureau">Bureau</button>
</nav>

<section id="vue-ligue">
  <div class="grille">
    <div>
      <div class="carte doree" id="carte-legendes" hidden>
        <h2>&#11088; Mur des l&eacute;gendes</h2>
        <div id="legendes"></div>
      </div>
      <div class="carte">
        <h2>Classement de ligue <span id="info-seuil"></span></h2>
        <div id="classement"><p class="vide">Chargement&hellip;</p></div>
      </div>
    </div>
    <div class="carte">
      <h2>Activit&eacute; de la boucle (fil live)</h2>
      <ul id="fil"></ul>
      <p id="etat">en attente du premier poll&hellip;</p>
    </div>
  </div>
</section>

<section id="vue-bureau" hidden>
  <div class="carte">
    <h2>Le bureau NEXUS &mdash; 4 organes, &eacute;tats tir&eacute;s des derniers capteurs r&eacute;els</h2>
    <div id="bureau"><p class="vide">Chargement&hellip;</p></div>
  </div>
</section>

<script>
"use strict";
var offsets = { capteurs: 0, lecons: 0 };
var nbEvts = 0;

document.getElementById("ong-ligue").onclick = function () { montrer("ligue"); };
document.getElementById("ong-bureau").onclick = function () { montrer("bureau"); };
function montrer(vue) {
  document.getElementById("vue-ligue").hidden = vue !== "ligue";
  document.getElementById("vue-bureau").hidden = vue !== "bureau";
  document.getElementById("ong-ligue").className = vue === "ligue" ? "actif" : "";
  document.getElementById("ong-bureau").className = vue === "bureau" ? "actif" : "";
}

function esc(s) {
  return String(s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
  });
}

/* ---------------- vue Ligue ---------------- */
function ligneJoueur(j, y, maxPts) {
  var barre = Math.max(4, (j.points / maxPts) * 280);
  var fleche = j.tendance === "promotion" ? ["&#9650;", "fleche-haut"]
             : j.tendance === "relegation" ? ["&#9660;", "fleche-bas"]
             : ["&#61;", "fleche-egal"];
  var mouv = "";
  if (j.mouvement === "monte")
    mouv = '<text class="mouv-haut" x="588" y="' + (y + 18) + '">&#8679;L1</text>';
  if (j.mouvement === "descend")
    mouv = '<text class="mouv-bas" x="588" y="' + (y + 18) + '">&#8681;L2</text>';
  return '<text class="rang" x="4" y="' + (y + 18) + '">' + j.rang + '</text>' +
    '<text x="30" y="' + (y + 18) + '">' + esc(j.fiche) + '</text>' +
    '<rect x="230" y="' + (y + 6) + '" width="' + barre.toFixed(1) +
    '" height="16" rx="3" fill="var(--barre)" opacity="0.85"></rect>' +
    '<text class="pts" x="545" y="' + (y + 18) + '" text-anchor="end">' +
    j.points.toFixed(2) + '</text>' +
    '<text class="' + fleche[1] + '" x="558" y="' + (y + 18) + '">' + fleche[0] +
    '</text>' + mouv;
}

function dessinerClassement(data) {
  var zone = document.getElementById("classement");
  var joueurs = data.joueurs;
  document.getElementById("info-seuil").innerHTML =
    "&mdash; seuil L1/L2 : " + data.seuil.toFixed(2) +
    (data.seuil_est_defaut ? " (d&eacute;faut, d&eacute;cision Kily en attente)" : "");
  if (!joueurs.length) {
    zone.innerHTML = '<p class="vide">Aucun joueur : forces.json vide et aucun capteur porteur de fiche.</p>';
    return;
  }
  var H = 34, PAD = 6, SEP = 26, largeur = 640;
  var maxPts = Math.max.apply(null, joueurs.map(function (j) { return j.points; }).concat([1]));
  var y = PAD, corps = "", sepFaite = false;
  joueurs.forEach(function (j) {
    if (!sepFaite && j.division === "Ligue 2") {
      corps += '<line x1="0" y1="' + (y + 4) + '" x2="' + largeur + '" y2="' +
        (y + 4) + '" stroke="var(--or)" stroke-dasharray="6 4"></line>' +
        '<text class="seuil" x="' + (largeur / 2) + '" y="' + (y + 18) +
        '" text-anchor="middle">&mdash; seuil ' + data.seuil.toFixed(2) +
        ' : au-dessus Ligue 1, en dessous Ligue 2 &mdash;</text>';
      y += SEP; sepFaite = true;
    }
    corps += ligneJoueur(j, y, maxPts);
    y += H;
  });
  zone.innerHTML = '<svg viewBox="0 0 ' + largeur + ' ' + (y + PAD) +
    '" width="100%" role="img" aria-label="classement">' + corps + '</svg>';
}

function dessinerLegendes(murs) {
  var carte = document.getElementById("carte-legendes");
  if (!murs.length) { carte.hidden = true; return; }
  carte.hidden = false;
  document.getElementById("legendes").innerHTML = murs.map(function (m) {
    var pts = m.points == null ? "" : " &middot; " + m.points.toFixed(2) + " pts";
    var src = m.source === "journal" ? "journal" : "plafond";
    return "<span>&#11088; " + esc(m.fiche) + pts + " (" + src + ")</span>";
  }).join("");
}

/* ---------------- vue Bureau ---------------- */
var COULEUR_ETAT = { travaille: "var(--vert)", alerte: "var(--rouge)", repos: "var(--gris)" };
var LIBELLE_ETAT = { travaille: "travaille", alerte: "ALERTE", repos: "au repos" };

function poste(o, i) {
  var x = 12 + i * 158, c = COULEUR_ETAT[o.etat] || "var(--gris)";
  var tache = o.tache ? String(o.tache) : "";
  if (tache.length > 21) tache = tache.slice(0, 20) + "\\u2026";
  return (
    /* halo d'etat */
    '<circle cx="' + (x + 44) + '" cy="50" r="26" fill="' + c + '" opacity="0.14"></circle>' +
    /* personnage : tete + buste */
    '<circle cx="' + (x + 44) + '" cy="44" r="11" fill="' + c + '"></circle>' +
    '<rect x="' + (x + 32) + '" y="57" width="24" height="30" rx="8" fill="' + c + '"></rect>' +
    /* ecran sur le bureau */
    '<rect x="' + (x + 82) + '" y="60" width="36" height="24" rx="3" fill="#0f1420" stroke="var(--ligne)"></rect>' +
    '<rect x="' + (x + 86) + '" y="64" width="28" height="4" rx="2" fill="' + c + '" opacity="0.8"></rect>' +
    '<rect x="' + (x + 86) + '" y="71" width="20" height="4" rx="2" fill="var(--gris)" opacity="0.5"></rect>' +
    /* bureau + pieds */
    '<rect x="' + (x + 16) + '" y="88" width="116" height="10" rx="3" fill="#242e47"></rect>' +
    '<rect x="' + (x + 24) + '" y="98" width="6" height="16" fill="#242e47"></rect>' +
    '<rect x="' + (x + 118) + '" y="98" width="6" height="16" fill="#242e47"></rect>' +
    /* voyant d'etat */
    '<circle cx="' + (x + 124) + '" cy="46" r="6" fill="' + c + '"></circle>' +
    /* etiquettes */
    '<text class="poste-nom" x="' + (x + 74) + '" y="132" text-anchor="middle">' +
    o.code + " &middot; " + esc(o.nom) + '</text>' +
    '<text class="poste-detail" x="' + (x + 74) + '" y="148" text-anchor="middle">' +
    LIBELLE_ETAT[o.etat] + (o.statut ? " [" + esc(o.statut) + "]" : "") + '</text>' +
    '<text class="poste-detail" x="' + (x + 74) + '" y="163" text-anchor="middle">' +
    esc(tache) + '</text>'
  );
}

function dessinerBureau(data) {
  var svg = '<svg viewBox="0 0 644 176" width="100%" role="img" aria-label="bureau">';
  data.organes.forEach(function (o, i) { svg += poste(o, i); });
  document.getElementById("bureau").innerHTML = svg + "</svg>" +
    '<p class="vide">Fen&ecirc;tre : ' + data.fenetre + ' derniers capteurs r&eacute;els. ' +
    'Mapping heuristique v1 : tier CONSEIL/DUO &rarr; 95, note analyse/mesure &rarr; 96, ' +
    'note sante/garde &rarr; 98, d&eacute;faut &rarr; 97.</p>';
}

/* ---------------- polls ---------------- */
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
    .then(function (j) { dessinerClassement(j); dessinerLegendes(j.legendes); })
    .catch(function () {});
}

function pollBureau() {
  fetch("/bureau")
    .then(function (r) { return r.json(); })
    .then(dessinerBureau)
    .catch(function () {});
}

setInterval(function () { pollEvents("capteurs"); pollEvents("lecons"); }, 500);
setInterval(pollClassement, 1000);
setInterval(pollBureau, 1000);
pollEvents("capteurs"); pollEvents("lecons"); pollClassement(); pollBureau();
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
    p.add_argument("--seuil", type=float, default=None,
                   help=f"seuil Ligue 1/Ligue 2 (défaut {SEUIL_DEFAUT} — "
                        f"décision Kily en attente)")
    p.add_argument("--classement", action="store_true",
                   help="afficher le classement en console et sortir (pas de serveur)")
    a = p.parse_args()
    seuil = SEUIL_DEFAUT if a.seuil is None else a.seuil

    if a.classement:
        joueurs = classement(seuil=seuil)
        etiquette = " (défaut)" if a.seuil is None else ""
        print(f"⚽ NEXUS — Ligue (forces = points, seuil L1/L2 {seuil}{etiquette})\n")
        if not joueurs:
            print("📭 Aucun joueur : forces.json vide et aucun capteur porteur de fiche.")
        for j in joueurs:
            fleche = {"promotion": "▲", "relegation": "▼", "stable": "="}[j["tendance"]]
            mouv = {" monte": " ⇧L1", "descend": " ⇩L2"}.get(j["mouvement"] or "", "")
            print(f"   {j['rang']:>2}. [{j['division']}] {j['fiche']:<28} "
                  f"{j['points']:>5.2f} pts  {fleche}{mouv}")
        murs = legendes()
        if murs:
            print("\n⭐ Mur des légendes : " + ", ".join(m["fiche"] for m in murs))
        return

    srv = creer_serveur(a.port, seuil=a.seuil)
    print(f"⚽ Ligue NEXUS — http://127.0.0.1:{a.port}  (lecture seule, Ctrl-C pour arrêter)")
    print(f"   seuil L1/L2 : {srv.seuil}{' (défaut)' if srv.seuil_est_defaut else ''}")
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
