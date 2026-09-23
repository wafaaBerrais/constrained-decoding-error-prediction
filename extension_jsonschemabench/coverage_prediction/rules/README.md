# Decision Tree Rule Extraction

Ces arbres sont des modeles interpretables peu profonds entraines pour extraire des regles.
Ils completent les modeles retenus principaux, qui restent les meilleurs modeles predictifs.

## Methode

- Donnees : tables `modeling/under_dataset.csv` et `modeling/over_dataset.csv`.
- Split : groupe par `schema_id`, environ 70% train, 15% validation, 15% test.
- Features : liste retenue du modele principal correspondant.
- Candidats : arbres de profondeur 2 a 5 et `min_samples_leaf` 20, 50, 100.
- Selection : PR-AUC validation, puis F1, recall, precision.
- Seuil : choisi sur validation pour maximiser le F1.

## Resultats

| framework | target | tree | features | F1 | precision | recall | PR-AUC | ROC-AUC |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| guidance | OVER | tree_depth5_leaf50 | 117 | 0.793 | 0.746 | 0.847 | 0.838 | 0.808 |
| outlines | UNDER | tree_depth5_leaf50 | 146 | 0.733 | 0.907 | 0.615 | 0.711 | 0.915 |
| outlines | OVER | tree_depth5_leaf50 | 65 | 0.797 | 0.867 | 0.737 | 0.851 | 0.928 |
| xgr | UNDER | tree_depth5_leaf20 | 161 | 0.601 | 0.450 | 0.904 | 0.448 | 0.868 |
| xgr | OVER | tree_depth5_leaf20 | 117 | 0.749 | 0.897 | 0.642 | 0.762 | 0.880 |

## Fichiers

Chaque dossier contient :

- `*_tree.svg` : plot de l'arbre.
- `*_tree.txt` : arbre textuel complet.
- `*_positive_rules.csv` : feuilles positives sous forme de regles.
- `*_all_leaf_rules.csv` : toutes les feuilles, positives et negatives.
- `*_rules.md` : explication et regles lisibles.
- `*_candidate_metrics.csv` : metriques de tous les arbres candidats.
- `*_selected_metrics.csv` : metriques de l'arbre retenu.
