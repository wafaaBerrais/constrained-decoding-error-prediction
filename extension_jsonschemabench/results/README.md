# Résultats de validation des frameworks

## But du dossier

Ce dossier rassemble les résultats de l'exécution de **Guidance**, **XGrammar (`xgr`)** et **Outlines** sur les tests JSONSchemaBench/MaskBench. Il permet de vérifier si chaque framework accepte ou rejette correctement les instances JSON, de mesurer le coût des étapes et d'étudier les erreurs de compilation, les lenteurs et les timeouts.

L'extension ajoute aux exécutions du benchmark :

- un résultat détaillé **par test**, avec validité attendue et décision du framework ;
- le profilage du chargement, de la compilation, de la tokenisation et de la validation ;
- une supervision par schéma, la reprise des runs et l'enregistrement des interruptions ;
- pour Outlines, le détail de la construction de la regex, de l'index et du guide ;
- des statistiques par schéma, des graphiques et des analyses des caractéristiques associées aux erreurs.

Ces données alimentent les notebooks de visualisation et les expériences de [prédiction des erreurs](../coverage_prediction/README.md). Les scripts producteurs sont décrits dans le [README des scripts](../scripts/README.md).

## Organisation

```text
results/
├── README.md
└── per_dataset_runs/
    ├── guidance/
    │   ├── Github_trivial/  Github_easy/  Github_medium/
    │   ├── Github_hard/     Github_ultra/
    │   ├── Github_global/
    │   └── Kubernetes/
    ├── xgr/
    │   └── mêmes datasets et Github_global/
    └── outlines/
        ├── Github_trivial/  Github_easy/  Github_medium/
        ├── Github_hard/     Github_ultra/
        ├── Github_global_no_hard/
        ├── Kubernetes/
        └── Github_hard_nfs_busy_20260719_152848/
```

Le chemin usuel est `per_dataset_runs/<framework>/<dataset>/`. Tous les datasets ne possèdent pas les mêmes fichiers : cela dépend du profilage activé, de la progression du run et des analyses générées.

`Github_global` est une **fusion d'artefacts GitHub existants**, utilisée pour les analyses globales. Pour Outlines, `Github_global_no_hard` exclut `Github_hard`. Ces dossiers ne représentent pas de nouvelles exécutions : ne pas additionner leurs lignes à celles des datasets sources.

Dans l'état inspecté, `outlines/Github_hard/` contient le profilage et les informations de timeout, mais pas de `per_test_results.jsonl` ; ce n'est donc pas un run de validation complet. Le dossier suffixé `nfs_busy_...` est un reliquat technique, pas un dataset supplémentaire.

## Retrouver les schémas et les instances

Les résultats ne recopient généralement pas les schémas et les instances. Ils les **référencent dans les fichiers sources**, généralement sous `maskbench/data/` à la racine du projet.

| Champ | Signification |
| --- | --- |
| `schema_id` | Identifiant du schéma, par exemple `Github_medium---o1.json`. |
| `schema_path` | Chemin du fichier source, relatif à la racine `jsonschemabench`. |
| `test_index` | Position du test dans le tableau `tests` du fichier source. |
| `test_id` | Identifiant du test, par exemple `Github_medium---o1.json::test_00000`. |
| `test_path` | Chemin du fichier avec un fragment tel que `#/tests/0`. |
| `dataset_id`, `framework_id`, `framework` | Dataset et moteur ayant produit l'observation. |

Le document source contient notamment `schema` et `tests`, avec les instances et leur validité attendue. Pour rapprocher résultats et temps, utiliser les identifiants de schéma, de test et de framework plutôt que l'ordre des lignes.

## Fichiers principaux d'un run

### `per_test_results.jsonl` — résultat de chaque test

Un objet JSON par ligne décrit normalement un test exécuté pour le framework. Le fichier est produit par `run_per_test_framework_logging.py` et peut être complété par la supervision.

| Champs | Contenu et usage |
| --- | --- |
| Identifiants et chemins | Retrouver le schéma, le test et le framework. |
| `expected_validity` | Validité de référence : `valid`, `invalid` ou éventuellement `unknown`. |
| `accepted` | Décision d'acceptation, lorsqu'elle est disponible. |
| `actual_result` | Statut, notamment `passed`, `failed`, `compile_error` ou `timeout`, selon le cas et le producteur. |
| `result_available` | Indique si une décision de validation exploitable est disponible. |
| `error_message`, `notes` | Exception, explication ou contexte du runner/superviseur. |
| `runner_or_command` | Indication du script ou de la commande productrice. |
| `num_tokens`, `tokens_checked` | Nombre de tokens et progression de la validation. |
| `ttfm_us`, `compute_mask_us`, `commit_token_us`, `masks_us`, `max_mask_us` | Mesures de compilation ou de traitement des tokens, lorsqu'elles sont présentes. Dans ce runner, `ttfm_us` reçoit le temps de compilation mesuré. |

**`passed` signifie que la décision correspond à celle attendue, pas nécessairement que l'instance a été acceptée.**

| Validité attendue | Décision | Interprétation |
| --- | --- | --- |
| Valide | Acceptation | Résultat correct, `passed`. |
| Invalide | Rejet | Résultat correct, `passed`. |
| Invalide | Acceptation | **UNDER** : sous-contrainte, `failed`. |
| Valide | Rejet | **OVER** : sur-contrainte, `failed`. |

Identifier les timeouts et les erreurs de compilation par leur statut et `result_available` avant d'interpréter `accepted`. Une valeur absente ne prouve pas un rejet OVER. Les analyses peuvent appliquer des règles d'inclusion différentes ; vérifier leur périmètre avant de comparer les taux.

### `timing_profile.csv` — profilage par test

Ce CSV décompose le coût d'exécution et aide à repérer une étape lente ou interrompue. Les colonnes dépendent du framework et de la version du profilage.

| Colonnes | Ce qu'elles décrivent |
| --- | --- |
| Identifiants, `actual_result`, `accepted`, `result_available` | Correspondance avec les résultats et état du test. |
| `schema_file_bytes`, `schema_json_chars`, `instance_json_chars` | Taille des entrées, pour rapprocher complexité et durée. |
| `engine_tokenizer_load_us`, `engine_init_us` | Chargement du tokenizer et initialisation du moteur. |
| `schema_load_us`, `compile_grammar_us` | Chargement du schéma et compilation. |
| `test_json_dumps_us`, `tokenize_us`, `reset_matcher_us` | Sérialisation de l'instance, tokenisation et préparation du matcher. |
| `validation_loop_us` | Durée de la boucle de validation. |
| `compute_mask_us`, `commit_token_us`, `max_compute_mask_us`, `max_commit_token_us` | Durées cumulées et maxima des opérations sur les tokens. |
| `num_tokens`, `tokens_checked`, `first_rejected_token_index` | Volume, avancement et position d'un éventuel rejet. |
| `regex_build_us`, `index_build_us`, `guide_init_us`, `total_compile_us`, etc. | Détail supplémentaire de la compilation Outlines. |
| `final_status`, `last_stage`, `exception_type`, `exception_message`, `error_message` | État final ou partiel et diagnostic. |

Les suffixes **`_us` sont en microsecondes**. Des lignes partielles peuvent être écrites avant ou pendant une opération longue : une cellule vide signifie une mesure indisponible, pas un temps nul. Des durées d'initialisation ou de compilation peuvent être répétées sur plusieurs tests d'un même schéma ; leur somme naïve ne représente pas le temps réel du run.

### `schema_compile_profile.csv` — compilation d'Outlines par schéma

| Colonnes | Usage |
| --- | --- |
| `schema_load_s`, `schema_serialize_s` | Lecture et sérialisation du schéma. |
| `regex_build_s`, `regex_built` | Durée et réussite de la construction de la regex. |
| `regex_chars`, `regex_bytes`, `regex_hash`, `regex_expansion_ratio` | Taille, empreinte et expansion de la regex. L'empreinte ne contient pas la regex complète. |
| `regex_num_alternations_proxy`, `regex_num_groups_proxy`, `regex_num_repetitions_proxy`, `regex_max_group_depth_proxy` | Indicateurs approximatifs de complexité de la regex. |
| `index_build_s`, `index_built` | Durée et réussite de la construction de l'index. |
| `guide_init_s`, `guide_built`, `total_compile_s` | Initialisation du guide et durée totale de compilation. |
| `outlines_core_version`, `final_status`, `last_stage`, `exception_type`, `exception_message`, `timeout_seconds` | Version et contexte d'une réussite, erreur ou interruption. |

Les suffixes **`_s` sont en secondes**. Ce fichier permet notamment de distinguer un blocage pendant la création de la regex d'un blocage pendant celle de l'index.

### `timed_out_schemas.jsonl` — schémas interrompus

Ce fichier contient les identifiants, les limites configurées (`timeout_minutes`, `compile_timeout_minutes`, `validation_timeout_minutes`), la durée observée (`elapsed_seconds`), l'étape (`timeout_stage`) et une explication (`notes`).

Il sert à compter les schémas concernés, distinguer compilation et validation et reprendre les runs sans relancer systématiquement les mêmes blocages. Selon le superviseur, certaines entrées décrivent aussi une terminaison anormale ou un signal : toutes ne prouvent pas un dépassement de délai classique.

### `timeout_checkpoints.jsonl` — dernière étape connue

Principalement utilisé pour Outlines, ce fichier conserve `last_stage` et, selon l'enregistrement, le statut final, le temps écoulé et l'exception. Il peut contenir des états de progression ou de fin normale : **ce n'est pas une liste exclusivement composée de timeouts**.

Il aide à localiser un arrêt survenu avant l'écriture du résultat final, notamment lors de la construction de la regex ou de l'index.

### Journaux, fusions et fichiers historiques

| Fichier ou motif | Rôle |
| --- | --- |
| `supervisor.log` | Sorties des processus enfants : schémas lancés, traces d'étapes si activées et messages d'erreur. |
| `resume_run_*.log`, `direct_resume_run_*.log` | Journaux de relance ou de reprise. |
| `tmux_resume_run_*.log`, `tmux_direct_resume_run_*.log`, `tmux_supervisor_resume_run_*.log` | Traces des variantes de reprise lancées via `tmux`. |
| `Kubernetes_launcher_*.log` | Journal du lanceur Kubernetes, placé au niveau du framework. |
| `merge_manifest.json` | Date, framework, datasets inclus/exclus et nombres de lignes des artefacts fusionnés. |
| `MERGE_SOURCES.md` | Présentation lisible des sources de `Github_global` ou `Github_global_no_hard`. |
| `guidance/Github_medium/per_test_results.raw_with_resume_duplicates_20260720.jsonl` | Copie brute historique signalant des doublons de reprise. Utiliser `per_test_results.jsonl` pour l'analyse courante, sans additionner cette copie. |
| `.nfs*` et `outlines/Github_hard_nfs_busy_20260719_152848/` | Reliquats techniques du stockage NFS, sans valeur de résultat supplémentaire. |

## Analyses dérivées

Les runs enrichis, notamment les fusions GitHub et Kubernetes, possèdent aussi des tableaux et des graphiques. Ils sont calculés à partir des résultats et des sources ; ce ne sont pas de nouvelles exécutions.

### `plots/` — statistiques générales et diagnostic

`plots/README.md` décrit les figures et conclusions locales. Les CSV conservent les données des analyses :

| Fichier ou famille | Contenu |
| --- | --- |
| `schema_level_stats.csv` | Table centrale par schéma : caractéristiques, résultats, taux, temps et timeouts. |
| `feature_constraint_rates.csv` | Taux de résultats selon la présence des features. |
| `feature_under_lift.csv`, `feature_over_lift.csv`, `feature_timeout_lift.csv` | Risque associé à une feature par rapport au taux de référence. |
| `feature_pair_rates.csv` | Fréquences et résultats pour des paires de features. |
| `feature_pair_under_lift.csv`, `feature_pair_over_lift.csv`, `feature_pair_timeout_lift.csv` | Risques associés aux combinaisons de deux features. |
| `feature_group_heatmap.csv`, `feature_pair_group_heatmap.csv` | Tables des cartes de chaleur par groupes et combinaisons. |
| `over_rejection_ratio.csv` | Mesures du rejet des instances valides pour l'étude OVER. |
| `phase_timing_summary_by_status.csv` | Synthèse des temps par phase et statut. |
| `timing_by_result_case.csv` | Durées selon le type de résultat. |
| `schema_characteristic_constraint_bins.csv` | Résultats regroupés par classes de caractéristiques des schémas. |
| `slow_completed_constraint_quartiles.csv` | Erreurs selon les quartiles de lenteur des schémas terminés. |
| `timeout_expected_validity.csv` | Répartition des tests concernés par les timeouts selon leur validité attendue. |
| `compile_error_top_causes.csv` | Causes probables regroupées à partir des messages de compilation. |
| `compile_error_top_schema_features.csv` | Features fréquentes des schémas en erreur de compilation. |
| `compile_error_feature_lift.csv` | Surreprésentation des features parmi ces erreurs. |

Les **SVG** visualisent ces analyses : taux et lifts `feature_*`/`feature_pair_*`, cartes de chaleur, distributions et comparaisons des temps, schémas les plus lents. Par exemple, `timeout_by_stage.svg`, `compile_completed_vs_timeout_boxplot.svg`, `top_slowest_schemas.svg` et `tokens_vs_validation_loop.svg` servent au diagnostic des lenteurs. Les figures par cas de résultat comparent notamment compilation et validation.

Un **lift** compare un taux dans un groupe au taux de référence ; une valeur supérieure à 1 indique un risque associé plus élevé. Examiner aussi le nombre de cas : une association ne démontre pas que la feature cause l'erreur.

### `refined_feature_analysis/` — features détaillées et contextes

| Fichier | Contenu |
| --- | --- |
| `refined_schema_features.csv` | Features raffinées au niveau du schéma. |
| `refined_test_features.csv` | Features par test, avec caractéristiques de l'instance, contexte dans le schéma et résultats. |
| `risk_tables/numeric_context_risk.csv` | Risques associés aux contraintes numériques et à leur contexte. |
| `risk_tables/combinator_context_risk.csv` | Risques associés aux combinateurs `allOf`, `anyOf`, `oneOf`, etc. |
| `risk_tables/not_context_risk.csv` | Contextes de négation `not`. |
| `risk_tables/patternProperties_context_risk.csv` | Contextes des propriétés définies par motifs. |
| `refined_feature_analysis_report.md` | Rapport de synthèse. |

Les graphiques sont regroupés par familles `numeric/`, `combinators/`, `not/`, `patternProperties/` et `summary/`. Ils montrent les distributions, taux d'erreur et contextes présentant les lifts les plus élevés.

### `refined_feature_analysis_v2/` — analyses conditionnelles

| Fichier | Contenu |
| --- | --- |
| `under_invalid_only_risk.csv` | Risque UNDER uniquement parmi les tests attendus invalides. |
| `over_valid_only_risk.csv` | Risque OVER uniquement parmi les tests attendus valides. |
| `schema_level_context_risk.csv` | Analyse des contextes au niveau du schéma. |
| `top_context_examples.csv` | Exemples de tests et valeurs permettant d'examiner les contextes. |
| `refined_feature_analysis_v2_report.md` | Rapport des analyses conditionnelles. |

Les graphiques présentent risques conditionnels, croisements de caractéristiques, supports et cooccurrences. Les noms `under_invalid_only_*`, `over_valid_only_*`, `support_vs_*`, `cooccurrence_*` et `top20_*` indiquent le périmètre de la figure.

**Emplacement des graphiques raffinés :** dans les fusions GitHub, ils sont notamment sous `refined_feature_analysis/plots/` et `refined_feature_analysis_v2/plots/`. Dans Kubernetes, ils sont sous `plots/refined_feature_analysis/` et `plots/refined_feature_analysis_v2/`. Les CSV restent dans les dossiers d'analyse correspondants.

## Lire le profilage token par token

Pour XGrammar, le runner charge le tokenizer et initialise le moteur, lit le fichier source, puis compile la grammaire du schéma. Pour chaque test, il sérialise l'instance avec `json.dumps`, la tokenise, réinitialise le matcher et rejoue les tokens.

Deux opérations expliquent le coût de cette boucle :

1. `compute_mask` calcule les tokens du vocabulaire autorisés par la grammaire à la position courante.
2. `commit_token` présente le token réel de l'instance au matcher et fait avancer son état si le token est accepté.

Dans ce benchmark, l'instance est déjà connue : on teste sa compatibilité avec la grammaire. Il ne s'agit pas de générer une réponse avec un LLM. En génération contrainte, le masque servirait à restreindre les tokens que le modèle peut choisir.

`engine_tokenizer_load_us` mesure le chargement de l'outil tokenizer au début du runner, tandis que `tokenize_us` mesure son application à une instance précise. Pour convertir une durée : **secondes = microsecondes / 1 000 000**. Les temps `compute_mask_us` et `commit_token_us` décrivent des opérations internes à `validation_loop_us` ; ne pas les additionner une seconde fois à cette durée globale.

### Exemples historiques XGrammar

Les exemples suivants proviennent de l'ancienne note de profilage. Ils illustrent la lecture des mesures ; ils ne constituent pas une nouvelle mesure ni une vérification de l'état actuel des CSV.

| Mesure | Test valide terminé : `Github_easy---o9778.json::test_00000` | Test interrompu : `Github_easy---o9966.json::test_00002` |
| --- | --- | --- |
| Validité attendue | `valid` | `invalid` |
| Résultat | `passed`, `accepted=True` | `timeout`, décision absente |
| `result_available` | `True` | `False` |
| Chargement du tokenizer | 1 328 740 µs, soit environ 1,33 s | 1 485 862 µs |
| Initialisation du moteur | 838 528 µs | 836 235 µs |
| Chargement du schéma | 613 µs | 213 µs |
| Compilation | 111 397 261 µs, soit environ 111,40 s | Mesure finale absente |
| Tokenisation de l'instance | 1 000 µs | Mesure absente |
| Boucle de validation | 6 387 µs, soit environ 0,0064 s | Mesure absente |
| Tokens vérifiés | 54 sur 54 | Pas de résultat final de validation |
| Diagnostic | Coût dominé par la compilation. | Checkpoint `stage=compile_grammar` et arrêt après environ 1 200,114 s. |

Le second cas montre pourquoi une compilation sans mesure finale n'est pas une compilation instantanée : elle n'avait pas rendu la main avant l'interruption. L'instance attendue invalide ne peut être classée ni comme correctement rejetée ni comme UNDER, faute de décision.

### Observations conservées des relances XGrammar

Ce tableau reprend un **état historique partiel** des profils `Github_easy` et `Github_trivial`, tel que décrit dans l'ancienne note. Les effectifs ne décrivent pas nécessairement les runs complets conservés aujourd'hui.

| Dataset | Limite de cette relance par schéma | Lignes profilées | Résultats normaux | Lignes timeout | Schémas uniques en timeout |
| --- | --- | ---: | --- | ---: | ---: |
| `Github_easy` | 20 minutes | 151 | 45 `passed`, 4 `failed` | 102 | 20 |
| `Github_trivial` | 10 minutes | 1 174 | 1 033 `passed`, 121 `failed` | 9 | 3 |

Dans cet état historique, les timeouts identifiés pour ces deux datasets survenaient pendant `compile_grammar`. Les trois schémas de `Github_trivial` concernés étaient `Github_trivial---o9790.json`, `Github_trivial---o9912.json` et `Github_trivial---o9933.json`.

Deux autres schémas `Github_trivial` avaient été interrompus avec `exit_-15` avant le délai : `Github_trivial---o64546.json` conservait des checkpoints `compiled`/`running_validation`, et `Github_trivial---o67212.json` un checkpoint `running_compile_grammar`. Ces interruptions doivent rester distinctes des dépassements de délai.

Pour les comptages, distinguer **lignes de tests**, **schémas uniques** et **tentatives de reprise**. Un journal historique de timeouts peut contenir plusieurs tentatives pour le même schéma ; compter les `schema_id` uniques au sein d'un framework/dataset lorsqu'on cherche le nombre de schémas touchés. Pour des statistiques actuelles, recalculer les effectifs à partir des fichiers du run choisi.

## Étudier un timeout

1. Repérer le schéma dans `timed_out_schemas.jsonl` : délai, durée observée, étape et notes. Distinguer arrêt par signal et limite de temps atteinte.
2. Retrouver le même `schema_id` dans `timeout_checkpoints.jsonl`, s'il existe, pour examiner la dernière étape connue et l'exception.
3. Pour Outlines, lire `schema_compile_profile.csv` : la regex a-t-elle été construite ? L'index ou le guide a-t-il terminé ? Quelle est la taille de la regex ?
4. Consulter `timing_profile.csv` : compilation terminée, validation commencée, tokens vérifiés, mesures finales ou partielles.
5. Lire les traces correspondantes dans `supervisor.log` et les journaux de reprise.
6. Retrouver les entrées via `schema_path` et `test_index`, puis comparer ce cas aux schémas terminés à l'aide des statistiques et des features raffinées.

La dernière étape connue localise l'interruption sans nécessairement en établir la cause. Une mesure manquante ne signifie pas une durée nulle. L'absence de fichier de timeout ne suffit pas non plus à déclarer un run complet.

## Production et réutilisation

- `run_per_test_framework_logging.py` produit résultats et profilage ; les superviseurs et la reprise résiliente ajoutent le suivi des interruptions.
- `analyze_dataset_statistics.py`, `analyze_compile_error_causes.py` et les analyses spécialisées produisent les tableaux et figures.
- `analyze_refined_features_v2.py` exploite les tables raffinées existantes. Le module d'extraction initial `analyze_refined_features.py` est actuellement absent du dossier des scripts ; il faut rétablir ou remplacer cette dépendance pour régénérer les features via les scripts qui l'importent.
- Les notebooks consomment les tables et les graphiques. Les scripts de prédiction rapprochent les résultats par test des sources pour construire les cibles et les modèles.

Les scripts d'indexation peuvent également produire un index global et des synthèses, mais ces fichiers ne sont pas présents à la racine de `results` dans l'état décrit ici. Ce README documente les artefacts existants ; sa rédaction n'a pas relancé les validations ni modifié les résultats.
