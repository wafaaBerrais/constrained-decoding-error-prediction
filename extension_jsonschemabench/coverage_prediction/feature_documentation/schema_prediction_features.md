# Schema Prediction Features

Features globales de schema actuellement utilisees par au moins un modele predictif filtre.

Notes:

- Aucun bucket `_bucket` n est conserve dans les listes actives.
- `schema_max_depth` est calcule avec `depth(child)=depth(parent)+1` pour chaque sous-schema.
- Les dependances sont separees entre `dependentSchemas`, `dependentRequired` et `dependencies`.
- Les features de complexite par noeud dependent de listes manuelles dans `analyze_refined_features.py`.
- Les anciens alias/cas ambigus retires incluent `type_validation_case`, `schema_dependency_keyword_count`, `schema_advanced_keywords_present`, `patternProperties_regex_complexity_score` et les ratios generiques `*_satisfied_branch_ratio`.

| feature | used_by | meaning |
|---|---|---|
| `any_visited_type_mismatch` | outlines/under;xgr/under | Booleen: au moins une verification type visitee ne correspond pas a l instance; ce n est pas un echec global sous anyOf/oneOf/not. |
| `complex_keywords_same_node_avg` | guidance/over;outlines/under;xgr/over;xgr/under | nombre moyen de mots-cles complexes presents sur un meme noeud du schema. |
| `complex_keywords_same_node_max` | guidance/over;outlines/under;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `logical_complex_keywords_same_node_count` | guidance/over;outlines/under;xgr/over;xgr/under | Maximum de mots-cles logiques complexes sur un meme noeud, selon une liste manuelle. |
| `object_complex_keywords_same_node_count` | guidance/over;outlines/under;xgr/over;xgr/under | Maximum de mots-cles objet complexes sur un meme noeud, selon une liste manuelle. |
| `regex_complex_keywords_same_node_count` | guidance/over;outlines/under;xgr/over;xgr/under | Maximum de mots-cles regex/string complexes sur un meme noeud, selon une liste manuelle. |
| `required_property_count_total` | guidance/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `schema_advanced_keyword_count` | outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `schema_boolean_schema_count` | outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `schema_format_keyword_count` | outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `schema_keyword_count` | guidance/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `schema_legacy_dependencies_count` | outlines/under;xgr/over | Nombre d occurrences du mot-cle historique dependencies. |
| `schema_max_depth` | guidance/over;outlines/under;xgr/over;xgr/under | Profondeur maximale du schema avec depth(child)=depth(parent)+1, racine a 0. |
| `schema_nullable_type_count` | outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `schema_ref_count` | outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `schema_total_properties_recursive` | guidance/over;outlines/under;xgr/over;xgr/under | nombre total de proprietes declarees dans tout le schema, en comptant recursivement les sous-objets. |
| `schema_type_union_count` | outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `type_mismatch_count` | outlines/under;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
