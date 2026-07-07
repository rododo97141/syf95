# Accès distant privé au Bureau live — via Tailscale (pour Kily)

Ce guide explique comment **toi, Kily**, tu rends le Bureau NEXUS live
(`organes/nexus_bureau_live.py`) accessible **depuis tes propres appareils, à
distance, et à toi seul** — sans jamais le publier sur Internet ni l'exposer sur
ton réseau local.

> **Le principe, en une phrase.** Le Bureau n'écoute que sur `127.0.0.1`
> (la loopback de ton Mac) : il n'est donc joignable par **personne** sur le
> réseau, pas même les autres appareils de ton salon. Tailscale crée un tunnel
> privé chiffré entre tes propres appareils (ton *tailnet*), et c'est **par ce
> tunnel seul** que tu atteins la loopback de ton Mac depuis ton téléphone ou ton
> portable, où que tu sois.

Ces étapes sont **manuelles** : tu les exécutes toi-même. Rien ici n'est
scripté, automatisé, ni exécuté par NEXUS. Tailscale est un **outil externe** que
tu installes — ce n'est pas une dépendance Python du projet.

---

## Ce que tu ne changes pas

Rien dans le code. Le Bureau se lie déjà à la loopback par défaut :

- `creer_serveur(...)` a `hote="127.0.0.1"` par défaut ;
- le lancement (`main()`) ne passe jamais d'hôte, et la CLI n'expose que `--port` ;
- **il n'y a pas** d'option `--host` — c'est volontaire, pour qu'on ne puisse pas
  ouvrir le Bureau sur le LAN par accident.

Un test comportemental (`backend/tests/test_bureau_bind_loopback.py`) verrouille
cette garantie : il instancie le vrai serveur et vérifie que la socket est bien
liée à `127.0.0.1`.

---

## Étape 0 — Lancer le Bureau (sur ton Mac)

Depuis le dépôt, sur ton Mac :

```sh
python3 organes/nexus_bureau_live.py
# → sert http://127.0.0.1:8079   (lecture seule)
```

Le port par défaut est **8079** (`PORT_DEFAUT` dans le module). Si tu préfères un
autre port, lance plutôt :

```sh
python3 organes/nexus_bureau_live.py --port 9000
# → sert http://127.0.0.1:9000
```

**Retiens le port que tu utilises** (8079 par défaut, ou celui que tu as choisi
via `--port`). Tu vas devoir le **nommer explicitement** à l'étape 3. Dans la
suite, on écrit `<PORT>` pour ce numéro : remplace-le par **8079** (ou par ta
valeur).

Vérifie tout de suite, sur le Mac lui-même, que ça répond :

```sh
curl http://127.0.0.1:8079        # remplace 8079 par <PORT> si tu as changé
# → doit renvoyer la page HTML du Bureau
```

Laisse ce processus tourner dans un terminal tant que tu veux accéder au Bureau.

---

## Étape 1 — Installer Tailscale sur ton Mac et rejoindre ton tailnet

1. Installe l'app **Tailscale** sur ton Mac (depuis le site officiel de Tailscale
   ou le Mac App Store).
2. Ouvre-la et **connecte-toi avec ton compte** : ton Mac rejoint alors **ton
   tailnet personnel** (le réseau privé de tes propres appareils).
3. Installe aussi Tailscale sur **le ou les appareils depuis lesquels tu veux
   consulter le Bureau à distance** (ton iPhone, ton portable…) et connecte-les
   **au même compte / au même tailnet**.

À la fin de cette étape, tes appareils se voient entre eux dans Tailscale, et
**uniquement** eux (personne d'autre n'est dans ton tailnet).

---

## Étape 2 — (le concept) Ce que fait `tailscale serve`

`tailscale serve` prend un service qui tourne en local sur ton Mac (ici, le
Bureau sur `127.0.0.1:<PORT>`) et le rend joignable **à l'intérieur de ton
tailnet**, à travers le tunnel privé chiffré. Le service reste lié à la
loopback ; Tailscale ne fait que **pont** entre le tunnel et cette loopback.

> Important : on utilise `serve` (privé au tailnet), **pas** `funnel`.
> `funnel` exposerait le service sur l'Internet public — ce n'est **jamais** ce
> qu'on veut ici.

---

## Étape 3 — Ponter le Bureau dans ton tailnet, en nommant le port réel

Sur ton Mac, avec le Bureau lancé (étape 0), lance Tailscale serve **en indiquant
explicitement le port réel du Bureau**. Si tu utilises le port par défaut :

```sh
tailscale serve 8079
```

Si tu as lancé le Bureau sur un autre port (par ex. `--port 9000`), nomme **ce**
port-là :

```sh
tailscale serve 9000
```

> Ne te contente pas de « lancer tailscale serve » : tu dois **nommer le numéro
> de port exact** sur lequel le Bureau écoute (8079 par défaut, ou ta valeur
> `--port`). Un port qui ne correspond pas → rien ne s'affichera.

Tailscale t'indiquera l'URL interne à ton tailnet (basée sur le nom de ton Mac
dans le tailnet, du style `https://<nom-de-ton-mac>.<ton-tailnet>.ts.net/`).
Depuis un autre de **tes** appareils **connecté au même tailnet**, ouvre cette
URL : tu dois voir le Bureau.

Pour arrêter le pont plus tard :

```sh
tailscale serve --https=443 off      # ou : tailscale serve reset
```

(vérifie l'état à tout moment avec `tailscale serve status`.)

---

## Étape 4 — Vérification manuelle finale : prouver que le LAN NE voit PAS le Bureau

C'est l'étape qui prouve que la garantie tient. Tu vas confirmer, de tes propres
mains, que le Bureau **n'est PAS accessible sur ton réseau local** — seulement
via Tailscale.

1. Sur ton Mac, trouve son **IP sur le réseau local (LAN)** — l'adresse de ton
   Wi-Fi/Ethernet domestique, du type `192.168.x.y` ou `10.x.y.z` (ce **n'est
   pas** l'adresse Tailscale en `100.x.y.z`). Par exemple, via *Réglages Système
   → Réseau*, ou :

   ```sh
   ipconfig getifaddr en0        # Wi-Fi (ou en1 selon la machine)
   ```

2. Prends **un autre appareil de ton réseau local** (un appareil branché sur le
   même Wi-Fi que ton Mac) sur lequel **Tailscale n'est PAS installé / PAS
   connecté à ton tailnet** — c'est-à-dire un appareil qui est sur ton LAN mais
   **hors** de ton tailnet.

3. Depuis cet appareil, essaie de joindre le Bureau **directement par l'IP LAN**
   du Mac et le port réel :

   ```sh
   curl http://<IP-LAN-de-ton-Mac>:<PORT>
   # ex. : curl http://192.168.1.42:8079
   ```

4. **Résultat attendu : ÉCHEC.** La commande doit **échouer** ou **rester
   bloquée puis expirer (time out)** — par exemple `Connection refused` ou un
   long silence suivi d'un timeout. Tu ne dois **pas** voir la page du Bureau.

   > C'est **la preuve** que le Bureau n'écoute que sur la loopback de ton Mac :
   > il n'est pas exposé sur le LAN. Le seul chemin pour l'atteindre à distance,
   > c'est le tunnel Tailscale (étape 3), réservé à tes appareils.

5. Contre-épreuve (facultatif mais rassurant) : depuis un appareil **DANS** ton
   tailnet, ouvre l'URL `…ts.net` de l'étape 3 → le Bureau **s'affiche**. Depuis
   l'appareil hors tailnet de l'étape 4, il **ne s'affiche pas**. La différence
   entre les deux, c'est exactement Tailscale.

---

## En cas de souci

- **L'URL `…ts.net` n'affiche rien.** Vérifie que le Bureau tourne bien
  (`curl http://127.0.0.1:<PORT>` sur le Mac), et que le port nommé dans
  `tailscale serve <PORT>` est **exactement** celui du Bureau.
- **`curl` sur l'IP LAN (étape 4) réussit** au lieu d'échouer. C'est anormal :
  le Bureau ne devrait pas être joignable sur le LAN. N'aille pas plus loin —
  signale-le, car cela voudrait dire que le bind n'est plus sur la loopback.
- **Tu ne vois pas tes appareils entre eux dans Tailscale.** Assure-toi qu'ils
  sont tous connectés au **même compte / même tailnet**.

---

## Rappels de périmètre

- **Accès privé-solo.** Ce montage est pour toi seul, via ton tailnet. On ne
  publie pas, on n'ouvre pas au LAN, on n'utilise pas `funnel`.
- **Aucune dépendance Python ajoutée.** Tailscale est un outil externe que tu
  installes toi-même ; le projet n'en dépend pas.
- **Aucun changement fonctionnel du Bureau.** Le bind loopback était déjà le
  défaut ; on n'a fait que le verrouiller par un test et documenter ta procédure.
