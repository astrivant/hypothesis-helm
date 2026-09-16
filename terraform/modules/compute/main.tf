locals {
  shards = { for index in range(var.workers.replicas) : format("%03d", index + 1) => index + 1 }
  operators = { for entry in setproduct(keys(local.shards), var.workers.operator_members) :
    "${entry[0]}:${entry[1]}" => { shard = entry[0], member = entry[1] }
  }
}
resource "google_project_service" "api" {
  for_each           = toset(["compute.googleapis.com", "iap.googleapis.com", "oslogin.googleapis.com", "iam.googleapis.com"])
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}
resource "google_compute_network" "workers" {
  project                 = var.project_id
  name                    = var.name
  auto_create_subnetworks = false
  depends_on              = [google_project_service.api]
}
resource "google_compute_subnetwork" "workers" {
  project                  = var.project_id
  name                     = var.name
  region                   = var.region
  network                  = google_compute_network.workers.id
  ip_cidr_range            = var.workers.subnet_cidr
  private_ip_google_access = true
}
resource "google_compute_router" "workers" {
  project = var.project_id
  name    = var.name
  region  = var.region
  network = google_compute_network.workers.id
}
resource "google_compute_router_nat" "egress" {
  project                            = var.project_id
  name                               = var.name
  router                             = google_compute_router.workers.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"
  subnetwork {
    name                    = google_compute_subnetwork.workers.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }
}
resource "google_service_account" "workers" {
  project      = var.project_id
  account_id   = "${substr(var.name, 0, 20)}-${substr(sha256(var.name), 0, 8)}"
  display_name = "Hypothesis shard workers; no project roles or service account keys"
  depends_on   = [google_project_service.api]
}
resource "google_compute_instance" "worker" {
  for_each                  = local.shards
  project                   = var.project_id
  zone                      = var.zone
  name                      = "${var.name}-${each.key}"
  machine_type              = var.workers.machine_type
  deletion_protection       = var.workers.deletion_protection
  allow_stopping_for_update = true
  tags                      = [var.name]
  labels                    = { application = "hypothesis-helm", shard = each.key }
  metadata                  = { enable-oslogin = "TRUE", block-project-ssh-keys = "TRUE" }
  boot_disk {
    initialize_params {
      image = var.workers.image
      type  = "pd-balanced"
      size  = var.workers.disk_gib
    }
  }
  network_interface {
    subnetwork = google_compute_subnetwork.workers.id
  }
  service_account {
    email  = google_service_account.workers.email
    scopes = ["cloud-platform"]
  }
  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }
  depends_on = [google_compute_router_nat.egress]
  lifecycle {
    precondition {
      condition     = startswith(var.zone, "${var.region}-")
      error_message = "The zone must be in the configured region."
    }
  }
}
resource "google_compute_firewall" "iap" {
  project       = var.project_id
  name          = "${var.name}-iap"
  network       = google_compute_network.workers.id
  source_ranges = ["35.235.240.0/20"]
  target_tags   = [var.name]
  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}
resource "google_iap_tunnel_instance_iam_member" "operator" {
  for_each = local.operators
  project  = var.project_id
  zone     = var.zone
  instance = google_compute_instance.worker[each.value.shard].name
  role     = "roles/iap.tunnelResourceAccessor"
  member   = each.value.member
}
resource "google_project_iam_member" "login" {
  for_each = var.workers.operator_members
  project  = var.project_id
  role     = "roles/compute.osAdminLogin"
  member   = each.key
}
resource "google_project_iam_member" "viewer" {
  for_each = var.workers.operator_members
  project  = var.project_id
  role     = "roles/compute.viewer"
  member   = each.key
}
resource "google_service_account_iam_member" "operator" {
  for_each           = var.workers.operator_members
  service_account_id = google_service_account.workers.name
  role               = "roles/iam.serviceAccountUser"
  member             = each.key
}
