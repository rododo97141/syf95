# Accès distant privé à l'État réel — via Tailscale (pour Kily)

Ce service (`organes/nexus_etat_reel.py`) suit **exactement** le même montage
privé que le Bureau live : voir **docs/bureau_tailscale.md** pour toutes les
étapes Tailscale communes (installation, `tailscale serve`, vérification
finale que le LAN ne voit rien). Rien de spécifique à Tailscale n'est répété
ici — seule la différence de port compte.

## Ce qui change : le port

- **État réel** écoute par défaut sur le port **`8090`** (`PORT_DEFAUT` dans
  `organes/nexus_etat_reel.py`).
- Le **Bureau** live écoute par défaut sur le port `8079`.

Les deux services peuvent tourner en même temps, sur la même machine, chacun
sur son port :

```sh
python3 organes/nexus_bureau_live.py     # → http://127.0.0.1:8079
python3 organes/nexus_etat_reel.py       # → http://127.0.0.1:8090
```

Quand tu suis les étapes de **docs/bureau_tailscale.md**, remplace simplement
`<PORT>` par **8090** pour l'État réel (au lieu de 8079) — par exemple :

```sh
tailscale serve 8090
```

## Ce qui ne change pas

- Le service ne se lie **que** sur `127.0.0.1` (`creer_serveur(...)` a
  `hote="127.0.0.1"` codé en dur) — pas d'option `--host`, `main()` n'accepte
  que `--port`.
- Lecture seule stricte : aucune écriture, aucun secret affiché (seuls des
  noms de parties et un seuil, le cas échéant).
- La page se rafraîchit toute seule (balise `meta http-equiv="refresh"`
  toutes les `REFRESH_S` secondes) — pas de JavaScript, pas de websocket.
