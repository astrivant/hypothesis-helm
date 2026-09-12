# Bitnami Helm chart scan

Completed all 115 discovered charts with **--filter**, four workers, and a **five-minute test budget per chart**. No scan-wide deadline was imposed.

Recorded **19,846 test attempts across the 115 primary chart records** in **41.0 minutes** of wall time, including dependency preparation. Attempts include baseline checks and counterexample shrinking; they are not a count of unique inputs or bugs.

The kube-prometheus worker also recursively tested its nested CRD chart. That additional result is retained in supplemental-recursive-results.json; the 115-chart totals use each chart's dedicated job once.

**Findings:** 112 failed; 1 skipped-library; 2 time-limit.

**Known-input phase:** 112 failed; 2 time-limit.
**Deferred robustness phase:** 13 failed; 95 passed; 6 time-limit.

Known fields receive up to 90% of each chart budget; deferred original-contract cases run afterward using the remainder. A phase can finish early after finding and shrinking a counterexample. Dynamic and schema-defined maps remain open; the generation preference does not change the original validation contract or prove deferred inputs irrelevant.

Failure diagnostics across both phases: 13 explicit chart validation rejection; 6 manifest processing; 11 other; inspect diagnostic; 76 rendered YAML; 15 template evaluation; 4 values transport. These categories are based on diagnostic text and are not confirmed root causes.

Failures are observed render/manifest-check failures, including deliberate chart validation rejections and manifest-processing limitations. They need triage before being classified as chart defects. Charts without a values schema use inferred generation, not an authoritative input specification. A passed sample or completed scan does not establish exhaustive coverage.

Checks: dependency build in isolated copies, Helm lint, Helm template with values-schema checks, and built-in manifest checks. External kubeconform/kubesec validation was not configured for this run.

Source: `third_party/bitnami-charts` at `6a8cccf3c29a1faabf0c34c8276a09ed14f3c5b3`. The source checkout is retained.
A post-run serializer correction keeps ordinary Unicode keys literal instead of unnecessarily escaping every character. The original production findings remain unchanged; the four values-transport diagnostics are not evidence of chart-template defects. See transport-triage.json for the isolated reproduction.


[Combined PDF](bitnami.pdf) · [Aggregate data](bitnami-runs/bitnami-charts_1789251211/scan.json) · [Raw logs and provenance](bitnami-runs/bitnami-charts_1789251211/README.md)

Directory: third_party/bitnami-charts
Started (Unix epoch): 1789251228
Elapsed: 2461.80 seconds
Charts discovered: 115
Scan status: completed
Discovery complete: True
Unstarted charts: 0

Results describe the tested sample; they do not prove chart correctness.
Baseline-only, skipped, blocked, and incomplete charts are not property-test passes.

## Status counts

```json
{
  "failed": 112,
  "skipped-library": 1,
  "time-limit": 2
}
```

## Settings

```json
{
  "max_examples": 100,
  "filter": true,
  "permutations": null,
  "chart_timeout_seconds": 300.0,
  "scan_timeout_seconds": null,
  "helm": "Helm 4.3.0",
  "seed": 0,
  "build_dependencies": true,
  "values": "values.yaml",
  "workers": 4,
  "max_examples_per_phase": 100,
  "known_input_budget_fraction": 0.9,
  "external_conformity": false
}
```

## Charts

### bitnami/airflow

Result: FAIL | Status: failed
Attempts: 145 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/airflow_1789251228/0000](<bitnami-runs/bitnami-charts_1789251211/runs/airflow_1789251228/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 44

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: execution error at (airflow/templates/NOTES.txt:129:3): 
VALUES VALIDATION:

airflow: executors
    You need to provide at least one value for the '.executor' parameter.

Use --debug flag to render out invalid YAML
```

### bitnami/apache

Result: FAIL | Status: failed
Attempts: 411 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/apache_1789251228/0000](<bitnami-runs/bitnami-charts_1789251211/runs/apache_1789251228/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 119

Phase robustness: failed | Attempts: 292

```text
known-inputs: invalid rendered manifest: Object of type TaggedScalar is not JSON serializable

robustness: Error: YAML parse error on apache/templates/svc.yaml: error converting YAML to JSON: yaml: line 13: mapping values are not allowed in this context

Use --debug flag to render out invalid YAML
```

### bitnami/apisix

Result: FAIL | Status: failed
Attempts: 83 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/apisix_1789251228/0000](<bitnami-runs/bitnami-charts_1789251211/runs/apisix_1789251228/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 52

Phase robustness: time-limit | Attempts: 31

```text
known-inputs: Error: YAML parse error on apisix/templates/control-plane/api-token-secret.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/appsmith

Result: FAIL | Status: failed
Attempts: 136 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/appsmith_1789251228/0000](<bitnami-runs/bitnami-charts_1789251211/runs/appsmith_1789251228/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 35

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on appsmith/templates/backend/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/argo-cd

Result: FAIL | Status: failed
Attempts: 162 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/argo-cd_1789251295/0000](<bitnami-runs/bitnami-charts_1789251211/runs/argo-cd_1789251295/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 61

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on argo-cd/templates/extra-list.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go value of type util.SimpleHead

Use --debug flag to render out invalid YAML
```

### bitnami/argo-workflows

Result: FAIL | Status: failed
Attempts: 130 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/argo-workflows_1789251302/0000](<bitnami-runs/bitnami-charts_1789251211/runs/argo-workflows_1789251302/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 29

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on argo-workflows/templates/controller/deployment.yaml: error converting YAML to JSON: yaml: line 30: mapping values are not allowed in this context

Use --debug flag to render out invalid YAML
```

### bitnami/aspnet-core

Result: FAIL | Status: failed
Attempts: 186 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/aspnet-core_1789251350/0000](<bitnami-runs/bitnami-charts_1789251211/runs/aspnet-core_1789251350/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 85

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: execution error at (aspnet-core/templates/NOTES.txt:58:4): 
VALUES VALIDATION:
aspnet-core: missing-extra-volume-mounts
    You specified extra volumes but not mount points for them.
    Please also set the extraVolumeMounts parameter.

Use --debug flag to render out invalid YAML
```

### bitnami/cadvisor

Result: FAIL | Status: failed
Attempts: 126 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/cadvisor_1789251373/0000](<bitnami-runs/bitnami-charts_1789251211/runs/cadvisor_1789251373/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 25

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: execution error at (cadvisor/templates/daemonset.yaml:155:25): ERROR: Preset key '' invalid. Allowed values are xlarge,2xlarge,nano,micro,small,medium,large

Use --debug flag to render out invalid YAML
```

### bitnami/cassandra

Result: FAIL | Status: failed
Attempts: 135 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/cassandra_1789251382/0000](<bitnami-runs/bitnami-charts_1789251211/runs/cassandra_1789251382/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 34

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on cassandra/templates/statefulset.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/cert-manager

Result: FAIL | Status: failed
Attempts: 170 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/cert-manager_1789251391/0000](<bitnami-runs/bitnami-charts_1789251211/runs/cert-manager_1789251391/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 69

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on cert-manager/templates/cainjector/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/chainloop

Result: FAIL | Status: failed
Attempts: 165 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/chainloop_1789251406/0000](<bitnami-runs/bitnami-charts_1789251211/runs/chainloop_1789251406/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 64

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: execution error at (chainloop/templates/controlplane/secret-jwt-cas-private-key.yaml:14:22): Authentication Private Key "casJWTPrivateKey" required

Use --debug flag to render out invalid YAML
```

### bitnami/cilium

Result: FAIL | Status: failed
Attempts: 187 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/cilium_1789251449/0000](<bitnami-runs/bitnami-charts_1789251211/runs/cilium_1789251449/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 86

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: template: cilium/templates/agent/daemonset.yaml:30:15: executing "cilium/templates/agent/daemonset.yaml" at <semverCompare "<1.30-0" (include "common.capabilities.kubeVersion" .)>: error calling semverCompare: invalid semantic version

Use --debug flag to render out invalid YAML
```

### bitnami/clickhouse

Result: FAIL | Status: failed
Attempts: 193 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/clickhouse_1789251452/0000](<bitnami-runs/bitnami-charts_1789251211/runs/clickhouse_1789251452/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 92

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on clickhouse/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 178: mapping values are not allowed in this context

Use --debug flag to render out invalid YAML
```

### bitnami/clickhouse-operator

Result: FAIL | Status: failed
Attempts: 157 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/clickhouse-operator_1789251497/0000](<bitnami-runs/bitnami-charts_1789251211/runs/clickhouse-operator_1789251497/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 56

Phase robustness: passed | Attempts: 101

```text
known-inputs: duplicate resource: ('rbac.authorization.k8s.io/v1', 'Role', None, 'hypothesis-clickhouse-operator')
```

### bitnami/cloudnative-pg

Result: FAIL | Status: failed
Attempts: 152 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/cloudnative-pg_1789251513/0000](<bitnami-runs/bitnami-charts_1789251211/runs/cloudnative-pg_1789251513/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 51

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on cloudnative-pg/templates/operator/clusterrolebinding.yaml: error converting YAML to JSON: yaml: line 4: did not find expected comment or line break

Use --debug flag to render out invalid YAML
```

### bitnami/common

Result: N/A | Status: skipped-library
Attempts: N/A | Remaining iterations: unknown
Coverage: not a standalone application
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/common_1789251532/0000](<bitnami-runs/bitnami-charts_1789251211/runs/common_1789251532/0000>)

Filtering applied: False
Chart did not enter finite permutation testing

### bitnami/concourse

Result: FAIL | Status: failed
Attempts: 158 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/concourse_1789251532/0000](<bitnami-runs/bitnami-charts_1789251211/runs/concourse_1789251532/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 57

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: template: concourse/templates/worker/rolebinding.yaml:27:22: executing "concourse/templates/worker/rolebinding.yaml" at <semverCompare "<1.25-0" (include "common.capabilities.kubeVersion" .)>: error calling semverCompare: invalid semantic version

Use --debug flag to render out invalid YAML
```

### bitnami/consul

Result: FAIL | Status: failed
Attempts: 140 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/consul_1789251533/0000](<bitnami-runs/bitnami-charts_1789251211/runs/consul_1789251533/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 39

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on consul/templates/statefulset.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/contour

Result: FAIL | Status: failed
Attempts: 120 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/contour_1789251558/0000](<bitnami-runs/bitnami-charts_1789251211/runs/contour_1789251558/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 19

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on contour/templates/certgen/serviceaccount.yaml: error converting YAML to JSON: yaml: line 15: did not find expected key

Use --debug flag to render out invalid YAML
```

### bitnami/deepspeed

Result: FAIL | Status: failed
Attempts: 101 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/deepspeed_1789251584/0000](<bitnami-runs/bitnami-charts_1789251211/runs/deepspeed_1789251584/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 12

Phase robustness: time-limit | Attempts: 89

```text
known-inputs: Error: YAML parse error on deepspeed/templates/client/client-dep-job.yaml: error converting YAML to JSON: yaml: line 31: did not find expected key

Use --debug flag to render out invalid YAML
```

### bitnami/discourse

Result: FAIL | Status: failed
Attempts: 162 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/discourse_1789251597/0000](<bitnami-runs/bitnami-charts_1789251211/runs/discourse_1789251597/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 61

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on discourse/templates/service.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go struct field .metadata.annotations. of type string

Use --debug flag to render out invalid YAML
```

### bitnami/dremio

Result: FAIL | Status: failed
Attempts: 133 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/dremio_1789251625/0000](<bitnami-runs/bitnami-charts_1789251211/runs/dremio_1789251625/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 32

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on dremio/templates/extra-list.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go value of type util.SimpleHead

Use --debug flag to render out invalid YAML
```

### bitnami/drupal

Result: FAIL | Status: failed
Attempts: 252 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/drupal_1789251652/0000](<bitnami-runs/bitnami-charts_1789251211/runs/drupal_1789251652/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 29

Phase robustness: failed | Attempts: 223

```text
known-inputs: Error: execution error at (drupal/charts/mariadb/templates/NOTES.txt:74:4): 
VALUES VALIDATION:
mariadb: architecture
    Invalid architecture selected. Valid values are "standalone" and
    "replication". Please set a valid architecture (--set architecture="xxxx")

Use --debug flag to render out invalid YAML

robustness: Error: YAML parse error on drupal/templates/svc.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/ejbca

Result: FAIL | Status: failed
Attempts: 147 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/ejbca_1789251723/0000](<bitnami-runs/bitnami-charts_1789251211/runs/ejbca_1789251723/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 46

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on ejbca/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/elasticsearch

Result: FAIL | Status: failed
Attempts: 180 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/elasticsearch_1789251725/0000](<bitnami-runs/bitnami-charts_1789251211/runs/elasticsearch_1789251725/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 79

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on elasticsearch/templates/coordinating/statefulset.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/envoy-gateway

Result: FAIL | Status: failed
Attempts: 157 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/envoy-gateway_1789251751/0000](<bitnami-runs/bitnami-charts_1789251211/runs/envoy-gateway_1789251751/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 56

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on envoy-gateway/templates/deployment.yaml: error converting YAML to JSON: yaml: line 37: did not find expected key

Use --debug flag to render out invalid YAML
```

### bitnami/etcd

Result: N/A | Status: time-limit
Attempts: 105 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/etcd_1789251756/0000](<bitnami-runs/bitnami-charts_1789251211/runs/etcd_1789251756/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: time-limit | Attempts: 95

Phase robustness: time-limit | Attempts: 10

### bitnami/external-dns

Result: FAIL | Status: failed
Attempts: 148 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/external-dns_1789251819/0000](<bitnami-runs/bitnami-charts_1789251211/runs/external-dns_1789251819/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 47

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on external-dns/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/flink

Result: FAIL | Status: failed
Attempts: 120 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/flink_1789251853/0000](<bitnami-runs/bitnami-charts_1789251211/runs/flink_1789251853/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 19

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on flink/templates/jobmanager/deployment.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go struct field .metadata.annotations. of type string

Use --debug flag to render out invalid YAML
```

### bitnami/fluent-bit

Result: FAIL | Status: failed
Attempts: 245 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/fluent-bit_1789251880/0000](<bitnami-runs/bitnami-charts_1789251211/runs/fluent-bit_1789251880/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 144

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: execution error at (fluent-bit/templates/NOTES.txt:30:4): 

⚠ ERROR: Original containers have been substituted for unrecognized ones. Deploying this chart with non-standard containers is likely to cause degraded security and performance, broken chart features, and missing environment variables.

Unrecognized images:
  - 00/bitnami/fluent-bit:4.0.8-debian-12-r0

If you are sure you want to proceed with non-standard containers, you can skip container image verification by setting the global parameter 'global.security.allowInsecureImages' to true.
Further information can be obtained at https://github.com/bitnami/charts/issues/30850

Use --debug flag to render out invalid YAML
```

### bitnami/fluentd

Result: FAIL | Status: failed
Attempts: 129 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/fluentd_1789251891/0000](<bitnami-runs/bitnami-charts_1789251211/runs/fluentd_1789251891/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 28

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on fluentd/templates/extra-list.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go value of type util.SimpleHead

Use --debug flag to render out invalid YAML
```

### bitnami/flux

Result: FAIL | Status: failed
Attempts: 119 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/flux_1789251919/0000](<bitnami-runs/bitnami-charts_1789251211/runs/flux_1789251919/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 18

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on flux/templates/extra-list.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go value of type util.SimpleHead

Use --debug flag to render out invalid YAML
```

### bitnami/ghost

Result: FAIL | Status: failed
Attempts: 396 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/ghost_1789251929/0000](<bitnami-runs/bitnami-charts_1789251211/runs/ghost_1789251929/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 154

Phase robustness: failed | Attempts: 242

```text
known-inputs: Error: YAML parse error on ghost/templates/svc.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go struct field .metadata.annotations. of type string

Use --debug flag to render out invalid YAML

robustness: Error: failed to parse /var/folders/dd/pd400p1j4vgf5gv6qp6zfx000000gn/T/hypothesis-helm-if0kaa5a/values.json: cannot unmarshal yaml document: error converting YAML to JSON: yaml: did not find expected ',' or '}'
```

### bitnami/gitea

Result: FAIL | Status: failed
Attempts: 147 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/gitea_1789251952/0000](<bitnami-runs/bitnami-charts_1789251211/runs/gitea_1789251952/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 46

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on gitea/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/gitlab-runner

Result: FAIL | Status: failed
Attempts: 213 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/gitlab-runner_1789251987/0000](<bitnami-runs/bitnami-charts_1789251211/runs/gitlab-runner_1789251987/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 112

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on gitlab-runner/templates/cluster-role.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/grafana

Result: FAIL | Status: failed
Attempts: 197 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/grafana_1789252005/0000](<bitnami-runs/bitnami-charts_1789251211/runs/grafana_1789252005/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 96

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: grafana/templates/application.yaml:225:72
  executing "grafana/templates/application.yaml" at <.configMapName>:
    nil pointer evaluating interface {}.configMapName

Use --debug flag to render out invalid YAML
```

### bitnami/grafana-alloy

Result: FAIL | Status: failed
Attempts: 239 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/grafana-alloy_1789252023/0000](<bitnami-runs/bitnami-charts_1789251211/runs/grafana-alloy_1789252023/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 138

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on grafana-alloy/templates/application.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/grafana-k6-operator

Result: FAIL | Status: failed
Attempts: 187 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/grafana-k6-operator_1789252042/0000](<bitnami-runs/bitnami-charts_1789251211/runs/grafana-k6-operator_1789252042/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 86

Phase robustness: passed | Attempts: 101

```text
known-inputs: invalid rendered manifest: Object of type TaggedScalar is not JSON serializable
```

### bitnami/grafana-loki

Result: FAIL | Status: failed
Attempts: 149 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/grafana-loki_1789252062/0000](<bitnami-runs/bitnami-charts_1789251211/runs/grafana-loki_1789252062/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 48

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on grafana-loki/templates/gateway/configmap-http.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/grafana-mimir

Result: FAIL | Status: failed
Attempts: 125 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/grafana-mimir_1789252066/0000](<bitnami-runs/bitnami-charts_1789251211/runs/grafana-mimir_1789252066/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 24

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: execution error at (grafana-mimir/charts/memcachedchunks/templates/NOTES.txt:46:4): 
VALUES VALIDATION:
memcached: architecture
    Invalid architecture selected. Valid values are "standalone" and
    "high-availability". Please set a valid architecture (--set architecture="xxxx")

Use --debug flag to render out invalid YAML
```

### bitnami/grafana-operator

Result: FAIL | Status: failed
Attempts: 162 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/grafana-operator_1789252073/0000](<bitnami-runs/bitnami-charts_1789251211/runs/grafana-operator_1789252073/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 61

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on grafana-operator/templates/extra-list.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go value of type util.SimpleHead

Use --debug flag to render out invalid YAML
```

### bitnami/grafana-tempo

Result: FAIL | Status: failed
Attempts: 138 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/grafana-tempo_1789252105/0000](<bitnami-runs/bitnami-charts_1789251211/runs/grafana-tempo_1789252105/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 37

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on grafana-tempo/templates/tempo-configmap.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/haproxy

Result: FAIL | Status: failed
Attempts: 193 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/haproxy_1789252206/0000](<bitnami-runs/bitnami-charts_1789251211/runs/haproxy_1789252206/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 92

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on haproxy/templates/extra-list.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go value of type util.SimpleHead

Use --debug flag to render out invalid YAML
```

### bitnami/harbor

Result: FAIL | Status: failed
Attempts: 137 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/harbor_1789252208/0000](<bitnami-runs/bitnami-charts_1789251211/runs/harbor_1789252208/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 36

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on harbor/templates/core/core-dpl.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/influxdb

Result: FAIL | Status: failed
Attempts: 344 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/influxdb_1789252221/0000](<bitnami-runs/bitnami-charts_1789251211/runs/influxdb_1789252221/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 243

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on influxdb/templates/pdb.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/jaeger

Result: FAIL | Status: failed
Attempts: 207 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/jaeger_1789252233/0000](<bitnami-runs/bitnami-charts_1789251211/runs/jaeger_1789252233/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 106

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: execution error at (jaeger/templates/collector/deployment.yaml:199:25): ERROR: Preset key '' invalid. Allowed values are xlarge,2xlarge,nano,micro,small,medium,large

Use --debug flag to render out invalid YAML
```

### bitnami/janusgraph

Result: FAIL | Status: failed
Attempts: 139 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/janusgraph_1789252257/0000](<bitnami-runs/bitnami-charts_1789251211/runs/janusgraph_1789252257/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 38

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on janusgraph/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/jenkins

Result: FAIL | Status: failed
Attempts: 405 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/jenkins_1789252283/0000](<bitnami-runs/bitnami-charts_1789251211/runs/jenkins_1789252283/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 136

Phase robustness: failed | Attempts: 269

```text
known-inputs: Error: execution error at (jenkins/templates/NOTES.txt:54:4): 

⚠ ERROR: Original containers have been substituted for unrecognized ones. Deploying this chart with non-standard containers is likely to cause degraded security and performance, broken chart features, and missing environment variables.

Unrecognized images:
  - 00/bitnami/jenkins:2.516.2-debian-12-r0
  - 00/bitnami/jenkins-agent:0.3327.0-debian-12-r1
  - 00/bitnami/os-shell:12-debian-12-r51

If you are sure you want to proceed with non-standard containers, you can skip container image verification by setting the global parameter 'global.security.allowInsecureImages' to true.
Further information can be obtained at https://github.com/bitnami/charts/issues/30850

Use --debug flag to render out invalid YAML

robustness: Error: failed to parse /var/folders/dd/pd400p1j4vgf5gv6qp6zfx000000gn/T/hypothesis-helm-aswf0y7m/values.json: cannot unmarshal yaml document: error converting YAML to JSON: yaml: did not find expected ',' or '}'
```

### bitnami/jupyterhub

Result: FAIL | Status: failed
Attempts: 126 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/jupyterhub_1789252291/0000](<bitnami-runs/bitnami-charts_1789251211/runs/jupyterhub_1789252291/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 25

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: execution error at (jupyterhub/templates/proxy/deployment.yaml:32:32): ERROR: Preset key '' invalid. Allowed values are small,medium,large,xlarge,2xlarge,nano,micro

Use --debug flag to render out invalid YAML
```

### bitnami/kafka

Result: FAIL | Status: failed
Attempts: 141 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/kafka_1789252297/0000](<bitnami-runs/bitnami-charts_1789251211/runs/kafka_1789252297/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 40

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on kafka/templates/controller-eligible/statefulset.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/keycloak

Result: FAIL | Status: failed
Attempts: 240 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/keycloak_1789252350/0000](<bitnami-runs/bitnami-charts_1789251211/runs/keycloak_1789252350/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 139

Phase robustness: passed | Attempts: 101

```text
known-inputs: resource has no metadata.name
```

### bitnami/keydb

Result: FAIL | Status: failed
Attempts: 127 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/keydb_1789252362/0000](<bitnami-runs/bitnami-charts_1789251211/runs/keydb_1789252362/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 26

Phase robustness: passed | Attempts: 101

```text
known-inputs: resource has no metadata.name
```

### bitnami/kibana

Result: FAIL | Status: failed
Attempts: 317 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/kibana_1789252366/0000](<bitnami-runs/bitnami-charts_1789251211/runs/kibana_1789252366/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 216

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: kibana/templates/ingress.yaml:33:64
  executing "kibana/templates/ingress.yaml" at <.name>:
    nil pointer evaluating interface {}.name

Use --debug flag to render out invalid YAML
```

### bitnami/kong

Result: FAIL | Status: failed
Attempts: 142 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/kong_1789252404/0000](<bitnami-runs/bitnami-charts_1789251211/runs/kong_1789252404/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 41

Phase robustness: passed | Attempts: 101

```text
known-inputs: invalid rendered manifest: Object of type TaggedScalar is not JSON serializable
```

### bitnami/kube-arangodb

Result: FAIL | Status: failed
Attempts: 163 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/kube-arangodb_1789252412/0000](<bitnami-runs/bitnami-charts_1789251211/runs/kube-arangodb_1789252412/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 62

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on kube-arangodb/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/kube-prometheus

Result: FAIL | Status: failed
Attempts: 119 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/kube-prometheus_1789252419/0000](<bitnami-runs/bitnami-charts_1789251211/runs/kube-prometheus_1789252419/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 18

Phase robustness: passed | Attempts: 101

```text
known-inputs: level=INFO msg="warning: destination for kube-state-metrics.rbac.rules is a table. Ignoring non-table value ([])"
Error: YAML parse error on kube-prometheus/templates/extra-list.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go value of type util.SimpleHead

Use --debug flag to render out invalid YAML
```

### bitnami/kube-prometheus/charts/kube-prometheus-crds

Result: FAIL | Status: failed
Attempts: 2 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/kube-prometheus-crds_1789252451/0000](<bitnami-runs/bitnami-charts_1789251211/runs/kube-prometheus-crds_1789252451/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 1

Phase robustness: failed | Attempts: 1

```text
known-inputs: chart rendered no resources (use allow_empty explicitly)

robustness: chart rendered no resources (use allow_empty explicitly)
```

### bitnami/kube-state-metrics

Result: FAIL | Status: failed
Attempts: 118 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/kube-state-metrics_1789252452/0000](<bitnami-runs/bitnami-charts_1789251211/runs/kube-state-metrics_1789252452/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 17

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: execution error at (kube-state-metrics/templates/deployment.yaml:205:25): ERROR: Preset key '' invalid. Allowed values are large,xlarge,2xlarge,nano,micro,small,medium

Use --debug flag to render out invalid YAML
```

### bitnami/kuberay

Result: FAIL | Status: failed
Attempts: 132 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/kuberay_1789252452/0000](<bitnami-runs/bitnami-charts_1789251211/runs/kuberay_1789252452/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 31

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on kuberay/templates/apiserver/clusterrolebinding.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go struct field .metadata.annotations. of type string

Use --debug flag to render out invalid YAML
```

### bitnami/kubernetes-event-exporter

Result: FAIL | Status: failed
Attempts: 331 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/kubernetes-event-exporter_1789252461/0000](<bitnami-runs/bitnami-charts_1789251211/runs/kubernetes-event-exporter_1789252461/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 230

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on kubernetes-event-exporter/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/logstash

Result: FAIL | Status: failed
Attempts: 141 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/logstash_1789252473/0000](<bitnami-runs/bitnami-charts_1789251211/runs/logstash_1789252473/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 40

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on logstash/templates/sts.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/mariadb

Result: FAIL | Status: failed
Attempts: 127 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/mariadb_1789252495/0000](<bitnami-runs/bitnami-charts_1789251211/runs/mariadb_1789252495/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 5

Phase robustness: failed | Attempts: 122

```text
known-inputs: Error: execution error at (mariadb/templates/NOTES.txt:74:4): 
VALUES VALIDATION:
mariadb: architecture
    Invalid architecture selected. Valid values are "standalone" and
    "replication". Please set a valid architecture (--set architecture="xxxx")

Use --debug flag to render out invalid YAML

robustness: Error: execution error at (mariadb/templates/NOTES.txt:74:4): 
VALUES VALIDATION:
mariadb: architecture
    Invalid architecture selected. Valid values are "standalone" and
    "replication". Please set a valid architecture (--set architecture="xxxx")

Use --debug flag to render out invalid YAML
```

### bitnami/mariadb-galera

Result: FAIL | Status: failed
Attempts: 90 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/mariadb-galera_1789252506/0000](<bitnami-runs/bitnami-charts_1789251211/runs/mariadb-galera_1789252506/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 68

Phase robustness: time-limit | Attempts: 22

```text
known-inputs: Error: YAML parse error on mariadb-galera/templates/extra-list.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go value of type util.SimpleHead

Use --debug flag to render out invalid YAML
```

### bitnami/mastodon

Result: FAIL | Status: failed
Attempts: 200 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/mastodon_1789252506/0000](<bitnami-runs/bitnami-charts_1789251211/runs/mastodon_1789252506/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 99

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on mastodon/templates/extra-list.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go value of type util.SimpleHead

Use --debug flag to render out invalid YAML
```

### bitnami/matomo

Result: FAIL | Status: failed
Attempts: 134 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/matomo_1789252549/0000](<bitnami-runs/bitnami-charts_1789251211/runs/matomo_1789252549/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 33

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on matomo/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/memcached

Result: FAIL | Status: failed
Attempts: 161 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/memcached_1789252601/0000](<bitnami-runs/bitnami-charts_1789251211/runs/memcached_1789252601/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 60

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: execution error at (memcached/templates/NOTES.txt:46:4): 
VALUES VALIDATION:
memcached: architecture
    Invalid architecture selected. Valid values are "standalone" and
    "high-availability". Please set a valid architecture (--set architecture="xxxx")

Use --debug flag to render out invalid YAML
```

### bitnami/metallb

Result: FAIL | Status: failed
Attempts: 225 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/metallb_1789252639/0000](<bitnami-runs/bitnami-charts_1789251211/runs/metallb_1789252639/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 124

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: template: metallb/templates/speaker/rbac.yaml:44:14: executing "metallb/templates/speaker/rbac.yaml" at <include "common.capabilities.psp.supported" .>: error calling include: template: metallb/charts/common/templates/_capabilities.tpl:131:32: executing "common.capabilities.psp.supported" at <semverCompare "<1.25-0" $kubeVersion>: error calling semverCompare: invalid semantic version

Use --debug flag to render out invalid YAML
```

### bitnami/metrics-server

Result: FAIL | Status: failed
Attempts: 248 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/metrics-server_1789252645/0000](<bitnami-runs/bitnami-charts_1789251211/runs/metrics-server_1789252645/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 147

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on metrics-server/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/milvus

Result: N/A | Status: time-limit
Attempts: 30 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/milvus_1789252691/0000](<bitnami-runs/bitnami-charts_1789251211/runs/milvus_1789252691/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: time-limit | Attempts: 23

Phase robustness: time-limit | Attempts: 7

### bitnami/mlflow

Result: FAIL | Status: failed
Attempts: 193 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/mlflow_1789252697/0000](<bitnami-runs/bitnami-charts_1789251211/runs/mlflow_1789252697/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 66

Phase robustness: failed | Attempts: 127

```text
known-inputs: Error: YAML parse error on mlflow/templates/run/dep-job.yaml: error converting YAML to JSON: yaml: line 29: did not find expected key

Use --debug flag to render out invalid YAML

robustness: Error: YAML parse error on mlflow/templates/run/dep-job.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/mongodb

Result: FAIL | Status: failed
Attempts: 87 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/mongodb_1789252761/0000](<bitnami-runs/bitnami-charts_1789251211/runs/mongodb_1789252761/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 43

Phase robustness: time-limit | Attempts: 44

```text
known-inputs: Error: YAML parse error on mongodb/templates/configmap.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/mongodb-sharded

Result: FAIL | Status: failed
Attempts: 145 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/mongodb-sharded_1789252809/0000](<bitnami-runs/bitnami-charts_1789251211/runs/mongodb-sharded_1789252809/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 44

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on mongodb-sharded/templates/config-server/config-server-statefulset.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/moodle

Result: FAIL | Status: failed
Attempts: 184 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/moodle_1789252874/0000](<bitnami-runs/bitnami-charts_1789251211/runs/moodle_1789252874/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 83

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on moodle/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/multus-cni

Result: FAIL | Status: failed
Attempts: 135 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/multus-cni_1789252902/0000](<bitnami-runs/bitnami-charts_1789251211/runs/multus-cni_1789252902/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 34

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on multus-cni/templates/daemonset.yaml: error converting YAML to JSON: yaml: line 73: did not find expected comment or line break

Use --debug flag to render out invalid YAML
```

### bitnami/mysql

Result: FAIL | Status: failed
Attempts: 234 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/mysql_1789252935/0000](<bitnami-runs/bitnami-charts_1789251211/runs/mysql_1789252935/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 133

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on mysql/templates/extra-list.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go value of type util.SimpleHead

Use --debug flag to render out invalid YAML
```

### bitnami/nats

Result: FAIL | Status: failed
Attempts: 152 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/nats_1789252944/0000](<bitnami-runs/bitnami-charts_1789251211/runs/nats_1789252944/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 51

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: execution error at (nats/templates/NOTES.txt:176:4): 
VALUES VALIDATION:
nats: resourceType
    Invalid resourceType selected. Valid values are "deployment" and
    "statefulset". Please set a valid mode (--set resourceType="xxxx")

Use --debug flag to render out invalid YAML
```

### bitnami/neo4j

Result: FAIL | Status: failed
Attempts: 188 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/neo4j_1789252975/0000](<bitnami-runs/bitnami-charts_1789251211/runs/neo4j_1789252975/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 87

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: neo4j/templates/networkpolicy.yaml:47:19
  executing "neo4j/templates/networkpolicy.yaml" at <.containerPort>:
    nil pointer evaluating interface {}.containerPort

Use --debug flag to render out invalid YAML
```

### bitnami/nessie

Result: FAIL | Status: failed
Attempts: 252 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/nessie_1789252998/0000](<bitnami-runs/bitnami-charts_1789251211/runs/nessie_1789252998/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 151

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on nessie/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/nginx

Result: FAIL | Status: failed
Attempts: 325 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/nginx_1789253009/0000](<bitnami-runs/bitnami-charts_1789251211/runs/nginx_1789253009/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 81

Phase robustness: failed | Attempts: 244

```text
known-inputs: Error: YAML parse error on nginx/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML

robustness: Error: YAML parse error on nginx/templates/context-includes-configmap.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/node-exporter

Result: FAIL | Status: failed
Attempts: 190 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/node-exporter_1789253016/0000](<bitnami-runs/bitnami-charts_1789251211/runs/node-exporter_1789253016/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 89

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on node-exporter/templates/daemonset.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/oauth2-proxy

Result: FAIL | Status: failed
Attempts: 130 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/oauth2-proxy_1789253043/0000](<bitnami-runs/bitnami-charts_1789251211/runs/oauth2-proxy_1789253043/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 29

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: execution error at (oauth2-proxy/charts/redis/templates/NOTES.txt:202:4): 
VALUES VALIDATION:
redis: architecture
    Invalid architecture selected. Valid values are "standalone" and
    "replication". Please set a valid architecture (--set architecture="xxxx")

Use --debug flag to render out invalid YAML
```

### bitnami/odoo

Result: FAIL | Status: failed
Attempts: 128 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/odoo_1789253062/0000](<bitnami-runs/bitnami-charts_1789251211/runs/odoo_1789253062/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 27

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: execution error at (odoo/templates/deployment.yaml:270:25): ERROR: Preset key '' invalid. Allowed values are large,xlarge,2xlarge,nano,micro,small,medium

Use --debug flag to render out invalid YAML
```

### bitnami/opensearch

Result: FAIL | Status: failed
Attempts: 183 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/opensearch_1789253064/0000](<bitnami-runs/bitnami-charts_1789251211/runs/opensearch_1789253064/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 82

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: execution error at (opensearch/templates/ingest/statefulset.yaml:90:12): ERROR: Preset key '' invalid. Allowed values are small,medium,large,xlarge,2xlarge,nano,micro

Use --debug flag to render out invalid YAML
```

### bitnami/parse

Result: FAIL | Status: failed
Attempts: 120 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/parse_1789253081/0000](<bitnami-runs/bitnami-charts_1789251211/runs/parse_1789253081/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 19

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on parse/templates/extra-list.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go value of type util.SimpleHead

Use --debug flag to render out invalid YAML
```

### bitnami/phpmyadmin

Result: FAIL | Status: failed
Attempts: 301 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/phpmyadmin_1789253091/0000](<bitnami-runs/bitnami-charts_1789251211/runs/phpmyadmin_1789253091/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 200

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on phpmyadmin/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/pinniped

Result: FAIL | Status: failed
Attempts: 160 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/pinniped_1789253122/0000](<bitnami-runs/bitnami-charts_1789251211/runs/pinniped_1789253122/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 59

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on pinniped/templates/concierge/apiservice-identity.yaml: error converting YAML to JSON: yaml: line 23: found unexpected end of stream

Use --debug flag to render out invalid YAML
```

### bitnami/postgresql

Result: FAIL | Status: failed
Attempts: 116 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/postgresql_1789253136/0000](<bitnami-runs/bitnami-charts_1789251211/runs/postgresql_1789253136/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 15

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: execution error at (postgresql/templates/NOTES.txt:118:4): 
VALUES VALIDATION:
postgresql: psp.create, rbac.create
    RBAC should be enabled if PSP is enabled in order for PSP to work.
    More info at https://kubernetes.io/docs/concepts/policy/pod-security-policy/#authorizing-policies

Use --debug flag to render out invalid YAML
```

### bitnami/postgresql-ha

Result: FAIL | Status: failed
Attempts: 156 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/postgresql-ha_1789253152/0000](<bitnami-runs/bitnami-charts_1789251211/runs/postgresql-ha_1789253152/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 55

Phase robustness: passed | Attempts: 101

```text
known-inputs: resource has no metadata.name
```

### bitnami/prometheus

Result: FAIL | Status: failed
Attempts: 318 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/prometheus_1789253175/0000](<bitnami-runs/bitnami-charts_1789251211/runs/prometheus_1789253175/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 75

Phase robustness: failed | Attempts: 243

```text
known-inputs: Error: YAML parse error on prometheus/templates/alertmanager/networkpolicy.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML

robustness: Error: YAML parse error on prometheus/templates/extra-list.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go value of type util.SimpleHead

Use --debug flag to render out invalid YAML
```

### bitnami/pytorch

Result: FAIL | Status: failed
Attempts: 143 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/pytorch_1789253187/0000](<bitnami-runs/bitnami-charts_1789251211/runs/pytorch_1789253187/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 42

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: execution error at (pytorch/templates/NOTES.txt:69:3): 
VALUES VALIDATION:
pytorch: architecture
    Invalid architecture selected. Valid values are "distributed" and
    "standalone". Please set a valid architecture (--set architecture="xxxx")

Use --debug flag to render out invalid YAML
```

### bitnami/rabbitmq

Result: FAIL | Status: failed
Attempts: 539 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/rabbitmq_1789253191/0000](<bitnami-runs/bitnami-charts_1789251211/runs/rabbitmq_1789253191/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 274

Phase robustness: failed | Attempts: 265

```text
known-inputs: Error: failed to parse /var/folders/dd/pd400p1j4vgf5gv6qp6zfx000000gn/T/hypothesis-helm-rtvpkvk8/values.json: cannot unmarshal yaml document: error converting YAML to JSON: yaml: did not find expected ',' or '}'

robustness: Error: YAML parse error on rabbitmq/templates/statefulset.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/rabbitmq-cluster-operator

Result: FAIL | Status: failed
Attempts: 173 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/rabbitmq-cluster-operator_1789253208/0000](<bitnami-runs/bitnami-charts_1789251211/runs/rabbitmq-cluster-operator_1789253208/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 72

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: template: rabbitmq-cluster-operator/templates/messaging-topology-operator/validating-webhook-configuration.yaml:14:13: executing "rabbitmq-cluster-operator/templates/messaging-topology-operator/validating-webhook-configuration.yaml" at <genSignedCert (include "rmqco.msgTopologyOperator.fullname" .) nil (list (printf "%s.%s.svc" (include "rmqco.msgTopologyOperator.webhook.fullname" .) (include "common.names.namespace" .)) (printf "%s.%s.svc.%s" (include "rmqco.msgTopologyOperator.webhook.fullname" .) (include "common.names.namespace" .) .Values.clusterDomain)) 365 $ca>: error calling genSignedCert: error creating certificate: x509: "hypothesis-rabbitmq-messaging-topology-operator-webhook.default.svc.\u0080" cannot be encoded as an IA5String

Use --debug flag to render out invalid YAML
```

### bitnami/redis

Result: FAIL | Status: failed
Attempts: 145 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/redis_1789253220/0000](<bitnami-runs/bitnami-charts_1789251211/runs/redis_1789253220/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 5

Phase robustness: failed | Attempts: 140

```text
known-inputs: Error: execution error at (redis/templates/NOTES.txt:202:4): 
VALUES VALIDATION:
redis: architecture
    Invalid architecture selected. Valid values are "standalone" and
    "replication". Please set a valid architecture (--set architecture="xxxx")

Use --debug flag to render out invalid YAML

robustness: Error: execution error at (redis/templates/NOTES.txt:202:4): 
VALUES VALIDATION:
redis: architecture
    Invalid architecture selected. Valid values are "standalone" and
    "replication". Please set a valid architecture (--set architecture="xxxx")

Use --debug flag to render out invalid YAML
```

### bitnami/redis-cluster

Result: FAIL | Status: failed
Attempts: 150 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/redis-cluster_1789253276/0000](<bitnami-runs/bitnami-charts_1789251211/runs/redis-cluster_1789253276/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 49

Phase robustness: passed | Attempts: 101

```text
known-inputs: invalid rendered manifest: Object of type TaggedScalar is not JSON serializable
```

### bitnami/redmine

Result: FAIL | Status: failed
Attempts: 304 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/redmine_1789253293/0000](<bitnami-runs/bitnami-charts_1789251211/runs/redmine_1789253293/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 62

Phase robustness: failed | Attempts: 242

```text
known-inputs: Error: YAML parse error on redmine/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML

robustness: Error: failed to parse /var/folders/dd/pd400p1j4vgf5gv6qp6zfx000000gn/T/hypothesis-helm-i22elfg5/values.json: cannot unmarshal yaml document: error converting YAML to JSON: yaml: did not find expected ',' or '}'
```

### bitnami/schema-registry

Result: FAIL | Status: failed
Attempts: 172 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/schema-registry_1789253309/0000](<bitnami-runs/bitnami-charts_1789251211/runs/schema-registry_1789253309/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 71

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: schema-registry/templates/http-route.yaml:7:13
  executing "schema-registry/templates/http-route.yaml" at <$route.enabled>:
    nil pointer evaluating interface {}.enabled

Use --debug flag to render out invalid YAML
```

### bitnami/scylladb

Result: FAIL | Status: failed
Attempts: 247 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/scylladb_1789253311/0000](<bitnami-runs/bitnami-charts_1789251211/runs/scylladb_1789253311/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 146

Phase robustness: passed | Attempts: 101

```text
known-inputs: invalid rendered manifest: Object of type TaggedScalar is not JSON serializable
```

### bitnami/sealed-secrets

Result: FAIL | Status: failed
Attempts: 164 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/sealed-secrets_1789253315/0000](<bitnami-runs/bitnami-charts_1789251211/runs/sealed-secrets_1789253315/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 63

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: execution error at (sealed-secrets/templates/deployment.yaml:172:25): ERROR: Preset key '' invalid. Allowed values are small,medium,large,xlarge,2xlarge,nano,micro

Use --debug flag to render out invalid YAML
```

### bitnami/seaweedfs

Result: FAIL | Status: failed
Attempts: 135 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/seaweedfs_1789253341/0000](<bitnami-runs/bitnami-charts_1789251211/runs/seaweedfs_1789253341/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 34

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on seaweedfs/templates/filer/statefulset.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/solr

Result: FAIL | Status: failed
Attempts: 166 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/solr_1789253352/0000](<bitnami-runs/bitnami-charts_1789251211/runs/solr_1789253352/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 65

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on solr/templates/statefulset.yaml: error converting YAML to JSON: yaml: line 180: did not find expected key

Use --debug flag to render out invalid YAML
```

### bitnami/sonarqube

Result: FAIL | Status: failed
Attempts: 128 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/sonarqube_1789253377/0000](<bitnami-runs/bitnami-charts_1789251211/runs/sonarqube_1789253377/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 27

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on sonarqube/templates/extra-list.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go value of type util.SimpleHead

Use --debug flag to render out invalid YAML
```

### bitnami/spark

Result: FAIL | Status: failed
Attempts: 220 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/spark_1789253392/0000](<bitnami-runs/bitnami-charts_1789251211/runs/spark_1789253392/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 119

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on spark/templates/extra-list.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go value of type util.SimpleHead

Use --debug flag to render out invalid YAML
```

### bitnami/superset

Result: FAIL | Status: failed
Attempts: 137 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/superset_1789253412/0000](<bitnami-runs/bitnami-charts_1789251211/runs/superset_1789253412/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 36

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on superset/templates/extra-list.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go value of type util.SimpleHead

Use --debug flag to render out invalid YAML
```

### bitnami/tensorflow-resnet

Result: FAIL | Status: failed
Attempts: 179 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/tensorflow-resnet_1789253441/0000](<bitnami-runs/bitnami-charts_1789251211/runs/tensorflow-resnet_1789253441/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 78

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on tensorflow-resnet/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/thanos

Result: FAIL | Status: failed
Attempts: 132 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/thanos_1789253463/0000](<bitnami-runs/bitnami-charts_1789251211/runs/thanos_1789253463/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 31

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on thanos/templates/storegateway/configmap.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/tomcat

Result: FAIL | Status: failed
Attempts: 144 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/tomcat_1789253463/0000](<bitnami-runs/bitnami-charts_1789251211/runs/tomcat_1789253463/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 43

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on tomcat/templates/deployment.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/valkey

Result: FAIL | Status: failed
Attempts: 140 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/valkey_1789253482/0000](<bitnami-runs/bitnami-charts_1789251211/runs/valkey_1789253482/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 39

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on valkey/templates/replicas/application.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/valkey-cluster

Result: FAIL | Status: failed
Attempts: 134 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/valkey-cluster_1789253483/0000](<bitnami-runs/bitnami-charts_1789251211/runs/valkey-cluster_1789253483/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 33

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on valkey-cluster/templates/extra-list.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go value of type util.SimpleHead

Use --debug flag to render out invalid YAML
```

### bitnami/vault

Result: FAIL | Status: failed
Attempts: 167 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/vault_1789253486/0000](<bitnami-runs/bitnami-charts_1789251211/runs/vault_1789253486/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 66

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on vault/templates/extra-list.yaml: error unmarshaling JSON: while decoding JSON: json: cannot unmarshal array into Go value of type util.SimpleHead

Use --debug flag to render out invalid YAML
```

### bitnami/victoriametrics

Result: FAIL | Status: failed
Attempts: 171 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/victoriametrics_1789253519/0000](<bitnami-runs/bitnami-charts_1789251211/runs/victoriametrics_1789253519/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 70

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on victoriametrics/templates/vmagent/dep-ds.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/whereabouts

Result: FAIL | Status: failed
Attempts: 120 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/whereabouts_1789253539/0000](<bitnami-runs/bitnami-charts_1789251211/runs/whereabouts_1789253539/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 19

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: execution error at (whereabouts/templates/daemonset.yaml:164:25): ERROR: Preset key '' invalid. Allowed values are small,medium,large,xlarge,2xlarge,nano,micro

Use --debug flag to render out invalid YAML
```

### bitnami/wildfly

Result: FAIL | Status: failed
Attempts: 145 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/wildfly_1789253553/0000](<bitnami-runs/bitnami-charts_1789251211/runs/wildfly_1789253553/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 44

Phase robustness: passed | Attempts: 101

```text
known-inputs: resource has no metadata.name
```

### bitnami/wordpress

Result: FAIL | Status: failed
Attempts: 213 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/wordpress_1789253554/0000](<bitnami-runs/bitnami-charts_1789251211/runs/wordpress_1789253554/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 112

Phase robustness: passed | Attempts: 101

```text
known-inputs: Error: YAML parse error on wordpress/templates/httpd-configmap.yaml: error converting YAML to JSON: yaml: control characters are not allowed

Use --debug flag to render out invalid YAML
```

### bitnami/zipkin

Result: FAIL | Status: failed
Attempts: 2 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/zipkin_1789253576/0000](<bitnami-runs/bitnami-charts_1789251211/runs/zipkin_1789253576/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 1

Phase robustness: failed | Attempts: 1

```text
known-inputs: invalid rendered YAML: more indented follow up line than first in a block scalar
  in "<unicode string>", line 474, column 15:
                  set -o errexit
                  ^ (line: 474)

robustness: invalid rendered YAML: more indented follow up line than first in a block scalar
  in "<unicode string>", line 474, column 15:
                  set -o errexit
                  ^ (line: 474)
```

### bitnami/zookeeper

Result: FAIL | Status: failed
Attempts: 133 | Remaining iterations: unknown
Coverage: known inputs, then original-schema robustness sampling
Artifacts: [bitnami-runs/bitnami-charts_1789251211/runs/zookeeper_1789253580/0000](<bitnami-runs/bitnami-charts_1789251211/runs/zookeeper_1789253580/0000>)

Filtering applied: True
Generation order only; original-schema cases run last, not removed

Phase known-inputs: failed | Attempts: 32

Phase robustness: passed | Attempts: 101

```text
known-inputs: invalid rendered manifest: Object of type TaggedScalar is not JSON serializable
```

