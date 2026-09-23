# outlines Coverage Prediction Report

## Scope

- Included datasets: `Kubernetes`
- Skipped datasets: none
- Framework: `outlines`
- Split: grouped by `schema_id` with train/validation/test partitions.
- Candidate models: tuned variants of `LogisticRegression`, `RandomForestClassifier`, `HistGradientBoostingClassifier`, and `LGBMClassifier` when LightGBM is installed.
- Model selection: best validation PR-AUC, then F1, recall, and precision as tie-breakers.
- Decision threshold: selected on validation to maximize F1 for each candidate model.
- Trained targets: `over`

## Modeling Tables

- UNDER rows: 2853 ({'CORRECT_INVALID': 2853})
- OVER rows: 1632 ({'CORRECT_VALID': 1425, 'OVER': 207})

## Notes

- `dataset` is kept as metadata and is not used as an input feature.
- A target is skipped when it has only one class, because binary classifiers cannot be trained meaningfully.
- For `outlines`, both `UNDER` and `OVER` modeling tables exclude `compile_error` rows and keep only runtime `passed`/`failed` results.
- For `outlines`, the `UNDER` model uses all usable refined runtime features from the fused feature table.

## Retained artifacts

- Shared feature CSV: [Kubernetes_external_features.csv](../../external_eval/Kubernetes/outlines/Kubernetes_external_features.csv). The identical local feature CSV copies were removed.
- `models/over_model.pkl` is the retained model. Candidate model pickles were removed; selection metrics remain in `metrics/`.
