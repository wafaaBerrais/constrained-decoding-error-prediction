# Extension JSONSchemaBench — étude des limites du décodage contraint

## Contexte et objectif du stage

Les LLM sont utilisés pour produire des données JSON structurées. Une sortie syntaxiquement correcte ne suffit cependant pas : elle doit aussi respecter les contraintes du JSON Schema fourni, par exemple les champs requis, les bornes numériques ou les interactions entre plusieurs sous-schémas.

Les frameworks de **décodage contraint** (*constrained decoding*) guident la génération en limitant les tokens autorisés à partir d'une grammaire ou d'un schéma. L'expressivité de JSON Schema rend cette prise en charge difficile : certaines contraintes sont mal supportées, certaines instances sont acceptées ou rejetées à tort, et certains schémas entraînent des compilations longues ou interrompues.

**L'objectif du stage est d'étudier finement les limites de ces frameworks pour la génération JSON, de caractériser leurs erreurs de conformité et d'identifier des configurations à risque interprétables.** Le projet cherche à aller au-delà d'un score global : quelles contraintes sont associées aux erreurs, dans quels contextes, et peut-on prédire ces erreurs sur des schémas non vus ?

L'étude s'appuie sur les schémas, instances et validités attendues de JSONSchemaBench/MaskBench. Elle porte sur trois frameworks : **Guidance / LLGuidance**, **Outlines** et **XGrammar (`xgr`)**. Ce dossier contient l'extension d'exécution et d'analyse développée autour du benchmark existant.

## Travail réalisé

### 1. Observer les décisions des frameworks par test

Nous avons ajouté un runner qui exécute les couples schéma–instance pour chaque framework et enregistre la décision obtenue, les identifiants du test et les erreurs éventuelles. La décision est comparée à la validité attendue du benchmark.

| Cas | Comportement observé |
| --- | --- |
| Résultat correct | Instance valide acceptée, ou instance invalide rejetée. |
| **UNDER — sous-contrainte** | Instance invalide acceptée : le framework est trop permissif. |
| **OVER — sur-contrainte** | Instance valide rejetée : le framework est trop restrictif. |
| Erreur de compilation ou interruption | Le framework ne fournit pas nécessairement de décision exploitable ; ces cas sont identifiés séparément. |

Les tests rejouent des instances connues avec les moteurs du benchmark. Ils étudient leur comportement de validation sous contraintes ; ils ne constituent pas une campagne de génération libre de réponses par un LLM.

Les runs couvrent les datasets GitHub disponibles (`Github_trivial`, `Github_easy`, `Github_medium`, `Github_hard`, `Github_ultra`) et Kubernetes, avec un périmètre variable selon le framework et l'état des exécutions. Les analyses globales Outlines conservées excluent `Github_hard`.

### 2. Mesurer les coûts et diagnostiquer les interruptions

Nous avons ajouté le profilage des étapes : chargement, compilation de la grammaire, tokenisation et validation token par token. Pour Outlines, le suivi distingue aussi la construction de la regex, de l'index et du guide.

Les superviseurs imposent des délais par schéma, permettent de reprendre les runs et conservent les étapes atteintes avant interruption. Les CSV de temps, les checkpoints et les journaux servent à distinguer les blocages de compilation des lenteurs de validation et des autres arrêts de processus.

### 3. Explorer les erreurs et construire des features plus précises

L'analyse exploratoire a d'abord rapproché les erreurs de caractéristiques simples : présence de mots-clés, compteurs et profondeur des schémas. Ces premiers signaux ont orienté le feature engineering vers des contextes plus détaillés :

- contraintes numériques et cas de frontière, comme une valeur sous un minimum ou au-dessus d'un maximum ;
- structure des objets, propriétés requises ou supplémentaires et `patternProperties` ;
- chaînes, expressions régulières, tableaux et énumérations ;
- combinateurs `allOf`, `anyOf`, `oneOf`, négation `not` et branches satisfaites ;
- interactions entre les caractéristiques du schéma et celles de l'instance.

Les analyses raffinées distinguent notamment le risque UNDER **parmi les tests invalides** et le risque OVER **parmi les tests valides**. Elles examinent les supports, les lifts et les résultats au niveau du test et du schéma pour éviter qu'un petit nombre de schémas très représentés domine l'interprétation.

### 4. Apprendre à prédire UNDER et OVER

Nous avons comparé des modèles de **régression logistique**, **Random Forest**, **HistGradientBoosting** et **LightGBM**. Les modèles sont séparés par framework et par cible. Les partitions d'apprentissage, de validation et de test sont regroupées par `schema_id`, afin que les tests d'un même schéma restent dans une seule partition.

Ces modèles servent à mesurer le signal prédictif et à identifier les features utiles. Le filtrage combine les importances, les features utilisées par les règles et des choix de domaine, puis retire des variables redondantes ou peu informatives. Les modèles sont ensuite réentraînés sur les listes simplifiées.

Cinq modèles principaux sont retenus dans la synthèse finale : Guidance OVER, Outlines UNDER/OVER et XGR UNDER/OVER. Guidance UNDER n'a pas de modèle appris, car les données de modélisation correspondantes ne contiennent aucun cas positif.

### 5. Extraire des règles lisibles et préparer l'analyse causale

Des **arbres de décision peu profonds** ont été entraînés sur les features retenues afin d'exporter des règles, des arbres graphiques et des exemples de configurations à risque. Ils sont distincts des modèles prédictifs principaux : les règles ne sont pas une traduction exacte des Random Forest ou de LightGBM.

Les analyses font notamment ressortir les contraintes numériques pour certaines erreurs UNDER et les interactions entre propriétés, regex et combinateurs pour certaines erreurs OVER. Les contextes et performances varient selon le framework et le dataset.

Un outil de minimisation HDD a également été ajouté pour réduire des schémas tout en cherchant à conserver un désaccord Outlines. Il fournit un moyen d'examiner les contraintes impliquées ; l'existence de cet outil ne signifie pas que toutes les règles ont été validées causalement.

### 6. Étudier Kubernetes avec deux protocoles

| Expérience | Question | Emplacement |
| --- | --- | --- |
| **Évaluation externe** | Les modèles appris sur GitHub prédisent-ils aussi les erreurs sur Kubernetes, sans réentraînement ? | [`coverage_prediction/external_eval/`](coverage_prediction/external_eval/) |
| **Entraînement sur Kubernetes** | Peut-on apprendre sur une partie des schémas Kubernetes et prédire les erreurs sur une autre partie ? | [`coverage_prediction/kubernetes_eval/`](coverage_prediction/kubernetes_eval/) |

Ces expériences sont complémentaires et restent séparées. Les résultats externes enregistrés montrent une généralisation variable selon les frameworks ; ils concernent les modèles prédictifs chargés par le script d'évaluation, **pas directement les arbres explicatifs**.

Les tables Kubernetes évaluées ne contiennent pas de cas UNDER positifs : elles permettent d'observer les faux positifs, mais pas de mesurer la détection d'erreurs UNDER. Les détails des scores, des modèles chargés et des limites de comparaison sont dans le [guide Coverage Prediction](coverage_prediction/README.md).

## Structure du projet

L'extension se situe dans le dépôt `jsonschemabench`. Les fichiers sources associant schémas et tests sont généralement sous `maskbench/data/` ; les résultats les référencent par leurs chemins et identifiants.

```text
jsonschemabench/
├── maskbench/                         # Moteurs et données du benchmark
│   └── data/                          # Documents schéma + tests
├── data/                              # Corpus et archives présents dans le dépôt
└── extension_jsonschemabench/
    ├── README.md                      # Objectif, démarche et orientation
    ├── scripts/
    │   └── README.md                  # Description de chaque script
    ├── results/
    │   ├── README.md                  # Résultats, temps et diagnostic des timeouts
    │   └── per_dataset_runs/
    │       ├── guidance/
    │       ├── outlines/
    │       └── xgr/
    ├── coverage_prediction/
    │   ├── README.md                  # Méthodologie et guide des artefacts
    │   ├── modeles_predictifs/
    │   │   ├── guidance/
    │   │   ├── outlines/
    │   │   └── xgr/
    │   ├── feature_documentation/
    │   ├── feature_filter/
    │   ├── rules/
    │   ├── external_eval/
    │   ├── kubernetes_eval/
    │   └── slides/
    ├── visualisation_etudes_frameworks.ipynb
    ├── visualisation_etudes_frameworks_grouped.ipynb
    ├── README_features_raffinees.md
    └── REFINED_FEATURES_README.md
```

| Élément | Rôle et document de référence |
| --- | --- |
| [`scripts/`](scripts/README.md) | Exécution des frameworks, supervision, analyses, entraînement, évaluation et minimisation. Le README décrit chaque script. |
| [`results/`](results/README.md) | Résultats par framework/dataset : JSONL par test, CSV de temps, timeouts, journaux et analyses dérivées. |
| [`coverage_prediction/`](coverage_prediction/README.md) | Données de modélisation, modèles retenus, sélection des features, règles et évaluations. |
| [`feature_documentation/`](coverage_prediction/feature_documentation/README.md) | Définition et justification des features de prédiction. |
| [`rules/`](coverage_prediction/rules/README.md) | Arbres interprétables, règles exportées et performances associées. |
| [Notebook de visualisation](visualisation_etudes_frameworks.ipynb) et [variante groupée](visualisation_etudes_frameworks_grouped.ipynb) | Exploration des résultats des frameworks et des analyses raffinées. |
| [`README_features_raffinees.md`](README_features_raffinees.md) | Étude détaillée historique d'Outlines/Github_medium ; certains chemins de résultats ne sont plus présents. |
| [`REFINED_FEATURES_README.md`](REFINED_FEATURES_README.md) | Dictionnaire exploratoire et propositions initiales de sélection. Certaines recommandations précèdent le filtrage final. |
| [`slides/`](coverage_prediction/slides/) | Présentation du stage, version Markdown, diaporama et notes orales. |

Le présent README sert de point d'entrée. Les descriptions des fichiers, colonnes, scripts et métriques restent dans les guides spécialisés pour éviter de les maintenir en double.

## État actuel et limites

Le projet fournit une chaîne allant des résultats de validation aux modèles et aux règles interprétables. Les associations observées aident à cibler les configurations à examiner, mais ne constituent pas des lois universelles ni des preuves de causalité.

Quelques points doivent être pris en compte avant une nouvelle exécution ou une comparaison des scores :

- Les modèles utilisent des features du **schéma et de l'instance**. Une alerte fondée uniquement sur le schéma avant génération demande une adaptation.
- La validation croisée enregistrée correspond à des listes de features antérieures au dernier nettoyage ; elle doit être recalculée pour caractériser les modèles finaux.
- Pour XGR, `models/` et `models_recovered/` sont chargés dans un ordre différent selon les scripts. L'évaluation externe OVER enregistrée utilise un seuil différent de celui du réentraînement final. Il faut harmoniser le chargement avant une nouvelle comparaison.
- `scripts/analyze_refined_features.py` est actuellement absent alors qu'il est importé par le script de construction des modèles. Cette dépendance doit être rétablie ou remplacée pour relancer les étapes concernées.
- Les rapports historiques et les slides reflètent les expériences disponibles à leur rédaction. Les précisions du README de Coverage Prediction distinguent les arbres explicatifs, les modèles principaux et leurs versions.

## Perspectives

### Consolider la reproductibilité et l'évaluation

Rétablir les dépendances manquantes, unifier la résolution des modèles et associer chaque résultat à une version de framework, un modèle, une liste de features et un protocole explicites. Recalculer ensuite la validation croisée et l'évaluation externe des modèles finaux.

Étendre l'évaluation à d'autres datasets et rechercher des corpus comportant des erreurs UNDER positives. Étudier les variations de précision, de rappel et de seuil selon les domaines, plutôt que de supposer qu'un seuil se transfère automatiquement.

### Vérifier les mécanismes derrière les règles

Utiliser la minimisation HDD et des mutations contrôlées pour isoler les contraintes impliquées dans les erreurs. Comparer des cas proches où l'on modifie une borne, une propriété ou une branche de combinateur. Compléter cette analyse par des ablations de features pour mesurer ce qui apporte réellement du signal.

### Exploiter les résultats pour la génération avec les LLM

Les pistes présentées dans les slides sont :

- construire des alertes sur les schémas à risque avant génération, en sélectionnant des features disponibles sans connaître l'instance future ;
- générer des tests ciblés et des contre-exemples autour des bornes numériques, de `patternProperties`, d'`additionalProperties` et des combinateurs ;
- enrichir les prompts et les procédures de validation avec des cas limites identifiés ;
- aider au choix du framework ou d'une stratégie de validation selon les contraintes du schéma ;
- prolonger le diagnostic des regex et de la compilation pour anticiper les blocages.

Ces usages sont des **perspectives à développer et à évaluer**, pas des fonctionnalités déjà garanties par les règles actuelles.

## Pour commencer

1. Consulter le [guide des résultats](results/README.md) pour comprendre les observations et les timeouts.
2. Ouvrir les notebooks pour explorer les analyses disponibles.
3. Lire le [guide des prédictions](coverage_prediction/README.md) pour les modèles, features, règles et expériences Kubernetes.
4. Consulter le [catalogue des scripts](scripts/README.md) avant de lancer ou régénérer une étape.

Depuis la racine `jsonschemabench`, l'aide d'un script présente ses arguments, une fois ses dépendances disponibles :

```bash
.venv/bin/python extension_jsonschemabench/scripts/run_dataset_with_timeouts.py --help
```

La présentation du contexte et des perspectives s'appuie sur les [slides du stage](coverage_prediction/slides/coverage_prediction_rules_slides.md) et les [notes orales](coverage_prediction/slides/coverage_prediction_rules_speaker_notes.md). Le [README du dépôt](../README.md) décrit le benchmark de base.
