# Prometheus Community Helm chart scan

<!-- toc:start -->
<details>
<summary>Table of contents</summary>

- [Status counts](#status-counts)
- [Settings](#settings)
- [Errors](#errors)
- [Charts](#charts)
  - [charts/alertmanager](#chartsalertmanager)
  - [charts/alertmanager-snmp-notifier](#chartsalertmanager-snmp-notifier)
  - [charts/jiralert](#chartsjiralert)
  - [charts/kube-prometheus-stack](#chartskube-prometheus-stack)
  - [charts/kube-prometheus-stack/charts/crds](#chartskube-prometheus-stackchartscrds)
  - [charts/kube-state-metrics](#chartskube-state-metrics)
  - [charts/prom-label-proxy](#chartsprom-label-proxy)
  - [charts/prometheus](#chartsprometheus)
  - [charts/prometheus-adapter](#chartsprometheus-adapter)
  - [charts/prometheus-blackbox-exporter](#chartsprometheus-blackbox-exporter)
  - [charts/prometheus-cloudwatch-exporter](#chartsprometheus-cloudwatch-exporter)
  - [charts/prometheus-conntrack-stats-exporter](#chartsprometheus-conntrack-stats-exporter)
  - [charts/prometheus-consul-exporter](#chartsprometheus-consul-exporter)
  - [charts/prometheus-couchdb-exporter](#chartsprometheus-couchdb-exporter)
  - [charts/prometheus-druid-exporter](#chartsprometheus-druid-exporter)
  - [charts/prometheus-elasticsearch-exporter](#chartsprometheus-elasticsearch-exporter)
  - [charts/prometheus-fastly-exporter](#chartsprometheus-fastly-exporter)
  - [charts/prometheus-ipmi-exporter](#chartsprometheus-ipmi-exporter)
  - [charts/prometheus-json-exporter](#chartsprometheus-json-exporter)
  - [charts/prometheus-kafka-exporter](#chartsprometheus-kafka-exporter)
  - [charts/prometheus-memcached-exporter](#chartsprometheus-memcached-exporter)
  - [charts/prometheus-modbus-exporter](#chartsprometheus-modbus-exporter)
  - [charts/prometheus-mongodb-exporter](#chartsprometheus-mongodb-exporter)
  - [charts/prometheus-mysql-exporter](#chartsprometheus-mysql-exporter)
  - [charts/prometheus-nats-exporter](#chartsprometheus-nats-exporter)
  - [charts/prometheus-nginx-exporter](#chartsprometheus-nginx-exporter)
  - [charts/prometheus-node-exporter](#chartsprometheus-node-exporter)
  - [charts/prometheus-operator-admission-webhook](#chartsprometheus-operator-admission-webhook)
  - [charts/prometheus-operator-crds](#chartsprometheus-operator-crds)
  - [charts/prometheus-operator-crds/charts/crds](#chartsprometheus-operator-crdschartscrds)
  - [charts/prometheus-pgbouncer-exporter](#chartsprometheus-pgbouncer-exporter)
  - [charts/prometheus-pingdom-exporter](#chartsprometheus-pingdom-exporter)
  - [charts/prometheus-pingmesh-exporter](#chartsprometheus-pingmesh-exporter)
  - [charts/prometheus-postgres-exporter](#chartsprometheus-postgres-exporter)
  - [charts/prometheus-pushgateway](#chartsprometheus-pushgateway)
  - [charts/prometheus-rabbitmq-exporter](#chartsprometheus-rabbitmq-exporter)
  - [charts/prometheus-redis-exporter](#chartsprometheus-redis-exporter)
  - [charts/prometheus-smartctl-exporter](#chartsprometheus-smartctl-exporter)
  - [charts/prometheus-snmp-exporter](#chartsprometheus-snmp-exporter)
  - [charts/prometheus-sql-exporter](#chartsprometheus-sql-exporter)
  - [charts/prometheus-stackdriver-exporter](#chartsprometheus-stackdriver-exporter)
  - [charts/prometheus-statsd-exporter](#chartsprometheus-statsd-exporter)
  - [charts/prometheus-systemd-exporter](#chartsprometheus-systemd-exporter)
  - [charts/prometheus-to-sd](#chartsprometheus-to-sd)
  - [charts/prometheus-windows-exporter](#chartsprometheus-windows-exporter)
  - [charts/prometheus-yet-another-cloudwatch-exporter](#chartsprometheus-yet-another-cloudwatch-exporter)

</details>
<!-- toc:end -->

Visited all **46 discovered charts** with **--filter**, four workers, and a **five-minute test budget per chart**. No scan-wide deadline was
imposed.

Recorded **94,833 test attempts** in **50.6 minutes**. Attempts include shrinking and repeated inputs; they are not counts of unique inputs
or confirmed bugs.

**Findings:** 1 baseline-failed; 1 error; 41 failed; 1 missing-values; 2 time-limit.

**value-path:** 317 failed; 5 generation-error; 879 passed; 34 time-limit.

Observed failures include chart validation rejections, rendering failures, and possible tooling limitations. Inferred inputs are not an
authoritative chart contract. Findings need triage before being called chart defects; time-limited coverage remains incomplete.

Checks: dependency build in isolated copies, Helm lint, Helm template with values-schema checks, and built-in manifest checks. External
kubeconform/kubesec validation was not configured.

Source: `third_party/prometheus-community-helm-charts` at `732bf3642c931946f1962fbd2e1b694ce8827e77`; Helm 4.3.0. Per-worker dependency
caches are isolated. Each primary chart has one dedicated job; nested results from parent jobs are retained separately and excluded from
totals.

[Combined PDF](<https://github.com/astrivant/hypothesis-helm/blob/main/docs/reports/prometheus.pdf>) ·
[Aggregate data](<https://github.com/astrivant/hypothesis-helm/blob/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/scan.json.gz>)
·
[Raw logs and provenance](<https://github.com/astrivant/hypothesis-helm/blob/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/README.md>)

Generated C0/C1 controls are excluded except LF and CR. Other Unicode text remains eligible; explicit finite domains are unchanged.
Dependency preparation is excluded from chart testing budgets.

Directory: third_party/prometheus-community-helm-charts
Started (Unix epoch): 1789325515
Elapsed (wall clock): 3037.00 seconds
Chart testing: 11835.98 seconds
Dependency preparation: 6.40 seconds (excluded from testing budgets)
Charts discovered: 46
Scan status: completed
Discovery complete: True
Unstarted charts: 0

Results describe the tested sample; they do not prove chart correctness.
Baseline-only, skipped, blocked, and incomplete charts are not property-test passes.

## Status counts

1 baseline-failed; 1 error; 41 failed; 1 missing-values; 2 time-limit.

## Settings

Filtering: True | Seed: 0 | Traversal: random
Chart timeout: 300.0 seconds | Workers: 4
Complete settings are retained in the JSON report.

## Errors

281 distinct diagnostics across 327 occurrences; 46 repeats grouped.
Diagnostics and their triggering inputs are grouped under each chart below.
Up to two examples per diagnostic and six fields per example are shown. Long values and diagnostics are shortened.
Full inputs, diagnostics, and remaining cases are retained in JSON and linked artifacts.
Selected fields identify what the test varied, not an independently proven cause.

## Charts

### charts/alertmanager

Status: error | Attempts: N/A

#### E279

```text
recursive schema at ('config', 'route', 'routes', '*')
```

Phase: chart | Status: error

No triggering values were recorded for this diagnostic.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/alertmanager_1789325515/0000>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/alertmanager_1789325515/0000>)

### charts/alertmanager-snmp-notifier

Status: failed | Attempts: 2501

#### E002

```text
Error: YAML parse error on alertmanager-snmp-notifier/templates/deployment.yaml: error converting YAML to JSON: yaml: line 29: did not find
expected key
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"repository": "\""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/alertmanager-snmp-notifier_1789325516/0000/paths/8e79b7dd85a286cfaddb>)

#### E003

```text
Error: YAML parse error on alertmanager-snmp-notifier/templates/deployment.yaml: error converting YAML to JSON: yaml: line 40: did not find
expected ',' or ']'
```

Phase: $.snmpNotifier.snmpAuthenticationPasswordSecret | Status: failed

Selected fields (full context in artifacts):
- `$.snmpNotifier.snmpAuthenticationPasswordSecret = {"key": [null, []]}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/alertmanager-snmp-notifier_1789325516/0000/paths/740729cd8e617ed3beb2>)

Phase: $.snmpNotifier.snmpPrivatePasswordSecret | Status: failed

Selected fields (full context in artifacts):
- `$.snmpNotifier.snmpPrivatePasswordSecret = {"key": [null, []]}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/alertmanager-snmp-notifier_1789325516/0000/paths/16f6c651571833310a03>)

#### E004

```text
Error: YAML parse error on alertmanager-snmp-notifier/templates/service.yaml: error converting YAML to JSON: yaml: line 12: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/alertmanager-snmp-notifier_1789325516/0000/paths/6e931799d09f8182f34b>)

#### E252

```text
Error: alertmanager-snmp-notifier/templates/secrets.yaml:18:53 executing "alertmanager-snmp-notifier/templates/secrets.yaml" at <b64enc>:
wrong type for value; expected string; got []interface {}
```

Phase: $.snmpNotifier.snmpCommunity | Status: failed

Selected fields (full context in artifacts):
- `$.snmpNotifier.snmpCommunity = [null]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/alertmanager-snmp-notifier_1789325516/0000/paths/b739e43dd14f4d2948d2>)

#### E271

```text
[Diagnostic shortened; full text in artifacts] ... ting it again. It is also possible that applying this much filtering will distort the
domain and/or distribution of the test, leaving your testing less rigorous than expected. If you expect this many inputs to be filtered out
during generation, you can disable this health check with @settings(suppress_health_check=[HealthCheck.filter_too_much]). See
https://hypothesis.readthedocs.io/en/latest/reference/api.html#hypothesis.HealthCheck for details.
```

Phase: $.ingress.tls[*].hosts[*] | Status: generation-error

Selected fields (full context in artifacts):
- No supplied value at the selected paths.
Absent from overrides: $.ingress.tls["*"].hosts["*"]. Defaults may still apply.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/alertmanager-snmp-notifier_1789325516/0000/paths/ae968bea05135d8fcb71>)

#### E277

```text
invalid rendered YAML: while constructing a mapping in "<unicode string>", line 27, column 3: user-object-1-template.tpl: | ^ (line: 27)
found duplicate key "user-object-1-template.tpl" with value "" (original value: "") in "<unicode string>", line 29, column 3:
user-object-1-template.tpl: | ^ (line: 29) To suppress this check see: https://yaml.dev/doc/ruamel.yaml/api/#Duplicate_keys
```

Phase: $.snmpNotifier.trapTemplates | Status: failed

Selected fields (full context in artifacts):
- `$.snmpNotifier.trapTemplates = {"userObjects": [{"subOid": 1, "template": ""}, {"subOid": 1, "template": ""}]}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/alertmanager-snmp-notifier_1789325516/0000/paths/4d179d6e1f6346395f50>)

#### E281

```text
resource has no nonempty apiVersion
```

Phase: $.route.main | Status: failed

Selected fields (full context in artifacts):
- `$.route.main = {"apiVersion": "0", "enabled": true}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/alertmanager-snmp-notifier_1789325516/0000/paths/4040b7d9468c882f9251>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/alertmanager-snmp-notifier_1789325516/0000>)

### charts/jiralert

Status: failed | Attempts: 2398

#### E005

```text
Error: YAML parse error on jiralert/templates/deployment.yaml: error converting YAML to JSON: yaml: line 43: block sequence entries are not
allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "-"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/jiralert_1789325515/0000/paths/8e79b7dd85a286cfaddb>)

#### E006

```text
Error: YAML parse error on jiralert/templates/serviceaccount.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal
array into Go struct field .metadata.annotations. of type string
```

Phase: $.serviceAccount.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/jiralert_1789325515/0000/paths/840a8a2bc50327388c2a>)

#### E281

```text
resource has no nonempty apiVersion
```

Phase: $.route.main | Status: failed

Selected fields (full context in artifacts):
- `$.route.main = {"apiVersion": "0", "enabled": true}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/jiralert_1789325515/0000/paths/4040b7d9468c882f9251>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/jiralert_1789325515/0000>)

### charts/kube-prometheus-stack

Status: time-limit | Attempts: 132

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/kube-prometheus-stack_1789325516/0000>)

### charts/kube-prometheus-stack/charts/crds

Status: failed | Attempts: 1

#### E274

```text
chart rendered no resources
```

Phase: chart | Status: failed

No triggering values were recorded for this diagnostic.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/crds_1789325517/0000>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/crds_1789325517/0000>)

### charts/kube-state-metrics

Status: failed | Attempts: 1427

#### E007

```text
Error: YAML parse error on kube-state-metrics/templates/deployment.yaml: error converting YAML to JSON: yaml: line 50: found an indentation
indicator equal to 0
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": ">0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/kube-state-metrics_1789325518/0000/paths/8e79b7dd85a286cfaddb>)

#### E008

```text
Error: YAML parse error on kube-state-metrics/templates/extra-manifests.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go value of type util.SimpleHead
```

Phase: $.extraManifests | Status: failed

Selected fields (full context in artifacts):
- `$.extraManifests = [[]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/kube-state-metrics_1789325518/0000/paths/48d9e37d2076ecabc7a6>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/kube-state-metrics_1789325518/0000>)

### charts/prom-label-proxy

Status: failed | Attempts: 2010

#### E009

```text
Error: YAML parse error on prom-label-proxy/templates/deployment.yaml: error converting YAML to JSON: yaml: line 35: block sequence entries
are not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "-"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prom-label-proxy_1789325817/0000/paths/8e79b7dd85a286cfaddb>)

#### E010

```text
Error: YAML parse error on prom-label-proxy/templates/deployment.yaml: error converting YAML to JSON: yaml: line 44: found an indentation
indicator equal to 0
```

Phase: $.config | Status: failed

Selected fields (full context in artifacts):
- `$.config = {"listenAddress": ">0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prom-label-proxy_1789325817/0000/paths/24e6ce8e5165b2c58d67>)

#### E011

```text
Error: YAML parse error on prom-label-proxy/templates/service.yaml: error converting YAML to JSON: yaml: line 13: found an indentation
indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prom-label-proxy_1789325817/0000/paths/6e931799d09f8182f34b>)

#### E012

```text
Error: YAML parse error on prom-label-proxy/templates/serviceaccount.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.serviceAccount.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prom-label-proxy_1789325817/0000/paths/840a8a2bc50327388c2a>)

#### E253

```text
Error: prom-label-proxy/templates/extra-objects.yaml:8:10 executing "prom-label-proxy/templates/extra-objects.yaml" at <$extraObjects>:
range can't iterate over 1
```

Phase: $.extraManifests | Status: failed

Selected fields (full context in artifacts):
- `$.extraManifests = 1`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prom-label-proxy_1789325817/0000/paths/48d9e37d2076ecabc7a6>)

#### E281

```text
resource has no nonempty apiVersion
```

Phase: $.route.main | Status: failed

Selected fields (full context in artifacts):
- `$.route.main = {"apiVersion": "0", "enabled": true}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prom-label-proxy_1789325817/0000/paths/4040b7d9468c882f9251>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prom-label-proxy_1789325817/0000>)

### charts/prometheus

Status: failed | Attempts: 1

#### E278

```text
invalid rendered YAML: while scanning for the next token found character '\t' that cannot start any token in "<unicode string>", line 1359,
column 21: - apiVersion: v1 ^ (line: 1359)
```

Phase: chart | Status: failed

No triggering values were recorded for this diagnostic.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus_1789325817/0000>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus_1789325817/0000>)

### charts/prometheus-adapter

Status: failed | Attempts: 1834

#### E013

```text
Error: YAML parse error on prometheus-adapter/templates/custom-metrics-cluster-role.yaml: error converting YAML to JSON: yaml: line 18:
could not find expected ':'
```

Phase: $.rbac.customMetrics | Status: failed

Selected fields (full context in artifacts):
- `$.rbac.customMetrics = {"resources": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-adapter_1789325819/0000/paths/f7ef3eb5b5c382b61dc1>)

#### E014

```text
Error: YAML parse error on prometheus-adapter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 45: block sequence
entries are not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "-"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-adapter_1789325819/0000/paths/8e79b7dd85a286cfaddb>)

#### E015

```text
Error: YAML parse error on prometheus-adapter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 97: did not find expected
',' or ']'
```

Phase: $.image.pullSecrets[*] | Status: failed

Selected fields (full context in artifacts):
- No supplied value at the selected paths.
Absent from overrides: $.image.pullSecrets["*"]. Defaults may still apply.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-adapter_1789325819/0000/paths/6c7a809f27215e41451b>)

#### E016

```text
Error: YAML parse error on prometheus-adapter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 98: mapping values are
not allowed in this context
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [{"0": null, "": ""}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-adapter_1789325819/0000/paths/a4a0ea6ab697189bb963>)

#### E017

```text
Error: YAML parse error on prometheus-adapter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 99: did not find expected
',' or ']'
```

Phase: $.rules.existing | Status: failed

Selected fields (full context in artifacts):
- `$.rules.existing = [{}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-adapter_1789325819/0000/paths/d873c3fefbb570af30bd>)

#### E018

```text
Error: YAML parse error on prometheus-adapter/templates/extra-objects.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go value of type util.SimpleHead
```

Phase: $.extraManifests | Status: failed

Selected fields (full context in artifacts):
- `$.extraManifests = [[]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-adapter_1789325819/0000/paths/48d9e37d2076ecabc7a6>)

#### E019

```text
Error: YAML parse error on prometheus-adapter/templates/service.yaml: error converting YAML to JSON: yaml: line 23: found an indentation
indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-adapter_1789325819/0000/paths/6e931799d09f8182f34b>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-adapter_1789325819/0000>)

### charts/prometheus-blackbox-exporter

Status: failed | Attempts: 1620

#### E020

```text
Error: YAML parse error on prometheus-blackbox-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 44: could not
find expected ':'
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"digest": "\n0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-blackbox-exporter_1789325820/0000/paths/8e79b7dd85a286cfaddb>)

#### E021

```text
Error: YAML parse error on prometheus-blackbox-exporter/templates/extra-manifests.yaml: error unmarshaling JSON: while decoding JSON: json:
cannot unmarshal array into Go value of type util.SimpleHead
```

Phase: $.extraManifests | Status: failed

Selected fields (full context in artifacts):
- `$.extraManifests = [[]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-blackbox-exporter_1789325820/0000/paths/48d9e37d2076ecabc7a6>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-blackbox-exporter_1789325820/0000>)

### charts/prometheus-cloudwatch-exporter

Status: failed | Attempts: 2496

#### E022

```text
Error: YAML parse error on prometheus-cloudwatch-exporter/templates/configmap.yaml: error converting YAML to JSON: yaml: line 16: could not
find expected ':'
```

Phase: $.config | Status: failed

Selected fields (full context in artifacts):
- `$.config = "\r0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-cloudwatch-exporter_1789325826/0000/paths/24e6ce8e5165b2c58d67>)

#### E023

```text
Error: YAML parse error on prometheus-cloudwatch-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 33: did not
find expected key
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-cloudwatch-exporter_1789325826/0000/paths/3f7165f1837241716c3c>)

#### E024

```text
Error: YAML parse error on prometheus-cloudwatch-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 35: block
sequence entries are not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "-"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-cloudwatch-exporter_1789325826/0000/paths/8e79b7dd85a286cfaddb>)

#### E025

```text
Error: YAML parse error on prometheus-cloudwatch-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 35: could not
find expected ':'
```

Phase: $.extraEnv | Status: failed

Selected fields (full context in artifacts):
- `$.extraEnv = true`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-cloudwatch-exporter_1789325826/0000/paths/fcdb2a98d24bd18c59a4>)

#### E026

```text
Error: YAML parse error on prometheus-cloudwatch-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 37: did not
find expected ',' or ']'
```

Phase: $.aws.secret.name | Status: failed

Selected fields (full context in artifacts):
- `$.aws.secret.name = [{}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-cloudwatch-exporter_1789325826/0000/paths/c08b45ef27291722546b>)

#### E027

```text
Error: YAML parse error on prometheus-cloudwatch-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 40: could not
find expected ':'
```

Phase: $.aws.secret | Status: failed

Selected fields (full context in artifacts):
- `$.aws.secret = {"name": "\r0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-cloudwatch-exporter_1789325826/0000/paths/0b35a16c8f7c5b24fdc1>)

#### E028

```text
Error: YAML parse error on prometheus-cloudwatch-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 42: found an
indentation indicator equal to 0
```

Phase: $.livenessProbe.path | Status: failed

Selected fields (full context in artifacts):
- `$.livenessProbe.path = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-cloudwatch-exporter_1789325826/0000/paths/e19405645cb473fbf397>)

#### E029

```text
Error: YAML parse error on prometheus-cloudwatch-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 51: found an
indentation indicator equal to 0
```

Phase: $.readinessProbe.path | Status: failed

Selected fields (full context in artifacts):
- `$.readinessProbe.path = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-cloudwatch-exporter_1789325826/0000/paths/6e63684264db9d622def>)

#### E030

```text
Error: YAML parse error on prometheus-cloudwatch-exporter/templates/deployment.yaml: error unmarshaling JSON: while decoding JSON: json:
cannot unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.deployment.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.deployment.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-cloudwatch-exporter_1789325826/0000/paths/4d0453515f852ad02b1c>)

#### E031

```text
Error: YAML parse error on prometheus-cloudwatch-exporter/templates/pdb.yaml: error converting YAML to JSON: yaml: line 11: did not find
expected ',' or ']'
```

Phase: $.podDisruptionBudget | Status: failed

Selected fields (full context in artifacts):
- `$.podDisruptionBudget = {"enabled": true, "minAvailable": [{}]}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-cloudwatch-exporter_1789325826/0000/paths/77238443649996846759>)

#### E032

```text
Error: YAML parse error on prometheus-cloudwatch-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 14: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-cloudwatch-exporter_1789325826/0000/paths/6e931799d09f8182f34b>)

#### E033

```text
Error: YAML parse error on prometheus-cloudwatch-exporter/templates/serviceaccount.yaml: error unmarshaling JSON: while decoding JSON: json:
cannot unmarshal array into Go struct field .metadata.annotations of type map[string]string
```

Phase: $.serviceAccount.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount.annotations = [null]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-cloudwatch-exporter_1789325826/0000/paths/840a8a2bc50327388c2a>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-cloudwatch-exporter_1789325826/0000>)

### charts/prometheus-conntrack-stats-exporter

Status: failed | Attempts: 3079

#### E034

```text
Error: YAML parse error on prometheus-conntrack-stats-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 38: did
not find expected key
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-conntrack-stats-exporter_1789326118/0000/paths/3f7165f1837241716c3c>)

#### E035

```text
Error: YAML parse error on prometheus-conntrack-stats-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 40: block
sequence entries are not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "-"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-conntrack-stats-exporter_1789326118/0000/paths/8e79b7dd85a286cfaddb>)

#### E036

```text
Error: YAML parse error on prometheus-conntrack-stats-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 40: found
an indentation indicator equal to 0
```

Phase: $.image.pullPolicy | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullPolicy = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-conntrack-stats-exporter_1789326118/0000/paths/eb979f1d0345157961ea>)

#### E037

```text
Error: YAML parse error on prometheus-conntrack-stats-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 54: found
unexpected end of stream
```

Phase: $.image.tag | Status: failed

Selected fields (full context in artifacts):
- `$.image.tag = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-conntrack-stats-exporter_1789326118/0000/paths/7e365cc9986c8fb6c4ad>)

#### E038

```text
Error: YAML parse error on prometheus-conntrack-stats-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 7: found
an indentation indicator equal to 0
```

Phase: $.nameOverride | Status: failed

Selected fields (full context in artifacts):
- `$.nameOverride = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-conntrack-stats-exporter_1789326118/0000/paths/0ce120cfa523ba37df61>)

#### E039

```text
Error: YAML parse error on prometheus-conntrack-stats-exporter/templates/podmonitor.yaml: error converting YAML to JSON: yaml: line 18:
block sequence entries are not allowed in this context
```

Phase: $.podMonitor | Status: failed

Selected fields (full context in artifacts):
- `$.podMonitor = {"enabled": true, "interval": "-"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-conntrack-stats-exporter_1789326118/0000/paths/7d8a2fdc40bb146c86bf>)

#### E040

```text
Error: YAML parse error on prometheus-conntrack-stats-exporter/templates/serviceaccount.yaml: error unmarshaling JSON: while decoding JSON:
json: cannot unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.serviceAccount.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-conntrack-stats-exporter_1789326118/0000/paths/840a8a2bc50327388c2a>)

Phase: $.serviceAccount | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount = {"annotations": {"": []}}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-conntrack-stats-exporter_1789326118/0000/paths/7a010717afb4691aaeb8>)

#### E280

```text
resource has no metadata.name
```

Phase: $.serviceAccount.name | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount.name = "0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-conntrack-stats-exporter_1789326118/0000/paths/815bf9b751b356e044f0>)

Phase: $.fullnameOverride | Status: failed

Selected fields (full context in artifacts):
- `$.fullnameOverride = "0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-conntrack-stats-exporter_1789326118/0000/paths/e2f7761f901d86846684>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-conntrack-stats-exporter_1789326118/0000>)

### charts/prometheus-consul-exporter

Status: failed | Attempts: 3339

#### E041

```text
Error: YAML parse error on prometheus-consul-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 24: did not find
expected key
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-consul-exporter_1789326120/0000/paths/3f7165f1837241716c3c>)

Phase: $.image.tag | Status: failed

Selected fields (full context in artifacts):
- `$.image.tag = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-consul-exporter_1789326120/0000/paths/7e365cc9986c8fb6c4ad>)

#### E042

```text
Error: YAML parse error on prometheus-consul-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 26: block
sequence entries are not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "-"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-consul-exporter_1789326120/0000/paths/8e79b7dd85a286cfaddb>)

#### E043

```text
Error: YAML parse error on prometheus-consul-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 26: found an
indentation indicator equal to 0
```

Phase: $.image.pullPolicy | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullPolicy = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-consul-exporter_1789326120/0000/paths/eb979f1d0345157961ea>)

#### E044

```text
Error: YAML parse error on prometheus-consul-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 47: found
unexpected end of stream
```

Phase: $.options | Status: failed

Selected fields (full context in artifacts):
- `$.options = {"\\": null}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-consul-exporter_1789326120/0000/paths/d9954b8d56feade1f3bf>)

#### E045

```text
Error: YAML parse error on prometheus-consul-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 13: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-consul-exporter_1789326120/0000/paths/6e931799d09f8182f34b>)

#### E046

```text
Error: YAML parse error on prometheus-consul-exporter/templates/service.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.service.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.service.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-consul-exporter_1789326120/0000/paths/98a2bca1991be60ae38a>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-consul-exporter_1789326120/0000>)

### charts/prometheus-couchdb-exporter

Status: failed | Attempts: 2327

#### E047

```text
Error: YAML parse error on prometheus-couchdb-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 24: did not find
expected key
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-couchdb-exporter_1789326121/0000/paths/3f7165f1837241716c3c>)

#### E048

```text
Error: YAML parse error on prometheus-couchdb-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 26: found an
indentation indicator equal to 0
```

Phase: $.image.pullPolicy | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullPolicy = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-couchdb-exporter_1789326121/0000/paths/eb979f1d0345157961ea>)

#### E049

```text
Error: YAML parse error on prometheus-couchdb-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 27: did not find
expected key
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "\""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-couchdb-exporter_1789326121/0000/paths/8e79b7dd85a286cfaddb>)

#### E050

```text
Error: YAML parse error on prometheus-couchdb-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 30: did not find
expected '-' indicator
```

Phase: $.couchdb.uri | Status: failed

Selected fields (full context in artifacts):
- `$.couchdb.uri = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-couchdb-exporter_1789326121/0000/paths/8b786262570e7f3dc202>)

#### E051

```text
Error: YAML parse error on prometheus-couchdb-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 32: did not find
expected '-' indicator
```

Phase: $.couchdb.password | Status: failed

Selected fields (full context in artifacts):
- `$.couchdb.password = {"\"": null}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-couchdb-exporter_1789326121/0000/paths/9dfd6b29ae49b3b8c573>)

Phase: $.couchdb.username | Status: failed

Selected fields (full context in artifacts):
- `$.couchdb.username = {"\"": null}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-couchdb-exporter_1789326121/0000/paths/988bae84451493337ebe>)

#### E052

```text
Error: YAML parse error on prometheus-couchdb-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 48: found
unexpected end of stream
```

Phase: $.couchdb | Status: failed

Selected fields (full context in artifacts):
- `$.couchdb = {"databases": "\""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-couchdb-exporter_1789326121/0000/paths/5303eea7d1d40abe5463>)

Phase: $.couchdb.databases | Status: failed

Selected fields (full context in artifacts):
- `$.couchdb.databases = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-couchdb-exporter_1789326121/0000/paths/6c0f1c8e092a3a1c0c33>)

#### E053

```text
Error: YAML parse error on prometheus-couchdb-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 11: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-couchdb-exporter_1789326121/0000/paths/6e931799d09f8182f34b>)

#### E054

```text
Error: YAML parse error on prometheus-couchdb-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 13: could not find
expected ':'
```

Phase: $.service | Status: failed

Selected fields (full context in artifacts):
- `$.service = {"type": "\r0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-couchdb-exporter_1789326121/0000/paths/da628aa79e50e022e4ff>)

#### E055

```text
Error: YAML parse error on prometheus-couchdb-exporter/templates/serviceaccount.yaml: error unmarshaling JSON: while decoding JSON: json:
cannot unmarshal array into Go struct field .metadata.name of type string
```

Phase: $.serviceAccount.name | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount.name = [null]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-couchdb-exporter_1789326121/0000/paths/815bf9b751b356e044f0>)

#### E254

```text
Error: prometheus-couchdb-exporter/templates/NOTES.txt:3:17 executing "prometheus-couchdb-exporter/templates/NOTES.txt" at
<.Values.ingress.hosts>: range can't iterate over false
```

Phase: $.ingress | Status: failed

Selected fields (full context in artifacts):
- `$.ingress = {"enabled": true, "hosts": false}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-couchdb-exporter_1789326121/0000/paths/94ed38bb417a953196c3>)

#### E280

```text
resource has no metadata.name
```

Phase: $.serviceAccount | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount = {"name": "0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-couchdb-exporter_1789326121/0000/paths/7a010717afb4691aaeb8>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-couchdb-exporter_1789326121/0000>)

### charts/prometheus-druid-exporter

Status: failed | Attempts: 2483

#### E056

```text
Error: YAML parse error on prometheus-druid-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 31: found an
indentation indicator equal to 0
```

Phase: $.druidURL | Status: failed

Selected fields (full context in artifacts):
- `$.druidURL = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-druid-exporter_1789326127/0000/paths/d652ba0905ba99b2db9a>)

#### E057

```text
Error: YAML parse error on prometheus-druid-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 35: found an
indentation indicator equal to 0
```

Phase: $.logLevel | Status: failed

Selected fields (full context in artifacts):
- `$.logLevel = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-druid-exporter_1789326127/0000/paths/d4b057541dfc1a2d8d4d>)

#### E058

```text
Error: YAML parse error on prometheus-druid-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 37: did not find
expected key
```

Phase: $.image.name | Status: failed

Selected fields (full context in artifacts):
- `$.image.name = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-druid-exporter_1789326127/0000/paths/513f5326030235040688>)

#### E059

```text
Error: YAML parse error on prometheus-druid-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 37: found an
indentation indicator equal to 0
```

Phase: $.logFormat | Status: failed

Selected fields (full context in artifacts):
- `$.logFormat = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-druid-exporter_1789326127/0000/paths/699f2b0cffa1417e6453>)

#### E060

```text
Error: YAML parse error on prometheus-druid-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 39: found an
indentation indicator equal to 0
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": ">0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-druid-exporter_1789326127/0000/paths/8e79b7dd85a286cfaddb>)

Phase: $.image.pullPolicy | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullPolicy = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-druid-exporter_1789326127/0000/paths/eb979f1d0345157961ea>)

#### E061

```text
Error: YAML parse error on prometheus-druid-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 46: found
unexpected end of stream
```

Phase: $.image.tag | Status: failed

Selected fields (full context in artifacts):
- `$.image.tag = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-druid-exporter_1789326127/0000/paths/7e365cc9986c8fb6c4ad>)

#### E062

```text
Error: YAML parse error on prometheus-druid-exporter/templates/deployment.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-druid-exporter_1789326127/0000/paths/90b6880798789502760f>)

#### E063

```text
Error: YAML parse error on prometheus-druid-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 20: found an
indentation indicator equal to 0
```

Phase: $.serviceType | Status: failed

Selected fields (full context in artifacts):
- `$.serviceType = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-druid-exporter_1789326127/0000/paths/07ecff3471ba9b5d319b>)

#### E064

```text
Error: YAML parse error on prometheus-druid-exporter/templates/servicemonitor.yaml: error converting YAML to JSON: yaml: line 9: did not
find expected key
```

Phase: $.serviceMonitor | Status: failed

Selected fields (full context in artifacts):
- `$.serviceMonitor = {"additionalLabels": {"": null}, "enabled": true}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-druid-exporter_1789326127/0000/paths/fba48109c3f29511f06b>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-druid-exporter_1789326127/0000>)

### charts/prometheus-elasticsearch-exporter

Status: failed | Attempts: 2265

#### E065

```text
Error: YAML parse error on prometheus-elasticsearch-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 46: could
not find expected ':'
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "\r0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-elasticsearch-exporter_1789326320/0000/paths/8e79b7dd85a286cfaddb>)

#### E066

```text
Error: YAML parse error on prometheus-elasticsearch-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 55: did
not find expected ',' or ']'
```

Phase: $.es.timeout | Status: failed

Selected fields (full context in artifacts):
- `$.es.timeout = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-elasticsearch-exporter_1789326320/0000/paths/200d4c2c01235c785182>)

#### E067

```text
Error: YAML parse error on prometheus-elasticsearch-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 67: found
an indentation indicator equal to 0
```

Phase: $.service.metricsPort | Status: failed

Selected fields (full context in artifacts):
- `$.service.metricsPort = {"name": ">0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-elasticsearch-exporter_1789326320/0000/paths/8ccaf5636b1a904eed7f>)

#### E068

```text
Error: YAML parse error on prometheus-elasticsearch-exporter/templates/deployment.yaml: error unmarshaling JSON: while decoding JSON: json:
cannot unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.deployment.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.deployment.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-elasticsearch-exporter_1789326320/0000/paths/4d0453515f852ad02b1c>)

#### E069

```text
Error: YAML parse error on prometheus-elasticsearch-exporter/templates/prometheusrule.yaml: error converting YAML to JSON: yaml: line 5:
block sequence entries are not allowed in this context
```

Phase: $.prometheusRule | Status: failed

Selected fields (full context in artifacts):
- `$.prometheusRule = {"enabled": true, "namespace": "-"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-elasticsearch-exporter_1789326320/0000/paths/e58529c6a2268042286d>)

#### E070

```text
Error: YAML parse error on prometheus-elasticsearch-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 13: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-elasticsearch-exporter_1789326320/0000/paths/6e931799d09f8182f34b>)

#### E255

```text
Error: prometheus-elasticsearch-exporter/templates/cert-secret.yaml:11:37 executing
"prometheus-elasticsearch-exporter/templates/cert-secret.yaml" at <b64enc>: invalid value; expected string
```

Phase: $.es | Status: failed

Selected fields (full context in artifacts):
- `$.es = {"ssl": {"enabled": true}}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-elasticsearch-exporter_1789326320/0000/paths/706594807cb2a974992b>)

#### E256

```text
Error: prometheus-elasticsearch-exporter/templates/deployment.yaml:165:23 executing
"prometheus-elasticsearch-exporter/templates/deployment.yaml" at <.name>: nil pointer evaluating interface {}.name
```

Phase: $.secretMounts[*] | Status: failed

Selected fields (full context in artifacts):
- No supplied value at the selected paths.
Absent from overrides: $.secretMounts["*"]. Defaults may still apply.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-elasticsearch-exporter_1789326320/0000/paths/916cb9cf7a8ce78f0b67>)

Phase: $.secretMounts | Status: failed

Selected fields (full context in artifacts):
- `$.secretMounts = [null]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-elasticsearch-exporter_1789326320/0000/paths/d7f4210a0852343842ba>)

#### E257

```text
Error: prometheus-elasticsearch-exporter/templates/deployment.yaml:44:10 executing
"prometheus-elasticsearch-exporter/templates/deployment.yaml" at <include "elasticsearch-exporter.imagePullSecrets" .>: error calling
include: prometheus-elasticsearch-exporter/templates/_helpers.tpl:86:15 executing "elasticsearch-exporter.imagePullSecrets" at <.>: wrong
type for value; expected string; got interface {}
```

Phase: $.global.imagePullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.global.imagePullSecrets = [null]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-elasticsearch-exporter_1789326320/0000/paths/097f6358a00dddbcdd83>)

#### E258

```text
Error: prometheus-elasticsearch-exporter/templates/extra-manifests.yaml:3:7 executing
"prometheus-elasticsearch-exporter/templates/extra-manifests.yaml" at <.>: wrong type for value; expected string; got interface {}
```

Phase: $.extraManifests | Status: failed

Selected fields (full context in artifacts):
- `$.extraManifests = [null]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-elasticsearch-exporter_1789326320/0000/paths/48d9e37d2076ecabc7a6>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-elasticsearch-exporter_1789326320/0000>)

### charts/prometheus-fastly-exporter

Status: failed | Attempts: 2847

#### E071

```text
Error: YAML parse error on prometheus-fastly-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 25: did not find
expected key
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-fastly-exporter_1789326333/0000/paths/3f7165f1837241716c3c>)

#### E072

```text
Error: YAML parse error on prometheus-fastly-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 27: block
sequence entries are not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "-"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-fastly-exporter_1789326333/0000/paths/8e79b7dd85a286cfaddb>)

#### E073

```text
Error: YAML parse error on prometheus-fastly-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 34: found an
indentation indicator equal to 0
```

Phase: $.existingSecret.key | Status: failed

Selected fields (full context in artifacts):
- `$.existingSecret.key = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-fastly-exporter_1789326333/0000/paths/03e2c2b0be41f5d00fc4>)

Phase: $.existingSecret | Status: failed

Selected fields (full context in artifacts):
- `$.existingSecret = {"key": ">0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-fastly-exporter_1789326333/0000/paths/bf7372b3862550c529f3>)

#### E074

```text
Error: YAML parse error on prometheus-fastly-exporter/templates/extra-manifests.yaml: error unmarshaling JSON: while decoding JSON: json:
cannot unmarshal array into Go value of type util.SimpleHead
```

Phase: $.extraManifests | Status: failed

Selected fields (full context in artifacts):
- `$.extraManifests = [[]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-fastly-exporter_1789326333/0000/paths/48d9e37d2076ecabc7a6>)

#### E075

```text
Error: YAML parse error on prometheus-fastly-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 12: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-fastly-exporter_1789326333/0000/paths/6e931799d09f8182f34b>)

#### E076

```text
Error: YAML parse error on prometheus-fastly-exporter/templates/service.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.service.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.service.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-fastly-exporter_1789326333/0000/paths/98a2bca1991be60ae38a>)

#### E275

Source: prometheus-fastly-exporter 0.14.1 / templates/secret.yaml

```text
execution error at (prometheus-fastly-exporter/templates/secret.yaml:10:23): A Fastly token is required
```

Phase: $.fastly.token | Status: failed

Selected fields (full context in artifacts):
- `$.fastly.token = ""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-fastly-exporter_1789326333/0000/paths/af66eb9cab4e4aa33c2d>)

Phase: $.fastly | Status: failed

Selected fields (full context in artifacts):
- `$.fastly = {"token": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-fastly-exporter_1789326333/0000/paths/30145cbea97d73114d64>)

#### E281

```text
resource has no nonempty apiVersion
```

Phase: $.route.main | Status: failed

Selected fields (full context in artifacts):
- `$.route.main = {"apiVersion": "0", "enabled": true}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-fastly-exporter_1789326333/0000/paths/4040b7d9468c882f9251>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-fastly-exporter_1789326333/0000>)

### charts/prometheus-ipmi-exporter

Status: failed | Attempts: 2608

#### E077

```text
Error: YAML parse error on prometheus-ipmi-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 31: did not find
expected key
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-ipmi-exporter_1789326374/0000/paths/3f7165f1837241716c3c>)

#### E078

```text
Error: YAML parse error on prometheus-ipmi-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 60: did not find
expected ',' or '}'
```

Phase: $.resources | Status: failed

Selected fields (full context in artifacts):
- `$.resources = {"limits": {"cpu": "{"}}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-ipmi-exporter_1789326374/0000/paths/a18831338ac3673804ff>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-ipmi-exporter_1789326374/0000>)

### charts/prometheus-json-exporter

Status: failed | Attempts: 2484

#### E079

```text
Error: YAML parse error on prometheus-json-exporter/templates/configmap.yaml: error converting YAML to JSON: yaml: line 17: could not find
expected ':'
```

Phase: $.configuration.config | Status: failed

Selected fields (full context in artifacts):
- `$.configuration.config = "\r0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-json-exporter_1789326420/0000/paths/48c0936ef6759819cf71>)

#### E080

```text
Error: YAML parse error on prometheus-json-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 31: did not find
expected key
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-json-exporter_1789326420/0000/paths/3f7165f1837241716c3c>)

#### E081

```text
Error: YAML parse error on prometheus-json-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 33: block sequence
entries are not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "-"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-json-exporter_1789326420/0000/paths/8e79b7dd85a286cfaddb>)

#### E082

```text
Error: YAML parse error on prometheus-json-exporter/templates/prometheusrule.yaml: error converting YAML to JSON: yaml: line 5: found an
indentation indicator equal to 0
```

Phase: $.prometheusRule | Status: failed

Selected fields (full context in artifacts):
- `$.prometheusRule = {"enabled": true, "namespace": ">0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-json-exporter_1789326420/0000/paths/e58529c6a2268042286d>)

#### E083

```text
Error: YAML parse error on prometheus-json-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 13: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-json-exporter_1789326420/0000/paths/6e931799d09f8182f34b>)

#### E084

```text
Error: YAML parse error on prometheus-json-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 18: found an
indentation indicator equal to 0
```

Phase: $.service.name | Status: failed

Selected fields (full context in artifacts):
- `$.service.name = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-json-exporter_1789326420/0000/paths/16e8b0ef40bb4622d909>)

#### E085

```text
Error: YAML parse error on prometheus-json-exporter/templates/serviceaccount.yaml: error unmarshaling JSON: while decoding JSON: json:
cannot unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.serviceAccount.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-json-exporter_1789326420/0000/paths/840a8a2bc50327388c2a>)

#### E259

```text
Error: prometheus-json-exporter/templates/extra-manifests.yaml:3:7 executing "prometheus-json-exporter/templates/extra-manifests.yaml" at
<.>: wrong type for value; expected string; got interface {}
```

Phase: $.extraManifests | Status: failed

Selected fields (full context in artifacts):
- `$.extraManifests = [null]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-json-exporter_1789326420/0000/paths/48d9e37d2076ecabc7a6>)

#### E281

```text
resource has no nonempty apiVersion
```

Phase: $.route.main | Status: failed

Selected fields (full context in artifacts):
- `$.route.main = {"apiVersion": "0", "enabled": true}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-json-exporter_1789326420/0000/paths/4040b7d9468c882f9251>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-json-exporter_1789326420/0000>)

### charts/prometheus-kafka-exporter

Status: failed | Attempts: 2638

#### E086

```text
Error: YAML parse error on prometheus-kafka-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 28: did not find
expected key
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-kafka-exporter_1789326621/0000/paths/3f7165f1837241716c3c>)

#### E087

```text
Error: YAML parse error on prometheus-kafka-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 30: block sequence
entries are not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "-"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-kafka-exporter_1789326621/0000/paths/8e79b7dd85a286cfaddb>)

#### E088

```text
Error: YAML parse error on prometheus-kafka-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 35: did not find
expected ',' or ']'
```

Phase: $.sasl.kerberos.mountPath | Status: failed

Selected fields (full context in artifacts):
- `$.sasl.kerberos.mountPath = [{}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-kafka-exporter_1789326621/0000/paths/877ba46145df238cb594>)

Phase: $.sasl.kerberos | Status: failed

Selected fields (full context in artifacts):
- `$.sasl.kerberos = {"mountPath": [null, []]}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-kafka-exporter_1789326621/0000/paths/1caff83a87d6fee8d5a6>)

#### E089

```text
Error: YAML parse error on prometheus-kafka-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 35: found
unexpected end of stream
```

Phase: $.kafkaServer[*] | Status: failed

Selected fields (full context in artifacts):
- No supplied value at the selected paths.
Absent from overrides: $.kafkaServer["*"]. Defaults may still apply.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-kafka-exporter_1789326621/0000/paths/2555c5da846c29554fd3>)

#### E090

```text
Error: YAML parse error on prometheus-kafka-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 36: did not find
expected '-' indicator
```

Phase: $.imagePullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.imagePullSecrets = [{"": null, "0": null}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-kafka-exporter_1789326621/0000/paths/963d7244018d7b060689>)

Phase: $.global.imagePullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.global.imagePullSecrets = [{"": null, "0": null}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-kafka-exporter_1789326621/0000/paths/097f6358a00dddbcdd83>)

#### E091

```text
Error: YAML parse error on prometheus-kafka-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 38: could not find
expected ':'
```

Phase: $.server | Status: failed

Selected fields (full context in artifacts):
- `$.server = {"tls": {"mountPath": {"\n": null}}}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-kafka-exporter_1789326621/0000/paths/37783d3d65169269fb96>)

#### E092

```text
Error: YAML parse error on prometheus-kafka-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 11: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-kafka-exporter_1789326621/0000/paths/6e931799d09f8182f34b>)

#### E093

```text
Error: YAML parse error on prometheus-kafka-exporter/templates/serviceaccount.yaml: error unmarshaling JSON: while decoding JSON: json:
cannot unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.serviceAccount.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-kafka-exporter_1789326621/0000/paths/840a8a2bc50327388c2a>)

#### E260

```text
Error: prometheus-kafka-exporter/templates/extra-objects.yaml:8:10 executing "prometheus-kafka-exporter/templates/extra-objects.yaml" at
<$extraObjects>: range can't iterate over 1
```

Phase: $.extraManifests | Status: failed

Selected fields (full context in artifacts):
- `$.extraManifests = 1`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-kafka-exporter_1789326621/0000/paths/48d9e37d2076ecabc7a6>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-kafka-exporter_1789326621/0000>)

### charts/prometheus-memcached-exporter

Status: failed | Attempts: 3213

#### E094

```text
Error: YAML parse error on prometheus-memcached-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 27: did not
find expected key
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-memcached-exporter_1789326634/0000/paths/3f7165f1837241716c3c>)

#### E095

```text
Error: YAML parse error on prometheus-memcached-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 29: block
sequence entries are not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "-"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-memcached-exporter_1789326634/0000/paths/8e79b7dd85a286cfaddb>)

#### E096

```text
Error: YAML parse error on prometheus-memcached-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 29: found an
indentation indicator equal to 0
```

Phase: $.image.pullPolicy | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullPolicy = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-memcached-exporter_1789326634/0000/paths/eb979f1d0345157961ea>)

#### E097

```text
Error: YAML parse error on prometheus-memcached-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 33: could not
find expected ':'
```

Phase: $.extraArgs | Status: failed

Selected fields (full context in artifacts):
- `$.extraArgs = {"\n": null}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-memcached-exporter_1789326634/0000/paths/6b07fe5f61f90919fc2a>)

#### E098

```text
Error: YAML parse error on prometheus-memcached-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 45: found
unexpected end of stream
```

Phase: $.image.tag | Status: failed

Selected fields (full context in artifacts):
- `$.image.tag = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-memcached-exporter_1789326634/0000/paths/7e365cc9986c8fb6c4ad>)

#### E099

```text
Error: YAML parse error on prometheus-memcached-exporter/templates/hpa.yaml: error converting YAML to JSON: yaml: line 29: did not find
expected ',' or ']'
```

Phase: $.autoscaling | Status: failed

Selected fields (full context in artifacts):
- `$.autoscaling = {"enabled": true, "targetMemoryUtilizationPercentage": [{}]}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-memcached-exporter_1789326634/0000/paths/3137be176146e132d2b8>)

#### E100

```text
Error: YAML parse error on prometheus-memcached-exporter/templates/prometheusrule.yaml: error converting YAML to JSON: yaml: line 5: found
an indentation indicator equal to 0
```

Phase: $.prometheusRule | Status: failed

Selected fields (full context in artifacts):
- `$.prometheusRule = {"enabled": true, "namespace": ">0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-memcached-exporter_1789326634/0000/paths/e58529c6a2268042286d>)

#### E101

```text
Error: YAML parse error on prometheus-memcached-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 12: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-memcached-exporter_1789326634/0000/paths/6e931799d09f8182f34b>)

#### E102

```text
Error: YAML parse error on prometheus-memcached-exporter/templates/service.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.service.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.service.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-memcached-exporter_1789326634/0000/paths/98a2bca1991be60ae38a>)

#### E103

```text
Error: YAML parse error on prometheus-memcached-exporter/templates/serviceaccount.yaml: error unmarshaling JSON: while decoding JSON: json:
cannot unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.serviceAccount.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-memcached-exporter_1789326634/0000/paths/840a8a2bc50327388c2a>)

#### E270

```text
Inconsistent data generation! Data generation behaved differently between test cases. Is your data generation depending on external state?
The second run stopped drawing earlier than the first run, which continued to draw more data.
```

Phase: $.serviceMonitor.timeout | Status: failed

Selected fields (full context in artifacts):
- No supplied value at the selected paths.
Absent from overrides: $.serviceMonitor.timeout. Defaults may still apply.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-memcached-exporter_1789326634/0000/paths/e1dd5c30b396f1ebb190>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-memcached-exporter_1789326634/0000>)

### charts/prometheus-modbus-exporter

Status: failed | Attempts: 2668

#### E104

```text
Error: YAML parse error on prometheus-modbus-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 41: did not find
expected key
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-modbus-exporter_1789326675/0000/paths/3f7165f1837241716c3c>)

#### E105

```text
Error: YAML parse error on prometheus-modbus-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 45: could not
find expected ':'
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "\r0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-modbus-exporter_1789326675/0000/paths/8e79b7dd85a286cfaddb>)

#### E106

```text
Error: YAML parse error on prometheus-modbus-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 64: did not find
expected ',' or ']'
```

Phase: $.configMapFile | Status: failed

Selected fields (full context in artifacts):
- `$.configMapFile = [{}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-modbus-exporter_1789326675/0000/paths/435b09d3c26ba9d0ee75>)

#### E107

```text
Error: YAML parse error on prometheus-modbus-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 12: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-modbus-exporter_1789326675/0000/paths/6e931799d09f8182f34b>)

#### E108

```text
Error: YAML parse error on prometheus-modbus-exporter/templates/serviceaccount.yaml: error unmarshaling JSON: while decoding JSON: json:
cannot unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.serviceAccount.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-modbus-exporter_1789326675/0000/paths/840a8a2bc50327388c2a>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-modbus-exporter_1789326675/0000>)

### charts/prometheus-mongodb-exporter

Status: failed | Attempts: 2808

#### E109

```text
Error: YAML parse error on prometheus-mongodb-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 35: did not find
expected key
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-mongodb-exporter_1789326721/0000/paths/3f7165f1837241716c3c>)

#### E110

```text
Error: YAML parse error on prometheus-mongodb-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 35: found an
indentation indicator equal to 0
```

Phase: $.existingSecret.key | Status: failed

Selected fields (full context in artifacts):
- `$.existingSecret.key = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-mongodb-exporter_1789326721/0000/paths/03e2c2b0be41f5d00fc4>)

Phase: $.existingSecret | Status: failed

Selected fields (full context in artifacts):
- `$.existingSecret = {"key": ">0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-mongodb-exporter_1789326721/0000/paths/bf7372b3862550c529f3>)

#### E111

```text
Error: YAML parse error on prometheus-mongodb-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 37: block
sequence entries are not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "-"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-mongodb-exporter_1789326721/0000/paths/8e79b7dd85a286cfaddb>)

#### E112

```text
Error: YAML parse error on prometheus-mongodb-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 39: did not find
expected '-' indicator
```

Phase: $.extraArgs | Status: failed

Selected fields (full context in artifacts):
- `$.extraArgs = []`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-mongodb-exporter_1789326721/0000/paths/6b07fe5f61f90919fc2a>)

#### E113

```text
Error: YAML parse error on prometheus-mongodb-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 22: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-mongodb-exporter_1789326721/0000/paths/6e931799d09f8182f34b>)

#### E114

```text
Error: YAML parse error on prometheus-mongodb-exporter/templates/service.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.service.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.service.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-mongodb-exporter_1789326721/0000/paths/98a2bca1991be60ae38a>)

#### E261

```text
Error: prometheus-mongodb-exporter/templates/deployment.yaml:33:24 executing "prometheus-mongodb-exporter/templates/deployment.yaml" at
<include "prometheus-mongodb-exporter.mongodbUri" .>: error calling include: prometheus-mongodb-exporter/templates/_helpers.tpl:84:44
executing "prometheus-mongodb-exporter.mongodbUri" at <.uri>: nil pointer evaluating interface {}.uri
```

Phase: $.serviceMonitor.multiTarget | Status: failed

Selected fields (full context in artifacts):
- `$.serviceMonitor.multiTarget = {"enabled": true, "targets": [null]}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-mongodb-exporter_1789326721/0000/paths/1fdc27190b1c0e9570f3>)

#### E276

Source: prometheus-mongodb-exporter 3.22.0 / templates/secret.yaml

```text
execution error at (prometheus-mongodb-exporter/templates/secret.yaml:10:18): A MongoDB URI is required
```

Phase: $.mongodb.uri | Status: failed

Selected fields (full context in artifacts):
- `$.mongodb.uri = ""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-mongodb-exporter_1789326721/0000/paths/f008f023211b17fb880f>)

Phase: $.mongodb | Status: failed

Selected fields (full context in artifacts):
- `$.mongodb = {"uri": ""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-mongodb-exporter_1789326721/0000/paths/ac3b4d832039bdf0add2>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-mongodb-exporter_1789326721/0000>)

### charts/prometheus-mysql-exporter

Status: failed | Attempts: 2359

#### E115

```text
Error: YAML parse error on prometheus-mysql-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 35: did not find
expected key
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"registry": "\""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-mysql-exporter_1789326922/0000/paths/8e79b7dd85a286cfaddb>)

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-mysql-exporter_1789326922/0000/paths/3f7165f1837241716c3c>)

#### E116

```text
Error: YAML parse error on prometheus-mysql-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 62: found
unexpected end of stream
```

Phase: $.config.logLevel | Status: failed

Selected fields (full context in artifacts):
- `$.config.logLevel = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-mysql-exporter_1789326922/0000/paths/e4ad1a1830b0dc146749>)

#### E117

```text
Error: YAML parse error on prometheus-mysql-exporter/templates/prometheusrule.yaml: error converting YAML to JSON: yaml: line 5: found an
indentation indicator equal to 0
```

Phase: $.prometheusRule | Status: failed

Selected fields (full context in artifacts):
- `$.prometheusRule = {"enabled": true, "namespace": ">0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-mysql-exporter_1789326922/0000/paths/e58529c6a2268042286d>)

#### E118

```text
Error: YAML parse error on prometheus-mysql-exporter/templates/secret-config.yaml: error converting YAML to JSON: yaml: line 21: could not
find expected ':'
```

Phase: $.mysql.host | Status: failed

Selected fields (full context in artifacts):
- `$.mysql.host = "\n0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-mysql-exporter_1789326922/0000/paths/b44eae21aa0780552d49>)

#### E119

```text
Error: YAML parse error on prometheus-mysql-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 18: found an
indentation indicator equal to 0
```

Phase: $.service.name | Status: failed

Selected fields (full context in artifacts):
- `$.service.name = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-mysql-exporter_1789326922/0000/paths/16e8b0ef40bb4622d909>)

#### E271

```text
[Diagnostic shortened; full text in artifacts] ... ting it again. It is also possible that applying this much filtering will distort the
domain and/or distribution of the test, leaving your testing less rigorous than expected. If you expect this many inputs to be filtered out
during generation, you can disable this health check with @settings(suppress_health_check=[HealthCheck.filter_too_much]). See
https://hypothesis.readthedocs.io/en/latest/reference/api.html#hypothesis.HealthCheck for details.
```

Phase: $.extraEnvs[*].valueFrom | Status: generation-error

Selected fields (full context in artifacts):
- No supplied value at the selected paths.
Absent from overrides: $.extraEnvs["*"].valueFrom. Defaults may still apply.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-mysql-exporter_1789326922/0000/paths/7fad271bf60e338792f2>)

#### E273

```text
[Diagnostic shortened; full text in artifacts] ...  '#/$defs/uriString'}, 'additionalProperties': {'type': 'boolean'}}, '$comment': {'type':
'string'}, '$defs': {'type': 'object', 'additionalProperties': {'$dynamicRef': '#meta'}}}, '$defs': {'anchorString': {'type': 'string',
'pattern': '^[A-Za-z_][-A-Za-z0-9._]*$'}, 'uriString': {'type': 'string', 'format': 'uri'}, 'uriReferenceString': {'type': 'string',
'format': 'uri-reference'}}} On schema['properties']['extraEnvs']['items']: [{'const': ''}]
```

Phase: $.extraEnvs[*] | Status: generation-error

Selected fields (full context in artifacts):
- No supplied value at the selected paths.
Absent from overrides: $.extraEnvs["*"]. Defaults may still apply.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-mysql-exporter_1789326922/0000/paths/cca2d03f64715c2d3d43>)

#### E281

```text
resource has no nonempty apiVersion
```

Phase: $.extraManifests | Status: failed

Selected fields (full context in artifacts):
- `$.extraManifests = [{}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-mysql-exporter_1789326922/0000/paths/48d9e37d2076ecabc7a6>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-mysql-exporter_1789326922/0000>)

### charts/prometheus-nats-exporter

Status: failed | Attempts: 3515

#### E120

```text
Error: YAML parse error on prometheus-nats-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 37: did not find
expected '-' indicator
```

Phase: $.config | Status: failed

Selected fields (full context in artifacts):
- `$.config = {"nats": {"namespace": "\""}}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-nats-exporter_1789326935/0000/paths/24e6ce8e5165b2c58d67>)

Phase: $.config.nats.service | Status: failed

Selected fields (full context in artifacts):
- `$.config.nats.service = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-nats-exporter_1789326935/0000/paths/d89a975a43043bbf61a2>)

2 additional occurrences are retained in the JSON report and chart artifacts.

#### E121

```text
Error: YAML parse error on prometheus-nats-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 38: did not find
expected key
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-nats-exporter_1789326935/0000/paths/3f7165f1837241716c3c>)

#### E122

```text
Error: YAML parse error on prometheus-nats-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 40: found an
indentation indicator equal to 0
```

Phase: $.image.pullPolicy | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullPolicy = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-nats-exporter_1789326935/0000/paths/eb979f1d0345157961ea>)

#### E123

```text
Error: YAML parse error on prometheus-nats-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 59: found
unexpected end of stream
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "'"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-nats-exporter_1789326935/0000/paths/8e79b7dd85a286cfaddb>)

Phase: $.image.tag | Status: failed

Selected fields (full context in artifacts):
- `$.image.tag = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-nats-exporter_1789326935/0000/paths/7e365cc9986c8fb6c4ad>)

#### E124

```text
Error: YAML parse error on prometheus-nats-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 60: could not find
expected ':'
```

Phase: $.extraVolumes | Status: failed

Selected fields (full context in artifacts):
- `$.extraVolumes = "0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-nats-exporter_1789326935/0000/paths/0b94c6f90deb62ef8b9d>)

#### E125

```text
Error: YAML parse error on prometheus-nats-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 13: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-nats-exporter_1789326935/0000/paths/6e931799d09f8182f34b>)

#### E126

```text
Error: YAML parse error on prometheus-nats-exporter/templates/service.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.service.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.service.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-nats-exporter_1789326935/0000/paths/98a2bca1991be60ae38a>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-nats-exporter_1789326935/0000>)

### charts/prometheus-nginx-exporter

Status: failed | Attempts: 2957

#### E127

```text
Error: YAML parse error on prometheus-nginx-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 36: did not find
expected key
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-nginx-exporter_1789326976/0000/paths/3f7165f1837241716c3c>)

#### E128

```text
Error: YAML parse error on prometheus-nginx-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 38: mapping values
are not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": ":"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-nginx-exporter_1789326976/0000/paths/8e79b7dd85a286cfaddb>)

#### E129

```text
Error: YAML parse error on prometheus-nginx-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 57: found
unexpected end of stream
```

Phase: $.nginxServer | Status: failed

Selected fields (full context in artifacts):
- `$.nginxServer = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-nginx-exporter_1789326976/0000/paths/66d004fff8de521ea083>)

#### E130

```text
Error: YAML parse error on prometheus-nginx-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 5: found an
indentation indicator equal to 0
```

Phase: $.namespaceOverride | Status: failed

Selected fields (full context in artifacts):
- `$.namespaceOverride = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-nginx-exporter_1789326976/0000/paths/835d62e0a3e46b72c904>)

#### E131

```text
Error: YAML parse error on prometheus-nginx-exporter/templates/deployment.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.deployment.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.deployment.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-nginx-exporter_1789326976/0000/paths/4d0453515f852ad02b1c>)

Phase: $.additionalAnnotations | Status: failed

Selected fields (full context in artifacts):
- `$.additionalAnnotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-nginx-exporter_1789326976/0000/paths/ced24eb9a645a324bd82>)

#### E132

```text
Error: YAML parse error on prometheus-nginx-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 15: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-nginx-exporter_1789326976/0000/paths/6e931799d09f8182f34b>)

#### E133

```text
Error: YAML parse error on prometheus-nginx-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 16: found an
indentation indicator equal to 0
```

Phase: $.service.externalTrafficPolicy | Status: failed

Selected fields (full context in artifacts):
- `$.service.externalTrafficPolicy = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-nginx-exporter_1789326976/0000/paths/43cc43ff90438d02a31e>)

#### E134

```text
Error: YAML parse error on prometheus-nginx-exporter/templates/service.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.service.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.service.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-nginx-exporter_1789326976/0000/paths/98a2bca1991be60ae38a>)

#### E281

```text
resource has no nonempty apiVersion
```

Phase: $.serviceMonitor | Status: failed

Selected fields (full context in artifacts):
- `$.serviceMonitor = {"apiVersion": "", "enabled": true}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-nginx-exporter_1789326976/0000/paths/fba48109c3f29511f06b>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-nginx-exporter_1789326976/0000>)

### charts/prometheus-node-exporter

Status: failed | Attempts: 1547

#### E135

```text
Error: YAML parse error on prometheus-node-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 46: mapping values
are not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"digest": ":"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-node-exporter_1789327022/0000/paths/8e79b7dd85a286cfaddb>)

#### E136

```text
Error: YAML parse error on prometheus-node-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 99: did not find
expected '-' indicator
```

Phase: $.imagePullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.imagePullSecrets = [{"": null, "0": null}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-node-exporter_1789327022/0000/paths/963d7244018d7b060689>)

#### E137

```text
Error: YAML parse error on prometheus-node-exporter/templates/daemonset.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.daemonsetAnnotations | Status: failed

Selected fields (full context in artifacts):
- `$.daemonsetAnnotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-node-exporter_1789327022/0000/paths/2e93a3c57e04dfa290b1>)

#### E262

```text
Error: prometheus-node-exporter/templates/extra-manifests.yaml:3:7 executing "prometheus-node-exporter/templates/extra-manifests.yaml" at
<.>: wrong type for value; expected string; got interface {}
```

Phase: $.extraManifests | Status: failed

Selected fields (full context in artifacts):
- `$.extraManifests = [null]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-node-exporter_1789327022/0000/paths/48d9e37d2076ecabc7a6>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-node-exporter_1789327022/0000>)

### charts/prometheus-operator-admission-webhook

Status: failed | Attempts: 1576

#### E138

```text
Error: YAML parse error on prometheus-operator-admission-webhook/templates/deployment.yaml: error converting YAML to JSON: yaml: line 33:
mapping values are not allowed in this context
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [{"0": null, "": ""}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-operator-admission-webhook_1789327223/0000/paths/a4a0ea6ab697189bb963>)

#### E139

```text
Error: YAML parse error on prometheus-operator-admission-webhook/templates/deployment.yaml: error converting YAML to JSON: yaml: line 82:
found unexpected end of stream
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"digest": "\\"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-operator-admission-webhook_1789327223/0000/paths/8e79b7dd85a286cfaddb>)

#### E140

```text
Error: YAML parse error on prometheus-operator-admission-webhook/templates/deployment.yaml: error unmarshaling JSON: while decoding JSON:
json: cannot unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.deployment.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.deployment.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-operator-admission-webhook_1789327223/0000/paths/4d0453515f852ad02b1c>)

#### E141

```text
Error: YAML parse error on prometheus-operator-admission-webhook/templates/hooks/job-createSecret.yaml: error converting YAML to JSON: yaml:
line 30: found an indentation indicator equal to 0
```

Phase: $.jobs.image.pullPolicy | Status: failed

Selected fields (full context in artifacts):
- `$.jobs.image.pullPolicy = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-operator-admission-webhook_1789327223/0000/paths/9b4d8bb1c854cf03a757>)

#### E142

```text
Error: YAML parse error on prometheus-operator-admission-webhook/templates/hooks/job-patchWebhook.yaml: error unmarshaling JSON: while
decoding JSON: json: cannot unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.jobs.patchWebhook.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.jobs.patchWebhook.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-operator-admission-webhook_1789327223/0000/paths/120d661a1d30ca4b8f1b>)

#### E270

```text
Inconsistent data generation! Data generation behaved differently between test cases. Is your data generation depending on external state?
The second run stopped drawing earlier than the first run, which continued to draw more data.
```

Phase: $.networkPolicy.annotations | Status: failed

Selected fields (full context in artifacts):
- No supplied value at the selected paths.
Absent from overrides: $.networkPolicy.annotations. Defaults may still apply.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-operator-admission-webhook_1789327223/0000/paths/4ea739ee7069f13e3956>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-operator-admission-webhook_1789327223/0000>)

### charts/prometheus-operator-crds

Status: time-limit | Attempts: 29

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-operator-crds_1789327236/0000>)

### charts/prometheus-operator-crds/charts/crds

Status: missing-values | Attempts: N/A

#### E272

```text
Selected values file not found:
/Users/emmadoyle/projects/personal/hypothesis-helm/third_party/prometheus-community-helm-charts/charts/prometheus-operator-crds/charts/crds/values.yaml
```

Phase: chart | Status: missing-values

No triggering values were recorded for this diagnostic.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/crds_1789327277/0000>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/crds_1789327277/0000>)

### charts/prometheus-pgbouncer-exporter

Status: failed | Attempts: 2504

#### E143

```text
Error: YAML parse error on prometheus-pgbouncer-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 34: could not
find expected ':'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = {"": {"\r": null}}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pgbouncer-exporter_1789327277/0000/paths/a4a0ea6ab697189bb963>)

#### E144

```text
Error: YAML parse error on prometheus-pgbouncer-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 35: did not
find expected key
```

Phase: $.config.logLevel | Status: failed

Selected fields (full context in artifacts):
- `$.config.logLevel = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pgbouncer-exporter_1789327277/0000/paths/e4ad1a1830b0dc146749>)

#### E145

```text
Error: YAML parse error on prometheus-pgbouncer-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 44: found an
indentation indicator equal to 0
```

Phase: $.config.datasource.passwordFile | Status: failed

Selected fields (full context in artifacts):
- `$.config.datasource.passwordFile = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pgbouncer-exporter_1789327277/0000/paths/464c622a0774b82dd708>)

#### E146

```text
Error: YAML parse error on prometheus-pgbouncer-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 47: did not
find expected key
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pgbouncer-exporter_1789327277/0000/paths/3f7165f1837241716c3c>)

#### E147

```text
Error: YAML parse error on prometheus-pgbouncer-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 81: found
unexpected end of stream
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "\""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pgbouncer-exporter_1789327277/0000/paths/8e79b7dd85a286cfaddb>)

Phase: $.config.datasource.sslmode | Status: failed

Selected fields (full context in artifacts):
- `$.config.datasource.sslmode = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pgbouncer-exporter_1789327277/0000/paths/91fe16c08ac08ecf2da1>)

#### E148

```text
Error: YAML parse error on prometheus-pgbouncer-exporter/templates/prometheusrule.yaml: error converting YAML to JSON: yaml: line 5: found
an indentation indicator equal to 0
```

Phase: $.prometheusRule | Status: failed

Selected fields (full context in artifacts):
- `$.prometheusRule = {"enabled": true, "namespace": ">0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pgbouncer-exporter_1789327277/0000/paths/e58529c6a2268042286d>)

#### E149

```text
Error: YAML parse error on prometheus-pgbouncer-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 11: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pgbouncer-exporter_1789327277/0000/paths/6e931799d09f8182f34b>)

#### E150

```text
Error: YAML parse error on prometheus-pgbouncer-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 16: found an
indentation indicator equal to 0
```

Phase: $.service.name | Status: failed

Selected fields (full context in artifacts):
- `$.service.name = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pgbouncer-exporter_1789327277/0000/paths/16e8b0ef40bb4622d909>)

#### E151

```text
Error: YAML parse error on prometheus-pgbouncer-exporter/templates/serviceaccount.yaml: error converting YAML to JSON: yaml: line 12: did
not find expected key
```

Phase: $.serviceAccount.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount.annotations = {"\n": null}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pgbouncer-exporter_1789327277/0000/paths/840a8a2bc50327388c2a>)

#### E263

```text
Error: prometheus-pgbouncer-exporter/templates/secrets.yaml:13:89 executing "prometheus-pgbouncer-exporter/templates/secrets.yaml" at
<b64enc>: wrong type for value; expected string; got bool
```

Phase: $.config | Status: failed

Selected fields (full context in artifacts):
- `$.config = {"datasource": {"password": true}}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pgbouncer-exporter_1789327277/0000/paths/24e6ce8e5165b2c58d67>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pgbouncer-exporter_1789327277/0000>)

### charts/prometheus-pingdom-exporter

Status: failed | Attempts: 3162

#### E152

```text
Error: YAML parse error on prometheus-pingdom-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 23: found an
indentation indicator equal to 0
```

Phase: $.serviceAccount.name | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount.name = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pingdom-exporter_1789327324/0000/paths/815bf9b751b356e044f0>)

#### E153

```text
Error: YAML parse error on prometheus-pingdom-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 35: did not find
expected key
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pingdom-exporter_1789327324/0000/paths/3f7165f1837241716c3c>)

#### E154

```text
Error: YAML parse error on prometheus-pingdom-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 37: block
sequence entries are not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "-"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pingdom-exporter_1789327324/0000/paths/8e79b7dd85a286cfaddb>)

#### E155

```text
Error: YAML parse error on prometheus-pingdom-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 37: found an
indentation indicator equal to 0
```

Phase: $.image.pullPolicy | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullPolicy = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pingdom-exporter_1789327324/0000/paths/eb979f1d0345157961ea>)

#### E156

```text
Error: YAML parse error on prometheus-pingdom-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 42: found an
indentation indicator equal to 0
```

Phase: $.existingSecret | Status: failed

Selected fields (full context in artifacts):
- `$.existingSecret = {"name": ">0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pingdom-exporter_1789327324/0000/paths/bf7372b3862550c529f3>)

Phase: $.existingSecret.name | Status: failed

Selected fields (full context in artifacts):
- `$.existingSecret.name = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pingdom-exporter_1789327324/0000/paths/fd9b16a1b0486af8ebff>)

#### E157

```text
Error: YAML parse error on prometheus-pingdom-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 58: found
unexpected end of stream
```

Phase: $.image.tag | Status: failed

Selected fields (full context in artifacts):
- `$.image.tag = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pingdom-exporter_1789327324/0000/paths/7e365cc9986c8fb6c4ad>)

#### E158

```text
Error: YAML parse error on prometheus-pingdom-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 7: found an
indentation indicator equal to 0
```

Phase: $.nameOverride | Status: failed

Selected fields (full context in artifacts):
- `$.nameOverride = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pingdom-exporter_1789327324/0000/paths/0ce120cfa523ba37df61>)

#### E159

```text
Error: YAML parse error on prometheus-pingdom-exporter/templates/secret.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.secret.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.secret.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pingdom-exporter_1789327324/0000/paths/1690d23ac111700af9a3>)

Phase: $.secret | Status: failed

Selected fields (full context in artifacts):
- `$.secret = {"annotations": {"": []}}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pingdom-exporter_1789327324/0000/paths/7ed6936249ddb5c87cc5>)

#### E160

```text
Error: YAML parse error on prometheus-pingdom-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 12: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pingdom-exporter_1789327324/0000/paths/6e931799d09f8182f34b>)

#### E161

```text
Error: YAML parse error on prometheus-pingdom-exporter/templates/service.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.service.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.service.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pingdom-exporter_1789327324/0000/paths/98a2bca1991be60ae38a>)

Phase: $.service | Status: failed

Selected fields (full context in artifacts):
- `$.service = {"annotations": {"": []}}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pingdom-exporter_1789327324/0000/paths/da628aa79e50e022e4ff>)

#### E162

```text
Error: YAML parse error on prometheus-pingdom-exporter/templates/serviceaccount.yaml: error unmarshaling JSON: while decoding JSON: json:
cannot unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.serviceAccount | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount = {"annotations": {"": []}, "create": true}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pingdom-exporter_1789327324/0000/paths/7a010717afb4691aaeb8>)

#### E280

```text
resource has no metadata.name
```

Phase: $.fullnameOverride | Status: failed

Selected fields (full context in artifacts):
- `$.fullnameOverride = "0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pingdom-exporter_1789327324/0000/paths/e2f7761f901d86846684>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pingdom-exporter_1789327324/0000>)

### charts/prometheus-pingmesh-exporter

Status: failed | Attempts: 1491

#### E163

```text
Error: YAML parse error on prometheus-pingmesh-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 59: could not
find expected ':'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = {"": {"\r": null}}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pingmesh-exporter_1789327525/0000/paths/a4a0ea6ab697189bb963>)

#### E164

```text
Error: YAML parse error on prometheus-pingmesh-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 74: did not find
expected key
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "\""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pingmesh-exporter_1789327525/0000/paths/8e79b7dd85a286cfaddb>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pingmesh-exporter_1789327525/0000>)

### charts/prometheus-postgres-exporter

Status: baseline-failed | Attempts: N/A

#### E001

```text
[Diagnostic shortened; full text in artifacts] ... s-postgres-exporter/templates/secrets.yaml:12:38 executing
"prometheus-postgres-exporter/templates/secrets.yaml" at <.Values.config.datasource.password>: wrong type for value; expected string; got
interface {} level=WARN msg="missing required value" message="config.datasource.password is required when not using
config.datasource.passwordSecret, config.datasource.passwordFile, or config.datasourceSecret" Error: 1 chart(s) linted, 1 chart(s) failed
```

Phase: chart | Status: baseline-failed

No triggering values were recorded for this diagnostic.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-postgres-exporter_1789327537/0000>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-postgres-exporter_1789327537/0000>)

### charts/prometheus-pushgateway

Status: failed | Attempts: 2157

#### E165

```text
Error: YAML parse error on prometheus-pushgateway/templates/deployment.yaml: error converting YAML to JSON: yaml: line 34: found an
indentation indicator equal to 0
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": ">0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pushgateway_1789327538/0000/paths/8e79b7dd85a286cfaddb>)

#### E166

```text
Error: YAML parse error on prometheus-pushgateway/templates/deployment.yaml: error converting YAML to JSON: yaml: line 42: did not find
expected ',' or '}'
```

Phase: $.liveness | Status: failed

Selected fields (full context in artifacts):
- `$.liveness = {"probe": {"httpGet": {"path": "{"}}}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pushgateway_1789327538/0000/paths/ff9df3c5ede51cd2a539>)

#### E167

```text
Error: YAML parse error on prometheus-pushgateway/templates/deployment.yaml: error converting YAML to JSON: yaml: line 43: could not find
expected ':'
```

Phase: $.liveness.probe | Status: failed

Selected fields (full context in artifacts):
- `$.liveness.probe = {"httpGet": {"path": "\r0"}}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pushgateway_1789327538/0000/paths/d9d2f2d36212f76966a9>)

#### E168

```text
Error: YAML parse error on prometheus-pushgateway/templates/extra-manifests.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go value of type util.SimpleHead
```

Phase: $.extraManifests | Status: failed

Selected fields (full context in artifacts):
- `$.extraManifests = [[]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pushgateway_1789327538/0000/paths/48d9e37d2076ecabc7a6>)

#### E169

```text
Error: YAML parse error on prometheus-pushgateway/templates/httproute.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.route.main | Status: failed

Selected fields (full context in artifacts):
- `$.route.main = {"annotations": {"": []}, "enabled": true}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pushgateway_1789327538/0000/paths/4040b7d9468c882f9251>)

#### E170

```text
Error: YAML parse error on prometheus-pushgateway/templates/service.yaml: error converting YAML to JSON: yaml: line 13: found an indentation
indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pushgateway_1789327538/0000/paths/6e931799d09f8182f34b>)

#### E171

```text
Error: YAML parse error on prometheus-pushgateway/templates/service.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.serviceAnnotations | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAnnotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pushgateway_1789327538/0000/paths/3baebb4c577c05ed4481>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-pushgateway_1789327538/0000>)

### charts/prometheus-rabbitmq-exporter

Status: failed | Attempts: 2725

#### E172

```text
Error: YAML parse error on prometheus-rabbitmq-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 25: did not
find expected ',' or ']'
```

Phase: $.image.pullSecrets[*] | Status: failed

Selected fields (full context in artifacts):
- No supplied value at the selected paths.
Absent from overrides: $.image.pullSecrets["*"]. Defaults may still apply.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-rabbitmq-exporter_1789327578/0000/paths/6c7a809f27215e41451b>)

#### E173

```text
Error: YAML parse error on prometheus-rabbitmq-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 26: mapping
values are not allowed in this context
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [{"0": null, "": ""}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-rabbitmq-exporter_1789327578/0000/paths/a4a0ea6ab697189bb963>)

#### E174

```text
Error: YAML parse error on prometheus-rabbitmq-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 27: did not
find expected key
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-rabbitmq-exporter_1789327578/0000/paths/3f7165f1837241716c3c>)

#### E175

```text
Error: YAML parse error on prometheus-rabbitmq-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 29: block
sequence entries are not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "-"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-rabbitmq-exporter_1789327578/0000/paths/8e79b7dd85a286cfaddb>)

#### E176

```text
Error: YAML parse error on prometheus-rabbitmq-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 34: found an
indentation indicator equal to 0
```

Phase: $.rabbitmq.configMapOverrideReference | Status: failed

Selected fields (full context in artifacts):
- `$.rabbitmq.configMapOverrideReference = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-rabbitmq-exporter_1789327578/0000/paths/5ab2148b1f1e6157d626>)

#### E177

```text
Error: YAML parse error on prometheus-rabbitmq-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 36: did not
find expected key
```

Phase: $.rabbitmq.existingPasswordSecret | Status: failed

Selected fields (full context in artifacts):
- `$.rabbitmq.existingPasswordSecret = {"\"": null}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-rabbitmq-exporter_1789327578/0000/paths/dace7c3c533a9eaf121c>)

#### E178

```text
Error: YAML parse error on prometheus-rabbitmq-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 41: did not
find expected key
```

Phase: $.rabbitmq.existingUserSecret | Status: failed

Selected fields (full context in artifacts):
- `$.rabbitmq.existingUserSecret = {"\"": null}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-rabbitmq-exporter_1789327578/0000/paths/63a6844a7be1c17b0175>)

#### E179

```text
Error: YAML parse error on prometheus-rabbitmq-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 45: found an
indentation indicator equal to 0
```

Phase: $.rabbitmq.url | Status: failed

Selected fields (full context in artifacts):
- `$.rabbitmq.url = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-rabbitmq-exporter_1789327578/0000/paths/3298d334a5940dfc7047>)

#### E180

```text
Error: YAML parse error on prometheus-rabbitmq-exporter/templates/deployment.yaml: error unmarshaling JSON: while decoding JSON: json:
cannot unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.additionalAnnotations | Status: failed

Selected fields (full context in artifacts):
- `$.additionalAnnotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-rabbitmq-exporter_1789327578/0000/paths/ced24eb9a645a324bd82>)

#### E181

```text
Error: YAML parse error on prometheus-rabbitmq-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 11: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-rabbitmq-exporter_1789327578/0000/paths/6e931799d09f8182f34b>)

#### E182

```text
Error: YAML parse error on prometheus-rabbitmq-exporter/templates/serviceaccount.yaml: error unmarshaling JSON: while decoding JSON: json:
cannot unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.serviceAccount.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-rabbitmq-exporter_1789327578/0000/paths/840a8a2bc50327388c2a>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-rabbitmq-exporter_1789327578/0000>)

### charts/prometheus-redis-exporter

Status: failed | Attempts: 2526

#### E183

```text
Error: YAML parse error on prometheus-redis-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 31: did not find
expected ',' or ']'
```

Phase: $.image.pullSecrets[*] | Status: failed

Selected fields (full context in artifacts):
- No supplied value at the selected paths.
Absent from overrides: $.image.pullSecrets["*"]. Defaults may still apply.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-redis-exporter_1789327615/0000/paths/6c7a809f27215e41451b>)

#### E184

```text
Error: YAML parse error on prometheus-redis-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 32: mapping values
are not allowed in this context
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [{"0": null, "": ""}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-redis-exporter_1789327615/0000/paths/a4a0ea6ab697189bb963>)

#### E185

```text
Error: YAML parse error on prometheus-redis-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 34: block sequence
entries are not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "-"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-redis-exporter_1789327615/0000/paths/8e79b7dd85a286cfaddb>)

#### E186

```text
Error: YAML parse error on prometheus-redis-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 59: did not find
expected ',' or ']'
```

Phase: $.script | Status: failed

Selected fields (full context in artifacts):
- `$.script = {"configmap": [null, []]}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-redis-exporter_1789327615/0000/paths/24d526b3d1b52e557127>)

#### E187

```text
Error: YAML parse error on prometheus-redis-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 61: did not find
expected ',' or ']'
```

Phase: $.script.keyname | Status: failed

Selected fields (full context in artifacts):
- `$.script.keyname = [{}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-redis-exporter_1789327615/0000/paths/6d2a5388ef920dc4c06f>)

#### E188

```text
Error: YAML parse error on prometheus-redis-exporter/templates/extra-manifests.yaml: error unmarshaling JSON: while decoding JSON: json:
cannot unmarshal array into Go value of type util.SimpleHead
```

Phase: $.extraManifests | Status: failed

Selected fields (full context in artifacts):
- `$.extraManifests = [[]]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-redis-exporter_1789327615/0000/paths/48d9e37d2076ecabc7a6>)

#### E189

```text
Error: YAML parse error on prometheus-redis-exporter/templates/prometheusrule.yaml: error converting YAML to JSON: yaml: line 5: found an
indentation indicator equal to 0
```

Phase: $.prometheusRule | Status: failed

Selected fields (full context in artifacts):
- `$.prometheusRule = {"enabled": true, "namespace": ">0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-redis-exporter_1789327615/0000/paths/e58529c6a2268042286d>)

#### E190

```text
Error: YAML parse error on prometheus-redis-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 14: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-redis-exporter_1789327615/0000/paths/6e931799d09f8182f34b>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-redis-exporter_1789327615/0000>)

### charts/prometheus-smartctl-exporter

Status: failed | Attempts: 2619

#### E191

```text
Error: YAML parse error on prometheus-smartctl-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 29: did not find
expected ',' or ']'
```

Phase: $.image.pullSecrets[*] | Status: failed

Selected fields (full context in artifacts):
- No supplied value at the selected paths.
Absent from overrides: $.image.pullSecrets["*"]. Defaults may still apply.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-smartctl-exporter_1789327826/0000/paths/6c7a809f27215e41451b>)

#### E192

```text
Error: YAML parse error on prometheus-smartctl-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 30: mapping
values are not allowed in this context
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = [{"0": null, "": ""}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-smartctl-exporter_1789327826/0000/paths/a4a0ea6ab697189bb963>)

#### E193

```text
Error: YAML parse error on prometheus-smartctl-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 31: block
sequence entries are not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "-"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-smartctl-exporter_1789327826/0000/paths/8e79b7dd85a286cfaddb>)

#### E194

```text
Error: YAML parse error on prometheus-smartctl-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 36: did not find
expected key
```

Phase: $.common | Status: failed

Selected fields (full context in artifacts):
- `$.common = {"config": {"bind_to": "'"}}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-smartctl-exporter_1789327826/0000/paths/0601ec6ae51774a97371>)

#### E195

```text
Error: YAML parse error on prometheus-smartctl-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 12: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-smartctl-exporter_1789327826/0000/paths/6e931799d09f8182f34b>)

#### E264

```text
Error: prometheus-smartctl-exporter/templates/prometheusrule.yaml:19:15 executing
"prometheus-smartctl-exporter/templates/prometheusrule.yaml" at <.enabled>: nil pointer evaluating interface {}.enabled
```

Phase: $.prometheusRules | Status: failed

Selected fields (full context in artifacts):
- `$.prometheusRules = {"enabled": true, "rules": {"": null}}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-smartctl-exporter_1789327826/0000/paths/fb499fc59439090cba8d>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-smartctl-exporter_1789327826/0000>)

### charts/prometheus-snmp-exporter

Status: failed | Attempts: 2114

#### E196

```text
Error: YAML parse error on prometheus-snmp-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 43: block sequence
entries are not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "-"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-snmp-exporter_1789327839/0000/paths/8e79b7dd85a286cfaddb>)

#### E197

```text
Error: YAML parse error on prometheus-snmp-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 15: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-snmp-exporter_1789327839/0000/paths/6e931799d09f8182f34b>)

#### E265

```text
Error: prometheus-snmp-exporter/templates/configmap.yaml:11:27 executing "prometheus-snmp-exporter/templates/configmap.yaml" at <4>: wrong
type for value; expected string; got []interface {}
```

Phase: $.config | Status: failed

Selected fields (full context in artifacts):
- `$.config = [null]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-snmp-exporter_1789327839/0000/paths/24e6ce8e5165b2c58d67>)

#### E266

```text
Error: prometheus-snmp-exporter/templates/extra-manifests.yaml:3:7 executing "prometheus-snmp-exporter/templates/extra-manifests.yaml" at
<.>: wrong type for value; expected string; got interface {}
```

Phase: $.extraManifests | Status: failed

Selected fields (full context in artifacts):
- `$.extraManifests = [null]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-snmp-exporter_1789327839/0000/paths/48d9e37d2076ecabc7a6>)

#### E281

```text
resource has no nonempty apiVersion
```

Phase: $.route.main | Status: failed

Selected fields (full context in artifacts):
- `$.route.main = {"apiVersion": "0", "enabled": true}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-snmp-exporter_1789327839/0000/paths/4040b7d9468c882f9251>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-snmp-exporter_1789327839/0000>)

### charts/prometheus-sql-exporter

Status: failed | Attempts: 2576

#### E198

```text
Error: YAML parse error on prometheus-sql-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 33: found an
indentation indicator equal to 0
```

Phase: $.image.pullSecrets[*] | Status: failed

Selected fields (full context in artifacts):
- No supplied value at the selected paths.
Absent from overrides: $.image.pullSecrets["*"]. Defaults may still apply.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-sql-exporter_1789327879/0000/paths/6c7a809f27215e41451b>)

#### E199

```text
Error: YAML parse error on prometheus-sql-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 35: could not find
expected ':'
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullSecrets": ["\r0"]}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-sql-exporter_1789327879/0000/paths/8e79b7dd85a286cfaddb>)

#### E200

```text
Error: YAML parse error on prometheus-sql-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 38: did not find
expected key
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-sql-exporter_1789327879/0000/paths/3f7165f1837241716c3c>)

#### E201

```text
Error: YAML parse error on prometheus-sql-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 83: found unexpected
end of stream
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = ["'"]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-sql-exporter_1789327879/0000/paths/a4a0ea6ab697189bb963>)

#### E202

```text
Error: YAML parse error on prometheus-sql-exporter/templates/deployment.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.deployment.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.deployment.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-sql-exporter_1789327879/0000/paths/4d0453515f852ad02b1c>)

#### E203

```text
Error: YAML parse error on prometheus-sql-exporter/templates/prometheusrule.yaml: error converting YAML to JSON: yaml: line 5: found an
indentation indicator equal to 0
```

Phase: $.prometheusRule | Status: failed

Selected fields (full context in artifacts):
- `$.prometheusRule = {"enabled": true, "namespace": ">0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-sql-exporter_1789327879/0000/paths/e58529c6a2268042286d>)

#### E204

```text
Error: YAML parse error on prometheus-sql-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 17: found an
indentation indicator equal to 0
```

Phase: $.service.name | Status: failed

Selected fields (full context in artifacts):
- `$.service.name = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-sql-exporter_1789327879/0000/paths/16e8b0ef40bb4622d909>)

#### E205

```text
Error: YAML parse error on prometheus-sql-exporter/templates/serviceaccount.yaml: error converting YAML to JSON: yaml: line 13: did not find
expected key
```

Phase: $.serviceAccount.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount.annotations = {"\n": null}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-sql-exporter_1789327879/0000/paths/840a8a2bc50327388c2a>)

#### E271

```text
[Diagnostic shortened; full text in artifacts] ... ting it again. It is also possible that applying this much filtering will distort the
domain and/or distribution of the test, leaving your testing less rigorous than expected. If you expect this many inputs to be filtered out
during generation, you can disable this health check with @settings(suppress_health_check=[HealthCheck.filter_too_much]). See
https://hypothesis.readthedocs.io/en/latest/reference/api.html#hypothesis.HealthCheck for details.
```

Phase: $.extraEnvs[*].valueFrom | Status: generation-error

Selected fields (full context in artifacts):
- No supplied value at the selected paths.
Absent from overrides: $.extraEnvs["*"].valueFrom. Defaults may still apply.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-sql-exporter_1789327879/0000/paths/7fad271bf60e338792f2>)

#### E273

```text
[Diagnostic shortened; full text in artifacts] ...  '#/$defs/uriString'}, 'additionalProperties': {'type': 'boolean'}}, '$comment': {'type':
'string'}, '$defs': {'type': 'object', 'additionalProperties': {'$dynamicRef': '#meta'}}}, '$defs': {'anchorString': {'type': 'string',
'pattern': '^[A-Za-z_][-A-Za-z0-9._]*$'}, 'uriString': {'type': 'string', 'format': 'uri'}, 'uriReferenceString': {'type': 'string',
'format': 'uri-reference'}}} On schema['properties']['extraEnvs']['items']: [{'const': ''}]
```

Phase: $.extraEnvs[*] | Status: generation-error

Selected fields (full context in artifacts):
- No supplied value at the selected paths.
Absent from overrides: $.extraEnvs["*"]. Defaults may still apply.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-sql-exporter_1789327879/0000/paths/cca2d03f64715c2d3d43>)

#### E281

```text
resource has no nonempty apiVersion
```

Phase: $.extraManifests | Status: failed

Selected fields (full context in artifacts):
- `$.extraManifests = [{}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-sql-exporter_1789327879/0000/paths/48d9e37d2076ecabc7a6>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-sql-exporter_1789327879/0000>)

### charts/prometheus-stackdriver-exporter

Status: failed | Attempts: 2658

#### E206

```text
Error: YAML parse error on prometheus-stackdriver-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 39: could
not find expected ':'
```

Phase: $.image.pullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullSecrets = {"": {"\r": null}}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-stackdriver-exporter_1789327916/0000/paths/a4a0ea6ab697189bb963>)

#### E207

```text
Error: YAML parse error on prometheus-stackdriver-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 41: did not
find expected key
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-stackdriver-exporter_1789327916/0000/paths/3f7165f1837241716c3c>)

#### E208

```text
Error: YAML parse error on prometheus-stackdriver-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 43: did not
find expected key
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "\""}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-stackdriver-exporter_1789327916/0000/paths/8e79b7dd85a286cfaddb>)

#### E209

```text
Error: YAML parse error on prometheus-stackdriver-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 60: could
not find expected ':'
```

Phase: $.stackdriver.backoffJitter | Status: failed

Selected fields (full context in artifacts):
- `$.stackdriver.backoffJitter = "\n0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-stackdriver-exporter_1789327916/0000/paths/235164b351ae8bdafed7>)

Phase: $.web | Status: failed

Selected fields (full context in artifacts):
- `$.web = {"listenAddress": "\n0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-stackdriver-exporter_1789327916/0000/paths/2a0d5e566c38f5a1eb7d>)

#### E210

```text
Error: YAML parse error on prometheus-stackdriver-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 61: could
not find expected ':'
```

Phase: $.stackdriver.metrics.filters | Status: failed

Selected fields (full context in artifacts):
- `$.stackdriver.metrics.filters = [{"\r": null}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-stackdriver-exporter_1789327916/0000/paths/27f965a6daa64a89db50>)

Phase: $.stackdriver.universeDomain | Status: failed

Selected fields (full context in artifacts):
- `$.stackdriver.universeDomain = "\n0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-stackdriver-exporter_1789327916/0000/paths/ce35a1b4c6e1b6c0778e>)

#### E211

```text
Error: YAML parse error on prometheus-stackdriver-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 79: found
unexpected end of stream
```

Phase: $.stackdriver.projectIds[*] | Status: failed

Selected fields (full context in artifacts):
- No supplied value at the selected paths.
Absent from overrides: $.stackdriver.projectIds["*"]. Defaults may still apply.

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-stackdriver-exporter_1789327916/0000/paths/261a9701f261def3da8f>)

#### E212

```text
Error: YAML parse error on prometheus-stackdriver-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 80: found
unexpected end of stream
```

Phase: $.stackdriver.projectFilters | Status: failed

Selected fields (full context in artifacts):
- `$.stackdriver.projectFilters = "\n"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-stackdriver-exporter_1789327916/0000/paths/9853fd7e5ac3c77fb1a3>)

#### E213

```text
Error: YAML parse error on prometheus-stackdriver-exporter/templates/prometheusrule.yaml: error converting YAML to JSON: yaml: line 5: found
an indentation indicator equal to 0
```

Phase: $.prometheusRule | Status: failed

Selected fields (full context in artifacts):
- `$.prometheusRule = {"enabled": true, "namespace": ">0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-stackdriver-exporter_1789327916/0000/paths/e58529c6a2268042286d>)

#### E214

```text
Error: YAML parse error on prometheus-stackdriver-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 15: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-stackdriver-exporter_1789327916/0000/paths/6e931799d09f8182f34b>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-stackdriver-exporter_1789327916/0000>)

### charts/prometheus-statsd-exporter

Status: failed | Attempts: 2783

#### E215

```text
Error: YAML parse error on prometheus-statsd-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 32: did not find
expected key
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-statsd-exporter_1789328127/0000/paths/3f7165f1837241716c3c>)

#### E216

```text
Error: YAML parse error on prometheus-statsd-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 34: block
sequence entries are not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "-"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-statsd-exporter_1789328127/0000/paths/8e79b7dd85a286cfaddb>)

#### E217

```text
Error: YAML parse error on prometheus-statsd-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 34: found an
indentation indicator equal to 0
```

Phase: $.extraEnv | Status: failed

Selected fields (full context in artifacts):
- `$.extraEnv = {">0": null}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-statsd-exporter_1789328127/0000/paths/fcdb2a98d24bd18c59a4>)

#### E218

```text
Error: YAML parse error on prometheus-statsd-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 12: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-statsd-exporter_1789328127/0000/paths/6e931799d09f8182f34b>)

#### E219

```text
Error: YAML parse error on prometheus-statsd-exporter/templates/service.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.service.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.service.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-statsd-exporter_1789328127/0000/paths/98a2bca1991be60ae38a>)

#### E220

```text
Error: YAML parse error on prometheus-statsd-exporter/templates/serviceaccount.yaml: error unmarshaling JSON: while decoding JSON: json:
cannot unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.serviceAccount.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-statsd-exporter_1789328127/0000/paths/840a8a2bc50327388c2a>)

#### E267

```text
Error: prometheus-statsd-exporter/templates/deployment.yaml:18:28 executing "prometheus-statsd-exporter/templates/deployment.yaml" at
<include (print $.Template.BasePath "/configmap.yaml") .>: error calling include: prometheus-statsd-exporter/templates/configmap.yaml:12:19
executing "prometheus-statsd-exporter/templates/configmap.yaml" at <4>: wrong type for value; expected string; got []interface {}
```

Phase: $.statsd.mappingConfig | Status: failed

Selected fields (full context in artifacts):
- `$.statsd.mappingConfig = [null]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-statsd-exporter_1789328127/0000/paths/ea25c79ea1617db2194b>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-statsd-exporter_1789328127/0000>)

### charts/prometheus-systemd-exporter

Status: failed | Attempts: 2484

#### E221

```text
Error: YAML parse error on prometheus-systemd-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 38: did not find
expected '-' indicator
```

Phase: $.imagePullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.imagePullSecrets = [{"": null, "0": null}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-systemd-exporter_1789328140/0000/paths/963d7244018d7b060689>)

Phase: $.global.imagePullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.global.imagePullSecrets = [{"": null, "0": null}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-systemd-exporter_1789328140/0000/paths/097f6358a00dddbcdd83>)

#### E222

```text
Error: YAML parse error on prometheus-systemd-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 46: did not find
expected comment or line break
```

Phase: $.global.imageRegistry | Status: failed

Selected fields (full context in artifacts):
- `$.global.imageRegistry = ">"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-systemd-exporter_1789328140/0000/paths/fa90b40f46c6c70d8821>)

#### E223

```text
Error: YAML parse error on prometheus-systemd-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 48: could not
find expected ':'
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"digest": "\n0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-systemd-exporter_1789328140/0000/paths/8e79b7dd85a286cfaddb>)

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\n"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-systemd-exporter_1789328140/0000/paths/3f7165f1837241716c3c>)

#### E224

```text
Error: YAML parse error on prometheus-systemd-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 52: could not
find expected ':'
```

Phase: $.config.log | Status: failed

Selected fields (full context in artifacts):
- `$.config.log = {"level": "\n0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-systemd-exporter_1789328140/0000/paths/deda5fa63ba0b8862105>)

Phase: $.config | Status: failed

Selected fields (full context in artifacts):
- `$.config = {"log": {"level": "\n0"}}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-systemd-exporter_1789328140/0000/paths/24e6ce8e5165b2c58d67>)

#### E225

```text
Error: YAML parse error on prometheus-systemd-exporter/templates/daemonset.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.daemonsetAnnotations | Status: failed

Selected fields (full context in artifacts):
- `$.daemonsetAnnotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-systemd-exporter_1789328140/0000/paths/2e93a3c57e04dfa290b1>)

#### E226

```text
Error: YAML parse error on prometheus-systemd-exporter/templates/prometheusrule.yaml: error converting YAML to JSON: yaml: line 5: found an
indentation indicator equal to 0
```

Phase: $.prometheus.rules | Status: failed

Selected fields (full context in artifacts):
- `$.prometheus.rules = {"enabled": true, "namespace": ">0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-systemd-exporter_1789328140/0000/paths/06032f977468f2151a0d>)

#### E227

```text
Error: YAML parse error on prometheus-systemd-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 17: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-systemd-exporter_1789328140/0000/paths/6e931799d09f8182f34b>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-systemd-exporter_1789328140/0000>)

### charts/prometheus-to-sd

Status: failed | Attempts: 982

#### E228

```text
Error: YAML parse error on prometheus-to-sd/templates/deployment.yaml: error converting YAML to JSON: yaml: line 23: did not find expected
key
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-to-sd_1789328181/0000/paths/3f7165f1837241716c3c>)

#### E229

```text
Error: YAML parse error on prometheus-to-sd/templates/deployment.yaml: error converting YAML to JSON: yaml: line 25: block sequence entries
are not allowed in this context
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "-"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-to-sd_1789328181/0000/paths/8e79b7dd85a286cfaddb>)

#### E230

```text
Error: YAML parse error on prometheus-to-sd/templates/deployment.yaml: error converting YAML to JSON: yaml: line 25: found an indentation
indicator equal to 0
```

Phase: $.image.pullPolicy | Status: failed

Selected fields (full context in artifacts):
- `$.image.pullPolicy = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-to-sd_1789328181/0000/paths/eb979f1d0345157961ea>)

#### E231

```text
Error: YAML parse error on prometheus-to-sd/templates/deployment.yaml: error converting YAML to JSON: yaml: line 32: did not find expected
key
```

Phase: $.metricsSources | Status: failed

Selected fields (full context in artifacts):
- `$.metricsSources = {"\r": null}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-to-sd_1789328181/0000/paths/dfbec68571048d0ff433>)

#### E232

```text
Error: YAML parse error on prometheus-to-sd/templates/deployment.yaml: error converting YAML to JSON: yaml: line 35: could not find expected
':'
```

Phase: $.monitoredResourceTypes | Status: failed

Selected fields (full context in artifacts):
- `$.monitoredResourceTypes = "\n0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-to-sd_1789328181/0000/paths/5ac0ecb1ac8ef8d5c8da>)

Phase: $.metricsSources["kube-state-metrics"] | Status: failed

Selected fields (full context in artifacts):
- `$.metricsSources["kube-state-metrics"] = "\n0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-to-sd_1789328181/0000/paths/9cce132dc67f7111f7f8>)

#### E233

```text
Error: YAML parse error on prometheus-to-sd/templates/deployment.yaml: error converting YAML to JSON: yaml: line 36: found unexpected end of
stream
```

Phase: $.image.tag | Status: failed

Selected fields (full context in artifacts):
- `$.image.tag = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-to-sd_1789328181/0000/paths/7e365cc9986c8fb6c4ad>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-to-sd_1789328181/0000>)

### charts/prometheus-windows-exporter

Status: failed | Attempts: 2018

#### E234

```text
Error: YAML parse error on prometheus-windows-exporter/templates/config.yaml: error converting YAML to JSON: yaml: line 18: could not find
expected ':'
```

Phase: $.config | Status: failed

Selected fields (full context in artifacts):
- `$.config = "\r0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-windows-exporter_1789328217/0000/paths/24e6ce8e5165b2c58d67>)

#### E235

```text
Error: YAML parse error on prometheus-windows-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 45: could not
find expected ':'
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"digest": "\n0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-windows-exporter_1789328217/0000/paths/8e79b7dd85a286cfaddb>)

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\n"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-windows-exporter_1789328217/0000/paths/3f7165f1837241716c3c>)

#### E236

```text
Error: YAML parse error on prometheus-windows-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 75: found an
indentation indicator equal to 0
```

Phase: $.readinessProbe.httpGet.path | Status: failed

Selected fields (full context in artifacts):
- `$.readinessProbe.httpGet.path = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-windows-exporter_1789328217/0000/paths/a4433106ca2996c801fe>)

#### E237

```text
Error: YAML parse error on prometheus-windows-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 87: did not find
expected '-' indicator
```

Phase: $.imagePullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.imagePullSecrets = [{"": null, "0": null}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-windows-exporter_1789328217/0000/paths/963d7244018d7b060689>)

Phase: $.global.imagePullSecrets | Status: failed

Selected fields (full context in artifacts):
- `$.global.imagePullSecrets = [{"": null, "0": null}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-windows-exporter_1789328217/0000/paths/097f6358a00dddbcdd83>)

#### E238

```text
Error: YAML parse error on prometheus-windows-exporter/templates/daemonset.yaml: error unmarshaling JSON: while decoding JSON: json: cannot
unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.daemonsetAnnotations | Status: failed

Selected fields (full context in artifacts):
- `$.daemonsetAnnotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-windows-exporter_1789328217/0000/paths/2e93a3c57e04dfa290b1>)

#### E239

```text
Error: YAML parse error on prometheus-windows-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 15: found an
indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-windows-exporter_1789328217/0000/paths/6e931799d09f8182f34b>)

#### E240

```text
Error: YAML parse error on prometheus-windows-exporter/templates/serviceaccount.yaml: error unmarshaling JSON: while decoding JSON: json:
cannot unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.serviceAccount.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-windows-exporter_1789328217/0000/paths/840a8a2bc50327388c2a>)

#### E268

```text
Error: prometheus-windows-exporter/templates/daemonset.yaml:127:23 executing "prometheus-windows-exporter/templates/daemonset.yaml" at
<.name>: nil pointer evaluating interface {}.name
```

Phase: $.secrets | Status: failed

Selected fields (full context in artifacts):
- `$.secrets = [null]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-windows-exporter_1789328217/0000/paths/12727a3b60a60e40fafe>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-windows-exporter_1789328217/0000>)

### charts/prometheus-yet-another-cloudwatch-exporter

Status: failed | Attempts: 2872

#### E241

```text
Error: YAML parse error on prometheus-yet-another-cloudwatch-exporter/templates/configmap.yaml: error converting YAML to JSON: yaml: line
15: could not find expected ':'
```

Phase: $.config | Status: failed

Selected fields (full context in artifacts):
- `$.config = "\r0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-yet-another-cloudwatch-exporter_1789328252/0000/paths/24e6ce8e5165b2c58d67>)

#### E242

```text
Error: YAML parse error on prometheus-yet-another-cloudwatch-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line
19: did not find expected ',' or ']'
```

Phase: $.aws | Status: failed

Selected fields (full context in artifacts):
- `$.aws = {"role": [{}]}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-yet-another-cloudwatch-exporter_1789328252/0000/paths/85fe62d4914b75150381>)

#### E243

```text
Error: YAML parse error on prometheus-yet-another-cloudwatch-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line
32: did not find expected key
```

Phase: $.image.repository | Status: failed

Selected fields (full context in artifacts):
- `$.image.repository = "\""`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-yet-another-cloudwatch-exporter_1789328252/0000/paths/3f7165f1837241716c3c>)

#### E244

```text
Error: YAML parse error on prometheus-yet-another-cloudwatch-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line
36: could not find expected ':'
```

Phase: $.image | Status: failed

Selected fields (full context in artifacts):
- `$.image = {"pullPolicy": "\r0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-yet-another-cloudwatch-exporter_1789328252/0000/paths/8e79b7dd85a286cfaddb>)

#### E245

```text
Error: YAML parse error on prometheus-yet-another-cloudwatch-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line
40: could not find expected ':'
```

Phase: $.extraArgs | Status: failed

Selected fields (full context in artifacts):
- `$.extraArgs = {"\n": null}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-yet-another-cloudwatch-exporter_1789328252/0000/paths/6b07fe5f61f90919fc2a>)

#### E246

```text
Error: YAML parse error on prometheus-yet-another-cloudwatch-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line
43: found an indentation indicator equal to 0
```

Phase: $.portName | Status: failed

Selected fields (full context in artifacts):
- `$.portName = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-yet-another-cloudwatch-exporter_1789328252/0000/paths/a39789a46c9f2f8a2210>)

#### E247

```text
Error: YAML parse error on prometheus-yet-another-cloudwatch-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line
45: did not find expected ',' or ']'
```

Phase: $.aws.secret.name | Status: failed

Selected fields (full context in artifacts):
- `$.aws.secret.name = [{}]`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-yet-another-cloudwatch-exporter_1789328252/0000/paths/c08b45ef27291722546b>)

#### E248

```text
Error: YAML parse error on prometheus-yet-another-cloudwatch-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line
48: could not find expected ':'
```

Phase: $.aws.secret | Status: failed

Selected fields (full context in artifacts):
- `$.aws.secret = {"name": "\r0"}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-yet-another-cloudwatch-exporter_1789328252/0000/paths/0b35a16c8f7c5b24fdc1>)

#### E249

```text
Error: YAML parse error on prometheus-yet-another-cloudwatch-exporter/templates/prometheusrule.yaml: error converting YAML to JSON: yaml:
line 11: could not find expected ':'
```

Phase: $.prometheusRule | Status: failed

Selected fields (full context in artifacts):
- `$.prometheusRule = {"enabled": true, "labels": true}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-yet-another-cloudwatch-exporter_1789328252/0000/paths/e58529c6a2268042286d>)

#### E250

```text
Error: YAML parse error on prometheus-yet-another-cloudwatch-exporter/templates/service.yaml: error converting YAML to JSON: yaml: line 12:
found an indentation indicator equal to 0
```

Phase: $.service.type | Status: failed

Selected fields (full context in artifacts):
- `$.service.type = ">0"`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-yet-another-cloudwatch-exporter_1789328252/0000/paths/6e931799d09f8182f34b>)

#### E251

```text
Error: YAML parse error on prometheus-yet-another-cloudwatch-exporter/templates/service.yaml: error unmarshaling JSON: while decoding JSON:
json: cannot unmarshal array into Go struct field .metadata.annotations. of type string
```

Phase: $.service.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.service.annotations = {"": []}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-yet-another-cloudwatch-exporter_1789328252/0000/paths/98a2bca1991be60ae38a>)

#### E269

```text
Error: prometheus-yet-another-cloudwatch-exporter/templates/serviceaccount.yaml:15:42 executing
"prometheus-yet-another-cloudwatch-exporter/templates/serviceaccount.yaml" at <$v>: wrong type for value; expected string; got interface {}
```

Phase: $.serviceAccount.annotations | Status: failed

Selected fields (full context in artifacts):
- `$.serviceAccount.annotations = {"": null}`

[Full input and diagnostic](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-yet-another-cloudwatch-exporter_1789328252/0000/paths/840a8a2bc50327388c2a>)

[Chart artifacts](<https://github.com/astrivant/hypothesis-helm/tree/main/docs/reports/prometheus-runs/prometheus-charts_1789311940/runs/prometheus-yet-another-cloudwatch-exporter_1789328252/0000>)
