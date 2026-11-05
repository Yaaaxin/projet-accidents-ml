# Protocole fixé avant entraînement

## Question

Classification du contexte d’agglomération des accidents : biais d’évaluation, dépendance aux caractéristiques routières et généralisation géographique.

Dans BAAC 2024, la performance et l’avantage éventuel de la forêt sur la régression logistique persistent-ils après isolation des accidents, retrait de `vma` et `catr`, puis transfert vers des départements absents de l’apprentissage ? Il s’agit de classification descriptive conditionnelle à un accident enregistré, pas de risque d’accident ni de causalité.

## Unité et lieux multiples

Une ligne de `caract` correspond à un accident ; `Num_Acc` doit être unique. Les 70 248 lignes de `lieux` couvrent 54 402 accidents et ne sont pas des doublons exacts. La documentation officielle décrit le lieu principal, mais ne fournit pas de règle permettant de sélectionner la première de plusieurs lignes. Nous ne supposons pas que l’ordre du CSV désigne le lieu principal.

Choix : représentation symétrique de l’ensemble des descriptions de lieux, une ligne par accident. Pour chaque catégorie routière (`catr`, `circ`, `surf`, `plan`, `infra`, `situ`), calculer la proportion de chaque modalité et de la modalité inconnue parmi les lignes de l’accident. Pour `vma` et `nbv`, calculer médiane, minimum, maximum et proportion manquante. Ces résumés décrivent les valeurs renseignées, pas une vitesse réellement pratiquée ni un lieu principal reconstruit. Ils sont invariants à l’ordre des lignes. Chaque accident reçoit le même poids, à l’apprentissage, au calcul des scores et au bootstrap. Aucun poids de classe supplémentaire.

Limites : les proportions dépendent du nombre de descriptions enregistrées, dont le processus n’est pas documenté ; la médiane peut être une valeur intermédiaire non observée. Min/max et parts catégorielles conservent une partie de l’hétérogénéité mais pas la correspondance entre toutes les caractéristiques d’un même lieu.

## Nettoyage déterministe

Référence : ONISR, description BAAC 2005–2024, 21 octobre 2025 (lien dans `data/manifest.json`). Les transformations suivantes ne sont pas estimées à partir du test.

- Lire les codes comme chaînes, supprimer les espaces. `-1`, vide, point, `#VALEURMULTI` et codes hors nomenclature deviennent manquants. Ne pas remplacer tous les zéros : `infra=0` et `situ=0` sont des modalités documentées.
- `lum`, `atm`, `col` sont catégoriels ; les catégories routières sont représentées par des proportions suivant une nomenclature fixe, sans ordre numérique artificiel.
- `vma` : conserver les nombres dans ]0,130], les autres sont manquants. C’est une règle de plausibilité de cette étude, non une correction certaine de chaque erreur ; ne jamais transformer 900 en 90 par supposition. `nbv` : entier dans [1,20], sinon manquant ; borne 20 déclarée comme choix de plausibilité.
- Construire la date 2024 ; coder heure, mois et jour du mois par sinus/cosinus ; jour de semaine catégoriel. Une date/heure invalide devient manquante.
- L’imputation médiane des résumés numériques, le remplissage modal des catégories, OneHotEncoder et StandardScaler sont ajustés uniquement sur l’apprentissage dans un Pipeline.
- `agg` sert uniquement à la cible (`2 → 1`, `1 → 0`) ; `Num_Acc` uniquement aux contrôles ; `dep` uniquement au découpage géographique. Adresse, commune, coordonnées et année constante exclus des prédicteurs.

## Découpages figés

- **Aléatoire par accident** : 20 % test, stratification de la cible, graine 42, table accident triée par identifiant.
- **Géographique** : tous les accidents des 22 départements/territoires suivants sont réservés au test : `07, 08, 27, 29, 30, 32, 46, 51, 61, 62, 63, 66, 67, 73, 79, 80, 85, 89, 92, 94, 975, 986`.
- Liste tirée avant tout entraînement : `default_rng(20261104).choice(sorted(dep_uniques), ceil(0.2 * 107), replace=False)`. Liste enregistrée dans `config/experiment.json` et non resélectionnée selon les résultats. Les territoires à très faible effectif limitent l’interprétation territoriale.
- Vérifier intersection vide des identifiants pour les deux protocoles et intersection vide des départements pour le second. Aucune sélection de seuil sur le test : seuil 0,5.
- Ancien découpage par ligne : reconstruire seulement le chevauchement avec graine 42, sans présenter ses anciens scores comme validés ni attribuer toute différence future à la seule fuite (prétraitement et unité changent aussi).

## Comparaisons

Sur exactement les mêmes accidents de test : trois ensembles (`all`, `road_only`, `without_road`) × trois modèles × deux découpages = 18 évaluations.

- `all` : descendants des 14 variables initiales, avec jour de semaine dérivé de la date.
- `road_only` : résumés de `vma` et proportions de `catr` seulement.
- `without_road` : tous les autres descendants, sans `vma` ni `catr` ni leurs indicateurs manquants.
- Baseline : DummyClassifier, classe majoritaire d’apprentissage.
- Régression logistique : C=1, lbfgs, max_iter=3000, tol=1e-6 ; imputation, encodage et mise à l’échelle dans Pipeline. Un avertissement de convergence invalide l’exécution.
- Forêt : 300 arbres, profondeur maximale 18, minimum 5 observations par feuille, max_features=sqrt, graine 20261104, exécution séquentielle (`n_jobs=1`). Le passage de quatre tâches à une seule répond à une restriction de création de files parallèles sous Windows ; aucun paramètre statistique ni découpage n’a changé.
- Pas de recherche d’hyperparamètres. Les paramètres et ablations sont fixés avant les scores.

## Incertitude et sorties

Balanced accuracy, macro-F1, ROC-AUC, matrice de confusion (lignes vraies, colonnes prédites ; ordre 0,1). IC percentile 95 % sur 1 000 rééchantillonnages d’accidents avec remise, graine 20261105. Les tirages sont appariés entre modèles et ablations d’un même test ; enregistrer aussi les IC des différences forêt moins logistique, et all moins without_road/road_only. Une itération sans les deux classes est ignorée et comptée.

Ces IC conditionnent sur modèles et découpage fixés ; ils n’incluent ni variabilité du réentraînement ni variabilité du choix des départements, et supposent les accidents indépendants. Ils ne corrigent pas toute dépendance spatiale.

Publier uniquement des résultats agrégés. Conserver identifiants de découpage et prédictions accident par accident dans `results/private/`, exclu de Git. Enregistrer hachages des données, du protocole, de la configuration et du code, versions des bibliothèques, tailles et contrôles.
