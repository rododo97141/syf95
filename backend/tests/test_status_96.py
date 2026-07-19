"""Test du tableau de bord (nexus_status) — section 96 (D1, mandat 19/07).

CONTEXTE : nexus_status.main() filtrait la sortie de organes/nexus_96.py avec
grep_from='📡 KPIs'. Ce marqueur n'est émis par 96 QUE dans la branche `if cap:`
(capteurs non vides) — dès que les capteurs sont vides (ou tout simplement
avant ce marqueur conditionnel), aucune ligne ne matche jamais et la section 96
du tableau de bord reste TOUJOURS vide, même quand 96 répond normalement.
96 émet en revanche INCONDITIONNELLEMENT, en toute première ligne :
'🔎 NEXUS-96 — ANALYSTE (voit pour agir)'.

Ce test reproduit fidèlement ce cas (capteurs vides → pas de bloc KPIs dans la
sortie de 96) et prouve que la section 96 rendue par nexus_status N'EST PAS
vide. Avec l'ancien marqueur '📡 KPIs' il échoue (section vide) ; avec le
marqueur corrigé '🔎 NEXUS-96' il passe.
"""
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))              # backend/tests
RACINE = os.path.dirname(os.path.dirname(ICI))                # racine du dépôt
ORGANES = os.path.join(RACINE, "organes")
if ORGANES not in sys.path:
    sys.path.insert(0, ORGANES)


# Sortie RÉALISTE de nexus_96.py quand les capteurs sont vides (aucun bloc
# '📡 KPIs' ni '🪞 Gardien de la réalité', tous deux dans `if cap:`).
FAKE_96_SANS_CAPTEURS = """🔎 NEXUS-96 — ANALYSTE (voit pour agir)
   Confiance : moyenne — 12 fiches, base modeste
   Base observée : 12 fiches · 3 domaines

📊 Répartition par domaine :
     7  finance
     5  organes

🧭 Signaux de contenu :
   réussites/réalisé : 4   limites : 1   insights : 2
   méthodes : 3   architecture : 1   gouvernance : 0

🎯 Recommandations à 95 (96 propose, 95 décide) :
   1. Réussites (4) ≥ limites (1) : dynamique de réalisation saine.
"""

FAKE_SENSE_STATS = "\n".join(["ligne0", "ligne1", "s1", "s2", "s3", "s4", "s5", "s6"])
FAKE_98 = "   VERDICT DE SANTÉ : 🟢 SAIN — l'organisme va bien"


def _charger_status(monkeypatch):
    import nexus_status
    monkeypatch.setattr(nexus_status, "api_up", lambda: True)  # évite nexus_boot.sh
    return nexus_status


def _fake_run_factory():
    class _Resultat:
        def __init__(self, stdout):
            self.stdout = stdout

    def fake_run(cmd, capture_output=True, text=True):
        script = os.path.basename(cmd[1])
        if script == "nexus_96.py":
            return _Resultat(FAKE_96_SANS_CAPTEURS)
        if script == "nexus_sense.py":
            return _Resultat(FAKE_SENSE_STATS)
        if script == "nexus_98.py":
            return _Resultat(FAKE_98)
        return _Resultat("")

    return fake_run


def test_run_avec_le_bon_marqueur_capture_la_section_96(monkeypatch):
    """Preuve directe sur run() : avec le marqueur CORRIGÉ, la section 96 n'est
    pas vide même quand 96 ne produit pas de bloc '📡 KPIs' (capteurs vides)."""
    ns = _charger_status(monkeypatch)
    monkeypatch.setattr(ns.subprocess, "run", _fake_run_factory())

    # L'ANCIEN marqueur ne matche jamais cette sortie réaliste → section vide.
    assert ns.run("nexus_96.py", grep_from="📡 KPIs") == []

    # Le marqueur CORRIGÉ matche la toute première ligne, toujours émise.
    lignes = ns.run("nexus_96.py", grep_from="🔎 NEXUS-96")
    assert lignes, "la section 96 doit être non vide quand 96 répond"
    assert any("Recommandations" in l for l in lignes)


def test_main_rend_une_section_96_non_vide_quand_96_repond(monkeypatch, capsys):
    """Bout en bout sur nexus_status.main() : la section '🔎 ANALYSER — 96' du
    tableau de bord contient du contenu réel (pas seulement son titre)."""
    ns = _charger_status(monkeypatch)
    monkeypatch.setattr(ns.subprocess, "run", _fake_run_factory())

    ns.main()
    out = capsys.readouterr().out
    section = out.split("ANALYSER — 96")[1].split("VEILLER — 98")[0]
    assert section.strip(), "la section 96 du tableau de bord ne doit pas être vide"
    assert "Confiance" in section
