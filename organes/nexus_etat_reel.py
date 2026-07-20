#!/usr/bin/env python3
"""
NEXUS — État réel (page privée de lecture seule)
« Montrer ce qui EST, sans jamais rien exposer de secret. »

Petit serveur HTTP en LECTURE SEULE STRICTE qui affiche l'état réel de NEXUS :
les forces vivantes (forces.json via nexus_force), la vitalité observée
(nexus_vitalite) et, si le module existe, la configuration jeton_seuil
(nexus_jeton_seuil) — mais SEULEMENT les noms de parties et le seuil, JAMAIS
un secret. Reprend le patron déjà PROUVÉ de nexus_bureau_live.py : stdlib
http.server, bind loopback codé en dur, page échappée, aucune dépendance.

Différence assumée avec le Bureau live : pas de websocket ni de poll JS ici.
Le rafraîchissement se fait par une simple balise `<meta http-equiv="refresh">`
toutes les REFRESH_S secondes — la page se recharge, le serveur ne garde
aucun état de session.

nexus_jeton_seuil est un import DÉFENSIF : ce module peut ne pas encore
exister dans le dépôt. S'il est absent, ou si sa lecture échoue pour
n'importe quelle raison, la page affiche un état « config indisponible »
sans jamais lever d'exception — _etat() ne casse JAMAIS l'affichage.

Endpoints (stdlib http.server) :
  - GET /   → la page État réel (200, HTML) ;
  - tout le reste → 404.

Garanties par conception (identiques à nexus_bureau_live.py) :
  - LECTURE SEULE STRICTE : ce module ne fait AUCUNE écriture — ni forces.json,
    ni la mémoire, ni aucun fichier. Il LIT et SERT, point.
  - Le serveur ne se lie QU'À 127.0.0.1, codé en dur dans creer_serveur — pas
    de `--host`, pas de paramètre externe possible. Un accès distant PRIVÉ ne
    passe que par un tunnel comme Tailscale (cf. docs/etat_reel_tailscale.md),
    jamais par une exposition directe du bind.
  - ZÉRO secret affiché : _page_html() ne rend jamais que des noms de parties
    et un seuil ; tout le reste de la config jeton_seuil (s'il y en a) est
    ignoré, jamais transmis au rendu.
  - Front : une page HTML inline, CSS inline, ZÉRO CDN, ZÉRO dépendance,
    ZÉRO JavaScript. Tout texte dynamique est ÉCHAPPÉ (anti-injection).
  - Robustesse : source absente ou en échec → section dégradée, propre, sans
    erreur ; jamais d'exception qui remonte au client.

Usage :
  python3 nexus_etat_reel.py                 # sert http://127.0.0.1:8090
  python3 nexus_etat_reel.py --port 9001
"""
import os
import sys
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import nexus_force     # forces vivantes (forces.json), en LECTURE seule
import nexus_vitalite   # vitalité observée (consultations + capteurs), LECTURE seule

# Import DÉFENSIF : nexus_jeton_seuil peut ne pas encore exister sur ce dépôt.
# Son absence ne doit JAMAIS empêcher la page de se servir — elle affiche
# simplement un état « config indisponible » pour cette section.
try:
    import nexus_jeton_seuil  # noqa: E402  — config jeton_seuil (optionnel)
except ImportError:
    nexus_jeton_seuil = None

PORT_DEFAUT = 8090
# Rafraîchissement simple (balise meta http-equiv), en secondes. Pas de
# websocket, pas de poll JS : la page se recharge toute seule côté navigateur.
REFRESH_S = 30


# --------------------------------------------------------------------------- #
# Échappement HTML (anti-injection) — tout texte dynamique passe par ici
# --------------------------------------------------------------------------- #
def _esc(s):
    """Échappe le texte destiné au HTML : &, <, >, ". Tout ce qui vient d'une
    source lue (forces, vitalité, config) passe OBLIGATOIREMENT par ici."""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# --------------------------------------------------------------------------- #
# Agrégation de l'état réel — LECTURE SEULE, ne lève JAMAIS d'exception
# --------------------------------------------------------------------------- #
def _etat():
    """Agrège l'état réel de NEXUS : forces, vitalité, et config jeton_seuil
    (si disponible). Ne lève JAMAIS d'exception, quoi qu'il arrive en amont —
    chaque source est protégée individuellement, et l'ensemble est en plus
    entouré d'un filet global : un organe absent ou en échec dégrade
    l'affichage, il ne casse jamais la page.

    Pour jeton_seuil, on n'extrait QUE ce qui est montrable : les noms de
    parties et le seuil. Tout le reste de la config (secrets éventuels) est
    ignoré ici même — il n'atteint jamais _page_html()."""
    etat_defaut = {
        "forces": {},
        "vitalite": {},
        "jeton_disponible": False,
        "jeton_seuil": None,
        "jeton_parties": [],
    }
    try:
        try:
            forces = nexus_force._lire_forces_existantes()
        except Exception:
            forces = {}
        if not isinstance(forces, dict):
            forces = {}

        try:
            vitalite = nexus_vitalite.indice_vitalite(nexus_vitalite.mesurer_vitalite())
        except Exception:
            vitalite = {}
        if not isinstance(vitalite, dict):
            vitalite = {}

        jeton_disponible = False
        seuil = None
        parties = []
        if nexus_jeton_seuil is not None:
            try:
                config = nexus_jeton_seuil.lire_config()
            except Exception:
                config = None
            if isinstance(config, dict):
                jeton_disponible = True
                seuil = config.get("seuil")
                for partie in (config.get("parties") or []):
                    nom = partie.get("nom") if isinstance(partie, dict) else partie
                    if isinstance(nom, str) and nom:
                        parties.append(nom)

        return {
            "forces": forces,
            "vitalite": vitalite,
            "jeton_disponible": jeton_disponible,
            "jeton_seuil": seuil,
            "jeton_parties": parties,
        }
    except Exception:
        return etat_defaut


# --------------------------------------------------------------------------- #
# Rendu HTML : une page autonome, sans CDN, sans JS, TOUT échappé
# --------------------------------------------------------------------------- #
_STYLE = """<style>
  :root { --fond:#0f1420; --carte:#171e2e; --ligne:#232c42; --texte:#e8ecf5;
          --sourd:#8b94ab; --or:#e8b93c; --vert:#4fc07a; }
  * { box-sizing:border-box; }
  body { background:var(--fond); color:var(--texte); margin:0; padding:24px;
         font:14px/1.5 system-ui, sans-serif; }
  h1 { margin:0 0 4px; font-size:20px; }
  h2 { margin:0 0 8px; font-size:15px; color:var(--or); }
  p.sous { color:var(--sourd); font-size:12px; margin:0 0 20px; }
  section { background:var(--carte); border:1px solid var(--ligne);
            border-radius:8px; padding:14px 16px; margin-bottom:14px; }
  ul.liste, ul.parties { list-style:none; margin:0; padding:0; }
  ul.liste li, ul.parties li { display:flex; justify-content:space-between;
            padding:4px 0; border-bottom:1px solid var(--ligne); }
  ul.liste li:last-child, ul.parties li:last-child { border-bottom:none; }
  .nom { color:var(--texte); }
  .val { color:var(--or); font-weight:600; }
  .vide { color:var(--sourd); font-style:italic; }
</style>"""


def _page_html(etat=None):
    """Assemble la page État réel depuis _etat() (recalculé à chaque appel si
    non fourni, donc jamais figée). NE DOIT JAMAIS afficher de secret : seules
    des paires (nom, valeur numérique) pour forces/vitalité, et (nom de
    partie, seuil) pour jeton_seuil — rien d'autre n'est rendu, tout est
    échappé."""
    if etat is None:
        etat = _etat()

    forces = etat.get("forces") or {}
    if forces:
        lignes_forces = "".join(
            f'<li><span class="nom">{_esc(nom)}</span>'
            f'<span class="val">x{_esc(f"{val:.4f}")}</span></li>'
            for nom, val in sorted(forces.items(), key=lambda kv: (-kv[1], kv[0]))
        )
    else:
        lignes_forces = '<li class="vide">Aucune force enregistrée.</li>'

    vitalite = etat.get("vitalite") or {}
    if vitalite:
        lignes_vitalite = "".join(
            f'<li><span class="nom">{_esc(nom)}</span>'
            f'<span class="val">{_esc(f"{val:.2f}")}</span></li>'
            for nom, val in sorted(vitalite.items(), key=lambda kv: (-kv[1], kv[0]))
        )
    else:
        lignes_vitalite = '<li class="vide">Aucune vitalité mesurée.</li>'

    if etat.get("jeton_disponible"):
        seuil = etat.get("jeton_seuil")
        seuil_html = _esc(seuil) if seuil is not None else "&mdash;"
        parties = etat.get("jeton_parties") or []
        if parties:
            parties_html = "".join(f'<li><span class="nom">{_esc(p)}</span></li>'
                                    for p in parties)
        else:
            parties_html = '<li class="vide">Aucune partie.</li>'
        bloc_jeton = (
            f'<p>Seuil&nbsp;: <b>{seuil_html}</b></p>'
            f'<ul class="parties">{parties_html}</ul>'
        )
    else:
        bloc_jeton = '<p class="vide">Config indisponible.</p>'

    return (
        '<!DOCTYPE html>\n<html lang="fr">\n<head>\n'
        '<meta charset="utf-8">\n'
        f'<meta http-equiv="refresh" content="{REFRESH_S}">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<title>NEXUS &mdash; &Eacute;tat r&eacute;el</title>\n'
        + _STYLE + '\n</head>\n<body>\n'
        '<h1>NEXUS &mdash; &Eacute;tat r&eacute;el</h1>\n'
        f'<p class="sous">Lecture seule &middot; rafra&icirc;chi automatiquement '
        f'toutes les {REFRESH_S} s.</p>\n'
        '<section><h2>Forces</h2><ul class="liste">'
        + lignes_forces + '</ul></section>\n'
        '<section><h2>Vitalit&eacute;</h2><ul class="liste">'
        + lignes_vitalite + '</ul></section>\n'
        '<section><h2>Jeton / seuil</h2>' + bloc_jeton + '</section>\n'
        '</body>\n</html>\n'
    )


# --------------------------------------------------------------------------- #
# Serveur HTTP (stdlib uniquement — patron nexus_bureau_live) : GET / seul,
# 404 sur tout le reste.
# --------------------------------------------------------------------------- #
class EtatReelHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silencieux : le dashboard ne pollue pas la console
        pass

    def do_GET(self):
        if self.path == "/":
            corps = _page_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(corps)))
            self.end_headers()
            self.wfile.write(corps)
        else:
            corps = b"introuvable"
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(corps)))
            self.end_headers()
            self.wfile.write(corps)


def creer_serveur(port=PORT_DEFAUT, hote="127.0.0.1"):
    """Instancie le serveur sans le lancer (port=0 → port libre, pour tests).
    L'hôte reste CODÉ EN DUR sur 127.0.0.1 par défaut — jamais paramétrable
    depuis l'extérieur (main() ne passe jamais d'hôte, pas de --host en CLI),
    exactement comme nexus_bureau_live.py."""
    return ThreadingHTTPServer((hote, port), EtatReelHandler)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main():
    p = argparse.ArgumentParser(
        description="NEXUS — État réel (page privée, lecture seule)")
    p.add_argument("--port", type=int, default=PORT_DEFAUT)
    a = p.parse_args()

    srv = creer_serveur(a.port)
    print(f"📊 État réel NEXUS — http://127.0.0.1:{a.port}  "
          f"(lecture seule, Ctrl-C pour arrêter)")
    print(f"   forces  : {nexus_force._chemin_forces()}")
    print(f"   refresh : {REFRESH_S} s (meta refresh, pas de JavaScript)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
