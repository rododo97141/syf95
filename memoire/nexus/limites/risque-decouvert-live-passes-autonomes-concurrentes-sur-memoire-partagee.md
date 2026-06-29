# Risque decouvert live : passes autonomes concurrentes sur memoire partagee — domaine: nexus / catégorie: limites
> Créé le 21/06/2026 · Dernière mise à jour le 21/06/2026

## En bref
Pendant ma passe 22h18, une AUTRE passe 'decouvre-toi' ecrivait en meme temps (fiche youtube/veille apparue). Race possible sur la memoire partagee, sans verrou.

## Détail
Pendant le run 22h18, un fichier en_attente que je n'ai pas cree est apparu (20260621-022218-youtube-communaute-aios-active, domaine nexus/veille) et le compteur structure a bouge plus que mes 2 ajouts. Conclusion : plusieurs passes autonomes 'decouvre-toi' peuvent tourner en CONCURRENCE sur le meme magasin memoire (memoire_data sur le mount), sans verrou ni namespace par run. Risques : ecritures entrelacees, compteurs incoherents, deux runs qui se marchent dessus. Bon point : nexus_reconcile.py a correctement LAISSE INTACT le candidat de l'autre run (pas de match en structure -> non touche), donc le garde-fou 'ne tomber que ce qui est deja subsume' protege contre l'effacement du travail d'un run voisin. Piste d'amelioration : namespace par run (multi-scope memory deja note comme piste AIOS) ou simple verrou fichier sur les ecritures.

## Source
observation live 20/06/2026 22h18
