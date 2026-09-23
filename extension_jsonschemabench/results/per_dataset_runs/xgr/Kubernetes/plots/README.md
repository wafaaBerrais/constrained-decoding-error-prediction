# Statistical study: Kubernetes / xgr

This folder contains schema-level statistics and SVG plots generated from the dataset run files. Compile time is analyzed once per schema, not once per test, to avoid overweighting schemas that contain many tests.

## Inputs

- `per_test_results.jsonl`: 4588 rows
- `timing_profile.csv`: 4588 rows
- `timed_out_schemas.jsonl`: 0 rows

## Main summary

| metric | value |
| --- | ---: |
| schemas | 1014 |
| completed schemas | 1014 |
| timeout schemas | 0 |
| schema timeout rate | 0.0% |
| tests | 4588 |
| completed tests | 4588 |
| coverage rate | 100.0% |
| accuracy on completed tests | 92.5% |
| under-constraint rate | 0.0% |
| over-constraint rate | 20.6% |
| median compile_grammar_s | 1.33 |
| p95 compile_grammar_s | 31.8 |
| max compile_grammar_s | 108 |

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
| completed | compile_grammar_s | 1014 | 6.75 | 16.2 | 1.33 | 31.8 |
| completed | validation_loop_mean_s | 1012 | 0.014 | 0.314 | 0.00126 | 0.0155 |
| completed | compute_mask_mean_s | 1013 | 0.0137 | 0.312 | 0.00114 | 0.0151 |
| completed | commit_token_mean_s | 1013 | 7.11e-05 | 0.000228 | 3.51e-05 | 0.000208 |

For timeout schemas, phase values are partial checkpoints when available; `timeout_elapsed_s` is the supervisor elapsed time.

## Feature extraction

Raw structural features are `has_*` indicators for explicit JSON Schema keywords or benchmark categories. `$ref`, `$anchor`, `$dynamicRef`, `$defs`/`definitions`, `if`/`then`/`else`, and content keywords are mapped directly from the schema; `boolean_schema` is detected from boolean schema nodes and the benchmark `_boolSchema` metadata. `infinite-loop-detection` is only read from benchmark metadata when present because it is not a JSON Schema keyword.

Derived indicators (`large_enum`, `many_required`, `many_properties`, `deep_schema`) are kept separate from raw keyword features. Pair rows are generated automatically with `itertools.combinations(BASE_FEATURES, 2)`; a pair is present only when both base features are present in the same schema.

## Features associated with timeout

| feature | schemas | timeout with | timeout without | lift |
| --- | ---: | ---: | ---: | ---: |
| `has_additionalProperties` | 408 | 0.0% | 0.0% | 0.00 |
| `has_defs` | 731 | 0.0% | 0.0% | 0.00 |
| `has_enum` | 250 | 0.0% | 0.0% | 0.00 |
| `has_items` | 601 | 0.0% | 0.0% | 0.00 |
| `has_oneOf` | 239 | 0.0% | 0.0% | 0.00 |
| `has_properties` | 1010 | 0.0% | 0.0% | 0.00 |
| `has_ref` | 731 | 0.0% | 0.0% | 0.00 |
| `has_required` | 807 | 0.0% | 0.0% | 0.00 |
| `has_type` | 1014 | 0.0% | 0.0% | 0.00 |
| `large_enum` | 1 | 0.0% | 0.0% | 0.00 |

## Features associated with under/over-constraint

| feature | schemas | under_rate | over_rate | correct_rate |
| --- | ---: | ---: | ---: | ---: |
| `has_enum` | 250 | 0.0% | 57.5% | 80.1% |
| `large_enum` | 1 | 0.0% | 50.0% | 85.7% |
| `many_required` | 360 | 0.0% | 40.7% | 84.7% |
| `has_additionalProperties` | 408 | 0.0% | 39.9% | 85.5% |
| `many_properties` | 464 | 0.0% | 35.8% | 86.5% |
| `has_items` | 601 | 0.0% | 28.8% | 89.5% |
| `has_defs` | 731 | 0.0% | 25.8% | 90.3% |
| `has_ref` | 731 | 0.0% | 25.8% | 90.3% |
| `has_required` | 807 | 0.0% | 24.3% | 90.9% |
| `has_properties` | 1010 | 0.0% | 20.6% | 92.4% |

## Simple feature pairs

| feature_pair | schemas | timeout_rate | under_rate | over_rate |
| --- | ---: | ---: | ---: | ---: |
| `has_properties__AND__has_type` | 1010 | 0.0% | 0.0% | 20.6% |
| `has_properties__AND__has_required` | 807 | 0.0% | 0.0% | 24.3% |
| `has_required__AND__has_type` | 807 | 0.0% | 0.0% | 24.3% |
| `has_defs__AND__has_properties` | 731 | 0.0% | 0.0% | 25.8% |
| `has_defs__AND__has_ref` | 731 | 0.0% | 0.0% | 25.8% |
| `has_defs__AND__has_type` | 731 | 0.0% | 0.0% | 25.8% |
| `has_properties__AND__has_ref` | 731 | 0.0% | 0.0% | 25.8% |
| `has_ref__AND__has_type` | 731 | 0.0% | 0.0% | 25.8% |
| `has_defs__AND__has_required` | 636 | 0.0% | 0.0% | 28.2% |
| `has_ref__AND__has_required` | 636 | 0.0% | 0.0% | 28.2% |

## Selected pair heatmap candidates

The pair heatmap keeps the most interesting generated pairs. The ranking first requires usable support, then prioritizes the number of signals among timeout/under/over, then capped lift, delta, and support. This avoids filling the plot with rare pairs that only look strong because the denominator is tiny.

| feature_pair | schemas | risk_count | interest_score | timeout_group | under_group | over_group |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `has_properties__AND__has_type` | 1010 | 1 | 1.05e+06 | 0.0% | 0.0% | 100.0% |
| `has_additionalProperties__AND__has_enum` | 238 | 1 | 1.01e+06 | 0.0% | 0.0% | 63.1% |
| `has_enum__AND__has_required` | 246 | 1 | 1.01e+06 | 0.0% | 0.0% | 63.1% |
| `has_defs__AND__has_enum` | 250 | 1 | 1.01e+06 | 0.0% | 0.0% | 63.5% |
| `has_enum__AND__has_items` | 250 | 1 | 1.01e+06 | 0.0% | 0.0% | 63.5% |
| `has_enum__AND__has_properties` | 250 | 1 | 1.01e+06 | 0.0% | 0.0% | 63.5% |
| `has_enum__AND__has_ref` | 250 | 1 | 1.01e+06 | 0.0% | 0.0% | 63.5% |
| `has_enum__AND__has_type` | 250 | 1 | 1.01e+06 | 0.0% | 0.0% | 63.5% |
| `has_additionalProperties__AND__has_items` | 385 | 1 | 1.01e+06 | 0.0% | 0.0% | 75.0% |
| `has_additionalProperties__AND__has_defs` | 402 | 1 | 1.01e+06 | 0.0% | 0.0% | 76.2% |

## Very slow completed schemas and errors

| group | schemas | compile_min_s | compile_max_s | under_rate | over_rate | accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| fast | 256 | 3.2e-05 | 0.000103 | 0.0% | 6.4% | 97.7% |
| medium | 251 | 0.000104 | 1.32 | 0.0% | 7.9% | 96.9% |
| slow | 253 | 1.33 | 7.12 | 0.0% | 12.8% | 95.6% |
| very_slow | 254 | 7.19 | 108 | 0.0% | 53.7% | 79.8% |

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
