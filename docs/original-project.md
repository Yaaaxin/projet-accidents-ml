# Projet de cours initial et extension

Le projet M1 initial compare une régression logistique et une forêt aléatoire pour classer les accidents en/hors agglomération. Son implémentation est conservée dans [`notebooks/01_accidents_ml.ipynb`](../notebooks/01_accidents_ml.ipynb). Les quatorze cellules de code et leurs commentaires sont conservés ; une introduction distingue l’archive de l’analyse révisée. Les anciennes sorties ont été retirées pour éviter de publier des chemins personnels ou de présenter des résultats historiques comme validés.

Le projet de cours est signé **[Yaaaxin](https://github.com/Yaaaxin)** et **[zhailucc](https://github.com/zhailucc)**. Le dépôt distant a été créé par Yaaaxin. Son [commit initial](https://github.com/Yaaaxin/projet-accidents-ml/commit/355e61afff2cc430b3ed8316c23c7ac0c50d4de0) et son historique sont conservés ; le texte initial du README figure dans [original-remote-readme.md](original-remote-readme.md). L’extension est distinguée du travail initial, sans réattribuer rétroactivement ses contributions.

## Résultats historiques

Ces chiffres proviennent des sorties sauvegardées du notebook initial, avant correction ; ils ne sont pas de nouvelles mesures.

| Modèle | ROC-AUC historique | Matrice : lignes vraies, colonnes prédites (0,1) |
|---|---:|---|
| Régression logistique | 0,909273 | `[[3876, 736], [781, 8657]]` |
| Forêt aléatoire | 0,968666 | `[[3964, 648], [264, 9174]]` |

Le découpage par ligne après une jointure un-à-plusieurs partage 5 050 accidents entre apprentissage et test. Parmi les 14 050 lignes test, 5 069 (36,08 %) concernent un accident déjà présent à l’apprentissage. La régression logistique historique présente également un avertissement de non-convergence, et le remplacement des valeurs manquantes n’était pas appliqué à l’objet utilisé pour entraîner les modèles.

**Ces scores n’ont pas passé l’évaluation corrigée.** Leur comparaison directe aux nouveaux scores n’isole pas l’effet de la contamination : la représentation, le nettoyage, les poids implicites et certains paramètres changent aussi. Le chevauchement établit le défaut de séparation ; son effet exact sur le score n’est pas estimé par cette simple comparaison.

## Périmètre de l’extension

L’extension se trouve dans `src/`, `config/`, `tests/`, le notebook `02_methodologie.ipynb` et les résultats agrégés. Elle reprend la question du cours et les deux familles de modèles, corrige l’unité statistique et les traitements, puis ajoute une évaluation géographique, des ablations et des intervalles appariés. Elle ne revendique pas d’innovation algorithmique.
