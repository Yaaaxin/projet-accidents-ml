# Données BAAC 2024

Producteur : **Ministère de l’intérieur / Observatoire national interministériel de la sécurité routière (ONISR)**. Le jeu décrit des accidents corporels enregistrés par les forces de l’ordre ; ce ne sont pas des observations de trajets avec et sans accident.

- [Catalogue officiel](https://www.data.gouv.fr/datasets/53698f4ca3a729239d2036df)
- [Description des champs, édition du 21 octobre 2025, années 2005–2024](https://www.onisr.securite-routiere.gouv.fr/sites/default/files/2025-10/Description%20des%20bases%20de%20donn%C3%A9es%20annuelles_0.pdf)
- Licence annoncée par le catalogue : **Licence Ouverte / Open Licence**, [lien de licence associé au jeu](https://www.etalab.gouv.fr/wp-content/uploads/2014/05/Licence_Ouverte.pdf). La réutilisation exige notamment la mention de la source et de sa date de mise à jour. Cette licence concerne les données, pas automatiquement le code du projet.

## Fichiers et vérification

CSV UTF-8 séparés par `;`, avec une ligne d’en-tête. Les coordonnées décimales utilisent une virgule ; elles ne sont pas employées comme prédicteurs.

| Copie locale | Lignes de données | Colonnes | Octets | Ressource officielle |
|---|---:|---:|---:|---|
| `caract_2024.csv` | 54 402 | 15 | 6 538 156 | [Caract_2024.csv](https://www.data.gouv.fr/api/1/datasets/r/83f0fb0e-e0ef-47fe-93dd-9aaee851674a) |
| `lieux_2024.csv` | 70 248 | 18 | 7 070 795 | [Lieux_2024.csv](https://www.data.gouv.fr/api/1/datasets/r/228b3cda-fdfb-4677-bd54-ab2107028d2d) |

Les deux copies locales ont été comparées aux fichiers retéléchargés depuis ces URL officielles le **4 novembre 2026** : identité binaire confirmée par SHA-256. Leur date de téléchargement initiale est **inconnue**. La date de mise à jour affichée pour les deux ressources est le **21 octobre 2025** ; la mise à jour du catalogue global peut concerner d’autres millésimes.

```text
caract_2024.csv  45a69360aeb566f9065e079c5e9840fb1068e71cd4e6fcc34cb9fdcaff04b391
lieux_2024.csv   a500a44b4efdb18f80de31c2ebde48c682b050667b7b1348671caeec736c8f09
```

Les liens, tailles, empreintes et circonstances de la vérification sont conservés dans [manifest.json](manifest.json). Aucun fichier brut n’est publié dans ce dépôt. Les adresses, coordonnées et heures peuvent permettre de rapprocher un événement d’autres sources ; les sorties publiques se limitent aux statistiques agrégées. Les prédictions individuelles et identifiants de découpage restent dans `results/private/`, ignoré par Git.

## Acquisition

Depuis la racine du dépôt :

```bash
python -m src.download_data
```

Le téléchargement vérifie SHA-256 avant écriture et ne remplace pas un fichier existant. En cas de difficulté réseau, télécharger les deux ressources avec le navigateur et les enregistrer dans `data/` avec les noms **minuscules** ci-dessus, puis relancer la commande pour vérifier les fichiers. Si une ressource officielle change, la vérification échoue explicitement : ne pas modifier l’empreinte sans examiner la nouvelle version.

## Variables et unité statistique

| Variables | Sens et traitement |
|---|---|
| `Num_Acc` | Identifiant de liaison et de contrôle, jamais prédicteur |
| `agg` | Cible : 1 hors agglomération → classe 0 ; 2 en agglomération → classe 1 |
| `dep` | Code de département/territoire, uniquement pour le découpage géographique |
| `lum`, `atm`, `col` | Éclairage, météo, collision ; catégories nominales |
| `an`, `mois`, `jour`, `hrmn` | Date et heure ; composantes cycliques et jour de semaine |
| `catr`, `circ`, `surf`, `plan`, `infra`, `situ` | Caractéristiques des lieux ; proportions des modalités par accident |
| `vma` | Limite de vitesse autorisée au lieu et à l’heure de l’accident, pas vitesse pratiquée |
| `nbv` | Nombre total de voies de circulation |

Les 54 402 identifiants sont uniques dans `caract`. Dans `lieux`, 15 645 accidents ont plusieurs descriptions différentes. Aucune ligne n’est choisie arbitrairement : les catégories sont résumées par proportions, les valeurs numériques par médiane/min/max et proportion manquante. Voir [le protocole](../docs/protocol.md) pour les règles et leurs limites.

Le nettoyage distingue les codes inconnus des zéros valides (`infra=0`, `situ=0`). Les limites `0 < vma <= 130` et `1 <= nbv <= 20` sont des choix de plausibilité de cette analyse, et non des corrections officielles. Les valeurs rejetées sont rendues manquantes. L’imputation et la mise à l’échelle sont ensuite ajustées sur l’apprentissage seulement.
