# Résultats détaillés

Résultats mesurés sur BAAC 2024, avec une observation par accident. IC percentile à 95 %, 1000 rééchantillonnages appariés des accidents de test ; modèles fixés.

## Aléatoire par accident

Apprentissage : 43,521 accidents ; test : 10,881 accidents. Intersection des identifiants : zéro.

| Variables | Modèle | Balanced accuracy [IC] | Macro-F1 [IC] | ROC-AUC [IC] |
| --- | --- | --- | --- | --- |
| Toutes | Majorité | 0.5000 [0.5000 ; 0.5000] | 0.3847 [0.3810 ; 0.3882] | 0.5000 [0.5000 ; 0.5000] |
| Toutes | Régression logistique | 0.9264 [0.9210 ; 0.9322] | 0.9304 [0.9253 ; 0.9356] | 0.9663 [0.9627 ; 0.9698] |
| Toutes | Forêt aléatoire | 0.9306 [0.9251 ; 0.9359] | 0.9339 [0.9289 ; 0.9388] | 0.9711 [0.9679 ; 0.9743] |
| vma + catr | Majorité | 0.5000 [0.5000 ; 0.5000] | 0.3847 [0.3810 ; 0.3882] | 0.5000 [0.5000 ; 0.5000] |
| vma + catr | Régression logistique | 0.9246 [0.9193 ; 0.9304] | 0.9287 [0.9236 ; 0.9339] | 0.9545 [0.9499 ; 0.9589] |
| vma + catr | Forêt aléatoire | 0.9258 [0.9205 ; 0.9314] | 0.9297 [0.9246 ; 0.9349] | 0.9581 [0.9538 ; 0.9623] |
| Sans vma/catr | Majorité | 0.5000 [0.5000 ; 0.5000] | 0.3847 [0.3810 ; 0.3882] | 0.5000 [0.5000 ; 0.5000] |
| Sans vma/catr | Régression logistique | 0.7498 [0.7418 ; 0.7582] | 0.7580 [0.7501 ; 0.7666] | 0.8483 [0.8406 ; 0.8558] |
| Sans vma/catr | Forêt aléatoire | 0.7589 [0.7505 ; 0.7671] | 0.7687 [0.7602 ; 0.7772] | 0.8675 [0.8602 ; 0.8745] |

## Départements réservés

Apprentissage : 43,242 accidents ; test : 11,160 accidents. Intersection des identifiants : zéro.

| Variables | Modèle | Balanced accuracy [IC] | Macro-F1 [IC] | ROC-AUC [IC] |
| --- | --- | --- | --- | --- |
| Toutes | Majorité | 0.5000 [0.5000 ; 0.5000] | 0.3921 [0.3886 ; 0.3950] | 0.5000 [0.5000 ; 0.5000] |
| Toutes | Régression logistique | 0.9450 [0.9398 ; 0.9492] | 0.9488 [0.9444 ; 0.9526] | 0.9760 [0.9727 ; 0.9790] |
| Toutes | Forêt aléatoire | 0.9474 [0.9424 ; 0.9518] | 0.9513 [0.9467 ; 0.9552] | 0.9788 [0.9757 ; 0.9815] |
| vma + catr | Majorité | 0.5000 [0.5000 ; 0.5000] | 0.3921 [0.3886 ; 0.3950] | 0.5000 [0.5000 ; 0.5000] |
| vma + catr | Régression logistique | 0.9411 [0.9360 ; 0.9460] | 0.9455 [0.9410 ; 0.9498] | 0.9639 [0.9595 ; 0.9677] |
| vma + catr | Forêt aléatoire | 0.9435 [0.9383 ; 0.9480] | 0.9477 [0.9432 ; 0.9517] | 0.9649 [0.9604 ; 0.9689] |
| Sans vma/catr | Majorité | 0.5000 [0.5000 ; 0.5000] | 0.3921 [0.3886 ; 0.3950] | 0.5000 [0.5000 ; 0.5000] |
| Sans vma/catr | Régression logistique | 0.7562 [0.7479 ; 0.7647] | 0.7645 [0.7564 ; 0.7729] | 0.8493 [0.8418 ; 0.8562] |
| Sans vma/catr | Forêt aléatoire | 0.7619 [0.7535 ; 0.7700] | 0.7713 [0.7631 ; 0.7797] | 0.8708 [0.8641 ; 0.8772] |

## Différences appariées

Différence = premier modèle moins second, sans ajustement pour comparaisons multiples.

| Test | Comparaison | Métrique | Différence | IC à 95 % |
| --- | --- | --- | --- | --- |
| Aléatoire par accident | all/forest - all/logistic | balanced_accuracy | +0.0042 | [+0.0015 ; +0.0068] |
| Aléatoire par accident | all/forest - all/logistic | macro_f1 | +0.0035 | [+0.0009 ; +0.0061] |
| Aléatoire par accident | all/forest - all/logistic | roc_auc | +0.0048 | [+0.0028 ; +0.0068] |
| Aléatoire par accident | all/forest - road_only/forest | balanced_accuracy | +0.0047 | [+0.0026 ; +0.0067] |
| Aléatoire par accident | all/forest - road_only/forest | macro_f1 | +0.0042 | [+0.0022 ; +0.0060] |
| Aléatoire par accident | all/forest - road_only/forest | roc_auc | +0.0131 | [+0.0107 ; +0.0156] |
| Aléatoire par accident | all/forest - without_road/forest | balanced_accuracy | +0.1716 | [+0.1620 ; +0.1807] |
| Aléatoire par accident | all/forest - without_road/forest | macro_f1 | +0.1652 | [+0.1562 ; +0.1746] |
| Aléatoire par accident | all/forest - without_road/forest | roc_auc | +0.1036 | [+0.0971 ; +0.1102] |
| Départements réservés | all/forest - all/logistic | balanced_accuracy | +0.0024 | [-0.0005 ; +0.0053] |
| Départements réservés | all/forest - all/logistic | macro_f1 | +0.0025 | [-0.0005 ; +0.0052] |
| Départements réservés | all/forest - all/logistic | roc_auc | +0.0028 | [+0.0009 ; +0.0047] |
| Départements réservés | all/forest - road_only/forest | balanced_accuracy | +0.0040 | [+0.0017 ; +0.0063] |
| Départements réservés | all/forest - road_only/forest | macro_f1 | +0.0035 | [+0.0014 ; +0.0056] |
| Départements réservés | all/forest - road_only/forest | roc_auc | +0.0139 | [+0.0112 ; +0.0167] |
| Départements réservés | all/forest - without_road/forest | balanced_accuracy | +0.1855 | [+0.1766 ; +0.1943] |
| Départements réservés | all/forest - without_road/forest | macro_f1 | +0.1799 | [+0.1711 ; +0.1887] |
| Départements réservés | all/forest - without_road/forest | roc_auc | +0.1081 | [+0.1018 ; +0.1141] |

Voir `paired_differences.csv` pour toutes les comparaisons, `confusion_matrices.json` pour les 18 matrices et `run_metadata.json` pour l’environnement et les empreintes.

Les IC conditionnent sur les modèles ajustés et le découpage retenu. Ils ne couvrent pas la variabilité du réentraînement ni celle d’autres départements réservés ; les accidents peuvent rester spatialement dépendants.
