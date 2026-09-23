# Refined Feature Analysis

- Dataset: `Kubernetes`
- Framework: `guidance`
- Schemas analyzed: 1014
- Tests analyzed: 4588
- Baseline UNDER rate: 0.0000
- Baseline OVER rate: 0.1850

## Numeric Results

No non-low-support context exceeded the support thresholds.

## PatternProperties Results

- `instance_has_unmatched_keys=true`: over_rate=0.299, lift=1.62, support_tests=184, support_schemas=123.

## Not Results

No non-low-support context exceeded the support thresholds.

## Combinator Results

- `combinator_branch_count_bucket=2`: over_rate=0.346, lift=1.87, support_tests=772, support_schemas=239.
- `combinator_type=oneOf`: over_rate=0.346, lift=1.87, support_tests=772, support_schemas=239.

## Top UNDER Contexts By Lift


## Top OVER Contexts By Lift

- `combinator_branch_count_bucket=2`: lift=1.87, rate=0.346, tests=772.
- `combinator_type=oneOf`: lift=1.87, rate=0.346, tests=772.
- `instance_has_unmatched_keys=true`: lift=1.62, rate=0.299, tests=184.

## Limitations

- These results are correlational.
- A feature with high lift is not automatically the exact cause of the observed failure.
- Low-support contexts should be interpreted cautiously.
- HDD validation or controlled schema mutations can be used next to test causal hypotheses.
