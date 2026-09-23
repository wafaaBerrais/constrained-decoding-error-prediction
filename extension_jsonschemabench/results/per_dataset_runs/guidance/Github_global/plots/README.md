# Statistical study: Github_global / guidance

This folder contains schema-level statistics and SVG plots generated from the dataset run files. Compile time is analyzed once per schema, not once per test, to avoid overweighting schemas that contain many tests.

## Inputs

- `per_test_results.jsonl`: 23053 rows
- `timing_profile.csv`: 23053 rows
- `timed_out_schemas.jsonl`: 0 rows

## Main summary

| metric | value |
| --- | ---: |
| schemas | 4960 |
| completed schemas | 4960 |
| timeout schemas | 0 |
| schema timeout rate | 0.0% |
| tests | 23053 |
| completed tests | 23053 |
| coverage rate | 100.0% |
| accuracy on completed tests | 79.1% |
| under-constraint rate | 0.0% |
| over-constraint rate | 61.3% |
| median compile_grammar_s | 0.00114 |
| p95 compile_grammar_s | 0.00426 |
| max compile_grammar_s | 0.0307 |

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
| completed | compile_grammar_s | 4960 | 0.00166 | 0.00181 | 0.00114 | 0.00426 |
| completed | validation_loop_mean_s | 4084 | 0.00328 | 0.00619 | 0.00179 | 0.0101 |
| completed | compute_mask_mean_s | 4084 | 0.00295 | 0.00585 | 0.00159 | 0.00915 |
| completed | commit_token_mean_s | 4084 | 0.000158 | 0.000274 | 9.39e-05 | 0.000493 |

For timeout schemas, phase values are partial checkpoints when available; `timeout_elapsed_s` is the supervisor elapsed time.

## Feature extraction

Raw structural features are `has_*` indicators for explicit JSON Schema keywords or benchmark categories. `$ref`, `$anchor`, `$dynamicRef`, `$defs`/`definitions`, `if`/`then`/`else`, and content keywords are mapped directly from the schema; `boolean_schema` is detected from boolean schema nodes and the benchmark `_boolSchema` metadata. `infinite-loop-detection` is only read from benchmark metadata when present because it is not a JSON Schema keyword.

Derived indicators (`large_enum`, `many_required`, `many_properties`, `deep_schema`) are kept separate from raw keyword features. Pair rows are generated automatically with `itertools.combinations(BASE_FEATURES, 2)`; a pair is present only when both base features are present in the same schema.

## Features associated with timeout

| feature | schemas | timeout with | timeout without | lift |
| --- | ---: | ---: | ---: | ---: |
| `has_additionalProperties` | 2364 | 0.0% | 0.0% | 0.00 |
| `has_allOf` | 149 | 0.0% | 0.0% | 0.00 |
| `has_anyOf` | 413 | 0.0% | 0.0% | 0.00 |
| `has_boolean_schema` | 2285 | 0.0% | 0.0% | 0.00 |
| `has_const` | 39 | 0.0% | 0.0% | 0.00 |
| `has_contains` | 1 | 0.0% | 0.0% | 0.00 |
| `has_content` | 3 | 0.0% | 0.0% | 0.00 |
| `has_default` | 1115 | 0.0% | 0.0% | 0.00 |
| `has_defs` | 1144 | 0.0% | 0.0% | 0.00 |
| `has_enum` | 1961 | 0.0% | 0.0% | 0.00 |

## Features associated with under/over-constraint

| feature | schemas | under_rate | over_rate | correct_rate |
| --- | ---: | ---: | ---: | ---: |
| `has_minProperties` | 85 | 0.0% | 100.0% | 69.4% |
| `has_not` | 56 | 0.0% | 100.0% | 73.7% |
| `has_maxProperties` | 31 | 0.0% | 100.0% | 72.9% |
| `has_propertyNames` | 11 | 0.0% | 100.0% | 78.4% |
| `has_if_then_else` | 10 | 0.0% | 100.0% | 75.0% |
| `has_contains` | 1 | 0.0% | 100.0% | 66.7% |
| `has_patternProperties` | 314 | 0.0% | 99.3% | 66.4% |
| `has_allOf` | 149 | 0.0% | 85.8% | 74.1% |
| `large_enum` | 753 | 0.0% | 85.7% | 73.5% |
| `has_oneOf` | 502 | 0.0% | 85.4% | 70.2% |

## Simple feature pairs

| feature_pair | schemas | timeout_rate | under_rate | over_rate |
| --- | ---: | ---: | ---: | ---: |
| `has_properties__AND__has_type` | 4834 | 0.0% | 0.0% | 61.7% |
| `has_properties__AND__has_required` | 3620 | 0.0% | 0.0% | 62.6% |
| `has_required__AND__has_type` | 3619 | 0.0% | 0.0% | 62.6% |
| `has_items__AND__has_type` | 2399 | 0.0% | 0.0% | 71.2% |
| `has_items__AND__has_properties` | 2371 | 0.0% | 0.0% | 71.5% |
| `has_additionalProperties__AND__has_type` | 2363 | 0.0% | 0.0% | 65.4% |
| `has_additionalProperties__AND__has_properties` | 2338 | 0.0% | 0.0% | 65.4% |
| `has_boolean_schema__AND__has_type` | 2284 | 0.0% | 0.0% | 65.5% |
| `has_additionalProperties__AND__has_boolean_schema` | 2270 | 0.0% | 0.0% | 65.6% |
| `has_boolean_schema__AND__has_properties` | 2266 | 0.0% | 0.0% | 65.5% |

## Selected pair heatmap candidates

The pair heatmap keeps the most interesting generated pairs. The ranking first requires usable support, then prioritizes the number of signals among timeout/under/over, then capped lift, delta, and support. This avoids filling the plot with rare pairs that only look strong because the denominator is tiny.

| feature_pair | schemas | risk_count | interest_score | timeout_group | under_group | over_group |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `has_patternProperties__AND__has_type` | 313 | 1 | 1e+06 | 0.0% | 0.0% | 10.5% |
| `has_patternProperties__AND__has_required` | 242 | 1 | 1e+06 | 0.0% | 0.0% | 8.2% |
| `has_patternProperties__AND__has_properties` | 291 | 1 | 1e+06 | 0.0% | 0.0% | 9.7% |
| `has_additionalProperties__AND__has_patternProperties` | 250 | 1 | 1e+06 | 0.0% | 0.0% | 8.4% |
| `has_boolean_schema__AND__has_patternProperties` | 245 | 1 | 1e+06 | 0.0% | 0.0% | 8.2% |
| `has_items__AND__has_patternProperties` | 206 | 1 | 1e+06 | 0.0% | 0.0% | 6.9% |
| `has_oneOf__AND__has_patternProperties` | 115 | 1 | 1e+06 | 0.0% | 0.0% | 3.9% |
| `has_enum__AND__has_patternProperties` | 156 | 1 | 1e+06 | 0.0% | 0.0% | 5.2% |
| `has_minLength__AND__has_patternProperties` | 91 | 1 | 1e+06 | 0.0% | 0.0% | 3.1% |
| `has_minProperties__AND__has_type` | 85 | 1 | 1e+06 | 0.0% | 0.0% | 2.9% |

## Very slow completed schemas and errors

| group | schemas | compile_min_s | compile_max_s | under_rate | over_rate | accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| fast | 1240 | 0.000183 | 0.000776 | 0.0% | 71.2% | 73.6% |
| medium | 1243 | 0.000777 | 0.00114 | 0.0% | 32.7% | 87.9% |
| slow | 1238 | 0.00115 | 0.00189 | 0.0% | 60.4% | 79.9% |
| very_slow | 1239 | 0.00189 | 0.0307 | 0.0% | 78.5% | 76.3% |

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
| keyword: patternProperties | 288 | 1460 |
| format: uri | 127 | 594 |
| keyword: oneOf | 122 | 522 |
| keyword: minProperties | 66 | 321 |
| format: path | 44 | 111 |
| keyword: dependencies | 39 | 168 |
| keyword: not | 37 | 189 |
| format: url | 27 | 123 |

Top feature lift signals:

| feature | schemas | rate | lift |
| --- | --- | ---: | ---: |
| has_patternProperties | 310 | 98.7% | 8.10 |
| has_minProperties | 84 | 98.8% | 6.08 |
| has_not | 56 | 100.0% | 5.98 |
| has_propertyNames | 11 | 100.0% | 5.72 |
| has_maxProperties | 30 | 96.8% | 5.64 |
| has_oneOf | 329 | 65.5% | 5.34 |
| has_if_then_else | 8 | 80.0% | 4.56 |
| has_allOf | 82 | 55.0% | 3.33 |
<!-- compile-error-causes:end -->
