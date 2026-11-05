# Environnements de reproduction

Les versions ci-dessous sont celles des interpréteurs ayant effectivement exécuté les expériences. Les versions centrales sont enregistrées dans les métadonnées d'exécution ; l'[inventaire complémentaire](environment_receipt.json) résulte d'un import direct dans chacun des deux interpréteurs.

| Version de l'étude | Python | NumPy | Pandas | SciPy | scikit-learn | threadpoolctl | Matplotlib |
|---|---:|---:|---:|---:|---:|---:|---:|
| research-v2 original | 3.13.5 | 2.1.3 | 2.2.3 | 1.15.3 | 1.6.1 | 3.5.0 | 3.10.0 |
| audit | 3.14.3 | 2.4.2 | 3.0.1 | 1.17.1 | 1.8.0 | 3.6.0 | 3.11.1 |

L'environnement original comprend aussi `nbformat 5.10.4`, `nbclient 0.10.2` et `ipykernel 6.29.5` pour le notebook. L'audit publié n'exécute pas de notebook et ne les ajoute donc pas à son verrou minimal.

- [Verrou research-v2](requirements-research-v2.txt)
- [Verrou audit](requirements-audit.txt)
- Preuves originales : `results/development/execution.json` et `results/final/execution.json`.
- Preuves d'audit : `results/audit/development/execution.json`, `results/audit/corrected_2025/execution.json` et `results/audit/density_reference_execution.json`.

Sous Linux ou macOS, remplacer `py -3.13` et `py -3.14` par les exécutables Python correspondants, puis `Scripts\python` par `bin/python`. Les deux environnements doivent rester séparés : les résultats publiés ne justifient pas de considérer les versions comme interchangeables.
