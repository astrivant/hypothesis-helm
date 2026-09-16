output "shard_workers" {
  description = "Non-secret inventory consumed by ansible/site.yml; export with terraform output -json."
  value = {
    project_id  = var.project_id
    shard_total = var.workers.replicas
    workers = [for key, vm in google_compute_instance.worker : {
      name        = vm.name
      instance_id = vm.instance_id
      zone        = vm.zone
      shard_index = local.shards[key]
    }]
  }
}
