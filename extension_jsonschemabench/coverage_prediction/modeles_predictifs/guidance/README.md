# Guidance Coverage Prediction - Filtered Features

Ce dossier contient la version actuelle des modeles `guidance`,
reentrainee avec les features filtrees et les overrides numeriques/combinator.

## Modeles actifs

| target | statut | features | modele retenu | seuil | note |
|---|---:|---:|---|---:|---|
| UNDER | skipped, une seule classe positive absente | 0 | - | - |  |
| OVER | trained | 138 | `random_forest_leaf2_0.7` | 0.46 |  |

## Fichiers principaux

- `modeling/selected_under_features.txt` / `modeling/selected_over_features.txt`: features filtrees.
- `metrics/`: metriques du reentrainement filtre.
- `plots/feature_importance/`: importances du modele filtre.
- `errors/`: erreurs de classification regenerees avec les modeles filtres.

Le dossier `feature_filter/` a la racine de `coverage_prediction` conserve l audit des features gardees et supprimees.
