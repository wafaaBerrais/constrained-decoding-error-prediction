# Statistical study: Github_global_no_hard / outlines

This folder contains schema-level statistics and SVG plots generated from the dataset run files. Compile time is analyzed once per schema, not once per test, to avoid overweighting schemas that contain many tests.

## Inputs

- `per_test_results.jsonl`: 17325 rows
- `timing_profile.csv`: 18154 rows
- `timed_out_schemas.jsonl`: 121 rows

## Main summary

| metric | value |
| --- | ---: |
| schemas | 4072 |
| completed schemas | 3951 |
| timeout schemas | 121 |
| schema timeout rate | 3.0% |
| tests | 18154 |
| completed tests | 17325 |
| coverage rate | 95.4% |
| accuracy on completed tests | 82.9% |
| under-constraint rate | 11.1% |
| over-constraint rate | 27.9% |
| median compile_grammar_s | 1.36 |
| p95 compile_grammar_s | 72.2 |
| max compile_grammar_s | 577 |

## Timeout stages

| timeout_stage | schemas |
| --- | ---: |
| building_index | 117 |
| completed | 2 |
| building_regex | 1 |
| loading_schema | 1 |

Timeout stages are inferred from the timeout log when available, otherwise from partial checkpoints in `timing_profile.csv`.

## Expected validity among timeout tests

| expected_validity | tests | share |
| --- | ---: | ---: |
| valid | 205 | 24.7% |
| invalid | 626 | 75.3% |

## Timing by schema status

| status | phase | n | mean_s | std_s | median_s | p95_s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| completed | compile_grammar_s | 3951 | 16.2 | 56.9 | 1.36 | 72.2 |
| completed | validation_loop_mean_s | 3423 | 0.0962 | 0.21 | 0.0439 | 0.343 |
| completed | compute_mask_mean_s | 3423 | 0.0429 | 0.0947 | 0.0192 | 0.153 |
| completed | commit_token_mean_s | 3423 | 0.0531 | 0.115 | 0.0243 | 0.188 |
| timeout | compile_grammar_s | 2 | 2.88 | 0.414 | 2.88 | 3.14 |
| timeout | validation_loop_mean_s | 1 | 0.135 | 0 | 0.135 | 0.135 |
| timeout | compute_mask_mean_s | 1 | 0.0304 | 0 | 0.0304 | 0.0304 |
| timeout | commit_token_mean_s | 1 | 0.0369 | 0 | 0.0369 | 0.0369 |
| timeout | timeout_elapsed_s | 121 | 601 | 1.54 | 601 | 602 |

For timeout schemas, phase values are partial checkpoints when available; `timeout_elapsed_s` is the supervisor elapsed time.

## Feature extraction

Raw structural features are `has_*` indicators for explicit JSON Schema keywords or benchmark categories. `$ref`, `$anchor`, `$dynamicRef`, `$defs`/`definitions`, `if`/`then`/`else`, and content keywords are mapped directly from the schema; `boolean_schema` is detected from boolean schema nodes and the benchmark `_boolSchema` metadata. `infinite-loop-detection` is only read from benchmark metadata when present because it is not a JSON Schema keyword.

Derived indicators (`large_enum`, `many_required`, `many_properties`, `deep_schema`) are kept separate from raw keyword features. Pair rows are generated automatically with `itertools.combinations(BASE_FEATURES, 2)`; a pair is present only when both base features are present in the same schema.

## Features associated with timeout

| feature | schemas | timeout with | timeout without | lift |
| --- | ---: | ---: | ---: | ---: |
| `has_type` | 4062 | 3.0% | 0.0% | inf |
| `has_maxLength` | 448 | 19.9% | 0.9% | 22.50 |
| `has_minLength` | 561 | 13.5% | 1.3% | 10.57 |
| `has_pattern` | 795 | 10.2% | 1.2% | 8.35 |
| `has_maxItems` | 143 | 15.4% | 2.5% | 6.11 |
| `has_additionalProperties` | 1840 | 4.9% | 1.4% | 3.52 |
| `has_enum` | 1385 | 5.6% | 1.6% | 3.52 |
| `has_boolean_schema` | 1783 | 4.9% | 1.5% | 3.28 |
| `has_maximum` | 217 | 8.3% | 2.7% | 3.10 |
| `many_properties` | 1437 | 5.1% | 1.8% | 2.79 |

## Features associated with under/over-constraint

| feature | schemas | under_rate | over_rate | correct_rate |
| --- | ---: | ---: | ---: | ---: |
| `has_exclusiveMaximum` | 3 | 0.0% | 100.0% | 73.7% |
| `has_propertyNames` | 3 | 0.0% | 100.0% | 76.5% |
| `has_contains` | 1 | 0.0% | 100.0% | 66.7% |
| `has_if_then_else` | 5 | 6.7% | 87.5% | 65.2% |
| `has_patternProperties` | 192 | 7.1% | 80.2% | 65.1% |
| `has_allOf` | 96 | 4.8% | 80.5% | 69.8% |
| `has_maxProperties` | 20 | 0.0% | 82.8% | 76.5% |
| `has_not` | 39 | 6.2% | 72.9% | 74.4% |
| `has_maximum` | 217 | 40.0% | 34.2% | 61.6% |
| `has_minimum` | 551 | 42.4% | 25.3% | 62.3% |

## Simple feature pairs

| feature_pair | schemas | timeout_rate | under_rate | over_rate |
| --- | ---: | ---: | ---: | ---: |
| `has_maxLength__AND__has_maxProperties` | 2 | 50.0% | 0.0% | 100.0% |
| `has_default__AND__has_maxItems` | 7 | 42.9% | 0.0% | 0.0% |
| `has_maxItems__AND__has_maxLength` | 40 | 42.5% | 7.0% | 73.7% |
| `has_maxItems__AND__has_minLength` | 41 | 39.0% | 9.7% | 65.9% |
| `has_maxItems__AND__has_multipleOf` | 3 | 33.3% | 30.8% | 0.0% |
| `has_default__AND__has_maxLength` | 68 | 32.4% | 19.0% | 45.3% |
| `has_default__AND__has_minLength` | 69 | 31.9% | 11.8% | 43.2% |
| `has_maxLength__AND__has_pattern` | 229 | 28.8% | 11.1% | 47.4% |
| `has_maxItems__AND__has_oneOf` | 32 | 28.1% | 2.1% | 76.9% |
| `has_maxItems__AND__has_pattern` | 66 | 27.3% | 3.6% | 40.2% |

## Selected pair heatmap candidates

The pair heatmap keeps the most interesting generated pairs. The ranking first requires usable support, then prioritizes the number of signals among timeout/under/over, then capped lift, delta, and support. This avoids filling the plot with rare pairs that only look strong because the denominator is tiny.

| feature_pair | schemas | risk_count | interest_score | timeout_group | under_group | over_group |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `has_default__AND__has_maxLength` | 68 | 3 | 3.01e+06 | 18.2% | 3.0% | 2.0% |
| `has_maxLength__AND__has_maximum` | 60 | 3 | 3.01e+06 | 13.2% | 2.3% | 2.3% |
| `has_maximum__AND__has_minLength` | 54 | 3 | 3.01e+06 | 10.7% | 2.1% | 2.0% |
| `has_maximum__AND__has_pattern` | 73 | 3 | 3.01e+06 | 12.4% | 4.4% | 2.7% |
| `has_maxLength__AND__has_minimum` | 94 | 3 | 3.01e+06 | 13.2% | 6.8% | 3.1% |
| `has_enum__AND__has_maximum` | 110 | 3 | 3.01e+06 | 14.9% | 6.3% | 4.4% |
| `has_default__AND__has_maximum` | 69 | 3 | 3.01e+06 | 8.3% | 7.5% | 1.7% |
| `has_minLength__AND__has_minimum` | 101 | 3 | 3e+06 | 10.7% | 7.4% | 3.2% |
| `has_maximum__AND__has_properties` | 212 | 3 | 3e+06 | 14.9% | 19.8% | 5.9% |
| `has_maximum__AND__has_minimum` | 212 | 3 | 3e+06 | 14.9% | 19.6% | 5.8% |

## Very slow completed schemas and errors

| group | schemas | compile_min_s | compile_max_s | under_rate | over_rate | accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| fast | 988 | 0.0253 | 0.551 | 6.5% | 63.1% | 71.6% |
| medium | 988 | 0.553 | 1.36 | 12.1% | 10.5% | 88.5% |
| slow | 987 | 1.36 | 5.14 | 15.4% | 14.1% | 85.0% |
| very_slow | 988 | 5.14 | 577 | 9.4% | 26.8% | 84.9% |

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
| unsupported schema structure | 97 | 380 |
| boolean false schema | 95 | 469 |
| DFA state limit | 51 | 263 |
| annotation-only/metadata schema | 46 | 184 |
| tokenizer/regex incompatible | 43 | 288 |
| format: path | 43 | 109 |
| format: topic | 24 | 51 |
| format: url | 23 | 103 |

Top feature lift signals:

| feature | schemas | rate | lift |
| --- | --- | ---: | ---: |
| has_patternProperties | 108 | 56.2% | 5.20 |
| has_not | 19 | 48.7% | 3.86 |
| has_maxProperties | 9 | 45.0% | 3.51 |
| has_minProperties | 20 | 32.8% | 2.59 |
| deep_schema | 138 | 28.0% | 2.57 |
| has_allOf | 28 | 29.2% | 2.32 |
| has_oneOf | 86 | 26.1% | 2.21 |
| has_anyOf | 58 | 26.2% | 2.15 |
<!-- compile-error-causes:end -->
