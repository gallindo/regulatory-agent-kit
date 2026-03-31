terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  name_prefix = "${var.project_name}-${var.environment}"
  common_labels = {
    project     = var.project_name
    environment = var.environment
    managed-by  = "terraform"
  }
}

# VPC Network
resource "google_compute_network" "main" {
  name                    = "${local.name_prefix}-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "main" {
  name          = "${local.name_prefix}-subnet"
  ip_cidr_range = "10.0.0.0/20"
  region        = var.region
  network       = google_compute_network.main.id

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.1.0.0/16"
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.2.0.0/20"
  }
}

# GKE Autopilot Cluster
resource "google_container_cluster" "main" {
  name     = "${local.name_prefix}-cluster"
  location = var.region

  network    = google_compute_network.main.id
  subnetwork = google_compute_subnetwork.main.id

  enable_autopilot = true

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  release_channel {
    channel = var.environment == "prod" ? "STABLE" : "REGULAR"
  }

  resource_labels = local.common_labels
}

# Cloud SQL PostgreSQL
resource "google_sql_database_instance" "postgres" {
  name             = "${local.name_prefix}-postgres"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    tier              = var.db_tier
    availability_type = var.environment == "prod" ? "REGIONAL" : "ZONAL"

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      backup_retention_settings {
        retained_backups = 7
      }
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.main.id
    }

    disk_size       = 50
    disk_autoresize = true
    disk_type       = "PD_SSD"

    user_labels = local.common_labels
  }

  deletion_protection = var.environment == "prod"
}

resource "google_sql_database" "rak" {
  name     = "rak"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "rak_admin" {
  name     = "rak_admin"
  instance = google_sql_database_instance.postgres.name
  password = var.db_password
}

# Private service connection for Cloud SQL
resource "google_compute_global_address" "private_ip" {
  name          = "${local.name_prefix}-private-ip"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main.id
}

resource "google_service_networking_connection" "private_vpc" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip.name]
}

# GCS Bucket for audit archives
resource "google_storage_bucket" "audit_archives" {
  name     = "${local.name_prefix}-audit-archives"
  location = var.region

  versioning {
    enabled = true
  }

  encryption {
    default_kms_key_name = null # Uses Google-managed keys by default
  }

  uniform_bucket_level_access = true

  labels = local.common_labels
}

# Artifact Registry
resource "google_artifact_registry_repository" "rak" {
  for_each = toset(["api", "worker"])

  location      = var.region
  repository_id = "${local.name_prefix}-${each.key}"
  format        = "DOCKER"

  labels = local.common_labels
}

# Secret Manager
resource "google_secret_manager_secret" "api_keys" {
  secret_id = "${local.name_prefix}-api-keys"

  replication {
    auto {}
  }

  labels = local.common_labels
}
