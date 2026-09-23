# Outlines — interprétation des règles de prédiction OVER

Ce document réorganise les règles extraites de l’arbre de décision entraîné pour prédire les cas **OVER** du framework **Outlines**.

Sources utilisées :

- `over_rules.md` : règles, métriques et arbre textuel ;
- `over_tree.svg` : représentation graphique de l’arbre ;
- `analyze_refined_features.py` : définition des features utilisées.

![Arbre de décision Outlines OVER](outlines_over_tree.svg)

---

## 1. Signification d’un cas OVER

Un cas **OVER** correspond à la situation suivante :

```text
instance attendue valide + instance rejetée par Outlines
```

Outlines applique alors une contrainte plus restrictive que le JSON Schema de référence et rejette une instance qui devrait être acceptée.

---

## 2. Performances de l’arbre retenu

| Élément | Valeur |
|---|---:|
| Arbre | `tree_depth5_leaf50` |
| Seuil de décision | `0.78` |
| F1 test | `0.796748` |
| Précision test | `0.867257` |
| Recall test | `0.736842` |
| PR-AUC test | `0.851046` |
| ROC-AUC test | `0.927568` |

L’arbre a été entraîné avec un découpage par `schema_id`. Les schémas du jeu de test ne sont donc pas présents dans le jeu d’entraînement.

---

## 3. Comment lire les métriques d’une règle

Chaque règle correspond à une feuille de l’arbre.

- **Taux positif feuille train** : proportion de cas OVER parmi les exemples d’entraînement arrivant dans cette feuille.
- **Support test** : nombre de tests du jeu de test satisfaisant la règle.
- **Précision test** : proportion de vrais cas OVER parmi les tests couverts.
- **Contribution au recall test** : proportion de tous les vrais cas OVER du jeu de test capturée par la règle.

### Relation entre `class: 1` et le seuil final

L’arbre textuel affiche la classe obtenue avec le seuil standard de `0.5`. Le modèle final utilise toutefois un seuil plus strict :

```text
0.78
```

Une feuille peut donc être affichée comme `class: 1` dans l’arbre textuel sans être exportée comme règle positive finale si sa probabilité de cas OVER reste inférieure ou égale à `0.78`.

Les huit règles documentées ici sont les feuilles qui dépassent effectivement le seuil final.

---

## 4. Rappel rapide des features utilisées

- `unmatched_keys_allowed_by_additionalProperties` : nombre cumulé de clés de l’instance qui ne correspondent ni à `properties` ni à `patternProperties`, mais qui ne sont pas immédiatement interdites par `additionalProperties: false`.
- `branches_have_properties` : booléen indiquant si au moins une branche d’un `allOf`, `anyOf` ou `oneOf` contient un mot-clé `properties`.
- `instance_num_properties` : nombre de propriétés de l’objet situé à la racine de l’instance ; la valeur est `0` si la racine n’est pas un objet.
- `combinator_same_type_ratio` : proportion des occurrences de combinateurs dont les branches déclarant explicitement un type sont considérées comme homogènes.
- `has_allOf` : booléen indiquant que le schéma contient au moins une occurrence de `allOf`.
- `has_patternProperties` : booléen indiquant que le schéma contient au moins un mot-clé `patternProperties`.
- `additionalProperties_mode_false` : indicateur issu de l’encodage catégoriel, actif lorsque le mode global détecté pour `additionalProperties` est `false`.

### Signification de « cumulé »

Le calcul descend dans les objets et sous-schémas visités. Une même instance peut être évaluée dans plusieurs branches de combinateurs ; le compteur représente donc les occurrences observées pendant cette évaluation, et pas nécessairement uniquement les chemins de clés distincts.

---

## 5. Résumé opérationnel de l’arbre

Avec le seuil final de `0.78`, les huit feuilles positives peuvent être regroupées en trois grands profils :

```text
Outlines prédit OVER si :

PROFIL A
unmatched_keys_allowed_by_additionalProperties >= 1

OU

PROFIL B
unmatched_keys_allowed_by_additionalProperties = 0
ET combinator_same_type_ratio > 0.416667
ET has_allOf = true

OU

PROFIL C
unmatched_keys_allowed_by_additionalProperties = 0
ET combinator_same_type_ratio <= 0.416667
ET (
     has_patternProperties = true

     OU

     has_patternProperties = false
     ET instance_num_properties = 0
     ET additionalProperties_mode_false = true
)
```

Les subdivisions du profil A sur le nombre de propriétés racines, le nombre de clés non reconnues et la présence de `properties` dans les branches ne changent pas la prédiction finale : elles servent surtout à estimer des probabilités légèrement différentes.

---

## 6. Vue synthétique des profils

Les métriques agrégées sont approximatives, car elles sont reconstruites à partir des métriques de feuilles arrondies.

| Profil | Règles regroupées | Support test | Précision agrégée approximative | Contribution au recall |
|---|---|---:|---:|---:|
| Au moins une clé non reconnue et non immédiatement interdite | 1, 3, 4, 5, 6 | 62 | ≈ 0.984 | 0.458 |
| Aucun unmatched, combinateurs plutôt homogènes et présence de `allOf` | 2 | 17 | 1.000 | 0.128 |
| Aucun unmatched, faible homogénéité et `patternProperties` | 8 | 19 | 0.526 | 0.075 |
| Aucun unmatched, faible homogénéité, pas de `patternProperties`, instance racine vide et objet fermé | 7 | 15 | 0.667 | 0.075 |

Les quatre lignes couvrent ensemble environ :

```text
0.458 + 0.128 + 0.075 + 0.075 = 0.736
```

du recall test, ce qui correspond au recall global de l’arbre à l’arrondi près.

---

# 7. Profil A — clés non reconnues mais non immédiatement interdites

## Règle générale

```text
unmatched_keys_allowed_by_additionalProperties >= 1
```

Règles concernées : **1, 3, 4, 5 et 6**.

Toutes les feuilles situées sous cette branche dépassent le seuil `0.78`, que :

- des branches de combinateurs contiennent ou non `properties` ;
- l’instance racine contienne peu ou beaucoup de propriétés ;
- une ou plusieurs clés soient comptées comme non reconnues.

## Interprétation

Ce profil correspond à des instances contenant au moins une clé qui :

1. n’est pas nommée dans `properties` ;
2. ne correspond pas à un motif de `patternProperties` ;
3. n’est pas immédiatement rejetée par `additionalProperties: false`.

Dans les données de test, cette situation est fortement associée aux cas où Outlines rejette une instance pourtant valide. Le signal peut notamment apparaître dans les schémas ouverts, les schémas où `additionalProperties` est absent ou égal à `true`, ou lorsque les propriétés supplémentaires doivent être validées par un sous-schéma.

## Sous-profils de confiance

| Sous-profil | Règles | Support | Précision |
|---|---|---:|---:|
| Aucune branche de combinateur avec `properties`, instance avec au moins 9 propriétés racines | 1 | 18 | 1.000 |
| Aucune branche avec `properties`, instance avec 5 à 8 propriétés racines | 4 | 9 | 1.000 |
| Aucune branche avec `properties`, instance avec au plus 4 propriétés et au moins 2 unmatched | 3 | 16 | 1.000 |
| Aucune branche avec `properties`, instance avec au plus 4 propriétés et exactement 1 unmatched | 5 | 8 | 1.000 |
| Au moins une branche de combinateur contient `properties` | 6 | 11 | 0.909 |

Ces subdivisions modifient principalement le niveau de confiance. Elles ne changent pas la prédiction OVER dans cet arbre.

### Exemple réel à insérer

- `schema_id` : `[À REMPLIR]`
- `test_id` : `[À REMPLIR]`
- Clé ou chemin non reconnu : `[À REMPLIR]`
- Mode réel de `additionalProperties` : `[À REMPLIR]`
- Résultat du validateur de référence : valide
- Résultat Outlines : rejetée

**Requête de recherche à transmettre à l’outil :**

```text
Dans refined_test_features du run Outlines, cherche un test avec
failure_type == "OVER"
et unmatched_keys_allowed_by_additionalProperties >= 1.

Retourne :
- schema_id, test_id et test_index ;
- le JSON Schema complet ;
- l’instance complète ;
- la valeur exacte de unmatched_keys_allowed_by_additionalProperties ;
- instance_num_properties ;
- branches_have_properties ;
- additionalProperties_mode et additionalProperties_value ;
- les clés ou chemins qui ne correspondent ni à properties ni à
  patternProperties ;
- expected_validity et le résultat Outlines.

Vérifie avec le validateur de référence que l’instance est valide. Détermine
ensuite si chaque clé supplémentaire est autorisée parce que
additionalProperties est absent, égal à true, ou défini comme sous-schéma.
Si un sous-schéma est utilisé, vérifie que la valeur de la clé le respecte.
Ne modifie ni le schéma ni l’instance et n’invente aucune clé.
```

---

# 8. Profil B — `allOf` et combinateurs plutôt homogènes

## Règle

```text
unmatched_keys_allowed_by_additionalProperties = 0
AND combinator_same_type_ratio > 0.416667
AND has_allOf = true
```

Règle concernée : **2**.

## Interprétation

Aucune clé supplémentaire non reconnue n’est détectée. Le profil repose plutôt sur la structure logique du schéma :

- le schéma contient au moins un `allOf` ;
- plus de 41,67 % des occurrences de combinateurs sont considérées comme homogènes selon les types explicitement déclarés dans leurs branches.

Cette règle couvre 17 tests et possède une précision test de `1.000`. Elle décrit donc un profil fort dans cet arbre, lié à l’interaction entre `allOf` et des branches de types similaires.

### Exemple réel à insérer

- `schema_id` : `[À REMPLIR]`
- `test_id` : `[À REMPLIR]`
- Occurrence de `allOf` concernée : `[À REMPLIR]`
- Types déclarés dans les branches : `[À REMPLIR]`

**Requête de recherche à transmettre à l’outil :**

```text
Dans refined_test_features du run Outlines, cherche un test avec
failure_type == "OVER",
unmatched_keys_allowed_by_additionalProperties == 0,
combinator_same_type_ratio > 0.416667
et has_allOf == true.

Retourne schema_id, test_id, le schéma complet, l’instance complète,
allOf_count, combinator_count, combinator_same_type_count,
combinator_same_type_ratio et la liste des branches de chaque allOf avec
leurs types explicites. Vérifie que l’instance est valide selon le validateur
de référence et précise quelle occurrence de allOf est satisfaite par
l’instance. Indique ensuite que l’association avec la règle est prédictive,
sans présenter l’homogénéité des types comme une cause démontrée.
```

---

# 9. Profil C — faible homogénéité des combinateurs

Condition commune :

```text
unmatched_keys_allowed_by_additionalProperties = 0
AND combinator_same_type_ratio <= 0.416667
```

Deux variantes positives apparaissent.

---

## 9.1 Variante C1 — présence de `patternProperties`

```text
has_patternProperties = true
```

Règle concernée : **8**.

### Interprétation

Le schéma utilise `patternProperties`, mais aucune clé n’est comptée comme unmatched. Les clés de l’instance sont donc soit nommées explicitement, soit reconnues par au moins une expression régulière.

La règle peut illustrer des cas où la gestion des noms de propriétés par regex interagit avec les combinateurs du schéma.

### Exemple réel à insérer

- `schema_id` : `[À REMPLIR]`
- `test_id` : `[À REMPLIR]`
- Patterns concernés : `[À REMPLIR]`
- Clés de l’instance correspondant aux patterns : `[À REMPLIR]`

**Requête de recherche à transmettre à l’outil :**

```text
Dans refined_test_features du run Outlines, cherche un test avec
failure_type == "OVER",
unmatched_keys_allowed_by_additionalProperties == 0,
combinator_same_type_ratio <= 0.416667
et has_patternProperties == true.

Retourne schema_id, test_id, le schéma complet, l’instance complète,
les dictionnaires patternProperties, les clés de l’instance et les patterns
auxquels elles correspondent, ainsi que les occurrences de allOf, anyOf et
oneOf. Vérifie avec le validateur de référence que l’instance est valide.
Choisis de préférence un cas où la correspondance entre clés et regex est
facile à expliquer dans un rapport.
```

---

## 9.2 Variante C2 — objet fermé et instance racine sans propriété

```text
has_patternProperties = false
AND instance_num_properties = 0
AND additionalProperties_mode_false = true
```

Règle concernée : **7**.

### Interprétation

Cette variante décrit un schéma sans `patternProperties`, dans lequel le mode global de `additionalProperties` est `false`, appliqué à une instance dont l’objet racine ne contient aucune propriété — ou à une instance non objet, puisque `instance_num_properties` vaut également zéro dans ce cas.

Le profil peut correspondre à une interaction entre un objet fermé et les branches de combinateurs. L’exemple réel devra préciser le type de l’instance et vérifier qu’aucune propriété obligatoire ne manque.

### Exemple réel à insérer

- `schema_id` : `[À REMPLIR]`
- `test_id` : `[À REMPLIR]`
- Type de l’instance racine : `[À REMPLIR]`
- Liste des propriétés obligatoires : `[À REMPLIR]`

**Requête de recherche à transmettre à l’outil :**

```text
Dans refined_test_features du run Outlines, cherche un test avec
failure_type == "OVER",
unmatched_keys_allowed_by_additionalProperties == 0,
combinator_same_type_ratio <= 0.416667,
has_patternProperties == false,
instance_num_properties == 0
et additionalProperties_mode_false == true.

Retourne schema_id, test_id, instance_type, le schéma complet, l’instance
complète, tous les blocs additionalProperties: false, les tableaux required
et les combinateurs. Vérifie que l’instance est valide selon le validateur
de référence. Si l’instance est {}, explique pourquoi l’objet vide est valide.
Si l’instance n’est pas un objet, indique explicitement que
instance_num_properties vaut zéro par convention d’extraction.
```

---

# 10. Tableau détaillé des huit feuilles

Les conditions ci-dessous sont simplifiées en supprimant les seuils redondants hérités du chemin de l’arbre.

| Règle | Condition simplifiée | Taux train | Support | Précision | Recall | Niveau |
|---:|---|---:|---:|---:|---:|---|
| 1 | unmatched ≥ 1 ; aucune branche de combinateur avec `properties` ; au moins 9 propriétés racines | 1.000 | 18 | 1.000 | 0.135 | Très élevé |
| 2 | unmatched = 0 ; ratio de combinateurs homogènes > 0,416667 ; présence de `allOf` | 0.885 | 17 | 1.000 | 0.128 | Très élevé |
| 3 | unmatched ≥ 2 ; aucune branche avec `properties` ; au plus 4 propriétés racines | 1.000 | 16 | 1.000 | 0.120 | Très élevé |
| 4 | unmatched ≥ 1 ; aucune branche avec `properties` ; entre 5 et 8 propriétés racines | 0.992 | 9 | 1.000 | 0.068 | Très élevé, support faible |
| 5 | unmatched = 1 ; aucune branche avec `properties` ; au plus 4 propriétés racines | 0.997 | 8 | 1.000 | 0.060 | Très élevé, support faible |
| 6 | unmatched ≥ 1 ; au moins une branche de combinateur avec `properties` | 0.913 | 11 | 0.909 | 0.075 | Élevé |
| 7 | unmatched = 0 ; ratio homogène ≤ 0,416667 ; pas de `patternProperties` ; aucune propriété racine ; mode `additionalProperties=false` | 0.848 | 15 | 0.667 | 0.075 | Modéré |
| 8 | unmatched = 0 ; ratio homogène ≤ 0,416667 ; présence de `patternProperties` | 0.823 | 19 | 0.526 | 0.075 | Exploratoire |

---

# 11. Interprétation globale

## 11.1 Le signal principal concerne les clés non reconnues

La racine de l’arbre teste :

```text
unmatched_keys_allowed_by_additionalProperties <= 0.5
```

Toutes les feuilles de la branche opposée, où au moins une clé est comptée, dépassent le seuil final. Ce profil couvre 62 tests avec une précision agrégée approximative de `0.984`.

Il s’agit donc du signal le plus fort et le plus fréquent de cet arbre.

## 11.2 En l’absence de clés unmatched, la structure logique devient déterminante

Lorsque le compteur vaut zéro, l’arbre se tourne vers :

- la proportion de combinateurs homogènes ;
- la présence de `allOf` ;
- la présence de `patternProperties` ;
- la fermeture des objets avec `additionalProperties: false`.

## 11.3 Les splits internes du profil A ajustent surtout la confiance

Sous la branche `unmatched >= 1`, les deux côtés de tous les splits restent positifs :

- présence ou absence de `properties` dans les branches ;
- petit ou grand objet racine ;
- une ou plusieurs clés unmatched.

Ces features ne sont donc pas nécessaires pour résumer la décision finale, mais elles permettent de distinguer les feuilles ayant une précision de `1.000` de celle ayant une précision de `0.909`.

## 11.4 Nature de l’interprétation

Les profils sont des associations prédictives. Ils ne démontrent pas que `additionalProperties`, `allOf` ou `patternProperties` constitue seul la cause technique du rejet.

Pour établir une cause, il faut examiner :

1. le schéma réel ;
2. l’instance valide rejetée ;
3. le sous-schéma ou le motif concerné ;
4. éventuellement une réduction HDD ou une mutation contrôlée.

---

# 12. Requête générale pour compléter tous les exemples

```text
Lis le README des règles Outlines OVER et la table refined_test_features du
même run. Pour chaque profil demandé, filtre d’abord failure_type == "OVER".
Vérifie ensuite que expected_validity indique une instance valide et
qu’Outlines l’a rejetée.

Retourne :
- schema_id ;
- test_id et test_index ;
- les valeurs exactes des features de la règle ;
- le JSON Schema complet ;
- l’instance complète ;
- le résultat du validateur de référence ;
- le résultat Outlines.

Pour les règles sur additionalProperties, identifie les clés concernées et
précise si elles sont autorisées par absence du mot-clé, par true ou par un
sous-schéma. Pour les règles sur les combinateurs, indique quelles branches
sont satisfaites. Pour patternProperties, indique les correspondances entre
clés et regex.

Choisis un exemple compréhensible et n’invente aucune donnée. Distingue
toujours les conditions prédictives de l’arbre de la cause technique réelle.
Si cette cause ne peut pas être établie à partir du seul exemple, écris
qu’elle reste à confirmer.
```
