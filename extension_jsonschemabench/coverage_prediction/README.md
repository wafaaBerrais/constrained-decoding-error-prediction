# Coverage Prediction — prédiction des erreurs des frameworks

## But du dossier

Ce dossier rassemble les données de modélisation, les modèles appris et les analyses qui cherchent à **prédire les erreurs de respect des contraintes JSON Schema** de trois frameworks : **Guidance**, **XGrammar (`xgr`)** et **Outlines**.

L'unité étudiée est un **test associant un schéma JSON et une instance JSON**, pour un framework donné. À partir des caractéristiques du schéma et de l'instance, on apprend à reconnaître deux types d'erreurs :

| Cible | Tests concernés | Classe positive à prédire | Classe négative |
| --- | --- | --- | --- |
| **UNDER** — sous-contrainte | Instances attendues invalides | Le framework accepte une instance qui devrait être rejetée. | Le framework rejette correctement l'instance. |
| **OVER** — sur-contrainte | Instances attendues valides | Le framework rejette une instance qui devrait être acceptée. | Le framework accepte correctement l'instance. |

Il s'agit de classifieurs distincts par framework et par cible, et non de modèles qui génèrent du JSON ou prédisent le temps d'exécution. Comme certaines features décrivent l'instance et ses relations avec le schéma, la prédiction ne repose pas uniquement sur le schéma.

Le travail comprend la création de features, la comparaison de plusieurs familles de modèles, le filtrage des features et le réentraînement, l'analyse des erreurs, l'extraction de règles lisibles et deux expériences sur Kubernetes. Les scripts sont dans [`../scripts/`](../scripts/) ; ce dossier contient essentiellement leurs données et leurs résultats.

## Structure générale

```text
coverage_prediction/
├── README.md                         # Présentation globale et guide de lecture
├── filtered_retraining_summary.csv   # Statut et configuration du réentraînement retenu
├── retained_list_retraining_scores.csv
├── retained_selected_pickle_validation.csv
├── cross_validation_summary.csv
├── cross_validation_fold_metrics.csv
├── cross_validation_confusion_matrix.csv
├── modeles_predictifs/
│   ├── guidance/
│   ├── outlines/
│   └── xgr/
├── feature_documentation/            # Définition des features et choix de simplification
├── feature_filter/                   # Listes de features et audit du filtrage
├── rules/                            # Arbres de décision et règles interprétables
├── external_eval/
│   └── Kubernetes/                   # Application des modèles GitHub sans réentraînement
├── kubernetes_eval/                  # Entraînement et évaluation internes à Kubernetes
└── slides/                           # Présentation de l'étude et notes orales
```

## Démarche suivie

### 1. Construire les données et les features

Les résultats par test proviennent de `../results/per_dataset_runs/<framework>/<dataset>/per_test_results.jsonl`. Ils sont rapprochés des schémas et des instances du benchmark pour construire une ligne de caractéristiques par test.

Les tables principales utilisent les datasets `Github_trivial`, `Github_easy`, `Github_medium`, `Github_hard` et `Github_ultra`, selon les résultats disponibles. Les tables Outlines actuellement conservées ne contiennent pas `Github_hard`.

Le feature engineering repose sur le module `analyze_refined_features.py`, notamment `analyze_schema`, `analyze_instance` et `add_buckets`, importés par [`build_outlines_coverage_prediction.py`](../scripts/build_outlines_coverage_prediction.py). Malgré son nom, ce dernier script prend en charge les trois frameworks. **Dans l’état du dossier inspecté lors de cette rédaction, `analyze_refined_features.py` est absent de `../scripts/`, alors que cet import est toujours présent : il faut rétablir ou remplacer cette dépendance avant de relancer la construction des features et les scripts qui en dépendent.**

Les familles de features couvrent notamment :

- **Structure du schéma** : profondeur, nombre de propriétés, mots-clés présents, types et complexité structurelle.
- **Contraintes numériques** : bornes, exclusivité, `multipleOf` et position des valeurs par rapport aux limites.
- **Chaînes et expressions régulières** : longueurs, motifs et caractéristiques de complexité des regex.
- **Objets** : propriétés requises, propriétés supplémentaires, `patternProperties` et taille des objets.
- **Tableaux, types et énumérations** : taille, unicité, compatibilité des types et appartenance à un `enum`.
- **Combinateurs** : `allOf`, `anyOf`, `oneOf`, `not`, nombre de branches satisfaites et contexte des contraintes.
- **Instance et relation instance–schéma** : forme, valeurs, violations et cas proches des frontières des contraintes.

Les identifiants, le dataset, les résultats observés et les labels servent à organiser les données et à définir les cibles ; ils ne constituent pas les variables prédictives sélectionnées. Les tables UNDER et OVER sont construites séparément. Pour Outlines et XGR, elles retiennent les résultats runtime `passed`/`failed`, en excluant les erreurs de compilation ; le même filtre s'applique à OVER pour Guidance.

### 2. Comparer les modèles prédictifs

Les familles testées sont :

| Famille | Rôle dans la comparaison |
| --- | --- |
| Régression logistique | Référence linéaire, avec plusieurs niveaux de régularisation. |
| Random Forest | Ensemble d'arbres permettant de modéliser des interactions entre features ; plusieurs tailles minimales de feuilles et nombres de variables candidates ont été testés. |
| HistGradientBoosting | Boosting d'arbres avec plusieurs paramètres d'apprentissage et de complexité. |
| LightGBM | Autre famille de boosting, utilisée lorsque la dépendance est disponible, avec plusieurs taux d'apprentissage et nombres de feuilles. |

Le prétraitement standardise les variables numériques et encode les variables catégorielles en indicateurs (*one-hot*). Les partitions d'apprentissage, de validation et de test sont regroupées par `schema_id`, avec environ **70 % / 15 % / 15 % des schémas** : les tests d'un même schéma restent dans une seule partition.

La sélection utilise la **PR-AUC sur validation**, puis le F1, le rappel et la précision pour départager les candidats. Le seuil de décision est choisi sur validation pour maximiser le F1. Les résultats incluent aussi la ROC-AUC, l'accuracy, la balanced accuracy et les matrices de confusion.

### 3. Filtrer les features et réentraîner

Le filtrage combine l'importance des features, leur présence dans les règles d'arbres et des choix liés au domaine JSON Schema. Les importances des variables encodées sont regroupées au niveau de leur feature d'origine.

La configuration de filtrage enregistrée utilise :

- une part d'importance minimale de **0,003** ;
- une importance cumulée cible de **95 %** ;
- un minimum de **12 features**, lorsque le nombre de candidates le permet ;
- la conservation des features utilisées dans les règles ;
- des ajouts et exclusions explicites pour les features numériques et les combinateurs.

Ces critères se combinent : une feature peut être conservée pour atteindre le minimum, l'importance cumulée, sa propre importance ou sa présence dans les règles. Le nettoyage de domaine retire aussi des features redondantes ou complexes, dont les variables suffixées `_bucket`.

Une simplification ultérieure a supprimé des features quasi nulles et réentraîné les modèles. `branches_with_additionalProperties_schema_count` et `oneOf_satisfied_all_branch_count` ont été retirées de toutes les listes retenues ; une liste plus large de features quasi nulles a été retirée des listes OVER uniquement. Les listes `selected_*`, `retained_*` et celles des modèles ont fait l'objet d'un contrôle de cohérence enregistré dans `retained_selected_pickle_validation.csv`.

Les modèles retenus après ce nettoyage sont décrits par les CSV de synthèse à la racine :

| Framework | Cible | Tests de modélisation | Positifs | Features | Modèle retenu | Seuil | F1 test enregistré |
| --- | --- | ---: | ---: | ---: | --- | ---: | ---: |
| Guidance | UNDER | 15 208 | 0 | 0 | Aucun : une seule classe | — | — |
| Guidance | OVER | 6 349 | 3 315 | 117 | `random_forest_leaf2_0.7` | 0,32 | 0,781 |
| Outlines | UNDER | 9 787 | 1 242 | 146 | `lightgbm_lr0.05_leaves31` | 0,87 | 0,845 |
| Outlines | OVER | 5 267 | 831 | 65 | `random_forest_leaf5_sqrt` | 0,72 | 0,812 |
| XGR | UNDER | 14 046 | 2 159 | 161 | `random_forest_leaf2_sqrt` | 0,44 | 0,744 |
| XGR | OVER | 7 485 | 1 424 | 117 | `random_forest_leaf2_0.7` | 0,44 | 0,736 |

Les effectifs indiqués sont ceux des tables complètes ; les F1 portent sur leurs partitions de test. Sources : [configuration](filtered_retraining_summary.csv), [scores](retained_list_retraining_scores.csv) et [contrôle des listes](retained_selected_pickle_validation.csv).

### 4. Extraire des règles interprétables

Des **arbres de décision peu profonds** ont été entraînés séparément pour rendre les associations plus lisibles. Ils complètent les modèles prédictifs principaux ; les règles ne sont pas une traduction exacte des Random Forest ou des modèles de boosting.

Les essais combinent des profondeurs de **2 à 5** et des tailles minimales de feuilles de **20, 50 ou 100**. Ils utilisent les tables UNDER/OVER, les listes de features retenues et des partitions par schéma. La sélection et le seuil reposent sur la validation. Les feuilles positives sont exportées comme des conditions associées à une prédiction UNDER ou OVER, avec leurs supports et leurs performances. Ces associations ne prouvent pas à elles seules une causalité.

Les résultats sont dans [`rules/`](rules/README.md).

## Contenu des sous-dossiers et des fichiers

### `modeles_predictifs/` — modèles principaux appris sur GitHub

Les dossiers [`guidance/`](modeles_predictifs/guidance/), [`outlines/`](modeles_predictifs/outlines/) et [`xgr/`](modeles_predictifs/xgr/) regroupent chacun :

| Emplacement ou famille de fichiers | Contenu |
| --- | --- |
| `README.md` | Présentation locale du framework ; certains chiffres décrivent une étape antérieure au dernier filtrage. La synthèse globale ci-dessus utilise les CSV du réentraînement final. |
| `models/over_model.pkl`, `models/under_model.pkl` | Modèles sérialisés avec pipeline, features sélectionnées, seuil et informations de partition. Guidance ne possède pas de modèle UNDER appris. |
| `xgr/models_recovered/` | Modèles XGR sauvegardés lors d'un problème d'écriture signalé dans l'historique. Ils sont réellement utilisés ; voir la note ci-dessous. |
| `modeling/over_dataset.csv`, `modeling/under_dataset.csv` | Tables d'apprentissage : une ligne par test, features, métadonnées et cible. |
| `modeling/selected_*_features.txt`, `modeling/retained_*_features.txt` | Listes de variables sélectionnées et retenues par cible. Les copies actuelles sont synchronisées. |
| `modeling/*_feature_filter_decisions.csv` | Audit des décisions de filtrage associé aux tables de modélisation. |
| `metrics/*_metrics.csv` | Mesures de performance par cible, modèle et partition selon le run. |
| `metrics/*_model_selection.csv` | Résultats de validation permettant de comparer les candidats. |
| `metrics/*_classification_report.csv`, `metrics/*_confusion_matrix.csv` | Précision, rappel et F1 par classe ; comptes de prédictions correctes et incorrectes. |
| `metrics/*_feature_importance.csv` | Importance des variables du modèle retenu. |
| `errors/*_test_misclassified_tests.csv` | Tests mal classés pour chaque cible et export regroupé `all_test_misclassified_tests.csv`. |
| `errors/test_misclassification_summary.csv` | Synthèse des erreurs exportées. |
| `cross_validation/*_fold_metrics.csv`, `*_fold_confusion_matrix.csv` | Résultats par pli et fichiers regroupés `all_fold_*`. |
| `cross_validation/cv_summary.csv` | Synthèse de la validation croisée du framework. |
| `plots/feature_importance/` | Graphiques SVG des principales importances, CSV `*_grouped_feature_importance.csv` et index HTML `feature_importance_index.html`. |

**Particularité XGR :** `models/under_model.pkl` est vide dans l'état inspecté. Les scripts de validation croisée et d'export des erreurs privilégient `models_recovered/`. L'évaluation externe essaie d'abord `models/`, puis `models_recovered/` en cas d'échec. Ces deux dossiers ne doivent donc pas être considérés comme interchangeables ni supprimés sans harmoniser le chargement et vérifier les modèles.

### `feature_documentation/` — définitions et simplifications

| Fichier | Rôle |
| --- | --- |
| `README.md` | Index de la documentation des features. |
| `used_prediction_features_union.md` et `.csv` | Union documentée des features utilisées par les modèles filtrés. |
| `numeric_prediction_features.md` | Features numériques et choix associés. |
| `combinator_prediction_features.md` | Features des combinateurs JSON Schema. |
| `instance_prediction_features.md` | Features d'instance et simplification des catégories discrétisées. |
| `object_prediction_features.md` | Features relatives aux objets. |
| `schema_prediction_features.md` | Features globales des schémas. |
| `near_zero_importance_features.csv` | Relevé des features de très faible importance utilisé pour la simplification. |

### `feature_filter/` — traçabilité du filtrage

- `README.md` explique la configuration de filtrage ; ses effectifs décrivent le premier état filtré, avant la dernière suppression des features quasi nulles.
- `feature_filter_summary.csv` et `all_feature_filter_decisions.csv` regroupent les synthèses et les décisions.
- Chaque sous-dossier `<framework>/<under|over>/` contient `retained_features.txt`, `dropped_features.txt` et `feature_filter_decisions.csv` : variables gardées, supprimées et raisons des décisions.
- Le cas Guidance UNDER conserve des fichiers vides ou des en-têtes, puisqu'aucun classifieur binaire n'a pu être appris sur cette cible.

### `rules/` — arbres et règles

À la racine, `README.md` présente la méthode et `decision_tree_rule_summary.csv` résume les arbres retenus. Les sous-dossiers sont organisés par framework et cible ; Guidance ne possède ici qu'une cible OVER.

| Fichiers dans `<framework>/<cible>/` | Rôle |
| --- | --- |
| `*_tree.svg`, `*_tree.txt` | Arbre sous forme graphique et textuelle. |
| `*_positive_rules.csv` | Conditions des feuilles prédisant une erreur. |
| `*_all_leaf_rules.csv` | Toutes les feuilles, positives et négatives. |
| `*_rules.md` | Règles et interprétations lisibles. |
| `*_candidate_metrics.csv` | Comparaison des arbres candidats. |
| `*_selected_metrics.csv` | Performances de l'arbre retenu. |

### `external_eval/Kubernetes/` — généralisation sans réentraînement

Cette expérience répond à la question : **les modèles appris sur les datasets GitHub permettent-ils de prédire les erreurs sur un dataset externe, Kubernetes ?** Les modèles existants et leurs seuils sont appliqués aux features Kubernetes, sans les réentraîner sur ce dataset.

- `README.md` et `external_eval_summary.csv` présentent les résultats regroupés.
- Chaque dossier `guidance/`, `outlines/`, `xgr/` contient `Kubernetes_external_features.csv`, la copie de référence des features Kubernetes pour ce framework.
- `*_external_predictions.csv` contient les prédictions détaillées ; `*_external_misclassified_tests.csv` en extrait les erreurs.
- `*_external_metrics.csv`, `*_external_classification_report.csv` et `*_external_confusion_matrix.csv` contiennent les mesures de performance.
- `external_eval/Kubernetes_auto_eval_20260903.log`, un niveau au-dessus, conserve le journal du lancement automatique.

Les F1 OVER enregistrés sont **0,774 pour Guidance**, **0,379 pour XGR** et **0,542 pour Outlines**. Ils décrivent ce run précis. Pour XGR OVER, le CSV indique un seuil de **0,58** et un modèle chargé depuis `models/`, tandis que le réentraînement final résumé plus haut indique **0,44** et utilise les modèles de récupération dans certains scripts. Il ne faut donc pas présenter ce résultat externe comme une évaluation certaine du même artefact final sans refaire cette vérification.

Aucun cas UNDER positif n'est présent dans les tables Kubernetes évaluées. Les résultats UNDER permettent d'observer les faux positifs, mais pas de mesurer la capacité à détecter des erreurs UNDER sur ce dataset. Guidance UNDER est ignoré faute de modèle appris.

### `kubernetes_eval/` — apprendre directement sur Kubernetes

Cette expérience répond à une autre question : **peut-on apprendre à prédire les erreurs à partir des données Kubernetes elles-mêmes ?** Elle entraîne des modèles sur une partie des schémas Kubernetes, sélectionne leurs paramètres sur validation et les évalue sur une partition de test Kubernetes distincte.

Il s'agit d'une évaluation interne au dataset, pas d'une évaluation externe. Elle reste donc séparée de `external_eval/`. Ses scores ne doivent pas être assimilés à ceux d'un transfert GitHub vers Kubernetes.

Chaque dossier `guidance/`, `outlines/`, `xgr/` contient :

- `coverage_prediction_report.md` : périmètre, méthode et liens vers les features partagées ;
- `modeling/under_dataset.csv`, `over_dataset.csv` et `selected_*_features.txt` : tables et listes des features de cette expérience ;
- `models/over_model.pkl` : modèle OVER retenu ;
- `metrics/` : mêmes familles de fichiers de performance, de sélection et d'importance que pour les modèles principaux.

Seule la cible **OVER** a été entraînée : les tables UNDER ne contiennent qu'une classe. Les modèles sélectionnés d'après les métriques de validation sont une Random Forest `leaf1_sqrt` pour Guidance, une Random Forest `leaf2_sqrt` pour Outlines et `hist_gradient_boosting_lr0.08_leaf15` pour XGR.

Les **45 pickles des modèles candidats ont été supprimés**, tout en conservant les modèles finaux et les métriques de comparaison. Les six CSV de features dupliqués ont également été supprimés : pour chaque framework, la référence est désormais `external_eval/Kubernetes/<framework>/Kubernetes_external_features.csv`. Le partage de ces fichiers ne fusionne pas les protocoles des deux expériences.

### `slides/` — présentation des résultats

- `coverage_prediction_rules_slides.pptx` : diaporama.
- `coverage_prediction_rules_slides.md` : contenu textuel des diapositives.
- `coverage_prediction_rules_speaker_notes.md` : notes pour la présentation orale.
- `assets/xgr_feature_over_lift.png` et `assets/xgr_feature_under_lift.png` : illustrations utilisées dans la présentation.

### Fichiers de synthèse à la racine

| Fichier | Contenu et portée |
| --- | --- |
| `README.md` | Guide global unique, intégrant l'ancien README du réentraînement filtré. |
| `filtered_retraining_summary.csv` | Statut, effectifs, nombre de features et modèle retenu pour chaque framework/cible. |
| `retained_list_retraining_scores.csv` | Scores de test et seuils du réentraînement après simplification des listes. |
| `retained_selected_pickle_validation.csv` | Contrôle enregistré de cohérence entre listes retenues, listes sélectionnées et features du pickle. |
| `cross_validation_summary.csv` | Moyennes, écarts-types et autres agrégats de la validation croisée à cinq plis. |
| `cross_validation_fold_metrics.csv` | Métriques détaillées des plis pour les frameworks et cibles. |
| `cross_validation_confusion_matrix.csv` | Matrices de confusion détaillées de cette validation croisée. |

**Portée de la validation croisée conservée :** son CSV de synthèse indique encore 138/167/81/185/139 features pour Guidance OVER, Outlines UNDER/OVER et XGR UNDER/OVER. Ces résultats correspondent à un état antérieur aux listes finales de 117/146/65/161/117 features. Ils ne valident donc pas automatiquement le dernier réentraînement. Les rapports locaux et audits historiques peuvent également conserver les chiffres de cette étape antérieure.

## Scripts associés

Les principaux points d'entrée sont dans `../scripts/` :

| Script | Travail réalisé |
| --- | --- |
| [`build_outlines_coverage_prediction.py`](../scripts/build_outlines_coverage_prediction.py) | Extraction des features, création des tables, comparaison et entraînement des modèles. |
| [`filter_coverage_features_by_importance_and_rules.py`](../scripts/filter_coverage_features_by_importance_and_rules.py) | Filtrage par importance, règles et politique de domaine. |
| [`retrain_coverage_models_with_filtered_features.py`](../scripts/retrain_coverage_models_with_filtered_features.py) | Réentraînement à partir des tables existantes et des listes retenues. |
| [`plot_coverage_feature_importance.py`](../scripts/plot_coverage_feature_importance.py) | Graphiques des importances individuelles et regroupées. |
| [`export_coverage_misclassifications.py`](../scripts/export_coverage_misclassifications.py) | Export des erreurs des modèles sur la partition de test. |
| [`cross_validate_coverage_models.py`](../scripts/cross_validate_coverage_models.py) | Validation croisée regroupée par schéma. |
| [`extract_coverage_decision_tree_rules.py`](../scripts/extract_coverage_decision_tree_rules.py) | Entraînement des arbres explicatifs et export des règles. |
| [`evaluate_coverage_models_on_dataset.py`](../scripts/evaluate_coverage_models_on_dataset.py) | Application des modèles existants à un dataset externe. |
| [`analyze_guidance_runtime_prediction.py`](../scripts/analyze_guidance_runtime_prediction.py), [`analyze_outlines_runtime_prediction.py`](../scripts/analyze_outlines_runtime_prediction.py) | Analyses complémentaires des différences de features et des erreurs de prédiction. |

Les scripts de construction peuvent recréer des sorties intermédiaires et des modèles candidats lors d'un nouveau run. Le réentraînement filtré utilise par défaut une sortie `filtered_retrained/`, distincte des modèles principaux. Vérifier les arguments de sortie avant de régénérer des résultats ; le nettoyage et la réorganisation des fichiers ne constituent pas une nouvelle exécution des expériences.
