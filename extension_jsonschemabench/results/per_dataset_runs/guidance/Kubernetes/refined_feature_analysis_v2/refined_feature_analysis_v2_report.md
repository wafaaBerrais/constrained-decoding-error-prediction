# Refined Feature Analysis v2

## Baseline

- Total tests: 4588
- Total valid tests: 1680
- Total invalid tests: 2908
- UNDER rate among invalid tests: 0.0000
- OVER rate among valid tests: 0.5054

## Numeric UNDER Results

Among invalid tests, the strongest non-low-support numeric contexts are:
- `numeric_boundary_case=not_applicable`: rate=0.000, lift=0.00, invalid_tests=2908, schemas=949.
- `numeric_has_default=false`: rate=0.000, lift=0.00, invalid_tests=2908, schemas=949.
- `numeric_has_min_and_max=false`: rate=0.000, lift=0.00, invalid_tests=2908, schemas=949.
- `numeric_is_in_properties=false`: rate=0.000, lift=0.00, invalid_tests=2908, schemas=949.
- `numeric_parent_keyword=absent`: rate=0.000, lift=0.00, invalid_tests=2908, schemas=949.
- `numeric_property_required=false`: rate=0.000, lift=0.00, invalid_tests=2908, schemas=949.
- `numeric_target_type=absent`: rate=0.000, lift=0.00, invalid_tests=2908, schemas=949.

Interpretation: these rates condition on invalid examples only, so boundary cases are compared against the right denominator rather than all tests.

## PatternProperties OVER Results

- `instance_has_unmatched_keys=true`: rate=0.679, lift=1.34, valid_tests=81, schemas=73.
- `additionalProperties_value=absent`: rate=0.505, lift=1.00, valid_tests=1680, schemas=1014.
- `instance_matching_pattern_keys_count=0`: rate=0.505, lift=1.00, valid_tests=1680, schemas=1014.
- `patternProperties_has_additionalProperties=false`: rate=0.505, lift=1.00, valid_tests=1680, schemas=1014.
- `patternProperties_regex_has_alternation=false`: rate=0.505, lift=1.00, valid_tests=1680, schemas=1014.
- `patternProperties_regex_has_anchor=false`: rate=0.505, lift=1.00, valid_tests=1680, schemas=1014.
- `patternProperties_regex_has_charclass=false`: rate=0.505, lift=1.00, valid_tests=1680, schemas=1014.
- `patternProperties_regex_has_dotstar=false`: rate=0.505, lift=1.00, valid_tests=1680, schemas=1014.

Interpretation: high patternProperties lifts should be read together with support; the support-vs-lift plot separates rare sharp signals from broader effects.

## Combinator OVER Results

- `combinator_branch_count_bucket=2`: rate=0.667, lift=1.32, valid_tests=400, schemas=239.
- `combinator_type=oneOf`: rate=0.667, lift=1.32, valid_tests=400, schemas=239.
- `allOf_satisfied_branch_count_bucket=0`: rate=0.505, lift=1.00, valid_tests=1680, schemas=1014.
- `allOf_satisfied_branch_ratio=absent`: rate=0.505, lift=1.00, valid_tests=1680, schemas=1014.
- `anyOf_satisfied_branch_count=0`: rate=0.505, lift=1.00, valid_tests=1680, schemas=1014.
- `anyOf_satisfied_branch_count_bucket=0`: rate=0.505, lift=1.00, valid_tests=1680, schemas=1014.
- `branches_conflicting_types=false`: rate=0.505, lift=1.00, valid_tests=1680, schemas=1014.
- `branches_have_enum=false`: rate=0.505, lift=1.00, valid_tests=1680, schemas=1014.

Interpretation: branch count and matched-branch buckets help distinguish combinator presence from branch interaction cases.

## Test-Level vs Schema-Level

UNDER comparison:
- `allOf_satisfied_branch_count_bucket=0`: test lift 0.00; schema lift 0.00; schemas 1014.
- `allOf_satisfied_branch_ratio=absent`: test lift 0.00; schema lift 0.00; schemas 1014.
- `anyOf_satisfied_branch_count=0`: test lift 0.00; schema lift 0.00; schemas 1014.
- `anyOf_satisfied_branch_count_bucket=0`: test lift 0.00; schema lift 0.00; schemas 1014.
- `branches_conflicting_types=false`: test lift 0.00; schema lift 0.00; schemas 1014.
- `branches_have_enum=false`: test lift 0.00; schema lift 0.00; schemas 1014.
- `branches_have_not=false`: test lift 0.00; schema lift 0.00; schemas 1014.
- `branches_have_properties=false`: test lift 0.00; schema lift 0.00; schemas 1014.

OVER comparison:
- `instance_has_unmatched_keys=true`: test lift 1.34; schema lift 1.33; schemas 123.
- `combinator_branch_count_bucket=2`: test lift 1.32; schema lift 1.30; schemas 239.
- `combinator_type=oneOf`: test lift 1.32; schema lift 1.30; schemas 239.
- `allOf_satisfied_branch_count_bucket=0`: test lift 1.00; schema lift 1.00; schemas 1014.
- `allOf_satisfied_branch_ratio=absent`: test lift 1.00; schema lift 1.00; schemas 1014.
- `anyOf_satisfied_branch_count=0`: test lift 1.00; schema lift 1.00; schemas 1014.
- `anyOf_satisfied_branch_count_bucket=0`: test lift 1.00; schema lift 1.00; schemas 1014.
- `branches_conflicting_types=false`: test lift 1.00; schema lift 1.00; schemas 1014.

If a context has high test-level lift but modest schema-level lift, it may be amplified by a smaller number of schemas with many tests.

## Limitations

- Results remain correlational.
- HDD or controlled mutations are still needed for causal validation.
- Low-support contexts should not be overinterpreted.
