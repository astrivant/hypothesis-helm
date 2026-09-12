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
set `kubesec: 'true'` for core-sized GNU Parallel security scans (`kubesec-jobs`
overrides the worker count), `schema-cache: 'false'` to disable remote cache persistence or
`kubeconform: 'false'` to disable API validation. A supplied `kubeconform-binary`
path uses that executable instead of installing one. For a shard-only GitHub
matrix, pass `strategy.job-index` and `strategy.job-total` through the action's
`job-index` and `job-total` inputs; GitHub does not export these automatically
as environment variables. For a version/shard matrix, pass `matrix.shard` and the
fixed shard total for each version, as in the local workflow.

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
          schema-version: '1.35.0'
          kubesec: true
          kubesec-jobs: auto
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
form a version/shard matrix. Explicit shard indices ensure every Kubernetes version
runs the full suite across its three shards.

```yaml
helm-properties:
  image: python:3.13-slim
  stage: test
  parallel:
    matrix:
      - K8S_VERSION: ['1.34.0', '1.35.0']
        SHARD_INDEX: ['1', '2', '3']
  variables:
    HELM_VERSION: v3.19.0
    HELM_CHART: ./chart
    KUBECONFORM_VERSION: v0.7.0
    KUBESEC_ENABLED: 'false' # opt in to security scanning
    KUBESEC_VERSION: v2.14.2
    KUBESEC_JOBS: auto
    HYPOTHESIS_HELM_SCHEMA_MEMORY_DIR: "" # Optional: /dev/shm/helm-schemas
    SCHEMA_CACHE_DIR: .cache/hypothesis-helm/schemas
  cache:
    key: "helm-schemas-v1-linux-amd64-${K8S_VERSION}-${SHARD_INDEX}"
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
      if [ "$KUBESEC_ENABLED" = "true" ]; then
        apt-get install -y --no-install-recommends parallel
        curl -fsSL "https://github.com/controlplaneio/kubesec/releases/download/${KUBESEC_VERSION}/kubesec_linux_amd64.tar.gz" \
          -o /tmp/kubesec.tar.gz
        tar -xzf /tmp/kubesec.tar.gz -C /tmp kubesec
        install /tmp/kubesec /usr/local/bin/kubesec
      fi
    - PYTHON=python3.13 helm plugin install https://github.com/astrivant/hypothesis-helm
    - helm hypothesis schemas --schema-version "$K8S_VERSION" --schema-cache-dir "$SCHEMA_CACHE_DIR"
  script:
    - mkdir -p reports/hypothesis-helm
    - |
      validation_option=--kubeconform
      if [ "$KUBESEC_ENABLED" = "true" ]; then validation_option=; fi
      test_status=0
      helm hypothesis test "$HELM_CHART" \
        --shard "$SHARD_INDEX/3" --jobs auto --max-examples 50 --seed 0 --rerun all \
        ${validation_option:+"$validation_option"} --schema-version "$K8S_VERSION" \
        --schema-cache-dir "$SCHEMA_CACHE_DIR" --schema-offline \
        --artifact-dir reports/hypothesis-helm --output json \
        > "reports/hypothesis-helm/manifests-${SHARD_INDEX}.jsonl" || test_status=$?
      if [ "$KUBESEC_ENABLED" = "true" ]; then
        plugin_python="$(helm env HELM_PLUGINS)/hypothesis/.plugin-venv/bin/python"
        scan_status=0
        "$plugin_python" -m hypothesis_helm.integrations.kubesec \
          "reports/hypothesis-helm/manifests-${SHARD_INDEX}.jsonl" \
          --output reports/hypothesis-helm/kubesec --jobs "$KUBESEC_JOBS" \
          --shard "$SHARD_INDEX/3" --pre-sharded --validate-rest \
          --schema-version "$K8S_VERSION" --schema-cache-dir "$SCHEMA_CACHE_DIR" \
          --schema-offline || scan_status=$?
        if [ "$test_status" -eq 0 ]; then test_status=$scan_status; fi
      fi
      exit "$test_status"
  artifacts:
    when: always
    name: "helm-properties-${K8S_VERSION}-${SHARD_INDEX}"
    paths:
      - reports/hypothesis-helm/
    reports:
      junit: reports/hypothesis-helm/shards/*/junit.xml
```

Set the `K8S_VERSION` matrix to the releases you support. If changing
`SCHEMA_CACHE_DIR`, change `cache.paths` to match. The example restores and saves
schemas on both successful and failed runs, with independent cache keys per shard.
A cache miss downloads the selected schemas from GitHub through sparse checkout;
a hit refreshes the catalog once before testing. Both validators then use the local
snapshot offline; individual resources do not fetch API specifications.

Each node runs its own adaptive worker pool and reports its own exit status.
JUnit reports live under `shards/INDEX-of-TOTAL/`; the example also preserves
manifests and diagnostics when tests fail. Pin the plugin installation with
`--version <git-tag-or-commit>` when adopting the example in a release pipeline.

## Security scan scope

Kubesec is optional and installs alongside GNU Parallel. `auto` uses the CPU count
available to each runner; set `kubesec-jobs` (GitHub/CircleCI) or `KUBESEC_JOBS`
(GitLab) to limit it. Each Kubesec process uses one Go execution thread.

Only the shard's emitted manifests are scanned. `--pre-sharded` prevents a second
partition; standalone scans of a shared stream can use `--shard INDEX/TOTAL`
without that flag. Reports include job timings, scan output, and resource counts for each validator.
Kubesec supports Pod, Deployment, StatefulSet, and DaemonSet in the pinned release;
Kubeconform validates the other resource kinds. Kubesec's nonzero exit fails the job,
while an existing Helm failure retains its exit code.

Both validators use the same versioned sparse-checkout snapshot. CI caches persist
it across pipelines; locally, reuse `.cache/hypothesis-helm/schemas` with
`--schema-offline` after preparing the desired version once.

### Memory-backed schemas

On Linux, set the GitHub Action input `schema-memory-dir`, the CircleCI job
parameter of the same name, or `HYPOTHESIS_HELM_SCHEMA_MEMORY_DIR` in GitLab
and local runs to `/dev/shm/helm-schemas`. Leave it empty to use the disk cache.

The selected snapshot is copied once to tmpfs and shared by local validator
workers. Both Kubeconform and Kubesec read it through their normal file APIs.
Persistent CI caches stay on disk; separate CI machines stage their own copy.
Use a job-specific directory when concurrent jobs share a mount, and remove it
when a persistent runner finishes the job.

The directory must be on an existing Linux tmpfs mount with enough free space;
containers may need a larger runner-provided mount than their default `/dev/shm`.
This avoids disk-backed schema reads, but parsing still costs time and the OS may
already cache disk reads. Measure before enabling it by default. Tmpfs can swap
under memory pressure ([Linux documentation](https://docs.kernel.org/filesystems/tmpfs.html)).

With Kubesec enabled, CI routes its supported workload kinds to Kubesec and all
other resources to Kubeconform. Each resource receives schema validation once.
GitHub security runs use `--rerun all` so cached test results cannot hide manifests
from the downstream validators. Validation reports live in the Kubesec artifact
directory; downstream validation failures fail the job, outside the Helm JUnit report.
