# Refined Feature Analysis

- Dataset: `Kubernetes`
- Framework: `xgr`
- Schemas analyzed: 1014
- Tests analyzed: 4588
- Baseline UNDER rate: 0.0000
- Baseline OVER rate: 0.0754

## Numeric Results

No non-low-support context exceeded the support thresholds.

## PatternProperties Results

- `instance_has_unmatched_keys=true`: over_rate=0.440, lift=5.84, support_tests=184, support_schemas=123.

## Not Results

No non-low-support context exceeded the support thresholds.

## Combinator Results

No non-low-support context exceeded the support thresholds.

## Top UNDER Contexts By Lift


## Top OVER Contexts By Lift

- `instance_has_unmatched_keys=true`: lift=5.84, rate=0.440, tests=184.

## Limitations

- These results are correlational.
- A feature with high lift is not automatically the exact cause of the observed failure.
- Low-support contexts should be interpreted cautiously.
- HDD validation or controlled schema mutations can be used next to test causal hypotheses.
