# Chart findings and ignored checks

[Project](../../README.md) · [CLI reference](../cli/README.md)

Codes describe observed conditions across runs, independently of Python exceptions.
The catalog distinguishes **violations** (an input or output fails a checked contract), **warnings**
(missing values documentation or defaults), and **diagnostics** (execution or analysis could not establish a result).
A timeout, unresolved dynamic access or an unclassified Helm failure does not by itself establish a chart defect.
Even a violation can be intentional: a chart designed to render nothing can disable the nonempty-output check.
The report's `E001`, `E002`, etc. identify groups within one report and cannot be used to disable checks.

Copy [the repository configuration](../../.hypothesis-helm.yaml), which lists every code commented out, into your working directory.
Uncomment the checks you want to disable:

```yaml
ignored:
  - HH1008  # Duplicate resource identities
  - HH2003  # Missing schema descriptions
```

```bash
helm hypothesis rules
helm hypothesis rules --format config > .hypothesis-helm.yaml
helm hypothesis rules --format json > finding-catalog.json
helm hypothesis test ./charts --config .hypothesis-helm.yaml
helm hypothesis scan https://github.com/example/charts.git --ignore HH2003
```

`audit`, `generate`, `test`, `scan`, and `run` read `.hypothesis-helm.yaml` from the working directory by default.
`--config FILE` selects another file. Repeat `--ignore CODE` to add codes to the file's list.
Run generated suites through `helm hypothesis run` to apply this file; plain `pytest` does not load CLI configuration.
An empty or fully commented `ignored` list disables nothing. Unknown codes and configuration keys are errors.
Remote repositories cannot supply their own ignore policy: the policy is loaded locally before fetching charts.

## What ignoring changes

Disabled manifest checks allow the remaining checks to continue when the parsed output permits it.
Kubernetes schema checking and its schema preparation are not invoked when `HH1010` is disabled.
Codes select individual conditions, not an exception class or a family of errors. For example, ignoring `HH3001`
(missing object access) does not ignore `HH3002` (incompatible type). `HH1001` covers only unclassified template failures;
it does not suppress these specific findings or baseline lint (`HH1012`).
If Helm fails or produces unreadable output, ignoring that failure cannot create valid manifests: the affected candidate is excluded,
or the baseline/property is marked `ignored`/skipped when further checks cannot run. These cases do not become successful validation witnesses.
A generated Python property blocked by such a failure is skipped, including its remaining examples.
Audits keep ignored findings separately. Reports list disabled checks, and candidate reports count ignored blocking failures by code.
Passing means the enabled checks passed; it does not certify the disabled checks.

The resolved policy is inherited by workers and included in cache identities. Re-enabling a check forces fresh validation.
All shards must use the same policy. Ignore codes do not suppress configuration errors, missing executables, dependency preparation failures,
whole-run deadlines, interrupts, or assertions in user-written Python tests.
External tools such as kubesec retain their own rule systems; `DL` and `SC` codes are not hypothesis-helm codes.

## Shared finding library

[`findings/catalog.py`](../../pkg/hypothesis_helm/findings/catalog.py) stores each code's category, evidence criterion,
example and suggested action. [`FindingGenerator`](../../pkg/hypothesis_helm/findings/generator.py) creates structured
findings and generates the CLI listing, JSON catalog, commented configuration and reference below from those definitions.
Add a definition and a detector with regression tests when implementing a new check; a catalog entry alone does not detect anything.

Audits attach structured findings to values paths and template references. Test reports retain the classification,
diagnostic, triggering paths and values, and suggested action. Exceptions carry these findings where execution needs to stop;
they do not define the taxonomy. A template error, a manifest check and an audit can report findings through the same interface.

Specific Helm classifications require a recognized diagnostic. Unrecognized messages stay unclassified.
User-authored `fail`/`required` messages do not become type or missing-object findings just because they contain similar wording.
The existing input-rejection verification still decides which explicit configuration constraints can be filtered.
Likewise, an invalid manifest does not prove its cause was missing quotes: the catalog describes the observed failure,
with quoting offered only as something to investigate.

## Finding catalog

<!-- [[[cog
import cog
from hypothesis_helm.findings.generator import FindingGenerator
cog.out(FindingGenerator.render("markdown"))
]]] -->
| Code | Finding | Category | Kind |
| --- | --- | --- | --- |
| `HH1001` | Unclassified template failure | unclassified | diagnostic |
| `HH1002` | Render invocation timed out | execution | diagnostic |
| `HH1003` | Invalid YAML in rendered output | manifest | violation |
| `HH1004` | Manifest document is not an object | manifest | violation |
| `HH1005` | Missing resource API version or kind | manifest | violation |
| `HH1006` | Invalid resource list | manifest | violation |
| `HH1007` | Missing resource name | manifest | violation |
| `HH1008` | Duplicate resource identity | manifest | violation |
| `HH1009` | Empty resource bundle | manifest | violation |
| `HH1010` | Kubernetes schema validation failed | manifest | violation |
| `HH1011` | Rendered output cannot be encoded as JSON | unclassified | diagnostic |
| `HH1012` | Unclassified baseline lint failure | unclassified | diagnostic |
| `HH2001` | Undocumented values path | values | warning |
| `HH2002` | Unspecified values type | values | warning |
| `HH2003` | Missing values description | values | warning |
| `HH2004` | No supplied default for a values path | values | warning |
| `HH2005` | Unresolved template value access | analysis | diagnostic |
| `HH3001` | Template accesses a missing object | template | violation |
| `HH3002` | Incompatible value type in template | template | violation |
| `HH3003` | Undefined named template | template | violation |

### HH1001: Unclassified template failure

Detected when: Helm template exits unsuccessfully without a recognized diagnostic.

Example: A chart-specific fail message that has not been verified as an input constraint.

Suggested action: Inspect the Helm diagnostic and reproducer; the exit alone does not establish a chart defect.

### HH1002: Render invocation timed out

Detected when: The Helm subprocess exceeds its invocation deadline.

Example: A render takes longer than the configured timeout.

Suggested action: Check runner load and render cost, then adjust the timeout if appropriate. This is incomplete validation, not proof of a bug.

### HH1003: Invalid YAML in rendered output

Detected when: The YAML parser rejects rendered output, or Helm reports a YAML parse error.

Example: A substituted value breaks YAML indentation.

Suggested action: Inspect the failing YAML and template interpolation, including quoting and indentation.

### HH1004: Manifest document is not an object

Detected when: A nonempty rendered document is a scalar or sequence instead of a mapping.

Example: A template emits a bare string document.

Suggested action: Emit a resource mapping or remove the stray document.

### HH1005: Missing resource API version or kind

Detected when: A resource has no nonempty string apiVersion or kind.

Example: kind: null

Suggested action: Supply both resource identifiers in every branch that emits a resource.

### HH1006: Invalid resource list

Detected when: A resource with kind List has no array-valued items field.

Example: kind: List with items: null

Suggested action: Emit an items array, including an empty array when appropriate.

### HH1007: Missing resource name

Detected when: The resource fails the tool's nonempty metadata.name contract.

Example: metadata: {name: ""}

Suggested action: Provide a name in each resource branch; ignore this check if your workflow intentionally uses generated names.

### HH1008: Duplicate resource identity

Detected when: Two resources in the checked bundle share apiVersion, kind, namespace and name.

Example: Enabling an optional component emits a second ConfigMap with the same identity.

Suggested action: Give the resources distinct names or make their activation conditions exclusive.

### HH1009: Empty resource bundle

Detected when: The active test requires resources but this configuration renders none.

Example: All resource-producing branches are disabled.

Suggested action: Check resource activation; ignore this contract if an empty chart is intentional.

### HH1010: Kubernetes schema validation failed

Detected when: The configured Kubernetes validator rejects the output.

Example: An unquoted boolean becomes a non-string ConfigMap data value.

Suggested action: Use the validator's field path and expected type to check the template and input schema.

### HH1011: Rendered output cannot be encoded as JSON

Detected when: Manifest processing reports a JSON representation failure.

Example: A YAML tag produces an unsupported Python scalar object.

Suggested action: Inspect YAML tags and parser support. A serialization failure can be a tooling limitation rather than a chart defect.

### HH1012: Unclassified baseline lint failure

Detected when: Helm lint fails on the supplied chart defaults.

Example: Lint reports an error before generated inputs are tested.

Suggested action: Read the lint diagnostic; distinguish chart errors from missing dependencies or environment requirements.

### HH2001: Undocumented values path

Detected when: The audit finds a values path with no matching schema declaration.

Example: Templates read service.mode but its schema entry is absent.

Suggested action: Document the path in values.schema.json, including its accepted values.

### HH2002: Unspecified values type

Detected when: A schema path declares no type, enum or const.

Example: service.mode has only a description: "Service mode".

Suggested action: Declare the accepted type or a finite set of values.

### HH2003: Missing values description

Detected when: A typed schema path has no description.

Example: A boolean gate is declared without explaining which component it enables.

Suggested action: Describe the field's behavior and any requirements shared with other fields.

### HH2004: No supplied default for a values path

Detected when: A discovered path is absent from the original values file.

Example: A conditional branch reads credentials.token, which defaults omit.

Suggested action: Supply a default or document when users must provide the field. Absence alone does not prove rendering fails.

### HH2005: Unresolved template value access

Detected when: Static analysis cannot resolve a template's values access.

Example: An index expression selects a key computed at runtime.

Suggested action: Review the dynamic access and coverage report; unresolved analysis is not a chart defect.

### HH3001: Template accesses a missing object

Detected when: Helm reports a nil pointer while evaluating a template field.

Example: A template reads .Values.service.port when service is absent.

Suggested action: Guard or default the parent object, or require it in the values schema.

### HH3002: Incompatible value type in template

Detected when: Helm reports a wrong value type, a field unavailable on a type, or an unsupported range operand.

Example: A string-only template function receives a boolean allowed by the input schema.

Suggested action: Align the template operation with the accepted input types, or narrow the schema.

### HH3003: Undefined named template

Detected when: Helm reports that a called named template is not defined.

Example: include "service.name" . refers to an absent helper.

Suggested action: Check the helper name, its definition and dependency availability.
<!-- [[[end]]] -->
