# Features raffinees pour l'analyse des erreurs

Ce document resume le travail fait sur les features raffinees dans
`extension_jsonschemabench`, en particulier pour le run:

`extension_jsonschemabench/results/per_dataset_runs/outlines/Github_medium`

L'objectif etait de depasser les features globales simples du schema
(`has_anyOf`, `has_patternProperties`, `nb_keywords`, etc.) pour mieux
expliquer les erreurs observees avec `outlines`.

## Pourquoi ajouter des features raffinees

Les premieres analyses montraient quels mots-cles JSON Schema etaient
associes a des erreurs, mais pas assez de contexte pour comprendre pourquoi.
Par exemple, savoir qu'un schema contient `minimum` est moins informatif que
de savoir si le test est juste sous la borne, si le champ est requis, si le
type cible est `number`, ou si une valeur par defaut est presente.

Les features raffinees ajoutent donc des contextes plus proches du mecanisme
de validation:

- contexte numerique: bornes, type cible, champ requis, valeurs par defaut;
- contexte `patternProperties`: regex, `additionalProperties`, cles qui
  matchent ou non les patterns;
- contexte `not`: contenu du sous-schema nie et mots-cles voisins;
- contexte combinateurs: type de combinateur, nombre de branches, branches
  satisfaites, proprietes qui se recouvrent, enums, `required`, etc.;
- cooccurrences locales: mots-cles presents dans le meme noeud du schema.

## Scripts utilises

Deux scripts generent les tables et les graphiques.

### Analyse v1

Script:

```bash
extension_jsonschemabench/scripts/analyze_refined_features.py
```

Commande utilisee pour regenerer les resultats dans le dossier du run:

```bash
.venv/bin/python extension_jsonschemabench/scripts/analyze_refined_features.py \
  --framework outlines \
  --dataset Github_medium \
  --output-data-dir extension_jsonschemabench/results/per_dataset_runs/outlines/Github_medium/refined_feature_analysis \
  --output-plot-dir extension_jsonschemabench/results/per_dataset_runs/outlines/Github_medium/plots/refined_feature_analysis
```

Sorties principales:

- `refined_schema_features.csv`: une ligne par schema;
- `refined_test_features.csv`: une ligne par test;
- `risk_tables/*.csv`: tables de risque par famille de features;
- `refined_feature_analysis_report.md`: rapport automatique;
- `plots/refined_feature_analysis/`: graphiques SVG.

### Analyse v2

Script:

```bash
extension_jsonschemabench/scripts/analyze_refined_features_v2.py
```

Commande utilisee:

```bash
.venv/bin/python extension_jsonschemabench/scripts/analyze_refined_features_v2.py \
  --dataset Github_medium \
  --input-dir extension_jsonschemabench/results/per_dataset_runs/outlines/Github_medium/refined_feature_analysis \
  --output-data-dir extension_jsonschemabench/results/per_dataset_runs/outlines/Github_medium/refined_feature_analysis_v2 \
  --output-plot-dir extension_jsonschemabench/results/per_dataset_runs/outlines/Github_medium/plots/refined_feature_analysis_v2
```

La v2 separe mieux les deux types d'erreurs:

- UNDER parmi les tests invalides seulement;
- OVER parmi les tests valides seulement.

Cela evite de melanger les denominateurs. Par exemple, les erreurs UNDER
doivent etre comparees aux tests attendus invalides, pas a tous les tests.

## Donnees analysees

Pour `outlines/Github_medium`, les scripts ont analyse:

- 1736 schemas;
- 8542 tests;
- 5602 tests invalides;
- 2940 tests valides.

Dans le rapport v1:

- taux UNDER global: 0.0764;
- taux OVER global: 0.1147.

Dans le rapport v2, avec les bons denominateurs:

- taux UNDER parmi les tests invalides: 0.1166;
- taux OVER parmi les tests valides: 0.3333.

## Resultats principaux

### 1. Les erreurs UNDER sont surtout liees aux contraintes numeriques

Les contextes numeriques sont les signaux les plus forts pour UNDER. Les cas
les plus marques sont:

| Contexte | Taux UNDER | Lift | Support |
| --- | ---: | ---: | ---: |
| `numeric_boundary_case=below_min` | 0.715 | 6.13 | 568 tests invalides, 194 schemas |
| `numeric_has_default=true` | 0.632 | 5.42 | 427 tests invalides, 105 schemas |
| `numeric_target_type=mixed` | 0.545 | 4.68 | 253 tests invalides, 60 schemas |
| `numeric_boundary_case=above_max` | 0.484 | 4.15 | 122 tests invalides, 63 schemas |
| `numeric_target_type=number` | 0.474 | 4.07 | 392 tests invalides, 93 schemas |
| `numeric_property_required=true` | 0.455 | 3.91 | 784 tests invalides, 173 schemas |

Interpretation: `outlines` semble plus souvent accepter des instances qui
devraient etre rejetees quand l'erreur attendue depend d'une borne numerique,
en particulier autour de `minimum`/`maximum`, des champs requis, des types
numeriques et des valeurs par defaut.

### 2. Les erreurs OVER ressortent fortement avec `patternProperties`

Pour OVER, les signaux les plus forts viennent de `patternProperties`,
`additionalProperties` et des regex.

| Contexte | Taux OVER | Lift | Support |
| --- | ---: | ---: | ---: |
| `patternProperties_regex_has_alternation=true` | 1.000 | 3.00 | 28 tests valides, 15 schemas |
| `additionalProperties_value=false` | 0.983 | 2.95 | 119 tests valides, 66 schemas |
| `patternProperties_has_additionalProperties=true` | 0.975 | 2.93 | 121 tests valides, 68 schemas |
| `instance_has_unmatched_keys=true` | 0.938 | 2.81 | 340 tests valides, 243 schemas |
| `instance_matching_pattern_keys_count_bucket=2` | 0.921 | 2.76 | 76 tests valides, 45 schemas |
| `patternProperties_regex_has_anchor=true` | 0.893 | 2.68 | 169 tests valides, 93 schemas |

Interpretation: `outlines` rejette souvent des instances pourtant valides
quand la validite depend de l'interaction entre cles d'objet, regex de
`patternProperties` et politique `additionalProperties`.

### 3. Les combinateurs expliquent aussi des erreurs OVER

Les combinateurs ne sont pas seulement importants par leur presence. Les
features raffinees montrent que le nombre de branches et les branches
satisfaites donnent un signal plus utile.

| Contexte | Taux OVER | Lift | Support |
| --- | ---: | ---: | ---: |
| `combinator_branch_count_bucket=6+` | 0.905 | 2.71 | 21 tests valides, 14 schemas |
| `combinator_type=mixed` | 0.789 | 2.37 | 76 tests valides, 42 schemas |
| `anyOf_satisfied_branch_count=2` | 0.750 | 2.25 | 20 tests valides, 12 schemas |
| `branches_overlapping_properties=true` | 0.733 | 2.20 | 60 tests valides, 36 schemas |
| `branches_have_enum=true` | 0.722 | 2.17 | 90 tests valides, 52 schemas |
| `branches_have_properties=true` | 0.706 | 2.12 | 143 tests valides, 80 schemas |

Interpretation: les erreurs OVER augmentent quand la generation doit respecter
des interactions fines entre branches de `anyOf`, `oneOf` ou `allOf`.

### 4. `not` n'a pas donne de signal robuste dans cette analyse

Dans la v1, aucun contexte `not` non-low-support ne depasse les seuils de
support. Cela ne veut pas dire que `not` n'est jamais un probleme, mais les
donnees `Github_medium` disponibles ne donnent pas un signal assez stable pour
en faire une conclusion forte.

## Comparaison test-level et schema-level

La v2 compare aussi les lifts au niveau test et au niveau schema.

Pour UNDER, les signaux numeriques restent forts au niveau schema:

- `numeric_boundary_case=below_min`: lift test 6.13, lift schema 5.07;
- `numeric_has_default=true`: lift test 5.42, lift schema 5.06;
- `numeric_property_required=true`: lift test 3.91, lift schema 4.53.

Pour OVER, plusieurs signaux `patternProperties` restent aussi visibles au
niveau schema:

- `patternProperties_regex_has_alternation=true`: lift test 3.00, lift schema 2.80;
- `additionalProperties_value=false`: lift test 2.95, lift schema 2.75;
- `patternProperties_has_additionalProperties=true`: lift test 2.93, lift schema 2.71.

Quand le lift test est fort mais le lift schema est plus faible, cela veut dire
que l'effet peut etre amplifie par quelques schemas qui ont beaucoup de tests.

## Ou regarder les resultats

Tables:

- `extension_jsonschemabench/results/per_dataset_runs/outlines/Github_medium/refined_feature_analysis/`
- `extension_jsonschemabench/results/per_dataset_runs/outlines/Github_medium/refined_feature_analysis_v2/`

Rapports automatiques:

- `extension_jsonschemabench/results/per_dataset_runs/outlines/Github_medium/refined_feature_analysis/refined_feature_analysis_report.md`
- `extension_jsonschemabench/results/per_dataset_runs/outlines/Github_medium/refined_feature_analysis_v2/refined_feature_analysis_v2_report.md`

Plots:

- `extension_jsonschemabench/results/per_dataset_runs/outlines/Github_medium/plots/refined_feature_analysis/`
- `extension_jsonschemabench/results/per_dataset_runs/outlines/Github_medium/plots/refined_feature_analysis_v2/`

Les deux dossiers de plots contiennent 93 fichiers SVG au total:

- 48 plots pour la v1;
- 45 plots pour la v2.

## Conclusion

Les features raffinees ont permis de passer d'une analyse par mots-cles
generaux a une analyse contextualisee des erreurs.

Les conclusions les plus solides pour `outlines/Github_medium` sont:

- UNDER est principalement associe aux contraintes numeriques et aux cas de
  frontiere (`below_min`, `above_max`, types numeriques, champs requis);
- OVER est principalement associe a `patternProperties`, `additionalProperties`
  et aux regex;
- les combinateurs contribuent surtout aux OVER quand plusieurs branches ou
  branches interactives sont impliquees;
- les signaux `not` ne sont pas suffisamment robustes sur ce dataset;
- les resultats restent correlationnels: pour prouver la causalite, il faut
  ensuite utiliser HDD ou des mutations controlees de schemas.

