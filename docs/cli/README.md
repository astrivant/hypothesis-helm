# CLI reference

[Documentation](../README.md) · [Project](../../README.md)

Generated from the argument parser with cogapp. After changing CLI arguments, run
`bash scripts/project-run.sh cog -r docs/cli/README.md`.
Checks enforce that this reference stays current.

<!-- [[[cog
import argparse
import os
import cog
from hypothesis_helm.cli import argument_parser

os.environ["COLUMNS"] = "88"
parser = argument_parser(prog="helm hypothesis")
parsers = [("helm hypothesis", parser)]
for action in parser._actions:
    if isinstance(action, argparse._SubParsersAction):
        parsers.extend((f"helm hypothesis {name}", child) for name, child in action.choices.items())
for title, command in parsers:
    cog.outl(f"<details>\n<summary>{title}</summary>\n")
    cog.outl("~~~text")
    cog.out(command.format_help())
    cog.outl("~~~\n\n</details>\n")
]]] -->
<details>
<summary>helm hypothesis</summary>

~~~text
usage: helm hypothesis [-h]
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
~~~

</details>

<details>
<summary>helm hypothesis rules</summary>

~~~text
usage: helm hypothesis rules [-h] [--format {text,json,config,markdown}]

options:
  -h, --help            show this help message and exit
  --format {text,json,config,markdown}
                        catalog output format
~~~

</details>

<details>
<summary>helm hypothesis replay-changes</summary>

~~~text
usage: helm hypothesis replay-changes [-h] [--section {overrides,values,manifests}]
                                      [--baseline BASELINE] [--output OUTPUT]
                                      record

positional arguments:
  record                changes.json from a failing case

options:
  -h, --help            show this help message and exit
  --section {overrides,values,manifests}
  --baseline BASELINE   baseline JSON file; overrides default to an empty map
  --output OUTPUT       write reconstructed JSON to this file; default: stdout
~~~

</details>

<details>
<summary>helm hypothesis aggregate</summary>

~~~text
usage: helm hypothesis aggregate [-h] --shards SHARDS --run-id RUN_ID
                                 [--output-dir OUTPUT_DIR]
                                 [reports ...]

positional arguments:
  reports               JSON files or artifact roots; default: stdin

options:
  -h, --help            show this help message and exit
  --shards SHARDS
  --run-id RUN_ID       identifier shared by this run's shards
  --output-dir OUTPUT_DIR
                        new report directory; stdin default: reports/aggregate
~~~

</details>

<details>
<summary>helm hypothesis export-minimal-values</summary>

~~~text
usage: helm hypothesis export-minimal-values [-h] [--filename FILENAME] [--helm HELM]
                                             [--timeout TIMEOUT]
                                             [--minimal-values-timeout MINIMAL_VALUES_TIMEOUT]
                                             [--files-list FILES_LIST] [--kubeconform]
                                             [--schema-version SCHEMA_VERSION]
                                             [--schema-cache-dir SCHEMA_CACHE_DIR]
                                             [--schema-offline]
                                             [--kubeconform-binary KUBECONFORM_BINARY]
                                             source

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
  --kubeconform         validate Kubernetes API schemas
  --schema-version SCHEMA_VERSION
                        Kubernetes schema version: latest or X.Y.Z
  --schema-cache-dir SCHEMA_CACHE_DIR
  --schema-offline      reuse cached schemas without network access
  --kubeconform-binary KUBECONFORM_BINARY
~~~

</details>

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
                            [--filter] [--fail] [--seed SEED]
                            [--build-dependencies | --no-build-dependencies]
                            [--filter-adaptive]
                            [--sampling-calibration SAMPLING_CALIBRATION]
                            [--sample-random PERCENT] [--sample-min-cases N]
                            [--traversal-strategy {random,linear,root-first,leaf-first}]
                            [--base-ref BASE_REF]
                            [--export-topological-graph [FILENAME]]
                            [--minimal-values-timeout MINIMAL_VALUES_TIMEOUT]
                            [--export-minimal-values [FILENAME]] [--config CONFIG]
                            [--ignore CODE]
                            SOURCE

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
  --report [PATH]       write Markdown and PDF; default: <dir>_<epoch>_report
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
                        finite interaction strength; default: automatic finite
                        coverage or sampling
  --filter              filter finite charts with failure expansion; otherwise filter
                        generated inputs before path traversal
  --fail                stop on the first chart test failure; save partial results and
                        exit 1
  --seed SEED
  --build-dependencies, --no-build-dependencies
                        build locked dependencies in temporary chart copies
  --filter-adaptive     enable --filter and retain 70% subject to measured topology
                        sample floors; unmatched charts keep all filtered cases
  --sampling-calibration SAMPLING_CALIBRATION
                        override the packaged adaptive-sampling calibration JSON
  --sample-random PERCENT
                        retain this percentage after filtering; default: 100
                        (disabled); no bug-recall guarantee
  --sample-min-cases N  retain at least N eligible cases, or all when fewer exist
                        (default: 128)
  --traversal-strategy {random,linear,root-first,leaf-first}
                        value-path order: seeded random (default), original linear,
                        root-first, or leaf-first
  --base-ref BASE_REF   Git comparison ref for repository tests; overrides CI target
                        or previous trunk commit
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
  --config CONFIG       rule policy YAML; default: .hypothesis-helm.yaml in the
                        working directory
  --ignore CODE         disable one built-in check; repeat to add codes
~~~

</details>

<details>
<summary>helm hypothesis generate</summary>

~~~text
usage: helm hypothesis generate [-h] [--output OUTPUT] [--max-examples MAX_EXAMPLES]
                                [--strict] [--export-topological-graph [FILENAME]]
                                [--minimal-values-timeout MINIMAL_VALUES_TIMEOUT]
                                [--export-minimal-values [FILENAME]] [--config CONFIG]
                                [--ignore CODE]
                                chart

positional arguments:
  chart

options:
  -h, --help            show this help message and exit
  --output OUTPUT
  --max-examples MAX_EXAMPLES
  --strict              require all configurable fields in source values.yaml and a
                        clean audit
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
  --config CONFIG       rule policy YAML; default: .hypothesis-helm.yaml in the
                        working directory
  --ignore CODE         disable one built-in check; repeat to add codes
~~~

</details>

<details>
<summary>helm hypothesis audit</summary>

~~~text
usage: helm hypothesis audit [-h] [--strict] [--export-topological-graph [FILENAME]]
                             [--minimal-values-timeout MINIMAL_VALUES_TIMEOUT]
                             [--export-minimal-values [FILENAME]] [--config CONFIG]
                             [--ignore CODE]
                             chart

positional arguments:
  chart

options:
  -h, --help            show this help message and exit
  --strict              fail on any finding or unresolved access
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
  --config CONFIG       rule policy YAML; default: .hypothesis-helm.yaml in the
                        working directory
  --ignore CODE         disable one built-in check; repeat to add codes
~~~

</details>

<details>
<summary>helm hypothesis run</summary>

~~~text
usage: helm hypothesis run [-h] [--seed SEED] [--match MATCH] [--collect-only]
                           [--artifact-dir ARTIFACT_DIR] [--sample-random PERCENT]
                           [--sample-min-cases N]
                           [--traversal-strategy {random,linear,root-first,leaf-first}]
                           [--kubeconform] [--schema-version SCHEMA_VERSION]
                           [--schema-cache-dir SCHEMA_CACHE_DIR] [--schema-offline]
                           [--kubeconform-binary KUBECONFORM_BINARY] [--dry-run]
                           [--cache-dir CACHE_DIR] [--disable-schema-caching]
                           [--progress] [--run-id RUN_ID] [--no-cache]
                           [--rerun {auto,all,failed}] [--shard SHARD] [--jobs JOBS]
                           [--output {json}] [--strict] [--config CONFIG]
                           [--ignore CODE]
                           suite

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
                        (disabled); no bug-recall guarantee
  --sample-min-cases N  retain at least N eligible cases, or all when fewer exist
                        (default: 128)
  --traversal-strategy {random,linear,root-first,leaf-first}
                        value-path order: seeded random (default), original linear,
                        root-first, or leaf-first
  --kubeconform         validate Kubernetes API schemas
  --schema-version SCHEMA_VERSION
                        Kubernetes schema version: latest or X.Y.Z
  --schema-cache-dir SCHEMA_CACHE_DIR
  --schema-offline      reuse cached schemas without network access
  --kubeconform-binary KUBECONFORM_BINARY
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
  --output, -o {json}   stream one rendered manifest per JSON line on stdout; reports
                        go to stderr
  --strict              require all configurable fields in source values.yaml and a
                        clean audit
  --config CONFIG       rule policy YAML; default: .hypothesis-helm.yaml in the
                        working directory
  --ignore CODE         disable one built-in check; repeat to add codes
~~~

</details>

<details>
<summary>helm hypothesis test</summary>

~~~text
usage: helm hypothesis test [-h] [--report [PATH]] [--values VALUES]
                            [--chart-timeout CHART_TIMEOUT]
                            [--scan-timeout SCAN_TIMEOUT]
                            [--build-dependencies | --no-build-dependencies] [--fail]
                            [--max-examples MAX_EXAMPLES] [--time-limit DURATION]
                            [--paths | --exhaustive | --whole-chart |
                            --permutations N] [--filter] [--trim-random N]
                            [--trim-topology N] [--expand-failures]
                            [--prune-equivalent] [--match MATCH] [--collect-only]
                            [--max-cases MAX_CASES] [--max-candidates MAX_CANDIDATES]
                            [--exhaustive-threshold EXHAUSTIVE_THRESHOLD]
                            [--exhaustive-group PATH,PATH] [--no-infer-groups]
                            [--max-group-cases MAX_GROUP_CASES] [--seed SEED]
                            [--filter-adaptive]
                            [--sampling-calibration SAMPLING_CALIBRATION]
                            [--sample-random PERCENT] [--sample-min-cases N]
                            [--traversal-strategy {random,linear,root-first,leaf-first}]
                            [--timeout TIMEOUT] [--helm HELM] [--release RELEASE]
                            [--namespace NAMESPACE] [--kube-version KUBE_VERSION]
                            [--allow-empty] [--artifact-dir ARTIFACT_DIR]
                            [--kubeconform] [--schema-version SCHEMA_VERSION]
                            [--schema-cache-dir SCHEMA_CACHE_DIR] [--schema-offline]
                            [--kubeconform-binary KUBECONFORM_BINARY]
                            [--base-ref BASE_REF] [--dry-run] [--cache-dir CACHE_DIR]
                            [--disable-schema-caching] [--progress] [--run-id RUN_ID]
                            [--no-cache] [--rerun {auto,all,failed}] [--shard SHARD]
                            [--jobs JOBS] [--output {json}] [--strict]
                            [--export-topological-graph [FILENAME]]
                            [--minimal-values-timeout MINIMAL_VALUES_TIMEOUT]
                            [--export-minimal-values [FILENAME]] [--config CONFIG]
                            [--ignore CODE]
                            [chart]

positional arguments:
  chart                 local chart or directory containing charts (default: current
                        directory)

options:
  -h, --help            show this help message and exit
  --report [PATH]       write combined Markdown/PDF; default: <dir>_<epoch>_report
  --values VALUES       baseline file relative to each chart, or an absolute path
  --chart-timeout CHART_TIMEOUT
                        property-test budget per discovered chart (default: 3m)
  --scan-timeout SCAN_TIMEOUT
                        total local discovery/testing budget, excluding dependency
                        preparation
  --build-dependencies, --no-build-dependencies
                        build dependencies in isolated copies
  --fail                stop on the first chart failure and save partial results
  --max-examples MAX_EXAMPLES
  --time-limit DURATION
                        whole-chart execution budget, e.g. 30s or 3m (default: 3m);
                        excludes planning
  --paths               force generated per-path testing
  --exhaustive          enumerate finite whole-chart inputs
  --whole-chart         sample whole-chart inputs
  --permutations N      cover every valid N-way finite interaction
  --trim-random, --trim N
                        retain a seeded quarter of finite permutation cases per step;
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
  --sample-random PERCENT
                        retain this percentage after filtering; default: 100
                        (disabled); no bug-recall guarantee
  --sample-min-cases N  retain at least N eligible cases, or all when fewer exist
                        (default: 128)
  --traversal-strategy {random,linear,root-first,leaf-first}
                        value-path order: seeded random (default), original linear,
                        root-first, or leaf-first
  --timeout TIMEOUT
  --helm HELM
  --release RELEASE
  --namespace NAMESPACE
  --kube-version KUBE_VERSION
  --allow-empty
  --artifact-dir ARTIFACT_DIR
  --kubeconform         validate Kubernetes API schemas
  --schema-version SCHEMA_VERSION
                        Kubernetes schema version: latest or X.Y.Z
  --schema-cache-dir SCHEMA_CACHE_DIR
  --schema-offline      reuse cached schemas without network access
  --kubeconform-binary KUBECONFORM_BINARY
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
  --output, -o {json}   stream one rendered manifest per JSON line on stdout; reports
                        go to stderr
  --strict              require all configurable fields in source values.yaml and a
                        clean audit
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
  --config CONFIG       rule policy YAML; default: .hypothesis-helm.yaml in the
                        working directory
  --ignore CODE         disable one built-in check; repeat to add codes

filtering:
  Use --filter or the individual methods below; random trimming is independent.

  --filter              enable --trim-topology 2 and --expand-failures
  --trim-topology N     thin symbolic output/branch regions; retain representatives
                        and unknowns; combines with --trim-random
  --expand-failures     test omitted members of failed symbolic regions within the
                        execution budget
~~~

</details>

<details>
<summary>helm hypothesis schemas</summary>

~~~text
usage: helm hypothesis schemas [-h] [--schema-version SCHEMA_VERSION]
                               [--schema-cache-dir SCHEMA_CACHE_DIR]
                               [--schema-offline]
                               [--kubeconform-binary KUBECONFORM_BINARY]

options:
  -h, --help            show this help message and exit
  --schema-version SCHEMA_VERSION
  --schema-cache-dir SCHEMA_CACHE_DIR
  --schema-offline
  --kubeconform-binary KUBECONFORM_BINARY
~~~

</details>

<!-- [[[end]]] -->
