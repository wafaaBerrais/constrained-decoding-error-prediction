# Statistical study: Kubernetes / guidance

This folder contains schema-level statistics and SVG plots generated from the dataset run files. Compile time is analyzed once per schema, not once per test, to avoid overweighting schemas that contain many tests.

## Inputs

- `per_test_results.jsonl`: 4588 rows
- `timing_profile.csv`: 4545 rows
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
| accuracy on completed tests | 81.5% |
| under-constraint rate | 0.0% |
| over-constraint rate | 50.5% |
| median compile_grammar_s | 0.0021 |
| p95 compile_grammar_s | 0.0143 |
| max compile_grammar_s | 0.0561 |

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
| completed | compile_grammar_s | 996 | 0.0042 | 0.00669 | 0.0021 | 0.0143 |
| completed | validation_loop_mean_s | 966 | 0.00324 | 0.00291 | 0.00237 | 0.00888 |
| completed | compute_mask_mean_s | 971 | 0.00284 | 0.00262 | 0.00211 | 0.0079 |
| completed | commit_token_mean_s | 971 | 0.000201 | 0.000187 | 0.000147 | 0.000563 |

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
| `large_enum` | 1 | 0.0% | 100.0% | 71.4% |
| `has_enum` | 250 | 0.0% | 83.6% | 71.1% |
| `many_required` | 360 | 0.0% | 80.9% | 69.5% |
| `many_properties` | 464 | 0.0% | 77.9% | 70.6% |
| `has_additionalProperties` | 408 | 0.0% | 72.1% | 73.7% |
| `has_oneOf` | 239 | 0.0% | 66.8% | 65.4% |
| `has_items` | 601 | 0.0% | 65.2% | 76.3% |
| `has_defs` | 731 | 0.0% | 58.7% | 77.9% |
| `has_ref` | 731 | 0.0% | 58.7% | 77.9% |
| `has_required` | 807 | 0.0% | 55.0% | 79.5% |

## Simple feature pairs

| feature_pair | schemas | timeout_rate | under_rate | over_rate |
| --- | ---: | ---: | ---: | ---: |
| `has_properties__AND__has_type` | 1010 | 0.0% | 0.0% | 50.7% |
| `has_properties__AND__has_required` | 807 | 0.0% | 0.0% | 55.0% |
| `has_required__AND__has_type` | 807 | 0.0% | 0.0% | 55.0% |
| `has_defs__AND__has_properties` | 731 | 0.0% | 0.0% | 58.7% |
| `has_defs__AND__has_ref` | 731 | 0.0% | 0.0% | 58.7% |
| `has_defs__AND__has_type` | 731 | 0.0% | 0.0% | 58.7% |
| `has_properties__AND__has_ref` | 731 | 0.0% | 0.0% | 58.7% |
| `has_ref__AND__has_type` | 731 | 0.0% | 0.0% | 58.7% |
| `has_defs__AND__has_required` | 636 | 0.0% | 0.0% | 61.2% |
| `has_ref__AND__has_required` | 636 | 0.0% | 0.0% | 61.2% |

## Selected pair heatmap candidates

The pair heatmap keeps the most interesting generated pairs. The ranking first requires usable support, then prioritizes the number of signals among timeout/under/over, then capped lift, delta, and support. This avoids filling the plot with rare pairs that only look strong because the denominator is tiny.

| feature_pair | schemas | risk_count | interest_score | timeout_group | under_group | over_group |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `has_properties__AND__has_type` | 1010 | 1 | 1.05e+06 | 0.0% | 0.0% | 100.0% |
| `has_items__AND__has_properties` | 601 | 1 | 1e+06 | 0.0% | 0.0% | 78.5% |
| `has_items__AND__has_type` | 601 | 1 | 1e+06 | 0.0% | 0.0% | 78.5% |
| `has_defs__AND__has_items` | 539 | 1 | 1e+06 | 0.0% | 0.0% | 73.5% |
| `has_items__AND__has_ref` | 539 | 1 | 1e+06 | 0.0% | 0.0% | 73.5% |
| `has_defs__AND__has_properties` | 731 | 1 | 1e+06 | 0.0% | 0.0% | 86.0% |
| `has_defs__AND__has_ref` | 731 | 1 | 1e+06 | 0.0% | 0.0% | 86.0% |
| `has_defs__AND__has_type` | 731 | 1 | 1e+06 | 0.0% | 0.0% | 86.0% |
| `has_properties__AND__has_ref` | 731 | 1 | 1e+06 | 0.0% | 0.0% | 86.0% |
| `has_ref__AND__has_type` | 731 | 1 | 1e+06 | 0.0% | 0.0% | 86.0% |

## Very slow completed schemas and errors

| group | schemas | compile_min_s | compile_max_s | under_rate | over_rate | accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| fast | 249 | 0.00032 | 0.00148 | 0.0% | 28.5% | 89.8% |
| medium | 249 | 0.00148 | 0.0021 | 0.0% | 34.2% | 87.9% |
| slow | 249 | 0.0021 | 0.00384 | 0.0% | 54.3% | 80.7% |
| very_slow | 249 | 0.00389 | 0.0561 | 0.0% | 84.6% | 66.4% |

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
