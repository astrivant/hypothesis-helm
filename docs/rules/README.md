# Check codes and ignored checks

[Project](../../README.md) · [CLI reference](../cli/README.md)

Every built-in check below has a stable code. These codes identify kinds of findings across runs.
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
Helm lint and template execution are independent checks: disabling `HH1001` does not disable baseline lint (`HH1012`).
If Helm fails or produces unreadable output, ignoring that failure cannot create valid manifests: the affected candidate is excluded,
or the baseline/property is marked `ignored`/skipped when further checks cannot run. These cases do not become successful validation witnesses.
A generated Python property blocked by such a failure is skipped, including its remaining examples.
Audits keep ignored findings separately. Reports list disabled checks, and candidate reports count ignored blocking failures by code.
Passing means the enabled checks passed; it does not certify the disabled checks.

The resolved policy is inherited by workers and included in cache identities. Re-enabling a check forces fresh validation.
All shards must use the same policy. Ignore codes do not suppress configuration errors, missing executables, dependency preparation failures,
whole-run deadlines, interrupts, or assertions in user-written Python tests.
External tools such as kubesec retain their own rule systems; `DL` and `SC` codes are not hypothesis-helm codes.

## Built-in checks

| Code | Check |
| --- | --- |
| `HH1001` | Helm template execution failed |
| `HH1002` | Helm render exceeded its invocation timeout |
| `HH1003` | Rendered YAML cannot be parsed |
| `HH1004` | Rendered document is not an object |
| `HH1005` | Resource lacks a nonempty apiVersion or kind |
| `HH1006` | List resource lacks an items array |
| `HH1007` | Resource lacks a nonempty metadata.name |
| `HH1008` | Duplicate resource identity in a manifest bundle |
| `HH1009` | Chart renders no resources |
| `HH1010` | Kubernetes API schema validation failed |
| `HH1011` | Rendered manifest cannot be represented as JSON |
| `HH1012` | Helm lint failed on the chart defaults |
| `HH2001` | Values path is undocumented in the schema |
| `HH2002` | Values path has no declared type, enum or constant |
| `HH2003` | Values path has no schema description |
| `HH2004` | Values path has no supplied default |
| `HH2005` | Template value access cannot be resolved statically |
