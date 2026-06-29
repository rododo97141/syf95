# 98 calibre : fin de la sur-sensibilite + boucle immunitaire prouvee — domaine: nexus / catégorie: reussites
> Créé le 22/06/2026 · Dernière mise à jour le 22/06/2026

## En bref
98 calibre (vrai compte en_attente, seuil redondance 0.5, alerte limites retiree) : ALERTE->VIGILANCE. Boucle immunitaire prouvee : 98 signale -> reconcile -> en_attente 39->0. Reste 1 signal legitime (retour negatif). Sur-sensibilite = point ferme.

## Détail
20/06/2026 : calibrage de 98 (faux positifs traines depuis le debut). 3 corrections : (1) compteur en_attente -> vrai compte des candidats actifs (exclut les tombes promu:true) via fonction vrais_en_attente() ; (2) seuil de redondance jaccard 0.30 -> 0.50 (ne signaler que les vrais doublons : 6 paires -> 2) ; (3) retire l alerte sur les limites (connaitre ses limites n est PAS un dommage - Danger Theory ; info, pas alerte). RESULTAT : verdict 98 passe de ROUGE ALERTE a JAUNE VIGILANCE. Puis BOUCLE IMMUNITAIRE PROUVEE EN DIRECT : 98 signale un vrai backlog (39 en_attente a reconcilier) -> action nexus_reconcile --apply (39 tombes) -> sante amelioree (en_attente 39->0). Il ne reste qu UN signal, LEGITIME : le retour negatif de Kily (analyse-sessions ratee) = seule vraie douleur non digeree. 98 ne crie plus au loup : quand il alerte, c est vrai. Point ouvert ferme (la sur-sensibilite). RESTE backlog : logging automatique des capteurs.

## Source
calibrage 98 20/06/2026
