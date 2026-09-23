# Coverage Feature Filter

This report selects retained features from model importances, decision-tree rules, and numeric/combinator domain overrides.

## Settings

- Minimum importance share: `0.003`
- Cumulative importance share: `0.95`
- Minimum retained features: `12`
- Maximum retained features: `none`
- Rule features included: `True`
- Domain overrides: numeric and combinator features listed in the filtering script.

## Summary

| framework | target | candidates | retained | dropped | rule features |
|---|---|---:|---:|---:|---:|
| guidance | over | 231 | 138 | 93 | 11 |
| guidance | under | 0 | 0 | 0 | 0 |
| outlines | over | 118 | 81 | 37 | 12 |
| outlines | under | 317 | 167 | 150 | 15 |
| xgr | over | 256 | 139 | 117 | 16 |
| xgr | under | 316 | 185 | 131 | 18 |

Each target folder contains:

- `feature_filter_decisions.csv`: full audit for every candidate feature.
- `retained_features.txt`: features to keep for a simplified model.
- `dropped_features.txt`: low-impact or policy-excluded features.
