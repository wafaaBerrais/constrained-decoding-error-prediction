# Refined Feature Analysis

- Dataset: `Github_global_no_hard`
- Framework: `outlines`
- Schemas analyzed: 3952
- Tests analyzed: 17325
- Baseline UNDER rate: 0.0717
- Baseline OVER rate: 0.0989

## Numeric Results

- `numeric_boundary_case=multiple_violation`: under_rate=0.750, lift=10.46, support_tests=28, support_schemas=20.
- `numeric_boundary_case=below_min`: under_rate=0.745, lift=10.39, support_tests=922, support_schemas=361.
- `numeric_boundary_case=above_max`: under_rate=0.618, lift=8.62, support_tests=241, support_schemas=122.
- `numeric_has_default=true`: under_rate=0.456, lift=6.37, support_tests=769, support_schemas=138.
- `numeric_target_type=mixed`: under_rate=0.371, lift=5.18, support_tests=477, support_schemas=81.

## PatternProperties Results

- `patternProperties_regex_has_alternation=true`: over_rate=0.387, lift=3.91, support_tests=106, support_schemas=24.
- `instance_matching_pattern_keys_count_bucket=2`: over_rate=0.376, lift=3.80, support_tests=234, support_schemas=72.
- `instance_matching_pattern_keys_count_bucket=4-5`: over_rate=0.354, lift=3.58, support_tests=96, support_schemas=42.
- `additionalProperties_value=false`: over_rate=0.345, lift=3.49, support_tests=525, support_schemas=105.
- `patternProperties_regex_has_charclass=true`: over_rate=0.327, lift=3.30, support_tests=539, support_schemas=115.

## Not Results

- `instance_satisfies_not_subschema=false`: over_rate=0.250, lift=2.53, support_tests=56, support_schemas=17.
- `not_contains_required=true`: over_rate=0.214, lift=2.17, support_tests=98, support_schemas=17.
- `not_parent_keyword=properties`: over_rate=0.169, lift=1.71, support_tests=71, support_schemas=15.
- `instance_satisfies_not_subschema=true`: over_rate=0.146, lift=1.48, support_tests=41, support_schemas=16.

## Combinator Results

- `allOf_satisfied_branch_count_bucket=2`: over_rate=0.308, lift=3.11, support_tests=104, support_schemas=33.
- `combinator_type=allOf`: over_rate=0.279, lift=2.82, support_tests=197, support_schemas=45.
- `combinator_branch_count_bucket=6+`: over_rate=0.274, lift=2.77, support_tests=274, support_schemas=52.
- `combinator_type=mixed`: over_rate=0.254, lift=2.57, support_tests=382, support_schemas=70.
- `oneOf_satisfied_branch_count_bucket=1`: over_rate=0.253, lift=2.56, support_tests=758, support_schemas=239.

## Top UNDER Contexts By Lift

- `numeric_boundary_case=multiple_violation`: lift=10.46, rate=0.750, tests=28.
- `numeric_boundary_case=below_min`: lift=10.39, rate=0.745, tests=922.
- `numeric_boundary_case=above_max`: lift=8.62, rate=0.618, tests=241.
- `numeric_has_default=true`: lift=6.37, rate=0.456, tests=769.
- `numeric_target_type=mixed`: lift=5.18, rate=0.371, tests=477.
- `numeric_property_required=true`: lift=4.65, rate=0.333, tests=1734.
- `numeric_target_type=number`: lift=4.63, rate=0.332, tests=1022.
- `numeric_parent_keyword=properties`: lift=4.53, rate=0.325, tests=2684.
- `numeric_is_in_properties=true`: lift=4.42, rate=0.317, tests=2895.
- `numeric_has_min_and_max=true`: lift=4.04, rate=0.290, tests=1164.
- `numeric_target_type=integer`: lift=3.74, rate=0.268, tests=1669.
- `numeric_parent_keyword=$defs`: lift=3.56, rate=0.255, tests=102.
- `numeric_parent_keyword=mixed`: lift=2.93, rate=0.210, tests=219.
- `oneOf_satisfied_branch_count_bucket=2`: lift=2.72, rate=0.195, tests=41.
- `numeric_parent_keyword=items`: lift=2.13, rate=0.153, tests=59.
- `numeric_boundary_case=multiple_ok`: lift=1.99, rate=0.143, tests=56.
- `patternProperties_regex_has_dotstar=true`: lift=1.81, rate=0.129, tests=170.
- `instance_has_unmatched_keys=false`: lift=1.19, rate=0.085, tests=14209.
- `combinator_branch_count_bucket=0`: lift=1.07, rate=0.077, tests=14674.
- `combinator_type=absent`: lift=1.07, rate=0.077, tests=14674.

## Top OVER Contexts By Lift

- `patternProperties_regex_has_alternation=true`: lift=3.91, rate=0.387, tests=106.
- `instance_matching_pattern_keys_count_bucket=2`: lift=3.80, rate=0.376, tests=234.
- `instance_matching_pattern_keys_count_bucket=4-5`: lift=3.58, rate=0.354, tests=96.
- `additionalProperties_value=false`: lift=3.49, rate=0.345, tests=525.
- `patternProperties_regex_has_charclass=true`: lift=3.30, rate=0.327, tests=539.
- `patternProperties_regex_has_anchor=true`: lift=3.21, rate=0.318, tests=696.
- `patternProperties_with_properties=true`: lift=3.18, rate=0.315, tests=213.
- `allOf_satisfied_branch_count_bucket=2`: lift=3.11, rate=0.308, tests=104.
- `instance_matching_pattern_keys_count_bucket=6+`: lift=2.88, rate=0.284, tests=109.
- `combinator_type=allOf`: lift=2.82, rate=0.279, tests=197.
- `combinator_branch_count_bucket=6+`: lift=2.77, rate=0.274, tests=274.
- `instance_matching_pattern_keys_count_bucket=3`: lift=2.76, rate=0.273, tests=176.
- `patternProperties_regex_has_dotstar=true`: lift=2.68, rate=0.265, tests=170.
- `combinator_type=mixed`: lift=2.57, rate=0.254, tests=382.
- `oneOf_satisfied_branch_count_bucket=1`: lift=2.56, rate=0.253, tests=758.
- `instance_satisfies_not_subschema=false`: lift=2.53, rate=0.250, tests=56.
- `anyOf_satisfied_branch_count_bucket=2`: lift=2.45, rate=0.242, tests=99.
- `combinator_branch_count_bucket=4-5`: lift=2.29, rate=0.226, tests=212.
- `instance_matching_pattern_keys_count_bucket=1`: lift=2.21, rate=0.219, tests=96.
- `branches_have_properties=true`: lift=2.18, rate=0.216, tests=1058.

## Limitations

- These results are correlational.
- A feature with high lift is not automatically the exact cause of the observed failure.
- Low-support contexts should be interpreted cautiously.
- HDD validation or controlled schema mutations can be used next to test causal hypotheses.
