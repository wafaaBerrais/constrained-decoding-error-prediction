# Refined Feature Analysis

- Dataset: `Github_global`
- Framework: `xgr`
- Schemas analyzed: 4772
- Tests analyzed: 21698
- Baseline UNDER rate: 0.0995
- Baseline OVER rate: 0.0677

## Numeric Results

- `numeric_boundary_case=multiple_violation`: under_rate=0.750, lift=7.54, support_tests=36, support_schemas=25.
- `numeric_target_type=number`: under_rate=0.354, lift=3.56, support_tests=1314, support_schemas=229.
- `numeric_boundary_case=below_min`: under_rate=0.347, lift=3.48, support_tests=1212, support_schemas=461.
- `numeric_boundary_case=above_max`: under_rate=0.313, lift=3.14, support_tests=310, support_schemas=158.
- `numeric_has_default=true`: under_rate=0.304, lift=3.05, support_tests=1238, support_schemas=214.

## PatternProperties Results

- `instance_matching_pattern_keys_count_bucket=4-5`: over_rate=0.384, lift=5.67, support_tests=198, support_schemas=74.
- `instance_matching_pattern_keys_count_bucket=2`: over_rate=0.377, lift=5.57, support_tests=236, support_schemas=82.
- `instance_matching_pattern_keys_count_bucket=3`: over_rate=0.356, lift=5.26, support_tests=236, support_schemas=81.
- `instance_matching_pattern_keys_count_bucket=6+`: over_rate=0.349, lift=5.16, support_tests=189, support_schemas=51.
- `patternProperties_regex_has_alternation=true`: over_rate=0.346, lift=5.11, support_tests=159, support_schemas=33.

## Not Results

- `not_contains_enum=true`: over_rate=0.157, lift=2.32, support_tests=51, support_schemas=11.
- `not_contains_required=true`: over_rate=0.148, lift=2.19, support_tests=169, support_schemas=26.
- `not_sibling_keyword_count_bucket=1`: over_rate=0.132, lift=1.96, support_tests=68, support_schemas=12.
- `instance_satisfies_not_subschema=false`: over_rate=0.111, lift=1.64, support_tests=99, support_schemas=24.

## Combinator Results

- `oneOf_satisfied_branch_count_bucket=1`: over_rate=0.177, lift=2.61, support_tests=995, support_schemas=305.
- `anyOf_satisfied_branch_count_bucket=2`: over_rate=0.159, lift=2.35, support_tests=176, support_schemas=51.
- `combinator_branch_count_bucket=6+`: over_rate=0.144, lift=2.12, support_tests=425, support_schemas=82.
- `combinator_branch_count_bucket=3`: over_rate=0.141, lift=2.09, support_tests=737, support_schemas=136.
- `combinator_type=oneOf`: over_rate=0.140, lift=2.06, support_tests=1461, support_schemas=327.

## Top UNDER Contexts By Lift

- `numeric_boundary_case=multiple_violation`: lift=7.54, rate=0.750, tests=36.
- `oneOf_satisfied_branch_count_bucket=2`: lift=5.95, rate=0.592, tests=49.
- `not_parent_keyword=properties`: lift=4.86, rate=0.483, tests=89.
- `allOf_satisfied_branch_count_bucket=2`: lift=4.48, rate=0.446, tests=148.
- `instance_satisfies_not_subschema=true`: lift=4.28, rate=0.426, tests=54.
- `allOf_satisfied_branch_count_bucket=1`: lift=3.64, rate=0.362, tests=210.
- `numeric_target_type=number`: lift=3.56, rate=0.354, tests=1314.
- `numeric_boundary_case=below_min`: lift=3.48, rate=0.347, tests=1212.
- `branches_have_not=true`: lift=3.37, rate=0.335, tests=170.
- `numeric_boundary_case=above_max`: lift=3.14, rate=0.313, tests=310.
- `numeric_has_default=true`: lift=3.05, rate=0.304, tests=1238.
- `not_contains_enum=true`: lift=2.96, rate=0.294, tests=51.
- `anyOf_satisfied_branch_count_bucket=2`: lift=2.74, rate=0.273, tests=176.
- `combinator_type=allOf`: lift=2.41, rate=0.240, tests=279.
- `combinator_type=mixed`: lift=2.41, rate=0.240, tests=967.
- `instance_satisfies_not_subschema=false`: lift=2.33, rate=0.232, tests=99.
- `branches_have_required=true`: lift=2.33, rate=0.232, tests=1698.
- `numeric_property_required=true`: lift=2.27, rate=0.225, tests=2396.
- `not_contains_required=true`: lift=2.26, rate=0.225, tests=169.
- `numeric_target_type=mixed`: lift=2.22, rate=0.221, tests=976.

## Top OVER Contexts By Lift

- `instance_matching_pattern_keys_count_bucket=4-5`: lift=5.67, rate=0.384, tests=198.
- `instance_matching_pattern_keys_count_bucket=2`: lift=5.57, rate=0.377, tests=236.
- `instance_matching_pattern_keys_count_bucket=3`: lift=5.26, rate=0.356, tests=236.
- `instance_matching_pattern_keys_count_bucket=6+`: lift=5.16, rate=0.349, tests=189.
- `patternProperties_regex_has_alternation=true`: lift=5.11, rate=0.346, tests=159.
- `patternProperties_regex_has_dotstar=true`: lift=4.79, rate=0.324, tests=321.
- `patternProperties_regex_has_charclass=true`: lift=4.60, rate=0.311, tests=854.
- `patternProperties_regex_has_anchor=true`: lift=4.50, rate=0.305, tests=1083.
- `additionalProperties_value=false`: lift=4.47, rate=0.303, tests=839.
- `instance_matching_pattern_keys_count_bucket=1`: lift=4.47, rate=0.303, tests=119.
- `patternProperties_with_properties=true`: lift=4.31, rate=0.292, tests=384.
- `numeric_boundary_case=equal_max`: lift=2.87, rate=0.194, tests=36.
- `oneOf_satisfied_branch_count_bucket=1`: lift=2.61, rate=0.177, tests=995.
- `anyOf_satisfied_branch_count_bucket=2`: lift=2.35, rate=0.159, tests=176.
- `not_contains_enum=true`: lift=2.32, rate=0.157, tests=51.
- `not_contains_required=true`: lift=2.19, rate=0.148, tests=169.
- `combinator_branch_count_bucket=6+`: lift=2.12, rate=0.144, tests=425.
- `combinator_branch_count_bucket=3`: lift=2.09, rate=0.141, tests=737.
- `instance_has_unmatched_keys=true`: lift=2.08, rate=0.141, tests=4004.
- `combinator_type=oneOf`: lift=2.06, rate=0.140, tests=1461.

## Limitations

- These results are correlational.
- A feature with high lift is not automatically the exact cause of the observed failure.
- Low-support contexts should be interpreted cautiously.
- HDD validation or controlled schema mutations can be used next to test causal hypotheses.
