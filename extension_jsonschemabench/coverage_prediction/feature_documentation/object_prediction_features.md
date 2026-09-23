# Object Prediction Features

Features objet actuellement utilisees par au moins un modele filtre.

- `object_additionalProperties_value` a ete retire des features actives; `additionalProperties_mode` porte le signal global conserve.
- Les compteurs `object_required_subset_valid_context_count`, `object_required_subset_invalid_context_count` et `object_has_required_outside_properties` sont conserves.

| feature | used_by | meaning |
|---|---|---|
| `additionalProperties_mode` | outlines/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `additionalProperties_value` | outlines/over;xgr/over | Feature derivee utilisee par au moins un modele predictif. |
| `object_additional_properties_case` | guidance/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `object_complex_keywords_same_node_count` | guidance/over;outlines/under;xgr/over;xgr/under | Maximum de mots-cles objet complexes sur un meme noeud, selon une liste manuelle. |
| `object_context_count` | guidance/over;outlines/under;xgr/over;xgr/under | nombre de contextes objet detectes dans le schema. |
| `object_depth_max` | guidance/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `object_extra_properties_count` | guidance/over;outlines/under;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `object_has_minProperties` | xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `object_has_required_outside_properties` | guidance/over;outlines/under;xgr/under | indicateur binaire : au moins un contexte objet declare un champ `required` absent de `properties`. |
| `object_missing_required_count` | outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `object_parent_keyword` | guidance/over | Feature derivee utilisee par au moins un modele predictif. |
| `object_properties_count_max` | guidance/over;outlines/under;xgr/over;xgr/under | nombre maximal de proprietes declarees dans un meme objet du schema. |
| `object_property_count_boundary_case` | xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `object_required_case` | guidance/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `object_required_count_max` | guidance/over;outlines/under;xgr/over;xgr/under | nombre maximal de champs `required` dans un meme objet du schema. |
| `object_required_subset_invalid_context_count` | guidance/over;outlines/under;xgr/under | nombre de contextes objet ou au moins un champ `required` est absent de `properties`. |
| `object_required_subset_of_properties` | guidance/over;outlines/under;xgr/under | indicateur binaire historique : au moins un contexte objet a ses champs `required` inclus dans `properties`. |
| `object_required_subset_valid_context_count` | guidance/over;outlines/under;xgr/under | nombre de contextes objet ou `required` est non vide et entierement inclus dans `properties`. |
| `object_target_type` | guidance/over;outlines/under;xgr/over;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `patternProperties_anchor_mix` | outlines/over;outlines/under | Feature derivee utilisee par au moins un modele predictif. |
| `patternProperties_occurrence_count` | outlines/over | Feature derivee utilisee par au moins un modele predictif. |
| `patternProperties_pattern_count` | outlines/over;xgr/over | nombre de patterns declares dans `patternProperties`. |
| `patternProperties_regex_has_anchor` | outlines/over | Feature derivee utilisee par au moins un modele predictif. |
| `patternProperties_regex_has_dotstar` | outlines/under | Feature derivee utilisee par au moins un modele predictif. |
| `patternProperties_unanchored_count` | outlines/over | Feature derivee utilisee par au moins un modele predictif. |
| `patternProperties_with_properties` | outlines/over;outlines/under;xgr/under | Feature derivee utilisee par au moins un modele predictif. |
| `patternProperties_with_properties_count` | outlines/over;outlines/under;xgr/under | Nombre de contextes ou patternProperties et properties apparaissent ensemble. |
| `unmatched_key_count_when_additionalProperties_true` | outlines/over;xgr/over | Feature derivee utilisee par au moins un modele predictif. |
| `unmatched_keys_allowed_by_additionalProperties` | outlines/over;xgr/over | nombre de cles de l'instance non declarees dans `properties` mais acceptees via `additionalProperties`. |
