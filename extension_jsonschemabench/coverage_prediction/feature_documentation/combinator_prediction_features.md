# Combinator Prediction Features

Features de combinateurs actuellement utilisees par au moins un modele filtre.

- Les anciens ratios generiques `*_satisfied_branch_ratio` ne sont plus actifs; on garde les ratios alignes `*_ratio_min/max/avg`.
- `allOf_satisfied_all_branch_count` a ete retire car il duplique `allOf_occurrence_satisfied_count`.

| feature | used_by | meaning |
|---|---|---|
| `allOf_branch_count` | xgr/under | nombre total de branches dans les blocs `allOf` du schema. |
| `allOf_count` | outlines/over;xgr/over;xgr/under | nombre d'occurrences du mot-cle `allOf` dans le schema. |
| `allOf_failed_branch_count_for_instance` | xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `allOf_is_satisfied_for_instance` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | indicateur binaire : toutes les occurrences `allOf` observees sont satisfaites par l'instance. |
| `allOf_occurrence_failed_count` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `allOf_occurrence_satisfied_count` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `allOf_ratio_avg` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | moyenne des ratios branches satisfaites / branches totales, calculee occurrence par occurrence pour `allOf`. |
| `allOf_ratio_max` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `allOf_ratio_min` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `allOf_satisfied_branch_count` | xgr/over | Feature derivee utilisee par au moins un modele predictif. |
| `anyOf_branch_count` | outlines/under;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `anyOf_count` | outlines/over | Feature derivee utilisee par au moins un modele predictif. |
| `anyOf_is_satisfied_for_instance` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | indicateur binaire : toutes les occurrences `anyOf` observees satisfont au moins une branche. |
| `anyOf_occurrence_failed_count` | outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `anyOf_occurrence_satisfied_count` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `anyOf_ratio_avg` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | moyenne des ratios branches satisfaites / branches totales, calculee occurrence par occurrence pour `anyOf`. |
| `anyOf_ratio_max` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `anyOf_ratio_min` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `anyOf_satisfied_all_branch_count` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `branches_have_different_type` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | indicateur binaire : au moins un combinator a des branches heterogenes en type declare. |
| `branches_have_properties` | outlines/over;xgr/over | indicateur binaire : au moins une branche de combinator contient des `properties`. |
| `branches_have_required` | outlines/over;xgr/over;xgr/under | indicateur binaire : au moins une branche de combinator contient des champs `required`. |
| `branches_have_same_type` | outlines/over | indicateur binaire : les branches d'un combinator portent sur le meme type JSON. |
| `branches_with_additionalProperties_count` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `branches_with_additionalProperties_false_count` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `branches_with_additionalProperties_ratio` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `branches_with_additionalProperties_schema_count` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `branches_with_additionalProperties_true_count` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `branches_with_not_count` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `branches_with_not_ratio` | outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `branches_with_numeric_count` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `branches_with_numeric_ratio` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `branches_with_properties_count` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `branches_with_properties_ratio` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `branches_with_required_count` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | nombre total de branches de combinator contenant `required`. |
| `branches_with_required_ratio` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | proportion de branches de combinator contenant `required`. |
| `combinator_branch_count_avg` | outlines/over;xgr/over | nombre moyen de branches dans les combinators (`allOf`, `anyOf`, `oneOf`). |
| `combinator_branch_count_max` | outlines/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `combinator_branch_count_min` | outlines/over;xgr/over;xgr/under | nombre minimum de branches observe dans les combinators du schema. |
| `combinator_count` | guidance/over;outlines/over;outlines/under;xgr/under | nombre total de combinators (`allOf`, `anyOf`, `oneOf`) dans le schema. |
| `combinator_depth_avg` | xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `combinator_depth_max` | xgr/under | profondeur maximale selon la convention interne du script : +2 via `properties`, +2 via une branche de combinator, +1 via `not`, +1 via `items`. |
| `combinator_depth_min` | xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `combinator_different_type_count` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | nombre de combinators dont les branches sont heterogenes en type declare. |
| `combinator_different_type_ratio` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | proportion de combinators heterogenes parmi les combinators observes. |
| `combinator_have_additionalProperties_count` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `combinator_have_not_count` | outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `combinator_have_numeric_count` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `combinator_have_properties_count` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `combinator_have_required_count` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | nombre de combinators ayant au moins une branche contenant `required`. |
| `combinator_same_type_count` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | nombre de combinators dont les branches sont homogenes en type declare. |
| `combinator_same_type_ratio` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | proportion de combinators homogenes parmi les combinators observes. |
| `combinator_type` | guidance/over;outlines/over;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `combinator_with_additionalProperties` | outlines/over | Feature derivee utilisee par au moins un modele predictif. |
| `combinator_with_additionalProperties_false` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | indicateur binaire : une branche de combinator contient `additionalProperties: false`. |
| `combinator_with_additionalProperties_schema` | guidance/over;xgr/over;xgr/under | indicateur binaire : une branche de combinator contient `additionalProperties` sous forme de schema. |
| `combinator_with_additionalProperties_true` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | indicateur binaire : une branche de combinator contient `additionalProperties: true`. |
| `oneOf_count` | outlines/over | Feature derivee utilisee par au moins un modele predictif. |
| `oneOf_is_satisfied_for_instance` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | indicateur binaire : toutes les occurrences `oneOf` observees satisfont exactement une branche. |
| `oneOf_occurrence_failed_count` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `oneOf_occurrence_satisfied_count` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `oneOf_ratio_avg` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | moyenne des ratios branches satisfaites / branches totales, calculee occurrence par occurrence pour `oneOf`. |
| `oneOf_ratio_max` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `oneOf_ratio_min` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `oneOf_satisfied_all_branch_count` | guidance/over;outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
