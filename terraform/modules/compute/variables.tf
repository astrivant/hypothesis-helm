variable "project_id" {
  description = "Existing GCP project, authenticated through application default credentials."
  type        = string
}
variable "region" {
  type    = string
  default = "us-central1"
}
variable "zone" {
  type    = string
  default = "us-central1-a"
}
variable "name" {
  type    = string
  default = "hypothesis-shards"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,39}$", var.name))
    error_message = "Use a lowercase GCE name prefix of at most 40 characters."
  }
}
variable "workers" {
  description = "Fixed VM replicas; each owns one stable 1-based application shard."
  type = object({
    replicas            = optional(number, 3)
    machine_type        = optional(string, "e2-standard-4")
    disk_gib            = optional(number, 50)
    image               = optional(string, "debian-cloud/debian-13")
    subnet_cidr         = optional(string, "10.84.0.0/24")
    operator_members    = set(string)
    deletion_protection = optional(bool, false)
  })
  validation {
    condition     = var.workers.replicas >= 1 && var.workers.replicas <= 100 && floor(var.workers.replicas) == var.workers.replicas
    error_message = "replicas must be an integer from 1 to 100."
  }
  validation {
    condition     = var.workers.disk_gib >= 30 && length(var.workers.operator_members) > 0
    error_message = "Provide at least 30 GiB per worker and at least one OS Login/IAP operator."
  }
}
