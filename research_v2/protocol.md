# Protocole expérimental

Version destinée au gel avant ouverture des étiquettes 2025. Les valeurs numériques sont définies dans [config.json](config.json), les partitions dans [partitions.json](partitions.json). La question est : à budget identique d'étiquettes locales, une allocation tenant compte de la rareté régionale des décès améliore-t-elle la couverture par département et pour la classe mortelle sans réduire excessivement la proportion d'ensembles à une seule étiquette ?

## Domaines et rôles

Trois découpages géographiques sont obtenus en classant les codes départementaux par SHA-256 avec les graines 17, 43 et 89, puis en réservant les vingt premiers. Les listes sont fixées indépendamment des étiquettes et des performances. Un département réservé est absent de tous les rôles sources. Certains territoires ne sont pas présents chaque année ; ce fait est conservé.

Pour une année cible t :

- apprentissage du prédicteur : années 2019 à t−2, régions sources ;
- année t−1, régions sources, séparation par hachage : 25 % validation du prédicteur, 25 % calibration de Platt, 50 % calibration conforme source ;
- année t, régions réservées, séparation par hachage d'identifiant : environ 50 % pool d'adaptation, 50 % test final.

Les accidents sont disjoints entre tous les rôles et les départements sont disjoints entre source et cible. La séparation d'adaptation/test cible est fixée par le sel public `adaptation-v2-20261105`. Les proportions naturelles sont conservées : pas de suréchantillonnage de classe dans calibration ou test.

Les années cibles 2022, 2023 et 2024 servent à la validation glissante du protocole sur les trois découpages. Le petit pilot utilise seulement 2024, découpage 17, budget 500, graine de calibration 11 et les deux modèles. Les méthodes, paramètres et budgets sont ensuite gelés avant d'appeler le chargeur d'étiquettes 2025. L'année 2025 est évaluée une seule fois selon le même protocole ; aucune valeur du test ne sert à choisir une méthode, un modèle, un budget, un seuil ou une rédaction de règle.

## Prédicteurs et probabilités

Deux modèles fixes sont comparés : régression logistique et `HistGradientBoostingClassifier`. Les paramètres sont raisonnables et définis avant l'évaluation complète ; aucun ajustement selon le test n'est réalisé. Chaque modèle est une `Pipeline` : imputation médiane et mise à l'échelle des numériques, imputation constante et one-hot des catégories, puis estimateur. Toutes les transformations sont ajustées sur le rôle apprentissage.

Les probabilités brutes sont recalibrées par une régression logistique de Platt sur le rôle distinct `probability`. Le rôle `tuning` mesure PR-AUC et Brier source sans modifier les paramètres : les deux modèles sont conservés jusqu'au rapport final. Tous les calculs utilisent un seul processus et une seule limite de thread.

## Trois niveaux d'accès au domaine cible

1. **Sans donnée cible** : calibration conforme pooled sur la source ; calibration conforme par classe sur la source.
2. **Caractéristiques cibles sans étiquette** : rapport de densités estimé par une régression logistique de domaine entre apprentissage source et pool d'adaptation cible ; quantile source pondéré avec atome test à l'infini. Les poids sont tronqués entre 0,1 et 10. Cette estimation n'hérite pas de la garantie exacte du rapport connu.
3. **Étiquettes cibles limitées** : calibration par département × classe, avec budget total B∈{500,1000,2000}. Trois allocations sont comparées.

Les budgets ont été choisis avant le test 2025. Ils sont réalisables pour tous les pools historiques et 2025. Le pilot à B=500 a montré le régime parcimonieux où les vingt cellules fatales restent à seuil infini ; 1000 et 2000 permettent d'étudier la transition vers des seuils finis. Cette grille n'a pas été choisie à partir d'une performance 2025.

## Allocations locales

- **Proportionnelle** : quotas proportionnels aux capacités restantes des départements.
- **Uniforme** : mêmes quotas cibles entre départements, avec redistribution lorsqu'une capacité est atteinte.
- **Pilot-variance** : au plus cinq labels tirés dans chaque département ; coût inclus dans B et observations exclues des quantiles. Les taux de décès observés sont lissés avec le taux source et une force de 20, puis le budget restant minimise le critère entier somme 1/(n_g p̂_g).

Après fixation des quotas, les observations de calibration sont tirées uniformément sans remise dans chaque département, avec graines 11, 29 et 47. Une gravité indéterminée consomme le budget mais n'entre pas dans un quantile. Les cellules avec moins de neuf décès connus à α=0,10 incluent toujours la classe mortelle. Le détail mathématique et les hypothèses sont dans [theory.md](theory.md).

## Mesures et stabilité

Mesures primaires : couverture globale, couverture mortelle, couverture de chaque département, taille moyenne, taux d'ensembles à une étiquette et taux d'ensembles vides. Mesures auxiliaires du prédicteur : PR-AUC et score de Brier. Sont également publiés le nombre d'accidents mortels, les cellules à seuil infini et les départements avec moins de vingt décès test.

Les trois découpages géographiques et trois graines d'acquisition donnent neuf répétitions de chaque couple budget–allocation par modèle et année. Les intervalles descriptifs à 95 % rééchantillonnent les départements entiers, 1 000 fois ; ils traitent la dépendance interne au département comme un bloc. Les découpages se recouvrent et ne sont pas des répétitions indépendantes : les écarts entre graines et découpages sont présentés comme stabilité empirique, pas comme erreur standard nationale.

Les comparaisons d'allocation sont appariées par année, découpage, modèle, budget et graine. Un gain doit être examiné conjointement sur couverture, taille et cellules insuffisantes. Une règle qui augmente la couverture uniquement en retournant `{non mortel, mortel}` plus souvent n'est pas déclarée meilleure. L'absence de gain de la règle candidate est conservée.

## Simulation et audit final

Cent répétitions d'un mécanisme connu couvrent : échangeabilité, décalage source–cible, rupture calibration–test et effet commun par région. Elles vérifient l'implémentation et montrent où les garanties disparaissent. La simulation n'est pas ajustée pour reproduire BAAC.

Avant publication : exécuter les tests, vérifier les empreintes et la disjonction des rôles, recalculer les tableaux à partir des CSV agrégés, contrôler l'absence d'identifiants et de chemins personnels, exécuter le notebook de rapport, puis inspecter le diff et l'index Git. Les données brutes, prédictions et suivi local restent exclus.
