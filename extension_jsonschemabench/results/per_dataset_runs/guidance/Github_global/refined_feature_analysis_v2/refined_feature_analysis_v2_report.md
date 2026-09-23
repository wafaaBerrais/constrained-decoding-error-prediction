# Refined Feature Analysis v2

## Baseline

- Total tests: 23053
- Total valid tests: 7845
- Total invalid tests: 15208
- UNDER rate among invalid tests: 0.0000
- OVER rate among valid tests: 0.6133

## Numeric UNDER Results

Among invalid tests, the strongest non-low-support numeric contexts are:
- `numeric_boundary_case=above_max`: rate=0.000, lift=0.00, invalid_tests=362, schemas=185.
- `numeric_boundary_case=below_min`: rate=0.000, lift=0.00, invalid_tests=1269, schemas=497.
- `numeric_boundary_case=equal_max`: rate=0.000, lift=0.00, invalid_tests=21, schemas=12.
- `numeric_boundary_case=equal_min`: rate=0.000, lift=0.00, invalid_tests=292, schemas=110.
- `numeric_boundary_case=inside_range`: rate=0.000, lift=0.00, invalid_tests=652, schemas=238.
- `numeric_boundary_case=multiple_ok`: rate=0.000, lift=0.00, invalid_tests=35, schemas=15.
- `numeric_boundary_case=multiple_violation`: rate=0.000, lift=0.00, invalid_tests=37, schemas=26.
- `numeric_boundary_case=not_applicable`: rate=0.000, lift=0.00, invalid_tests=12540, schemas=4114.

Interpretation: these rates condition on invalid examples only, so boundary cases are compared against the right denominator rather than all tests.

## PatternProperties OVER Results

- `instance_matching_pattern_keys_count_bucket=1`: rate=1.000, lift=1.63, valid_tests=53, schemas=37.
- `instance_matching_pattern_keys_count_bucket=2`: rate=1.000, lift=1.63, valid_tests=127, schemas=80.
- `instance_matching_pattern_keys_count_bucket=3`: rate=1.000, lift=1.63, valid_tests=93, schemas=65.
- `instance_matching_pattern_keys_count_bucket=4-5`: rate=1.000, lift=1.63, valid_tests=81, schemas=55.
- `instance_matching_pattern_keys_count_bucket=6+`: rate=1.000, lift=1.63, valid_tests=72, schemas=46.
- `patternProperties_regex_has_charclass=true`: rate=1.000, lift=1.63, valid_tests=339, schemas=196.
- `patternProperties_regex_has_dotstar=true`: rate=1.000, lift=1.63, valid_tests=125, schemas=70.
- `patternProperties_with_properties=true`: rate=1.000, lift=1.63, valid_tests=130, schemas=73.

Interpretation: high patternProperties lifts should be read together with support; the support-vs-lift plot separates rare sharp signals from broader effects.

## Combinator OVER Results

- `branches_have_not=true`: rate=0.957, lift=1.56, valid_tests=47, schemas=28.
- `combinator_type=mixed`: rate=0.923, lift=1.50, valid_tests=285, schemas=169.
- `combinator_branch_count_bucket=6+`: rate=0.911, lift=1.49, valid_tests=146, schemas=87.
- `combinator_branch_count_bucket=3`: rate=0.860, lift=1.40, valid_tests=242, schemas=140.
- `allOf_satisfied_branch_count_bucket=1`: rate=0.851, lift=1.39, valid_tests=47, schemas=31.
- `combinator_branch_count_bucket=4-5`: rate=0.839, lift=1.37, valid_tests=143, schemas=97.
- `branches_overlapping_properties=true`: rate=0.834, lift=1.36, valid_tests=199, schemas=121.
- `combinator_type=oneOf`: rate=0.828, lift=1.35, valid_tests=615, schemas=362.

Interpretation: branch count and matched-branch buckets help distinguish combinator presence from branch interaction cases.

## Test-Level vs Schema-Level

UNDER comparison:
- `allOf_satisfied_branch_count_bucket=0`: test lift 0.00; schema lift 0.00; schemas 4902.
- `allOf_satisfied_branch_count_bucket=1`: test lift 0.00; schema lift 0.00; schemas 57.
- `allOf_satisfied_branch_count_bucket=2`: test lift 0.00; schema lift 0.00; schemas 49.
- `allOf_satisfied_branch_ratio=0`: test lift 0.00; schema lift 0.00; schemas 4902.
- `allOf_satisfied_branch_ratio=0.5`: test lift 0.00; schema lift 0.00; schemas 32.
- `allOf_satisfied_branch_ratio=1`: test lift 0.00; schema lift 0.00; schemas 79.
- `anyOf_satisfied_branch_count=0`: test lift 0.00; schema lift 0.00; schemas 4853.
- `anyOf_satisfied_branch_count=1`: test lift 0.00; schema lift 0.00; schemas 219.

OVER comparison:
- `instance_satisfies_not_subschema=false`: test lift 1.63; schema lift 1.67; schemas 24.
- `not_contains_required=true`: test lift 1.63; schema lift 1.67; schemas 26.
- `not_parent_keyword=properties`: test lift 1.63; schema lift 1.67; schemas 19.
- `instance_matching_pattern_keys_count_bucket=1`: test lift 1.63; schema lift 1.67; schemas 68.
- `instance_matching_pattern_keys_count_bucket=2`: test lift 1.63; schema lift 1.67; schemas 98.
- `instance_matching_pattern_keys_count_bucket=3`: test lift 1.63; schema lift 1.67; schemas 84.
- `instance_matching_pattern_keys_count_bucket=4-5`: test lift 1.63; schema lift 1.67; schemas 77.
- `instance_matching_pattern_keys_count_bucket=6+`: test lift 1.63; schema lift 1.67; schemas 55.

If a context has high test-level lift but modest schema-level lift, it may be amplified by a smaller number of schemas with many tests.

## Limitations

- Results remain correlational.
- HDD or controlled mutations are still needed for causal validation.
- Low-support contexts should not be overinterpreted.
