# RAK Infrastructure Modules

This directory is reserved for shared Terraform modules used across cloud providers.

## Cloud Provider Templates

Each cloud provider directory contains a standalone Terraform configuration that
provisions the core infrastructure needed to run the Regulatory Agent Kit (RAK):

| Directory | Provider | Key Resources |
|-----------|----------|---------------|
| `aws/`    | AWS      | VPC, EKS, RDS PostgreSQL 16, S3, ECR, Secrets Manager |
| `gcp/`    | GCP      | VPC, GKE Autopilot, Cloud SQL PostgreSQL 16, GCS, Artifact Registry, Secret Manager |
| `azure/`  | Azure    | VNet, AKS, PostgreSQL Flexible Server 16, Blob Storage, ACR, Key Vault |

## Usage

1. Navigate to the desired provider directory (e.g., `cd aws/`).
2. Copy and configure a `terraform.tfvars` file with your values.
3. Run the standard Terraform workflow:

```bash
terraform init
terraform plan -out=plan.tfplan
terraform apply plan.tfplan
```

## Required Variables

All providers require at minimum:

- `environment` -- Target environment (`dev`, `staging`, `prod`)
- `db_password` -- Database administrator password (sensitive)

Provider-specific variables (region, project ID, instance sizes) have sensible
defaults documented in each `variables.tf`.

## Design Decisions

- **Production hardening:** Resources automatically enable multi-AZ / HA, deletion
  protection, and geo-redundant backups when `environment = "prod"`.
- **Private networking:** Databases are placed in private subnets with no public
  IP; only the Kubernetes cluster can reach them.
- **Encryption at rest:** All storage (database, object storage, container images)
  is encrypted by default.
- **Immutable container images:** Container registries enforce immutable tags (AWS)
  or use content-addressable digests (GCP, Azure).
