# Calibration d'accidents mortels sous décalages spatio-temporels

Projet de cours de **M1 mathématiques** réalisé par **[Yaaaxin](https://github.com/Yaaaxin)** et **[zhailucc](https://github.com/zhailucc)** à partir des données françaises BAAC. La branche `research-v2` prolonge le projet initial par une étude méthodologique :

> Comment répartir un budget limité d'étiquettes locales, après transfert vers une nouvelle année et de nouveaux départements, pour couvrir la classe mortelle et les régions sans perdre tout pouvoir discriminant ?

L'étude combine des méthodes existantes de prédiction conforme, une validation spatio-temporelle et une hypothèse d'allocation. Elle ne revendique pas d'innovation algorithmique. Elle classe le caractère mortel **parmi les accidents corporels déjà enregistrés** ; elle ne prédit ni la survenue d'un accident ni une cause de décès.

## Trois résultats

Les chiffres de cette page proviennent tous de l'[audit corrigé](research_v2/results/audit/report.md). Ils moyennent les trois découpages géographiques et les deux modèles ; les méthodes locales ajoutent trois tirages de calibration. Les analyses 2025 de l'audit sont postérieures à la première publication du test.

1. **La couverture marginale masque la classe mortelle.** La calibration pooled couvre environ 90 % des accidents mais aucun décès, y compris dans le contrôle de même domaine. Le transfert n'est donc pas nécessaire pour produire ce zéro.
2. **La correction des densités vient du changement de distribution de référence.** Avec les mêmes probabilités mises en cache et le même environnement, passer de `fit` à `tuning` augmente la couverture pondérée 2025 de `0,01608`. L'écart attribuable conjointement aux versions logicielles et au correctif de compatibilité n'est que de `0,00005`. La couverture mortelle reste nulle.
3. **La protection régionale coûte de l'ambiguïté.** À budget 2 000, la calibration uniforme par classe atteint une couverture mortelle macro-départementale de `0,892` avec une taille de `1,522`; le croisement département × classe atteint `0,966`, mais avec une taille de `1,832`. La règle pilot–variance n'apporte pas de gain stable.

| Méthode 2025 corrigée | Budget | Couverture | Mortelle macro-départementale | Taille | Singleton |
|---|---:|---:|---:|---:|---:|
| Source pooled | 0 | 0,907 | 0,000 | 0,953 | 0,953 |
| Source pondérée, référence `tuning` | 0 | 0,903 | 0,000 | 0,949 | 0,949 |
| Source par classe | 0 | 0,910 | 0,907 | **1,524** | **0,476** |
| Locale uniforme par classe | 2 000 | 0,933 | 0,892 | **1,522** | **0,478** |
| Locale proportionnelle, département × classe | 2 000 | 0,904 | **0,984** | 1,812 | 0,188 |
| Locale uniforme, département × classe | 2 000 | 0,903 | 0,966 | 1,832 | 0,168 |
| Locale pilot–variance, département × classe | 2 000 | 0,902 | 0,965 | 1,836 | 0,164 |

![Budget, couverture régionale et taille des ensembles](research_v2/results/audit/figures/tradeoff_2025_corrected.png)

Le [rapport original](research_v2/results/report.md), son [gel](research_v2/freeze.json) et ses résultats restent inchangés. Le [protocole d'audit](research_v2/audit_protocol.md), son [gel séparé](research_v2/audit_freeze.json), la [comparaison de densités appariée](research_v2/results/audit/tables/density_reference_versions.csv) et le [rapport corrigé](research_v2/results/audit/report.md) assurent la traçabilité des corrections.

## Méthode

L'étiquette accident est construite uniquement à partir de `Usagers.grav` : au moins une personne enregistrée tuée dans les trente jours. Une gravité inconnue n'est jamais assimilée à une absence de décès. Usagers n'alimente aucune variable du prédicteur.

Les variables décrivent le contexte de l'accident : temps, luminosité, atmosphère, agglomération, intersection et caractéristiques routières. Identifiants, département, adresse, coordonnées, type de collision et informations sur les victimes sont exclus du modèle. Les lignes multiples de Lieux sont agrégées à l'accident sans choisir arbitrairement la première.

Deux prédicteurs fixes sont comparés : régression logistique et gradient boosting sur histogrammes. Imputation, encodage et standardisation sont ajustés dans une `Pipeline` sur l'apprentissage uniquement. Une calibration de Platt distincte produit les probabilités. Les trois situations d'accès à la cible sont : aucune donnée cible, caractéristiques cibles sans étiquette, puis 500, 1 000 ou 2 000 étiquettes locales.

La calibration conforme utilise α=0,10. Un quantile département × classe n'est fini qu'à partir de neuf observations de cette classe. Le pilot de cinq labels par département est payé dans le budget et n'est pas réutilisé dans les quantiles. Les hypothèses, la dérivation du critère substitutif et ses limites sont détaillées dans [theory.md](research_v2/theory.md).

## Reproduire

Les deux environnements sont séparés et verrouillés dans [requirements-research-v2.txt](research_v2/requirements-research-v2.txt) et [requirements-audit.txt](research_v2/requirements-audit.txt). Les versions proviennent des métadonnées des exécutions publiées ; voir [environments.md](research_v2/environments.md). Tous les calculs sont séquentiels avec `n_jobs=1`.

```bash
# research-v2 original — Python 3.13.5
py -3.13 -m venv .venv-research-v2
.venv-research-v2\Scripts\python -m pip install -r research_v2\requirements-research-v2.txt
.venv-research-v2\Scripts\python -m research_v2.download
.venv-research-v2\Scripts\python -m research_v2.data
.venv-research-v2\Scripts\python -m research_v2.simulation
.venv-research-v2\Scripts\python -m research_v2.run pilot
.venv-research-v2\Scripts\python -m research_v2.run development
.venv-research-v2\Scripts\python -m research_v2.run final
.venv-research-v2\Scripts\python -m research_v2.report

# audit — Python 3.14.3, après les commandes de préparation ci-dessus
py -3.14 -m venv .venv-audit
.venv-audit\Scripts\python -m pip install -r research_v2\requirements-audit.txt
.venv-audit\Scripts\python -m unittest discover -s tests -v
.venv-audit\Scripts\python -m research_v2.audit development
.venv-audit\Scripts\python -m research_v2.audit_simulation
.venv-audit\Scripts\python -m research_v2.audit corrected_2025
.venv-audit\Scripts\python -m research_v2.density_reference
.venv-audit\Scripts\python -m research_v2.audit_report
.venv-audit\Scripts\python -m research_v2.audit_pack pack
.venv-audit\Scripts\python -m research_v2.audit_validate
```

Les exécutions écrivent des checkpoints dans `research_v2/private/` afin de reprendre après interruption. Ce répertoire, les données brutes et les prédictions par accident sont exclus de Git. Les résultats publics sont agrégés. Les empreintes des entrées et sorties de référence figurent dans le manifeste, le gel et les métadonnées d'exécution.

Les grands CSV de l'amendement sont publiés en `csv.gz`. `audit_pack` vérifie que leur décompression, et la concaténation chronologique des trois partitions départementales, redonnent exactement les SHA-256 du gel.

Le notebook [03_research_v2.ipynb](notebooks/03_research_v2.ipynb) présente en français le problème, le protocole et les résultats. Il lit les tableaux agrégés ; les commandes ci-dessus refont les modèles.

## Documents

- [Comparaison de dix publications primaires](research_v2/literature.md), avec vérification du DOI `10.1080/15389588.2025.2538725`.
- [Protocole expérimental](research_v2/protocol.md), [données et intégrité](research_v2/data.md), [dérivation mathématique](research_v2/theory.md).
- [Audit avant gel](research_v2/results/data_audit_before_freeze.json), [simulation contrôlée](research_v2/results/simulation_summary_clean.csv), [résultats régionaux 2025](research_v2/results/final/departments.csv).
- [Amendement d'audit](research_v2/audit_protocol.md), [gel de l'amendement](research_v2/audit_freeze.json), [rapport corrigé](research_v2/results/audit/report.md) et [métriques 2025 corrigées](research_v2/results/audit/corrected_2025/metrics.csv).
- [Environnements verrouillés](research_v2/environments.md) et [comparaison appariée des références de densité](research_v2/results/audit/tables/density_reference_versions.csv).

## Données, licence et limites

Les 21 CSV proviennent du jeu officiel [BAAC 2005–2025](https://www.data.gouv.fr/datasets/53698f4ca3a729239d2036df/), sous [Licence Ouverte 2.0](https://www.data.gouv.fr/datasets/licence-ouverte-2-0). Les données brutes ne sont pas publiées dans ce dépôt. Le [manifeste research-v2](research_v2/data_manifest.json) contient les URL, identifiants de ressource, tailles, SHA-256 et contrôles d'empreinte disponibles. La date de téléchargement des données du projet initial demeure inconnue ; celles de research-v2 sont enregistrées précisément.

Les résultats 2025 décrivent une adaptation rétrospective au sein d'une même année. Ils supposent une stabilité entre pool d'adaptation et test qui n'est pas démontrée et ne garantissent pas un transfert vers 2026. Quarante-deux des 58 couples découpage–département ont moins de vingt accidents mortels dans le test ; les couvertures locales sont donc souvent imprécises. La dépendance spatiale est examinée par rééchantillonnage des départements, sans être éliminée.

BAAC est une base administrative brute, avec erreurs de saisie et usagers potentiellement manquants. Les résultats ne couvrent pas les décès non enregistrés ni les accidents dont la gravité reste indéterminée. Aucune importance ou association prédictive n'est interprétée comme cause d'un accident ou d'un décès.

## Auteurs / Contributions

| Auteur | Contributions établies par les matériaux du dépôt |
|---|---|
| [Yaaaxin](https://github.com/Yaaaxin) | Coauteur du projet de cours ; création du dépôt et du commit initial. |
| [zhailucc](https://github.com/zhailucc) | Coauteur du projet de cours et collaborateur du dépôt. |

Le notebook initial ne documente pas une répartition individuelle plus précise. Le projet original est donc présenté comme un travail commun ; aucune attribution détaillée n'est inventée pour research-v2.

## Version initiale conservée

Le premier sujet, « Classification du contexte d'agglomération des accidents », reste entièrement disponible : [notebook original](notebooks/01_accidents_ml.ipynb), [extension méthodologique v1](notebooks/02_methodologie.ipynb), [résultats v1](results/summary.md), [protocole v1](docs/protocol.md) et [note historique](docs/original-project.md). L'historique Git conserve le commit v1 sur `main` ; research-v2 est développé sur une branche distincte.

La licence des données ne s'étend pas automatiquement au code et aux documents du projet ; aucune licence de code n'est attribuée unilatéralement aux contributions communes.
