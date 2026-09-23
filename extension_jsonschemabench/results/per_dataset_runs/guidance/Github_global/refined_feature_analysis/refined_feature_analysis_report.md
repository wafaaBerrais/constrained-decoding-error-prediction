# Refined Feature Analysis

- Dataset: `Github_global`
- Framework: `guidance`
- Schemas analyzed: 4960
- Tests analyzed: 23053
- Baseline UNDER rate: 0.0000
- Baseline OVER rate: 0.2087

## Numeric Results

No non-low-support context exceeded the support thresholds.

## PatternProperties Results

- `instance_matching_pattern_keys_count_bucket=2`: over_rate=0.398, lift=1.91, support_tests=319, support_schemas=98.
- `instance_matching_pattern_keys_count_bucket=4-5`: over_rate=0.391, lift=1.88, support_tests=207, support_schemas=77.
- `instance_matching_pattern_keys_count_bucket=3`: over_rate=0.383, lift=1.83, support_tests=243, support_schemas=84.
- `patternProperties_regex_has_dotstar=true`: over_rate=0.355, lift=1.70, support_tests=352, support_schemas=70.
- `instance_matching_pattern_keys_count_bucket=6+`: over_rate=0.346, lift=1.66, support_tests=208, support_schemas=55.

## Not Results

- `not_contains_enum=true`: over_rate=0.353, lift=1.69, support_tests=51, support_schemas=11.
- `instance_satisfies_not_subschema=false`: over_rate=0.323, lift=1.55, support_tests=99, support_schemas=24.
- `not_parent_keyword=properties`: over_rate=0.284, lift=1.36, support_tests=95, support_schemas=19.
- `not_sibling_keyword_count_bucket=1`: over_rate=0.265, lift=1.27, support_tests=68, support_schemas=12.
- `not_contains_required=true`: over_rate=0.254, lift=1.22, support_tests=169, support_schemas=26.

## Combinator Results

- `allOf_satisfied_branch_count_bucket=3`: over_rate=0.533, lift=2.56, support_tests=30, support_schemas=13.
- `oneOf_satisfied_branch_count_bucket=1`: over_rate=0.396, lift=1.90, support_tests=1158, support_schemas=337.
- `combinator_type=oneOf`: over_rate=0.304, lift=1.46, support_tests=1675, support_schemas=362.
- `combinator_branch_count_bucket=6+`: over_rate=0.293, lift=1.40, support_tests=454, support_schemas=87.
- `combinator_branch_count_bucket=3`: over_rate=0.275, lift=1.32, support_tests=756, support_schemas=140.

## Top UNDER Contexts By Lift


## Top OVER Contexts By Lift

- `allOf_satisfied_branch_count_bucket=3`: lift=2.56, rate=0.533, tests=30.
- `instance_matching_pattern_keys_count_bucket=2`: lift=1.91, rate=0.398, tests=319.
- `oneOf_satisfied_branch_count_bucket=1`: lift=1.90, rate=0.396, tests=1158.
- `instance_matching_pattern_keys_count_bucket=4-5`: lift=1.88, rate=0.391, tests=207.
- `instance_matching_pattern_keys_count_bucket=3`: lift=1.83, rate=0.383, tests=243.
- `numeric_boundary_case=equal_min`: lift=1.78, rate=0.371, tests=580.
- `patternProperties_regex_has_dotstar=true`: lift=1.70, rate=0.355, tests=352.
- `not_contains_enum=true`: lift=1.69, rate=0.353, tests=51.
- `instance_matching_pattern_keys_count_bucket=6+`: lift=1.66, rate=0.346, tests=208.
- `patternProperties_regex_has_alternation=true`: lift=1.66, rate=0.346, tests=159.
- `patternProperties_with_properties=true`: lift=1.62, rate=0.339, tests=384.
- `patternProperties_regex_has_charclass=true`: lift=1.60, rate=0.334, tests=1016.
- `numeric_boundary_case=equal_max`: lift=1.60, rate=0.333, tests=39.
- `patternProperties_regex_has_anchor=true`: lift=1.59, rate=0.332, tests=1245.
- `instance_satisfies_not_subschema=false`: lift=1.55, rate=0.323, tests=99.
- `additionalProperties_value=false`: lift=1.54, rate=0.321, tests=1007.
- `numeric_boundary_case=multiple_ok`: lift=1.54, rate=0.321, tests=78.
- `numeric_boundary_case=inside_range`: lift=1.46, rate=0.306, tests=1315.
- `combinator_type=oneOf`: lift=1.46, rate=0.304, tests=1675.
- `instance_matching_pattern_keys_count_bucket=1`: lift=1.42, rate=0.296, tests=179.

## Limitations

- These results are correlational.
- A feature with high lift is not automatically the exact cause of the observed failure.
- Low-support contexts should be interpreted cautiously.
- HDD validation or controlled schema mutations can be used next to test causal hypotheses.
