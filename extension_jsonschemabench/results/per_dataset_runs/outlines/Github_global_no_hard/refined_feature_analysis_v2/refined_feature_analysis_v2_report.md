# Refined Feature Analysis v2

## Baseline

- Total tests: 17325
- Total valid tests: 6149
- Total invalid tests: 11176
- UNDER rate among invalid tests: 0.1111
- OVER rate among valid tests: 0.2786

## Numeric UNDER Results

Among invalid tests, the strongest non-low-support numeric contexts are:
- `numeric_boundary_case=multiple_violation`: rate=0.750, lift=6.75, invalid_tests=28, schemas=20.
- `numeric_boundary_case=below_min`: rate=0.746, lift=6.71, invalid_tests=921, schemas=361.
- `numeric_has_default=true`: rate=0.643, lift=5.78, invalid_tests=546, schemas=136.
- `numeric_boundary_case=above_max`: rate=0.621, lift=5.59, invalid_tests=240, schemas=122.
- `numeric_target_type=mixed`: rate=0.507, lift=4.56, invalid_tests=349, schemas=81.
- `numeric_target_type=number`: rate=0.468, lift=4.21, invalid_tests=724, schemas=181.
- `numeric_property_required=true`: rate=0.464, lift=4.17, invalid_tests=1247, schemas=300.
- `numeric_parent_keyword=properties`: rate=0.455, lift=4.09, invalid_tests=1917, schemas=469.

Interpretation: these rates condition on invalid examples only, so boundary cases are compared against the right denominator rather than all tests.

## PatternProperties OVER Results

- `additionalProperties_value=false`: rate=0.989, lift=3.55, valid_tests=183, schemas=105.
- `patternProperties_has_additionalProperties=true`: rate=0.979, lift=3.51, valid_tests=187, schemas=109.
- `patternProperties_regex_has_alternation=true`: rate=0.953, lift=3.42, valid_tests=43, schemas=24.
- `patternProperties_with_properties=true`: rate=0.944, lift=3.39, valid_tests=71, schemas=42.
- `instance_has_unmatched_keys=true`: rate=0.900, lift=3.23, valid_tests=611, schemas=429.
- `patternProperties_regex_has_charclass=true`: rate=0.893, lift=3.21, valid_tests=197, schemas=115.
- `instance_matching_pattern_keys_count_bucket=2`: rate=0.880, lift=3.16, valid_tests=100, schemas=62.
- `patternProperties_regex_has_anchor=true`: rate=0.867, lift=3.11, valid_tests=255, schemas=147.

Interpretation: high patternProperties lifts should be read together with support; the support-vs-lift plot separates rare sharp signals from broader effects.

## Combinator OVER Results

- `combinator_branch_count_bucket=6+`: rate=0.852, lift=3.06, valid_tests=88, schemas=52.
- `allOf_satisfied_branch_count_bucket=2`: rate=0.821, lift=2.95, valid_tests=39, schemas=24.
- `combinator_type=mixed`: rate=0.815, lift=2.93, valid_tests=119, schemas=70.
- `combinator_type=allOf`: rate=0.775, lift=2.78, valid_tests=71, schemas=45.
- `combinator_branch_count_bucket=4-5`: rate=0.750, lift=2.69, valid_tests=64, schemas=42.
- `allOf_satisfied_branch_ratio=1`: rate=0.696, lift=2.50, valid_tests=79, schemas=49.
- `branches_have_not=true`: rate=0.692, lift=2.49, valid_tests=26, schemas=16.
- `branches_overlapping_properties=true`: rate=0.654, lift=2.35, valid_tests=156, schemas=93.

Interpretation: branch count and matched-branch buckets help distinguish combinator presence from branch interaction cases.

## Test-Level vs Schema-Level

UNDER comparison:
- `numeric_boundary_case=multiple_violation`: test lift 6.75; schema lift 5.19; schemas 20.
- `numeric_boundary_case=below_min`: test lift 6.71; schema lift 6.02; schemas 361.
- `numeric_has_default=true`: test lift 5.78; schema lift 5.87; schemas 138.
- `numeric_boundary_case=above_max`: test lift 5.59; schema lift 4.77; schemas 122.
- `numeric_target_type=mixed`: test lift 4.56; schema lift 5.30; schemas 81.
- `numeric_target_type=number`: test lift 4.21; schema lift 4.63; schemas 184.
- `numeric_property_required=true`: test lift 4.17; schema lift 5.17; schemas 304.
- `numeric_parent_keyword=properties`: test lift 4.09; schema lift 5.03; schemas 475.

OVER comparison:
- `additionalProperties_value=false`: test lift 3.55; schema lift 3.52; schemas 105.
- `patternProperties_has_additionalProperties=true`: test lift 3.51; schema lift 3.45; schemas 109.
- `patternProperties_regex_has_alternation=true`: test lift 3.42; schema lift 3.40; schemas 24.
- `patternProperties_with_properties=true`: test lift 3.39; schema lift 3.38; schemas 42.
- `instance_has_unmatched_keys=true`: test lift 3.23; schema lift 1.51; schemas 1481.
- `patternProperties_regex_has_charclass=true`: test lift 3.21; schema lift 3.18; schemas 115.
- `instance_matching_pattern_keys_count_bucket=2`: test lift 3.16; schema lift 3.06; schemas 72.
- `patternProperties_regex_has_anchor=true`: test lift 3.11; schema lift 3.09; schemas 147.

If a context has high test-level lift but modest schema-level lift, it may be amplified by a smaller number of schemas with many tests.

## Limitations

- Results remain correlational.
- HDD or controlled mutations are still needed for causal validation.
- Low-support contexts should not be overinterpreted.
