variable "environment" {
  type    = string
  default = "production"
}

variable "region" {
  type    = string
  default = "eu-west-1"
}

variable "availability_zones" {
  type    = list(string)
  default = ["eu-west-1a", "eu-west-1b"]
}

variable "rds_instance_class" {
  type    = string
  default = "db.r6g.xlarge"
}

variable "rds_storage_size" {
  type    = number
  default = 100
}

variable "opensearch_instance_type" {
  type    = string
  default = "r6g.large.search"
}

variable "opensearch_instance_count" {
  type    = number
  default = 3
}

variable "opensearch_ebs_volume" {
  type    = number
  default = 50
}

variable "eks_app_desired" {
  type    = number
  default = 3
}

variable "eks_app_min" {
  type    = number
  default = 2
}

variable "eks_temporal_desired" {
  type    = number
  default = 2
}

variable "eks_temporal_min" {
  type    = number
  default = 1
}

variable "eks_monitoring_desired" {
  type    = number
  default = 1
}

variable "eks_monitoring_min" {
  type    = number
  default = 1
}

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------

module "networking" {
  source = "../../modules/networking"

  environment        = var.environment
  region             = var.region
  availability_zones = var.availability_zones
}

# ---------------------------------------------------------------------------
# Data Layer
# ---------------------------------------------------------------------------

module "rds" {
  source = "../../modules/rds"

  environment       = var.environment
  instance_class    = var.rds_instance_class
  storage_size      = var.rds_storage_size
  subnet_ids        = module.networking.private_data_subnet_ids
  security_group_id = module.networking.rds_sg_id
}

module "opensearch" {
  source = "../../modules/opensearch"

  environment       = var.environment
  instance_type     = var.opensearch_instance_type
  instance_count    = var.opensearch_instance_count
  ebs_volume_size   = var.opensearch_ebs_volume
  subnet_ids        = module.networking.private_data_subnet_ids
  security_group_id = module.networking.opensearch_sg_id
}

module "s3" {
  source = "../../modules/s3"

  environment = var.environment
}

# ---------------------------------------------------------------------------
# Compute Layer
# ---------------------------------------------------------------------------

module "eks" {
  source = "../../modules/eks"

  environment       = var.environment
  subnet_ids        = module.networking.private_app_subnet_ids
  security_group_id = module.networking.eks_cluster_sg_id
}

module "iam" {
  source = "../../modules/iam"

  environment        = var.environment
  oidc_provider_arn  = module.eks.oidc_provider_arn
  oidc_provider_url  = module.eks.oidc_provider_url
  s3_bucket_arn      = module.s3.bucket_arn
}

# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------

module "secrets" {
  source = "../../modules/secrets"

  environment = var.environment
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "vpc_id" {
  value = module.networking.vpc_id
}

output "eks_cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "rds_endpoint" {
  value     = module.rds.endpoint
  sensitive = true
}

output "opensearch_endpoint" {
  value = module.opensearch.domain_endpoint
}

output "s3_bucket" {
  value = module.s3.bucket_name
}
