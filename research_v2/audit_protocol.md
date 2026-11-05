# Amendement d'audit de research-v2

Cet amendement est postérieur à la publication du test BAAC 2025 dans le commit [`3523444`](https://github.com/Yaaaxin/projet-accidents-ml/commit/35234446432e71b877728ab59ed15685f1e4fd7e). Le gel original, ses résultats et son rapport restent inchangés. Les méthodes ajoutées ici sont choisies et vérifiées avec les cibles 2022–2024. Toute valeur 2025 produite par cet amendement est signalée comme **correction** ou **analyse postérieure**, jamais comme validation préenregistrée.

## Correction du rapport de densités

L'implémentation originale ajuste le classifieur de domaine avec `frames["fit"]`, constitué d'années antérieures, puis applique ses rapports à `frames["conformal"]`, issu de la dernière année source. Le numérateur cible et le dénominateur source ne décrivent donc pas exactement les distributions auxquelles le quantile pondéré est appliqué.

La correction ajuste le classifieur de domaine avec `frames["tuning"]` et le pool d'adaptation cible. `tuning` et `conformal` sont deux partitions par hachage, disjointes, de la même année et des mêmes départements sources. L'estimation du rapport est donc indépendante des scores conformes auxquels elle s'applique et sa distribution source est alignée par construction. Les caractéristiques cibles sont utilisées sans étiquette. Les poids restent tronqués entre 0,1 et 10 ; la garantie exacte du rapport connu ne s'applique toujours pas à ces poids estimés.

## Décomposition de la calibration locale

Pour chaque politique, budget, graine et scénario, les mêmes accidents acquis alimentent trois calibrations :

1. un quantile local pooled ;
2. deux quantiles locaux conditionnels à la classe ;
3. des quantiles département × classe.

Les hachages des ensembles acquis sont enregistrés afin de vérifier l'identité des échantillons. Le premier contrôle teste si la couverture mortelle nulle apparaît déjà sans décalage calibration–test. Le deuxième sépare l'effet d'étiquettes locales de celui d'une granularité régionale plus fine.

## Mesure régionale

L'objectif candidat donne le même poids aux départements. L'évaluation primaire de ce mécanisme ajoute donc la moyenne non pondérée des couvertures mortelles départementales parmi les départements ayant au moins un décès test, ainsi que minimum, déciles, quartiles, médiane, maximum et effectifs mortels correspondants. La couverture mortelle agrégée reste publiée, mais ne décide plus seule du bénéfice. Couverture globale, taille moyenne et taux de singletons sont toujours présentés ensemble.

## Décomposition du pilot

Trois références oracle sont limitées aux années historiques et aux simulations. Elles utilisent toutes les étiquettes du pool d'adaptation pour expliquer un mécanisme et sont explicitement non déployables :

- `oracle_variance_costed` connaît les taux régionaux mais retire et exclut le même pilot que la règle candidate : comparaison de qualité d'estimation à coût égal ;
- `oracle_variance` connaît les taux et consacre tout le budget à la calibration : comparaison du coût du pilot ;
- `oracle_equal_fatal` connaît les taux et alloue approximativement selon 1/p_g afin d'égaliser le nombre attendu de décès, alors que l'objectif de variance conduit approximativement à 1/√p_g : contrôle de l'adéquation au seuil fini de neuf décès.

Les taux oracle sont les fréquences complètes du pool historique, lissées par `(d_g+0,5)/(n_g+1)` pour éviter une division par zéro dans les très petits départements. Le taux brut reste publié. Le nombre attendu de cellules sous neuf décès est calculé avec une approximation binomiale ; ce diagnostic n'est pas une garantie pour un échantillonnage sans remise.

## Simulation amendée

La simulation distingue désormais :

- `shared_region_effect` : un même intercept aléatoire régional agit dans adaptation et test ; les accidents sont corrélés marginalement, mais la loi conditionnelle régionale est stable ;
- `changed_region_effect` : les intercepts d'adaptation et de test sont indépendants ; la loi conditionnelle change entre les deux ensembles.

Les scénarios échangeable, décalage de covariables et rupture conceptuelle globale sont conservés séparément. Les contrôles locaux sur le même échantillon et les trois références oracle sont évalués avec 100 répétitions. Aux budgets 120 et 600 s'ajoute un budget 2 400 propre à la simulation : ce point de pression ne représente pas le budget BAAC, mais rend assez de cellules mortelles finies pour révéler une éventuelle rupture adaptation–test, au lieu de confondre couverture et ensembles systématiquement complets.

## Ordre d'exécution

1. Tests unitaires et expériences 2022–2024.
2. Lecture des diagnostics historiques et fixation de cet amendement, sans résultat 2025 corrigé.
3. Création d'un gel d'audit contenant les empreintes du code, de la configuration et des résultats historiques.
4. Exécution 2025 une seule fois avec les méthodes déjà listées ; aucun oracle historique n'est présenté comme méthode 2025.
5. Rapport séparant résultats maintenus, corrigés et nouveaux contrôles postérieurs.
