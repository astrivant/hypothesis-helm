# Getting started

<!-- toc:start -->
**Table of contents**

- [Install](#install)
- [Quick Start](#quick-start)
- [Caching and validation](#caching-and-validation)
<!-- toc:end -->

[Documentation](../README.md) · [Project](../../README.md)

## Install

Requires Helm 4 and Python 3.13+. The plugin uses Helm 4’s
[versioned CLI plugin format](https://helm.sh/docs/plugins/migrate/). The plugin installs its Python dependencies,
including the test runner, automatically.

```sh
PYTHON=python3.13 helm plugin install https://github.com/astrivant/hypothesis-helm
```

To install from a local checkout:

```sh
PYTHON=python3.13 helm plugin install .
```

## Quick Start

Test a chart using its values schema and template references:

```sh
helm hypothesis test ./path/to/chart
```

Audit values, configure test generation, or rerun a saved suite:

```sh
helm hypothesis audit ./path/to/chart
helm hypothesis test ./path/to/chart --strict
helm hypothesis test ./path/to/chart --paths --max-examples 50 --seed 42
helm hypothesis test ./path/to/chart --permutations 2
helm hypothesis test ./path/to/chart --exhaustive-group ingress,service
helm hypothesis test ./path/to/chart --dry-run
helm hypothesis test ./path/to/chart --match replicas
helm hypothesis generate ./path/to/chart --output generated-tests
helm hypothesis run generated-tests
```

If every input has a supported, finite set of choices, `test` can list the possible
configurations. It tests all of them when there are fewer than 10,000 and they fit
the case budget. For larger finite spaces, it selects configurations that exercise
every allowed pair of field choices, plus all choices within selected groups of
related fields when affordable.<sup>[\[1\]](../usage.md#interaction-coverage)</sup>

If the tool cannot list the whole space, it generates tests for individual values
paths and logs why it chose that mode. Each test tries multiple inputs. `--paths`
explicitly selects this mode.

The per-path workflow generates a Python property per values path, executes the suite
inside the plugin environment, and returns its exit status. Generated source, values,
schemas, JUnit results and a run report stay in `reports/hypothesis-helm` by default.
Use `--artifact-dir` to choose a different location. Tests default to `--jobs auto`,
which adjusts the number of workers based on how quickly tests finish. Set `--jobs N` for a fixed
worker count or `--jobs 1` to run serially.

Path order defaults to seeded random traversal. Use `--seed` to reproduce it or
change which paths are likely to be tested before a timeout. Use
`--traversal-strategy linear|root-first|leaf-first` to choose another order.<sup>[\[2\]](../execution/README.md#value-path-traversal)</sup>

Add `--output json` (or `-o json`) to `test` or `run` to stream rendered
manifests as JSON Lines, with progress and test reports on stderr. See
[streaming to Kubeconform and Kubesec](../usage.md#stream-rendered-manifests)
for a pipeline that validates each resource as it arrives.

`--strict` requires all schema-declared and template-referenced configurable fields
to exist in the original `values.yaml`, including optional fields and values with
template fallbacks. Missing fields fail preflight; coalesced defaults and cached
passes do not satisfy it. See [strict source values](../usage.md#strict-source-values).

Each generated suite includes Python tests, YAML assembled from the chart's inputs, an inferred schema,
and a path/strategy inventory. Source charts remain unchanged. Inferred contracts
and unresolved template constructs need review; sampled tests do not prove
that every template branch was exercised or every allowed input can render successfully.

Use `--permutations N` to cover every valid interaction among any `N` finite
schema factors: `2` covers pairs, `3` covers triples. Small spaces still receive
full enumeration; `--exhaustive-threshold 0` disables that promotion. Repeat
`--exhaustive-group ingress,service` to require selected groups. Logs and reports
show planned, completed and remaining iterations, timing estimates, and the count
change from the previous run in the same artifact directory. Finite runs test each
distinct normalized configuration once, including defaults; equivalent overrides
are deduplicated before rendering. Array order remains significant. This mode requires
enumerable domains (such as booleans,
enums and bounded integers) and refuses incomplete coverage when planning limits
are exceeded. See [interaction coverage](../usage.md#interaction-coverage)
for factor definitions, limits and reports.

## Caching and validation

Local reruns reuse successful path results and retry failures by default. CI runs
continue to test the full selection. Use `--rerun all` for a fresh run,
`--cache-dir .cache/hypothesis-helm` to choose a persistent cache, or `--no-cache`
to disable it. See [persistent path results](../usage.md#persistent-path-results)
and [CI cache setup](../ci.md#persisting-path-outcomes).

Enable optional Kubernetes API schema validation using
[kubeconform](https://github.com/yannh/kubeconform) with
`helm hypothesis test ./chart --kubeconform --schema-version 1.35.0`.
The version defaults to the latest published stable schemas; strict schemas are
cached through a sparse Git checkout for offline and parallel reuse.
See [API conformity setup](../usage.md#kubernetes-api-conformity).

Rendered bundles also use an in-memory SHA-256 index to reuse successful standard
manifest validation for identical output. Helm and custom assertions still run
for each input. Reports expose duplicate-output and validation-reuse counts;
indexes are local to a whole-chart run or pytest worker, not shared across CI jobs.
See [rendered-output comparison](../usage.md#in-memory-rendered-output-comparison).

Planning keeps one shared model of the chart's field names and types. Input
generation, interaction groups and template analysis all refer to those same
fields.<sup>[\[3\]](../usage.md#shared-typed-values-model)</sup>

Use `--prune-equivalent` for conservative pre-render pruning against successfully
rendered representatives. Unknown behavior still renders, and custom assertions
run for every input. The [proof compiler contract](../safe-pruning.md) describes
its supported subset, exact-equivalence bounds and per-candidate certificates.
