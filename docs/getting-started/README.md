# Getting started

<!-- toc:start -->
**Table of contents**

- [Install](#install)
- [Quick start](#quick-start)
- [Ten useful options](#ten-useful-options)
- [What our tests suggest](#what-our-tests-suggest)
- [Read the result](#read-the-result)
<!-- toc:end -->

[Documentation](../README.md) · [Project](../../README.md)

## Install

Requires Helm 4 and Python 3.13+. The plugin installs its Python dependencies automatically.

```sh
PYTHON=python3.13 helm plugin install https://github.com/astrivant/hypothesis-helm
```

## Quick start

Start with a filtered, five-minute test and a readable report:

```sh
helm hypothesis test ./chart --filter --chart-timeout 5m --jobs 2 --report
```

This renders locally without deploying. Point it at a directory to test each chart in turn, with a separate budget
and dependencies prepared in temporary copies. Reports go to `docs/reports/`; working data stays in `.cache/`.

Charts without `values.schema.json` use [inferred types](../inputs/README.md#declared-and-inferred-types).
Unbounded strings and open maps need sampling rather than full enumeration.
See [how schemas become tests](../input-domains/README.md#how-schemas-become-tests) for how fields, ranges and test assertions connect.

Use `scan` for a Git URL or an already configured Helm repository:

```sh
helm hypothesis scan prometheus-community/prometheus --filter --chart-timeout 5m --jobs 2 --report
```

## Ten useful options

| Option | When to use it |
| --- | --- |
| `--filter` | Start here, including on main. Filters inputs and expands around failures where supported. |
| `--filter-adaptive` | PR checks: adds sampling when calibration supports the chart; otherwise keeps ordinary filtering. |
| `--chart-timeout 5m` | Bound testing time per chart. Default: 3 minutes. Dependency preparation is outside this budget. |
| `--jobs 2` | Share chart work across two workers on a 2-vCPU runner. Default: available CPUs. |
| `--max-examples 10` | Set examples per path. Ten is the default; increase after enough paths are being reached. |
| `--values ci/values.yaml` | Select a baseline relative to each chart. Default: `values.yaml`; absolute paths also work. |
| `--seed 42` | Reproduce input selection, or change the seed to explore different paths before a timeout. |
| `--report` | Save Markdown and PDF summaries. Add a filename prefix to choose the destination. |
| `--fail` | Stop at the first unsuppressed finding and exit 1. Includes audit warnings. |
| `--validate-schemas` | Validate rendered resources against Kubernetes API schemas. Uses locally cached schemas; no validator binary is needed. |

Choose either filtering mode. Worker counts are starting estimates.<sup>[\[1\]](../ci/resources.md)</sup>
Schema validation works with both local `test` and remote `scan`; pin the target Kubernetes version and provide custom-resource schemas.
Custom resources without a supplied schema skip schema validation; add `--strict` to report missing schemas as errors.
See [validation setup](../usage.md#kubernetes-api-conformity) and [CRD requirements](../input-domains/README.md#custom-resources).

## What our tests suggest

Bitnami charts had a median of **320 supplied values paths**, before dependencies.
Check how many paths finish before increasing examples per path; five minutes may leave substantial work.
See the [sizing observations](../../studies/resource-sizing/README.md).

Our [sampling study](../../studies/sampling/README.md) found common bugs quickly; rare failures remain easy to miss.
Use adaptive filtering for PRs, ordinary filtering on main, and a
[full release check](../coverage.md#release-checks) before tagging.
Exhaustive coverage requires finite inputs and a completed run.

## Read the result

Review findings and triggering values by chart. Timeouts and skipped charts mean incomplete testing.
No findings applies only to tested inputs. Without `--fail`, scans continue, but test failures can still return a nonzero exit status.

If a generated value is inappropriate for a field, add a schema restriction or
[field-specific input constraint](../input-domains/README.md#chart-specific-constraints).
For example, constrain a Secret reference to valid names while keeping malformed-YAML checks enabled.

For the next step, see [saved suites](../usage.md#inspect-and-rerun-generated-suites),
[pairwise and higher-order coverage](../usage.md#interaction-coverage), or
[repository authentication and caching](../scanning/README.md).
