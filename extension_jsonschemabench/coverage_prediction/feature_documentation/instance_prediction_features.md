# Instance Prediction Features

Features d instance actuellement utilisees par au moins un modele predictif filtre.

## Choix de nettoyage

- Les buckets redondants d instance ont ete retires des listes actives.
- `instance_num_numeric_values` et `instance_number_count` sont remplaces par `instance_numeric_value_count`.
- `instance_max_object_depth` compte maintenant chaque objet rencontre, meme dans un tableau racine.
- `instance_max_container_depth` est disponible dans les datasets pour la profondeur generale objets + tableaux, mais il n est utilise que s il est retenu dans une liste de features.

## Features Actives

| feature | used_by | meaning |
|---|---|---|
| `array_nested_object_count` | guidance/over;outlines/under;xgr/under;xgr/over | Feature derivee utilisee par au moins un modele predictif. |
| `instance_array_count` | guidance/over;outlines/under;xgr/under;xgr/over | Feature derivee utilisee par au moins un modele predictif. |
| `instance_boolean_count` | outlines/under;xgr/under;xgr/over | Feature derivee utilisee par au moins un modele predictif. |
| `instance_empty_array_count` | xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `instance_empty_object_count` | outlines/under;xgr/under;xgr/over | Feature derivee utilisee par au moins un modele predictif. |
| `instance_has_int32_boundary_risk` | guidance/over;outlines/under;xgr/under;xgr/over | Feature derivee utilisee par au moins un modele predictif. |
| `instance_has_large_integer` | guidance/over;outlines/under;xgr/under;xgr/over | Feature derivee utilisee par au moins un modele predictif. |
| `instance_has_unmatched_keys` | guidance/over;outlines/over | Feature derivee utilisee par au moins un modele predictif. |
| `instance_integer_count` | guidance/over;outlines/under;xgr/under;xgr/over | Feature derivee utilisee par au moins un modele predictif. |
| `instance_matching_pattern_keys_count` | outlines/under;outlines/over;xgr/under;xgr/over | Nombre brut de cles de l instance qui matchent patternProperties. |
| `instance_max_abs_numeric_value` | guidance/over;outlines/under;xgr/under;xgr/over | Feature derivee utilisee par au moins un modele predictif. |
| `instance_max_array_length` | guidance/over;outlines/under;xgr/under;xgr/over | Longueur maximale brute d un tableau dans l instance. |
| `instance_max_object_depth` | guidance/over;outlines/under;xgr/under;xgr/over | Profondeur maximale des objets dans l instance. Un objet racine vaut 1; un objet dans un tableau racine vaut aussi 1; les tableaux ne creent pas de niveau objet. |
| `instance_nested_array_count` | xgr/under;xgr/over | Feature derivee utilisee par au moins un modele predictif. |
| `instance_null_count` | outlines/under;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `instance_num_properties` | guidance/over;outlines/under;outlines/over;xgr/under;xgr/over | Feature derivee utilisee par au moins un modele predictif. |
| `instance_numeric_value_count` | guidance/over;outlines/under;xgr/under;xgr/over | Nombre de valeurs numeriques dans l instance, entiers et flottants, booleens exclus. Remplace instance_num_numeric_values / instance_number_count. |
| `instance_string_count` | guidance/over;outlines/under;xgr/under;xgr/over | Nombre brut de chaines dans l instance. |
| `instance_string_max_length` | guidance/over;outlines/under;xgr/under;xgr/over | Longueur maximale brute des chaines dans l instance. |
| `instance_string_total_length` | guidance/over;outlines/under;xgr/under;xgr/over | Somme des longueurs des chaines dans l instance. |
| `instance_total_array_items` | guidance/over;outlines/under;xgr/under;xgr/over | Nombre total brut d elements de tableaux dans l instance. |
| `instance_total_object_properties_recursive` | guidance/over;outlines/under;xgr/under;xgr/over | Nombre total brut de proprietes objet dans l instance, recursivement. |

## Buckets Retires

- `instance_matching_pattern_keys_count_bucket`
- `instance_max_array_length_bucket`
- `instance_max_object_depth_bucket`
- `instance_string_count_bucket`
- `instance_string_max_length_bucket`
- `instance_total_array_items_bucket`
- `instance_total_object_properties_recursive_bucket`
