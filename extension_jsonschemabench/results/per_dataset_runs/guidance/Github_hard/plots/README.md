# Statistical study: Github_hard / guidance

This folder contains schema-level statistics and SVG plots generated from the dataset run files. Compile time is analyzed once per schema, not once per test, to avoid overweighting schemas that contain many tests.

## Inputs

- `per_test_results.jsonl`: 4898 rows
- `timing_profile.csv`: 4898 rows
- `timed_out_schemas.jsonl`: 0 rows

## Main summary

| metric | value |
| --- | ---: |
| schemas | 888 |
| completed schemas | 888 |
| timeout schemas | 0 |
| schema timeout rate | 0.0% |
| tests | 4898 |
| completed tests | 4898 |
| coverage rate | 100.0% |
| accuracy on completed tests | 72.9% |
| under-constraint rate | 0.0% |
| over-constraint rate | 89.0% |
| median compile_grammar_s | 0.00179 |
| p95 compile_grammar_s | 0.00506 |
| max compile_grammar_s | 0.0139 |

## Timeout stages

| timeout_stage | schemas |
| --- | ---: |
| none | 0 |

Timeout stages are inferred from the timeout log when available, otherwise from partial checkpoints in `timing_profile.csv`.

## Expected validity among timeout tests

| expected_validity | tests | share |
| --- | ---: | ---: |
| valid | 0 | 0.0% |
| invalid | 0 | 0.0% |

## Timing by schema status

| status | phase | n | mean_s | std_s | median_s | p95_s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| completed | compile_grammar_s | 888 | 0.00207 | 0.00158 | 0.00179 | 0.00506 |
| completed | validation_loop_mean_s | 633 | 0.00449 | 0.00733 | 0.00258 | 0.0138 |
| completed | compute_mask_mean_s | 633 | 0.00406 | 0.00679 | 0.00229 | 0.0128 |
| completed | commit_token_mean_s | 633 | 0.000227 | 0.000503 | 0.000142 | 0.000639 |

For timeout schemas, phase values are partial checkpoints when available; `timeout_elapsed_s` is the supervisor elapsed time.

## Feature extraction

Raw structural features are `has_*` indicators for explicit JSON Schema keywords or benchmark categories. `$ref`, `$anchor`, `$dynamicRef`, `$defs`/`definitions`, `if`/`then`/`else`, and content keywords are mapped directly from the schema; `boolean_schema` is detected from boolean schema nodes and the benchmark `_boolSchema` metadata. `infinite-loop-detection` is only read from benchmark metadata when present because it is not a JSON Schema keyword.

Derived indicators (`large_enum`, `many_required`, `many_properties`, `deep_schema`) are kept separate from raw keyword features. Pair rows are generated automatically with `itertools.combinations(BASE_FEATURES, 2)`; a pair is present only when both base features are present in the same schema.

## Features associated with timeout

| feature | schemas | timeout with | timeout without | lift |
| --- | ---: | ---: | ---: | ---: |
| `has_additionalProperties` | 524 | 0.0% | 0.0% | 0.00 |
| `has_allOf` | 53 | 0.0% | 0.0% | 0.00 |
| `has_anyOf` | 192 | 0.0% | 0.0% | 0.00 |
| `has_boolean_schema` | 502 | 0.0% | 0.0% | 0.00 |
| `has_const` | 10 | 0.0% | 0.0% | 0.00 |
| `has_content` | 1 | 0.0% | 0.0% | 0.00 |
| `has_default` | 378 | 0.0% | 0.0% | 0.00 |
| `has_defs` | 362 | 0.0% | 0.0% | 0.00 |
| `has_enum` | 576 | 0.0% | 0.0% | 0.00 |
| `has_exclusiveMaximum` | 1 | 0.0% | 0.0% | 0.00 |

## Features associated with under/over-constraint

| feature | schemas | under_rate | over_rate | correct_rate |
| --- | ---: | ---: | ---: | ---: |
| `has_oneOf` | 173 | 0.0% | 100.0% | 68.1% |
| `has_patternProperties` | 122 | 0.0% | 100.0% | 71.0% |
| `has_minProperties` | 24 | 0.0% | 100.0% | 74.7% |
| `has_not` | 17 | 0.0% | 100.0% | 78.2% |
| `has_maxProperties` | 11 | 0.0% | 100.0% | 74.4% |
| `has_const` | 10 | 0.0% | 100.0% | 78.9% |
| `has_propertyNames` | 8 | 0.0% | 100.0% | 78.9% |
| `has_exclusiveMinimum` | 5 | 0.0% | 100.0% | 72.4% |
| `has_if_then_else` | 5 | 0.0% | 100.0% | 81.1% |
| `has_content` | 1 | 0.0% | 100.0% | 50.0% |

## Simple feature pairs

| feature_pair | schemas | timeout_rate | under_rate | over_rate |
| --- | ---: | ---: | ---: | ---: |
| `has_properties__AND__has_type` | 888 | 0.0% | 0.0% | 89.0% |
| `has_properties__AND__has_required` | 749 | 0.0% | 0.0% | 88.0% |
| `has_required__AND__has_type` | 749 | 0.0% | 0.0% | 88.0% |
| `has_items__AND__has_properties` | 678 | 0.0% | 0.0% | 91.4% |
| `has_items__AND__has_type` | 678 | 0.0% | 0.0% | 91.4% |
| `has_items__AND__has_required` | 598 | 0.0% | 0.0% | 90.7% |
| `has_enum__AND__has_properties` | 576 | 0.0% | 0.0% | 89.7% |
| `has_enum__AND__has_type` | 576 | 0.0% | 0.0% | 89.7% |
| `has_additionalProperties__AND__has_properties` | 524 | 0.0% | 0.0% | 93.3% |
| `has_additionalProperties__AND__has_type` | 524 | 0.0% | 0.0% | 93.3% |

## Selected pair heatmap candidates

The pair heatmap keeps the most interesting generated pairs. The ranking first requires usable support, then prioritizes the number of signals among timeout/under/over, then capped lift, delta, and support. This avoids filling the plot with rare pairs that only look strong because the denominator is tiny.

| feature_pair | schemas | risk_count | interest_score | timeout_group | under_group | over_group |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `has_properties__AND__has_type` | 888 | 1 | 1.05e+06 | 0.0% | 0.0% | 100.0% |
| `has_oneOf__AND__has_properties` | 173 | 1 | 1e+06 | 0.0% | 0.0% | 21.5% |
| `has_oneOf__AND__has_type` | 173 | 1 | 1e+06 | 0.0% | 0.0% | 21.5% |
| `has_items__AND__has_oneOf` | 167 | 1 | 1e+06 | 0.0% | 0.0% | 20.8% |
| `has_oneOf__AND__has_required` | 161 | 1 | 1e+06 | 0.0% | 0.0% | 20.0% |
| `has_defs__AND__has_oneOf` | 138 | 1 | 1e+06 | 0.0% | 0.0% | 17.2% |
| `has_additionalProperties__AND__has_oneOf` | 141 | 1 | 1e+06 | 0.0% | 0.0% | 17.6% |
| `has_oneOf__AND__has_ref` | 137 | 1 | 1e+06 | 0.0% | 0.0% | 17.1% |
| `has_boolean_schema__AND__has_oneOf` | 139 | 0 | 1.16e+03 | 0.0% | 0.0% | 17.3% |
| `has_patternProperties__AND__has_properties` | 122 | 0 | 1.16e+03 | 0.0% | 0.0% | 15.2% |

## Very slow completed schemas and errors

| group | schemas | compile_min_s | compile_max_s | under_rate | over_rate | accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| fast | 222 | 0.000298 | 0.000806 | 0.0% | 100.0% | 68.4% |
| medium | 222 | 0.000809 | 0.00178 | 0.0% | 75.2% | 78.2% |
| slow | 222 | 0.00179 | 0.00261 | 0.0% | 85.6% | 72.5% |
| very_slow | 222 | 0.00262 | 0.0139 | 0.0% | 93.7% | 72.5% |

## Generated files

- `schema_level_stats.csv`: one row per schema with timing, correctness, timeout status, and JSON Schema features.
- `feature_timeout_lift.csv`: P(timeout | feature), P(timeout | absence), and lift.
- `feature_under_lift.csv`: P(under | feature), P(under | absence), and lift using completed invalid tests.
- `feature_over_lift.csv`: P(over | feature), P(over | absence), and lift using completed valid tests.
- `feature_constraint_rates.csv`: under/over/correct rates for schemas containing each feature.
- `feature_group_heatmap.csv`: feature prevalence for correct, timeout, under, and over schema groups.
- `feature_pair_group_heatmap.csv`: selected pair prevalence for correct, timeout, under, and over schema groups.
- `feature_pair_rates.csv`: automatically generated pairwise rates over all raw base features.
- `feature_pair_timeout_lift.csv`: P(timeout | feature pair), P(timeout | absence), and lift.
- `feature_pair_under_lift.csv`: P(under | feature pair), P(under | absence), and lift using completed invalid tests.
- `feature_pair_over_lift.csv`: P(over | feature pair), P(over | absence), and lift using completed valid tests.
- `slow_completed_constraint_quartiles.csv`: under/over rates by compile-time quartile.
- `timeout_expected_validity.csv`: valid vs invalid expected tests among timeout schemas.
- `phase_timing_summary_by_status.csv`: mean/std timing by phase for completed and timeout schemas.
- `timing_by_result_case.csv`: per-test timing classified as correct_accept, correct_reject, under, over, or no_decision.
- `schema_characteristic_constraint_bins.csv`: non-feature schema characteristics binned by quartile with under/over rates.
- SVG plots: open directly from this folder.

## Plots to inspect first

- `schema_size_vs_compile.svg` and `schema_depth_vs_compile.svg` for the size/depth relationship.
- `feature_timeout_lift.svg`, `feature_under_lift.svg`, and `feature_over_lift.svg` for single-feature lift signals.
- `feature_under_over_rates.svg` and `feature_group_heatmap.svg` for isolated feature errors.
- `feature_pair_timeout_lift.svg`, `feature_pair_under_lift.svg`, and `feature_pair_over_lift.svg` for pairwise lift signals.
- `feature_pair_group_heatmap.svg` for the most interesting generated pairwise combinations.
- `phase_time_share_top_schemas.svg` to verify whether compile time dominates the slow completed schemas.
- `timeout_expected_validity_share.svg` for the valid/invalid mix inside timeout schemas.
- `compile_time_by_result_case_boxplot.svg` and `validation_time_by_result_case_boxplot.svg` for timing by result type.
- `schema_size_vs_*_constraint_group.svg` and `schema_size_quartiles_under_over_rates.svg` for schema size/complexity vs under/over.

<!-- compile-error-causes:start -->
## Compile-error causes

These files summarize compile errors by explicit framework message and by JSON Schema features present in the affected schemas.

- `compile_error_top_causes.csv` / `compile_error_top_causes.svg`: normalized causes extracted from `error_message`.
- `compile_error_top_schema_features.csv` / `compile_error_top_schema_features.svg`: most frequent schema features among compile-error schemas.
- `compile_error_feature_lift.csv` / `compile_error_feature_lift.svg`: features with the strongest compile-error lift compared with schemas that do not contain the feature.

Top causes by affected schemas:

| cause | schemas | tests |
| --- | ---: | ---: |
| keyword: patternProperties | 109 | 649 |
| format: uri | 45 | 234 |
| keyword: oneOf | 33 | 155 |
| keyword: minProperties | 19 | 118 |
| keyword: not | 9 | 60 |
| keyword: maxProperties | 7 | 42 |
| keyword: propertyNames | 5 | 34 |
| format: url | 5 | 29 |

Top feature lift signals:

| feature | schemas | rate | lift |
| --- | --- | ---: | ---: |
| has_patternProperties | 121 | 99.2% | 5.67 |
| has_items | 240 | 35.4% | 4.96 |
| has_oneOf | 139 | 80.3% | 4.95 |
| has_not | 17 | 100.0% | 3.66 |
| has_ref | 177 | 51.3% | 3.57 |
| has_minProperties | 23 | 95.8% | 3.57 |
| has_propertyNames | 8 | 100.0% | 3.56 |
| has_if_then_else | 5 | 100.0% | 3.53 |
<!-- compile-error-causes:end -->
