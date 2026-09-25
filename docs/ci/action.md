# GitHub Action reference

<!-- toc:start -->
**Table of contents**

- [Inputs](#inputs)
- [Outputs](#outputs)
<!-- toc:end -->

[CI guide](../ci.md#github-action) · [CLI reference](../cli/README.md)

`with:` values are strings. Quote booleans. Empty optional inputs leave the CLI
or configuration default in effect. This reference is generated from `action.yml`
and the CLI parser; regenerate it with `cog -r docs/ci/action.md`.

## Inputs

<!-- [[[cog
import cog
from pathlib import Path
from ruamel.yaml import YAML
from hypothesis_helm.integrations.action_options import options
metadata = YAML(typ="safe").load(Path("action.yml").read_text())
commands = options()
cog.outl("| Input | Default | Commands | Purpose |")
cog.outl("| --- | --- | --- | --- |")
for name, item in metadata["inputs"].items():
    available = ", ".join(f"`{command}`" for command, entries in commands.items() if name in entries) or "Action setup"
    if name in {"source", "chart", "config-inline"}:
        available = "All five"
    default = "`" + str(item.get("default", "")) + "`" if item.get("default", "") != "" else "Empty"
    description = " ".join(item["description"].split()).replace("|", "\\|")
    cog.outl(f"| `{name}` | {default} | {available} | {description} |")
]]] -->
| Input | Default | Commands | Purpose |
| --- | --- | --- | --- |
| `chart` | `.` | All five | Local chart or source relative to the workspace; source takes precedence when supplied. |
| `export-minimal-values` | `false` | `test`, `scan`, `audit`, `generate` | Export deterministic concrete values beside each chart after testing (shard 1 only). |
| `commit-minimal-values` | `false` | Action setup | Export example values and commit the YAML and verification proof files to the checked-out branch. |
| `minimal-values-filename` | `values-minimal.yaml` | Action setup | YAML basename in every discovered chart directory; directory overrides are rejected. |
| `minimal-values-timeout` | `30s` | `test`, `scan`, `audit`, `generate` | Verification and minimization budget per chart. |
| `python-version` | `3.13` | Action setup | Python version (3.13 or newer). |
| `binary-cache` | `true` | Action setup | Restore and save versioned Helm and optional Kubesec binaries between workflow runs. |
| `helm-version` | `v4.3.0` | Action setup | Helm 4 version to install. |
| `shard` | `auto` | `test`, `run` | auto detects CI coordinates; INDEX/TOTAL overrides; none disables sharding. |
| `job-index` | Empty | Action setup | Zero-based GitHub strategy.job-index; pass this from a matrix workflow. |
| `job-total` | Empty | Action setup | GitHub strategy.job-total; pass this from a matrix workflow. |
| `jobs` | `auto` | `test`, `scan`, `run` | auto tunes worker concurrency per runner; a positive integer fixes the limit. |
| `run-id` | Empty | `test`, `run` | Common run identifier for combining all shards into one final report. |
| `max-examples` | Empty | `test`, `scan`, `generate` | Maximum Hypothesis examples per property; empty inherits config, then the CLI default (test/scan 10, generate 100). |
| `sample-random` | Empty | `test`, `scan`, `run` | Percentage of eligible path properties to retain; 100 disables sampling. |
| `sample-min-cases` | Empty | `test`, `scan`, `run` | Minimum retained sample; smaller suites run in full. |
| `seed` | Empty | `test`, `scan`, `run` | Shared Hypothesis seed for reproducible runs. |
| `timeout` | Empty | `test`, `scan` | Timeout in seconds per Helm render. |
| `match` | Empty | `test`, `run` | Optional pytest keyword expression applied before sharding. |
| `schema-validation` | `true` | `test`, `scan`, `run` | Validate Kubernetes API schemas; with Kubesec, route validation through the security dispatcher. |
| `kubesec` | `false` | Action setup | Route fresh and verified cached manifests to Kubesec and other resources to native schema validation. |
| `kubesec-version` | `v2.14.2` | Action setup | Kubesec release to install. |
| `kubesec-jobs` | `auto` | Action setup | auto uses this runner process CPU count; a positive integer overrides it. |
| `kubesec-score-minimum` | `0` | Action setup | Minimum acceptable score for every Kubesec resource; equality passes. Invalid manifests and scanner errors always fail. |
| `kubesec-binary` | `kubesec` | Action setup | Path or name of a preinstalled Kubesec executable. |
| `schema-cache` | `true` | Action setup | Restore and save Kubernetes schemas between workflow runs. |
| `schema-version` | `latest` | `test`, `scan`, `run` | Kubernetes schema version, latest stable or exact X.Y.Z. |
| `schema-cache-dir` | `schemas` | `test`, `scan`, `run` | Sparse schema checkout and immutable snapshot cache. |
| `schema-memory-dir` | Empty | Action setup | Optional directory on a Linux tmpfs mount, such as /dev/shm/helm-schemas |
| `schema-offline` | `false` | `test`, `scan`, `run` | Use restored schemas without fetching upstream. |
| `cache-dir` | Empty | `test`, `scan`, `run` | Optional persistent path-result cache directory to restore with your CI cache. |
| `cache` | `true` | `test`, `scan`, `run` | Enable disk caching of successful and failed paths. |
| `disable-schema-caching` | `false` | `test`, `run` | Compare against restored values structure markers without overwriting them. |
| `rerun` | `auto` | `test`, `run` | auto runs all paths unless incremental is enabled; failed retries failures and uncached paths; all forces a full run. |
| `incremental` | `false` | Action setup | With rerun auto, reuse successful properties of Git-unchanged charts; requires restored outcomes and comparison history. |
| `base-ref` | Empty | `test`, `scan` | Override the incremental comparison reference; otherwise use the PR target or previous trunk commit. |
| `artifact-dir` | `.cache/hypothesis-helm/runs` | `test`, `scan`, `audit`, `run` | Artifact root; sharded runs append shards/INDEX-of-TOTAL. |
| `upload-artifacts` | `true` | Action setup | Upload the generated suite, reports, and JSON manifests, including on failure. |
| `artifact-name` | `hypothesis-helm` | Action setup | Artifact name prefix; job name and shard identifier are appended. |
| `artifact-retention-days` | `30` | Action setup | Report retention in days, subject to repository policy; does not change CI cache eviction. |
| `command` | `test` | Action setup | CLI command: test (local charts), scan (remote sources), audit, generate, or run (saved suite). |
| `source` | Empty | All five | Chart directory, remote repository/chart reference, or saved suite directory. When empty, use chart. |
| `config-inline` | Empty | All five | Inline policy YAML merged over config. Mappings merge; lists and scalars replace. Relative paths use the workspace. |
| `report` | Empty | `test`, `scan` | Write Markdown/PDF reports; true writes scan.md/pdf inside artifacts, a path chooses a location, false or empty omits. |
| `pca-samples` | Empty | `test`, `scan` | with --report, measure up to N reference configurations per chart for output PCA; 0 disables it (default: 64) |
| `pca-timeout` | Empty | `test`, `scan` | additional output-PCA measurement budget per chart with --report (default: 1m) |
| `max-mutations` | Empty | `test`, `scan` | with --report, measure sensitivity for up to N fields per chart and all their pairs (opt-in) |
| `sensitivity-timeout` | Empty | `test`, `scan` | additional sensitivity measurement budget per chart with --max-mutations (default: 3m) |
| `values` | Empty | `test`, `scan` | baseline file relative to each chart, or an absolute path |
| `chart-timeout` | Empty | `test`, `scan` | property-test budget per discovered chart (default: 3m) |
| `scan-timeout` | Empty | `test`, `scan` | total local discovery/testing budget, excluding dependency preparation |
| `build-dependencies` | Empty | `test`, `scan` | build dependencies in isolated copies; true/false, empty inherits the CLI/config default |
| `fail` | Empty | `test`, `scan`, `audit`, `generate`, `run` | stop at this severity or higher and exit 1; bare flag: any finding; lower findings remain reported; true uses the default, false or empty omits |
| `time-limit` | Empty | `test` | whole-chart execution budget, e.g. 30s or 3m (default: 3m); excludes planning |
| `paths` | Empty | `test` | force generated per-path testing; true enables, false or empty omits |
| `exhaustive` | Empty | `test` | enumerate finite whole-chart inputs; true enables, false or empty omits |
| `whole-chart` | Empty | `test` | sample whole-chart inputs; true enables, false or empty omits |
| `permutations` | Empty | `test`, `scan` | cover valid N-way finite interactions; non-finite charts fall back to path sampling |
| `filter` | Empty | `test`, `scan` | enable --filter-topology 2 and --expand-failures; true enables, false or empty omits |
| `filter-random` | Empty | `test` | retain a seeded quarter of finite permutation cases per step; default: 0 |
| `filter-topology` | Empty | `test` | thin symbolic output/branch regions; retain representatives and unknowns; combines with --filter-random |
| `expand-failures` | Empty | `test` | test omitted members of failed symbolic regions within the execution budget; true enables, false or empty omits |
| `prune-equivalent` | Empty | `test` | skip Helm only for proved output equivalence to a successful render; true enables, false or empty omits |
| `collect-only` | Empty | `test`, `run` | generate and list tests; true enables, false or empty omits |
| `max-cases` | Empty | `test` | bound exhaustive domains or permutation suites and factor domains |
| `max-candidates` | Empty | `test` | bound permutation planning work |
| `exhaustive-threshold` | Empty | `test` | enumerate finite spaces smaller than this count; 0 disables promotion |
| `exhaustive-group` | Empty | `test` | require exhaustive coverage of a group of value paths or containers; repeatable; one comma-separated group per line |
| `no-infer-groups` | Empty | `test` | disable inferred exhaustive groups; true enables, false or empty omits |
| `max-group-cases` | Empty | `test` | bound automatically inferred group domains |
| `filter-adaptive` | Empty | `test`, `scan` | enable --filter and retain 70% subject to measured topology sample floors; unmatched charts keep all filtered cases; true enables, false or empty omits |
| `sampling-calibration` | Empty | `test`, `scan` | override the packaged adaptive-sampling calibration JSON |
| `sensitivity-order` | Empty | `test`, `scan` | maximum measured interaction order for sensitivity-first; 1..permutations, default: min(2, permutations) |
| `traversal-strategy` | Empty | `test`, `scan`, `run` | seeded random (default), linear, root-first, leaf-first, or sensitivity-first (finite coverage defaults to pairs) |
| `helm` | Empty | `test`, `scan` | helm |
| `release` | Empty | `test` | release |
| `namespace` | Empty | `test` | namespace |
| `kube-version` | Empty | `test` | kube-version |
| `allow-empty` | Empty | `test` | allow-empty; true enables, false or empty omits |
| `strict` | Empty | `test`, `scan`, `generate`, `run` | require schemas for custom resources; otherwise skip schema validation when their schema is missing; true/false, empty inherits the CLI/config default |
| `dry-run` | Empty | `test`, `run` | plot coverage and forecast filtering or cached property work without execution; true enables, false or empty omits |
| `progress` | Empty | `test`, `run` | force a live progress bar on stderr, including redirected output; true enables, false or empty omits |
| `output-format` | Empty | `test`, `scan`, `run` | stream rendered manifests as JSON lines or YAML documents on stdout; logs and reports go to stderr |
| `export-suppressions` | Empty | `test`, `scan`, `audit`, `run` | write categorized suppressions.yaml in each chart's artifacts after testing; review before applying; true enables, false or empty omits |
| `export-topological-graph` | Empty | `test`, `scan`, `audit`, `generate` | Export JSON/DOT input-output graphs; true writes topology.json inside artifacts, or provide a filename. |
| `log-color` | Empty | `test`, `scan`, `audit`, `generate`, `run` | Color severity labels: auto, always or never. true selects always; false selects never; empty inherits the CLI default. |
| `log-file` | Empty | `test`, `scan`, `audit`, `generate`, `run` | Append logs to this file; empty keeps diagnostics visible on stderr while stdout is saved as an Action output. |
| `config` | Empty | `test`, `scan`, `audit`, `generate`, `run` | finding and input-domain policy YAML; default: .hypothesis-helm.yaml in the working directory |
| `character-sets` | Empty | `test`, `scan`, `audit`, `generate`, `run` | generated text alphabet; overrides config; default: ascii |
| `renderer-policy` | Empty | `test`, `scan`, `audit`, `generate`, `run` | auto controls supported random inputs with visible native fallback (default); native uses Helm; strict requires replay |
| `yaml-parser` | Empty | `test`, `scan`, `audit`, `generate`, `run` | manifest parser backend; overrides yaml_parser in config; default: ruamel, or the saved suite's parser |
| `ignore` | Empty | `test`, `scan`, `audit`, `generate`, `run` | disable one built-in check; repeat to add codes; one code per line |
| `disable-codes` | Empty | `test`, `scan`, `audit`, `generate`, `run` | disable comma-delimited finding codes; adds to --ignore and the config file; repeatable |
| `helm-repository` | Empty | `scan` | interpret SOURCE as a Helm repository name or HTTP(S) base URL; true enables, false or empty omits |
| `chart-version` | Empty | `scan` | Helm chart version or constraint; default: latest stable release per chart |
| `clone-timeout` | Empty | `scan` | Git checkout or Helm source preparation budget, also bounded by --scan-timeout (default: 3m) |
| `suite-output` | Empty | `generate` | Generated suite directory (generate --output); empty writes generated-tests inside the artifact directory. |
<!-- [[[end]]] -->

Inputs marked Action setup control installation, artifact handling or the wrapper.
`schema-validation`, schema-cache settings, and minimal-values export also affect
post-test steps, even when the selected command does not accept those flags.
`export-minimal-values: 'true'` uses `minimal-values-filename`; local exports happen
once in shard 1. Remote scans export into their retained chart artifacts and cannot
commit back to the remote repository. A saved suite cannot export source values.

## Outputs

<!-- [[[cog
cog.outl("| Output | Meaning |")
cog.outl("| --- | --- |")
for name, item in metadata["outputs"].items():
    cog.outl(f"| `{name}` | {item['description']} |")
]]] -->
| Output | Meaning |
| --- | --- |
| `suite-path` | Generated suite directory for command generate. |
| `report-path` | Requested Markdown report location; may not exist after setup failure. |
| `pdf-path` | Requested PDF report location; may not exist after setup failure. |
| `command-output` | Captured stdout for audit, generation, dry-run or collection. |
| `report-dir` | Absolute path to this shard's artifact directory. |
| `junit-path` | Absolute path to the JUnit report. |
| `manifest-path` | Absolute path to the manifest stream (JSON Lines or YAML); empty for non-rendering commands. |
| `shard` | Resolved one-based shard coordinates, or none. |
| `kubesec-report-dir` | This shard's Kubesec report directory. |
| `kubesec-exit-code` | Kubesec scan exit code when enabled. |
| `exit-code` | Combined Helm and optional Kubesec status; Helm failures take precedence. |
<!-- [[[end]]] -->

The Action does not expose `aggregate`, `schemas`, `rules` or `replay-changes` as
execution modes. Use those CLI commands in subsequent steps, as shown in the
[aggregation example](../ci.md#github-action). Command-specific long-option aliases
and short flags map to the same canonical inputs listed above; `clone-timeout`
corresponds to `--clone-timeout`/`--source-timeout`.
