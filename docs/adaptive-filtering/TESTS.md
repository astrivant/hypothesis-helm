# Sampling proof obligations and test matrix

[Policy](README.md) · [Measured matrix and graphs](../../studies/calibration-variation/MATRIX.md)

These checks establish selector behavior. They do not prove that omitted inputs cannot reveal a bug.
The empirical matrix measures that separate question on generated charts with known defects.
The [load test](../../studies/filtering/README.md) separately measures runtime against input count and nested template conditions.

## Deterministic argument

Let `E` be the finite eligible set, `P` its protected subset, `m` the case floor and `f` the changed-field floor.
The initial selected set contains `P`. It adds unique case identities from a seed-dependent total order until its size is
`min(|E|, max(ceil(0.7 × |E|), m, |P|))`. Further additions stop when the union of changed paths reaches `f` or `E` is exhausted.

This construction preserves protected cases, avoids duplicates, meets the case quota whenever possible, and either meets the
field floor or keeps every eligible case. Permuting the input list changes presentation order but cannot change membership.
An empty eligible set remains empty. It does not prove that every branch is represented: the compiler determines `P`, and unresolved
analysis disables the extra percentage sampling.

Nearby lookup imposes range and compatibility checks; these are policy boundaries, not a mathematical bound on bug recall.
Maximum output complexity alone cannot bound the probability of a rare defect.

## Regression matrix

| Obligation | Test | Evidence |
| --- | --- | --- |
| Protected cases survive; identities are unique; membership ignores traversal order | `test_sampling_preserves_protected_cases_and_order_independence` | Hypothesis-generated seeds, percentages and field floors |
| A rare changed path can enlarge the sample; impossible floors retain all cases | `test_field_floor_adds_cases_in_seeded_order` | Deliberately rare path |
| Exact evidence wins; nearby evidence cannot extrapolate | `test_nearby_lookup_is_bounded_and_exact_takes_precedence` | Interior and boundary targets |
| Nearby selection takes the greatest case and field floors separately | `test_nearby_selection_uses_maximum_neighbor_floors` | Native planner with two surrounding profiles |
| Empty eligible populations do not invent work | `test_empty_population_remains_empty` | Empty-plan base case |
| Different domains, types, depth, settings or versions cannot borrow unsupported evidence | `test_incompatible_profiles_keep_all_cases` | Parameterized descriptor changes |
| Invalid radii cannot authorize sampling | `test_invalid_radius_disables_approximation` | Nonpositive, nonfinite and excessive radii |
| Missing, incomplete, unknown or unmatched calibration keeps the filtered plan | `test_uncalibrated_cases_are_retained` | Native generated chart |
| Every chart visit recalculates; stale snapshots cannot authorize omissions | `test_repeated_visits_recompute_complexity`, `test_stale_snapshot_disables_selection` | Repeated visits and changed source bytes |
| The preset executes selected cases and enables expansion | `test_calibrated_selection_runs_real_helm` | Real Helm CLI execution and report accounting |
| Conflicting presets are rejected in either order | `test_presets_are_exclusive` | Local test and remote scan parsers |
| Nearby comparisons exclude exact targets; weak evidence or missed rare bugs disables activation | `test_matrix_excludes_target_and_requires_useful_measured_reduction` | Controlled reference population and generated matrix |
| Matrix artifacts retain a complete reference and plots can be regenerated | `test_calibration_command_writes_reproducible_matrix_and_plots` | Native Helm study, PNG/SVG, JSON/CSV and plot-only execution |
| Topology retention equals the sum of rounded group quotas | `test_supported_region_retention_formula` | Generated group sizes, trim depths and seeds |
| Runtime comparisons use paired seeds, real execution and consistent phase accounting | `test_native_filtering_load_matrix` | Native four-method study and plot-only reproduction |
| Benchmark presets match the real engine's calibrated selection | `test_benchmark_preset_matches_native_calibrated_selection` | Packaged calibration, nonzero omissions and real Helm execution |
| Unmatched structural cases retain ordinary filtering | `test_matrix_strategy_contracts` | All six topology families and seven strategies |
| PCA expansion uses visited Helm observations and never duplicates a case | `test_pca_presets_expand_only_observed_failures` | Paired correct and failing observations |
| Time-limited measurements retain unfinished counts | `test_execution_ceiling_is_not_a_completed_timing` | Native execution with a deliberately short deadline |
| An overlapping execution deadline cannot interrupt child cleanup | `test_timeout_alarm_waits_for_real_child_cleanup` | Real child, injected subprocess timeout and POSIX alarm |
| A deadline cannot hide a cleanup failure | `test_deferred_deadline_preserves_cleanup_failure` | Failed join retained alongside the deferred deadline |
| Publication rejects missing presets, duplicated runs and inconsistent timing phases | `test_refresh_requires_complete_stress_matrix` | Damaged structural, PCA, expansion, nesting, stress, calibration and load-test ledgers |

Tests live in [test_aggressive.py](../../pkg/hypothesis_helm/tests/test_aggressive.py) and
[test_calibration_matrix.py](../../pkg/hypothesis_helm/tests/test_calibration_matrix.py).
Runtime checks are in [test_filtering_load.py](../../pkg/hypothesis_helm/tests/test_filtering_load.py), with publication checks in
[test_refresh.py](../../pkg/hypothesis_helm/tests/test_refresh.py).

```sh
pytest pkg/hypothesis_helm/tests/test_aggressive.py pkg/hypothesis_helm/tests/test_calibration_matrix.py
```

## Empirical matrix

The study varies 6, 7 and 8 Boolean inputs, depths 1 through 5, and two seeded placements of injected defects.
For every chart it compares ordinary filtering, exact-profile sampling and nearby matching at four candidate radii.
The reference is the complete rendered population, checked against a separate defect-trigger oracle.

A radius is enabled only if at least two target profiles permit additional case reduction and every matched target reaches
96% distinct known-bug recall and its measured field floor in at least 95 of 100 seeds.
All exact matches for each target are removed from nearby lookup. Unmatched cells retain ordinary filtering.
The matrix records retained counts, recall and successful seed counts, including fallback cells.

This acceptance rule is an empirical calibration criterion. The fixtures and seeds also select the radius, and there is no
independent validation set. For fixtures with only three or four known defects, reaching 96% recall requires finding all of them.
A production chart may contain failures absent from these synthetic fixtures, even when its descriptor matches exactly.
