# Outlines Coverage Prediction - Filtered Features

Ce dossier contient la version actuelle des modeles `outlines`,
reentrainee avec les features filtrees et les overrides numeriques/combinator.

## Modeles actifs

| target | statut | features | modele retenu | seuil | note |
|---|---:|---:|---|---:|---|
| UNDER | trained | 167 | `lightgbm_lr0.05_leaves31` | 0.88 |  |
| OVER | trained | 81 | `random_forest_leaf5_sqrt` | 0.61 |  |

## Fichiers principaux

- `modeling/selected_under_features.txt` / `modeling/selected_over_features.txt`: features filtrees.
- `metrics/`: metriques du reentrainement filtre.
- `plots/feature_importance/`: importances du modele filtre.
- `errors/`: erreurs de classification regenerees avec les modeles filtres.

Le dossier `feature_filter/` a la racine de `coverage_prediction` conserve l audit des features gardees et supprimees.
