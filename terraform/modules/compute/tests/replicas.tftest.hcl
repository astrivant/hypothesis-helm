mock_provider "google" {}
variables {
  project_id = "hypothesis-test"
  workers    = { replicas = 3, operator_members = ["user:test@example.com"] }
}
run "private_replicas" {
  command = plan
  assert {
    condition     = length(google_compute_instance.worker) == 3 && output.shard_workers.shard_total == 3 && [for vm in output.shard_workers.workers : vm.shard_index] == [1, 2, 3]
    error_message = "Each replica must own one complete, unique, 1-based shard assignment."
  }
  assert {
    condition     = alltrue([for vm in google_compute_instance.worker : length(vm.network_interface[0].access_config) == 0 && vm.metadata["enable-oslogin"] == "TRUE"])
    error_message = "Workers must stay private and require OS Login."
  }
  assert {
    condition     = google_compute_firewall.iap.source_ranges == toset(["35.235.240.0/20"])
    error_message = "SSH must be restricted to IAP."
  }
}
run "single_worker" {
  command = plan
  variables { workers = { replicas = 1, operator_members = ["user:test@example.com"] } }
  assert {
    condition     = output.shard_workers.shard_total == 1 && output.shard_workers.workers[0].shard_index == 1
    error_message = "A single replica must receive shard 1/1."
  }
}
run "reject_fractional_replicas" {
  command = plan
  variables { workers = { replicas = 1.5, operator_members = ["user:test@example.com"] } }
  expect_failures = [var.workers]
}
