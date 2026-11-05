# Données BAAC 2019–2025

## Source, licence et fichiers locaux

Les données proviennent du jeu officiel [Bases annuelles des accidents corporels de la circulation routière](https://www.data.gouv.fr/datasets/53698f4ca3a729239d2036df/), diffusé par le ministère de l'Intérieur et l'ONISR. Le catalogue indique la licence `fr-lo`, c'est-à-dire la [Licence Ouverte / Open Licence 2.0](https://www.data.gouv.fr/datasets/licence-ouverte-2-0). Le code de licence et les métadonnées ont été vérifiés le 5 novembre 2026.

`python -m research_v2.download` télécharge Caractéristiques, Lieux et Usagers pour 2019 à 2025, ainsi que les dictionnaires officiels 2020 et 2025. Le [manifeste](data_manifest.json) conserve pour chaque ressource : identifiant data.gouv.fr, URL, date de modification annoncée, date de téléchargement de research-v2, taille, SHA-256 local et résultat de la vérification de l'empreinte du catalogue. Les 23 fichiers représentent 179 987 706 octets. Vingt ressources ont une empreinte de catalogue vérifiée. Les trois ressources 2024 n'en fournissent pas dans les métadonnées consultées ; leur SHA-256 local est enregistré, mais leur identité ne bénéficie donc pas de ce second contrôle.

La date de téléchargement des deux CSV du projet de cours initial reste inconnue. Les données research-v2 ont été téléchargées le 5 novembre 2026 UTC, selon les dates précises du manifeste.

Les CSV et PDF bruts sont stockés dans `data/raw/research_v2/` et exclus de Git. Ils sont redistribuables sous la licence annoncée, mais le dépôt ne les embarque pas : ce choix limite sa taille et évite de publier des lignes contenant notamment adresse partielle et coordonnées. Les tables officielles sont déjà pseudonymisées et le dictionnaire précise que certaines informations sensibles ne sont pas diffusées. Cela n'autorise pas à traiter les lignes comme dépourvues de tout risque de réidentification par recoupement.

## Population et étiquette

L'unité est l'accident corporel enregistré dans BAAC. Il s'agit d'un accident impliquant au moins un véhicule et au moins une victime nécessitant des soins, relevé par les forces de l'ordre. Le modèle estime donc le caractère mortel **parmi ces accidents enregistrés** ; il ne prédit ni la survenue d'un accident ni le risque individuel de décès dans la population.

L'étiquette est construite uniquement avec `Usagers.grav` :

- 1 si au moins un usager enregistré porte le code 2, « tué », défini comme un décès sur le coup ou dans les trente jours ;
- 0 si au moins un usager est enregistré et si toutes les gravités appartiennent aux codes connus 1, 3 ou 4 ;
- indéterminée si aucun décès n'est enregistré et qu'au moins une gravité est inconnue ou invalide, ou si aucun usager n'est disponible.

Un accident avec un décès connu reste mortel même si un autre usager a une gravité inconnue. Les étiquettes indéterminées ne deviennent jamais non mortelles. Elles consomment un label si elles sont tirées dans un budget d'adaptation, puis sont exclues du quantile. Avant 2025, on observe 58 accidents indéterminés en 2021, 230 en 2022 et 116 en 2023. Le dictionnaire officiel indique qu'à partir de 2021 l'ajout d'usagers en fuite entraîne des informations manquantes, dont parfois la gravité.

## Adaptation des schémas

Les trois tables sont jointes par le numéro d'accident, préfixé par l'année afin d'éviter toute collision interannuelle. Les adaptations sont explicites dans [data.py](data.py) :

- la colonne d'identifiant de Caractéristiques s'appelle `Accident_Id` en 2022 et `Num_Acc` les autres années ;
- `id_usager` apparaît dans Usagers à partir de 2021 ;
- les codes numériques de département sont normalisés sur au moins deux chiffres, car 2019 et les années suivantes ne les représentent pas toujours de la même façon ; `2A`, `2B` et les codes ultramarins sont conservés ;
- la présence, l'unicité et la correspondance des identifiants sont contrôlées ; les changements de colonnes attendus sont consignés dans l'audit.

Le dictionnaire 2025 décrit Lieux comme le lieu principal, mais les fichiers observés contiennent plusieurs lignes pour 15 870 accidents en 2023, 15 645 en 2024 et 15 831 en 2025, contre aucune de 2019 à 2022. Prendre arbitrairement la première ligne créerait une règle dépendante de l'ordre. Les catégories de route sont donc agrégées en proportions par accident ; `vma` et `nbv` par médiane, minimum, maximum et part manquante. Cette adaptation conserve l'unité accident mais ne reconstitue pas les combinaisons exactes entre champs d'une même ligne Lieux.

## Variables et disponibilité

Les variables du prédicteur sont limitées à des informations de contexte présentes dans Caractéristiques et Lieux : luminosité, atmosphère, type d'intersection, agglomération, date et heure cycliques, catégorie et régime de route, surface, tracé, infrastructure, limite autorisée et nombre de voies. Les codes inconnus `-1`, les valeurs hors nomenclature et les valeurs numériques non plausibles deviennent manquants ; imputation, encodage et mise à l'échelle sont ajustés seulement sur l'apprentissage.

`Usagers` sert uniquement à l'étiquette. `grav`, les autres caractéristiques des victimes, le type de collision `col`, l'adresse, les coordonnées, la commune, l'identifiant et le département ne sont pas des variables du prédicteur. `dep` sert au découpage et à la calibration régionale. `agg` est ici un contexte observable avant l'issue et non la cible de research-v2 ; il reste une variable candidate, signalée comme potentiellement liée à l'organisation du réseau routier. Les résultats ne sont pas des effets causaux.

Le champ BAAC décrit ce qui a été saisi après intervention. La disponibilité réellement antérieure au décès n'est pas horodatée dans les CSV. L'étude suppose que les champs de contexte retenus seraient disponibles au moment où un accident a déjà été enregistré ; elle ne démontre pas un fonctionnement en temps réel.

## Intégrité et confidentialité des résultats

Les caractéristiques transformées, listes d'identifiants, prédictions et checkpoints sont dans `research_v2/private/` et exclus de Git. Les résultats publics sont agrégés par méthode, année, découpage, graine et département. Ils ne contiennent ni identifiant d'accident, ni adresse, ni coordonnées, ni prédiction individuelle.

La partition 2025 a été calculée à partir des identifiants et des caractéristiques avant lecture de `grav`. Ses effectifs et hachages d'ensembles figurent dans [partitions.json](partitions.json). Les identifiants eux-mêmes restent locaux. Le verrou de [data.py](data.py) interdit de charger les étiquettes 2025 avant la présence du gel de protocole.
