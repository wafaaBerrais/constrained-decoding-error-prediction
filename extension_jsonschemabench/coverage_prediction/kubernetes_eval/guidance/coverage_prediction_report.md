# guidance Coverage Prediction Report

## Scope

- Included datasets: `Kubernetes`
- Skipped datasets: none
- Framework: `guidance`
- Split: grouped by `schema_id` with train/validation/test partitions.
- Candidate models: tuned variants of `LogisticRegression`, `RandomForestClassifier`, `HistGradientBoostingClassifier`, and `LGBMClassifier` when LightGBM is installed.
- Model selection: best validation PR-AUC, then F1, recall, and precision as tie-breakers.
- Decision threshold: selected on validation to maximize F1 for each candidate model.
- Trained targets: `over`

## Modeling Tables

- UNDER rows: 2908 ({'CORRECT_INVALID': 2908})
- OVER rows: 1658 ({'OVER': 827, 'CORRECT_VALID': 831})

## Notes

- `dataset` is kept as metadata and is not used as an input feature.
- A target is skipped when it has only one class, because binary classifiers cannot be trained meaningfully.
- For `guidance`, the `OVER` modeling table excludes `compile_error` rows and keeps only runtime `passed`/`failed` results.
- For `guidance`, the `OVER` model uses an expanded runtime feature set covering string/regex, numeric, array, enum, object-size, and instance-shape signals.

## Retained artifacts

- Shared feature CSV: [Kubernetes_external_features.csv](../../external_eval/Kubernetes/guidance/Kubernetes_external_features.csv). The identical local feature CSV copies were removed.
- `models/over_model.pkl` is the retained model. Candidate model pickles were removed; selection metrics remain in `metrics/`.
