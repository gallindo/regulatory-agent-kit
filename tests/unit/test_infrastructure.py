"""Tests for Infrastructure-as-Code templates."""

from pathlib import Path

INFRA_DIR = Path(__file__).resolve().parents[2] / "infrastructure"


class TestAWSInfrastructure:
    """Validate AWS Terraform configuration files."""

    def test_main_tf_exists(self) -> None:
        assert (INFRA_DIR / "aws" / "main.tf").exists()

    def test_variables_tf_exists(self) -> None:
        assert (INFRA_DIR / "aws" / "variables.tf").exists()

    def test_outputs_tf_exists(self) -> None:
        assert (INFRA_DIR / "aws" / "outputs.tf").exists()

    def test_main_tf_contains_required_resources(self) -> None:
        content = (INFRA_DIR / "aws" / "main.tf").read_text()
        assert "aws_db_instance" in content  # RDS
        assert "eks" in content  # EKS
        assert "aws_s3_bucket" in content  # S3
        assert "aws_ecr_repository" in content  # ECR
        assert "aws_secretsmanager_secret" in content  # Secrets

    def test_variables_has_required_vars(self) -> None:
        content = (INFRA_DIR / "aws" / "variables.tf").read_text()
        assert "project_name" in content
        assert "region" in content
        assert "environment" in content

    def test_outputs_has_required_outputs(self) -> None:
        content = (INFRA_DIR / "aws" / "outputs.tf").read_text()
        assert "eks_cluster_endpoint" in content
        assert "rds_endpoint" in content
        assert "s3_audit_bucket" in content
        assert "ecr_repositories" in content

    def test_main_tf_has_provider_config(self) -> None:
        content = (INFRA_DIR / "aws" / "main.tf").read_text()
        assert 'provider "aws"' in content
        assert "required_version" in content

    def test_main_tf_has_vpc(self) -> None:
        content = (INFRA_DIR / "aws" / "main.tf").read_text()
        assert "module" in content and "vpc" in content
        assert "private_subnets" in content

    def test_rds_uses_postgres_16(self) -> None:
        content = (INFRA_DIR / "aws" / "main.tf").read_text()
        assert 'engine         = "postgres"' in content
        assert 'engine_version = "16"' in content

    def test_s3_bucket_has_versioning(self) -> None:
        content = (INFRA_DIR / "aws" / "main.tf").read_text()
        assert "aws_s3_bucket_versioning" in content

    def test_s3_bucket_has_encryption(self) -> None:
        content = (INFRA_DIR / "aws" / "main.tf").read_text()
        assert "aws_s3_bucket_server_side_encryption_configuration" in content

    def test_db_password_is_sensitive(self) -> None:
        content = (INFRA_DIR / "aws" / "main.tf").read_text()
        assert "sensitive   = true" in content


class TestGCPInfrastructure:
    """Validate GCP Terraform configuration files."""

    def test_main_tf_exists(self) -> None:
        assert (INFRA_DIR / "gcp" / "main.tf").exists()

    def test_variables_tf_exists(self) -> None:
        assert (INFRA_DIR / "gcp" / "variables.tf").exists()

    def test_outputs_tf_exists(self) -> None:
        assert (INFRA_DIR / "gcp" / "outputs.tf").exists()

    def test_main_tf_contains_required_resources(self) -> None:
        content = (INFRA_DIR / "gcp" / "main.tf").read_text()
        assert "google_container_cluster" in content  # GKE
        assert "google_sql_database_instance" in content  # Cloud SQL
        assert "google_storage_bucket" in content  # GCS
        assert "google_artifact_registry_repository" in content  # Artifact Registry

    def test_variables_has_required_vars(self) -> None:
        content = (INFRA_DIR / "gcp" / "variables.tf").read_text()
        assert "project_name" in content
        assert "project_id" in content
        assert "region" in content
        assert "environment" in content

    def test_outputs_has_required_outputs(self) -> None:
        content = (INFRA_DIR / "gcp" / "outputs.tf").read_text()
        assert "gke_cluster_endpoint" in content
        assert "cloud_sql_connection_name" in content
        assert "gcs_audit_bucket" in content
        assert "artifact_registry_repositories" in content

    def test_main_tf_has_provider_config(self) -> None:
        content = (INFRA_DIR / "gcp" / "main.tf").read_text()
        assert 'provider "google"' in content
        assert "required_version" in content

    def test_gke_is_autopilot(self) -> None:
        content = (INFRA_DIR / "gcp" / "main.tf").read_text()
        assert "enable_autopilot = true" in content

    def test_cloud_sql_uses_postgres_16(self) -> None:
        content = (INFRA_DIR / "gcp" / "main.tf").read_text()
        assert "POSTGRES_16" in content

    def test_gcs_has_versioning(self) -> None:
        content = (INFRA_DIR / "gcp" / "main.tf").read_text()
        assert "versioning" in content

    def test_secret_manager_configured(self) -> None:
        content = (INFRA_DIR / "gcp" / "main.tf").read_text()
        assert "google_secret_manager_secret" in content

    def test_db_password_is_sensitive(self) -> None:
        content = (INFRA_DIR / "gcp" / "variables.tf").read_text()
        assert "sensitive   = true" in content


class TestAzureInfrastructure:
    """Validate Azure Terraform configuration files."""

    def test_main_tf_exists(self) -> None:
        assert (INFRA_DIR / "azure" / "main.tf").exists()

    def test_variables_tf_exists(self) -> None:
        assert (INFRA_DIR / "azure" / "variables.tf").exists()

    def test_outputs_tf_exists(self) -> None:
        assert (INFRA_DIR / "azure" / "outputs.tf").exists()

    def test_main_tf_contains_required_resources(self) -> None:
        content = (INFRA_DIR / "azure" / "main.tf").read_text()
        assert "azurerm_kubernetes_cluster" in content  # AKS
        assert "azurerm_postgresql_flexible_server" in content  # PostgreSQL
        assert "azurerm_storage_account" in content  # Blob
        assert "azurerm_container_registry" in content  # ACR
        assert "azurerm_key_vault" in content  # Key Vault

    def test_variables_has_required_vars(self) -> None:
        content = (INFRA_DIR / "azure" / "variables.tf").read_text()
        assert "project_name" in content
        assert "location" in content
        assert "environment" in content

    def test_outputs_has_required_outputs(self) -> None:
        content = (INFRA_DIR / "azure" / "outputs.tf").read_text()
        assert "aks_cluster_endpoint" in content
        assert "postgresql_fqdn" in content
        assert "storage_account_name" in content
        assert "acr_login_server" in content
        assert "key_vault_uri" in content

    def test_main_tf_has_provider_config(self) -> None:
        content = (INFRA_DIR / "azure" / "main.tf").read_text()
        assert 'provider "azurerm"' in content
        assert "required_version" in content

    def test_postgresql_uses_version_16(self) -> None:
        content = (INFRA_DIR / "azure" / "main.tf").read_text()
        assert 'version                = "16"' in content

    def test_storage_has_versioning(self) -> None:
        content = (INFRA_DIR / "azure" / "main.tf").read_text()
        assert "versioning_enabled = true" in content

    def test_aks_has_autoscaling(self) -> None:
        content = (INFRA_DIR / "azure" / "main.tf").read_text()
        assert "auto_scaling_enabled = true" in content

    def test_db_password_is_sensitive(self) -> None:
        content = (INFRA_DIR / "azure" / "variables.tf").read_text()
        assert "sensitive   = true" in content


class TestInfrastructureModules:
    """Validate shared infrastructure modules directory."""

    def test_modules_readme_exists(self) -> None:
        assert (INFRA_DIR / "modules" / "README.md").exists()

    def test_all_providers_present(self) -> None:
        for provider in ("aws", "gcp", "azure"):
            provider_dir = INFRA_DIR / provider
            assert provider_dir.is_dir(), f"Missing provider directory: {provider}"
            assert (provider_dir / "main.tf").exists(), f"Missing main.tf for {provider}"
            assert (provider_dir / "variables.tf").exists(), f"Missing variables.tf for {provider}"
            assert (provider_dir / "outputs.tf").exists(), f"Missing outputs.tf for {provider}"
