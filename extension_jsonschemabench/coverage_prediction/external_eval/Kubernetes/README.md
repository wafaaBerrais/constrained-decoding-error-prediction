# External Coverage Prediction Evaluation: Kubernetes

These metrics apply existing coverage-prediction models to an external dataset without retraining on it.

| Framework | Target | Status | N | Positives | F1 | PR-AUC | ROC-AUC | Balanced accuracy | Confusion |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| guidance | under | skipped | 2908 | 0 |  |  |  |  | /home/berrais/stage/jsonschemabench/extension_jsonschemabench/coverage_prediction/modeles_predictifs/guidance/models/under_model.pkl: missing_or_empty; /home/berrais/stage/jsonschemabench/extension_jsonschemabench/coverage_prediction/modeles_predictifs/guidance/models_recovered/under_model.pkl: missing_or_empty |
| guidance | over | evaluated | 1658 | 827 | 0.7742 | 0.8119 | 0.8239 | 0.7512 | tn=537, fp=294, fn=119, tp=708 |
| xgr | under | evaluated | 2908 | 0 | 0.0000 | nan | nan | nan | tn=2903, fp=5, fn=0, tp=0 |
| xgr | over | evaluated | 1680 | 346 | 0.3785 | 0.5975 | 0.8439 | 0.6167 | tn=1333, fp=1, fn=265, tp=81 |
| outlines | under | evaluated | 2853 | 0 | 0.0000 | nan | nan | nan | tn=2853, fp=0, fn=0, tp=0 |
| outlines | over | evaluated | 1632 | 207 | 0.5423 | 0.5715 | 0.8292 | 0.6860 | tn=1425, fp=0, fn=130, tp=77 |
