# One configurable benchmark chart

[Benchmarking](../README.md) · [Chart](../chart)

The generator is the common chart definition for every synthetic study. A command
compiles each setting into the same temporary directory, measures it, and saves its
parameters. It releases the directory after the command's workers finish. Concurrent
commands use separate directories.

The [combined stress parameters](../chart/benchmark-parameters.yaml)
start with twelve named Boolean inputs and the controls below. Edit the parameter
file and regenerate the chart to change its shape. The generated `values.yaml`
contains the inputs that vary during testing; the topology controls are held fixed
for each measurement.

| Control | Starts at | Reduced to | Effect |
| --- | ---: | ---: | --- |
| `coupled_pairs` | 2 | 0 | Pairs of inputs required to agree. |
| `gate_depth` | 5 | 0 | Nested conditions guarding an optional resource. |
| `interaction_order` | 5 | 1 | Inputs jointly required to emit another resource. |
| `shared_output_count` | 4 | 1 | Resources affected by the same input. |
| `boundary_regions` | 4 | 1 | Distinct output regions selected by two inputs. |
| `equivalent_inputs` | 4 | 0 | Inputs whose changes leave manifests unchanged. |
| `faults_enabled` | `true` | unchanged | Enable the six fixed defect families. |

`stress` decreases each numeric control by one, in table order. The initial setting
plus those changes gives 22 measurements per strategy. Field names, defect triggers,
and seed remain fixed. Removing constraints increases the valid input space;
removing equivalent inputs can increase render cost. Costs need not decrease at
every step. This is a deliberately difficult case, not a proven maximum.

The defects produce an incorrect ConfigMap value for known input interactions.
The study's independent oracle detects these semantic errors; ordinary YAML or
Kubernetes schema validation would accept the manifests. Results show both defect
families found and erroneous inputs evaluated, since many inputs can expose the
same defect. Reused exact-equivalent results and actual Helm renders are counted
separately.

Coupled schema constraints currently require conservative compiler fallback. The
first steps expose this limitation; later steps exercise supported topology
filtering. No unsupported condition is assumed safe to prune.

```sh
# Inspect the complete progression without executing benchmarks.
hypothesis-helm-benchmark stress --generate-only --output benchmarks/runs/stress-plan

# Export one case into a chart directory for inspection or manual rendering.
hypothesis-helm-benchmark generate \
  --parameters benchmarks/runs/stress-plan/cases/00-worst-case.yaml --output benchmarks/runs/chart

# Measure the progression and save its plots and tables.
hypothesis-helm-benchmark stress --time-limit 9m --output benchmarks/runs/stress
```

The time limit applies to each strategy at each step, not the whole command.
Five strategies run at each setting: unfiltered, exact equivalence, random,
topology, and combined. Time-limited results show only the work completed.

Other studies select profiles of this same generator: [normal quantiles](standard.yaml),
[gated resources](topology.yaml), individual topology categories, mixed depths, and
seeded faults. Their existing distribution and fault controls remain available.

```sh
hypothesis-helm-benchmark --parameters benchmarks/fixture/standard.yaml \
  run --time-limit 9m --output benchmarks/runs/performance
```

Each retained case records generator parameters, fault operations, and oracle
metadata. Replay requires the matching generator version; measurement metadata
records the application source fingerprint. Historical published results keep
their original snapshots rather than being relabeled as new measurements.
