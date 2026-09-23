# Scripts de l'extension JSONSchemaBench

Ce dossier contient les scripts d'exécution du benchmark, d'analyse des résultats et de construction des modèles de prédiction. Ce guide résume les **23 scripts Python actuellement présents**, regroupés par rôle.

Les données et rapports produits se trouvent principalement dans [`../results/`](../results/) et [`../coverage_prediction/`](../coverage_prediction/README.md). Les scripts sont des points d'entrée utilisables séparément ; certains importent aussi les fonctions d'autres scripts.

Dans les analyses, **UNDER** désigne l'acceptation d'une instance attendue invalide et **OVER** le rejet d'une instance attendue valide.

## Exécuter les tests et gérer les interruptions

| Script | Ce qu'il fait |
| --- | --- |
| [`run_per_test_framework_logging.py`](run_per_test_framework_logging.py) | Exécute un framework via les moteurs MaskBench et enregistre un résultat JSONL par test. Gère la sélection des datasets, les limites de tests et, en option, les mesures de temps et les étapes de compilation. C'est le moteur d'exécution utilisé par les superviseurs. |
| [`run_dataset_with_timeouts.py`](run_dataset_with_timeouts.py) | Lance le moteur précédent dans un processus distinct pour chaque schéma. Applique les délais, reprend les résultats existants et enregistre les schémas interrompus, les journaux et les mesures de profilage demandées. |
| [`run_dataset_profile_csv_with_timeouts.py`](run_dataset_profile_csv_with_timeouts.py) | Variante destinée à rejouer les tests pour compléter un CSV de temps. Reprend à partir des mesures finales déjà présentes et écrit les résultats rejoués, les timeouts et les journaux dans des fichiers explicitement indiqués. |
| [`resume_outlines_hard_resilient.py`](resume_outlines_hard_resilient.py) | Reprend Outlines sur `Github_hard`, schéma par schéma, en appelant le superviseur. Ignore les cas déjà terminés et enregistre les arrêts anormaux du processus enfant pour poursuivre les schémas suivants. |
| [`outlines_hard_resilient_helper.py`](outlines_hard_resilient_helper.py) | Petit outil avec deux commandes : `status` vérifie si un schéma reste à exécuter ; `mark` enregistre une interruption et met à jour les fichiers de timeout/profilage. Il a été conçu pour le lanceur Bash résilient, qui n'est plus présent dans ce dossier. |

## Indexer et analyser les résultats du benchmark

| Script | Ce qu'il fait |
| --- | --- |
| [`build_schema_test_framework_index.py`](build_schema_test_framework_index.py) | Rassemble les informations des schémas, tests, frameworks, résultats et timeouts dans un index commun. Produit des fichiers CSV/JSON et un rapport Markdown pour retrouver les cas exécutés et leurs résultats. |
| [`summarize_constraint_results.py`](summarize_constraint_results.py) | Lit cet index et résume les résultats corrects, les erreurs UNDER/OVER et les erreurs de compilation. Peut filtrer un framework, afficher des exemples et écrire un rapport Markdown. |
| [`analyze_dataset_statistics.py`](analyze_dataset_statistics.py) | Analyse un run pour un dataset et un framework à partir des résultats par test, des temps et des timeouts. Calcule des statistiques par schéma et des associations avec les caractéristiques JSON Schema ; produit des CSV, graphiques SVG et un rapport. Fournit aussi des fonctions communes aux autres analyses. |
| [`analyze_cross_dataset_statistics.py`](analyze_cross_dataset_statistics.py) | Compare les tables statistiques déjà produites pour plusieurs datasets d'un même framework : performances, temps, timeouts, fréquence des features et associations avec les erreurs. Génère des tableaux et graphiques comparatifs. |
| [`analyze_compile_error_causes.py`](analyze_compile_error_causes.py) | Regroupe les messages d'erreur de compilation par causes probables et les rapproche des features des schémas. Produit des CSV, des graphiques et une mise à jour du rapport de plots du run. |
| [`analyze_outlines_specific.py`](analyze_outlines_specific.py) | Approfondit les résultats Outlines : étapes d'échec, coût des regex, cas extrêmes, indicateurs de complexité et liens avec les contraintes. L'étude configurée exclut `Github_hard`. |
| [`analyze_refined_features_v2.py`](analyze_refined_features_v2.py) | Lit les tables de features raffinées déjà extraites pour calculer des risques conditionnels UNDER/OVER, des cooccurrences et des exemples détaillés. Produit des CSV, graphiques et rapports. Il est également importé par les notebooks de visualisation de l'extension. |

## Construire et évaluer les modèles prédictifs

Le détail des expériences et de leurs résultats est présenté dans le [README de Coverage Prediction](../coverage_prediction/README.md).

| Script | Ce qu'il fait |
| --- | --- |
| [`build_outlines_coverage_prediction.py`](build_outlines_coverage_prediction.py) | Construit les features par test et les tables UNDER/OVER, puis compare régression logistique, Random Forest, HistGradientBoosting et LightGBM lorsque disponible. Sélectionne les modèles et leurs seuils sur validation ; exporte modèles, métriques et importances. Malgré son nom, il prend en charge Guidance, Outlines et XGR. |
| [`filter_coverage_features_by_importance_and_rules.py`](filter_coverage_features_by_importance_and_rules.py) | Sélectionne les features à conserver en combinant leur importance, leur présence dans les règles d'arbres et des choix de domaine. Écrit les listes retenues/supprimées et les raisons de chaque décision dans `coverage_prediction/feature_filter/`. |
| [`retrain_coverage_models_with_filtered_features.py`](retrain_coverage_models_with_filtered_features.py) | Réentraîne les modèles à partir des tables existantes et des listes filtrées. Réutilise l'entraînement du script de construction et produit les modèles, métriques et synthèses correspondants ; sa sortie par défaut est `coverage_prediction/filtered_retrained/`. |
| [`cross_validate_coverage_models.py`](cross_validate_coverage_models.py) | Réévalue les configurations retenues par validation croisée, avec regroupement par `schema_id`. Réentraîne les modèles sur les plis et ajuste le seuil sur une validation interne ; exporte les métriques, matrices de confusion et synthèses. |
| [`evaluate_coverage_models_on_dataset.py`](evaluate_coverage_models_on_dataset.py) | Reconstruit les features d'un dataset externe, charge les modèles existants et applique leurs seuils sans réentraînement. Produit les prédictions, erreurs et métriques ; le dataset par défaut est Kubernetes, avec sorties sous `coverage_prediction/external_eval/`. |
| [`export_coverage_misclassifications.py`](export_coverage_misclassifications.py) | Charge les modèles retenus et leurs tables pour exporter les tests mal classés, par cible et dans un fichier regroupé. La partition analysée est configurable, avec `test` par défaut. |
| [`plot_coverage_feature_importance.py`](plot_coverage_feature_importance.py) | Lit les importances enregistrées, regroupe celles des variables encodées par feature d'origine et produit des graphiques SVG des principales features, des CSV regroupés et un index HTML. |
| [`analyze_guidance_runtime_prediction.py`](analyze_guidance_runtime_prediction.py) | Analyse les données runtime de Guidance pour la cible OVER. Compare les features des tests `failed`/`passed`, puis celles des faux positifs, faux négatifs et prédictions correctes du modèle ; produit des CSV, graphiques et un rapport dans `analyse/`. |
| [`analyze_outlines_runtime_prediction.py`](analyze_outlines_runtime_prediction.py) | Analyse les signaux et erreurs de prédiction runtime pour les deux cibles OVER et UNDER. Compare les classes positives/négatives et les groupes d'erreurs. Le dossier et le libellé du framework sont paramétrables, même si le défaut est Outlines. |

## Expliquer les erreurs et rechercher des cas minimaux

| Script | Ce qu'il fait |
| --- | --- |
| [`extract_coverage_decision_tree_rules.py`](extract_coverage_decision_tree_rules.py) | Entraîne des arbres de décision peu profonds sur les tables UNDER/OVER pour extraire des règles lisibles. Compare plusieurs profondeurs et tailles de feuilles ; exporte arbres SVG/texte, règles des feuilles et métriques dans `coverage_prediction/rules/`. Ces arbres explicatifs sont distincts des modèles prédictifs principaux. |
| [`run_hdd_minimization.py`](run_hdd_minimization.py) | Réduit progressivement les schémas de cas UNDER/OVER Outlines en cherchant à conserver le désaccord observé. Produit des schémas simplifiés, des traces et des synthèses pour étudier les contraintes impliquées. L'interface actuelle est limitée à Outlines sur `Github_medium`. |

## Principales dépendances entre les étapes

- **Exécution** : `run_dataset_with_timeouts.py` et la variante de profilage lancent `run_per_test_framework_logging.py`. La reprise résiliente Python ajoute une supervision autour de `run_dataset_with_timeouts.py`.
- **Analyse générale** : l'index construit par `build_schema_test_framework_index.py` est consommé par `summarize_constraint_results.py`. Les comparaisons multi-datasets s'appuient sur les tables produites par `analyze_dataset_statistics.py`.
- **Analyse raffinée** : la V2 consomme `refined_test_features.csv` et `refined_schema_features.csv`. Elle complète l'extraction des features ; elle ne la remplace pas.
- **Prédiction** : construction des tables et premiers modèles, puis filtrage et réentraînement. Le filtrage peut intégrer des règles déjà extraites ; les arbres explicatifs peuvent ensuite être régénérés avec les listes finales. Les graphiques, exports d'erreurs, validations et évaluations sont des outils complémentaires.

**Dépendance actuellement manquante :** `build_outlines_coverage_prediction.py` importe encore `analyze_refined_features.py`, absent de ce dossier au moment de cette rédaction. Il faut rétablir ou remplacer ce module pour relancer la construction et les scripts qui l'importent directement ou indirectement. La V2 peut exploiter des tables raffinées déjà existantes.

## Repères d'utilisation

Les options varient selon le script ; une fois ses dépendances disponibles, `--help` présente ses arguments. Depuis la racine `jsonschemabench`, par exemple :

```bash
.venv/bin/python extension_jsonschemabench/scripts/run_dataset_with_timeouts.py --help
```

Les scripts de prédiction utilisent les dossiers principaux sous `coverage_prediction/modeles_predictifs/`. Pour les outils à argument `--output-root`, vérifier le chemin : plusieurs ciblent **Outlines par défaut**, même lorsqu'un autre framework est sélectionnable. `--coverage-root` désigne le dossier global `coverage_prediction`, tandis que `--model-root` de l'évaluation externe désigne par défaut `coverage_prediction/modeles_predictifs`.

`__pycache__/` contient uniquement le cache Python généré automatiquement ; ce n'est pas un ensemble de scripts supplémentaires. Ce README décrit le code présent et n'indique pas que toutes les expériences ont été relancées.
