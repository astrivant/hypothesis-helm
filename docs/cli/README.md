# CLI reference

[Documentation](../README.md) · [Project](../../README.md)

Generated from the argument parser with cogapp. After changing CLI arguments, run
`bash scripts/project-python.sh -m cogapp -r docs/cli/README.md`.
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
usage: helm hypothesis [-h] {generate,audit,run,test,schemas} ...

Audit and property-test Helm chart values.

positional arguments:
  {generate,audit,run,test,schemas}
    generate            generate one typed Python property test per values path
    audit               discover value references and schema gaps
    run                 run a saved generated Python suite
    test                select finite coverage or generate per-path tests
    schemas             prepare the sparse Kubernetes schema cache

options:
  -h, --help            show this help message and exit
~~~

</details>

<details>
<summary>helm hypothesis generate</summary>

~~~text
usage: helm hypothesis generate [-h] [--output OUTPUT] [--max-examples MAX_EXAMPLES]
                                [--strict]
                                chart

positional arguments:
  chart

options:
  -h, --help            show this help message and exit
  --output OUTPUT
  --max-examples MAX_EXAMPLES
  --strict              require all configurable fields in source values.yaml and a
                        clean audit
~~~

</details>

<details>
<summary>helm hypothesis audit</summary>

~~~text
usage: helm hypothesis audit [-h] [--strict] chart

positional arguments:
  chart

options:
  -h, --help  show this help message and exit
  --strict    fail on any finding or unresolved access
~~~

</details>

<details>
<summary>helm hypothesis run</summary>

~~~text
usage: helm hypothesis run [-h] [--seed SEED] [--match MATCH] [--collect-only]
                           [--artifact-dir ARTIFACT_DIR] [--dry-run] [--kubeconform]
                           [--schema-version SCHEMA_VERSION]
                           [--schema-cache-dir SCHEMA_CACHE_DIR] [--schema-offline]
                           [--kubeconform-binary KUBECONFORM_BINARY]
                           [--cache-dir CACHE_DIR] [--disable-schema-caching]
                           [--progress] [--no-cache] [--rerun {auto,all,failed}]
                           [--shard SHARD] [--jobs JOBS] [--output {json}] [--strict]
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
  --dry-run             plot coverage and forecast filtering or cached property work
                        without execution
  --kubeconform         validate Kubernetes API schemas
  --schema-version SCHEMA_VERSION
                        Kubernetes schema version: latest or X.Y.Z
  --schema-cache-dir SCHEMA_CACHE_DIR
  --schema-offline      reuse cached schemas without network access
  --kubeconform-binary KUBECONFORM_BINARY
  --cache-dir CACHE_DIR
                        persistent path-result cache directory
  --disable-schema-caching
                        compare values structure against the cached baseline without
                        updating it
  --progress            force a live progress bar on stderr, including redirected
                        output
  --no-cache            disable path-result caching
  --rerun {auto,all,failed}
                        auto: rerun failures locally; run all paths in CI
  --shard SHARD         auto (default): detect CI node; INDEX/TOTAL: explicit shard;
                        none: disable
  --jobs, -j JOBS       auto (default): PID throughput tuning; N: fixed worker count;
                        1: serial
  --output, -o {json}   stream one rendered manifest per JSON line on stdout; reports
                        go to stderr
  --strict              require all configurable fields in source values.yaml and a
                        clean audit
~~~

</details>

<details>
<summary>helm hypothesis test</summary>

~~~text
usage: helm hypothesis test [-h] [--max-examples MAX_EXAMPLES] [--time-limit DURATION]
                            [--paths | --exhaustive | --whole-chart |
                            --permutations N] [--prune-equivalent] [--match MATCH]
                            [--collect-only] [--max-cases MAX_CASES]
                            [--max-candidates MAX_CANDIDATES]
                            [--exhaustive-threshold EXHAUSTIVE_THRESHOLD]
                            [--exhaustive-group PATH,PATH] [--no-infer-groups]
                            [--max-group-cases MAX_GROUP_CASES] [--seed SEED]
                            [--timeout TIMEOUT] [--helm HELM] [--release RELEASE]
                            [--namespace NAMESPACE] [--kube-version KUBE_VERSION]
                            [--allow-empty] [--artifact-dir ARTIFACT_DIR] [--dry-run]
                            [--kubeconform] [--schema-version SCHEMA_VERSION]
                            [--schema-cache-dir SCHEMA_CACHE_DIR] [--schema-offline]
                            [--kubeconform-binary KUBECONFORM_BINARY]
                            [--cache-dir CACHE_DIR] [--disable-schema-caching]
                            [--progress] [--no-cache] [--rerun {auto,all,failed}]
                            [--shard SHARD] [--jobs JOBS] [--output {json}] [--strict]
                            [chart]

positional arguments:
  chart                 chart directory (defaults to the current directory)

options:
  -h, --help            show this help message and exit
  --max-examples MAX_EXAMPLES
  --time-limit DURATION
                        whole-chart execution budget, e.g. 30s or 3m (default: 3m);
                        excludes planning
  --paths               force generated per-path testing
  --exhaustive          enumerate finite whole-chart inputs
  --whole-chart         sample whole-chart inputs
  --permutations N      cover every valid N-way finite interaction
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
  --timeout TIMEOUT
  --helm HELM
  --release RELEASE
  --namespace NAMESPACE
  --kube-version KUBE_VERSION
  --allow-empty
  --artifact-dir ARTIFACT_DIR
  --dry-run             plot coverage and forecast filtering or cached property work
                        without execution
  --kubeconform         validate Kubernetes API schemas
  --schema-version SCHEMA_VERSION
                        Kubernetes schema version: latest or X.Y.Z
  --schema-cache-dir SCHEMA_CACHE_DIR
  --schema-offline      reuse cached schemas without network access
  --kubeconform-binary KUBECONFORM_BINARY
  --cache-dir CACHE_DIR
                        persistent path-result cache directory
  --disable-schema-caching
                        compare values structure against the cached baseline without
                        updating it
  --progress            force a live progress bar on stderr, including redirected
                        output
  --no-cache            disable path-result caching
  --rerun {auto,all,failed}
                        auto: rerun failures locally; run all paths in CI
  --shard SHARD         auto (default): detect CI node; INDEX/TOTAL: explicit shard;
                        none: disable
  --jobs, -j JOBS       auto (default): PID throughput tuning; N: fixed worker count;
                        1: serial
  --output, -o {json}   stream one rendered manifest per JSON line on stdout; reports
                        go to stderr
  --strict              require all configurable fields in source values.yaml and a
                        clean audit
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
