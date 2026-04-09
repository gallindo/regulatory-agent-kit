variable "environment" {
  description = "Deployment environment (e.g. dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "oidc_provider_arn" {
  description = "ARN of the EKS OIDC provider for IRSA trust policies"
  type        = string
}

variable "oidc_provider_url" {
  description = "URL of the EKS OIDC provider (without https:// prefix)"
  type        = string
}

variable "s3_bucket_arn" {
  description = "ARN of the S3 bucket used for artifacts and storage"
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace for service accounts"
  type        = string
  default     = "rak"
}
