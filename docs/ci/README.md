# CI examples

[Documentation](../README.md) · [Project](../../README.md)

`--shard auto` is the default. CircleCI and GitLab parallel jobs are detected
from their node environment variables; local and single-job runs use the full
suite. Use `--shard INDEX/TOTAL` to override detection or `--shard none` to
disable it.

The repository includes a [GitHub Action](../../action.yml) that installs the tool and
kubeconform, validates against cached Kubernetes schemas by default, and uploads
per-shard reports and manifests. `schema-version` defaults to `latest`, and
`schema-cache-dir` defaults to `.cache/hypothesis-helm/schemas`, outside `reports/`.
The action restores schemas before testing and saves updates even when tests fail;
set `schema-cache: 'false'` to disable remote cache persistence or
`kubeconform: 'false'` to disable API validation. A supplied `kubeconform-binary`
path uses that executable instead of installing one. For a GitHub
matrix, pass `strategy.job-index` and `strategy.job-total` through the action's
`job-index` and `job-total` inputs; GitHub does not export these automatically
as environment variables.

See [CI integration](../ci.md) for provider examples, action inputs and outputs,
and publishing steps. The [local action workflow](../../.github/workflows/action.yml)
can verify the action before it is released.

### CircleCI inline orb

[`.circleci/config.yml`](../../.circleci/config.yml) defines the reference-only
`hypothesis-helm` inline orb. Its `test` command runs the installed plugin;
its `test-chart` job checks out the repository, installs Helm, kubeconform and the
local plugin, restores and refreshes the schema cache, runs the command, and uploads
JUnit results and JSON manifests. It saves schemas before testing so failed tests
do not prevent the next run from reusing them. The repository's
workflows do not invoke this job.

After copying the orb's `orbs:` definition into your configuration, you could
invoke it with this workflow fragment:

```yaml
# Example only; the inline orb definition must also be present in this config.
workflows:
  chart-properties:
    jobs:
      - hypothesis-helm/test-chart:
          chart: examples/workload
          plugin-path: .
          parallelism: 3
          jobs: auto
          max-examples: 50
          seed: 0
          artifact-dir: reports/hypothesis-helm
          schema-version: latest
          schema-cache-dir: .cache/hypothesis-helm/schemas
```

`plugin-path` points to a checkout of this plugin. The job defaults to Python 3.13,
Helm 3.19.0, one CircleCI node, automatic worker concurrency, and 100 examples per
property. With `parallelism: 3`, the tool reads `CIRCLE_NODE_INDEX` and
`CIRCLE_NODE_TOTAL` to assign shards. The command uses `--rerun all` so every
assigned path runs in CI. To reuse only the command in an existing job, call
`hypothesis-helm/test` after installing Helm and the plugin; it accepts the same
chart, worker, example, seed, artifact, and schema parameters. It requires kubeconform
as well. `schema-version` defaults to `latest`; use an exact version such as `1.35.0`
to select another Kubernetes release. The sparse checkout and immutable snapshots
live in `schema-cache-dir`, separate from reports.

### GitLab CI job

Add this job to `.gitlab-ci.yml` for a Linux amd64 Docker runner. Adjust
`HELM_CHART` to the chart in your repository. GitLab's [`parallel` jobs](https://docs.gitlab.com/ci/yaml/#parallel)
provide `CI_NODE_INDEX` and `CI_NODE_TOTAL`, which the tool detects automatically.

```yaml
helm-properties:
  image: python:3.13-slim
  stage: test
  parallel: 3
  variables:
    HELM_VERSION: v3.19.0
    HELM_CHART: ./chart
    KUBECONFORM_VERSION: v0.7.0
    K8S_VERSION: latest
    SCHEMA_CACHE_DIR: .cache/hypothesis-helm/schemas
  cache:
    key: "helm-schemas-v1-linux-amd64-${K8S_VERSION}-${CI_NODE_INDEX}"
    paths:
      - .cache/hypothesis-helm/schemas/
    policy: pull-push
    when: always
  before_script:
    - apt-get update
    - apt-get install -y --no-install-recommends ca-certificates curl git
    - |
      curl -fsSL "https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz" \
        -o /tmp/helm.tar.gz
      tar -xzf /tmp/helm.tar.gz -C /tmp
      install /tmp/linux-amd64/helm /usr/local/bin/helm
      curl -fsSL "https://github.com/yannh/kubeconform/releases/download/${KUBECONFORM_VERSION}/kubeconform-linux-amd64.tar.gz" \
        -o /tmp/kubeconform.tar.gz
      tar -xzf /tmp/kubeconform.tar.gz -C /tmp kubeconform
      install /tmp/kubeconform /usr/local/bin/kubeconform
    - PYTHON=python3.13 helm plugin install https://github.com/astrivant/hypothesis-helm
  script:
    - mkdir -p reports/hypothesis-helm
    - |
      helm hypothesis test "$HELM_CHART" \
        --shard auto --jobs auto --max-examples 50 --seed 0 --rerun all \
        --kubeconform --schema-version "$K8S_VERSION" \
        --schema-cache-dir "$SCHEMA_CACHE_DIR" \
        --artifact-dir reports/hypothesis-helm --output json \
        > "reports/hypothesis-helm/manifests-${CI_NODE_INDEX}.jsonl"
  artifacts:
    when: always
    name: "helm-properties-${CI_NODE_INDEX}"
    paths:
      - reports/hypothesis-helm/
    reports:
      junit: reports/hypothesis-helm/shards/*/junit.xml
```

Set `K8S_VERSION` to an exact release or leave it at `latest`. If changing
`SCHEMA_CACHE_DIR`, change `cache.paths` to match. The example restores and saves
schemas on both successful and failed runs, with independent cache keys per shard.
A cache miss downloads the selected schemas from GitHub through sparse checkout;
a hit still refreshes the catalog so `latest` can advance.

Each node runs its own adaptive worker pool and reports its own exit status.
JUnit reports live under `shards/INDEX-of-TOTAL/`; the example also preserves
manifests and diagnostics when tests fail. Pin the plugin installation with
`--version <git-tag-or-commit>` when adopting the example in a release pipeline.
