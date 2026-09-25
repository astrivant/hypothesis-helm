# CLI reference

<!-- toc:start -->
**Table of contents**

- [helm hypothesis](#helm-hypothesis)
- [helm hypothesis rules](#helm-hypothesis-rules)
- [helm hypothesis replay-changes](#helm-hypothesis-replay-changes)
- [helm hypothesis aggregate](#helm-hypothesis-aggregate)
- [helm hypothesis export-minimal-values](#helm-hypothesis-export-minimal-values)
- [helm hypothesis scan](#helm-hypothesis-scan)
- [helm hypothesis generate](#helm-hypothesis-generate)
- [helm hypothesis audit](#helm-hypothesis-audit)
- [helm hypothesis run](#helm-hypothesis-run)
- [helm hypothesis test](#helm-hypothesis-test)
- [helm hypothesis schemas](#helm-hypothesis-schemas)
- [Mutation sensitivity diagnostic](#mutation-sensitivity-diagnostic)
<!-- toc:end -->

[Documentation](../README.md) · [Project](../../README.md)

Generated from the argument parser with cogapp. After changing CLI arguments, run
`bash scripts/project-run.sh cog -r README.md docs/cli/README.md docs/rules/README.md docs/input-domains/README.md`.
Checks enforce that this reference stays current.

<!-- [[[cog
import cog
from hypothesis_helm.reporting.documentation.cli_reference import help_markdown
cog.out(help_markdown())
]]] -->
## helm hypothesis

<details>
<summary>helm hypothesis</summary>

~~~text
usage: helm hypothesis [-h] [--generate-config]
                       {rules,replay-changes,aggregate,export-minimal-values,scan,generate,audit,run,test,schemas} ...

Audit and property-test Helm chart values.

positional arguments:
  {rules,replay-changes,aggregate,export-minimal-values,scan,generate,audit,run,test,schemas}
    rules               list classified chart findings and diagnostics
    replay-changes      verify and replay saved values or manifest changes
    aggregate           verify piped shard reports and write one final report
    export-minimal-values
                        write example values beside each discovered chart
    scan                fetch and test charts from remote Git or Helm repositories
    generate            generate one typed Python property test per values path
    audit               discover value references and schema gaps
    run                 run a saved generated Python suite
    test                discover and test local charts recursively
    schemas             prepare the sparse Kubernetes schema cache

options:
  -h, --help            show this help message and exit
  --generate-config     print the default .hypothesis-helm.yaml template to stdout and
                        exit
~~~

</details>

## helm hypothesis rules

<details>
<summary>helm hypothesis rules</summary>

~~~text
usage: helm hypothesis rules [-h] [--format {text,json,config,markdown}]

List the finding codes used to report chart defects, schema gaps, and testing
limitations. Use these codes to configure which findings to ignore.

options:
  -h, --help            show this help message and exit
  --format {text,json,config,markdown}
                        catalog output format
~~~

</details>

## helm hypothesis replay-changes

<details>
<summary>helm hypothesis replay-changes</summary>

~~~text
usage: helm hypothesis replay-changes [-h] [--section {overrides,values,manifests}]
                                      [--baseline BASELINE] [--output OUTPUT]
                                      record

Reconstruct the overrides, values, or manifests saved with a failing test case. Verify
the baseline and replay the recorded changes to produce JSON.

positional arguments:
  record                changes.json from a failing case

options:
  -h, --help            show this help message and exit
  --section {overrides,values,manifests}
  --baseline BASELINE   baseline JSON file; overrides default to an empty map
  --output OUTPUT       write reconstructed JSON to this file; default: stdout
~~~

</details>

## helm hypothesis aggregate

<details>
<summary>helm hypothesis aggregate</summary>

~~~text
usage: helm hypothesis aggregate [-h] --shards SHARDS --run-id RUN_ID
                                 [--output-dir OUTPUT_DIR]
                                 [reports ...]

Combine reports from parallel CI shards into one Markdown and PDF report. Check that
the inputs belong to the requested run and account for the expected shards.

positional arguments:
  reports               JSON files or artifact roots; default: stdin

options:
  -h, --help            show this help message and exit
  --shards SHARDS
  --run-id RUN_ID       identifier shared by this run's shards
  --output-dir OUTPUT_DIR
                        new report directory; default: docs/reports/aggregate
~~~

</details>

## helm hypothesis export-minimal-values

<details>
<summary>helm hypothesis export-minimal-values</summary>

~~~text
usage: helm hypothesis export-minimal-values [-h] [--filename FILENAME] [--helm HELM]
                                             [--timeout TIMEOUT]
                                             [--minimal-values-timeout MINIMAL_VALUES_TIMEOUT]
                                             [--files-list FILES_LIST]
                                             [--validate-schemas]
                                             [--schema-version SCHEMA_VERSION]
                                             [--schema-cache-dir SCHEMA_CACHE_DIR]
                                             [--schema-offline]
                                             source

Create an example minimal values file beside each chart found in a local directory.
Also save a verification record describing what was checked and any remaining
limitations.

positional arguments:
  source

options:
  -h, --help            show this help message and exit
  --filename FILENAME   YAML basename only
  --helm HELM
  --timeout TIMEOUT
  --minimal-values-timeout MINIMAL_VALUES_TIMEOUT
  --files-list FILES_LIST
                        write NUL-delimited exported YAML and proof paths
  --validate-schemas    validate rendered resources against the local Kubernetes
                        schema cache
  --schema-version SCHEMA_VERSION
                        Kubernetes schema version: latest or X.Y.Z
  --schema-cache-dir SCHEMA_CACHE_DIR
  --schema-offline      reuse cached schemas without network access
~~~

</details>

## helm hypothesis scan

<details>
<summary>helm hypothesis scan</summary>

~~~text
usage: helm hypothesis scan [-h] [--helm-repository] [--chart-version CHART_VERSION]
                            [--clone-timeout CLONE_TIMEOUT] [--report [PATH]]
                            [--artifact-dir ARTIFACT_DIR] [--helm HELM]
                            [--values VALUES] [--timeout TIMEOUT]
                            [--chart-timeout CHART_TIMEOUT]
                            [--scan-timeout SCAN_TIMEOUT]
                            [--max-examples MAX_EXAMPLES] [--cache-dir CACHE_DIR]
                            [--no-cache] [--jobs JOBS] [--permutations PERMUTATIONS]
                            [--filter] [--fail [{info,warning,error}]] [--seed SEED]
                            [--build-dependencies | --no-build-dependencies]
                            [--pca-samples N] [--pca-timeout PCA_TIMEOUT]
                            [--max-mutations N]
                            [--sensitivity-timeout SENSITIVITY_TIMEOUT]
                            [--filter-adaptive]
                            [--sampling-calibration SAMPLING_CALIBRATION]
                            [--sensitivity-order N] [--sample-random PERCENT]
                            [--sample-min-cases N]
                            [--traversal-strategy {random,linear,root-first,leaf-first,sensitivity-first}]
                            [--strict | --no-strict] [--validate-schemas]
                            [--schema-version SCHEMA_VERSION]
                            [--schema-cache-dir SCHEMA_CACHE_DIR] [--schema-offline]
                            [--base-ref BASE_REF] [--output-format {json,yaml}]
                            [--export-suppressions]
                            [--export-topological-graph [FILENAME]]
                            [--minimal-values-timeout MINIMAL_VALUES_TIMEOUT]
                            [--export-minimal-values [FILENAME]]
                            [--log-color [{auto,always,never}]] [--log-file PATH]
                            [--config CONFIG] [--character-sets {ascii,unicode}]
                            [--renderer-policy {auto,native,strict}]
                            [--yaml-parser {ruamel,ruamel-safe,pyyaml}]
                            [--ignore CODE] [--disable-codes CODE[,CODE...]]
                            SOURCE

Fetch charts from a remote Git repository, Helm repository, or OCI chart reference,
then test generated values and report findings for each chart. Use test for charts
already on disk.

positional arguments:
  SOURCE                Git URL, Helm repo[/chart], public index.yaml URL, or OCI
                        chart; local paths use test

options:
  -h, --help            show this help message and exit
  --helm-repository     interpret SOURCE as a Helm repository name or HTTP(S) base URL
  --chart-version CHART_VERSION
                        Helm chart version or constraint; default: latest stable
                        release per chart
  --clone-timeout, --source-timeout CLONE_TIMEOUT
                        Git checkout or Helm source preparation budget, also bounded
                        by --scan-timeout (default: 3m)
  --report [PATH]       write Markdown and PDF; default:
                        docs/reports/<dir>_<epoch>_report
  --artifact-dir ARTIFACT_DIR
  --helm HELM
  --values VALUES       baseline file relative to each chart, or an absolute path
  --timeout TIMEOUT     seconds per Helm lint, render, or dependency build
  --chart-timeout, --time-limit CHART_TIMEOUT
                        property-test execution budget per chart (default: 3m)
  --scan-timeout SCAN_TIMEOUT
                        scan budget excluding dependency preparation; default:
                        unlimited
  --max-examples MAX_EXAMPLES
  --cache-dir CACHE_DIR
                        completed chart-result cache; default: .cache/hypothesis-
                        helm/charts
  --no-cache            disable completed chart-result caching
  --jobs, -j JOBS       path workers per chart; auto: available CPUs
  --permutations PERMUTATIONS
                        finite interaction strength; non-finite charts fall back to
                        path sampling
  --filter              filter finite charts with failure expansion; otherwise filter
                        generated inputs before path traversal
  --fail [{info,warning,error}]
                        stop at this severity or higher and exit 1; bare flag: any
                        finding; lower findings remain reported
  --seed SEED
  --build-dependencies, --no-build-dependencies
                        build locked dependencies in temporary chart copies
  --pca-samples N       with --report, measure up to N reference configurations per
                        chart for output PCA; 0 disables it (default: 64)
  --pca-timeout PCA_TIMEOUT
                        additional output-PCA measurement budget per chart with
                        --report (default: 1m)
  --max-mutations N     with --report, measure sensitivity for up to N fields per
                        chart and all their pairs (opt-in)
  --sensitivity-timeout SENSITIVITY_TIMEOUT
                        additional sensitivity measurement budget per chart with
                        --max-mutations (default: 3m)
  --filter-adaptive     enable --filter and retain 70% subject to measured topology
                        sample floors; unmatched charts keep all filtered cases
  --sampling-calibration SAMPLING_CALIBRATION
                        override the packaged adaptive-sampling calibration JSON
  --sensitivity-order N
                        maximum measured interaction order for sensitivity-first;
                        1..permutations, default: min(2, permutations)
  --sample-random PERCENT
                        retain this percentage after filtering; default: 100
                        (disabled); recall depends on selected inputs
  --sample-min-cases N  retain at least N eligible cases, or all when fewer exist
                        (default: 128)
  --traversal-strategy {random,linear,root-first,leaf-first,sensitivity-first}
                        seeded random (default), linear, root-first, leaf-first, or
                        sensitivity-first (finite coverage defaults to pairs)
  --strict, --no-strict
                        require schemas for custom resources; otherwise skip schema
                        validation when their schema is missing
  --validate-schemas    validate rendered resources against the local Kubernetes
                        schema cache
  --schema-version SCHEMA_VERSION
                        Kubernetes schema version: latest or X.Y.Z
  --schema-cache-dir SCHEMA_CACHE_DIR
  --schema-offline      reuse cached schemas without network access
  --base-ref BASE_REF   Git comparison ref for repository tests; overrides CI target
                        or previous trunk commit
  --output-format, -o {json,yaml}
                        stream rendered manifests as JSON lines or YAML documents on
                        stdout; logs and reports go to stderr
  --export-suppressions
                        write categorized suppressions.yaml in each chart's artifacts
                        after testing; review before applying
  --export-topological-graph [FILENAME]
                        export input references, control flow and observed manifests
                        as JSON and DOT
  --minimal-values-timeout MINIMAL_VALUES_TIMEOUT
                        verification and minimization budget for values export
                        (default: 30s)
  --export-minimal-values [FILENAME]
                        export example values with validation status and missing
                        fields; default: values-minimal-<checksum>-<epoch>.yaml (scan:
                        separate files per chart)
  --log-color [{auto,always,never}]
                        color log severity labels; bare flag: always; auto: terminals
                        unless NO_COLOR is set; default: never
  --log-file PATH       append logs to PATH; default: stdout (-), or stderr when
                        streaming manifests
  --config CONFIG       finding and input-domain policy YAML; default: .hypothesis-
                        helm.yaml in the working directory
  --character-sets {ascii,unicode}
                        generated text alphabet; overrides config; default: ascii
  --renderer-policy {auto,native,strict}
                        auto controls supported random inputs with visible native
                        fallback (default); native uses Helm; strict requires replay
  --yaml-parser {ruamel,ruamel-safe,pyyaml}
                        manifest parser backend; overrides yaml_parser in config;
                        default: ruamel, or the saved suite's parser
  --ignore CODE         disable one built-in check; repeat to add codes
  --disable-codes CODE[,CODE...]
                        disable comma-delimited finding codes; adds to --ignore and
                        the config file; repeatable
~~~

</details>

## helm hypothesis generate

<details>
<summary>helm hypothesis generate</summary>

~~~text
usage: helm hypothesis generate [-h] [--output OUTPUT] [--max-examples MAX_EXAMPLES]
                                [--strict | --no-strict]
                                [--fail [{info,warning,error}]]
                                [--export-topological-graph [FILENAME]]
                                [--minimal-values-timeout MINIMAL_VALUES_TIMEOUT]
                                [--export-minimal-values [FILENAME]]
                                [--log-color [{auto,always,never}]] [--log-file PATH]
                                [--config CONFIG] [--character-sets {ascii,unicode}]
                                [--renderer-policy {auto,native,strict}]
                                [--yaml-parser {ruamel,ruamel-safe,pyyaml}]
                                [--ignore CODE] [--disable-codes CODE[,CODE...]]
                                chart

Create a reusable Python property-test suite for a local chart, with one test per
values path. Input types come from the chart schema or are inferred from its values;
execute the saved suite with run.

positional arguments:
  chart

options:
  -h, --help            show this help message and exit
  --output OUTPUT
  --max-examples MAX_EXAMPLES
  --strict, --no-strict
                        require schemas for custom resources; otherwise skip schema
                        validation when their schema is missing
  --fail [{info,warning,error}]
                        stop at this severity or higher and exit 1; bare flag: any
                        finding; lower findings remain reported
  --export-topological-graph [FILENAME]
                        export input references, control flow and observed manifests
                        as JSON and DOT
  --minimal-values-timeout MINIMAL_VALUES_TIMEOUT
                        verification and minimization budget for values export
                        (default: 30s)
  --export-minimal-values [FILENAME]
                        export example values with validation status and missing
                        fields; default: values-minimal-<checksum>-<epoch>.yaml (scan:
                        separate files per chart)
  --log-color [{auto,always,never}]
                        color log severity labels; bare flag: always; auto: terminals
                        unless NO_COLOR is set; default: never
  --log-file PATH       append logs to PATH; default: stdout (-), or stderr when
                        streaming manifests
  --config CONFIG       finding and input-domain policy YAML; default: .hypothesis-
                        helm.yaml in the working directory
  --character-sets {ascii,unicode}
                        generated text alphabet; overrides config; default: ascii
  --renderer-policy {auto,native,strict}
                        auto controls supported random inputs with visible native
                        fallback (default); native uses Helm; strict requires replay
  --yaml-parser {ruamel,ruamel-safe,pyyaml}
                        manifest parser backend; overrides yaml_parser in config;
                        default: ruamel, or the saved suite's parser
  --ignore CODE         disable one built-in check; repeat to add codes
  --disable-codes CODE[,CODE...]
                        disable comma-delimited finding codes; adds to --ignore and
                        the config file; repeatable
~~~

</details>

## helm hypothesis audit

<details>
<summary>helm hypothesis audit</summary>

~~~text
usage: helm hypothesis audit [-h] [--fail [{info,warning,error}]]
                             [--artifact-dir ARTIFACT_DIR] [--export-suppressions]
                             [--export-topological-graph [FILENAME]]
                             [--minimal-values-timeout MINIMAL_VALUES_TIMEOUT]
                             [--export-minimal-values [FILENAME]]
                             [--log-color [{auto,always,never}]] [--log-file PATH]
                             [--config CONFIG] [--character-sets {ascii,unicode}]
                             [--renderer-policy {auto,native,strict}]
                             [--yaml-parser {ruamel,ruamel-safe,pyyaml}]
                             [--ignore CODE] [--disable-codes CODE[,CODE...]]
                             chart

Inspect a local chart's values, schema, and template references to identify missing
types, undocumented paths, and limits on what can be analyzed. Use this to understand
the input space before testing.

positional arguments:
  chart

options:
  -h, --help            show this help message and exit
  --fail [{info,warning,error}]
                        fail on audit findings at this severity or higher; bare flag:
                        any finding
  --artifact-dir ARTIFACT_DIR
                        audit export directory
  --export-suppressions
                        write categorized suppressions.yaml in each chart's artifacts
                        after testing; review before applying
  --export-topological-graph [FILENAME]
                        export input references, control flow and observed manifests
                        as JSON and DOT
  --minimal-values-timeout MINIMAL_VALUES_TIMEOUT
                        verification and minimization budget for values export
                        (default: 30s)
  --export-minimal-values [FILENAME]
                        export example values with validation status and missing
                        fields; default: values-minimal-<checksum>-<epoch>.yaml (scan:
                        separate files per chart)
  --log-color [{auto,always,never}]
                        color log severity labels; bare flag: always; auto: terminals
                        unless NO_COLOR is set; default: never
  --log-file PATH       append logs to PATH; default: stdout (-), or stderr when
                        streaming manifests
  --config CONFIG       finding and input-domain policy YAML; default: .hypothesis-
                        helm.yaml in the working directory
  --character-sets {ascii,unicode}
                        generated text alphabet; overrides config; default: ascii
  --renderer-policy {auto,native,strict}
                        auto controls supported random inputs with visible native
                        fallback (default); native uses Helm; strict requires replay
  --yaml-parser {ruamel,ruamel-safe,pyyaml}
                        manifest parser backend; overrides yaml_parser in config;
                        default: ruamel, or the saved suite's parser
  --ignore CODE         disable one built-in check; repeat to add codes
  --disable-codes CODE[,CODE...]
                        disable comma-delimited finding codes; adds to --ignore and
                        the config file; repeatable
~~~

</details>

## helm hypothesis run

<details>
<summary>helm hypothesis run</summary>

~~~text
usage: helm hypothesis run [-h] [--seed SEED] [--match MATCH] [--collect-only]
                           [--artifact-dir ARTIFACT_DIR] [--sample-random PERCENT]
                           [--sample-min-cases N]
                           [--traversal-strategy {random,linear,root-first,leaf-first,sensitivity-first}]
                           [--strict | --no-strict] [--validate-schemas]
                           [--schema-version SCHEMA_VERSION]
                           [--schema-cache-dir SCHEMA_CACHE_DIR] [--schema-offline]
                           [--dry-run] [--cache-dir CACHE_DIR]
                           [--disable-schema-caching] [--progress] [--run-id RUN_ID]
                           [--no-cache] [--rerun {auto,all,failed}] [--shard SHARD]
                           [--jobs JOBS] [--output-format {json,yaml}]
                           [--export-suppressions] [--fail [{info,warning,error}]]
                           [--log-color [{auto,always,never}]] [--log-file PATH]
                           [--config CONFIG] [--character-sets {ascii,unicode}]
                           [--renderer-policy {auto,native,strict}]
                           [--yaml-parser {ruamel,ruamel-safe,pyyaml}] [--ignore CODE]
                           [--disable-codes CODE[,CODE...]]
                           suite

Execute a property-test suite previously created by generate. Generate values for its
selected paths, render the chart, and record any findings.

positional arguments:
  suite

options:
  -h, --help            show this help message and exit
  --seed SEED
  --match MATCH         select tests by value-path keyword
  --collect-only
  --artifact-dir ARTIFACT_DIR
                        report directory for a saved suite
  --sample-random PERCENT
                        retain this percentage after filtering; default: 100
                        (disabled); recall depends on selected inputs
  --sample-min-cases N  retain at least N eligible cases, or all when fewer exist
                        (default: 128)
  --traversal-strategy {random,linear,root-first,leaf-first,sensitivity-first}
                        seeded random (default), linear, root-first, leaf-first, or
                        sensitivity-first (finite coverage defaults to pairs)
  --strict, --no-strict
                        require schemas for custom resources; otherwise skip schema
                        validation when their schema is missing
  --validate-schemas    validate rendered resources against the local Kubernetes
                        schema cache
  --schema-version SCHEMA_VERSION
                        Kubernetes schema version: latest or X.Y.Z
  --schema-cache-dir SCHEMA_CACHE_DIR
  --schema-offline      reuse cached schemas without network access
  --dry-run             plot coverage and forecast filtering or cached property work
                        without execution
  --cache-dir CACHE_DIR
                        persistent path-result cache directory
  --disable-schema-caching
                        compare values structure against the cached baseline without
                        updating it
  --progress            force a live progress bar on stderr, including redirected
                        output
  --run-id RUN_ID       common identifier for shards merged into one report
  --no-cache            disable path-result caching
  --rerun {auto,all,failed}
                        auto: rerun failures locally; run all paths in CI
  --shard SHARD         auto (default): detect CI node; INDEX/TOTAL: explicit shard;
                        none: disable
  --jobs, -j JOBS       workers per chart; auto: CPU count for repository/exhaustive
                        tests, PID tuning for suites; 1: serial
  --output-format, -o {json,yaml}
                        stream rendered manifests as JSON lines or YAML documents on
                        stdout; logs and reports go to stderr
  --export-suppressions
                        write categorized suppressions.yaml in each chart's artifacts
                        after testing; review before applying
  --fail [{info,warning,error}]
                        stop at this severity or higher and exit 1; bare flag: any
                        finding; lower findings remain reported
  --log-color [{auto,always,never}]
                        color log severity labels; bare flag: always; auto: terminals
                        unless NO_COLOR is set; default: never
  --log-file PATH       append logs to PATH; default: stdout (-), or stderr when
                        streaming manifests
  --config CONFIG       finding and input-domain policy YAML; default: .hypothesis-
                        helm.yaml in the working directory
  --character-sets {ascii,unicode}
                        generated text alphabet; overrides config; default: ascii
  --renderer-policy {auto,native,strict}
                        auto controls supported random inputs with visible native
                        fallback (default); native uses Helm; strict requires replay
  --yaml-parser {ruamel,ruamel-safe,pyyaml}
                        manifest parser backend; overrides yaml_parser in config;
                        default: ruamel, or the saved suite's parser
  --ignore CODE         disable one built-in check; repeat to add codes
  --disable-codes CODE[,CODE...]
                        disable comma-delimited finding codes; adds to --ignore and
                        the config file; repeatable
~~~

</details>

## helm hypothesis test

<details>
<summary>helm hypothesis test</summary>

~~~text
usage: helm hypothesis test [-h] [--report [PATH]] [--pca-samples N]
                            [--pca-timeout PCA_TIMEOUT] [--max-mutations N]
                            [--sensitivity-timeout SENSITIVITY_TIMEOUT]
                            [--values VALUES] [--chart-timeout CHART_TIMEOUT]
                            [--scan-timeout SCAN_TIMEOUT]
                            [--build-dependencies | --no-build-dependencies]
                            [--fail [{info,warning,error}]]
                            [--max-examples MAX_EXAMPLES] [--time-limit DURATION]
                            [--paths | --exhaustive | --whole-chart |
                            --permutations N] [--filter] [--filter-random N]
                            [--filter-topology N] [--expand-failures]
                            [--prune-equivalent] [--match MATCH] [--collect-only]
                            [--max-cases MAX_CASES] [--max-candidates MAX_CANDIDATES]
                            [--exhaustive-threshold EXHAUSTIVE_THRESHOLD]
                            [--exhaustive-group PATH,PATH] [--no-infer-groups]
                            [--max-group-cases MAX_GROUP_CASES] [--seed SEED]
                            [--filter-adaptive]
                            [--sampling-calibration SAMPLING_CALIBRATION]
                            [--sensitivity-order N] [--sample-random PERCENT]
                            [--sample-min-cases N]
                            [--traversal-strategy {random,linear,root-first,leaf-first,sensitivity-first}]
                            [--timeout TIMEOUT] [--helm HELM] [--release RELEASE]
                            [--namespace NAMESPACE] [--kube-version KUBE_VERSION]
                            [--allow-empty] [--artifact-dir ARTIFACT_DIR]
                            [--strict | --no-strict] [--validate-schemas]
                            [--schema-version SCHEMA_VERSION]
                            [--schema-cache-dir SCHEMA_CACHE_DIR] [--schema-offline]
                            [--base-ref BASE_REF] [--dry-run] [--cache-dir CACHE_DIR]
                            [--disable-schema-caching] [--progress] [--run-id RUN_ID]
                            [--no-cache] [--rerun {auto,all,failed}] [--shard SHARD]
                            [--jobs JOBS] [--output-format {json,yaml}]
                            [--export-suppressions]
                            [--export-topological-graph [FILENAME]]
                            [--minimal-values-timeout MINIMAL_VALUES_TIMEOUT]
                            [--export-minimal-values [FILENAME]]
                            [--log-color [{auto,always,never}]] [--log-file PATH]
                            [--config CONFIG] [--character-sets {ascii,unicode}]
                            [--renderer-policy {auto,native,strict}]
                            [--yaml-parser {ruamel,ruamel-safe,pyyaml}]
                            [--ignore CODE] [--disable-codes CODE[,CODE...]]
                            [chart]

Test a local chart or recursively discover charts in a local directory. Generate
values, render the charts, and report findings with the inputs that triggered them.

positional arguments:
  chart                 local chart or directory containing charts (default: current
                        directory)

options:
  -h, --help            show this help message and exit
  --report [PATH]       write combined Markdown/PDF; default:
                        docs/reports/<dir>_<epoch>_report
  --pca-samples N       with --report, measure up to N reference configurations per
                        chart for output PCA; 0 disables it (default: 64)
  --pca-timeout PCA_TIMEOUT
                        additional output-PCA measurement budget per chart with
                        --report (default: 1m)
  --max-mutations N     with --report, measure sensitivity for up to N fields per
                        chart and all their pairs (opt-in)
  --sensitivity-timeout SENSITIVITY_TIMEOUT
                        additional sensitivity measurement budget per chart with
                        --max-mutations (default: 3m)
  --values VALUES       baseline file relative to each chart, or an absolute path
  --chart-timeout CHART_TIMEOUT
                        property-test budget per discovered chart (default: 3m)
  --scan-timeout SCAN_TIMEOUT
                        total local discovery/testing budget, excluding dependency
                        preparation
  --build-dependencies, --no-build-dependencies
                        build dependencies in isolated copies
  --fail [{info,warning,error}]
                        stop at this severity or higher and exit 1; bare flag: any
                        finding; lower findings remain reported
  --max-examples MAX_EXAMPLES
  --time-limit DURATION
                        whole-chart execution budget, e.g. 30s or 3m (default: 3m);
                        excludes planning
  --paths               force generated per-path testing
  --exhaustive          enumerate finite whole-chart inputs
  --whole-chart         sample whole-chart inputs
  --permutations N      cover valid N-way finite interactions; non-finite charts fall
                        back to path sampling
  --filter-random N     retain a seeded quarter of finite permutation cases per step;
                        default: 0
  --prune-equivalent    skip Helm only for proved output equivalence to a successful
                        render
  --match MATCH         select generated tests by value-path keyword
  --collect-only        generate and list tests
  --max-cases MAX_CASES
                        bound exhaustive domains or permutation suites and factor
                        domains
  --max-candidates MAX_CANDIDATES
                        bound permutation planning work
  --exhaustive-threshold EXHAUSTIVE_THRESHOLD
                        enumerate finite spaces smaller than this count; 0 disables
                        promotion
  --exhaustive-group PATH,PATH
                        require exhaustive coverage of a group of value paths or
                        containers; repeatable
  --no-infer-groups     disable inferred exhaustive groups
  --max-group-cases MAX_GROUP_CASES
                        bound automatically inferred group domains
  --seed SEED
  --filter-adaptive     enable --filter and retain 70% subject to measured topology
                        sample floors; unmatched charts keep all filtered cases
  --sampling-calibration SAMPLING_CALIBRATION
                        override the packaged adaptive-sampling calibration JSON
  --sensitivity-order N
                        maximum measured interaction order for sensitivity-first;
                        1..permutations, default: min(2, permutations)
  --sample-random PERCENT
                        retain this percentage after filtering; default: 100
                        (disabled); recall depends on selected inputs
  --sample-min-cases N  retain at least N eligible cases, or all when fewer exist
                        (default: 128)
  --traversal-strategy {random,linear,root-first,leaf-first,sensitivity-first}
                        seeded random (default), linear, root-first, leaf-first, or
                        sensitivity-first (finite coverage defaults to pairs)
  --timeout TIMEOUT
  --helm HELM
  --release RELEASE
  --namespace NAMESPACE
  --kube-version KUBE_VERSION
  --allow-empty
  --artifact-dir ARTIFACT_DIR
  --strict, --no-strict
                        require schemas for custom resources; otherwise skip schema
                        validation when their schema is missing
  --validate-schemas    validate rendered resources against the local Kubernetes
                        schema cache
  --schema-version SCHEMA_VERSION
                        Kubernetes schema version: latest or X.Y.Z
  --schema-cache-dir SCHEMA_CACHE_DIR
  --schema-offline      reuse cached schemas without network access
  --base-ref BASE_REF   Git comparison ref for repository tests; overrides CI target
                        or previous trunk commit
  --dry-run             plot coverage and forecast filtering or cached property work
                        without execution
  --cache-dir CACHE_DIR
                        persistent path-result cache directory
  --disable-schema-caching
                        compare values structure against the cached baseline without
                        updating it
  --progress            force a live progress bar on stderr, including redirected
                        output
  --run-id RUN_ID       common identifier for shards merged into one report
  --no-cache            disable path-result caching
  --rerun {auto,all,failed}
                        auto: rerun failures locally; run all paths in CI
  --shard SHARD         auto (default): detect CI node; INDEX/TOTAL: explicit shard;
                        none: disable
  --jobs, -j JOBS       workers per chart; auto: CPU count for repository/exhaustive
                        tests, PID tuning for suites; 1: serial
  --output-format, -o {json,yaml}
                        stream rendered manifests as JSON lines or YAML documents on
                        stdout; logs and reports go to stderr
  --export-suppressions
                        write categorized suppressions.yaml in each chart's artifacts
                        after testing; review before applying
  --export-topological-graph [FILENAME]
                        export input references, control flow and observed manifests
                        as JSON and DOT
  --minimal-values-timeout MINIMAL_VALUES_TIMEOUT
                        verification and minimization budget for values export
                        (default: 30s)
  --export-minimal-values [FILENAME]
                        export example values with validation status and missing
                        fields; default: values-minimal-<checksum>-<epoch>.yaml (scan:
                        separate files per chart)
  --log-color [{auto,always,never}]
                        color log severity labels; bare flag: always; auto: terminals
                        unless NO_COLOR is set; default: never
  --log-file PATH       append logs to PATH; default: stdout (-), or stderr when
                        streaming manifests
  --config CONFIG       finding and input-domain policy YAML; default: .hypothesis-
                        helm.yaml in the working directory
  --character-sets {ascii,unicode}
                        generated text alphabet; overrides config; default: ascii
  --renderer-policy {auto,native,strict}
                        auto controls supported random inputs with visible native
                        fallback (default); native uses Helm; strict requires replay
  --yaml-parser {ruamel,ruamel-safe,pyyaml}
                        manifest parser backend; overrides yaml_parser in config;
                        default: ruamel, or the saved suite's parser
  --ignore CODE         disable one built-in check; repeat to add codes
  --disable-codes CODE[,CODE...]
                        disable comma-delimited finding codes; adds to --ignore and
                        the config file; repeatable

filtering:
  Use --filter or the individual methods below; random filtering is independent.

  --filter              enable --filter-topology 2 and --expand-failures
  --filter-topology N   thin symbolic output/branch regions; retain representatives
                        and unknowns; combines with --filter-random
  --expand-failures     test omitted members of failed symbolic regions within the
                        execution budget
~~~

</details>

## helm hypothesis schemas

<details>
<summary>helm hypothesis schemas</summary>

~~~text
usage: helm hypothesis schemas [-h] [--schema-version SCHEMA_VERSION]
                               [--schema-cache-dir SCHEMA_CACHE_DIR]
                               [--schema-offline]

Prepare a local cache of Kubernetes API schemas for built-in manifest validation.
Select a Kubernetes version to download, or use --schema-offline to reuse schemas
already cached.

options:
  -h, --help            show this help message and exit
  --schema-version SCHEMA_VERSION
  --schema-cache-dir SCHEMA_CACHE_DIR
  --schema-offline
~~~

</details>
<!-- [[[end]]] -->

## Mutation sensitivity diagnostic

The separate hypothesis-helm-sensitivity command measures output changes for an explicit list of values mutations.
See [usage, input format and metric definitions](../compiler/sensitivity.md).
