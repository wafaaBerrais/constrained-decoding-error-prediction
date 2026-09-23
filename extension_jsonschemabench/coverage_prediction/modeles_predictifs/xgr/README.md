# XGR Coverage Prediction - Filtered Features

Ce dossier contient la version actuelle des modeles `xgr`,
reentrainee avec les features filtrees et les overrides numeriques/combinator.

## Modeles actifs

| target | statut | features | modele retenu | seuil | note |
|---|---:|---:|---|---:|---|
| UNDER | trained | 185 | `random_forest_leaf2_sqrt` | 0.49 | recovered_pickle |
| OVER | trained | 139 | `random_forest_leaf2_0.7` | 0.54 | recovered_pickle |

## Fichiers principaux

- `modeling/selected_under_features.txt` / `modeling/selected_over_features.txt`: features filtrees.
- `metrics/`: metriques du reentrainement filtre.
- `plots/feature_importance/`: importances du modele filtre.
- `errors/`: erreurs de classification regenerees avec les modeles filtres.

Le dossier `feature_filter/` a la racine de `coverage_prediction` conserve l audit des features gardees et supprimees.
