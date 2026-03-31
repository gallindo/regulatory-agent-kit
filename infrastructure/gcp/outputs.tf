output "gke_cluster_endpoint" {
  description = "GKE cluster endpoint"
  value       = google_container_cluster.main.endpoint
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL connection name"
  value       = google_sql_database_instance.postgres.connection_name
}

output "gcs_audit_bucket" {
  description = "GCS bucket for audit archives"
  value       = google_storage_bucket.audit_archives.name
}

output "artifact_registry_repositories" {
  description = "Artifact Registry repository URLs"
  value = {
    for k, v in google_artifact_registry_repository.rak :
    k => "${var.region}-docker.pkg.dev/${var.project_id}/${v.repository_id}"
  }
}
