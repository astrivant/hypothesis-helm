# Prometheus Community Helm chart scan

Visited all **46 discovered charts** with **--filter**, four workers, and a **five-minute test budget per chart**. No scan-wide deadline was
imposed.

Recorded **6,515 test attempts** in **7.2 minutes**. Attempts include shrinking and repeated inputs; they are not counts of unique inputs or
confirmed bugs.

**Findings:** 1 baseline-failed; 42 failed; 1 missing-values; 2 time-limit.

**known-inputs:** 41 failed; 1 generation-error; 2 time-limit.

**robustness:** 8 failed; 34 passed; 2 time-limit.

Observed failures include chart validation rejections, rendering failures, and possible tooling limitations. Inferred inputs are not an
authoritative chart contract. Findings need triage before being called chart defects; time-limited coverage remains incomplete.

Checks: dependency build in isolated copies, Helm lint, Helm template with values-schema checks, and built-in manifest checks. External
kubeconform/kubesec validation was not configured.

Source: `third_party/prometheus-community-helm-charts` at `732bf3642c931946f1962fbd2e1b694ce8827e77`; Helm 4.3.0. Per-worker dependency
caches are isolated. Each primary chart has one dedicated job; nested results from parent jobs are retained separately and excluded from
totals.

[Combined PDF](prometheus.pdf) · [Aggregate data](prometheus-runs/prometheus-charts_1789260855/scan.json.gz) ·
[Raw logs and provenance](prometheus-runs/prometheus-charts_1789260855/README.md)

Coverage notes: Alertmanager known-input generation could not expand the recursive schema at config.route.routes[*]; its deferred robustness
phase still ran. Prometheus PostgreSQL Exporter failed baseline lint because datasource password configuration was not supplied. The nested
CRD chart lacks values.yaml. Kube-Prometheus Stack and Prometheus Operator CRDs reached their test budgets.

Directory: third_party/prometheus-community-helm-charts
Started (Unix epoch): 1789263973
Elapsed: 434.00 seconds
Charts discovered: 46
Scan status: completed
Discovery complete: True
Unstarted charts: 0

Results describe the tested sample; they do not prove chart correctness.
Baseline-only, skipped, blocked, and incomplete charts are not property-test passes.

## Status counts

```json
{
  "baseline-failed": 1,
  "failed": 42,
  "missing-values": 1,
  "time-limit": 2
}
```

## Settings

```json
{
  "max_examples": 100,
  "filter": true,
  "fail": false,
  "permutations": null,
  "chart_timeout_seconds": 300.0,
  "scan_timeout_seconds": null,
  "helm": "Helm 4.3.0",
  "seed": 0,
  "build_dependencies": true,
  "values": "values.yaml",
  "clone_timeout_seconds": 180,
  "workers": 4,
  "external_conformity": false
}
```

## Errors

45 distinct diagnostics across 53 occurrences; 8 repeats grouped.
Matching diagnostics do not establish a shared root cause.

### E001

```text
==> Linting /var/folders/dd/pd400p1j4vgf5gv6qp6zfx000000gn/T/hypothesis-helm-scan-gndz6572/chart
[INFO] Chart.yaml: icon is recommended
[ERROR] templates/: prometheus-postgres-exporter/templates/secrets.yaml:12:38
  executing "prometheus-postgres-exporter/templates/secrets.yaml" at <.Values.config.datasource.password>:
    wrong type for value; expected string; got interface {}

level=WARN msg="missing required value" message="config.datasource.password is required when not using config.datasource.passwordSecret, config.datasource.passwordFile, or config.datasourceSecret"
Error: 1 chart(s) linted, 1 chart(s) failed
```

- [charts/prometheus-postgres-exporter (chart; baseline-failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-postgres-exporter_1789264137/0000>)

### E002

```text
Error: YAML parse error on alertmanager-snmp-notifier/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/alertmanager-snmp-notifier (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/alertmanager-snmp-notifier_1789263974/0000>)

### E003

```text
Error: YAML parse error on alertmanager-snmp-notifier/templates/service.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/alertmanager-snmp-notifier (robustness; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/alertmanager-snmp-notifier_1789263974/0000>)

### E004

```text
Error: YAML parse error on jiralert/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/jiralert (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/jiralert_1789263974/0000>)

### E005

```text
Error: YAML parse error on kube-state-metrics/templates/extra-manifests.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go value of type util.SimpleHead
```

- [charts/kube-state-metrics (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/kube-state-metrics_1789263977/0000>)

### E006

```text
Error: YAML parse error on prom-label-proxy/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/prom-label-proxy (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prom-label-proxy_1789263985/0000>)

### E007

```text
Error: YAML parse error on prometheus-adapter/templates/certmanager.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/prometheus-adapter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-adapter_1789263996/0000>)

### E008

```text
Error: YAML parse error on prometheus-blackbox-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/prometheus-blackbox-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-blackbox-exporter_1789264001/0000>)

### E009

```text
Error: YAML parse error on prometheus-consul-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/prometheus-consul-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-consul-exporter_1789264018/0000>)

### E010

```text
Error: YAML parse error on prometheus-druid-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/prometheus-druid-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-druid-exporter_1789264027/0000>)

### E011

```text
Error: YAML parse error on prometheus-elasticsearch-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 56: did not find expected node content
```

- [charts/prometheus-elasticsearch-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-elasticsearch-exporter_1789264032/0000>)

### E012

```text
Error: YAML parse error on prometheus-ipmi-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/prometheus-ipmi-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-ipmi-exporter_1789264041/0000>)
- [charts/prometheus-ipmi-exporter (robustness; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-ipmi-exporter_1789264041/0000>)

### E013

```text
Error: YAML parse error on prometheus-kafka-exporter/templates/deployment.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go struct field .metadata.annotations. of type string
```

- [charts/prometheus-kafka-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-kafka-exporter_1789264050/0000>)

### E014

```text
Error: YAML parse error on prometheus-modbus-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 64: did not find expected ',' or ']'
```

- [charts/prometheus-modbus-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-modbus-exporter_1789264058/0000>)

### E015

```text
Error: YAML parse error on prometheus-mongodb-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/prometheus-mongodb-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-mongodb-exporter_1789264063/0000>)

### E016

```text
Error: YAML parse error on prometheus-mysql-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/prometheus-mysql-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-mysql-exporter_1789264067/0000>)

### E017

```text
Error: YAML parse error on prometheus-mysql-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 30: mapping keys are not allowed in this context
```

- [charts/prometheus-mysql-exporter (robustness; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-mysql-exporter_1789264067/0000>)

### E018

```text
Error: YAML parse error on prometheus-nats-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 60: could not find expected ':'
```

- [charts/prometheus-nats-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-nats-exporter_1789264071/0000>)

### E019

```text
Error: YAML parse error on prometheus-nginx-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/prometheus-nginx-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-nginx-exporter_1789264076/0000>)

### E020

```text
Error: YAML parse error on prometheus-operator-admission-webhook/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/prometheus-operator-admission-webhook (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-operator-admission-webhook_1789264092/0000>)
- [charts/prometheus-operator-admission-webhook (robustness; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-operator-admission-webhook_1789264092/0000>)

### E021

```text
Error: YAML parse error on prometheus-pgbouncer-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/prometheus-pgbouncer-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-pgbouncer-exporter_1789264113/0000>)

### E022

```text
Error: YAML parse error on prometheus-pingmesh-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/prometheus-pingmesh-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-pingmesh-exporter_1789264127/0000>)

### E023

```text
Error: YAML parse error on prometheus-pushgateway/templates/service.yaml: error converting YAML to JSON: yaml: line 24: found unexpected end of stream
```

- [charts/prometheus-pushgateway (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-pushgateway_1789264138/0000>)

### E024

```text
Error: YAML parse error on prometheus-rabbitmq-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/prometheus-rabbitmq-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-rabbitmq-exporter_1789264152/0000>)

### E025

```text
Error: YAML parse error on prometheus-redis-exporter/templates/service.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go struct field .metadata.annotations. of type string
```

- [charts/prometheus-redis-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-redis-exporter_1789264160/0000>)

### E026

```text
Error: YAML parse error on prometheus-snmp-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 64: found unexpected end of stream
```

- [charts/prometheus-snmp-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-snmp-exporter_1789264181/0000>)

### E027

```text
Error: YAML parse error on prometheus-sql-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/prometheus-sql-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-sql-exporter_1789264189/0000>)
- [charts/prometheus-sql-exporter (robustness; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-sql-exporter_1789264189/0000>)

### E028

```text
Error: YAML parse error on prometheus-stackdriver-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: line 78: found unexpected end of stream
```

- [charts/prometheus-stackdriver-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-stackdriver-exporter_1789264201/0000>)

### E029

```text
Error: YAML parse error on prometheus-statsd-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/prometheus-statsd-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-statsd-exporter_1789264214/0000>)

### E030

```text
Error: YAML parse error on prometheus-systemd-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/prometheus-systemd-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-systemd-exporter_1789264223/0000>)

### E031

```text
Error: YAML parse error on prometheus-to-sd/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/prometheus-to-sd (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-to-sd_1789264230/0000>)

### E032

```text
Error: YAML parse error on prometheus-windows-exporter/templates/config.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/prometheus-windows-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-windows-exporter_1789264239/0000>)

### E033

```text
Error: YAML parse error on prometheus-yet-another-cloudwatch-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed
```

- [charts/prometheus-yet-another-cloudwatch-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-yet-another-cloudwatch-exporter_1789264241/0000>)

### E034

```text
Error: prometheus-couchdb-exporter/templates/NOTES.txt:3:17
  executing "prometheus-couchdb-exporter/templates/NOTES.txt" at <.Values.ingress.hosts>:
    range can't iterate over false
```

- [charts/prometheus-couchdb-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-couchdb-exporter_1789264025/0000>)

### E035

```text
Error: prometheus-node-exporter/templates/daemonset.yaml:222:29
  executing "prometheus-node-exporter/templates/daemonset.yaml" at <$mount.name>:
    nil pointer evaluating interface {}.name
```

- [charts/prometheus-node-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-node-exporter_1789264082/0000>)

### E036

```text
Error: prometheus-smartctl-exporter/templates/daemonset.yaml:5:35
  executing "prometheus-smartctl-exporter/templates/daemonset.yaml" at <$item.config>:
    nil pointer evaluating interface {}.config
```

- [charts/prometheus-smartctl-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-smartctl-exporter_1789264178/0000>)

### E037

```text
Known-input preparation or testing exhausted its phase budget
```

- [charts/kube-prometheus-stack (known-inputs; time-limit)](<prometheus-runs/prometheus-charts_1789260855/runs/kube-prometheus-stack_1789263974/0000>)

### E038

```text
Selected values file not found: /Users/emmadoyle/projects/personal/hypothesis-helm/third_party/prometheus-community-helm-charts/charts/prometheus-operator-crds/charts/crds/values.yaml
```

- [charts/prometheus-operator-crds/charts/crds (chart; missing-values)](<prometheus-runs/prometheus-charts_1789260855/runs/crds_1789264112/0000>)

### E039

```text
chart rendered no resources (use allow_empty explicitly)
```

- [charts/kube-prometheus-stack/charts/crds (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/crds_1789263976/0000>)
- [charts/kube-prometheus-stack/charts/crds (robustness; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/crds_1789263976/0000>)

### E040

Source: prometheus-fastly-exporter 0.14.1 / templates/secret.yaml

```text
execution error at (prometheus-fastly-exporter/templates/secret.yaml:10:23): A Fastly token is required
```

- [charts/prometheus-fastly-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-fastly-exporter_1789264040/0000>)

### E041

```text
invalid rendered YAML: more indented follow up line than first in a block scalar
  in "<unicode string>", line 49, column 1:
    ---
    ^ (line: 49)
```

- [charts/prometheus-cloudwatch-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-cloudwatch-exporter_1789264003/0000>)

### E042

```text
invalid rendered YAML: while scanning for the next token
found character '\t' that cannot start any token
  in "<unicode string>", line 1359, column 21:
        - apiVersion: v1
                        ^ (line: 1359)
```

- [charts/prometheus (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus_1789263989/0000>)
- [charts/prometheus (robustness; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus_1789263989/0000>)

### E043

```text
invalid rendered YAML: while scanning for the next token
found character '\t' that cannot start any token
  in "<unicode string>", line 165, column 21:
        - apiVersion: v1
                        ^ (line: 165)
```

- [charts/alertmanager (robustness; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/alertmanager_1789263974/0000>)

### E044

```text
recursive schema at ('config', 'route', 'routes', '*')
```

- [charts/alertmanager (known-inputs; generation-error)](<prometheus-runs/prometheus-charts_1789260855/runs/alertmanager_1789263974/0000>)

### E045

```text
resource has no metadata.name
```

- [charts/prometheus-conntrack-stats-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-conntrack-stats-exporter_1789264015/0000>)
- [charts/prometheus-json-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-json-exporter_1789264046/0000>)
- [charts/prometheus-memcached-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-memcached-exporter_1789264051/0000>)
- [charts/prometheus-pingdom-exporter (known-inputs; failed)](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-pingdom-exporter_1789264121/0000>)

## Charts

### charts/alertmanager

Result: FAIL | Status: failed
Attempts: 1 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/alertmanager_1789263974/0000](<prometheus-runs/prometheus-charts_1789260855/runs/alertmanager_1789263974/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 120 | Varied in render attempts: 0
Missing values: 15 | Undocumented template fields: 48
Unreferenced values: 4 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: generation-error | Attempts: 0

Phase robustness: failed | Attempts: 1

Errors: [E044](#e044), [E043](#e043)

Reproducing values (robustness):

```json
{}
```

### charts/alertmanager-snmp-notifier

Result: FAIL | Status: failed
Attempts: 59 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/alertmanager-snmp-notifier_1789263974/0000](<prometheus-runs/prometheus-charts_1789260855/runs/alertmanager-snmp-notifier_1789263974/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 58 | Varied in render attempts: 15
Missing values: 27 | Undocumented template fields: 23
Unreferenced values: 4 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 18

Phase robustness: failed | Attempts: 41

Errors: [E002](#e002), [E003](#e003)

Reproducing values (known-inputs):

```json
{
  "image": {
    "repository": "\u001f"
  },
  "replicaCount": 0,
  "service": {
    "port": 0,
    "type": ""
  },
  "serviceAccount": {
    "create": false
  },
  "snmpNotifier": {}
}
```

Reproducing values (robustness):

```json
{
  "image": {
    "repository": ""
  },
  "replicaCount": 0,
  "service": {
    "port": 0,
    "type": "\u001f",
    "": []
  },
  "serviceAccount": {
    "create": false
  },
  "snmpNotifier": {}
}
```

### charts/jiralert

Result: FAIL | Status: failed
Attempts: 143 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/jiralert_1789263974/0000](<prometheus-runs/prometheus-charts_1789260855/runs/jiralert_1789263974/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 51 | Varied in render attempts: 1
Missing values: 7 | Undocumented template fields: 56
Unreferenced values: 4 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 42

Phase robustness: passed | Attempts: 101

Errors: [E004](#e004)

Reproducing values (known-inputs):

```json
{
  "existingConfigSecret": "\b"
}
```

### charts/kube-prometheus-stack

Result: N/A | Status: time-limit
Attempts: 29 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/kube-prometheus-stack_1789263974/0000](<prometheus-runs/prometheus-charts_1789260855/runs/kube-prometheus-stack_1789263974/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 1536 | Varied in render attempts: 0
Missing values: 525 | Undocumented template fields: 1594
Unreferenced values: 0 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: time-limit | Attempts: 0

Phase robustness: time-limit | Attempts: 29

Errors: [E037](#e037)

### charts/kube-prometheus-stack/charts/crds

Result: FAIL | Status: failed
Attempts: 2 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/crds_1789263976/0000](<prometheus-runs/prometheus-charts_1789260855/runs/crds_1789263976/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 34 | Varied in render attempts: 0
Missing values: 33 | Undocumented template fields: 34
Unreferenced values: 0 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 1

Phase robustness: failed | Attempts: 1

Errors: [E039](#e039)

Reproducing values (known-inputs):

```json
{}
```

Reproducing values (robustness):

```json
{}
```

### charts/kube-state-metrics

Result: FAIL | Status: failed
Attempts: 151 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/kube-state-metrics_1789263977/0000](<prometheus-runs/prometheus-charts_1789260855/runs/kube-state-metrics_1789263977/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 166 | Varied in render attempts: 20
Missing values: 22 | Undocumented template fields: 169
Unreferenced values: 0 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 50

Phase robustness: passed | Attempts: 101

Errors: [E005](#e005)

Reproducing values (known-inputs):

```json
{
  "extraManifests": [
    []
  ]
}
```

### charts/prom-label-proxy

Result: FAIL | Status: failed
Attempts: 157 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prom-label-proxy_1789263985/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prom-label-proxy_1789263985/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 70 | Varied in render attempts: 9
Missing values: 3 | Undocumented template fields: 75
Unreferenced values: 6 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 56

Phase robustness: passed | Attempts: 101

Errors: [E006](#e006)

Reproducing values (known-inputs):

```json
{
  "config": {
    "label": "\u001f"
  }
}
```

### charts/prometheus

Result: FAIL | Status: failed
Attempts: 2 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus_1789263989/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus_1789263989/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 170 | Varied in render attempts: 0
Missing values: 17 | Undocumented template fields: 34
Unreferenced values: 0 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 1

Phase robustness: failed | Attempts: 1

Errors: [E042](#e042)

Reproducing values (known-inputs):

```json
{}
```

Reproducing values (robustness):

```json
{}
```

### charts/prometheus-adapter

Result: FAIL | Status: failed
Attempts: 263 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-adapter_1789263996/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-adapter_1789263996/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 70 | Varied in render attempts: 59
Missing values: 3 | Undocumented template fields: 71
Unreferenced values: 5 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 162

Phase robustness: passed | Attempts: 101

Errors: [E007](#e007)

Reproducing values (known-inputs):

```json
{
  "certManager": {
    "caCertDuration": "\u001f",
    "enabled": true
  }
}
```

### charts/prometheus-blackbox-exporter

Result: FAIL | Status: failed
Attempts: 134 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-blackbox-exporter_1789264001/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-blackbox-exporter_1789264001/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 93 | Varied in render attempts: 1
Missing values: 4 | Undocumented template fields: 97
Unreferenced values: 70 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 33

Phase robustness: passed | Attempts: 101

Errors: [E008](#e008)

Reproducing values (known-inputs):

```json
{
  "configExistingSecretName": "\u001f"
}
```

### charts/prometheus-cloudwatch-exporter

Result: FAIL | Status: failed
Attempts: 134 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-cloudwatch-exporter_1789264003/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-cloudwatch-exporter_1789264003/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 69 | Varied in render attempts: 4
Missing values: 13 | Undocumented template fields: 69
Unreferenced values: 2 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 33

Phase robustness: passed | Attempts: 101

Errors: [E041](#e041)

Reproducing values (known-inputs):

```json
{
  "config": " "
}
```

### charts/prometheus-conntrack-stats-exporter

Result: FAIL | Status: failed
Attempts: 122 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-conntrack-stats-exporter_1789264015/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-conntrack-stats-exporter_1789264015/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 21 | Varied in render attempts: 0
Missing values: 0 | Undocumented template fields: 21
Unreferenced values: 4 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 21

Phase robustness: passed | Attempts: 101

Errors: [E045](#e045)

Reproducing values (known-inputs):

```json
{
  "fullnameOverride": "0"
}
```

### charts/prometheus-consul-exporter

Result: FAIL | Status: failed
Attempts: 164 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-consul-exporter_1789264018/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-consul-exporter_1789264018/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 35 | Varied in render attempts: 20
Missing values: 7 | Undocumented template fields: 36
Unreferenced values: 4 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 63

Phase robustness: passed | Attempts: 101

Errors: [E009](#e009)

Reproducing values (known-inputs):

```json
{
  "consulServer": "\u001f"
}
```

### charts/prometheus-couchdb-exporter

Result: FAIL | Status: failed
Attempts: 198 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-couchdb-exporter_1789264025/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-couchdb-exporter_1789264025/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 22 | Varied in render attempts: 11
Missing values: 2 | Undocumented template fields: 22
Unreferenced values: 1 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 97

Phase robustness: passed | Attempts: 101

Errors: [E034](#e034)

Reproducing values (known-inputs):

```json
{
  "ingress": {
    "enabled": true,
    "hosts": false
  }
}
```

### charts/prometheus-druid-exporter

Result: FAIL | Status: failed
Attempts: 164 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-druid-exporter_1789264027/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-druid-exporter_1789264027/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 24 | Varied in render attempts: 6
Missing values: 0 | Undocumented template fields: 24
Unreferenced values: 1 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 63

Phase robustness: passed | Attempts: 101

Errors: [E010](#e010)

Reproducing values (known-inputs):

```json
{
  "druidURL": "\u001f"
}
```

### charts/prometheus-elasticsearch-exporter

Result: FAIL | Status: failed
Attempts: 127 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-elasticsearch-exporter_1789264032/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-elasticsearch-exporter_1789264032/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 83 | Varied in render attempts: 20
Missing values: 3 | Undocumented template fields: 83
Unreferenced values: 16 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 26

Phase robustness: passed | Attempts: 101

Errors: [E011](#e011)

Reproducing values (known-inputs):

```json
{
  "extraArgs": [
    null
  ]
}
```

### charts/prometheus-fastly-exporter

Result: FAIL | Status: failed
Attempts: 114 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-fastly-exporter_1789264040/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-fastly-exporter_1789264040/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 42 | Varied in render attempts: 6
Missing values: 9 | Undocumented template fields: 47
Unreferenced values: 3 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 13

Phase robustness: passed | Attempts: 101

Errors: [E040](#e040)

Reproducing values (known-inputs):

```json
{
  "fastly": {
    "token": ""
  }
}
```

### charts/prometheus-ipmi-exporter

Result: FAIL | Status: failed
Attempts: 67 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-ipmi-exporter_1789264041/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-ipmi-exporter_1789264041/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 31 | Varied in render attempts: 4
Missing values: 20 | Undocumented template fields: 0
Unreferenced values: 24 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 33

Phase robustness: failed | Attempts: 34

Errors: [E012](#e012)

Reproducing values (known-inputs):

```json
{
  "image": {
    "pullPolicy": "Never",
    "repository": "\u001f"
  },
  "replicaCount": 0,
  "resources": {},
  "service": {
    "port": 1,
    "type": "NodePort"
  }
}
```

Reproducing values (robustness):

```json
{
  "image": {
    "pullPolicy": "Never",
    "repository": "\u001f",
    "": []
  },
  "replicaCount": 0,
  "resources": {},
  "service": {
    "port": 1,
    "type": "NodePort"
  }
}
```

### charts/prometheus-json-exporter

Result: FAIL | Status: failed
Attempts: 117 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-json-exporter_1789264046/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-json-exporter_1789264046/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 61 | Varied in render attempts: 0
Missing values: 1 | Undocumented template fields: 65
Unreferenced values: 3 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 16

Phase robustness: passed | Attempts: 101

Errors: [E045](#e045)

Reproducing values (known-inputs):

```json
{
  "fullnameOverride": "0"
}
```

### charts/prometheus-kafka-exporter

Result: FAIL | Status: failed
Attempts: 132 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-kafka-exporter_1789264050/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-kafka-exporter_1789264050/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 80 | Varied in render attempts: 17
Missing values: 14 | Undocumented template fields: 80
Unreferenced values: 0 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 31

Phase robustness: passed | Attempts: 101

Errors: [E013](#e013)

Reproducing values (known-inputs):

```json
{
  "deploymentAnnotations": {
    "": []
  }
}
```

### charts/prometheus-memcached-exporter

Result: FAIL | Status: failed
Attempts: 178 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-memcached-exporter_1789264051/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-memcached-exporter_1789264051/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 48 | Varied in render attempts: 29
Missing values: 17 | Undocumented template fields: 48
Unreferenced values: 3 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 77

Phase robustness: passed | Attempts: 101

Errors: [E045](#e045)

Reproducing values (known-inputs):

```json
{
  "fullnameOverride": "0"
}
```

### charts/prometheus-modbus-exporter

Result: FAIL | Status: failed
Attempts: 141 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-modbus-exporter_1789264058/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-modbus-exporter_1789264058/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 32 | Varied in render attempts: 7
Missing values: 2 | Undocumented template fields: 32
Unreferenced values: 5 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 40

Phase robustness: passed | Attempts: 101

Errors: [E014](#e014)

Reproducing values (known-inputs):

```json
{
  "configMapFile": [
    null,
    []
  ]
}
```

### charts/prometheus-mongodb-exporter

Result: FAIL | Status: failed
Attempts: 146 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-mongodb-exporter_1789264063/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-mongodb-exporter_1789264063/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 50 | Varied in render attempts: 12
Missing values: 0 | Undocumented template fields: 50
Unreferenced values: 4 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 45

Phase robustness: passed | Attempts: 101

Errors: [E015](#e015)

Reproducing values (known-inputs):

```json
{
  "existingSecret": {
    "key": "\u001f"
  }
}
```

### charts/prometheus-mysql-exporter

Result: FAIL | Status: failed
Attempts: 331 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-mysql-exporter_1789264067/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-mysql-exporter_1789264067/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 74 | Varied in render attempts: 28
Missing values: 14 | Undocumented template fields: 5
Unreferenced values: 6 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 266

Phase robustness: failed | Attempts: 65

Errors: [E016](#e016), [E017](#e017)

Reproducing values (known-inputs):

```json
{
  "namespaceOverride": "\u001f"
}
```

Reproducing values (robustness):

```json
{
  "priorityClassName": "?",
  "": []
}
```

### charts/prometheus-nats-exporter

Result: FAIL | Status: failed
Attempts: 146 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-nats-exporter_1789264071/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-nats-exporter_1789264071/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 39 | Varied in render attempts: 20
Missing values: 0 | Undocumented template fields: 39
Unreferenced values: 1 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 45

Phase robustness: passed | Attempts: 101

Errors: [E018](#e018)

Reproducing values (known-inputs):

```json
{
  "extraVolumes": "0"
}
```

### charts/prometheus-nginx-exporter

Result: FAIL | Status: failed
Attempts: 177 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-nginx-exporter_1789264076/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-nginx-exporter_1789264076/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 41 | Varied in render attempts: 38
Missing values: 1 | Undocumented template fields: 41
Unreferenced values: 6 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 76

Phase robustness: passed | Attempts: 101

Errors: [E019](#e019)

Reproducing values (known-inputs):

```json
{
  "image": {
    "pullPolicy": "\u001f"
  }
}
```

### charts/prometheus-node-exporter

Result: FAIL | Status: failed
Attempts: 186 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-node-exporter_1789264082/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-node-exporter_1789264082/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 165 | Varied in render attempts: 22
Missing values: 6 | Undocumented template fields: 171
Unreferenced values: 0 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 85

Phase robustness: passed | Attempts: 101

Errors: [E035](#e035)

Reproducing values (known-inputs):

```json
{
  "configmaps": [
    null
  ]
}
```

### charts/prometheus-operator-admission-webhook

Result: FAIL | Status: failed
Attempts: 146 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-operator-admission-webhook_1789264092/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-operator-admission-webhook_1789264092/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 97 | Varied in render attempts: 11
Missing values: 9 | Undocumented template fields: 19
Unreferenced values: 9 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 84

Phase robustness: failed | Attempts: 62

Errors: [E020](#e020)

Reproducing values (known-inputs):

```json
{
  "nameOverride": "\u001f"
}
```

Reproducing values (robustness):

```json
{
  "nameOverride": "\u001f",
  "": []
}
```

### charts/prometheus-operator-crds

Result: N/A | Status: time-limit
Attempts: 34 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-operator-crds_1789264107/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-operator-crds_1789264107/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 0 | Varied in render attempts: 0
Missing values: 0 | Undocumented template fields: 0
Unreferenced values: 11 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: time-limit | Attempts: 30

Phase robustness: time-limit | Attempts: 4

### charts/prometheus-operator-crds/charts/crds

Result: N/A | Status: missing-values
Attempts: N/A | Remaining iterations: unknown
Coverage: not exercised
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/crds_1789264112/0000](<prometheus-runs/prometheus-charts_1789260855/runs/crds_1789264112/0000>)

Filtering applied: False
Chart did not enter finite permutation testing

Errors: [E038](#e038)

### charts/prometheus-pgbouncer-exporter

Result: FAIL | Status: failed
Attempts: 142 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-pgbouncer-exporter_1789264113/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-pgbouncer-exporter_1789264113/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 62 | Varied in render attempts: 6
Missing values: 12 | Undocumented template fields: 63
Unreferenced values: 4 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 41

Phase robustness: passed | Attempts: 101

Errors: [E021](#e021)

Reproducing values (known-inputs):

```json
{
  "config": {
    "logFormat": "\u001f"
  }
}
```

### charts/prometheus-pingdom-exporter

Result: FAIL | Status: failed
Attempts: 196 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-pingdom-exporter_1789264121/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-pingdom-exporter_1789264121/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 28 | Varied in render attempts: 22
Missing values: 2 | Undocumented template fields: 29
Unreferenced values: 0 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 95

Phase robustness: passed | Attempts: 101

Errors: [E045](#e045)

Reproducing values (known-inputs):

```json
{
  "fullnameOverride": "0"
}
```

### charts/prometheus-pingmesh-exporter

Result: FAIL | Status: failed
Attempts: 182 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-pingmesh-exporter_1789264127/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-pingmesh-exporter_1789264127/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 78 | Varied in render attempts: 52
Missing values: 3 | Undocumented template fields: 90
Unreferenced values: 3 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 81

Phase robustness: passed | Attempts: 101

Errors: [E022](#e022)

Reproducing values (known-inputs):

```json
{
  "configPath": {
    "\u001f": null
  }
}
```

### charts/prometheus-postgres-exporter

Result: FAIL | Status: baseline-failed
Attempts: N/A | Remaining iterations: unknown
Coverage: defaults only
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-postgres-exporter_1789264137/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-postgres-exporter_1789264137/0000>)

Filtering applied: False
Chart did not enter finite permutation testing

Errors: [E001](#e001)

### charts/prometheus-pushgateway

Result: FAIL | Status: failed
Attempts: 190 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-pushgateway_1789264138/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-pushgateway_1789264138/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 55 | Varied in render attempts: 14
Missing values: 8 | Undocumented template fields: 57
Unreferenced values: 47 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 89

Phase robustness: passed | Attempts: 101

Errors: [E023](#e023)

Reproducing values (known-inputs):

```json
{
  "service": {
    "clusterIP": "'"
  }
}
```

### charts/prometheus-rabbitmq-exporter

Result: FAIL | Status: failed
Attempts: 245 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-rabbitmq-exporter_1789264152/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-rabbitmq-exporter_1789264152/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 53 | Varied in render attempts: 38
Missing values: 0 | Undocumented template fields: 53
Unreferenced values: 1 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 144

Phase robustness: passed | Attempts: 101

Errors: [E024](#e024)

Reproducing values (known-inputs):

```json
{
  "priorityClassName": "\u001f"
}
```

### charts/prometheus-redis-exporter

Result: FAIL | Status: failed
Attempts: 196 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-redis-exporter_1789264160/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-redis-exporter_1789264160/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 75 | Varied in render attempts: 22
Missing values: 17 | Undocumented template fields: 76
Unreferenced values: 6 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 95

Phase robustness: passed | Attempts: 101

Errors: [E025](#e025)

Reproducing values (known-inputs):

```json
{
  "service": {
    "annotations": {
      "": []
    }
  }
}
```

### charts/prometheus-smartctl-exporter

Result: FAIL | Status: failed
Attempts: 115 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-smartctl-exporter_1789264178/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-smartctl-exporter_1789264178/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 39 | Varied in render attempts: 5
Missing values: 2 | Undocumented template fields: 41
Unreferenced values: 1 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 14

Phase robustness: passed | Attempts: 101

Errors: [E036](#e036)

Reproducing values (known-inputs):

```json
{
  "extraInstances": [
    null
  ]
}
```

### charts/prometheus-snmp-exporter

Result: FAIL | Status: failed
Attempts: 189 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-snmp-exporter_1789264181/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-snmp-exporter_1789264181/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 78 | Varied in render attempts: 22
Missing values: 8 | Undocumented template fields: 78
Unreferenced values: 4 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 88

Phase robustness: passed | Attempts: 101

Errors: [E026](#e026)

Reproducing values (known-inputs):

```json
{
  "image": {
    "pullPolicy": "\""
  }
}
```

### charts/prometheus-sql-exporter

Result: FAIL | Status: failed
Attempts: 311 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-sql-exporter_1789264189/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-sql-exporter_1789264189/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 53 | Varied in render attempts: 36
Missing values: 11 | Undocumented template fields: 0
Unreferenced values: 2 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 31

Phase robustness: failed | Attempts: 280

Errors: [E027](#e027)

Reproducing values (known-inputs):

```json
{
  "configFilePath": "\u001f"
}
```

Reproducing values (robustness):

```json
{
  "": [],
  "configFilePath": "\u001f"
}
```

### charts/prometheus-stackdriver-exporter

Result: FAIL | Status: failed
Attempts: 140 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-stackdriver-exporter_1789264201/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-stackdriver-exporter_1789264201/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 66 | Varied in render attempts: 2
Missing values: 3 | Undocumented template fields: 66
Unreferenced values: 5 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 39

Phase robustness: passed | Attempts: 101

Errors: [E028](#e028)

Reproducing values (known-inputs):

```json
{
  "restartPolicy": "'"
}
```

### charts/prometheus-statsd-exporter

Result: FAIL | Status: failed
Attempts: 173 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-statsd-exporter_1789264214/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-statsd-exporter_1789264214/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 62 | Varied in render attempts: 41
Missing values: 5 | Undocumented template fields: 66
Unreferenced values: 4 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 72

Phase robustness: passed | Attempts: 101

Errors: [E029](#e029)

Reproducing values (known-inputs):

```json
{
  "image": {
    "pullPolicy": "\u001f"
  }
}
```

### charts/prometheus-systemd-exporter

Result: FAIL | Status: failed
Attempts: 181 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-systemd-exporter_1789264223/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-systemd-exporter_1789264223/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 44 | Varied in render attempts: 11
Missing values: 1 | Undocumented template fields: 44
Unreferenced values: 0 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 80

Phase robustness: passed | Attempts: 101

Errors: [E030](#e030)

Reproducing values (known-inputs):

```json
{
  "config": {
    "log": {
      "level": "\u001f"
    }
  }
}
```

### charts/prometheus-to-sd

Result: FAIL | Status: failed
Attempts: 134 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-to-sd_1789264230/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-to-sd_1789264230/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 10 | Varied in render attempts: 3
Missing values: 0 | Undocumented template fields: 10
Unreferenced values: 0 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 33

Phase robustness: passed | Attempts: 101

Errors: [E031](#e031)

Reproducing values (known-inputs):

```json
{
  "image": {
    "pullPolicy": "\u001f"
  }
}
```

### charts/prometheus-windows-exporter

Result: FAIL | Status: failed
Attempts: 133 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-windows-exporter_1789264239/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-windows-exporter_1789264239/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 94 | Varied in render attempts: 1
Missing values: 3 | Undocumented template fields: 97
Unreferenced values: 0 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 32

Phase robustness: passed | Attempts: 101

Errors: [E032](#e032)

Reproducing values (known-inputs):

```json
{
  "config": "\u001f"
}
```

### charts/prometheus-yet-another-cloudwatch-exporter

Result: FAIL | Status: failed
Attempts: 223 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts:
[prometheus-runs/prometheus-charts_1789260855/runs/prometheus-yet-another-cloudwatch-exporter_1789264241/0000](<prometheus-runs/prometheus-charts_1789260855/runs/prometheus-yet-another-cloudwatch-exporter_1789264241/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Identified input fields (lower bound): 56 | Varied in render attempts: 55
Missing values: 11 | Undocumented template fields: 61
Unreferenced values: 5 (unknown)
Field variation does not prove branch or output coverage.

Phase known-inputs: failed | Attempts: 122

Phase robustness: passed | Attempts: 101

Errors: [E033](#e033)

Reproducing values (known-inputs):

```json
{
  "image": {
    "pullPolicy": "\u001f"
  }
}
```

