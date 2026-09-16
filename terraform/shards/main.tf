provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}
module "compute" {
  source     = "../modules/compute"
  project_id = var.project_id
  region     = var.region
  zone       = var.zone
  name       = var.name
  workers    = var.workers
}
output "shard_workers" {
  value = module.compute.shard_workers
}
