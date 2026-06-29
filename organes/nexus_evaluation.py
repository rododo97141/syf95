#!/usr/bin/env python3
"""
NEXUS — Évaluateur de tâches ouvertes (option A « dur », axiomatique)
« Pour une tâche ouverte, il n'y a pas de valeur scalaire réelle à mesurer. On n'estime pas un réel,
  on AGRÈGE des préférences selon des AXIOMES choisis. » (verdict du conseil à cinq : Claude, Kimi,
  Gemini, ChatGPT + Claude frais)

Les 7 axiomes (proposés ; le Créateur amende en mode créateur) :
  1. COMPARATIF, pas absolu — on agrège des « A vs B », jamais une note « vraie » sur 5.
  2. AVEUGLE + SWAP — A vs B ET B vs A ; on ne garde que les jugements cohérents (anti position/longueur/sycophancy).
  3. PROBABILITÉ CALIBRÉE — sortir P(A≻B) via Bradley-Terry (axiome de calibration).
  4. ROBUSTESSE CLONES / CONDORCET — calculer aussi un classement ordinal (Copeland) ;
     si Bradley-Terry et l'ordinal DIVERGENT → signaler (clones/IIA suspects).
  5. CYCLES = SIGNAL — détecter les cycles de préférence (A≻B≻C≻A) et les RAPPORTER (qualité
     multidimensionnelle), au lieu de les lisser en un scalaire.
  6. BASELINE FORTE — comparer à une IA forte bien promptée (le programme ne l'impose pas, il le RAPPELLE).
  7. HONNÊTETÉ DE SPÉCIFICATION — déclarer : ceci agrège des préférences selon des axiomes, ça ne
     « mesure » pas un réel ; si aucune échelle latente n'existe, Bradley-Terry FABRIQUE un nombre.

Entrée : des comparaisons par paires « gagnant>perdant », séparées par des virgules.
Usage :
  python3 nexus_evaluation.py --paires "A>B,A>B,A>C,B>C,B>C,C>A"
"""
import argparse, math, collections

def parse(s):
    wins = collections.Counter()   # (gagnant, perdant) -> n
    items = set()
    for tok in s.split(","):
        tok = tok.strip()
        if not tok or ">" not in tok:
            continue
        a, b = (x.strip() for x in tok.split(">", 1))
        if not a or not b or a == b:
            continue
        wins[(a, b)] += 1
        items.update([a, b])
    return wins, sorted(items)

def bradley_terry(wins, items):
    """MLE par algorithme de Zermelo. Renvoie des forces normalisées, ou None si non identifiable."""
    W = {i: 0 for i in items}            # victoires totales de i
    N = collections.Counter()            # parties i vs j (non orientées comptées des deux côtés)
    for (i, j), c in wins.items():
        W[i] += c
        N[(i, j)] += c; N[(j, i)] += c
    # garde : un item qui n'a jamais perdu OU jamais gagné => séparation => MLE diverge (axiome 7)
    sépare = [i for i in items if W[i] == 0 or W[i] == sum(N[(i, j)] for j in items if j != i)]
    p = {i: 1.0 for i in items}
    for _ in range(5000):
        new = {}
        for i in items:
            denom = sum(N[(i, j)] / (p[i] + p[j]) for j in items if j != i and N[(i, j)])
            new[i] = W[i] / denom if denom > 0 else p[i]
        s = sum(new.values()) or 1.0
        new = {i: v / s * len(items) for i, v in new.items()}
        if max(abs(new[i] - p[i]) for i in items) < 1e-10:
            p = new; break
        p = new
    return p, sépare

def copeland(wins, items):
    """Classement ordinal robuste (Condorcet) : +1 par paire nette gagnée, -1 par paire nette perdue."""
    score = {i: 0 for i in items}
    for a in items:
        for b in items:
            if a >= b:
                continue
            wa, wb = wins[(a, b)], wins[(b, a)]
            if wa > wb: score[a] += 1; score[b] -= 1
            elif wb > wa: score[b] += 1; score[a] -= 1
    return score

def cycles(wins, items):
    """Détecte les cycles de préférence majoritaire (axiome 5 : signal, pas bruit)."""
    succ = {i: set() for i in items}     # i -> j si i bat j majoritairement
    for a in items:
        for b in items:
            if a != b and wins[(a, b)] > wins[(b, a)]:
                succ[a].add(b)
    trouves = []
    for a in items:                      # cherche les 3-cycles a->b->c->a
        for b in succ[a]:
            for c in succ[b]:
                if a in succ[c] and len({a, b, c}) == 3:
                    cyc = tuple(sorted([a, b, c]))
                    if cyc not in [tuple(sorted(x)) for x in trouves]:
                        trouves.append([a, b, c])
    return trouves

def main():
    p = argparse.ArgumentParser(description="NEXUS — évaluateur axiomatique de tâches ouvertes")
    p.add_argument("--paires", required=True, help="comparaisons « gagnant>perdant », séparées par des virgules")
    g = p.parse_args()
    wins, items = parse(g.paires)
    if len(items) < 2:
        print("🔴 Il faut au moins 2 options et des paires « A>B »."); return

    print("⚖️  NEXUS — ÉVALUATION AXIOMATIQUE (on agrège des préférences, on ne mesure pas un réel)\n")
    n = sum(wins.values())
    print(f"   {len(items)} options · {n} comparaisons par paires\n")

    # --- Bradley-Terry (axiome 3) ---
    pstr, sépare = bradley_terry(wins, items)
    lg = lambda x: 400 * math.log10(max(x, 1e-12))     # clamp : la séparation pousse p→0 (Elo→−∞)
    base = min(lg(pstr[i]) for i in items)
    elo = {i: round(lg(pstr[i]) - base + 1000) for i in items}
    bt_rank = sorted(items, key=lambda i: -elo[i])
    print("   ① Bradley-Terry (probabilité calibrée) :")
    if sépare:
        print(f"      ⚠️ SÉPARATION sur {sépare} (a toujours gagné OU toujours perdu) : le MLE DIVERGE (±∞).")
        print("      → Les Elo ci-dessous ne convergent pas ; Bradley-Terry FABRIQUE un nombre, il ne mesure")
        print("        rien de réel (axiome 7). Sur tâche ouverte transitive nette, se fier à Copeland (②).")
    for i in bt_rank:
        print(f"        {i:4} Elo≈{elo[i]}" + ("  (divergent)" if sépare else ""))
    a, b = bt_rank[0], bt_rank[1]
    pab = pstr[a] / (pstr[a] + pstr[b])
    print(f"      → P({a} ≻ {b}) ≈ {pab:.0%}")

    # --- Copeland (axiome 4) ---
    cope = copeland(wins, items)
    cope_rank = sorted(items, key=lambda i: -cope[i])
    print("\n   ② Copeland (ordinal, robuste aux clones / Condorcet) :")
    print("        " + " > ".join(f"{i}({cope[i]:+d})" for i in cope_rank))

    # --- divergence BT vs ordinal (axiome 4) ---
    if bt_rank != cope_rank:
        print("\n   ⚠️ DIVERGENCE Bradley-Terry vs Copeland : "
              "soupçon de clones/IIA ou de structure non scalaire — ne pas trancher au score seul.")
    else:
        print("\n   ✅ Bradley-Terry et Copeland CONCORDENT sur l'ordre.")

    # --- cycles (axiome 5) ---
    cyc = cycles(wins, items)
    if cyc:
        print("\n   🔁 CYCLES de préférence détectés (SIGNAL, pas bruit — qualité multidimensionnelle) :")
        for c in cyc:
            print(f"        {c[0]} ≻ {c[1]} ≻ {c[2]} ≻ {c[0]}")
        print("      → un score unique ÉCRASERAIT cette structure. La garder telle quelle (fronts de Pareto).")
    else:
        print("\n   🔁 Aucun cycle : un ordre de Condorcet existe (réduction scalaire défendable ici).")

    print("\n   🔒 Rappels d'axiomes : comparaisons en aveugle + swap (anti-biais) · baseline FORTE "
          "(pas d'homme de paille) · ceci agrège des préférences selon des axiomes, ne mesure pas un réel.")

if __name__ == "__main__":
    main()
