# Mutation sensitivity

<!-- toc:start -->
**Table of contents**

- [Run it](#run-it)
- [What the measurements mean](#what-the-measurements-mean)
- [Scope and reproducibility](#scope-and-reproducibility)
<!-- toc:end -->

[Compiler guide](README.md) · [CLI reference](../cli/README.md)

This diagnostic answers three questions:

- Which individual values changes affect the rendered manifests most?
- Which pairs behave differently together than their separate changes suggest?
- How much change accumulates along a sequence, and how much remains at its end?

It renders explicit, schema-valid configurations. It does not change filtering, claim mathematical singularities, or
collapse apparently unchanged regions. Two individually silent mutations can still expose an interaction together.

## Run it

The chart needs values.yaml, values.schema.json and its dependencies already present locally.
Put the changes to examine in a JSON file. Paths are arrays of object keys or zero-based array indices:

~~~json
[
  {"name": "change-message", "path": ["message"], "value": "world"},
  {"name": "disable-annotation", "path": ["enabled"], "value": false}
]
~~~

For the repository's ConfigMap example, save the JSON above as mutations.json and run:

~~~bash
bash scripts/project-run.sh hypothesis-helm-sensitivity examples/configmap --mutations mutations.json --plot
~~~

The wrapper uses this checkout's .venv even when your shell has another environment active. If you installed the package
into your active environment, you can invoke hypothesis-helm-sensitivity directly. New console commands require reinstalling
the project in that environment; an editable source checkout alone does not create new command launchers.

Reports default to studies/sensitivity/runs/ with a unique timestamp. Use --output to choose another fresh directory.
[The published study and plots](../../studies/sensitivity/README.md) include the mutation input file. The optional plots require the benchmarking extra.
The command writes README.md, results.json and, with --plot, sensitivity.png and sensitivity.svg.

To reproduce the denser study on the shared benchmark chart:

~~~bash
bash scripts/project-run.sh hypothesis-helm-benchmark sensitivity --inputs 48 --components 64 --time-limit 9m
~~~

This measures 48 distinct input flips, all 1,128 unordered pairs, and a 48-step sequence at one baseline.
Successful benchmark runs automatically replace the published results and plots in `studies/sensitivity/`.
Every run is also retained under `studies/sensitivity/runs/`. Incomplete or invalid measurements leave the published study unchanged.
Use `--output` to save a separate run without updating the published study.
Increase `--inputs` for more points; pair checks grow as `n(n-1)/2`. `--components` controls how many chart structures share
those inputs. The seed fixes their wiring, and the baseline alternates true and false in field order.
Refresh uses these same settings. Plots show all measured points and pairs; gray heatmap cells have no comparable measurement.
Numeric mutation IDs refer to input-file order. Summary tables show the 20 largest effects; JSON retains every result.

The default budget is three minutes, up to 100 mutations and 100 unordered pairs. Override these with --time-limit,
--max-mutations and --max-pairs. --max-pairs 0 measures singles and the supplied sequence without pair analysis.
The input file determines mutation order. A truncated analysis exits 1 and retains completed measurements; completion
exits 0 even if individual configurations produced render errors. Read their explicit statuses in the report.

## What the measurements mean

**Output distance** counts added and removed JSON path/value indicators. Replacing one scalar counts twice:
one old indicator disappears and one new indicator appears. Object key order is ignored; resource-document and array order
are retained. Empty containers count as leaves. The score measures syntactic output change, not security impact, runtime
resource usage or bug severity. For example, changing replicas from 1 to 100 affects one manifest field, not 99 rendered Pods.

**Interaction magnitude** is the L1 norm of the mixed finite difference:
F(a and b) - F(a) - F(b) + F(baseline), where F is the leaf-indicator vector.
Both application orders must reach the same input configuration. Otherwise the pair is reported as order-dependent.
A nonzero value means non-additivity in this chosen representation; it is not geometric curvature.
Schema-rejected inputs and rendering failures receive no distance or interaction magnitude.

**Cumulative path length** adds the distance of each successive change in the supplied order.
**Endpoint displacement** compares the current output directly with the baseline. A sequence can travel away and return:
its cumulative length stays positive while its endpoint displacement becomes zero.
The sequence stops on its first invalid or failed step.

## Scope and reproducibility

Hold the chart, dependencies and invocation context fixed. --release, --namespace, --kube-version and --helm control that
context. Configurations are cached only within this invocation. The analysis assumes deterministic rendering; templates that
use randomness, clocks or external lookup can confound the measurements. It does not independently prove determinism.

Pair checks cover only the supplied mutations at this baseline; higher-order interactions can remain invisible.
The JSON explicitly records pruning_authorized: false. Zero distance, low accumulated distance and zero pairwise interaction
are observations, not evidence that an entire input region is safe to omit.
