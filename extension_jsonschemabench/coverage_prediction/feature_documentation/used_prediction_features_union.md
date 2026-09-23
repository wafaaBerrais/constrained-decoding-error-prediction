# <span style="color:#2563eb">Dictionnaire des features de prédiction</span>

> **Objectif.** Ce document décrit les features retenues pour les modèles de prédiction des cas **UNDER** et **OVER**. Les définitions sont fondées sur la liste filtrée `used_prediction_features_union.csv` et sur leur calcul dans `analyze_refined_features.py`.

**Nombre total de features documentées : `194`.**

---

## <span style="color:#2563eb">Sommaire</span>

1. [Contraintes d’objet](#section-1)
2. [Combinateurs logiques](#section-2)
3. [Complexité globale du schéma](#section-3)
4. [Contraintes de tableau](#section-4)
5. [Forme et valeurs de l’instance](#section-5)
6. [Contraintes enum et const](#section-6)
7. [Présence et cooccurrences simples](#section-7)
8. [Contraintes numériques](#section-8)
9. [patternProperties](#section-9)
10. [Contraintes de chaîne](#section-10)

---

## <span style="color:#2563eb">0. Notes de lecture</span>

### <span style="color:#2563eb">0.1 Niveaux de calcul</span>

| Niveau | Signification |
|---|---|
| **Schéma** | Feature calculée uniquement à partir du `JSON Schema`. Elle garde donc la même valeur pour tous les tests associés au même schéma. |
| **Instance** | Feature calculée uniquement à partir de la valeur JSON testée. |
| **Interaction schéma–instance** | Feature qui compare une instance précise avec les contraintes ou sous-schémas applicables. |

### <span style="color:#2563eb">0.2 Parcours récursif</span>

Un parcours est dit **récursif** lorsque la fonction commence à la racine, puis entre dans chaque sous-structure et répète le même traitement jusqu’aux valeurs terminales.

- Pour un **schéma**, le parcours descend notamment dans `properties`, `patternProperties`, `$defs`, les branches de `allOf`/`anyOf`/`oneOf`, `items`, `prefixItems`, `not`, `if`, `then`, `else` et les autres sous-schémas.
- Dans la version documentée, la racine a une profondeur de `0` et chaque passage vers un sous-schéma ajoute `1`.
- Pour une **instance**, le parcours descend dans les valeurs des objets et dans les éléments des tableaux. Les noms de propriétés sont traités comme des clés, pas comme des valeurs de type chaîne.

**Exemple de parcours récursif d’une instance :**

```json
{
  "user": {
    "name": "Wafaa",
    "scores": [10, 12]
  }
}
```

Le parcours visite l’objet racine, l’objet `user`, la chaîne `"Wafaa"`, le tableau `scores`, puis les deux valeurs numériques. Ainsi, les compteurs globaux incluent les valeurs situées à tous les niveaux.

### <span style="color:#2563eb">0.3 Règles d’agrégation courantes</span>

- Un indicateur booléen global vaut généralement **`true`** si le cas est observé au moins une fois dans le schéma.
- Les suffixes **`_min`**, **`_max`** et **`_avg`** désignent respectivement le minimum, le maximum et la moyenne sur les contextes ou occurrences observés.
- Pour plusieurs valeurs catégorielles, une valeur unique est conservée si elle est la même partout ; **`mixed`** est utilisé lorsque plusieurs valeurs différentes sont présentes ; **`absent`** indique qu’aucun contexte applicable n’a été trouvé.

---

## <span style="color:#2563eb">Répartition par famille</span>

| Famille | Nombre de features | Rôle |
|---|---:|---|
| **Contraintes d’objet** | `20` | Décrit les structures de type objet (`properties`, `required`, `additionalProperties`, `minProperties`, etc.) et leur interaction avec les objets fournis dans les tests. |
| **Combinateurs logiques** | `65` | Décrit les combinateurs logiques `allOf`, `anyOf` et `oneOf`, la composition de leurs branches et le nombre de branches satisfaites par chaque instance. |
| **Complexité globale du schéma** | `18` | Mesure la taille, la profondeur et la concentration locale de mots-clés du schéma. Deux features de ce groupe décrivent aussi les vérifications de type effectuées sur l’instance. |
| **Contraintes de tableau** | `12` | Décrit les schémas de tableaux (`items`, `prefixItems`, minItems, maxItems, etc.) et les violations observées sur les tableaux testés. |
| **Forme et valeurs de l’instance** | `20` | Décrit la forme et le contenu de l’instance JSON : chaînes, nombres, tableaux, objets, profondeur et correspondance des clés. |
| **Contraintes enum et const** | `10` | Décrit les contraintes `enum` et `const`, ainsi que la correspondance de l’instance avec les valeurs autorisées. |
| **Présence et cooccurrences simples** | `6` | Regroupe des indicateurs simples de présence et de cooccurrence locale entre mots-clés. |
| **Contraintes numériques** | `17` | Décrit les contraintes numériques du schéma et la position des valeurs numériques de l’instance par rapport à ces contraintes. |
| **patternProperties** | `8` | Décrit les expressions régulières utilisées dans `patternProperties` et leur association avec `properties`. |
| **Contraintes de chaîne** | `18` | Décrit les contraintes appliquées aux chaînes (`pattern`, `minLength`, `maxLength`, `format`) et leur évaluation sur l’instance. |

---

<a id="section-1"></a>

## <span style="color:#2563eb">1. Contraintes d’objet</span>

**Rôle.** Décrit les structures de type objet (`properties`, `required`, `additionalProperties`, `minProperties`, etc.) et leur interaction avec les objets fournis dans les tests.

| Feature | Niveau | Définition et valeurs |
|---|---|---|
| `additionalProperties_mode` | **Schéma** | Mode global de `additionalProperties` dans tous les nœuds concernés. Les valeurs rencontrées sont agrégées sur l’ensemble du schéma. Valeurs : `absent` : non déclaré ; `true` : propriétés supplémentaires libres ; `false` : interdites ; `schema` : validées par un sous-schéma ; `mixed` : plusieurs modes. |
| `additionalProperties_value` | **Schéma** | Mode de `additionalProperties` dans les nœuds qui contiennent `patternProperties`. Valeurs : `absent`, `true`, `false`, `schema` ou `mixed`. |
| `object_additional_properties_case` | **Interaction schéma–instance** | Résume le traitement des clés de l’instance qui ne correspondent ni à `properties` ni à `patternProperties`. Valeurs : extra_disallowed, extra_validated_by_schema, extra_allowed_or_absent, no_extra_properties, not_object, not_applicable. |
| `object_context_count` | **Schéma** | Nombre de nœuds considérés comme des contextes objet : nœuds de type `object` ou contenant un mot-clé objet. |
| `object_depth_max` | **Schéma** | Profondeur maximale d’un contexte objet dans le parcours récursif du schéma. |
| `object_extra_properties_count` | **Interaction schéma–instance** | Nombre maximal de clés supplémentaires observées dans un même contexte objet. |
| `object_has_minProperties` | **Schéma** | Booléen indiquant si au moins un contexte objet contient `minProperties`. |
| `object_has_required_outside_properties` | **Schéma** | Booléen indiquant si au moins un contexte déclare dans `required` un nom `absent` de `properties`. |
| `object_missing_required_count` | **Interaction schéma–instance** | Nombre maximal de propriétés obligatoires absentes dans un même contexte objet. |
| `object_parent_keyword` | **Schéma** | Contexte structurel dans lequel les nœuds objet apparaissent. Valeurs : `root`, `properties`, `items`, un combinateur, `not`, etc. ; `mixed` si plusieurs contextes ; `absent` s’il n’y en a aucun. |
| `object_properties_count_max` | **Schéma** | Nombre maximal de propriétés déclarées dans le même dictionnaire `properties`. |
| `object_property_count_boundary_case` | **Interaction schéma–instance** | Position du nombre de propriétés de l’objet testé par rapport à `minProperties` et `maxProperties`. Valeurs : below_minProperties, above_maxProperties, inside_property_count_bounds, not_object, not_applicable. |
| `object_required_case` | **Interaction schéma–instance** | État des propriétés obligatoires pour l’instance. Valeurs : missing_required, all_required_present, not_object ou not_applicable. |
| `object_required_count_max` | **Schéma** | Nombre maximal de noms placés dans un même tableau `required`. |
| `object_required_subset_invalid_context_count` | **Schéma** | Nombre de contextes objet où au moins un nom de `required` est `absent` de `properties`. |
| `object_required_subset_of_properties` | **Schéma** | Booléen indiquant si au moins un contexte non vide possède un `required` entièrement inclus dans `properties`. |
| `object_required_subset_valid_context_count` | **Schéma** | Nombre de contextes où `required` est non vide et entièrement inclus dans `properties`. |
| `object_target_type` | **Schéma** | Type associé aux contextes objet, agrégé sur le schéma. Valeurs : Type unique (`object`, etc.), `mixed` si plusieurs types, `absent` si aucun type explicite. |
| `unmatched_key_count_when_additionalProperties_true` | **Interaction schéma–instance** | Nombre cumulé de clés non reconnues comptées dans le cas permissif du script : `additionalProperties`: `true` ou mot-clé `absent`. |
| `unmatched_keys_allowed_by_additionalProperties` | **Interaction schéma–instance** | Nombre cumulé de clés non reconnues qui ne sont pas immédiatement interdites : elles sont autorisées, laissées ouvertes ou transmises à un sous-schéma `additionalProperties`. |

**Exemple.**

> Pour un schéma déclarant `required`: ["name", "age"] et une instance contenant seulement {"name": "A"}, object_missing_required_count vaut 1 et object_required_case vaut missing_required.

---

<a id="section-2"></a>

## <span style="color:#2563eb">2. Combinateurs logiques</span>

**Rôle.** Décrit les combinateurs logiques `allOf`, `anyOf` et `oneOf`, la composition de leurs branches et le nombre de branches satisfaites par chaque instance.

| Feature | Niveau | Définition et valeurs |
|---|---|---|
| `allOf_branch_count` | **Schéma** | Nombre maximal de branches parmi toutes les occurrences `allOf`. |
| `allOf_count` | **Schéma** | Nombre d’occurrences du mot-clé `allOf` dans le schéma. |
| `allOf_failed_branch_count_for_instance` | **Interaction schéma–instance** | Nombre maximal de branches non satisfaites dans une même occurrence `allOf`. |
| `allOf_is_satisfied_for_instance` | **Interaction schéma–instance** | Booléen vrai lorsque le schéma contient au moins une occurrence `allOf` et que toutes les occurrences `allOf` sont satisfaites par l’instance. |
| `allOf_occurrence_failed_count` | **Interaction schéma–instance** | Nombre d’occurrences `allOf` non satisfaites par l’instance. |
| `allOf_occurrence_satisfied_count` | **Interaction schéma–instance** | Nombre d’occurrences `allOf` satisfaites par l’instance. |
| `allOf_ratio_avg` | **Interaction schéma–instance** | Moyenne des ratios « branches satisfaites / branches totales », calculés séparément pour chaque occurrence `allOf`. |
| `allOf_ratio_max` | **Interaction schéma–instance** | Maximum des ratios « branches satisfaites / branches totales », calculés séparément pour chaque occurrence `allOf`. |
| `allOf_ratio_min` | **Interaction schéma–instance** | Minimum des ratios « branches satisfaites / branches totales », calculés séparément pour chaque occurrence `allOf`. |
| `allOf_satisfied_branch_count` | **Interaction schéma–instance** | Nombre maximal de branches satisfaites dans une même occurrence `allOf`. |
| `anyOf_branch_count` | **Schéma** | Nombre maximal de branches parmi toutes les occurrences `anyOf`. |
| `anyOf_count` | **Schéma** | Nombre d’occurrences du mot-clé `anyOf` dans le schéma. |
| `anyOf_is_satisfied_for_instance` | **Interaction schéma–instance** | Booléen vrai lorsque le schéma contient au moins une occurrence `anyOf` et que toutes les occurrences `anyOf` sont satisfaites par l’instance. |
| `anyOf_occurrence_failed_count` | **Interaction schéma–instance** | Nombre d’occurrences `anyOf` non satisfaites par l’instance. |
| `anyOf_occurrence_satisfied_count` | **Interaction schéma–instance** | Nombre d’occurrences `anyOf` satisfaites par l’instance. |
| `anyOf_ratio_avg` | **Interaction schéma–instance** | Moyenne des ratios « branches satisfaites / branches totales », calculés séparément pour chaque occurrence `anyOf`. |
| `anyOf_ratio_max` | **Interaction schéma–instance** | Maximum des ratios « branches satisfaites / branches totales », calculés séparément pour chaque occurrence `anyOf`. |
| `anyOf_ratio_min` | **Interaction schéma–instance** | Minimum des ratios « branches satisfaites / branches totales », calculés séparément pour chaque occurrence `anyOf`. |
| `anyOf_satisfied_all_branch_count` | **Interaction schéma–instance** | Nombre d’occurrences `anyOf` pour lesquelles toutes les branches sont satisfaites. |
| `branches_have_different_type` | **Schéma** | Booléen indiquant qu’au moins un combinateur possède plusieurs types explicites différents dans ses branches. |
| `branches_have_properties` | **Schéma** | Booléen indiquant qu’au moins une branche de combinateur contient `properties`, directement ou dans un sous-schéma. |
| `branches_have_required` | **Schéma** | Booléen indiquant qu’au moins une branche de combinateur contient `required`, directement ou dans un sous-schéma. |
| `branches_have_same_type` | **Schéma** | Booléen indiquant qu’au moins un combinateur possède des branches dont les types explicites sont homogènes. |
| `branches_with_additionalProperties_count` | **Schéma** | Nombre total de branches de combinateurs contenant `additionalProperties`, avec recherche récursive dans chaque branche. |
| `branches_with_additionalProperties_false_count` | **Schéma** | Nombre de branches contenant au moins un `additionalProperties`: `false`. |
| `branches_with_additionalProperties_ratio` | **Schéma** | Proportion de toutes les branches de combinateurs contenant `additionalProperties`. |
| `branches_with_additionalProperties_schema_count` | **Schéma** | Nombre de branches contenant `additionalProperties` sous forme de sous-schéma. |
| `branches_with_additionalProperties_true_count` | **Schéma** | Nombre de branches contenant au moins un `additionalProperties`: `true`. |
| `branches_with_not_count` | **Schéma** | Nombre total de branches de combinateurs contenant `not`, avec recherche récursive dans chaque branche. |
| `branches_with_not_ratio` | **Schéma** | Proportion de toutes les branches de combinateurs contenant `not`. |
| `branches_with_numeric_count` | **Schéma** | Nombre total de branches de combinateurs contenant une contrainte numérique, avec recherche récursive dans chaque branche. |
| `branches_with_numeric_ratio` | **Schéma** | Proportion de toutes les branches de combinateurs contenant une contrainte numérique. |
| `branches_with_properties_count` | **Schéma** | Nombre total de branches de combinateurs contenant `properties`, avec recherche récursive dans chaque branche. |
| `branches_with_properties_ratio` | **Schéma** | Proportion de toutes les branches de combinateurs contenant `properties`. |
| `branches_with_required_count` | **Schéma** | Nombre total de branches de combinateurs contenant `required`, avec recherche récursive dans chaque branche. |
| `branches_with_required_ratio` | **Schéma** | Proportion de toutes les branches de combinateurs contenant `required`. |
| `combinator_branch_count_avg` | **Schéma** | Nombre moyen de branches par occurrence de combinateur. |
| `combinator_branch_count_max` | **Schéma** | Nombre maximal de branches dans une occurrence de combinateur. |
| `combinator_branch_count_min` | **Schéma** | Nombre minimal de branches dans une occurrence de combinateur. |
| `combinator_count` | **Schéma** | Nombre total d’occurrences `allOf`, `anyOf` et `oneOf`. |
| `combinator_depth_avg` | **Schéma** | Profondeur moyenne des nœuds contenant un combinateur. |
| `combinator_depth_max` | **Schéma** | Profondeur maximale des nœuds contenant un combinateur. |
| `combinator_depth_min` | **Schéma** | Profondeur minimale des nœuds contenant un combinateur. |
| `combinator_different_type_count` | **Schéma** | Nombre de combinateurs dont les branches déclarent plusieurs types explicites différents. |
| `combinator_different_type_ratio` | **Schéma** | Proportion de combinateurs dont les branches sont hétérogènes en type. |
| `combinator_have_additionalProperties_count` | **Schéma** | Nombre de combinateurs ayant au moins une branche qui contient `additionalProperties`. |
| `combinator_have_not_count` | **Schéma** | Nombre de combinateurs ayant au moins une branche qui contient `not`. |
| `combinator_have_numeric_count` | **Schéma** | Nombre de combinateurs ayant au moins une branche qui contient une contrainte numérique. |
| `combinator_have_properties_count` | **Schéma** | Nombre de combinateurs ayant au moins une branche qui contient `properties`. |
| `combinator_have_required_count` | **Schéma** | Nombre de combinateurs ayant au moins une branche qui contient `required`. |
| `combinator_same_type_count` | **Schéma** | Nombre de combinateurs dont les types explicites de branches sont homogènes. |
| `combinator_same_type_ratio` | **Schéma** | Proportion de combinateurs dont les types explicites de branches sont homogènes. |
| `combinator_type` | **Schéma** | Type de combinateur présent dans le schéma. Valeurs : `allOf`, `anyOf` ou `oneOf` si un seul type est présent ; `mixed` si plusieurs types ; `absent` sinon. |
| `combinator_with_additionalProperties` | **Schéma** | Booléen indiquant qu’au moins une branche de combinateur contient le mot-clé `additionalProperties`. |
| `combinator_with_additionalProperties_false` | **Schéma** | Booléen indiquant qu’au moins une branche contient `additionalProperties`: `false`. |
| `combinator_with_additionalProperties_schema` | **Schéma** | Booléen indiquant qu’au moins une branche contient `additionalProperties` sous forme de sous-schéma. |
| `combinator_with_additionalProperties_true` | **Schéma** | Booléen indiquant qu’au moins une branche contient `additionalProperties`: `true`. |
| `oneOf_count` | **Schéma** | Nombre d’occurrences du mot-clé `oneOf` dans le schéma. |
| `oneOf_is_satisfied_for_instance` | **Interaction schéma–instance** | Booléen vrai lorsque le schéma contient au moins une occurrence `oneOf` et que toutes les occurrences `oneOf` sont satisfaites par l’instance. |
| `oneOf_occurrence_failed_count` | **Interaction schéma–instance** | Nombre d’occurrences `oneOf` non satisfaites par l’instance. |
| `oneOf_occurrence_satisfied_count` | **Interaction schéma–instance** | Nombre d’occurrences `oneOf` satisfaites par l’instance. |
| `oneOf_ratio_avg` | **Interaction schéma–instance** | Moyenne des ratios « branches satisfaites / branches totales », calculés séparément pour chaque occurrence `oneOf`. |
| `oneOf_ratio_max` | **Interaction schéma–instance** | Maximum des ratios « branches satisfaites / branches totales », calculés séparément pour chaque occurrence `oneOf`. |
| `oneOf_ratio_min` | **Interaction schéma–instance** | Minimum des ratios « branches satisfaites / branches totales », calculés séparément pour chaque occurrence `oneOf`. |
| `oneOf_satisfied_all_branch_count` | **Interaction schéma–instance** | Nombre d’occurrences `oneOf` pour lesquelles toutes les branches sont satisfaites. |

**Exemple.**

> Pour un `allOf` composé de trois branches dont deux sont satisfaites par l’instance : allOf_satisfied_branch_count = 2, le ratio de cette occurrence vaut 2/3, et cette occurrence est comptée dans allOf_occurrence_failed_count.

---

<a id="section-3"></a>

## <span style="color:#2563eb">3. Complexité globale du schéma</span>

**Rôle.** Mesure la taille, la profondeur et la concentration locale de mots-clés du schéma. Deux features de ce groupe décrivent aussi les vérifications de type effectuées sur l’instance.

| Feature | Niveau | Définition et valeurs |
|---|---|---|
| `any_visited_type_mismatch` | **Interaction schéma–instance** | Booléen indiquant qu’au moins une vérification de type visitée pendant le parcours ne correspond pas au type de la valeur testée. |
| `complex_keywords_same_node_avg` | **Schéma** | Nombre moyen de mots-clés de la liste COMPLEX_KEYWORDS présents dans un même nœud. |
| `complex_keywords_same_node_max` | **Schéma** | Nombre maximal de mots-clés de la liste COMPLEX_KEYWORDS présents simultanément dans un même nœud. |
| `logical_complex_keywords_same_node_count` | **Schéma** | Maximum de mots-clés logiques (`not`, combinateurs, `if`, `then`, `else`) présents sur un même nœud. |
| `object_complex_keywords_same_node_count` | **Schéma** | Maximum de mots-clés objet complexes présents sur un même nœud. |
| `regex_complex_keywords_same_node_count` | **Schéma** | Maximum de mots-clés liés aux chaînes et regex (`pattern`, `patternProperties`, `format`) présents sur un même nœud. |
| `required_property_count_total` | **Schéma** | Somme des tailles de tous les tableaux `required` rencontrés récursivement. |
| `schema_advanced_keyword_count` | **Schéma** | Nombre total d’occurrences des mots-clés avancés définis par le script : références, conditions, dépendances, mots-clés unevaluated*, `contains`, `format`, etc. |
| `schema_boolean_schema_count` | **Schéma** | Nombre de sous-schémas booléens `true` ou `false` rencontrés pendant le parcours. |
| `schema_format_keyword_count` | **Schéma** | Nombre total d’occurrences du mot-clé `format`. |
| `schema_keyword_count` | **Schéma** | Somme du nombre de clés de tous les nœuds du schéma parcourus récursivement. |
| `schema_legacy_dependencies_count` | **Schéma** | Nombre d’occurrences du mot-clé historique `dependencies`. |
| `schema_max_depth` | **Schéma** | Profondeur maximale du schéma. La racine vaut 0 et chaque passage vers un sous-schéma ajoute 1. |
| `schema_nullable_type_count` | **Schéma** | Nombre de nœuds dont la déclaration type contient `null`, seul ou dans une union. |
| `schema_ref_count` | **Schéma** | Nombre total d’occurrences de $ref. |
| `schema_total_properties_recursive` | **Schéma** | Somme du nombre de propriétés déclarées dans tous les dictionnaires `properties` du schéma. |
| `schema_type_union_count` | **Schéma** | Nombre de nœuds où type contient plusieurs options. |
| `type_mismatch_count` | **Interaction schéma–instance** | Nombre total de vérifications de type visitées qui ne correspondent pas au type de la valeur évaluée. |

---

<a id="section-4"></a>

## <span style="color:#2563eb">4. Contraintes de tableau</span>

**Rôle.** Décrit les schémas de tableaux (`items`, `prefixItems`, minItems, maxItems, etc.) et les violations observées sur les tableaux testés.

| Feature | Niveau | Définition et valeurs |
|---|---|---|
| `array_context_count` | **Schéma** | Nombre de nœuds de type tableau ou contenant au moins un mot-clé de tableau. |
| `array_has_maxItems` | **Schéma** | Booléen indiquant si au moins un contexte tableau contient maxItems. |
| `array_has_minItems` | **Schéma** | Booléen indiquant si au moins un contexte tableau contient minItems. |
| `array_has_min_and_max_items` | **Schéma** | Booléen indiquant si au moins un même contexte tableau contient à la fois minItems et maxItems. |
| `array_invalid_items_count` | **Interaction schéma–instance** | Nombre maximal d’éléments invalides détectés dans un même contexte de tableau, selon `prefixItems` et `items`. |
| `array_items_kind` | **Schéma** | Forme du mot-clé `items`, agrégée sur le schéma. Valeurs : `schema` : un sous-schéma ; list : une liste ; `absent` ; other ; `mixed` si plusieurs formes. |
| `array_items_object_properties_max` | **Schéma** | Nombre maximal de propriétés directement déclarées par un objet rencontré dans les sous-schémas de `items`. |
| `array_items_schema_depth` | **Schéma** | Profondeur maximale atteinte dans les sous-schémas placés sous `items`. |
| `array_length_violation_count` | **Interaction schéma–instance** | Nombre de violations détectées de minItems ou maxItems pendant le parcours. |
| `array_parent_keyword` | **Schéma** | Contexte structurel des tableaux. Valeurs : `root`, `properties`, `items`, combinateur, etc. ; `mixed` si plusieurs contextes ; `absent` sinon. |
| `array_target_type` | **Schéma** | Type associé aux contextes tableau, agrégé sur le schéma. Valeurs : Type unique, `mixed` si plusieurs types, `absent` si aucun type explicite. |
| `array_validation_case` | **Interaction schéma–instance** | Principal résultat de validation des contraintes de tableau. Valeurs : below_minItems, above_maxItems, uniqueItems_violation, items_violation, contains_violation, inside_array_constraints, not_array, not_applicable. |

---

<a id="section-5"></a>

## <span style="color:#2563eb">5. Forme et valeurs de l’instance</span>

**Rôle.** Décrit la forme et le contenu de l’instance JSON : chaînes, nombres, tableaux, objets, profondeur et correspondance des clés.

| Feature | Niveau | Définition et valeurs |
|---|---|---|
| `array_nested_object_count` | **Instance** | Nombre d’objets rencontrés directement comme éléments d’un tableau. |
| `instance_array_count` | **Instance** | Nombre total de tableaux présents récursivement dans l’instance. |
| `instance_boolean_count` | **Instance** | Nombre total de valeurs booléennes. |
| `instance_empty_array_count` | **Instance** | Nombre total de tableaux vides. |
| `instance_empty_object_count` | **Instance** | Nombre total d’objets vides. |
| `instance_has_unmatched_keys` | **Interaction schéma–instance** | Booléen indiquant qu’au moins une clé ne correspond ni à une propriété nommée ni à un motif de `patternProperties`. |
| `instance_integer_count` | **Instance** | Nombre total de valeurs entières ; les booléens sont exclus. |
| `instance_matching_pattern_keys_count` | **Interaction schéma–instance** | Nombre cumulé de clés qui correspondent à au moins une expression de `patternProperties` pendant le parcours. |
| `instance_max_abs_numeric_value` | **Instance** | Plus grande valeur absolue parmi tous les nombres de l’instance. |
| `instance_max_array_length` | **Instance** | Longueur maximale parmi tous les tableaux de l’instance. |
| `instance_max_object_depth` | **Instance** | Profondeur maximale d’imbrication des objets. Le premier objet rencontré vaut 1 ; les tableaux n’augmentent pas cette profondeur. |
| `instance_nested_array_count` | **Instance** | Nombre de tableaux situés à l’intérieur d’un autre tableau. |
| `instance_null_count` | **Instance** | Nombre total de valeurs `null`. |
| `instance_num_properties` | **Instance** | Nombre de propriétés de l’objet racine ; vaut 0 si la racine n’est pas un objet. |
| `instance_numeric_value_count` | **Instance** | Nombre total de valeurs numériques, entiers et flottants, avec exclusion des booléens. |
| `instance_string_count` | **Instance** | Nombre total de valeurs chaîne. |
| `instance_string_max_length` | **Instance** | Longueur maximale parmi toutes les chaînes. |
| `instance_string_total_length` | **Instance** | Somme des longueurs de toutes les chaînes. |
| `instance_total_array_items` | **Instance** | Somme des longueurs de tous les tableaux rencontrés, y compris les tableaux imbriqués. |
| `instance_total_object_properties_recursive` | **Instance** | Somme du nombre de propriétés de tous les objets rencontrés récursivement. |

---

<a id="section-6"></a>

## <span style="color:#2563eb">6. Contraintes enum et const</span>

**Rôle.** Décrit les contraintes `enum` et `const`, ainsi que la correspondance de l’instance avec les valeurs autorisées.

| Feature | Niveau | Définition et valeurs |
|---|---|---|
| `const_validation_case` | **Interaction schéma–instance** | Résultat de la comparaison avec les contraintes `const`. Valeurs : const_match, const_mismatch ou not_applicable. |
| `enum_context_count` | **Schéma** | Nombre de nœuds contenant une liste `enum`. |
| `enum_parent_keyword` | **Schéma** | Contexte structurel des contraintes `enum`. Valeurs : `root`, `properties`, `items`, combinateur, etc. ; `mixed` si plusieurs contextes ; `absent` sinon. |
| `enum_size_max` | **Schéma** | Taille maximale d’une seule liste `enum`. |
| `enum_string_values_count` | **Schéma** | Nombre total de valeurs de type chaîne présentes dans toutes les listes `enum`. |
| `enum_target_type` | **Schéma** | Type associé aux contraintes `enum`, agrégé sur le schéma. Valeurs : Type unique, `mixed` si plusieurs types, `absent` si aucun type explicite. |
| `enum_total_values` | **Schéma** | Somme du nombre de valeurs de toutes les listes `enum`. |
| `enum_type_match_but_value_mismatch` | **Interaction schéma–instance** | Nombre de contextes où la valeur n’appartient pas à `enum`, mais possède le même type JSON qu’au moins une valeur autorisée. |
| `enum_validation_case` | **Interaction schéma–instance** | Résultat global des comparaisons avec `enum`. Valeurs : enum_match, enum_mismatch ou not_applicable. |
| `enum_value_mismatch_count` | **Interaction schéma–instance** | Nombre de contextes `enum` dans lesquels la valeur testée ne correspond à aucune valeur autorisée. |

---

<a id="section-7"></a>

## <span style="color:#2563eb">7. Présence et cooccurrences simples</span>

**Rôle.** Regroupe des indicateurs simples de présence et de cooccurrence locale entre mots-clés.

| Feature | Niveau | Définition et valeurs |
|---|---|---|
| `has_allOf` | **Schéma** | Booléen indiquant la présence d’au moins un `allOf`. |
| `has_oneOf` | **Schéma** | Booléen indiquant la présence d’au moins un `oneOf`. |
| `has_patternProperties` | **Schéma** | Booléen indiquant la présence d’au moins un dictionnaire `patternProperties`. |
| `same_node_combinator_and_properties` | **Schéma** | Booléen indiquant qu’un même nœud contient `properties` et au moins un combinateur (`allOf`, `anyOf` ou `oneOf`). |
| `same_node_properties_and_additionalProperties` | **Schéma** | Booléen indiquant qu’un même nœud contient `properties` et `additionalProperties`. |
| `same_node_properties_and_required` | **Schéma** | Booléen indiquant qu’un même nœud contient `properties` et `required`. |

---

<a id="section-8"></a>

## <span style="color:#2563eb">8. Contraintes numériques</span>

**Rôle.** Décrit les contraintes numériques du schéma et la position des valeurs numériques de l’instance par rapport à ces contraintes.

| Feature | Niveau | Définition et valeurs |
|---|---|---|
| `has_exclusiveMaximum` | **Schéma** | Booléen indiquant la présence d’au moins une contrainte `exclusiveMaximum`. |
| `has_exclusiveMinimum` | **Schéma** | Booléen indiquant la présence d’au moins une contrainte `exclusiveMinimum`. |
| `has_maximum` | **Schéma** | Booléen indiquant la présence d’au moins une contrainte `maximum`. |
| `has_minimum` | **Schéma** | Booléen indiquant la présence d’au moins une contrainte `minimum`. |
| `has_multipleOf` | **Schéma** | Booléen indiquant la présence d’au moins une contrainte `multipleOf`. |
| `instance_has_int32_boundary_risk` | **Instance** | Booléen activé lorsque l’instance contient au moins un entier et que la plus grande valeur numérique absolue dépasse 2 147 483 647. |
| `instance_has_large_integer` | **Instance** | Booléen activé lorsque l’instance contient au moins un entier et que la plus grande valeur numérique absolue est au moins égale à 1 000 000. |
| `numeric_boundary_case` | **Interaction schéma–instance** | Position prioritaire d’une valeur numérique testée par rapport aux contraintes numériques rencontrées. Valeurs : below_min, equal_min, above_max, equal_max, inside_range, multiple_ok, multiple_violation, unknown, not_applicable. |
| `numeric_constraints_with_integer_type` | **Schéma** | Nombre d’occurrences de contraintes numériques associées au type `integer` ou à l’union integer_or_number. |
| `numeric_depth` | **Schéma** | Profondeur maximale d’une occurrence de contrainte numérique. |
| `numeric_has_default` | **Schéma** | Booléen indiquant qu’au moins un nœud contenant une contrainte numérique contient aussi default. |
| `numeric_has_min_and_max` | **Schéma** | Booléen indiquant qu’au moins un même nœud contient une borne inférieure et une borne supérieure numériques. |
| `numeric_is_in_properties` | **Schéma** | Booléen indiquant qu’au moins une contrainte numérique se trouve dans le sous-schéma d’une propriété, y compris dans ses sous-structures. |
| `numeric_keyword_count` | **Schéma** | Nombre total d’occurrences de `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum` et `multipleOf`. |
| `numeric_parent_keyword` | **Schéma** | Contexte structurel des contraintes numériques. Valeurs : `root`, `properties`, `items`, combinateur, `not`, etc. ; `mixed` si plusieurs contextes ; `absent` sinon. |
| `numeric_property_required` | **Schéma** | Booléen indiquant qu’au moins une contrainte numérique appartient au sous-schéma d’une propriété déclarée dans `required`. |
| `numeric_target_type` | **Schéma** | Type ciblé par les contraintes numériques, agrégé sur le schéma. Valeurs : `integer`, `number`, integer_or_number, other, `mixed` ou `absent`. |

**Exemple.**

> Pour une contrainte `minimum`: 0 appliquée à la valeur -2, numeric_boundary_case vaut below_min. Pour `multipleOf`: 5 appliqué à 15, la valeur est multiple_ok.

---

<a id="section-9"></a>

## <span style="color:#2563eb">9. patternProperties</span>

**Rôle.** Décrit les expressions régulières utilisées dans `patternProperties` et leur association avec `properties`.

| Feature | Niveau | Définition et valeurs |
|---|---|---|
| `patternProperties_anchor_mix` | **Schéma** | Répartition globale des patterns selon la présence de ^ ou $. Valeurs : `absent`, none_anchored, all_anchored ou `mixed`. |
| `patternProperties_occurrence_count` | **Schéma** | Nombre de nœuds contenant un dictionnaire `patternProperties`. |
| `patternProperties_pattern_count` | **Schéma** | Nombre total de patterns déclarés comme clés de `patternProperties`. |
| `patternProperties_regex_has_anchor` | **Schéma** | Booléen indiquant qu’au moins un `pattern` contient ^ ou $. |
| `patternProperties_regex_has_dotstar` | **Schéma** | Booléen indiquant qu’au moins un `pattern` contient la séquence .*. |
| `patternProperties_unanchored_count` | **Schéma** | Nombre de patterns ne contenant ni ^ ni $. |
| `patternProperties_with_properties` | **Schéma** | Booléen indiquant qu’au moins un même nœud contient `patternProperties` et `properties`. |
| `patternProperties_with_properties_count` | **Schéma** | Nombre de nœuds contenant simultanément `patternProperties` et `properties`. |

**Exemple.**

> Avec `patternProperties`: {"^x_": {...}}, les clés x_name et x_score correspondent au `pattern`. Le motif contient une ancre de début, donc patternProperties_regex_has_anchor = `true`.

---

<a id="section-10"></a>

## <span style="color:#2563eb">10. Contraintes de chaîne</span>

**Rôle.** Décrit les contraintes appliquées aux chaînes (`pattern`, `minLength`, `maxLength`, `format`) et leur évaluation sur l’instance.

| Feature | Niveau | Définition et valeurs |
|---|---|---|
| `string_context_count` | **Schéma** | Nombre de nœuds de type `string` ou contenant `pattern`, `minLength`, `maxLength` ou `format`. |
| `string_format_value` | **Schéma** | Valeur de `format` agrégée sur les contextes chaîne. Valeurs : Nom du `format` s’il est unique, `mixed` si plusieurs formats, `absent` si aucun. |
| `string_has_maxLength` | **Schéma** | Booléen indiquant la présence d’au moins un `maxLength`. |
| `string_has_minLength` | **Schéma** | Booléen indiquant la présence d’au moins un `minLength`. |
| `string_has_min_and_max_length` | **Schéma** | Booléen indiquant qu’au moins un même nœud contient `minLength` et `maxLength`. |
| `string_length_violation_count` | **Interaction schéma–instance** | Nombre de violations détectées de `minLength` ou `maxLength`. |
| `string_parent_keyword` | **Schéma** | Contexte structurel des contraintes chaîne. Valeurs : `root`, `properties`, `items`, combinateur, etc. ; `mixed` si plusieurs contextes ; `absent` sinon. |
| `string_pattern_avg_length` | **Schéma** | Longueur moyenne des expressions `pattern` non vides. |
| `string_pattern_complexity_score` | **Schéma** | Somme d’un score heuristique par `pattern` : longueur, plus deux points pour chaque occurrence de \|, *, +, ?, [ et (. |
| `string_pattern_count` | **Schéma** | Nombre de patterns non vides. |
| `string_pattern_has_alternation` | **Schéma** | Booléen indiquant qu’au moins un `pattern` contient l’alternation \|. |
| `string_pattern_has_anchor` | **Schéma** | Booléen indiquant qu’au moins un `pattern` contient ^ ou $. |
| `string_pattern_has_charclass` | **Schéma** | Booléen indiquant qu’au moins un `pattern` contient une classe de caractères entre [ et ]. |
| `string_pattern_has_repetition` | **Schéma** | Booléen indiquant qu’au moins un `pattern` contient *, +, ? ou une répétition de forme {n...}. |
| `string_pattern_max_length` | **Schéma** | Longueur maximale d’une expression `pattern` non vide. |
| `string_pattern_violation_count` | **Interaction schéma–instance** | Nombre de contextes où une chaîne ne correspond pas à `pattern`, ou dans lesquels la regex ne peut pas être compilée par le moteur Python. |
| `string_target_type` | **Schéma** | Type associé aux contextes chaîne, agrégé sur le schéma. Valeurs : Type unique, `mixed` si plusieurs types, `absent` si aucun type explicite. |
| `string_validation_case` | **Interaction schéma–instance** | Principal résultat observé pour les contraintes chaîne. Valeurs : too_short, too_long, pattern_violation, pattern_regex_error, format_present, inside_string_constraints, not_string, not_applicable. |

---
