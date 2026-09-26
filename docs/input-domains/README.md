# Input domains

<!-- toc:start -->
**Table of contents**

- [Generation and rejected candidates](#generation-and-rejected-candidates)
- [Character sets](#character-sets)
- [YAML parser backends](#yaml-parser-backends)
- [Default destination catalog](#default-destination-catalog)
- [Chart-specific constraints](#chart-specific-constraints)
- [Complete configuration example](#complete-configuration-example)
  - [Inheritance and test budgets](#inheritance-and-test-budgets)
  - [Character exclusions](#character-exclusions)
  - [Source and chart matrices](#source-and-chart-matrices)
- [Opaque objects: HH2006](#opaque-objects-hh2006)
- [Custom resources](#custom-resources)
- [Coverage and reproducibility](#coverage-and-reproducibility)
- [Rebuilding the catalog before release](#rebuilding-the-catalog-before-release)
  - [Source verification and limits](#source-verification-and-limits)
<!-- toc:end -->

Input domains control which values Hypothesis generates and shrinks. For example, a Secret reference can use a valid
Secret name while its activation flag still varies. This avoids spending the test budget on `secretName: ">0"`, while
keeping YAML validation enabled for the configurations that are tested.

## Generation and rejected candidates

The generator builds Hypothesis strategies from schema constraints: bounded numbers, enum choices, object properties
and array items. It samples those strategies rather than enumerating every possible value and discarding invalid ones.
The original schema still validates each candidate after character restrictions and other generation-only adaptations.
Constraints that cannot be built directly may require rejection; excessive rejection remains a diagnostic, not a reason
to disable Hypothesis's health checks globally.

Before generation, conditional schemas are rewritten as `(condition AND then) OR (NOT condition AND else)`.
This preserves the accepted inputs and avoids a `hypothesis-jsonschema` 0.23.1 bug: an impossible conditional such as
`{"if": true, "then": false, "else": false}` can mutate the library's shared impossible-schema marker and corrupt later
strategies in the same process. Regression tests cover impossible conditionals followed by ordinary object and tuple generation.
This is a generator compatibility measure; it does not modify the chart's schema or suppress findings.

## Character sets

Generated strings and arbitrary map keys use ASCII by default. Tabs and other control characters are excluded by default;
line feeds (`\n`) and carriage returns (`\r`) remain available for multiline configuration.
ASCII punctuation is still tested. This restriction applies before rendering, in both normal and deferred sampling.

To include Unicode text, set the mode in `.hypothesis-helm.yaml`:

```yaml
hypothesis:
  character_sets: unicode
```

Or override the config for one command:

```sh
helm hypothesis test ./chart --filter --character-sets unicode
helm hypothesis scan https://github.com/example/charts.git --character-sets ascii
```

`--character-sets ascii|unicode` is available on `test`, `scan`, `run`, `generate` and `audit`.
The CLI overrides the global config default; more specific branch rules still apply. Reports and saved suites record the mode, workers inherit it,
and changing it invalidates cached test successes.

Supplied defaults, explicitly declared property names, and exact `enum`/`const` strings are not rewritten to ASCII.
The configured control-character restriction still applies to sampled enum/const values. Finite exhaustive enumeration
retains its declared domain. A pattern requiring non-ASCII generated text needs `unicode`; incompatible restrictions
produce a generation diagnostic rather than relaxing the schema.

The underlying generators support an [encoding constraint](https://github.com/python-jsonschema/hypothesis-jsonschema#api).
We also constrain nested values from unconstrained schemas, where a generic JSON strategy may produce Unicode.

## YAML parser backends

If a rendered manifest appears valid but the parser rejects it, rerun the same chart and seed with another parser:

```sh
helm hypothesis test ./chart --seed 42 --yaml-parser pyyaml
```

`--yaml-parser` is available on `audit`, `generate`, `test`, `scan` and `run`. To set a project default:

```yaml
yaml_parser: pyyaml
```

| Backend | Manifest reader | When to use it |
| --- | --- | --- |
| `ruamel` | ruamel.yaml round-trip reader; the default | Keep the existing parsing behavior. |
| `ruamel-safe` | ruamel.yaml safe reader, using LibYAML when installed | Compare ruamel's safe and round-trip readers. |
| `pyyaml` | PyYAML SafeLoader | Compare against an independent reader. |

The selected reader parses every rendered document. A rejection remains an `HH1101` finding and names the backend;
there is no automatic fallback. All three reject explicit duplicate mapping keys while allowing ordinary YAML anchors
and merge overrides. They do not execute Python object tags. Values-file reading and editing continue to use ruamel's
round-trip reader so comments and anchors are preserved.

Readers can disagree about both syntax and scalar types. For example, PyYAML treats an unquoted `on` as a boolean,
whereas ruamel's default YAML 1.2 reader treats it as a string. Safe readers also reject unknown tags that the round-trip
reader can preserve for subsequent JSON validation. A different result identifies a compatibility question; acceptance
by one reader does not establish that Kubernetes accepts the manifest. Existing structural and optional API schema
validation still run after parsing. The implementation used by `ruamel-safe` depends on whether LibYAML is installed.

Workers inherit the selection, reports record it in their input-domain metadata, and saved suites remember it.
An explicit CLI or configuration setting overrides a saved suite's choice. Parser selection separates cached test results;
the manifest-validation cache also records the parser package version and implementation.

## Default destination catalog

`hypothesis_helm_catalog` ships generation constraints for Kubernetes 1.35.0. No network or Go installation is needed to use them.
The rebuild combines pinned OpenAPI schemas, supported Go validation annotations, and reusable API machinery validators.
With `--validate-schemas`, generation also uses the selected cached schema version. A locally rebuilt catalog in the same
cache supplements that version; its digest becomes part of the test cache identity.

The compiler traces a manifest field back to its values path through helper arguments, local aliases,
branch assignments, and supported transformations. It reads the chart's templates each time; there is no
library of chart names or template hashes that substitutes for this analysis.

| Template structure | How generation uses it |
| --- | --- |
| Direct references, named helper arguments, `with`, and local variables | Carry the original values path to the manifest field. |
| `if`, `default`, `coalesce`, and `ternary` | Attach the condition selecting that input; keep unused fallback inputs available. |
| `quote`, string identity formatting, `toYaml`, `toJson`, `indent`, and `nindent` | Follow supported conversions, checking the source type before applying a destination constraint. |
| A bounded literal list of maps merged into a fresh local map | Constrain contributors to homogeneous destinations such as string-valued annotations. |
| `tpl` on a traced value | Constrain supported literal inputs; structured values containing template code remain for Helm. |
| Prepared dependency, including an alias or archive | Analyze its parsed templates in the parent's values namespace, retaining dependency activation guards. |

The analysis joins independent branches instead of enumerating every combination of those branches.
Partly known conditions can establish a smaller activation region without guessing the unknown operands.
An unsupported scalar transformation leaves that field unchanged. An unresolved YAML fragment can also block
mappings inside its containing structure. Shared input mutation, unresolved resource identities, and analysis-budget
exhaustion remain explicit limitations. Independently established mappings survive where their structure is known.

These are generation constraints, not a proof that two rendered manifests are equivalent. They do not authorize
skipping a candidate as an equivalent output. Map-merge contributors are generated within the destination's
value types, including contributors whose keys could be overwritten. Arbitrary transformation inverses, dynamic
loops, and forwarded dependency globals remain unresolved when their origins cannot be established.

For example, a helper forwarding a ConfigMap reference receives the same naming constraints in a new chart as
in Cilium or MongoDB. An empty fallback remains available when the helper selects another name for empty input.
PDB limits receive their count-or-percentage constraints only when the source branch emits them. Numeric-looking
strings such as `"0"` remain eligible when their destination permits them, so missing YAML quoting can still be detected.

When `coalesce` or `default` selects a map, the compiler follows fields and conditions through that selection.
The first nonempty map wins as a whole: a missing or empty field inside it does not select that field from the fallback map.
Constraints apply to the selected input when its branch emits the field; unused fallbacks and disabled branches remain available.

Helm treats `false`, zero, an empty string, an empty map, an empty list, and `nil` as empty for these functions.
A map with a key or a list with an element is nonempty even if its contents are empty.
`coalesce` returns `nil` when every argument is empty; `default` returns its fallback unchanged, including `false` or zero.
Both evaluate their arguments before selecting a result, so an unused fallback expression can still fail or mutate a local map.
The compiler checks these distinctions against native Helm in its fallback regression matrix.

When part of a selection condition is unknown, a constraint applies only where the known part proves which input is selected.
For comparisons such as `gt (int .Values.replicaCount) 0`, the compiler recognizes integer inputs within a safe conversion range.
Numeric strings, fractional values, and possible overflows remain outside that analysis and continue to Helm.
Helper conditions use the returned text: an empty result is false, but the text `"false"` is nonempty and therefore true.

For a helper that serializes structured values with `toYaml` or `toJson`, the compiler can carry destination constraints back
to those values. For example, a fragment inserted under NetworkPolicy `spec.ingress` must contribute an array of ingress rules,
not an arbitrary map. Each contributed field or item receives its destination constraints; required siblings, total item counts,
and position-dependent rules are checked on the assembled manifest because surrounding template text can supply them.

When the helper can also execute `tpl`, these constraints apply only to structured inputs proven free of template delimiters.
`compiler.max_fragment_depth` defaults to four nested containers and limits that inspection. Deeper structures, values containing
`{{`, and raw YAML strings stay available for native rendering. These bounded fragment guards are checked after generation and
shrinking, avoiding costly expansion inside the schema generator. This can require retries when many generated candidates are invalid.
This does not establish support for every numeric conversion, helper result, or YAML fragment.
The source schema and supplied defaults are not rewritten, and conflicting declared types are reported.

Helper analysis defaults to 16 nested calls. Set `compiler.max_call_depth` in the configuration below to analyze
deeper chains. `max_discovery_nodes` bounds analysis work; `max_symbolic_variants` bounds alternatives at a branch
join. These settings are independent of Helm's rendering limits. Unresolved cases remain ordinary tests; see
[compiler analysis budgets](../compiler/analysis.md#explicit-rejection-discovery).

The catalog imports explicit scalar constraints and integer format limits. It also includes these reviewed supplements:

| Destination | Generated domain | Evidence |
| --- | --- | --- |
| Container `containerPort` | Integers 1 through 65,535 | Upstream `IsValidPortNum` plus the field description |
| Deployment `replicas` | Nonnegative integers, including zero | Replica semantics and the published int32 format |
| Secret and ConfigMap volume/key references | DNS subdomain names, at most 253 characters | Upstream `IsDNS1123Subdomain` and reviewed API field bindings |
| Service port `protocol` | `TCP`, `UDP`, `SCTP` | Published supported protocols |
| Service `type` / `sessionAffinity` | Service types: `ClusterIP`, `NodePort`, `LoadBalancer`, `ExternalName`; affinity: `None`, `ClientIP` | Pinned Go validation; empty and null preserve API defaulting |
| Pod `restartPolicy` | `Always`, `OnFailure`, `Never` | Published alternatives; a particular workload can require a subset |
| Volume `mountPath` | Nonempty strings, including Windows drive paths | Reviewed upstream behavior; a blanket colon ban would exclude supported paths |
| PDB `minAvailable` / `maxUnavailable` | Integers 0 through 2,147,483,647, or percentages 0% through 100% | Pinned PDB validation, `IntOrString` storage, and the API machinery percentage validator |

Nullable upstream fields retain their nullable domain; a chart's narrower type still takes precedence.
Unclear prose does not justify invented limits. There is no blanket punctuation ban and no guessing based on a values key's name.
Passwords, commands and other free-form strings keep their declared schema constraints, subject to the selected character set
and any known destination or explicit input policy.

Kubernetes explains that [published validation schemas can be incomplete](https://kubernetes.io/docs/concepts/overview/kubernetes-api/).
These domains do not replace schema validation, admission checks or a server-side dry run.
The PDB supplement follows [Kubernetes' PDB validator](https://github.com/kubernetes/kubernetes/blob/66452049f3d692768c39c797b21b793dce80314e/pkg/apis/policy/validation/validation.go)
and its [count/percentage checks](https://github.com/kubernetes/kubernetes/blob/66452049f3d692768c39c797b21b793dce80314e/pkg/apis/apps/validation/validation.go).
Rebuilds check pinned source hashes, extract the percentage ceiling from the Go AST, and compare boundary cases using the upstream percentage
validator plus the reviewed count/range checks. This is not a full execution of Kubernetes admission validation.
See [Secret name constraints](https://kubernetes.io/docs/concepts/configuration/secret/#constraints-on-secret-names-and-data)
and the [schema source repository](https://github.com/yannh/kubernetes-json-schema).

## Chart-specific constraints

Use `.hypothesis-helm.yaml`, or select a file with `--config`:

```yaml
input_constraints:
  - charts: [external-dns]
    path: $.txtEncrypt.secretName
    profile: kubernetes-secret-name
    allow_empty: true
  - charts: [external-dns]
    path: $.aws.credentials.mountPath
    profile: absolute-posix-path
```

`charts` matches names from `Chart.yaml`, using exact names or case-sensitive glob patterns. It also accepts
[source/name matrices](#source-and-chart-matrices). Paths accept `$`, dotted object keys and array-item selectors such as
`$.containers[*].name`. Unknown paths are errors for schema/profile restrictions; settings and finding rules can target
branches that are not present in the defaults.
`allow_empty` retains an intentional empty-string branch but cannot override a chart schema that forbids empty strings.

The `absolute-posix-path` profile requires a leading `/` and excludes NUL and line breaks. It does not check that a file exists.
For a smaller application-specific domain, replace `profile` with an inline JSON Schema:

```yaml
input_constraints:
  - charts: [external-dns]
    path: $.aws.credentials.mountPath
    schema:
      type: string
      enum: ["/.aws", "/etc/aws", "/var/run/aws"]
```

Set `downstream_inputs: false` to disable automatic destination constraints. Explicit `input_constraints` still apply.
This switch is useful when deliberately testing how templates handle values outside the downstream API's domain.
Inline constraints must be self-contained: `$ref`, `$dynamicRef`, `$recursiveRef`, and `$id` are rejected because embedding them
under a values path would change how their references resolve. Resource schemas can use local references within their own document.

Rules also accept `ignored: [HH2001]` and `enabled: [HH2006]` to control findings for a values branch.
These lists can appear alongside a `profile` or `schema`, or on their own without changing generated values.
See [path-specific finding controls](../rules/README.md#controls-for-individual-values-paths) for precedence and multi-field failures.

## Complete configuration example

This example covers every supported local configuration field. Start with
`helm hypothesis --generate-config > .hypothesis-helm.yaml` for a safe template whose optional examples are commented out.
Uncomment only the rules for your charts. The example resource schema is available at
[schemas/widget.json](schemas/widget.json); supply your own schema when testing a real custom resource.

<!-- [[[cog
import cog
from hypothesis_helm.findings.configuration import COMPLETE_EXAMPLE
cog.outl("```yaml")
cog.out(COMPLETE_EXAMPLE)
cog.outl("```")
]]] -->
```yaml
ignored: [HH2006]  # Other findings remain enabled.

# Global defaults for fresh generated text; supplied values are preserved.
downstream_inputs: true  # Use constraints from supported downstream field mappings.
yaml_parser: ruamel  # Rendered manifests: ruamel, ruamel-safe or pyyaml. Values files retain round-trip editing.
findings:
  fail_on: null  # null: existing exit behavior; info, warning or error: fail fast at that severity or higher.
  severity:  # Optional per-code overrides; ignored/enabled still control whether a finding is emitted.
    HH2001: error  # Require documented values paths when a failure threshold is enabled.
    HH2003: info  # Missing descriptions remain informational.
# Compiler budgets are positive integers; bytes, characters and counts are separate units.
compiler:
  max_call_depth: 16  # Nested helper/tpl calls.
  max_files: 10000  # Members inspected per chart archive, including directories.
  max_context_bytes: 67108864  # Packed/unpacked bytes per archive; retained native certificate records per prepared chart.
  max_template_bytes: 1048576  # UTF-8 bytes in each dynamically analyzed tpl source.
  max_steps: 10000  # Statements/iterations per root analysis; effect calls per render and retained crypto records per chart.
  max_discovery_nodes: 10000  # Actions per discovery traversal or nodes per helper projection.
  max_tpl_depth: 32  # Nested tpl expansions during value-path discovery.
  max_range_items: 4096  # Elements in a collection evaluated by a range.
  max_dependency_depth: 16  # Dependency nesting inspected from the root chart.
  max_dependencies: 512  # Dependency instances inspected per chart.
  max_version_chars: 4096  # Combined characters in a semantic-version constraint and version.
  max_string_chars: 16384  # Characters in a transformation operand or replacement result.
  max_regex_pattern_chars: 256  # Characters in an analyzed Go regex pattern.
  max_regex_subject_chars: 4096  # Characters in an analyzed Go regex subject.
  max_symbolic_variants: 64  # Alternatives at one destination-projection branch join.
  max_indent_width: 128  # Spaces in a projected indent/nindent operation.
  max_fragment_depth: 4  # Nested input containers checked for literal serialized YAML fragment constraints.
  max_proof_bytes: 16777216  # Chart bytes retained for an exact-pruning proof snapshot.
  max_output_nodes: 100000  # Manifest nodes inspected per complexity measurement.
  max_complexity_cases: 4096  # Template assignments and witnesses in a complexity search.
  max_complexity_seconds: 5  # Whole seconds allowed for a complexity search.
  max_lua_memory_bytes: 67108864  # Lua allocations per complexity analysis; exhaustion uses Python bounds.
  max_sampling_domain_values: 4096  # Values per factor when computing a sampling profile.
  max_fallbacks: 128  # Distinct incomplete-analysis diagnostics retained per chart.
  max_preimage_steps: 128  # Search steps when proposing inputs for a transformed allowlist.
  max_preimage_choices: 16  # Targets and proposals per transformed-allowlist search step.
  max_rejections: 64  # Distinct rejection contracts used to guide generation.
  max_repair_attempts: 48  # Candidate changes tried for a rejected configuration.
  max_repair_branch_attempts: 16  # Candidate changes tried at one repair search node.
  max_repair_depth: 3  # Successive changes considered along a repair search branch.
  max_repair_length: 16  # Largest proposed list length during rejection repair.
hypothesis:
  character_sets: ascii  # ascii or unicode; explicit enum/const literals retain their alphabet.
  control_characters:
    exclude: true  # Exclude U+0000-U+001F and U+007F-U+009F, including tabs and DEL.
    allow: ["\n", "\r"]  # Exceptions; [] excludes every control character.
  exclude_characters: ""  # Additional literal characters to exclude, e.g. ">|".
  renderer_policy: auto  # auto: controlled draws with native fallback; native: Helm only; strict: require replay.
  max_examples: 10  # Per path property, not a shared budget for a branch.
  deadline_ms: null  # No Hypothesis per-example deadline; chart/render timeouts still apply.
  phases: [generate, shrink]  # Use [generate] to omit shrinking.
  suppress_health_check: [too_slow]  # Use [] to retain all ordinary health checks.

input_constraints:
  - charts:
      # Every source/name pairing in this row is eligible. Patterns are case-sensitive.
      - sources:
          - https://github.com/example/charts.git
          - git@github.com:example/charts.git
          - ./charts
        names: [example, example-worker]
    path: $  # Whole chart; descendants inherit these partial overrides.
    findings:
      fail_on: error  # Override the global threshold for these charts.
      severity:
        HH2003: info  # Other code severities retain their inherited settings.
    compiler:  # Chart-wide budgets, including dependencies; only accepted with path: $.
      max_call_depth: 64  # Other limits inherit the global compiler settings.
      max_steps: 20000
    hypothesis:
      character_sets: ascii
      max_examples: 20

  - charts: [example]  # Chart.yaml names or glob patterns; any source.
    path: $.credentials
    ignored: [HH2001]  # Silence this code only within this branch.
    hypothesis:
      max_examples: 30
      deadline_ms: 5000

  - charts: [example]
    path: $.credentials.secretName
    profile: kubernetes-secret-name
    allow_empty: true  # Only if the chart's own schema also permits an empty string.
    enabled: [HH2001]  # More specific than the credentials suppression.

  - charts: [example]
    path: $.credentials.mountPath
    profile: absolute-posix-path  # Alternative to a self-contained inline schema.

  - charts: [example]
    path: $.containers[*].label
    findings:
      severity:
        HH2001: warning  # Override this branch only; fail_on still inherits.
    schema:
      type: string
      minLength: 1
      maxLength: 40
    hypothesis:
      character_sets: unicode
      control_characters:
        exclude: true
        allow: []
      exclude_characters: ">|"
      max_examples: 50
      phases: [generate]
      suppress_health_check: [too_slow, filter_too_much]

strict: false  # Require schemas for custom resources when true; otherwise skip those without a schema.
# Whole-resource JSON schemas, relative to this configuration file.
# Remove this entry until you supply the schema; it is required when present.
resource_schemas:
  example.org/v1/Widget: ./schemas/widget.json
```
<!-- [[[end]]] -->

### Inheritance and test budgets

All text-generation and example controls live under `hypothesis`, globally or within an `input_constraints` rule.
Top-level `character_sets`, `control_characters` and `exclude_characters` are not accepted.

Global settings are defaults. A rule's `path` applies to that branch and its descendants; the deepest matching rule wins
for each setting independently. For example, overriding `max_examples` retains the inherited deadline and phases.
Conflicting generation settings at equal path depth are configuration errors. Schema/profile restrictions intersect;
[finding controls](../rules/README.md#controls-for-individual-values-paths) have their own suppression rules.

Rules also accept `findings.fail_on` and `findings.severity`, using the same keys as the global `findings` section.
Unspecified settings and code severities inherit their values; deeper matching paths override them individually.
See [severity thresholds](../rules/README.md#severity-thresholds) for examples and multi-path behavior.

Compiler budgets follow the same global/chart split. Put `compiler:` beside `hypothesis:` in a rule with `path: $`.
Use `charts: [airflow, "redis*"]`, or the source/name matrix shown above, to select charts. Only specified budgets
override the global `compiler:` mapping. Every budget accepts a positive integer.
Compiler rules apply to a whole chart and its dependencies, so narrower values paths are rejected.
Matching rules may set different budgets, but conflicting values for the same budget are configuration errors.
Each chart resolves its settings independently before analysis; workers use those settings, and audit/test results
record them as `compiler_limits`. Config changes invalidate cached results.

`--max-examples` and `--character-sets` override global defaults, while branch rules remain more specific.
`hypothesis.max_examples` sets the number of successful generated examples **per selected path property**.
For example, three selected paths under a branch with `max_examples: 20` can run up to 60 successful examples.
Baseline renders, rejected candidates, failure reproduction and shrinking can add attempts.
Timeouts and `--fail` can end testing earlier. Whole-document sampling uses root settings.
Finite permutation plans and exhaustive enumeration retain their explicit cases; this setting does not truncate them.

`deadline_ms` is Hypothesis' per-example deadline, separate from Helm invocation and chart timeouts. It defaults to `null`
because render times vary across machines. `phases` accepts `generate` and optional `shrink`; `generate` is required.
`--fail` disables shrinking to stop on the first finding. `suppress_health_check` accepts Hypothesis health-check names:
`data_too_large`, `filter_too_much`, `too_slow`, `large_base_example`, `function_scoped_fixture`,
`differing_executors`, and `nested_given`. Normally only `too_slow` is suppressed.
When the compiler rejects inputs known to violate chart constraints, the runner also suppresses `filter_too_much`.

### Character exclusions

`hypothesis.control_characters.exclude: true` excludes U+0000 through U+001F and U+007F through U+009F. That includes tabs and DEL.
The default `allow: ["\n", "\r"]` permits multiline text. Set `allow: []` to exclude every control character, or add
`"\t"` to deliberately test tabs in a particular branch. `exclude: false` permits all controls in the selected alphabet.
`hypothesis.exclude_characters` is a literal string of additional exclusions, not a regex; it takes precedence over `allow`.
ASCII means U+0000 through U+007F before these exclusions. Unicode mode uses UTF-8 encodable characters.

These settings apply to fresh strings and map keys, including descendants generated together in an object or array.
They do not rewrite supplied chart defaults. Generated candidates still have to satisfy the chart's schema; a pattern
requiring only forbidden characters is unsatisfiable and is reported as a generation problem. Explicit finite enum/const
plans retain their declared cases. All generation settings are saved with suites and included in cache identities.

### Source and chart matrices

Each matrix row selects every pairing of its `sources` and `names`. Rows and simple name entries are alternatives.
For example, two sources and three names describe six eligible source/name pairs. They restrict which charts a rule
applies to; they do not initiate downloads or discover additional charts.

Names come from `Chart.yaml`. Sources match the original URL or Helm reference passed to `scan`, or the local source
passed to `test`, before temporary dependency preparation. Direct single-chart commands use the resolved chart directory.
Local source patterns starting with `./`, `../`, `/` or `~` resolve relative to the config file; use `./charts` for a
recursive local test rooted there, or `./charts/*` for individual chart directories. Source and name patterns use
case-sensitive shell glob syntax (`*`, `?`, `[abc]`). HTTPS and SSH URLs are distinct: list both if both should match.
Source identity is inherited by workers and retained in saved suites.

## Opaque objects: HH2006

An entry such as `"extraConfig": {"type": "object"}` permits arbitrary field names and values.
It gives the generator no structure to test against: `enabled` could be a Boolean, a string or another object.
The tool reports **HH2006: Opaque object schema** with the affected values path during audits and test planning.
This is a schema documentation gap, not proof of a chart bug.

Describe known fields with `properties`. For an intentional map of strings, use
`"additionalProperties": {"type": "string"}`; use `patternProperties` when key patterns describe the fields.
These declarations improve generated inputs without requiring every valid configuration to be enumerable.
An object with named fields does not trigger HH2006 merely because additional keys are allowed.

To silence this warning for intentional free-form configuration, add this to `.hypothesis-helm.yaml`:

```yaml
ignored:
  - HH2006  # Opaque object schema
```

The repository config and `helm hypothesis --generate-config` template already include this exclusion.
Remove or comment out that entry to enable the warning.
The equivalent CLI option is `--disable-codes HH2006` (or `--ignore HH2006`); multiple codes can be comma-delimited.
Suppression does not exclude these values from testing or make
their domains finite. Audits retain suppressed findings under `ignored_findings`; `--fail` treats an unsuppressed
HH2006 like other audit findings. See the [finding catalog](../rules/README.md#hh2006-opaque-object-schema).

When a repository test cannot enumerate its input domain, it samples generated values for each selected path instead.
Input filtering still applies, including when `--permutations N` was requested. The warning and report identify the fallback;
path sampling does not guarantee the requested N-way coverage. See [discovery and testing](../scanning/README.md#discovery-and-testing).

## Custom resources

Custom resources without a supplied JSON Schema skip schema validation by default. Rendering and basic manifest checks still run;
the resource is retained in streamed output. Supplied schemas are always checked, including without `--strict`.
A schema describing the values file is a different contract: it describes chart inputs, whereas a resource schema describes the rendered object.

Use `--strict` to report a missing custom-resource schema as `HH1108`. Use `--fail` as well to stop on the finding immediately.
The configuration equivalent is `strict: true`; `--no-strict` overrides it for a run.

```yaml
resource_schemas:
  example.org/v1/Widget: ./schemas/widget.json
```

Paths are relative to the configuration file. Supply a schema for the **whole rendered resource**, keyed by its exact
API version and kind. Extract the relevant version's `openAPIV3Schema` from a CRD if that is the source of its contract.
Only local JSON references are permitted; references are never downloaded implicitly.
The tool uses this schema for direct input mappings and validates the rendered custom resources against it.
When schema validation is enabled, it continues to validate built-in resources against its cached schemas.
JSON Schema checking does not execute CRD CEL rules, admission webhooks or controller logic.

Saved suites embed these schemas in `input-domains.json`, so `run` can validate custom resources even when
the original schema files are unavailable. An explicit current configuration overrides saved schemas for the same
API version and kind. Changes to the effective schema invalidate cached manifest validation.
Saved suites also record strictness. An explicit current `strict` setting overrides the saved setting; otherwise the saved setting applies.

The [CRD integration tests](../../pkg/hypothesis_helm/tests/schemas/test_custom_resources.py) use a
[pinned Polyad Gate chart fixture](../../pkg/hypothesis_helm/tests/fixtures/polyad-gate/README.md).
They run Helm's real helper and `tpl` rendering, check schema bounds and missing contracts, exercise generated
values and failure reports, and verify saved-suite reuse. Mixed-resource routing tests check that built-ins still
reach the Python schema validator against local fixture schemas. No cluster or neighboring checkout is required.

```sh
bash scripts/project-run.sh pytest pkg/hypothesis_helm/tests/schemas/test_custom_resources.py
```

## Coverage and reproducibility

Constraints intersect the chart's schema. They affect whole-document generation, individual path properties, generated suites,
finite plans and shrinking. Declared defaults and supplied values files are preserved and tested as the baseline.
A default outside the generation domain appears as a diagnostic rather than being silently replaced.
Clearly contradictory types, enum domains and bounds fail early; more complex unsatisfiable schemas can fail during generation.

Reports retain the input paths, destination fields, source templates, constraints and unresolved mappings.
Coverage refers to this restricted domain, even with `--exhaustive`; it does not include intentionally excluded inputs.
Workers inherit the same resolved policy, and cache identities include policy contents and catalog data.
Generated suites retain their generation constraints; regenerate a suite to remove an earlier restriction.

## Rebuilding the catalog before release

To populate the ignored local cache on a developer or end-user machine:

```sh
hypothesis-helm-catalog --cache-dir schemas
```

The [development setup script](../development.md#environment) installs the required Git and Go 1.25+ toolchain on Linux or macOS.
The command sparsely checks out pinned Kubernetes and JSON Schema revisions, compiles the Go extractor, and writes
`schemas/catalogs/1.35.0/input-domains.json`. Go module and build caches also live under `schemas/`.
After an initial online build, `--offline` requires cached sources, schemas and Go dependencies.

For release publication, explicitly update the bundled catalog, then verify it:

```sh
hypothesis-helm-catalog --output pkg/hypothesis_helm_catalog/data/input-domains.json
hypothesis-helm-catalog --check
```

`--schema-dir` selects an existing standalone-strict schema directory; `--kubernetes-source-dir` selects existing pinned sources.
Both paths are useful for offline rebuilds. `--go` selects a toolchain executable. The Go bindings are pinned to Kubernetes 1.35.0;
changing `--schema-version` alone cannot upgrade them. Ordinary API validation can use other published schema versions.
`--check` compares generated contents without rewriting either catalog. The tag-release workflow runs it before building distributions.

### Source verification and limits

The extractor reads Go syntax trees and accepts supported independent numeric and string-length annotations.
It resolves DNS naming patterns and port bounds from the pinned API machinery source and checks exported domains against the
actual compiled Go validators on deterministic boundary cases. The catalog records the corpus hash, source hashes, function
hashes, and unresolved annotations. These comparisons detect translation mistakes; they are not a proof that every Kubernetes
validation rule has been translated.

Exact API type/field bindings connect those primitives to destinations such as `ConfigMapVolumeSource.name`.
Reviewed supplements also bind to exact API types and fields, followed through OpenAPI references into each resource.
Descriptions are checked for upstream changes; identical wording on another field never copies a constraint there.
Service enum supplements are temporary schema shims: their records link both validation and defaulting sources,
explain the missing machine-readable enum, and state when to remove the shim. The
[README inventory](../../README.md#upstream-schema-shims) lists the current reviewed supplements.
For example, the `SecretKeySelector.name` rule does not restrict `imagePullSecrets[].name`.
Mount paths must be nonempty, but the catalog allows Windows drive letters such as `C:\data`; it does not infer a colon ban from the description.
No bound is inferred solely from a Helm values key's name. Conditional annotations, unsupported types, arbitrary Go validation
functions and state-dependent rules are not translated. A field with no supported bound remains unconstrained by this catalog;
users can add an explicit profile or schema.

Source inventories are checked against [kubernetes-source-lock.json](../../pkg/hypothesis_helm_catalog/data/kubernetes-source-lock.json).
Reviewed field supplements live in [reviewed-domains.json](../../pkg/hypothesis_helm_catalog/data/reviewed-domains.json).
Source changes require review; rebuilding does not invent replacements. Identical sources produce identical output without timestamps.

References: [Kubernetes declarative validation](https://kubernetes.io/docs/reference/using-api/declarative-validation/),
[API machinery validators](https://github.com/kubernetes/apimachinery/blob/v0.35.0/pkg/util/validation/validation.go), and
[core API validation](https://github.com/kubernetes/kubernetes/blob/v1.35.0/pkg/apis/core/validation/validation.go).
