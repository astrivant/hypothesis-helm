# Remote shard workers

<!-- toc:start -->
**Table of contents**

- [Provision](#provision)
- [Validate without provisioning](#validate-without-provisioning)
<!-- toc:end -->

[Ansible execution and collection](../ansible/README.md) deploys the local source snapshot to these VMs and brings results back.
The compute module follows Astrivant's OS Login/IAP handoff pattern. It does not run Ansible during Terraform apply.

`modules/compute` creates a private VPC/subnet, Cloud NAT for package downloads, an IAP-only SSH rule, a service account with
no project roles, and a configurable number of Debian 13 VMs. Every VM receives a stable 1-based shard index in the output.
`shards` is the runnable root. Default capacity is three `e2-standard-4` workers, with 50 GiB boot disks each.

## Provision

Authenticate Terraform through application default credentials and Ansible through the active gcloud identity.
The project must already exist. The Terraform identity needs permission to enable APIs, create compute/network/IAM resources
and grant the configured operators access. Operators receive OS Admin Login, Compute Viewer, permission to act as the VM service account
(`serviceAccountUser`), and IAP tunnel access scoped to each worker.
No service-account keys or SSH private keys are stored in Terraform.

```bash
gcloud auth login
gcloud auth application-default login
cp terraform/shards/terraform.tfvars.example terraform/shards/terraform.tfvars
# Fill in the existing project ID and your user/service-account member.
terraform -chdir=terraform/shards init
terraform -chdir=terraform/shards plan -out=workers.tfplan
terraform -chdir=terraform/shards apply workers.tfplan
terraform -chdir=terraform/shards output -json > terraform/shards/outputs.json
```

Applying creates billable VMs, disks and Cloud NAT. This root uses local state by default; keep it until teardown and use
a protected remote backend for shared operation. Local state, tfvars and plans are ignored by Git.
Changing the replica count changes the shard partition: use a new run ID and complete fleet for subsequent runs.
The output's instance IDs are checked before connection, so a replacement VM requires a fresh output export.

The workers have no public IPs. Package and chart downloads use Cloud NAT; inbound SSH uses
[Google IAP](https://docs.cloud.google.com/iap/docs/using-tcp-forwarding) and
[OS Login](https://docs.cloud.google.com/compute/docs/oslogin/set-up-oslogin).
The Debian 13 image provides [Python 3.13](https://packages.debian.org/trixie/python3), as required by this project.
Override `workers.image` with a specific Debian 13 image to pin the OS revision.

## Validate without provisioning

```bash
terraform fmt -check -recursive terraform
terraform -chdir=terraform/modules/compute init -backend=false
terraform -chdir=terraform/modules/compute validate
terraform -chdir=terraform/modules/compute test
terraform -chdir=terraform/shards init -backend=false
terraform -chdir=terraform/shards validate
```

Tests mock the Google provider: private networking, shard ownership, single-worker operation and invalid replica counts.

After collecting and checking the local results, remove the workers and NAT to stop their running charges:

```bash
terraform -chdir=terraform/shards plan -destroy -out=destroy.tfplan
terraform -chdir=terraform/shards apply destroy.tfplan
```

Worker disks and their caches are deleted on teardown. The fetched artifacts remain local.
