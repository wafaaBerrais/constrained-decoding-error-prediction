# Refined Feature Analysis v2

## Baseline

- Total tests: 21698
- Total valid tests: 7529
- Total invalid tests: 14169
- UNDER rate among invalid tests: 0.1524
- OVER rate among valid tests: 0.1950

## Numeric UNDER Results

Among invalid tests, the strongest non-low-support numeric contexts are:
- `numeric_boundary_case=multiple_violation`: rate=0.750, lift=4.92, invalid_tests=36, schemas=25.
- `numeric_target_type=number`: rate=0.497, lift=3.26, invalid_tests=936, schemas=225.
- `numeric_has_default=true`: rate=0.425, lift=2.79, invalid_tests=884, schemas=210.
- `numeric_boundary_case=below_min`: rate=0.347, lift=2.28, invalid_tests=1211, schemas=461.
- `numeric_boundary_case=above_max`: rate=0.314, lift=2.06, invalid_tests=309, schemas=158.
- `numeric_property_required=true`: rate=0.310, lift=2.03, invalid_tests=1744, schemas=398.
- `numeric_target_type=mixed`: rate=0.296, lift=1.94, invalid_tests=729, schemas=153.
- `numeric_parent_keyword=properties`: rate=0.293, lift=1.93, invalid_tests=2556, schemas=601.

Interpretation: these rates condition on invalid examples only, so boundary cases are compared against the right denominator rather than all tests.

## PatternProperties OVER Results

- `instance_matching_pattern_keys_count_bucket=6+`: rate=0.985, lift=5.05, valid_tests=67, schemas=43.
- `instance_matching_pattern_keys_count_bucket=4-5`: rate=0.974, lift=5.00, valid_tests=78, schemas=53.
- `patternProperties_regex_has_alternation=true`: rate=0.965, lift=4.95, valid_tests=57, schemas=33.
- `instance_matching_pattern_keys_count_bucket=3`: rate=0.923, lift=4.73, valid_tests=91, schemas=64.
- `additionalProperties_value=false`: rate=0.904, lift=4.64, valid_tests=281, schemas=161.
- `instance_matching_pattern_keys_count_bucket=1`: rate=0.900, lift=4.62, valid_tests=40, schemas=27.
- `patternProperties_regex_has_charclass=true`: rate=0.899, lift=4.61, valid_tests=296, schemas=171.
- `patternProperties_regex_has_anchor=true`: rate=0.887, lift=4.55, valid_tests=372, schemas=214.

Interpretation: high patternProperties lifts should be read together with support; the support-vs-lift plot separates rare sharp signals from broader effects.

## Combinator OVER Results

- `combinator_type=mixed`: rate=0.468, lift=2.40, valid_tests=282, schemas=167.
- `branches_have_not=true`: rate=0.467, lift=2.39, valid_tests=45, schemas=27.
- `combinator_branch_count_bucket=3`: rate=0.443, lift=2.27, valid_tests=235, schemas=136.
- `combinator_branch_count_bucket=6+`: rate=0.439, lift=2.25, valid_tests=139, schemas=82.
- `branches_have_enum=true`: rate=0.410, lift=2.10, valid_tests=283, schemas=173.
- `anyOf_satisfied_branch_count=2`: rate=0.400, lift=2.05, valid_tests=70, schemas=43.
- `anyOf_satisfied_branch_count_bucket=2`: rate=0.400, lift=2.05, valid_tests=70, schemas=43.
- `combinator_type=oneOf`: rate=0.365, lift=1.87, valid_tests=559, schemas=327.

Interpretation: branch count and matched-branch buckets help distinguish combinator presence from branch interaction cases.

## Test-Level vs Schema-Level

UNDER comparison:
- `numeric_boundary_case=multiple_violation`: test lift 4.92; schema lift 4.35; schemas 25.
- `not_parent_keyword=properties`: test lift 4.48; schema lift 3.02; schemas 18.
- `allOf_satisfied_branch_count_bucket=2`: test lift 4.47; schema lift 3.91; schemas 48.
- `allOf_satisfied_branch_ratio=0.5`: test lift 4.12; schema lift 4.02; schemas 32.
- `oneOf_satisfied_branch_count=2`: test lift 4.05; schema lift 2.88; schemas 36.
- `oneOf_satisfied_branch_count_bucket=2`: test lift 4.05; schema lift 2.88; schemas 36.
- `instance_satisfies_not_subschema=true`: test lift 3.28; schema lift 2.70; schemas 22.
- `numeric_target_type=number`: test lift 3.26; schema lift 3.78; schemas 229.

OVER comparison:
- `instance_matching_pattern_keys_count_bucket=6+`: test lift 5.05; schema lift 4.86; schemas 51.
- `instance_matching_pattern_keys_count_bucket=4-5`: test lift 5.00; schema lift 4.86; schemas 74.
- `patternProperties_regex_has_alternation=true`: test lift 4.95; schema lift 4.91; schemas 33.
- `instance_matching_pattern_keys_count_bucket=3`: test lift 4.73; schema lift 4.75; schemas 81.
- `additionalProperties_value=false`: test lift 4.64; schema lift 4.62; schemas 161.
- `instance_matching_pattern_keys_count_bucket=1`: test lift 4.62; schema lift 4.23; schemas 49.
- `patternProperties_regex_has_charclass=true`: test lift 4.61; schema lift 4.47; schemas 171.
- `patternProperties_regex_has_anchor=true`: test lift 4.55; schema lift 4.47; schemas 214.

If a context has high test-level lift but modest schema-level lift, it may be amplified by a smaller number of schemas with many tests.

## Limitations

- Results remain correlational.
- HDD or controlled mutations are still needed for causal validation.
- Low-support contexts should not be overinterpreted.
