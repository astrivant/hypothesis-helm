# Dependency maintenance

<!-- toc:start -->
**Table of contents**

- [Where versions live](#where-versions-live)
- [Helm, Sprig and Go](#helm-sprig-and-go)
  - [Upgrading Helm or its template functions](#upgrading-helm-or-its-template-functions)
  - [Changing the shared catalog Go module](#changing-the-shared-catalog-go-module)
- [Kubernetes schemas and input domains](#kubernetes-schemas-and-input-domains)
- [Python packages and developer tools](#python-packages-and-developer-tools)
- [CI, remote workers and chart snapshots](#ci-remote-workers-and-chart-snapshots)
- [Repository refresh integration](#repository-refresh-integration)
- [Checks before release](#checks-before-release)
<!-- toc:end -->

[Documentation](README.md) · [Development](development.md)

Use this inventory when an upstream dependency releases a new version. Some dependencies are Python packages; others are compiled
into Go helpers, downloaded as source for analysis, or installed by CI. A Poetry update covers only the Python dependencies.
The linked manifests and source locks are authoritative. Update this inventory when adding another dependency source or tool installer.

Run the commands below from the repository root, with the [development tools](development.md#environment) on `PATH`.

## Where versions live

| Dependency group | Version declarations and locks | Related files to review |
| --- | --- | --- |
| Python runtime and development packages | [Root pyproject.toml](../pyproject.toml), [poetry.lock](../poetry.lock) | Core dependencies, development tools, optional extras and the Poetry build backend. |
| Benchmarking add-on | [Add-on pyproject.toml](../pkg/hypothesis_helm_benchmarking/pyproject.toml) | NumPy, Matplotlib, optional PySR and the setuptools build backend; the root lock resolves the local add-on. |
| Python interpreter | [.python-version](../.python-version), both Python manifests | Ruff/mypy targets, pre-commit interpreter, CI Python/container versions and [bootstrap script](../scripts/setup-dev.sh). |
| Native Helm renderer | [Renderer go.mod](../pkg/hypothesis_helm/compiler/assets/renderer/go.mod), [go.sum](../pkg/hypothesis_helm/compiler/assets/renderer/go.sum) | [Renderer implementation](../pkg/hypothesis_helm/compiler/assets/renderer/main.go), Python replay metadata and Helm tool defaults. |
| Catalog extractor and validator probes | [Catalog go.mod](../pkg/hypothesis_helm_catalog/upstream/go.mod), [go.sum](../pkg/hypothesis_helm_catalog/upstream/go.sum) | Shared Go executable for both catalog rebuild commands; compiled Kubernetes validators. |
| Helm, Sprig and Go template source snapshots | [builtin-sources.json](../pkg/hypothesis_helm_catalog/data/builtin-sources.json) | Artifact URLs, versions, archive paths and SHA-256 checksums; generated compiler inventory. |
| Kubernetes source and schema snapshots | [sources.py](../pkg/hypothesis_helm_catalog/sources.py), [builder.py](../pkg/hypothesis_helm_catalog/builder.py), [source lock](../pkg/hypothesis_helm_catalog/data/kubernetes-source-lock.json) | Separate Kubernetes Go and JSON Schema repository revisions; reviewed schema supplements and bundled domains. |
| Local and CI tools | [setup-dev.sh](../scripts/setup-dev.sh), [setup-project action](../.github/actions/setup-project/action.yml), [pre-commit config](../.pre-commit-config.yaml) | Go, Helm, Poetry, uv, Python and lint tools; publishing also installs Poetry. |
| Consumer CI and optional Kubesec | [Root action](../action.yml), [GitHub](../ci/github.yml), [GitLab](../ci/gitlab.yml), [CircleCI](../ci/circleci.yml) | Helm/Kubesec downloads, Python images, schema versions and versioned cache keys. |
| GitHub Actions | [CI workflow](../.github/workflows/ci.yml), [setup-project action](../.github/actions/setup-project/action.yml), [root action](../action.yml), [GitHub example](../ci/github.yml) | Every `uses: owner/action@version` reference is independent of Poetry and Go. |
| Remote workers | [Ansible requirements](../ansible/requirements.txt), [collections](../ansible/requirements.yml), [worker defaults](../ansible/roles/compute_worker/defaults/main.yml) | Ansible Core, Google Cloud collection, worker Helm/Poetry versions and Debian image assumptions. |
| Infrastructure providers | [Compute versions](../terraform/modules/compute/versions.tf), [shards versions](../terraform/shards/versions.tf) | Terraform minimum and Google provider constraint; each directory has its own `.terraform.lock.hcl`. |
| Real-chart study inputs | [.gitmodules](../.gitmodules) and the committed submodule revisions | Bitnami and Prometheus chart snapshots; chart dependencies belong to each chart's `Chart.yaml` and `Chart.lock`. |

Transitive Python and Go dependencies belong to their lockfiles and module manifests; do not duplicate their full lists here.
`go.sum` verifies downloaded modules; the selected Go dependency versions are declared in `go.mod`.

## Helm, Sprig and Go

There are **two independent Go modules**. Updating one does not update the other, the installed Helm CLI, or the analyzed source snapshots.

| Component | Current baseline | Purpose |
| --- | --- | --- |
| Optional random-input renderer | Helm `v4.3.0`, Sprig `v3.3.0`, Go `1.26.0` | Executes Helm's SDK with controlled random draws and recorded native certificate generation. Sprig is a direct dependency; Kubernetes libraries remain transitive. |
| Catalog extractor | Go `1.25.0`, `k8s.io/apimachinery v0.35.0` | Reads upstream syntax trees and checks generated input bounds against compiled Kubernetes validators. |
| Builtin source inventory | Helm `4.3.0`, Sprig `3.3.0`, Go `1.26.0` | Describes the upstream functions analyzed by the compiler; these source downloads are separate from the extractor's own imports. |

The [renderer builder](../pkg/hypothesis_helm/compiler/randomness/toolchain.py) uses `GOTOOLCHAIN=auto`, so its first build can download
the required Go toolchain even when the bootstrap installed Go 1.25. The [catalog builder](../pkg/hypothesis_helm_catalog/toolchain.py)
uses `GOTOOLCHAIN=local`; raising that module's Go requirement also requires an adequate installed toolchain.

### Upgrading Helm or its template functions

1. Update the renderer's Helm requirement, then run `go mod tidy` in that module. Review both `go.mod` and `go.sum`, including
   changes to Sprig, Kubernetes libraries and the required Go version.
2. Review the corresponding entries in `builtin-sources.json`. Change the version, URL, archive prefix and checksum together.
   Verify the new upstream contents before accepting a new checksum. A different checksum is a source change to inspect.
3. Review the [Go extractor](../pkg/hypothesis_helm_catalog/upstream/helm.go) and
   [compiler contracts](compiler/functions.md#what-comes-from-source-and-what-still-needs-a-contract) against changed functions.
   Regeneration extracts source facts; it does not automatically establish safe semantics for new behavior.
4. Update renderer-specific version metadata: `caps.HelmVersion.Version` in
   [main.go](../pkg/hypothesis_helm/compiler/assets/renderer/main.go), the replay writer/reader in
   [randomness/model.py](../pkg/hypothesis_helm/compiler/randomness/model.py), and the coverage record in
   [testing/runner.py](../pkg/hypothesis_helm/charts/testing/runner.py). Review the Go and Python random alphabets and replay tests
   when Sprig's random functions change. Preserve explicit rejection of incompatible replay artifacts.
5. Align the Helm CLI defaults in `scripts/setup-dev.sh`, `action.yml`, `ci/`, `.github/workflows/` and
   `ansible/roles/compute_worker/defaults/main.yml`. Update version assertions and the pinned source links in the compiler docs.

After reviewing the manifests and source lock:

```sh
go -C pkg/hypothesis_helm/compiler/assets/renderer mod tidy
bash scripts/project-run.sh hypothesis-helm-builtins
bash scripts/project-run.sh hypothesis-helm-builtins --check
bash scripts/project-run.sh hypothesis-helm-renderer --build
bash scripts/project-run.sh cog -r docs/compiler/functions.md
bash scripts/project-run.sh pytest pkg/hypothesis_helm/tests/compiler pkg/hypothesis_helm/tests/schemas/test_builtin_sources.py
```

Automatic testing builds a missing renderer when Go is available, before chart or sensitivity testing budgets start. The explicit
build command above prepares that cache in advance; native integration tests can skip when Go is unavailable. Changing source
or Go manifests changes the build identity, so the helper rebuilds under `.cache/random-renderer/` and prior replay context hashes no longer match.
Ordinary [native function probes](../pkg/hypothesis_helm/compiler/asts/native_operations.py) instead invoke the selected Helm CLI;
they do not use this SDK helper. Test both execution paths when upgrading Helm.

### Changing the shared catalog Go module

After updating its dependency requirements:

```sh
go -C pkg/hypothesis_helm_catalog/upstream mod tidy
go -C pkg/hypothesis_helm_catalog/upstream test ./...
```

Both catalog commands fingerprint the same Go sources, `go.mod` and `go.sum`. A change to those inputs requires regenerating
**both** the builtin inventory and the bundled input-domain catalog, even if the change primarily concerns one extractor.
Their generated metadata records the extractor fingerprint.

## Kubernetes schemas and input domains

These are separate update choices:

- **Schema validation version:** `helm hypothesis schemas --schema-version X.Y.Z` prepares a published version from the
  [schema repository configured in conformity.py](../pkg/hypothesis_helm/schemas/kubernetes/conformity.py). The cache records the
  resolved revision. This does not upgrade the bundled input-domain catalog or the Go renderer's Kubernetes libraries.
- **Bundled generation constraints:** rebuilding the catalog requires matching, reviewed Kubernetes Go sources, schema sources
  and compiled validators. The current source binding is Kubernetes `1.35.0`; changing the CLI version alone is rejected.

For a catalog upgrade, review these together:

1. `VERSION` and Kubernetes `REVISION` in [sources.py](../pkg/hypothesis_helm_catalog/sources.py), plus the version, revision and
   file hashes in [kubernetes-source-lock.json](../pkg/hypothesis_helm_catalog/data/kubernetes-source-lock.json).
2. `REVISION` in [builder.py](../pkg/hypothesis_helm_catalog/builder.py), which selects the **JSON Schema repository**, and its
   `--schema-version` default. This revision is different from the Kubernetes source commit.
3. The catalog module's `k8s.io/apimachinery` requirement and the extraction/verification logic in
   [kubernetes.go](../pkg/hypothesis_helm_catalog/upstream/kubernetes.go).
4. Exact API field bindings in `sources.py` and [reviewed-domains.json](../pkg/hypothesis_helm_catalog/data/reviewed-domains.json).
   Check whether upstream now expresses each supplement, whether its checked descriptions changed, and whether a shim can be removed.
   Keep the [public shim inventory](../README.md#upstream-schema-shims) current.
5. CI schema matrices and release cache keys in the [CI workflow](../.github/workflows/ci.yml)
   and `ci/`. Different tested schema versions may be intentional;
   they do not all need to equal the catalog's source version.

Publish regenerated data only after the source checks and boundary comparisons pass:

```sh
bash scripts/project-run.sh hypothesis-helm-catalog --output pkg/hypothesis_helm_catalog/data/input-domains.json
bash scripts/project-run.sh hypothesis-helm-catalog --check
bash scripts/project-run.sh pytest pkg/hypothesis_helm/tests/schemas
```

`input-domains.json` and `compiler/assets/builtin_inventory.json` are generated release assets. Update their sources and rebuild,
rather than editing generated records. `schemas/` contains ignored, reproducible caches; it is not another dependency lock to maintain.
See [catalog rebuilding](input-domains/README.md#rebuilding-the-catalog-before-release) for offline builds and source overrides.

## Python packages and developer tools

Update the relevant dependency constraints in `pyproject.toml`, then use a targeted `poetry update PACKAGE` to refresh the root lock.
Install with `poetry install --extras benchmarking --with dev` and inspect the resolved changes. The add-on has its own distribution
manifest but no separate committed Poetry lock; its optional PySR extra also brings a Julia runtime managed by that dependency.
Exercise the [symbolic fitting integration](../pkg/hypothesis_helm_benchmarking/studies/symbolic_surface.py) when updating PySR or Julia.
When changing supported package versions, also review the core/add-on compatibility ranges in both manifests and the root extras.

The Python package list includes Hypothesis and its schema generator, JSON Schema validation, both YAML parsers, attrs/cattrs,
DeepDiff, Rich, ReportLab, Matplotlib, immutables and Lupa. NumPy and optional PySR support benchmarking. Review the manifests
for the complete constraints, including type stubs, test tools and both build backends.

| Tool | Additional update locations |
| --- | --- |
| Python | `.python-version`; both package manifests; root Ruff/mypy settings; `.pre-commit-config.yaml`; setup script; root action, GitHub setup/publishing, and `ci/` images. |
| Poetry | `scripts/setup-dev.sh`, `.github/actions/setup-project/action.yml`, `.github/workflows/ci.yml`, Ansible worker defaults. Local/CI currently use `2.1.3`; workers use `2.2.1`. |
| uv bootstrap | `uv_version` in `scripts/setup-dev.sh` (currently `0.8.17`). |
| Go launcher | `go_version` in `scripts/setup-dev.sh`, `go-version` in the setup action, both Go modules and toolchain diagnostics. |
| pydocstyle / pydoclint | Root development dependencies **and** their isolated `rev` pins in `.pre-commit-config.yaml`. |
| Ruff, mypy, pre-commit, shfmt, Cog and pytest tools | Root development dependencies and `poetry.lock`; hooks and `scripts/check.sh` invoke those installed tools. |

Git, Git LFS, GNU Parallel, ShellCheck and the host build tools are installed through Homebrew/apt, without project version locks.
Those are platform prerequisites to check when changing supported systems. Helm archives are checksum-verified by the developer
bootstrap; CI and Ansible have their own installation paths, so review them too.

## CI, remote workers and chart snapshots

Kubesec's default is `v2.14.2` in the root action and GitLab/CircleCI examples. When changing it, check the download filename,
[JSON result reader](../pkg/hypothesis_helm/integrations/kubesec.py), score thresholds and integration tests. Schema validation is
handled by this project's schema cache; there is no kubeconform binary dependency to bump.

Review action references throughout `.github/`, `action.yml` and `ci/github.yml` together. Also review floating runner images
(`ubuntu-latest`) and Python container tags in the CI examples. Binary cache keys include version, OS and architecture;
schema caches include the selected Kubernetes version. A version update must select a corresponding cache entry.

Remote workers have separate [Ansible](../ansible/README.md) and [Terraform](../terraform/README.md) setup. Update Ansible Core
and collection requirements together with worker tool defaults. Terraform's two `versions.tf` files constrain the Google provider;
review both lockfiles after `terraform init -upgrade`. The default Debian 13 image family and the worker OS assertions must agree.
The Google Cloud CLI is an operator prerequisite, not a Poetry dependency.

Bitnami and Prometheus are Git submodules. Their committed revisions determine the chart input snapshot, independently of library
upgrades. A chart dependency update changes study inputs; record that revision with new results and preserve existing run provenance.
Old reports, frozen refresh recipes and published measurements should retain the versions they actually used.

## Repository refresh integration

Every fresh `hypothesis-helm-refresh` performs these preparation steps before project checks and the measured source snapshot:

| Operation | What it rebuilds or verifies |
| --- | --- |
| `compiler-builtins` | Rebuilds the builtin inventory from the locked Helm, Sprig and Go sources, then checks reproducibility. |
| `schema-catalog` | Rebuilds the bundled input domains and local schema cache, verifies the catalog, and runs the shared Go extractor tests. |
| `native-renderer` | Builds the pinned Helm SDK helper so the following Python checks can exercise it. |
| `dependency-docs` | Regenerates the Cog references and documentation tables of contents. |
| `checks` | Runs the normal shell, lint, typing, documentation and Python test checks against those prepared dependencies. |

The [operation inventory](../pkg/hypothesis_helm_benchmarking/refresh/plan.py) enforces this order. A failed preparation step stops
the refresh before measurements. These steps rebuild **the reviewed pins**; they do not select newer upstream versions or change
dependency constraints. Python dependencies and external tools must already be installed through the development setup.

The GitHub refresh runs the same steps in its preparation job, caching `schemas/`, `.cache/compiler-builtins/` and
`.cache/random-renderer/` by source/module pins, OS and architecture. Each study receives the prepared source snapshot, including
both Go modules, the Lua pass and generated catalogs. Dependency preparation is outside benchmark and chart-testing time budgets.
Inspect the steps without starting a run with `hypothesis-helm-refresh --dry-run`.

Existing refresh journals retain their recorded operations and frozen sources; resuming one does not insert new preparation steps
or upgrade the dependencies of measurements already collected.

## Checks before release

For an actual dependency upgrade, run the relevant rebuilds above, then the repository checks and package build:

```sh
bash scripts/project-run.sh hypothesis-helm-docs
bash scripts/check.sh
poetry build
```

The [CI workflow](../.github/workflows/ci.yml) checks release catalog consistency and installed Helm commands,
then gates publishing on code checks, chart tests, Kubesec and benchmark smoke tests.
Build the add-on separately if its manifest changed; its [publishing instructions](../pkg/hypothesis_helm_benchmarking/README.md#develop-and-publish)
are separate from the [core tag-release workflow](development.md#publishing-to-pypi).

Search for the old version across maintained files before finishing. Include hidden CI and hook files; omit caches and historical
results. For example, when reviewing Helm `4.3.0`:

```sh
rg -n --hidden --glob '!**/.git/**' --glob '!**/.venv/**' --glob '!**/.cache/**' \
    --glob '!third_party/**' --glob '!schemas/**' --glob '!docs/reports/**' --glob '!studies/**' \
    '4\.3\.0' pkg scripts .github ci ansible terraform docs README.md pyproject.toml action.yml .pre-commit-config.yaml
```

Keep new pins discoverable here, and update baseline versions in this guide as part of their upgrade.
