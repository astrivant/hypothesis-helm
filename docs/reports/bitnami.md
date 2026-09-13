# Bitnami Helm chart scan

Visited all **115 discovered charts** with **--filter**, four workers, and a **five-minute test budget per chart**. No scan-wide deadline
was imposed.

Recorded **101,799 test attempts** in **144.8 minutes**. Attempts include shrinking and repeated inputs; they are not counts of unique
inputs or confirmed bugs.

**Findings:** 92 failed; 1 skipped-library; 22 time-limit.

**value-path:** 272 failed; 1022 passed; 111 time-limit.

Observed failures include chart validation rejections, rendering failures, and possible tooling limitations. Inferred inputs are not an
authoritative chart contract. Findings need triage before being called chart defects; time-limited coverage remains incomplete.

Checks: dependency build in isolated copies, Helm lint, Helm template with values-schema checks, and built-in manifest checks. External
kubeconform/kubesec validation was not configured.

Source: `third_party/bitnami-charts` at `6a8cccf3c29a1faabf0c34c8276a09ed14f3c5b3`; Helm 4.3.0. Per-worker dependency caches are isolated.
Each primary chart has one dedicated job; nested results from parent jobs are retained separately and excluded from totals.

[Combined PDF](<https://github.com/astrivant/hypothesis-helm/blob/main/docs/reports/bitnami.pdf>) ·
[Aggregate data](<https://github.com/astrivant/hypothesis-helm/blob/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/scan.json.gz>)
·
[Raw logs and provenance](<https://github.com/astrivant/hypothesis-helm/blob/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/README.md>)

Generated C0/C1 controls are excluded except LF and CR. Other Unicode text remains eligible; explicit finite domains are unchanged.
Dependency preparation is excluded from chart testing budgets.

Directory: third_party/bitnami-charts
Started (Unix epoch): 1789316790
Elapsed (wall clock): 8687.00 seconds
Chart testing: 33730.96 seconds
Dependency preparation: 93.28 seconds (excluded from testing budgets)
Charts discovered: 115
Scan status: completed
Discovery complete: True
Unstarted charts: 0

Results describe the tested sample; they do not prove chart correctness.
Baseline-only, skipped, blocked, and incomplete charts are not property-test passes.

## Status counts

92 failed; 1 skipped-library; 22 time-limit.

## Settings

Filtering: True | Seed: 0 | Traversal: random
Chart timeout: 300.0 seconds | Workers: 4
Complete settings are retained in the JSON report.

## Errors

244 distinct diagnostics across 274 occurrences; 30 repeats grouped.
Diagnostics and their triggering inputs are grouped under each chart below.
Up to two examples per diagnostic and six fields per example are shown. Long values and diagnostics are shortened.
Full inputs, diagnostics, and remaining cases are retained in JSON and linked artifacts.
Selected fields identify what the test varied, not an independently proven cause.

## Charts

### bitnami/airflow

Status: time-limit | Attempts: 264

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/airflow_1789316791/0000>)

### bitnami/apache

Status: failed | Attempts: 1425

#### E001

```text
Error: YAML parse error on apache/templates/deployment.yaml: error converting YAML to JSON: yaml: line 178: found an indentation indicator
equal to 0
```

Phase: $.htdocsConfigMap | Status: failed

Selected fields (full context in artifacts):
- `$.htdocsConfigMap = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/apache_1789316791/0000/paths/a84b1abe3a11000d364a>)

#### E002

```text
Error: YAML parse error on apache/templates/deployment.yaml: error converting YAML to JSON: yaml: line 31: did not find expected ',' or ']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/apache_1789316791/0000/paths/a4a0ea6ab697189bb963>)

#### E003

```text
Error: YAML parse error on apache/templates/deployment.yaml: error converting YAML to JSON: yaml: line 62: mapping values are not allowed in
this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/apache_1789316791/0000/paths/8e79b7dd85a286cfaddb>)

#### E004

```text
Error: YAML parse error on apache/templates/pdb.yaml: error converting YAML to JSON: yaml: line 13: found an indentation indicator equal to
0
```

Phase: $.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/apache_1789316791/0000/paths/d6baed3b8998a068f471>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/apache_1789316791/0000>)

### bitnami/apisix

Status: failed | Attempts: 77

#### E005

```text
Error: YAML parse error on apisix/templates/control-plane/dep-ds.yaml: error converting YAML to JSON: yaml: line 329: found an indentation
indicator equal to 0
```

Phase: $.controlPlane.extraConfigExistingConfigMap | Status: failed

Selected fields (full context in artifacts):
- `$.controlPlane.extraConfigExistingConfigMap = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/apisix_1789316791/0000/paths/98c9de7170b4f8fa32cd>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/apisix_1789316791/0000>)

### bitnami/appsmith

Status: failed | Attempts: 415

#### E006

```text
Error: YAML parse error on appsmith/templates/backend/pdb.yaml: error converting YAML to JSON: yaml: line 14: found an indentation indicator
equal to 0
```

Phase: $.backend.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.backend.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/appsmith_1789316791/0000/paths/e5a7721b8b6a3e96d7c0>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/appsmith_1789316791/0000>)

### bitnami/argo-cd

Status: failed | Attempts: 254

#### E215

```text
Error: argo-cd/templates/server/ingress-grcp.yaml:41:15 executing "argo-cd/templates/server/ingress-grcp.yaml" at <.name>: nil pointer
evaluating interface {}.name
```

Phase: $.server.ingressGrpc | Status: failed

Selected fields (full context in artifacts):
- `$.server.ingressGrpc = {"enabled": true, "extraHosts": [null]}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/argo-cd_1789317093/0000/paths/13e1a098996e33c7f121>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/argo-cd_1789317093/0000>)

### bitnami/argo-workflows

Status: failed | Attempts: 609

#### E007

```text
Error: YAML parse error on argo-workflows/templates/controller/clusterrolebinding.yaml: error converting YAML to JSON: yaml: line 23: did
not find expected node content
```

Phase: $.controller.workflowNamespaces[*] | Status: failed

Selected fields (full context in artifacts):
- No supplied value at the selected paths.
Absent from overrides: $.controller.workflowNamespaces["*"]. Defaults may still apply.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/argo-workflows_1789317094/0000/paths/d21976126c873fdee7bc>)

#### E008

```text
Error: YAML parse error on argo-workflows/templates/controller/workflow-serviceaccount.yaml: error unmarshaling JSON: while decoding JSON:
json: cannot unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.workflows.serviceAccount | Status: failed

Selected fields (full context in artifacts):
- `$.workflows.serviceAccount = {"annotations": {"": []}}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/argo-workflows_1789317094/0000/paths/c246ccf3c22f11e34d43>)

#### E222

Source: argo-workflows 13.0.7 / templates/NOTES.txt

```text
[Diagnostic shortened; full text in artifacts] ... kely to cause degraded security and performance, broken chart features, and missing
environment variables. Unrecognized images: - 0/bitnami/argo-workflow-exec:3.7.1-debian-12-r1 If you are sure you want to proceed with
non-standard containers, you can skip container image verification by setting the global parameter 'global.security.allowInsecureImages' to
true. Further information can be obtained at https://github.com/bitnami/charts/issues/30850
```

Phase: $.executor.image.registry | Status: failed

Selected fields (full context in artifacts):
- `$.executor.image.registry = "0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/argo-workflows_1789317094/0000/paths/07b681bcf5ce22fbc17d>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/argo-workflows_1789317094/0000>)

### bitnami/aspnet-core

Status: failed | Attempts: 1420

#### E009

```text
Error: YAML parse error on aspnet-core/templates/deployment.yaml: error converting YAML to JSON: yaml: line 29: did not find expected ',' or
']'
```

Phase: $.appFromExternalRepo.clone.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.appFromExternalRepo.clone.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/aspnet-core_1789317096/0000/paths/5a7bb70f23ca77d7dde5>)

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/aspnet-core_1789317096/0000/paths/a4a0ea6ab697189bb963>)

#### E010

```text
Error: YAML parse error on aspnet-core/templates/deployment.yaml: error converting YAML to JSON: yaml: line 66: mapping values are not
allowed in this context
```

Phase: $.appFromExternalRepo.publish.image.tag | Status: failed

Selected fields (full context in artifacts):
- `$.appFromExternalRepo.publish.image.tag = ""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/aspnet-core_1789317096/0000/paths/6f16a3fce30f040bbbba>)

#### E011

```text
Error: YAML parse error on aspnet-core/templates/deployment.yaml: error converting YAML to JSON: yaml: line 83: mapping values are not
allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/aspnet-core_1789317096/0000/paths/8e79b7dd85a286cfaddb>)

#### E012

```text
Error: YAML parse error on aspnet-core/templates/pdb.yaml: error converting YAML to JSON: yaml: line 13: found an indentation indicator
equal to 0
```

Phase: $.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/aspnet-core_1789317096/0000/paths/d6baed3b8998a068f471>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/aspnet-core_1789317096/0000>)

### bitnami/cadvisor

Status: failed | Attempts: 1614

#### E013

```text
Error: YAML parse error on cadvisor/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 35: did not find expected ',' or ']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/cadvisor_1789317099/0000/paths/a4a0ea6ab697189bb963>)

Phase: $.global.imagePullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.global.imagePullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/cadvisor_1789317099/0000/paths/097f6358a00dddbcdd83>)

1 additional occurrences are retained in the JSON report and chart artifacts.

#### E014

```text
Error: YAML parse error on cadvisor/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 60: mapping values are not allowed
in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/cadvisor_1789317099/0000/paths/8e79b7dd85a286cfaddb>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/cadvisor_1789317099/0000>)

### bitnami/cassandra

Status: failed | Attempts: 1261

#### E015

```text
Error: YAML parse error on cassandra/templates/pdb.yaml: error converting YAML to JSON: yaml: line 13: found an indentation indicator equal
to 0
```

Phase: $.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/cassandra_1789317398/0000/paths/d6baed3b8998a068f471>)

#### E016

```text
Error: YAML parse error on cassandra/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 203: found an indentation
indicator equal to 0
```

Phase: $.persistence.existingClaim | Status: failed

Selected fields (full context in artifacts):
- `$.persistence.existingClaim = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/cassandra_1789317398/0000/paths/bc81b51736a9cdc4eda3>)

#### E017

```text
Error: YAML parse error on cassandra/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 205: found an indentation
indicator equal to 0
```

Phase: $.initDBSecret | Status: failed

Selected fields (full context in artifacts):
- `$.initDBSecret = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/cassandra_1789317398/0000/paths/54a61259d47f0b2947b0>)

#### E018

```text
Error: YAML parse error on cassandra/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 31: did not find expected ',' or
']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/cassandra_1789317398/0000/paths/a4a0ea6ab697189bb963>)

#### E019

```text
Error: YAML parse error on cassandra/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 68: mapping values are not
allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/cassandra_1789317398/0000/paths/8e79b7dd85a286cfaddb>)

#### E223

Source: cassandra 12.3.13 / templates/NOTES.txt

```text
execution error at (cassandra/templates/NOTES.txt:95:4): VALUES VALIDATION: cassandra: tls.enabled In order to enable TLS, you also need to
provide an existing secret containing the Keystore and Truststore or enable auto-generated certificates.
```

Phase: $.tls.internodeEncryption | Status: failed

Selected fields (full context in artifacts):
- `$.tls.internodeEncryption = ""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/cassandra_1789317398/0000/paths/6304a8bdd493268fe082>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/cassandra_1789317398/0000>)

### bitnami/cert-manager

Status: failed | Attempts: 620

#### E020

```text
Error: YAML parse error on cert-manager/templates/cainjector/deployment.yaml: error converting YAML to JSON: yaml: line 86: found an
indentation indicator equal to 0
```

Phase: $.cainjector.extraEnvVarsSecret | Status: failed

Selected fields (full context in artifacts):
- `$.cainjector.extraEnvVarsSecret = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/cert-manager_1789317398/0000/paths/a191661e18fe43471e4f>)

#### E021

```text
Error: YAML parse error on cert-manager/templates/controller/deployment.yaml: error converting YAML to JSON: yaml: line 43: found an
indentation indicator equal to 0
```

Phase: $.controller.runtimeClassName | Status: failed

Selected fields (full context in artifacts):
- `$.controller.runtimeClassName = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/cert-manager_1789317398/0000/paths/f82d28e2c30ee5985d85>)

#### E224

Source: cert-manager 1.5.15 / templates/NOTES.txt

```text
[Diagnostic shortened; full text in artifacts] ... containers is likely to cause degraded security and performance, broken chart features,
and missing environment variables. Unrecognized images: - docker.io/0:1.18.2-debian-12-r5 If you are sure you want to proceed with
non-standard containers, you can skip container image verification by setting the global parameter 'global.security.allowInsecureImages' to
true. Further information can be obtained at https://github.com/bitnami/charts/issues/30850
```

Phase: $.webhook.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.webhook.image.repository = "0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/cert-manager_1789317398/0000/paths/029ae7dbec2e908f49af>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/cert-manager_1789317398/0000>)

### bitnami/chainloop

Status: failed | Attempts: 385

#### E022

```text
Error: YAML parse error on chainloop/templates/controlplane/deployment.yaml: error converting YAML to JSON: yaml: line 60: found an
indentation indicator equal to 0
```

Phase: $.controlplane.terminationGracePeriodSeconds | Status: failed

Selected fields (full context in artifacts):
- `$.controlplane.terminationGracePeriodSeconds = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/chainloop_1789317399/0000/paths/94d51abc8b5003c3268d>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/chainloop_1789317399/0000>)

### bitnami/cilium

Status: time-limit | Attempts: 209

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/cilium_1789317401/0000>)

### bitnami/clickhouse

Status: failed | Attempts: 710

#### E026

```text
Error: YAML parse error on clickhouse/templates/usersd-configmap.yaml: error converting YAML to JSON: yaml: line 14: did not find expected
key
```

Phase: $.usersdFiles | Status: failed

Selected fields (full context in artifacts):
- `$.usersdFiles = {"": null}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/clickhouse_1789317700/0000/paths/638458d117473394e4a1>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/clickhouse_1789317700/0000>)

### bitnami/clickhouse-operator

Status: failed | Attempts: 1176

#### E023

```text
Error: YAML parse error on clickhouse-operator/templates/deployment.yaml: error converting YAML to JSON: yaml: line 44: block sequence
entries are not allowed in this context
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[null]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/clickhouse-operator_1789317700/0000/paths/a4a0ea6ab697189bb963>)

#### E024

```text
Error: YAML parse error on clickhouse-operator/templates/deployment.yaml: error converting YAML to JSON: yaml: line 68: mapping values are
not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/clickhouse-operator_1789317700/0000/paths/8e79b7dd85a286cfaddb>)

#### E025

```text
Error: YAML parse error on clickhouse-operator/templates/pdb.yaml: error converting YAML to JSON: yaml: line 15: found an indentation
indicator equal to 0
```

Phase: $.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/clickhouse-operator_1789317700/0000/paths/d6baed3b8998a068f471>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/clickhouse-operator_1789317700/0000>)

### bitnami/cloudnative-pg

Status: failed | Attempts: 442

#### E027

```text
Error: YAML parse error on cloudnative-pg/templates/plugin-barman-cloud/deployment.yaml: error converting YAML to JSON: yaml: line 138:
could not find expected ':'
```

Phase: $.pluginBarmanCloud.tls | Status: failed

Selected fields (full context in artifacts):
- `$.pluginBarmanCloud.tls = {"client": {"existingSecret": "\r0"}}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/cloudnative-pg_1789317702/0000/paths/42dca26bb7a7f8513cb0>)

#### E028

```text
Error: YAML parse error on cloudnative-pg/templates/plugin-barman-cloud/pdb.yaml: error converting YAML to JSON: yaml: line 15: found an
indentation indicator equal to 0
```

Phase: $.pluginBarmanCloud.pdb.minAvailable | Status: failed

Selected fields (full context in artifacts):
- `$.pluginBarmanCloud.pdb.minAvailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/cloudnative-pg_1789317702/0000/paths/c1ae5beb143c567fc7e6>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/cloudnative-pg_1789317702/0000>)

### bitnami/common

Status: skipped-library | Attempts: N/A

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/common_1789317705/0000>)

### bitnami/concourse

Status: failed | Attempts: 728

#### E029

```text
Error: YAML parse error on concourse/charts/postgresql/templates/primary/statefulset.yaml: error converting YAML to JSON: yaml: line 171:
found an indentation indicator equal to 0
```

Phase: $.postgresql.auth.existingSecret | Status: failed

Selected fields (full context in artifacts):
- `$.postgresql.auth.existingSecret = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/concourse_1789317706/0000/paths/a0cdb2ba618083d9a8df>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/concourse_1789317706/0000>)

### bitnami/consul

Status: failed | Attempts: 1456

#### E030

```text
Error: YAML parse error on consul/templates/pdb.yaml: error converting YAML to JSON: yaml: line 13: found an indentation indicator equal to
0
```

Phase: $.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/consul_1789318003/0000/paths/d6baed3b8998a068f471>)

#### E031

```text
Error: YAML parse error on consul/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 31: did not find expected ',' or ']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/consul_1789318003/0000/paths/a4a0ea6ab697189bb963>)

#### E032

```text
Error: YAML parse error on consul/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 55: mapping values are not allowed
in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/consul_1789318003/0000/paths/8e79b7dd85a286cfaddb>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/consul_1789318003/0000>)

### bitnami/contour

Status: time-limit | Attempts: 199

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/contour_1789318003/0000>)

### bitnami/deepspeed

Status: failed | Attempts: 95

#### E033

```text
Error: YAML parse error on deepspeed/templates/worker/pdb.yaml: error converting YAML to JSON: yaml: line 15: found an indentation indicator
equal to 0
```

Phase: $.worker.pdb | Status: failed

Selected fields (full context in artifacts):
- `$.worker.pdb = {"maxUnavailable": ">0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/deepspeed_1789318005/0000/paths/7b3233b72c7ae2177a76>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/deepspeed_1789318005/0000>)

### bitnami/discourse

Status: failed | Attempts: 793

#### E034

```text
Error: YAML parse error on discourse/charts/postgresql/templates/primary/statefulset.yaml: error converting YAML to JSON: yaml: line 173:
found an indentation indicator equal to 0
```

Phase: $.postgresql.auth.existingSecret | Status: failed

Selected fields (full context in artifacts):
- `$.postgresql.auth.existingSecret = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/discourse_1789318008/0000/paths/a0cdb2ba618083d9a8df>)

#### E035

```text
Error: YAML parse error on discourse/templates/deployment.yaml: error converting YAML to JSON: yaml: line 231: found an indentation
indicator equal to 0
```

Phase: $.persistence.existingClaim | Status: failed

Selected fields (full context in artifacts):
- `$.persistence.existingClaim = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/discourse_1789318008/0000/paths/bc81b51736a9cdc4eda3>)

#### E036

```text
Error: YAML parse error on discourse/templates/deployment.yaml: error converting YAML to JSON: yaml: line 60: mapping values are not allowed
in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/discourse_1789318008/0000/paths/8e79b7dd85a286cfaddb>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/discourse_1789318008/0000>)

### bitnami/dremio

Status: failed | Attempts: 288

#### E037

```text
Error: YAML parse error on dremio/templates/bootstrap-user/job.yaml: error converting YAML to JSON: yaml: line 121: did not find expected
key
```

Phase: $.dremio.auth.username | Status: failed

Selected fields (full context in artifacts):
- `$.dremio.auth.username = "\n"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/dremio_1789318305/0000/paths/7e3ba2e9db7688fe1f85>)

#### E038

```text
Error: YAML parse error on dremio/templates/bootstrap-user/job.yaml: error converting YAML to JSON: yaml: line 143: found an indentation
indicator equal to 0
```

Phase: $.bootstrapUserJob.extraEnvVarsCM | Status: failed

Selected fields (full context in artifacts):
- `$.bootstrapUserJob.extraEnvVarsCM = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/dremio_1789318305/0000/paths/5e487f511969b2a6049b>)

#### E225

Source: dremio 3.1.0 / templates/NOTES.txt

```text
[Diagnostic shortened; full text in artifacts] ... ners is likely to cause degraded security and performance, broken chart features, and
missing environment variables. Unrecognized images: - 00/bitnami/dremio:26.0.0-debian-12-r5 If you are sure you want to proceed with
non-standard containers, you can skip container image verification by setting the global parameter 'global.security.allowInsecureImages' to
true. Further information can be obtained at https://github.com/bitnami/charts/issues/30850
```

Phase: $.dremio.image.registry | Status: failed

Selected fields (full context in artifacts):
- `$.dremio.image.registry = "00"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/dremio_1789318305/0000/paths/c5408860d7e66fba867d>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/dremio_1789318305/0000>)

### bitnami/drupal

Status: failed | Attempts: 1009

#### E039

```text
Error: YAML parse error on drupal/templates/deployment.yaml: error converting YAML to JSON: yaml: line 227: found an indentation indicator
equal to 0
```

Phase: $.persistence.existingClaim | Status: failed

Selected fields (full context in artifacts):
- `$.persistence.existingClaim = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/drupal_1789318305/0000/paths/bc81b51736a9cdc4eda3>)

#### E040

```text
Error: YAML parse error on drupal/templates/deployment.yaml: error converting YAML to JSON: yaml: line 29: did not find expected ',' or ']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/drupal_1789318305/0000/paths/a4a0ea6ab697189bb963>)

#### E041

```text
Error: YAML parse error on drupal/templates/deployment.yaml: error converting YAML to JSON: yaml: line 60: mapping values are not allowed in
this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/drupal_1789318305/0000/paths/8e79b7dd85a286cfaddb>)

#### E231

Source: mariadb 22.0.0 / templates/NOTES.txt

```text
execution error at (mariadb/templates/NOTES.txt:74:4): VALUES VALIDATION: mariadb: architecture Invalid architecture selected. Valid values
are "standalone" and "replication". Please set a valid architecture (--set architecture="xxxx")
```

Phase: $.mariadb.architecture | Status: failed

Selected fields (full context in artifacts):
- `$.mariadb.architecture = ""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/drupal_1789318305/0000/paths/1ff74c0fd3bc5bc52c04>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/drupal_1789318305/0000>)

### bitnami/ejbca

Status: failed | Attempts: 1165

#### E042

```text
Error: YAML parse error on ejbca/templates/deployment.yaml: error converting YAML to JSON: yaml: line 206: found an indentation indicator
equal to 0
```

Phase: $.persistence.existingClaim | Status: failed

Selected fields (full context in artifacts):
- `$.persistence.existingClaim = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/ejbca_1789318311/0000/paths/bc81b51736a9cdc4eda3>)

#### E043

```text
Error: YAML parse error on ejbca/templates/deployment.yaml: error converting YAML to JSON: yaml: line 31: did not find expected ',' or ']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/ejbca_1789318311/0000/paths/a4a0ea6ab697189bb963>)

#### E044

```text
Error: YAML parse error on ejbca/templates/deployment.yaml: error converting YAML to JSON: yaml: line 69: mapping values are not allowed in
this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/ejbca_1789318311/0000/paths/8e79b7dd85a286cfaddb>)

#### E231

Source: mariadb 22.0.0 / templates/NOTES.txt

```text
execution error at (mariadb/templates/NOTES.txt:74:4): VALUES VALIDATION: mariadb: architecture Invalid architecture selected. Valid values
are "standalone" and "replication". Please set a valid architecture (--set architecture="xxxx")
```

Phase: $.mariadb.architecture | Status: failed

Selected fields (full context in artifacts):
- `$.mariadb.architecture = ""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/ejbca_1789318311/0000/paths/1ff74c0fd3bc5bc52c04>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/ejbca_1789318311/0000>)

### bitnami/elasticsearch

Status: time-limit | Attempts: 480

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/elasticsearch_1789318311/0000>)

### bitnami/envoy-gateway

Status: failed | Attempts: 217

#### E244

```text
resource has no metadata.name
```

Phase: $.certgen.serviceAccount.name | Status: failed

Selected fields (full context in artifacts):
- `$.certgen.serviceAccount.name = "0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/envoy-gateway_1789318608/0000/paths/3bafd983ae0b309b29cf>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/envoy-gateway_1789318608/0000>)

### bitnami/etcd

Status: time-limit | Attempts: 94

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/etcd_1789318609/0000>)

### bitnami/external-dns

Status: failed | Attempts: 1102

#### E045

```text
Error: YAML parse error on external-dns/templates/deployment.yaml: error converting YAML to JSON: yaml: line 52: mapping values are not
allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/external-dns_1789318613/0000/paths/8e79b7dd85a286cfaddb>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/external-dns_1789318613/0000>)

### bitnami/flink

Status: failed | Attempts: 1081

#### E046

```text
Error: YAML parse error on flink/templates/jobmanager/deployment.yaml: error converting YAML to JSON: yaml: line 62: mapping values are not
allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/flink_1789318615/0000/paths/8e79b7dd85a286cfaddb>)

#### E047

```text
Error: YAML parse error on flink/templates/taskmanager/pdb.yaml: error converting YAML to JSON: yaml: line 15: found an indentation
indicator equal to 0
```

Phase: $.taskmanager.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.taskmanager.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/flink_1789318615/0000/paths/3caeb4e538f52bc2b5ff>)

#### E048

```text
Error: YAML parse error on flink/templates/taskmanager/serviceaccount.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.taskmanager.serviceAccount | Status: failed

Selected fields (full context in artifacts):
- `$.taskmanager.serviceAccount = {"annotations": {"": []}}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/flink_1789318615/0000/paths/067a3a5b55160a73e780>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/flink_1789318615/0000>)

### bitnami/fluent-bit

Status: failed | Attempts: 1292

#### E049

```text
Error: YAML parse error on fluent-bit/templates/configmap.yaml: error converting YAML to JSON: yaml: line 17: could not find expected ':'
```

Phase: $.config.customParsers | Status: failed

Selected fields (full context in artifacts):
- `$.config.customParsers = "\r0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/fluent-bit_1789318911/0000/paths/895be26e57dfa94767ec>)

#### E050

```text
Error: YAML parse error on fluent-bit/templates/deployment.yaml: error converting YAML to JSON: yaml: line 35: block sequence entries are
not allowed in this context
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[null]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/fluent-bit_1789318911/0000/paths/a4a0ea6ab697189bb963>)

#### E051

```text
Error: YAML parse error on fluent-bit/templates/deployment.yaml: error converting YAML to JSON: yaml: line 60: mapping values are not
allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/fluent-bit_1789318911/0000/paths/8e79b7dd85a286cfaddb>)

#### E052

```text
Error: YAML parse error on fluent-bit/templates/pdb.yaml: error converting YAML to JSON: yaml: line 14: found an indentation indicator equal
to 0
```

Phase: $.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/fluent-bit_1789318911/0000/paths/d6baed3b8998a068f471>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/fluent-bit_1789318911/0000>)

### bitnami/fluentd

Status: failed | Attempts: 645

#### E053

```text
Error: YAML parse error on fluentd/templates/forwarder-daemonset.yaml: error converting YAML to JSON: yaml: line 125: found an indentation
indicator equal to 0
```

Phase: $.forwarder.livenessProbe.tcpSocket.port | Status: failed

Selected fields (full context in artifacts):
- `$.forwarder.livenessProbe.tcpSocket.port = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/fluentd_1789318914/0000/paths/25b567cc42066c51ab36>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/fluentd_1789318914/0000>)

### bitnami/flux

Status: time-limit | Attempts: 107

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/flux_1789318915/0000>)

### bitnami/ghost

Status: failed | Attempts: 1103

#### E226

Source: ghost 25.0.5 / templates/NOTES.txt

```text
[Diagnostic shortened; full text in artifacts] ... ainers is likely to cause degraded security and performance, broken chart features, and
missing environment variables. Unrecognized images: - 00/bitnami/ghost:6.0.5-debian-12-r0 If you are sure you want to proceed with
non-standard containers, you can skip container image verification by setting the global parameter 'global.security.allowInsecureImages' to
true. Further information can be obtained at https://github.com/bitnami/charts/issues/30850
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"registry": "00"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/ghost_1789318917/0000/paths/8e79b7dd85a286cfaddb>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/ghost_1789318917/0000>)

### bitnami/gitea

Status: failed | Attempts: 1163

#### E054

```text
Error: YAML parse error on gitea/charts/postgresql/templates/primary/statefulset.yaml: error converting YAML to JSON: yaml: line 173: found
an indentation indicator equal to 0
```

Phase: $.postgresql.auth.existingSecret | Status: failed

Selected fields (full context in artifacts):
- `$.postgresql.auth.existingSecret = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/gitea_1789319420/0000/paths/a0cdb2ba618083d9a8df>)

#### E055

```text
Error: YAML parse error on gitea/templates/deployment.yaml: error converting YAML to JSON: yaml: line 201: found an indentation indicator
equal to 0
```

Phase: $.persistence.existingClaim | Status: failed

Selected fields (full context in artifacts):
- `$.persistence.existingClaim = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/gitea_1789319420/0000/paths/bc81b51736a9cdc4eda3>)

#### E056

```text
Error: YAML parse error on gitea/templates/deployment.yaml: error converting YAML to JSON: yaml: line 202: found an indentation indicator
equal to 0
```

Phase: $.smtpExistingSecret | Status: failed

Selected fields (full context in artifacts):
- `$.smtpExistingSecret = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/gitea_1789319420/0000/paths/5787f0eface5fec9a681>)

#### E057

```text
Error: YAML parse error on gitea/templates/deployment.yaml: error converting YAML to JSON: yaml: line 29: did not find expected ',' or ']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/gitea_1789319420/0000/paths/a4a0ea6ab697189bb963>)

#### E058

```text
Error: YAML parse error on gitea/templates/deployment.yaml: error converting YAML to JSON: yaml: line 54: mapping values are not allowed in
this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/gitea_1789319420/0000/paths/8e79b7dd85a286cfaddb>)

#### E059

```text
Error: YAML parse error on gitea/templates/pdb.yaml: error converting YAML to JSON: yaml: line 13: found an indentation indicator equal to 0
```

Phase: $.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/gitea_1789319420/0000/paths/d6baed3b8998a068f471>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/gitea_1789319420/0000>)

### bitnami/gitlab-runner

Status: failed | Attempts: 1310

#### E060

```text
Error: YAML parse error on gitlab-runner/templates/configmap.yaml: error converting YAML to JSON: yaml: line 29: could not find expected ':'
```

Phase: $.runners | Status: failed

Selected fields (full context in artifacts):
- `$.runners = {"config": "\r0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/gitlab-runner_1789319420/0000/paths/b17636844fb2d0412107>)

#### E061

```text
Error: YAML parse error on gitlab-runner/templates/configmap.yaml: error converting YAML to JSON: yaml: line 35: could not find expected ':'
```

Phase: $.helperImage.repository | Status: failed

Selected fields (full context in artifacts):
- `$.helperImage.repository = "\r"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/gitlab-runner_1789319420/0000/paths/1009129d047c87cec347>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/gitlab-runner_1789319420/0000>)

### bitnami/grafana

Status: failed | Attempts: 1213

#### E071

```text
Error: YAML parse error on grafana/templates/application.yaml: error converting YAML to JSON: yaml: line 142: found an indentation indicator
equal to 0
```

Phase: $.persistence.existingClaim | Status: failed

Selected fields (full context in artifacts):
- `$.persistence.existingClaim = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana_1789319420/0000/paths/bc81b51736a9cdc4eda3>)

#### E072

```text
Error: YAML parse error on grafana/templates/application.yaml: error converting YAML to JSON: yaml: line 37: block sequence entries are not
allowed in this context
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[null]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana_1789319420/0000/paths/a4a0ea6ab697189bb963>)

#### E073

```text
Error: YAML parse error on grafana/templates/application.yaml: error converting YAML to JSON: yaml: line 63: mapping values are not allowed
in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana_1789319420/0000/paths/8e79b7dd85a286cfaddb>)

#### E074

```text
Error: YAML parse error on grafana/templates/pdb.yaml: error converting YAML to JSON: yaml: line 14: found an indentation indicator equal to
0
```

Phase: $.grafana.pdb | Status: failed

Selected fields (full context in artifacts):
- `$.grafana.pdb = {"maxUnavailable": ">0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana_1789319420/0000/paths/ba207baecff7b9d3f583>)

#### E227

Source: grafana 12.1.9 / templates/NOTES.txt

```text
execution error at (grafana/templates/NOTES.txt:36:3): VALUES VALIDATION: grafana: imageRenderer.enabled imageRenderer.serverURL and
imageRenderer.callbackURL You must provide the serverURL and callbackURL for Grafana Image Renderer when enabling it. (--set
imageRenderer.serverURL="http://image-renderer-url/render" --set imageRenderer.callbackURL="http://grafana-url:3000/")
```

Phase: $.imageRenderer | Status: failed

Selected fields (full context in artifacts):
- `$.imageRenderer = {"enabled": true}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana_1789319420/0000/paths/593ca6e46c6e401d5fac>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana_1789319420/0000>)

### bitnami/grafana-alloy

Status: failed | Attempts: 1174

#### E062

```text
Error: YAML parse error on grafana-alloy/templates/application.yaml: error converting YAML to JSON: yaml: line 85: could not find expected
':'
```

Phase: $.alloy | Status: failed

Selected fields (full context in artifacts):
- `$.alloy = {"listenAddr": "\n"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana-alloy_1789319420/0000/paths/678d8b0a3b6455a8e45c>)

#### E063

```text
Error: YAML parse error on grafana-alloy/templates/application.yaml: error converting YAML to JSON: yaml: line 93: found an indentation
indicator equal to 0
```

Phase: $.alloy.extraEnvVarsSecret | Status: failed

Selected fields (full context in artifacts):
- `$.alloy.extraEnvVarsSecret = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana-alloy_1789319420/0000/paths/c633d878cac5631aa773>)

#### E216

```text
Error: grafana-alloy/templates/networkpolicy.yaml:53:19 executing "grafana-alloy/templates/networkpolicy.yaml" at <.containerPort>: nil
pointer evaluating interface {}.containerPort
```

Phase: $.configReloader.extraContainerPorts | Status: failed

Selected fields (full context in artifacts):
- `$.configReloader.extraContainerPorts = [null]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana-alloy_1789319420/0000/paths/e4fbbfd6a02f60fba8aa>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana-alloy_1789319420/0000>)

### bitnami/grafana-k6-operator

Status: failed | Attempts: 1395

#### E064

```text
Error: YAML parse error on grafana-k6-operator/templates/deployment.yaml: error converting YAML to JSON: yaml: line 36: did not find
expected ',' or ']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana-k6-operator_1789319722/0000/paths/a4a0ea6ab697189bb963>)

Phase: $.global.imagePullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.global.imagePullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana-k6-operator_1789319722/0000/paths/097f6358a00dddbcdd83>)

#### E065

```text
Error: YAML parse error on grafana-k6-operator/templates/deployment.yaml: error converting YAML to JSON: yaml: line 60: mapping values are
not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana-k6-operator_1789319722/0000/paths/8e79b7dd85a286cfaddb>)

#### E066

```text
Error: YAML parse error on grafana-k6-operator/templates/pdb.yaml: error converting YAML to JSON: yaml: line 15: found an indentation
indicator equal to 0
```

Phase: $.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana-k6-operator_1789319722/0000/paths/d6baed3b8998a068f471>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana-k6-operator_1789319722/0000>)

### bitnami/grafana-loki

Status: time-limit | Attempts: 251

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana-loki_1789319722/0000>)

### bitnami/grafana-mimir

Status: time-limit | Attempts: 212

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana-mimir_1789319723/0000>)

### bitnami/grafana-operator

Status: failed | Attempts: 1060

#### E067

```text
Error: YAML parse error on grafana-operator/templates/grafana-pdb.yaml: error converting YAML to JSON: yaml: line 15: could not find
expected ':'
```

Phase: $.grafana.pdb | Status: failed

Selected fields (full context in artifacts):
- `$.grafana.pdb = {"create": true, "maxUnavailable": "\r0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana-operator_1789319723/0000/paths/ba207baecff7b9d3f583>)

#### E068

```text
Error: YAML parse error on grafana-operator/templates/grafana.yaml: error converting YAML to JSON: yaml: line 37: did not find expected ','
or ']'
```

Phase: $.grafana.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.grafana.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana-operator_1789319723/0000/paths/df306bacd6eea5dbd3fd>)

#### E069

```text
Error: YAML parse error on grafana-operator/templates/grafana.yaml: error converting YAML to JSON: yaml: line 58: did not find expected key
```

Phase: $.grafana.secrets | Status: failed

Selected fields (full context in artifacts):
- `$.grafana.secrets = [{"'": null}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana-operator_1789319723/0000/paths/c195ba00c143b0340a3b>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana-operator_1789319723/0000>)

### bitnami/grafana-tempo

Status: failed | Attempts: 359

#### E070

```text
Error: YAML parse error on grafana-tempo/templates/distributor/service.yaml: error converting YAML to JSON: yaml: line 15: found an
indentation indicator equal to 0
```

Phase: $.distributor.service.sessionAffinity | Status: failed

Selected fields (full context in artifacts):
- `$.distributor.service.sessionAffinity = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana-tempo_1789320024/0000/paths/9aef6208a1e363e5cf41>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/grafana-tempo_1789320024/0000>)

### bitnami/haproxy

Status: failed | Attempts: 1768

#### E075

```text
Error: YAML parse error on haproxy/templates/deployment.yaml: error converting YAML to JSON: yaml: line 35: did not find expected ',' or ']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/haproxy_1789320025/0000/paths/a4a0ea6ab697189bb963>)

Phase: $.global.imagePullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.global.imagePullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/haproxy_1789320025/0000/paths/097f6358a00dddbcdd83>)

1 additional occurrences are retained in the JSON report and chart artifacts.

#### E076

```text
Error: YAML parse error on haproxy/templates/deployment.yaml: error converting YAML to JSON: yaml: line 60: mapping values are not allowed
in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/haproxy_1789320025/0000/paths/8e79b7dd85a286cfaddb>)

#### E077

```text
Error: YAML parse error on haproxy/templates/pdb.yaml: error converting YAML to JSON: yaml: line 13: found an indentation indicator equal to
0
```

Phase: $.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/haproxy_1789320025/0000/paths/d6baed3b8998a068f471>)

#### E078

```text
Error: YAML parse error on haproxy/templates/service.yaml: error converting YAML to JSON: yaml: line 14: found an indentation indicator
equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/haproxy_1789320025/0000/paths/6e931799d09f8182f34b>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/haproxy_1789320025/0000>)

### bitnami/harbor

Status: time-limit | Attempts: 170

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/harbor_1789320028/0000>)

### bitnami/influxdb

Status: failed | Attempts: 1203

#### E079

```text
Error: YAML parse error on influxdb/templates/deployment.yaml: error converting YAML to JSON: yaml: line 62: mapping values are not allowed
in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/influxdb_1789320028/0000/paths/8e79b7dd85a286cfaddb>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/influxdb_1789320028/0000>)

### bitnami/jaeger

Status: time-limit | Attempts: 674

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/jaeger_1789320327/0000>)

### bitnami/janusgraph

Status: failed | Attempts: 968

#### E080

```text
Error: YAML parse error on janusgraph/templates/deployment.yaml: error converting YAML to JSON: yaml: line 62: mapping values are not
allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/janusgraph_1789320328/0000/paths/8e79b7dd85a286cfaddb>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/janusgraph_1789320328/0000>)

### bitnami/jenkins

Status: failed | Attempts: 1169

#### E081

```text
Error: YAML parse error on jenkins/templates/deployment.yaml: error converting YAML to JSON: yaml: line 161: found an indentation indicator
equal to 0
```

Phase: $.persistence.existingClaim | Status: failed

Selected fields (full context in artifacts):
- `$.persistence.existingClaim = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/jenkins_1789320330/0000/paths/bc81b51736a9cdc4eda3>)

#### E082

```text
Error: YAML parse error on jenkins/templates/deployment.yaml: error converting YAML to JSON: yaml: line 34: block sequence entries are not
allowed in this context
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[null]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/jenkins_1789320330/0000/paths/a4a0ea6ab697189bb963>)

#### E083

```text
Error: YAML parse error on jenkins/templates/deployment.yaml: error converting YAML to JSON: yaml: line 57: mapping values are not allowed
in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/jenkins_1789320330/0000/paths/8e79b7dd85a286cfaddb>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/jenkins_1789320330/0000>)

### bitnami/jupyterhub

Status: failed | Attempts: 521

#### E084

```text
Error: YAML parse error on jupyterhub/templates/hub/servicemonitor.yaml: error converting YAML to JSON: yaml: line 19: could not find
expected ':'
```

Phase: $.hub.metrics.serviceMonitor | Status: failed

Selected fields (full context in artifacts):
- `$.hub.metrics.serviceMonitor = {"enabled": true, "interval": "\r0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/jupyterhub_1789320333/0000/paths/373db267daac756f7747>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/jupyterhub_1789320333/0000>)

### bitnami/kafka

Status: time-limit | Attempts: 533

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kafka_1789320629/0000>)

### bitnami/keycloak

Status: failed | Attempts: 790

#### E242

```text
level=INFO msg="warning: destination for postgresql.tls.autoGenerated is a table. Ignoring non-table value (false)" Error: YAML parse error
on keycloak/charts/postgresql/templates/primary/statefulset.yaml: error converting YAML to JSON: yaml: line 173: found an indentation
indicator equal to 0
```

Phase: $.postgresql.auth.existingSecret | Status: failed

Selected fields (full context in artifacts):
- `$.postgresql.auth.existingSecret = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/keycloak_1789320630/0000/paths/a0cdb2ba618083d9a8df>)

#### E243

```text
level=INFO msg="warning: destination for postgresql.tls.autoGenerated is a table. Ignoring non-table value (false)" Error: YAML parse error
on keycloak/templates/keycloak-config-cli-job.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go
struct field .metadata.annotations. of type string
```

Phase: $.keycloakConfigCli | Status: failed

Selected fields (full context in artifacts):
- `$.keycloakConfigCli = {"annotations": {"": []}, "enabled": true}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/keycloak_1789320630/0000/paths/833e1ce85b0d7e5a8ef8>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/keycloak_1789320630/0000>)

### bitnami/keydb

Status: time-limit | Attempts: 735

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/keydb_1789320632/0000>)

### bitnami/kibana

Status: failed | Attempts: 1503

#### E085

```text
Error: YAML parse error on kibana/templates/saved-objects-configmap.yaml: error converting YAML to JSON: yaml: line 23: could not find
expected ':'
```

Phase: $.savedObjects.urls | Status: failed

Selected fields (full context in artifacts):
- `$.savedObjects.urls = [{"\r": null}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kibana_1789320637/0000/paths/7353f861890968cecbe7>)

#### E228

Source: kibana 12.1.11 / templates/NOTES.txt

```text
[Diagnostic shortened; full text in artifacts] ... iners is likely to cause degraded security and performance, broken chart features, and
missing environment variables. Unrecognized images: - 00/bitnami/kibana:9.1.2-debian-12-r0 If you are sure you want to proceed with
non-standard containers, you can skip container image verification by setting the global parameter 'global.security.allowInsecureImages' to
true. Further information can be obtained at https://github.com/bitnami/charts/issues/30850
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"registry": "00"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kibana_1789320637/0000/paths/8e79b7dd85a286cfaddb>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kibana_1789320637/0000>)

### bitnami/kong

Status: failed | Attempts: 818

#### E086

```text
Error: YAML parse error on kong/charts/postgresql/templates/primary/statefulset.yaml: error converting YAML to JSON: yaml: line 173: found
an indentation indicator equal to 0
```

Phase: $.postgresql.auth.existingSecret | Status: failed

Selected fields (full context in artifacts):
- `$.postgresql.auth.existingSecret = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kong_1789320932/0000/paths/a0cdb2ba618083d9a8df>)

#### E087

```text
Error: YAML parse error on kong/templates/dep-ds.yaml: error converting YAML to JSON: yaml: line 60: mapping values are not allowed in this
context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kong_1789320932/0000/paths/8e79b7dd85a286cfaddb>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kong_1789320932/0000>)

### bitnami/kube-arangodb

Status: failed | Attempts: 880

#### E088

```text
Error: YAML parse error on kube-arangodb/templates/deployment.yaml: error converting YAML to JSON: yaml: line 62: mapping values are not
allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kube-arangodb_1789320933/0000/paths/8e79b7dd85a286cfaddb>)

#### E089

```text
Error: YAML parse error on kube-arangodb/templates/service.yaml: error converting YAML to JSON: yaml: line 33: found an indentation
indicator equal to 0
```

Phase: $.service.nodePorts.apiGrpc | Status: failed

Selected fields (full context in artifacts):
- `$.service.nodePorts.apiGrpc = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kube-arangodb_1789320933/0000/paths/5e977ce661c5834a77a0>)

#### E090

```text
Error: YAML parse error on kube-arangodb/templates/webhook/service.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.webhooks.service.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.webhooks.service.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kube-arangodb_1789320933/0000/paths/076c619c7ae02788c2ae>)

#### E244

```text
resource has no metadata.name
```

Phase: $.serviceAccount.operator.name | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount.operator.name = "0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kube-arangodb_1789320933/0000/paths/95bc8b2087be846a7d07>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kube-arangodb_1789320933/0000>)

### bitnami/kube-prometheus

Status: time-limit | Attempts: 224

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kube-prometheus_1789320934/0000>)

### bitnami/kube-prometheus/charts/kube-prometheus-crds

Status: failed | Attempts: 1

#### E221

```text
chart rendered no resources
```

Phase: chart | Status: failed

No triggering values were recorded for this diagnostic.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kube-prometheus-crds_1789320938/0000>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kube-prometheus-crds_1789320938/0000>)

### bitnami/kube-state-metrics

Status: failed | Attempts: 1584

#### E091

```text
Error: YAML parse error on kube-state-metrics/templates/deployment.yaml: error converting YAML to JSON: yaml: line 31: block sequence
entries are not allowed in this context
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[null]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kube-state-metrics_1789320939/0000/paths/a4a0ea6ab697189bb963>)

Phase: $.global.imagePullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.global.imagePullSecrets = [[null]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kube-state-metrics_1789320939/0000/paths/097f6358a00dddbcdd83>)

1 additional occurrences are retained in the JSON report and chart artifacts.

#### E092

```text
Error: YAML parse error on kube-state-metrics/templates/deployment.yaml: error converting YAML to JSON: yaml: line 55: mapping values are
not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kube-state-metrics_1789320939/0000/paths/8e79b7dd85a286cfaddb>)

#### E093

```text
Error: YAML parse error on kube-state-metrics/templates/pdb.yaml: error converting YAML to JSON: yaml: line 13: found an indentation
indicator equal to 0
```

Phase: $.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kube-state-metrics_1789320939/0000/paths/d6baed3b8998a068f471>)

#### E094

```text
Error: YAML parse error on kube-state-metrics/templates/service.yaml: error converting YAML to JSON: yaml: line 16: found an indentation
indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kube-state-metrics_1789320939/0000/paths/6e931799d09f8182f34b>)

#### E095

```text
Error: YAML parse error on kube-state-metrics/templates/service.yaml: error converting YAML to JSON: yaml: line 27: block sequence entries
are not allowed in this context
```

Phase: $.selfMonitor | Status: failed

Selected fields (full context in artifacts):
- `$.selfMonitor = {"enabled": true, "telemetryNodePort": "-"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kube-state-metrics_1789320939/0000/paths/280d62af7078b21d80d1>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kube-state-metrics_1789320939/0000>)

### bitnami/kuberay

Status: failed | Attempts: 560

#### E096

```text
Error: YAML parse error on kuberay/templates/apiserver/deployment.yaml: error converting YAML to JSON: yaml: line 60: mapping values are not
allowed in this context
```

Phase: $.apiserver.image.tag | Status: failed

Selected fields (full context in artifacts):
- `$.apiserver.image.tag = ""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kuberay_1789321235/0000/paths/59e72c2ad87ace6ebb08>)

#### E097

```text
Error: YAML parse error on kuberay/templates/cluster/raycluster.yaml: error converting YAML to JSON: yaml: line 55: found an indentation
indicator equal to 0
```

Phase: $.rayImage.pullPolicy | Status: failed

Selected fields (full context in artifacts):
- `$.rayImage.pullPolicy = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kuberay_1789321235/0000/paths/21a6be6e1f125b3a5329>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kuberay_1789321235/0000>)

### bitnami/kubernetes-event-exporter

Status: failed | Attempts: 1626

#### E098

```text
Error: YAML parse error on kubernetes-event-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 35: did not find
expected ',' or ']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kubernetes-event-exporter_1789321235/0000/paths/a4a0ea6ab697189bb963>)

#### E099

```text
Error: YAML parse error on kubernetes-event-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 59: mapping values
are not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kubernetes-event-exporter_1789321235/0000/paths/8e79b7dd85a286cfaddb>)

#### E100

```text
Error: YAML parse error on kubernetes-event-exporter/templates/pdb.yaml: error converting YAML to JSON: yaml: line 13: found an indentation
indicator equal to 0
```

Phase: $.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kubernetes-event-exporter_1789321235/0000/paths/d6baed3b8998a068f471>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/kubernetes-event-exporter_1789321235/0000>)

### bitnami/logstash

Status: failed | Attempts: 1627

#### E101

```text
Error: YAML parse error on logstash/templates/configuration-cm.yaml: error converting YAML to JSON: yaml: line 31: could not find expected
':'
```

Phase: $.filter | Status: failed

Selected fields (full context in artifacts):
- `$.filter = "\r0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/logstash_1789321239/0000/paths/0e1e9caa4953f85afca2>)

#### E102

```text
Error: YAML parse error on logstash/templates/networkpolicy.yaml: error converting YAML to JSON: yaml: line 28: could not find expected ':'
```

Phase: $.networkPolicy.customRules | Status: failed

Selected fields (full context in artifacts):
- `$.networkPolicy.customRules = true`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/logstash_1789321239/0000/paths/1d6a5faf6612f0fc5d5a>)

#### E103

```text
Error: YAML parse error on logstash/templates/pdb.yaml: error converting YAML to JSON: yaml: line 13: found an indentation indicator equal
to 0
```

Phase: $.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/logstash_1789321239/0000/paths/d6baed3b8998a068f471>)

#### E104

```text
Error: YAML parse error on logstash/templates/sts.yaml: error converting YAML to JSON: yaml: line 34: block sequence entries are not allowed
in this context
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[null]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/logstash_1789321239/0000/paths/a4a0ea6ab697189bb963>)

Phase: $.global.imagePullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.global.imagePullSecrets = [[null]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/logstash_1789321239/0000/paths/097f6358a00dddbcdd83>)

#### E105

```text
Error: YAML parse error on logstash/templates/sts.yaml: error converting YAML to JSON: yaml: line 58: mapping values are not allowed in this
context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/logstash_1789321239/0000/paths/8e79b7dd85a286cfaddb>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/logstash_1789321239/0000>)

### bitnami/mariadb

Status: failed | Attempts: 872

#### E110

```text
Error: YAML parse error on mariadb/templates/primary/statefulset.yaml: error converting YAML to JSON: yaml: line 197: found an indentation
indicator equal to 0
```

Phase: $.primary.existingConfigmap | Status: failed

Selected fields (full context in artifacts):
- `$.primary.existingConfigmap = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/mariadb_1789321241/0000/paths/5840f42f3422db400ece>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/mariadb_1789321241/0000>)

### bitnami/mariadb-galera

Status: failed | Attempts: 1262

#### E106

```text
Error: YAML parse error on mariadb-galera/templates/networkpolicy.yaml: error converting YAML to JSON: yaml: line 29: could not find
expected ':'
```

Phase: $.networkPolicy.customRules | Status: failed

Selected fields (full context in artifacts):
- `$.networkPolicy.customRules = true`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/mariadb-galera_1789321537/0000/paths/1d6a5faf6612f0fc5d5a>)

#### E107

```text
Error: YAML parse error on mariadb-galera/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 235: found an indentation
indicator equal to 0
```

Phase: $.persistence.existingClaim | Status: failed

Selected fields (full context in artifacts):
- `$.persistence.existingClaim = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/mariadb-galera_1789321537/0000/paths/bc81b51736a9cdc4eda3>)

#### E108

```text
Error: YAML parse error on mariadb-galera/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 33: did not find expected
',' or ']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/mariadb-galera_1789321537/0000/paths/a4a0ea6ab697189bb963>)

#### E109

```text
Error: YAML parse error on mariadb-galera/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 57: mapping values are not
allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/mariadb-galera_1789321537/0000/paths/8e79b7dd85a286cfaddb>)

#### E229

Source: mariadb-galera 16.0.2 / templates/NOTES.txt

```text
execution error at (mariadb-galera/templates/NOTES.txt:90:3): VALUES VALIDATION: mariadb-galera: galera.mariabackup.password A MariaBackup
Password is required ("galera.mariabackup.forcePassword=true" is set) Please set a password (--set galera.mariabackup.password="xxxx")
```

Phase: $.galera.mariabackup.forcePassword | Status: failed

Selected fields (full context in artifacts):
- `$.galera.mariabackup.forcePassword = true`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/mariadb-galera_1789321537/0000/paths/374c3045cc99de520f56>)

#### E230

Source: mariadb-galera 16.0.2 / templates/NOTES.txt

```text
execution error at (mariadb-galera/templates/NOTES.txt:90:3): VALUES VALIDATION: mariadb-galera: rootUser.password A MariaDB Database Root
Password is required ("rootUser.forcePassword=true" is set) Please set a password (--set rootUser.password="xxxx")
```

Phase: $.rootUser | Status: failed

Selected fields (full context in artifacts):
- `$.rootUser = {"forcePassword": true}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/mariadb-galera_1789321537/0000/paths/9bfb61fcd2895ab39c7d>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/mariadb-galera_1789321537/0000>)

### bitnami/mastodon

Status: time-limit | Attempts: 364

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/mastodon_1789321537/0000>)

### bitnami/matomo

Status: failed | Attempts: 886

#### E111

```text
Error: YAML parse error on matomo/templates/cronjob.yaml: error converting YAML to JSON: yaml: line 40: mapping values are not allowed in
this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/matomo_1789321541/0000/paths/8e79b7dd85a286cfaddb>)

#### E112

```text
Error: YAML parse error on matomo/templates/deployment.yaml: error converting YAML to JSON: yaml: line 155: found an indentation indicator
equal to 0
```

Phase: $.persistence.existingClaim | Status: failed

Selected fields (full context in artifacts):
- `$.persistence.existingClaim = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/matomo_1789321541/0000/paths/bc81b51736a9cdc4eda3>)

#### E113

```text
Error: YAML parse error on matomo/templates/deployment.yaml: error converting YAML to JSON: yaml: line 156: found an indentation indicator
equal to 0
```

Phase: $.smtpExistingSecret | Status: failed

Selected fields (full context in artifacts):
- `$.smtpExistingSecret = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/matomo_1789321541/0000/paths/5787f0eface5fec9a681>)

#### E217

```text
Error: matomo/templates/deployment.yaml:328:34 executing "matomo/templates/deployment.yaml" at <$customCA.secret>: nil pointer evaluating
interface {}.secret
```

Phase: $.certificates.customCAs[*] | Status: failed

Selected fields (full context in artifacts):
- No supplied value at the selected paths.
Absent from overrides: $.certificates.customCAs["*"]. Defaults may still apply.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/matomo_1789321541/0000/paths/f0b38f929a3c18847f6b>)

#### E231

Source: mariadb 22.0.0 / templates/NOTES.txt

```text
execution error at (mariadb/templates/NOTES.txt:74:4): VALUES VALIDATION: mariadb: architecture Invalid architecture selected. Valid values
are "standalone" and "replication". Please set a valid architecture (--set architecture="xxxx")
```

Phase: $.mariadb.architecture | Status: failed

Selected fields (full context in artifacts):
- `$.mariadb.architecture = ""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/matomo_1789321541/0000/paths/1ff74c0fd3bc5bc52c04>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/matomo_1789321541/0000>)

### bitnami/memcached

Status: failed | Attempts: 1537

#### E114

```text
Error: YAML parse error on memcached/templates/deployment.yaml: error converting YAML to JSON: yaml: line 31: did not find expected ',' or
']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/memcached_1789321543/0000/paths/a4a0ea6ab697189bb963>)

#### E115

```text
Error: YAML parse error on memcached/templates/deployment.yaml: error converting YAML to JSON: yaml: line 56: mapping values are not allowed
in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/memcached_1789321543/0000/paths/8e79b7dd85a286cfaddb>)

#### E116

```text
Error: YAML parse error on memcached/templates/pdb.yaml: error converting YAML to JSON: yaml: line 13: found an indentation indicator equal
to 0
```

Phase: $.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/memcached_1789321543/0000/paths/d6baed3b8998a068f471>)

#### E117

```text
Error: YAML parse error on memcached/templates/service.yaml: error converting YAML to JSON: yaml: line 14: found an indentation indicator
equal to 0
```

Phase: $.service.trafficDistribution | Status: failed

Selected fields (full context in artifacts):
- `$.service.trafficDistribution = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/memcached_1789321543/0000/paths/76c21b9e4a991e167280>)

#### E233

Source: memcached 8.0.0 / templates/NOTES.txt

```text
execution error at (memcached/templates/NOTES.txt:46:4): VALUES VALIDATION: memcached: auth.username Enabling authentication requires
setting a valid admin username. Please set a valid username (--set auth.username="xxxx") memcached:
containerSecurityContext.readOnlyRootFilesystem Enabling authentication is not compatible with using a read-only filesystem. Please disable
it (--set containerSecurityContext.readOnlyRootFilesystem=false)
```

Phase: $.auth | Status: failed

Selected fields (full context in artifacts):
- `$.auth = {"enabled": true}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/memcached_1789321543/0000/paths/9add85c17048305af4de>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/memcached_1789321543/0000>)

### bitnami/metallb

Status: failed | Attempts: 593

#### E118

```text
Error: YAML parse error on metallb/templates/controller/deployment.yaml: error converting YAML to JSON: yaml: line 34: block sequence
entries are not allowed in this context
```

Phase: $.speaker.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.speaker.image.pullSecrets = [[null]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/metallb_1789321839/0000/paths/5ab2d3186d90225b4cbe>)

#### E218

```text
Error: metallb/templates/speaker/networkpolicy.yaml:41:64 executing "metallb/templates/speaker/networkpolicy.yaml" at
<.Values.rts.networkPolicy.extraEgress>: nil pointer evaluating interface {}.networkPolicy
```

Phase: $.speaker.networkPolicy | Status: failed

Selected fields (full context in artifacts):
- `$.speaker.networkPolicy = {"allowExternalEgress": false, "extraEgress": [null]}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/metallb_1789321839/0000/paths/f5d31f16549a6dfd7a6a>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/metallb_1789321839/0000>)

### bitnami/metrics-server

Status: failed | Attempts: 1861

#### E119

```text
Error: YAML parse error on metrics-server/templates/deployment.yaml: error converting YAML to JSON: yaml: line 30: block sequence entries
are not allowed in this context
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[null]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/metrics-server_1789321842/0000/paths/a4a0ea6ab697189bb963>)

Phase: $.global.imagePullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.global.imagePullSecrets = [[null]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/metrics-server_1789321842/0000/paths/097f6358a00dddbcdd83>)

1 additional occurrences are retained in the JSON report and chart artifacts.

#### E120

```text
Error: YAML parse error on metrics-server/templates/deployment.yaml: error converting YAML to JSON: yaml: line 54: mapping values are not
allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/metrics-server_1789321842/0000/paths/8e79b7dd85a286cfaddb>)

#### E121

```text
Error: YAML parse error on metrics-server/templates/pdb.yaml: error converting YAML to JSON: yaml: line 13: found an indentation indicator
equal to 0
```

Phase: $.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/metrics-server_1789321842/0000/paths/d6baed3b8998a068f471>)

Phase: $.pdb.minAvailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.minAvailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/metrics-server_1789321842/0000/paths/07d4854a45a9e7c1eb04>)

#### E122

```text
Error: YAML parse error on metrics-server/templates/svc.yaml: error converting YAML to JSON: yaml: line 13: found an indentation indicator
equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/metrics-server_1789321842/0000/paths/6e931799d09f8182f34b>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/metrics-server_1789321842/0000>)

### bitnami/milvus

Status: time-limit | Attempts: 78

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/milvus_1789321843/0000>)

### bitnami/mlflow

Status: time-limit | Attempts: 566

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/mlflow_1789321845/0000>)

### bitnami/mongodb

Status: time-limit | Attempts: 667

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/mongodb_1789322141/0000>)

### bitnami/mongodb-sharded

Status: failed | Attempts: 603

#### E123

```text
Error: YAML parse error on mongodb-sharded/templates/config-server/config-server-statefulset.yaml: error converting YAML to JSON: yaml: line
21: found an indentation indicator equal to 0
```

Phase: $.configsvr.podManagementPolicy | Status: failed

Selected fields (full context in artifacts):
- `$.configsvr.podManagementPolicy = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/mongodb-sharded_1789322143/0000/paths/31b5e6e1c0df26c243fd>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/mongodb-sharded_1789322143/0000>)

### bitnami/moodle

Status: failed | Attempts: 1146

#### E124

```text
Error: YAML parse error on moodle/templates/deployment.yaml: error converting YAML to JSON: yaml: line 108: could not find expected ':'
```

Phase: $.lifecycleHooks | Status: failed

Selected fields (full context in artifacts):
- `$.lifecycleHooks = "\r0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/moodle_1789322148/0000/paths/f43b61ad2b3dc983dbd6>)

#### E125

```text
Error: YAML parse error on moodle/templates/deployment.yaml: error converting YAML to JSON: yaml: line 155: found an indentation indicator
equal to 0
```

Phase: $.persistence.existingClaim | Status: failed

Selected fields (full context in artifacts):
- `$.persistence.existingClaim = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/moodle_1789322148/0000/paths/bc81b51736a9cdc4eda3>)

#### E126

```text
Error: YAML parse error on moodle/templates/deployment.yaml: error converting YAML to JSON: yaml: line 31: block sequence entries are not
allowed in this context
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[null]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/moodle_1789322148/0000/paths/a4a0ea6ab697189bb963>)

#### E127

```text
Error: YAML parse error on moodle/templates/deployment.yaml: error converting YAML to JSON: yaml: line 60: mapping values are not allowed in
this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/moodle_1789322148/0000/paths/8e79b7dd85a286cfaddb>)

#### E231

Source: mariadb 22.0.0 / templates/NOTES.txt

```text
execution error at (mariadb/templates/NOTES.txt:74:4): VALUES VALIDATION: mariadb: architecture Invalid architecture selected. Valid values
are "standalone" and "replication". Please set a valid architecture (--set architecture="xxxx")
```

Phase: $.mariadb.architecture | Status: failed

Selected fields (full context in artifacts):
- `$.mariadb.architecture = ""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/moodle_1789322148/0000/paths/1ff74c0fd3bc5bc52c04>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/moodle_1789322148/0000>)

### bitnami/multus-cni

Status: failed | Attempts: 2245

#### E128

```text
Error: YAML parse error on multus-cni/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 28: did not find expected ',' or
']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/multus-cni_1789322151/0000/paths/a4a0ea6ab697189bb963>)

Phase: $.global.imagePullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.global.imagePullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/multus-cni_1789322151/0000/paths/097f6358a00dddbcdd83>)

1 additional occurrences are retained in the JSON report and chart artifacts.

#### E129

```text
Error: YAML parse error on multus-cni/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 50: found an indentation indicator
equal to 0
```

Phase: $.schedulerName | Status: failed

Selected fields (full context in artifacts):
- `$.schedulerName = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/multus-cni_1789322151/0000/paths/57504c968732d9714f10>)

#### E130

```text
Error: YAML parse error on multus-cni/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 54: mapping values are not allowed
in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/multus-cni_1789322151/0000/paths/8e79b7dd85a286cfaddb>)

#### E131

```text
Error: YAML parse error on multus-cni/templates/service-account.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal
array into Go struct field .metadata.annotations. of type string
```

Phase: $.serviceAccount.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/multus-cni_1789322151/0000/paths/840a8a2bc50327388c2a>)

#### E234

Source: multus-cni 2.2.22 / templates/NOTES.txt

```text
[Diagnostic shortened; full text in artifacts] ...  containers is likely to cause degraded security and performance, broken chart features,
and missing environment variables. Unrecognized images: - docker.io/0:4.2.2-debian-12-r2 If you are sure you want to proceed with
non-standard containers, you can skip container image verification by setting the global parameter 'global.security.allowInsecureImages' to
true. Further information can be obtained at https://github.com/bitnami/charts/issues/30850
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/multus-cni_1789322151/0000/paths/3f7165f1837241716c3c>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/multus-cni_1789322151/0000>)

### bitnami/mysql

Status: failed | Attempts: 974

#### E132

```text
Error: YAML parse error on mysql/templates/primary/statefulset.yaml: error converting YAML to JSON: yaml: line 211: found an indentation
indicator equal to 0
```

Phase: $.primary.existingConfigmap | Status: failed

Selected fields (full context in artifacts):
- `$.primary.existingConfigmap = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/mysql_1789322445/0000/paths/5840f42f3422db400ece>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/mysql_1789322445/0000>)

### bitnami/nats

Status: failed | Attempts: 1470

#### E133

```text
Error: YAML parse error on nats/templates/application.yaml: error converting YAML to JSON: yaml: line 33: did not find expected ',' or ']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/nats_1789322446/0000/paths/a4a0ea6ab697189bb963>)

#### E134

```text
Error: YAML parse error on nats/templates/application.yaml: error converting YAML to JSON: yaml: line 57: mapping values are not allowed in
this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/nats_1789322446/0000/paths/8e79b7dd85a286cfaddb>)

#### E220

```text
Inconsistent data generation! Data generation behaved differently between test cases. Is your data generation depending on external state?
The second run stopped drawing earlier than the first run, which continued to draw more data.
```

Phase: $.livenessProbe.periodSeconds | Status: failed

Selected fields (full context in artifacts):
- No supplied value at the selected paths.
Absent from overrides: $.livenessProbe.periodSeconds. Defaults may still apply.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/nats_1789322446/0000/paths/1806901960e9247cdf0a>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/nats_1789322446/0000>)

### bitnami/neo4j

Status: failed | Attempts: 1230

#### E235

Source: neo4j 0.4.15 / templates/NOTES.txt

```text
[Diagnostic shortened; full text in artifacts] ... ners is likely to cause degraded security and performance, broken chart features, and
missing environment variables. Unrecognized images: - 00/bitnami/neo4j:5.26.11-debian-12-r0 If you are sure you want to proceed with
non-standard containers, you can skip container image verification by setting the global parameter 'global.security.allowInsecureImages' to
true. Further information can be obtained at https://github.com/bitnami/charts/issues/30850
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"registry": "00"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/neo4j_1789322450/0000/paths/8e79b7dd85a286cfaddb>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/neo4j_1789322450/0000>)

### bitnami/nessie

Status: failed | Attempts: 1064

#### E135

```text
Error: YAML parse error on nessie/charts/postgresql/templates/primary/statefulset.yaml: error converting YAML to JSON: yaml: line 173: found
an indentation indicator equal to 0
```

Phase: $.postgresql.auth.existingSecret | Status: failed

Selected fields (full context in artifacts):
- `$.postgresql.auth.existingSecret = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/nessie_1789322452/0000/paths/a0cdb2ba618083d9a8df>)

#### E136

```text
Error: YAML parse error on nessie/templates/deployment.yaml: error converting YAML to JSON: yaml: line 135: mapping values are not allowed
in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/nessie_1789322452/0000/paths/8e79b7dd85a286cfaddb>)

#### E137

```text
Error: YAML parse error on nessie/templates/deployment.yaml: error converting YAML to JSON: yaml: line 39: block sequence entries are not
allowed in this context
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[null]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/nessie_1789322452/0000/paths/a4a0ea6ab697189bb963>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/nessie_1789322452/0000>)

### bitnami/nginx

Status: failed | Attempts: 796

#### E138

```text
Error: YAML parse error on nginx/templates/deployment.yaml: error converting YAML to JSON: yaml: line 183: found an indentation indicator
equal to 0
```

Phase: $.existingContextEventsConfigmaps[*] | Status: failed

Selected fields (full context in artifacts):
- No supplied value at the selected paths.
Absent from overrides: $.existingContextEventsConfigmaps["*"]. Defaults may still apply.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/nginx_1789322747/0000/paths/d3a4ba9b3aa8276f735b>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/nginx_1789322747/0000>)

### bitnami/node-exporter

Status: failed | Attempts: 2042

#### E139

```text
Error: YAML parse error on node-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 32: block sequence entries are
not allowed in this context
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[null]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/node-exporter_1789322747/0000/paths/a4a0ea6ab697189bb963>)

Phase: $.global.imagePullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.global.imagePullSecrets = [[null]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/node-exporter_1789322747/0000/paths/097f6358a00dddbcdd83>)

1 additional occurrences are retained in the JSON report and chart artifacts.

#### E140

```text
Error: YAML parse error on node-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 55: mapping values are not
allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/node-exporter_1789322747/0000/paths/8e79b7dd85a286cfaddb>)

#### E141

```text
Error: YAML parse error on node-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 15: found an indentation
indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/node-exporter_1789322747/0000/paths/6e931799d09f8182f34b>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/node-exporter_1789322747/0000>)

### bitnami/oauth2-proxy

Status: failed | Attempts: 1205

#### E142

```text
Error: YAML parse error on oauth2-proxy/templates/deployment.yaml: error converting YAML to JSON: yaml: line 36: block sequence entries are
not allowed in this context
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[null]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/oauth2-proxy_1789322752/0000/paths/a4a0ea6ab697189bb963>)

#### E143

```text
Error: YAML parse error on oauth2-proxy/templates/deployment.yaml: error converting YAML to JSON: yaml: line 59: mapping values are not
allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/oauth2-proxy_1789322752/0000/paths/8e79b7dd85a286cfaddb>)

#### E237

Source: redis 22.0.4 / templates/NOTES.txt

```text
execution error at (redis/templates/NOTES.txt:202:4): VALUES VALIDATION: redis: architecture Using redis sentinel on standalone mode is not
supported. To deploy redis sentinel, please select the "replication" mode (--set "architecture=replication,sentinel.enabled=true")
```

Phase: $.redis.sentinel.enabled | Status: failed

Selected fields (full context in artifacts):
- `$.redis.sentinel.enabled = true`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/oauth2-proxy_1789322752/0000/paths/06ba645f6017e60308b2>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/oauth2-proxy_1789322752/0000>)

### bitnami/odoo

Status: failed | Attempts: 1281

#### E144

```text
Error: YAML parse error on odoo/charts/postgresql/templates/primary/statefulset.yaml: error converting YAML to JSON: yaml: line 173: found
an indentation indicator equal to 0
```

Phase: $.postgresql.auth.existingSecret | Status: failed

Selected fields (full context in artifacts):
- `$.postgresql.auth.existingSecret = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/odoo_1789322754/0000/paths/a0cdb2ba618083d9a8df>)

#### E145

```text
Error: YAML parse error on odoo/templates/deployment.yaml: error converting YAML to JSON: yaml: line 139: found an indentation indicator
equal to 0
```

Phase: $.persistence.existingClaim | Status: failed

Selected fields (full context in artifacts):
- `$.persistence.existingClaim = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/odoo_1789322754/0000/paths/bc81b51736a9cdc4eda3>)

#### E146

```text
Error: YAML parse error on odoo/templates/deployment.yaml: error converting YAML to JSON: yaml: line 150: found an indentation indicator
equal to 0
```

Phase: $.smtpExistingSecret | Status: failed

Selected fields (full context in artifacts):
- `$.smtpExistingSecret = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/odoo_1789322754/0000/paths/5787f0eface5fec9a681>)

#### E147

```text
Error: YAML parse error on odoo/templates/deployment.yaml: error converting YAML to JSON: yaml: line 30: did not find expected ',' or ']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/odoo_1789322754/0000/paths/a4a0ea6ab697189bb963>)

#### E148

```text
Error: YAML parse error on odoo/templates/deployment.yaml: error converting YAML to JSON: yaml: line 54: mapping values are not allowed in
this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/odoo_1789322754/0000/paths/8e79b7dd85a286cfaddb>)

#### E149

```text
Error: YAML parse error on odoo/templates/pdb.yaml: error converting YAML to JSON: yaml: line 13: found an indentation indicator equal to 0
```

Phase: $.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/odoo_1789322754/0000/paths/d6baed3b8998a068f471>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/odoo_1789322754/0000>)

### bitnami/opensearch

Status: time-limit | Attempts: 362

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/opensearch_1789323049/0000>)

### bitnami/parse

Status: failed | Attempts: 741

#### E150

```text
Error: YAML parse error on parse/charts/mongodb/templates/standalone/pvc.yaml: error converting YAML to JSON: yaml: line 22: could not find
expected ':'
```

Phase: $.mongodb.persistence | Status: failed

Selected fields (full context in artifacts):
- `$.mongodb.persistence = {"storageClass": "\r0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/parse_1789323049/0000/paths/41d6ae6f8aea08087045>)

#### E151

```text
Error: YAML parse error on parse/templates/server-deployment.yaml: error converting YAML to JSON: yaml: line 203: found an indentation
indicator equal to 0
```

Phase: $.persistence.existingClaim | Status: failed

Selected fields (full context in artifacts):
- `$.persistence.existingClaim = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/parse_1789323049/0000/paths/bc81b51736a9cdc4eda3>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/parse_1789323049/0000>)

### bitnami/phpmyadmin

Status: failed | Attempts: 1524

#### E152

```text
Error: YAML parse error on phpmyadmin/templates/deployment.yaml: error converting YAML to JSON: yaml: line 29: did not find expected ',' or
']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/phpmyadmin_1789323054/0000/paths/a4a0ea6ab697189bb963>)

#### E153

```text
Error: YAML parse error on phpmyadmin/templates/deployment.yaml: error converting YAML to JSON: yaml: line 60: mapping values are not
allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/phpmyadmin_1789323054/0000/paths/8e79b7dd85a286cfaddb>)

#### E154

```text
Error: YAML parse error on phpmyadmin/templates/pdb.yaml: error converting YAML to JSON: yaml: line 13: found an indentation indicator equal
to 0
```

Phase: $.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/phpmyadmin_1789323054/0000/paths/d6baed3b8998a068f471>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/phpmyadmin_1789323054/0000>)

### bitnami/pinniped

Status: failed | Attempts: 722

#### E155

```text
Error: YAML parse error on pinniped/templates/concierge/service-proxy.yaml: error converting YAML to JSON: yaml: line 15: found an
indentation indicator equal to 0
```

Phase: $.concierge.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.concierge.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/pinniped_1789323056/0000/paths/d209f09a7eedd8fb595e>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/pinniped_1789323056/0000>)

### bitnami/postgresql

Status: failed | Attempts: 714

#### E157

```text
Error: YAML parse error on postgresql/templates/primary/statefulset.yaml: error converting YAML to JSON: yaml: line 171: found an
indentation indicator equal to 0
```

Phase: $.primary.existingConfigmap | Status: failed

Selected fields (full context in artifacts):
- `$.primary.existingConfigmap = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/postgresql_1789323352/0000/paths/5840f42f3422db400ece>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/postgresql_1789323352/0000>)

### bitnami/postgresql-ha

Status: failed | Attempts: 633

#### E156

```text
Error: YAML parse error on postgresql-ha/templates/postgresql/extended-configmap.yaml: error converting YAML to JSON: yaml: line 17: could
not find expected ':'
```

Phase: $.postgresql.extendedConf | Status: failed

Selected fields (full context in artifacts):
- `$.postgresql.extendedConf = "\r0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/postgresql-ha_1789323352/0000/paths/ec3d694da0ed2a1dba65>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/postgresql-ha_1789323352/0000>)

### bitnami/prometheus

Status: failed | Attempts: 708

#### E158

```text
Error: YAML parse error on prometheus/templates/alertmanager/pdb.yaml: error converting YAML to JSON: yaml: line 15: found an indentation
indicator equal to 0
```

Phase: $.alertmanager.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.alertmanager.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/prometheus_1789323355/0000/paths/480167216d2b593f3a39>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/prometheus_1789323355/0000>)

### bitnami/pytorch

Status: failed | Attempts: 1780

#### E159

```text
Error: YAML parse error on pytorch/templates/deployment.yaml: error converting YAML to JSON: yaml: line 32: did not find expected ',' or ']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/pytorch_1789323358/0000/paths/a4a0ea6ab697189bb963>)

Phase: $.global.imagePullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.global.imagePullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/pytorch_1789323358/0000/paths/097f6358a00dddbcdd83>)

1 additional occurrences are retained in the JSON report and chart artifacts.

#### E160

```text
Error: YAML parse error on pytorch/templates/deployment.yaml: error converting YAML to JSON: yaml: line 57: mapping values are not allowed
in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/pytorch_1789323358/0000/paths/8e79b7dd85a286cfaddb>)

#### E161

```text
Error: YAML parse error on pytorch/templates/deployment.yaml: error converting YAML to JSON: yaml: line 79: could not find expected ':'
```

Phase: $.entrypoint | Status: failed

Selected fields (full context in artifacts):
- `$.entrypoint = {"file": "\n0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/pytorch_1789323358/0000/paths/cba2f2c92b4a1013a6b6>)

#### E162

```text
Error: YAML parse error on pytorch/templates/pdb.yaml: error converting YAML to JSON: yaml: line 14: found an indentation indicator equal to
0
```

Phase: $.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/pytorch_1789323358/0000/paths/d6baed3b8998a068f471>)

#### E163

```text
Error: YAML parse error on pytorch/templates/service.yaml: error converting YAML to JSON: yaml: line 15: did not find expected ',' or ']'
```

Phase: $.service.port | Status: failed

Selected fields (full context in artifacts):
- `$.service.port = [{}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/pytorch_1789323358/0000/paths/8519a498beb325a2a1ea>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/pytorch_1789323358/0000>)

### bitnami/rabbitmq

Status: failed | Attempts: 1005

#### E167

```text
Error: YAML parse error on rabbitmq/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 257: found an indentation
indicator equal to 0
```

Phase: $.persistence.existingClaim | Status: failed

Selected fields (full context in artifacts):
- `$.persistence.existingClaim = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/rabbitmq_1789323655/0000/paths/bc81b51736a9cdc4eda3>)

#### E168

```text
Error: YAML parse error on rabbitmq/templates/svc-headless.yaml: error converting YAML to JSON: yaml: line 31: found an indentation
indicator equal to 0
```

Phase: $.service.trafficDistribution | Status: failed

Selected fields (full context in artifacts):
- `$.service.trafficDistribution = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/rabbitmq_1789323655/0000/paths/76c21b9e4a991e167280>)

#### E236

Source: rabbitmq 16.0.16 / templates/validation.yaml

```text
execution error at (rabbitmq/templates/validation.yaml:6:4): VALUES VALIDATION: rabbitmq: memoryHighWatermark.type Invalid Memory high
watermark type. Valid values are "absolute" and "relative". Please set a valid mode (--set memoryHighWatermark.type="xxxx")
```

Phase: $.memoryHighWatermark.type | Status: failed

Selected fields (full context in artifacts):
- `$.memoryHighWatermark.type = ""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/rabbitmq_1789323655/0000/paths/1add63f1953bb5cbc012>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/rabbitmq_1789323655/0000>)

### bitnami/rabbitmq-cluster-operator

Status: failed | Attempts: 515

#### E164

```text
Error: YAML parse error on rabbitmq-cluster-operator/templates/cluster-operator/deployment.yaml: error converting YAML to JSON: yaml: line
91: found an indentation indicator equal to 0
```

Phase: $.clusterOperator.extraEnvVarsSecret | Status: failed

Selected fields (full context in artifacts):
- `$.clusterOperator.extraEnvVarsSecret = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/rabbitmq-cluster-operator_1789323655/0000/paths/a6041cb7b2e91c7b6c1e>)

#### E165

```text
Error: YAML parse error on rabbitmq-cluster-operator/templates/cluster-operator/service-account.yaml: error unmarshaling JSON: while
decoding JSON: json: cannot unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.clusterOperator.serviceAccount | Status: failed

Selected fields (full context in artifacts):
- `$.clusterOperator.serviceAccount = {"annotations": {"": []}}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/rabbitmq-cluster-operator_1789323655/0000/paths/6d28fd19dee82cbaef38>)

Phase: $.clusterOperator.serviceAccount.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.clusterOperator.serviceAccount.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/rabbitmq-cluster-operator_1789323655/0000/paths/abf0ef6f3f64bfaa2513>)

#### E166

```text
Error: YAML parse error on rabbitmq-cluster-operator/templates/messaging-topology-operator/deployment.yaml: error converting YAML to JSON:
yaml: line 58: found an indentation indicator equal to 0
```

Phase: $.msgTopologyOperator.hostNetwork | Status: failed

Selected fields (full context in artifacts):
- `$.msgTopologyOperator.hostNetwork = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/rabbitmq-cluster-operator_1789323655/0000/paths/2cd3ab168c8c9d9390a6>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/rabbitmq-cluster-operator_1789323655/0000>)

### bitnami/redis

Status: failed | Attempts: 593

#### E219

```text
Error: redis/templates/replicas/application.yaml:49:38 executing "redis/templates/replicas/application.yaml" at <include (print
$.Template.BasePath "/configmap.yaml") .>: error calling include: redis/templates/configmap.yaml:61:25 executing
"redis/templates/configmap.yaml" at <.password>: nil pointer evaluating interface {}.password
```

Phase: $.auth.acl | Status: failed

Selected fields (full context in artifacts):
- `$.auth.acl = {"enabled": true, "users": [null]}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/redis_1789323658/0000/paths/37081c129204c3c032e8>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/redis_1789323658/0000>)

### bitnami/redis-cluster

Status: failed | Attempts: 977

#### E169

```text
Error: YAML parse error on redis-cluster/templates/redis-statefulset.yaml: error converting YAML to JSON: yaml: line 39: did not find
expected ',' or ']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/redis-cluster_1789323660/0000/paths/a4a0ea6ab697189bb963>)

#### E170

```text
Error: YAML parse error on redis-cluster/templates/redis-statefulset.yaml: error converting YAML to JSON: yaml: line 64: mapping values are
not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/redis-cluster_1789323660/0000/paths/8e79b7dd85a286cfaddb>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/redis-cluster_1789323660/0000>)

### bitnami/redmine

Status: failed | Attempts: 931

#### E171

```text
Error: YAML parse error on redmine/charts/postgresql/templates/primary/statefulset.yaml: error converting YAML to JSON: yaml: line 173:
found an indentation indicator equal to 0
```

Phase: $.postgresql.auth.existingSecret | Status: failed

Selected fields (full context in artifacts):
- `$.postgresql.auth.existingSecret = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/redmine_1789323957/0000/paths/a0cdb2ba618083d9a8df>)

#### E172

```text
Error: YAML parse error on redmine/templates/deployment.yaml: error converting YAML to JSON: yaml: line 150: found an indentation indicator
equal to 0
```

Phase: $.persistence.existingClaim | Status: failed

Selected fields (full context in artifacts):
- `$.persistence.existingClaim = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/redmine_1789323957/0000/paths/bc81b51736a9cdc4eda3>)

#### E173

```text
Error: YAML parse error on redmine/templates/deployment.yaml: error converting YAML to JSON: yaml: line 58: mapping values are not allowed
in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/redmine_1789323957/0000/paths/8e79b7dd85a286cfaddb>)

#### E231

Source: mariadb 22.0.0 / templates/NOTES.txt

```text
execution error at (mariadb/templates/NOTES.txt:74:4): VALUES VALIDATION: mariadb: architecture Invalid architecture selected. Valid values
are "standalone" and "replication". Please set a valid architecture (--set architecture="xxxx")
```

Phase: $.mariadb.architecture | Status: failed

Selected fields (full context in artifacts):
- `$.mariadb.architecture = ""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/redmine_1789323957/0000/paths/1ff74c0fd3bc5bc52c04>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/redmine_1789323957/0000>)

### bitnami/schema-registry

Status: failed | Attempts: 1126

#### E174

```text
Error: YAML parse error on schema-registry/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 32: block sequence entries
are not allowed in this context
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[null]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/schema-registry_1789323957/0000/paths/a4a0ea6ab697189bb963>)

#### E175

```text
Error: YAML parse error on schema-registry/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 55: mapping values are not
allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/schema-registry_1789323957/0000/paths/8e79b7dd85a286cfaddb>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/schema-registry_1789323957/0000>)

### bitnami/scylladb

Status: failed | Attempts: 1245

#### E176

```text
Error: YAML parse error on scylladb/templates/individual-svc.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal
array into Go struct field .metadata.annotations. of type string
```

Phase: $.service.internal | Status: failed

Selected fields (full context in artifacts):
- `$.service.internal = {"annotations": {"": []}}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/scylladb_1789323961/0000/paths/b768ca9fe0c4043c8f02>)

#### E177

```text
Error: YAML parse error on scylladb/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 197: found an indentation
indicator equal to 0
```

Phase: $.persistence.existingClaim | Status: failed

Selected fields (full context in artifacts):
- `$.persistence.existingClaim = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/scylladb_1789323961/0000/paths/bc81b51736a9cdc4eda3>)

#### E178

```text
Error: YAML parse error on scylladb/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 35: did not find expected ',' or
']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/scylladb_1789323961/0000/paths/a4a0ea6ab697189bb963>)

#### E179

```text
Error: YAML parse error on scylladb/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 59: mapping values are not allowed
in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/scylladb_1789323961/0000/paths/8e79b7dd85a286cfaddb>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/scylladb_1789323961/0000>)

### bitnami/sealed-secrets

Status: failed | Attempts: 1678

#### E180

```text
Error: YAML parse error on sealed-secrets/templates/deployment.yaml: error converting YAML to JSON: yaml: line 29: did not find expected ','
or ']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/sealed-secrets_1789323962/0000/paths/a4a0ea6ab697189bb963>)

Phase: $.global.imagePullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.global.imagePullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/sealed-secrets_1789323962/0000/paths/097f6358a00dddbcdd83>)

#### E181

```text
Error: YAML parse error on sealed-secrets/templates/deployment.yaml: error converting YAML to JSON: yaml: line 52: mapping values are not
allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/sealed-secrets_1789323962/0000/paths/8e79b7dd85a286cfaddb>)

#### E182

```text
Error: YAML parse error on sealed-secrets/templates/pdb.yaml: error converting YAML to JSON: yaml: line 13: found an indentation indicator
equal to 0
```

Phase: $.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/sealed-secrets_1789323962/0000/paths/d6baed3b8998a068f471>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/sealed-secrets_1789323962/0000>)

### bitnami/seaweedfs

Status: failed | Attempts: 338

#### E231

Source: mariadb 22.0.0 / templates/NOTES.txt

```text
execution error at (mariadb/templates/NOTES.txt:74:4): VALUES VALIDATION: mariadb: architecture Invalid architecture selected. Valid values
are "standalone" and "replication". Please set a valid architecture (--set architecture="xxxx")
```

Phase: $.mariadb.architecture | Status: failed

Selected fields (full context in artifacts):
- `$.mariadb.architecture = ""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/seaweedfs_1789324259/0000/paths/1ff74c0fd3bc5bc52c04>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/seaweedfs_1789324259/0000>)

### bitnami/solr

Status: failed | Attempts: 973

#### E183

```text
Error: YAML parse error on solr/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 224: found an indentation indicator
equal to 0
```

Phase: $.persistence.existingClaim | Status: failed

Selected fields (full context in artifacts):
- `$.persistence.existingClaim = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/solr_1789324259/0000/paths/bc81b51736a9cdc4eda3>)

#### E184

```text
Error: YAML parse error on solr/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 64: mapping values are not allowed in
this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/solr_1789324259/0000/paths/8e79b7dd85a286cfaddb>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/solr_1789324259/0000>)

### bitnami/sonarqube

Status: failed | Attempts: 913

#### E185

```text
Error: YAML parse error on sonarqube/charts/postgresql/templates/primary/statefulset.yaml: error converting YAML to JSON: yaml: line 173:
found an indentation indicator equal to 0
```

Phase: $.postgresql.auth.existingSecret | Status: failed

Selected fields (full context in artifacts):
- `$.postgresql.auth.existingSecret = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/sonarqube_1789324263/0000/paths/a0cdb2ba618083d9a8df>)

#### E186

```text
Error: YAML parse error on sonarqube/templates/deployment.yaml: error converting YAML to JSON: yaml: line 243: found an indentation
indicator equal to 0
```

Phase: $.smtpExistingSecret | Status: failed

Selected fields (full context in artifacts):
- `$.smtpExistingSecret = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/sonarqube_1789324263/0000/paths/5787f0eface5fec9a681>)

#### E187

```text
Error: YAML parse error on sonarqube/templates/deployment.yaml: error converting YAML to JSON: yaml: line 55: mapping values are not allowed
in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/sonarqube_1789324263/0000/paths/8e79b7dd85a286cfaddb>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/sonarqube_1789324263/0000>)

### bitnami/spark

Status: failed | Attempts: 1053

#### E188

```text
Error: YAML parse error on spark/templates/pdb-worker.yaml: error converting YAML to JSON: yaml: line 14: found an indentation indicator
equal to 0
```

Phase: $.worker.pdb | Status: failed

Selected fields (full context in artifacts):
- `$.worker.pdb = {"maxUnavailable": ">0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/spark_1789324264/0000/paths/7b3233b72c7ae2177a76>)

#### E189

```text
Error: YAML parse error on spark/templates/statefulset-master.yaml: error converting YAML to JSON: yaml: line 58: mapping values are not
allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/spark_1789324264/0000/paths/8e79b7dd85a286cfaddb>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/spark_1789324264/0000>)

### bitnami/superset

Status: time-limit | Attempts: 446

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/superset_1789324562/0000>)

### bitnami/tensorflow-resnet

Status: failed | Attempts: 1912

#### E190

```text
Error: YAML parse error on tensorflow-resnet/templates/deployment.yaml: error converting YAML to JSON: yaml: line 29: did not find expected
',' or ']'
```

Phase: $.global.imagePullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.global.imagePullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/tensorflow-resnet_1789324564/0000/paths/097f6358a00dddbcdd83>)

#### E191

```text
Error: YAML parse error on tensorflow-resnet/templates/deployment.yaml: error converting YAML to JSON: yaml: line 46: found an indentation
indicator equal to 0
```

Phase: $.schedulerName | Status: failed

Selected fields (full context in artifacts):
- `$.schedulerName = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/tensorflow-resnet_1789324564/0000/paths/57504c968732d9714f10>)

#### E192

```text
Error: YAML parse error on tensorflow-resnet/templates/deployment.yaml: error converting YAML to JSON: yaml: line 93: mapping values are not
allowed in this context
```

Phase: $.server.image.tag | Status: failed

Selected fields (full context in artifacts):
- `$.server.image.tag = ""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/tensorflow-resnet_1789324564/0000/paths/80b6cb2f8dcf3d2dcb4b>)

#### E193

```text
Error: YAML parse error on tensorflow-resnet/templates/pdb.yaml: error converting YAML to JSON: yaml: line 13: found an indentation
indicator equal to 0
```

Phase: $.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/tensorflow-resnet_1789324564/0000/paths/d6baed3b8998a068f471>)

Phase: $.pdb.minAvailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.minAvailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/tensorflow-resnet_1789324564/0000/paths/07d4854a45a9e7c1eb04>)

#### E194

```text
Error: YAML parse error on tensorflow-resnet/templates/service.yaml: error converting YAML to JSON: yaml: line 13: found an indentation
indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/tensorflow-resnet_1789324564/0000/paths/6e931799d09f8182f34b>)

#### E238

Source: tensorflow-resnet 4.3.15 / templates/NOTES.txt

```text
[Diagnostic shortened; full text in artifacts] ... ely to cause degraded security and performance, broken chart features, and missing
environment variables. Unrecognized images: - 00/bitnami/tensorflow-resnet:2.19.1-debian-12-r0 If you are sure you want to proceed with
non-standard containers, you can skip container image verification by setting the global parameter 'global.security.allowInsecureImages' to
true. Further information can be obtained at https://github.com/bitnami/charts/issues/30850
```

Phase: $.client.image.registry | Status: failed

Selected fields (full context in artifacts):
- `$.client.image.registry = "00"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/tensorflow-resnet_1789324564/0000/paths/c7b0ad2c6e1b5f0ff3bc>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/tensorflow-resnet_1789324564/0000>)

### bitnami/thanos

Status: time-limit | Attempts: 256

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/thanos_1789324565/0000>)

### bitnami/tomcat

Status: failed | Attempts: 1483

#### E195

```text
Error: YAML parse error on tomcat/templates/deployment.yaml: error converting YAML to JSON: yaml: line 139: found an indentation indicator
equal to 0
```

Phase: $.persistence.existingClaim | Status: failed

Selected fields (full context in artifacts):
- `$.persistence.existingClaim = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/tomcat_1789324566/0000/paths/bc81b51736a9cdc4eda3>)

#### E196

```text
Error: YAML parse error on tomcat/templates/deployment.yaml: error converting YAML to JSON: yaml: line 29: did not find expected ',' or ']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/tomcat_1789324566/0000/paths/a4a0ea6ab697189bb963>)

#### E197

```text
Error: YAML parse error on tomcat/templates/deployment.yaml: error converting YAML to JSON: yaml: line 54: mapping values are not allowed in
this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/tomcat_1789324566/0000/paths/8e79b7dd85a286cfaddb>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/tomcat_1789324566/0000>)

### bitnami/valkey

Status: time-limit | Attempts: 610

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/valkey_1789324865/0000>)

### bitnami/valkey-cluster

Status: failed | Attempts: 916

#### E198

```text
Error: YAML parse error on valkey-cluster/templates/valkey-statefulset.yaml: error converting YAML to JSON: yaml: line 39: did not find
expected ',' or ']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/valkey-cluster_1789324866/0000/paths/a4a0ea6ab697189bb963>)

#### E199

```text
Error: YAML parse error on valkey-cluster/templates/valkey-statefulset.yaml: error converting YAML to JSON: yaml: line 63: mapping values
are not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/valkey-cluster_1789324866/0000/paths/8e79b7dd85a286cfaddb>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/valkey-cluster_1789324866/0000>)

### bitnami/vault

Status: time-limit | Attempts: 578

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/vault_1789324867/0000>)

### bitnami/victoriametrics

Status: failed | Attempts: 344

#### E200

```text
Error: YAML parse error on victoriametrics/templates/vmauth/pdb.yaml: error converting YAML to JSON: yaml: line 15: found an indentation
indicator equal to 0
```

Phase: $.vmauth.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.vmauth.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/victoriametrics_1789324870/0000/paths/937ff6fb474ef0a860f5>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/victoriametrics_1789324870/0000>)

### bitnami/whereabouts

Status: failed | Attempts: 2137

#### E201

```text
Error: YAML parse error on whereabouts/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 29: did not find expected ',' or
']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/whereabouts_1789325168/0000/paths/a4a0ea6ab697189bb963>)

Phase: $.global.imagePullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.global.imagePullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/whereabouts_1789325168/0000/paths/097f6358a00dddbcdd83>)

1 additional occurrences are retained in the JSON report and chart artifacts.

#### E202

```text
Error: YAML parse error on whereabouts/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 51: found an indentation
indicator equal to 0
```

Phase: $.schedulerName | Status: failed

Selected fields (full context in artifacts):
- `$.schedulerName = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/whereabouts_1789325168/0000/paths/57504c968732d9714f10>)

#### E203

```text
Error: YAML parse error on whereabouts/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 56: mapping values are not
allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/whereabouts_1789325168/0000/paths/8e79b7dd85a286cfaddb>)

#### E204

```text
Error: YAML parse error on whereabouts/templates/service-account.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal
array into Go struct field .metadata.annotations. of type string
```

Phase: $.serviceAccount.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/whereabouts_1789325168/0000/paths/840a8a2bc50327388c2a>)

#### E239

Source: whereabouts 1.2.20 / templates/NOTES.txt

```text
[Diagnostic shortened; full text in artifacts] ... containers is likely to cause degraded security and performance, broken chart features,
and missing environment variables. Unrecognized images: - docker.io/00:0.9.2-debian-12-r2 If you are sure you want to proceed with
non-standard containers, you can skip container image verification by setting the global parameter 'global.security.allowInsecureImages' to
true. Further information can be obtained at https://github.com/bitnami/charts/issues/30850
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "00"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/whereabouts_1789325168/0000/paths/3f7165f1837241716c3c>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/whereabouts_1789325168/0000>)

### bitnami/wildfly

Status: failed | Attempts: 1523

#### E205

```text
Error: YAML parse error on wildfly/templates/deployment.yaml: error converting YAML to JSON: yaml: line 182: found an indentation indicator
equal to 0
```

Phase: $.persistence.existingClaim | Status: failed

Selected fields (full context in artifacts):
- `$.persistence.existingClaim = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/wildfly_1789325168/0000/paths/bc81b51736a9cdc4eda3>)

#### E206

```text
Error: YAML parse error on wildfly/templates/deployment.yaml: error converting YAML to JSON: yaml: line 31: did not find expected ',' or ']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/wildfly_1789325168/0000/paths/a4a0ea6ab697189bb963>)

#### E207

```text
Error: YAML parse error on wildfly/templates/deployment.yaml: error converting YAML to JSON: yaml: line 68: mapping values are not allowed
in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/wildfly_1789325168/0000/paths/8e79b7dd85a286cfaddb>)

#### E208

```text
Error: YAML parse error on wildfly/templates/pdb.yaml: error converting YAML to JSON: yaml: line 13: found an indentation indicator equal to
0
```

Phase: $.pdb.maxUnavailable | Status: failed

Selected fields (full context in artifacts):
- `$.pdb.maxUnavailable = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/wildfly_1789325168/0000/paths/d6baed3b8998a068f471>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/wildfly_1789325168/0000>)

### bitnami/wordpress

Status: failed | Attempts: 853

#### E209

```text
Error: YAML parse error on wordpress/templates/deployment.yaml: error converting YAML to JSON: yaml: line 256: found an indentation
indicator equal to 0
```

Phase: $.persistence.existingClaim | Status: failed

Selected fields (full context in artifacts):
- `$.persistence.existingClaim = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/wordpress_1789325170/0000/paths/bc81b51736a9cdc4eda3>)

#### E210

```text
Error: YAML parse error on wordpress/templates/deployment.yaml: error converting YAML to JSON: yaml: line 257: found an indentation
indicator equal to 0
```

Phase: $.smtpExistingSecret | Status: failed

Selected fields (full context in artifacts):
- `$.smtpExistingSecret = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/wordpress_1789325170/0000/paths/5787f0eface5fec9a681>)

#### E231

Source: mariadb 22.0.0 / templates/NOTES.txt

```text
execution error at (mariadb/templates/NOTES.txt:74:4): VALUES VALIDATION: mariadb: architecture Invalid architecture selected. Valid values
are "standalone" and "replication". Please set a valid architecture (--set architecture="xxxx")
```

Phase: $.mariadb.architecture | Status: failed

Selected fields (full context in artifacts):
- `$.mariadb.architecture = ""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/wordpress_1789325170/0000/paths/1ff74c0fd3bc5bc52c04>)

#### E232

Source: memcached 7.9.7 / templates/NOTES.txt

```text
execution error at (memcached/templates/NOTES.txt:46:4): VALUES VALIDATION: memcached: auth.username Enabling authentication requires
setting a valid admin username. Please set a valid username (--set auth.username="xxxx") memcached:
containerSecurityContext.readOnlyRootFilesystem Enabling authentication is not compatible with using a read-only filesystem. Please disable
it (--set containerSecurityContext.readOnlyRootFilesystem=false)
```

Phase: $.memcached | Status: failed

Selected fields (full context in artifacts):
- `$.memcached = {"auth": {"enabled": true}, "enabled": true}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/wordpress_1789325170/0000/paths/db425870801cbb8fd099>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/wordpress_1789325170/0000>)

### bitnami/zipkin

Status: failed | Attempts: 1

#### E241

```text
invalid rendered YAML: more indented follow up line than first in a block scalar in "<unicode string>", line 474, column 15: set -o errexit
^ (line: 474)
```

Phase: chart | Status: failed

No triggering values were recorded for this diagnostic.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/zipkin_1789325174/0000>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/zipkin_1789325174/0000>)

### bitnami/zookeeper

Status: failed | Attempts: 1241

#### E211

```text
Error: YAML parse error on zookeeper/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 189: found an indentation
indicator equal to 0
```

Phase: $.persistence.existingClaim | Status: failed

Selected fields (full context in artifacts):
- `$.persistence.existingClaim = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/zookeeper_1789325176/0000/paths/bc81b51736a9cdc4eda3>)

#### E212

```text
Error: YAML parse error on zookeeper/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 191: could not find expected ':'
```

Phase: $.persistence.dataLogDir | Status: failed

Selected fields (full context in artifacts):
- `$.persistence.dataLogDir = {"existingClaim": "\r0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/zookeeper_1789325176/0000/paths/cd88da17db57f0ffc104>)

#### E213

```text
Error: YAML parse error on zookeeper/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 39: did not find expected ',' or
']'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [[{}]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/zookeeper_1789325176/0000/paths/a4a0ea6ab697189bb963>)

#### E214

```text
Error: YAML parse error on zookeeper/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 64: mapping values are not
allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"tag": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/zookeeper_1789325176/0000/paths/8e79b7dd85a286cfaddb>)

#### E240

Source: zookeeper 13.8.9 / templates/NOTES.txt

```text
execution error at (zookeeper/templates/NOTES.txt:79:4): VALUES VALIDATION: zookeeper: auth.client.enabled In order to enable client-server
authentication, you need to provide the list of users to be created and the user to use for clients authentication.
```

Phase: $.auth.client.enabled | Status: failed

Selected fields (full context in artifacts):
- `$.auth.client.enabled = true`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/zookeeper_1789325176/0000/paths/63842ee46576ca4d1d3b>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/bitnami-runs/bitnami-charts_1789311940/runs/zookeeper_1789325176/0000>)
