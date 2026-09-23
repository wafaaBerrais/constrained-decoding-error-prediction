# Statistical study: Github_global / xgr

This folder contains schema-level statistics and SVG plots generated from the dataset run files. Compile time is analyzed once per schema, not once per test, to avoid overweighting schemas that contain many tests.

## Inputs

- `per_test_results.jsonl`: 21698 rows
- `timing_profile.csv`: 23053 rows
- `timed_out_schemas.jsonl`: 190 rows

## Main summary

| metric | value |
| --- | ---: |
| schemas | 4960 |
| completed schemas | 4770 |
| timeout schemas | 190 |
| schema timeout rate | 3.8% |
| tests | 23046 |
| completed tests | 21698 |
| coverage rate | 94.2% |
| accuracy on completed tests | 83.3% |
| under-constraint rate | 15.2% |
| over-constraint rate | 19.5% |
| median compile_grammar_s | 1.78 |
| p95 compile_grammar_s | 23.3 |
| max compile_grammar_s | 597 |

## Timeout stages

| timeout_stage | schemas |
| --- | ---: |
| compile_grammar | 137 |
| terminated_signal_11 | 23 |
| terminated_signal_15 | 14 |
| validation | 12 |
| terminated_sigterm | 4 |

Timeout stages are inferred from the timeout log when available, otherwise from partial checkpoints in `timing_profile.csv`.

## Expected validity among timeout tests

| expected_validity | tests | share |
| --- | ---: | ---: |
| valid | 319 | 23.6% |
| invalid | 1033 | 76.4% |

## Timing by schema status

| status | phase | n | mean_s | std_s | median_s | p95_s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| completed | compile_grammar_s | 4770 | 7.46 | 32.7 | 1.78 | 23.3 |
| completed | validation_loop_mean_s | 4743 | 0.0519 | 0.789 | 0.00168 | 0.0381 |
| completed | compute_mask_mean_s | 4743 | 0.0511 | 0.778 | 0.00148 | 0.0364 |
| completed | commit_token_mean_s | 4743 | 0.000433 | 0.0142 | 3.7e-05 | 0.000338 |
| timeout | compile_grammar_s | 20 | 205 | 266 | 59.8 | 600 |
| timeout | validation_loop_mean_s | 11 | 415 | 197 | 513 | 560 |
| timeout | compute_mask_mean_s | 14 | 320 | 241 | 497 | 530 |
| timeout | commit_token_mean_s | 14 | 5.53 | 13.9 | 0.0234 | 36.7 |
| timeout | timeout_elapsed_s | 190 | 591 | 297 | 600 | 1.11e+03 |

For timeout schemas, phase values are partial checkpoints when available; `timeout_elapsed_s` is the supervisor elapsed time.

## Feature extraction

Raw structural features are `has_*` indicators for explicit JSON Schema keywords or benchmark categories. `$ref`, `$anchor`, `$dynamicRef`, `$defs`/`definitions`, `if`/`then`/`else`, and content keywords are mapped directly from the schema; `boolean_schema` is detected from boolean schema nodes and the benchmark `_boolSchema` metadata. `infinite-loop-detection` is only read from benchmark metadata when present because it is not a JSON Schema keyword.

Derived indicators (`large_enum`, `many_required`, `many_properties`, `deep_schema`) are kept separate from raw keyword features. Pair rows are generated automatically with `itertools.combinations(BASE_FEATURES, 2)`; a pair is present only when both base features are present in the same schema.

## Features associated with timeout

| feature | schemas | timeout with | timeout without | lift |
| --- | ---: | ---: | ---: | ---: |
| `has_type` | 4950 | 3.8% | 0.0% | inf |
| `has_maxLength` | 545 | 29.9% | 0.6% | 48.91 |
| `has_minLength` | 701 | 21.4% | 0.9% | 22.78 |
| `has_pattern` | 1135 | 13.2% | 1.0% | 12.64 |
| `has_maxItems` | 212 | 21.2% | 3.1% | 6.95 |
| `has_exclusiveMaximum` | 4 | 25.0% | 3.8% | 6.56 |
| `has_maximum` | 352 | 13.4% | 3.1% | 4.30 |
| `has_boolean_schema` | 2285 | 6.5% | 1.6% | 4.13 |
| `has_additionalProperties` | 2364 | 6.3% | 1.6% | 3.87 |
| `has_patternProperties` | 314 | 9.6% | 3.4% | 2.77 |

## Features associated with under/over-constraint

| feature | schemas | under_rate | over_rate | correct_rate |
| --- | ---: | ---: | ---: | ---: |
| `has_if_then_else` | 10 | 20.0% | 86.7% | 63.3% |
| `has_contains` | 1 | 0.0% | 100.0% | 66.7% |
| `has_patternProperties` | 314 | 7.5% | 87.0% | 64.7% |
| `has_exclusiveMaximum` | 4 | 20.0% | 71.4% | 63.6% |
| `has_propertyNames` | 11 | 22.4% | 62.5% | 68.9% |
| `has_not` | 56 | 43.1% | 41.0% | 57.5% |
| `has_allOf` | 149 | 46.0% | 26.9% | 59.8% |
| `has_minProperties` | 85 | 17.6% | 52.9% | 71.6% |
| `has_maxProperties` | 31 | 10.2% | 58.8% | 76.6% |
| `has_multipleOf` | 37 | 49.2% | 16.1% | 62.0% |

## Simple feature pairs

| feature_pair | schemas | timeout_rate | under_rate | over_rate |
| --- | ---: | ---: | ---: | ---: |
| `has_maxItems__AND__has_minLength` | 71 | 59.2% | 27.9% | 38.5% |
| `has_maxLength__AND__has_patternProperties` | 55 | 54.5% | 22.9% | 73.3% |
| `has_maxItems__AND__has_maxLength` | 81 | 54.3% | 28.0% | 35.3% |
| `has_maxItems__AND__has_patternProperties` | 32 | 43.8% | 2.9% | 86.2% |
| `has_maxLength__AND__has_pattern` | 296 | 41.9% | 21.2% | 29.3% |
| `has_maxItems__AND__has_oneOf` | 58 | 41.4% | 25.5% | 35.2% |
| `has_maxLength__AND__has_oneOf` | 85 | 40.0% | 22.6% | 37.2% |
| `has_maxLength__AND__has_maximum` | 116 | 39.7% | 23.2% | 35.0% |
| `has_maximum__AND__has_minLength` | 105 | 39.0% | 15.1% | 48.1% |
| `has_maxItems__AND__has_pattern` | 108 | 38.9% | 10.4% | 31.0% |

## Selected pair heatmap candidates

The pair heatmap keeps the most interesting generated pairs. The ranking first requires usable support, then prioritizes the number of signals among timeout/under/over, then capped lift, delta, and support. This avoids filling the plot with rare pairs that only look strong because the denominator is tiny.

| feature_pair | schemas | risk_count | interest_score | timeout_group | under_group | over_group |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `has_maxLength__AND__has_pattern` | 296 | 3 | 3.03e+06 | 65.3% | 8.0% | 5.2% |
| `has_additionalProperties__AND__has_maxLength` | 372 | 3 | 3.03e+06 | 68.4% | 9.5% | 5.4% |
| `has_minLength__AND__has_pattern` | 328 | 3 | 3.02e+06 | 62.6% | 8.2% | 7.8% |
| `has_enum__AND__has_maxLength` | 308 | 3 | 3.02e+06 | 60.5% | 8.0% | 5.4% |
| `has_boolean_schema__AND__has_minLength` | 423 | 3 | 3.02e+06 | 64.7% | 9.8% | 8.7% |
| `has_maxItems__AND__has_minLength` | 71 | 3 | 3.02e+06 | 22.1% | 1.8% | 1.3% |
| `has_additionalProperties__AND__has_minLength` | 428 | 3 | 3.02e+06 | 64.7% | 10.1% | 8.9% |
| `has_maxItems__AND__has_maxLength` | 81 | 3 | 3.02e+06 | 23.2% | 2.3% | 1.5% |
| `has_maxLength__AND__has_patternProperties` | 55 | 3 | 3.02e+06 | 15.8% | 0.5% | 1.9% |
| `has_items__AND__has_maxLength` | 258 | 3 | 3.02e+06 | 46.3% | 7.4% | 5.1% |

## Very slow completed schemas and errors

| group | schemas | compile_min_s | compile_max_s | under_rate | over_rate | accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| fast | 1193 | 3.8e-05 | 1.05 | 17.1% | 21.3% | 81.3% |
| medium | 1192 | 1.05 | 1.78 | 16.4% | 13.3% | 84.7% |
| slow | 1192 | 1.78 | 4.17 | 15.5% | 20.5% | 82.7% |
| very_slow | 1193 | 4.18 | 597 | 13.1% | 22.7% | 84.0% |

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
| numeric bound: non-integer maximum | 13 | 101 |
| other compile error | 8 | 48 |
| boolean false schema | 3 | 7 |
| regex/string escape unsupported | 2 | 8 |
| schema node is array | 1 | 3 |

Top feature lift signals:

| feature | schemas | rate | lift |
| --- | --- | ---: | ---: |
| has_maximum | 18 | 5.1% | 26.18 |
| has_minimum | 20 | 2.6% | 15.57 |
| has_maxLength | 12 | 2.2% | 6.48 |
| has_minLength | 13 | 1.9% | 5.64 |
| has_pattern | 15 | 1.3% | 4.21 |
| has_boolean_schema | 21 | 0.9% | 4.10 |
| has_patternProperties | 5 | 1.6% | 3.36 |
| many_properties | 18 | 0.8% | 2.27 |
<!-- compile-error-causes:end -->
