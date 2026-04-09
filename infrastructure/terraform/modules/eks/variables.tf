variable "environment" {
  description = "Deployment environment (e.g. dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version for the EKS cluster"
  type        = string
  default     = "1.29"
}

variable "subnet_ids" {
  description = "List of subnet IDs for the EKS cluster and node groups"
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group ID to attach to the EKS cluster"
  type        = string
}

variable "node_group_configs" {
  description = "Configuration overrides for managed node groups"
  type = map(object({
    instance_types = list(string)
    desired_size   = number
    min_size       = number
    max_size       = number
    labels         = map(string)
  }))
  default = {
    app = {
      instance_types = ["m6i.xlarge"]
      desired_size   = 3
      min_size       = 2
      max_size       = 5
      labels         = { role = "app" }
    }
    temporal = {
      instance_types = ["m6i.large"]
      desired_size   = 2
      min_size       = 1
      max_size       = 3
      labels         = { role = "temporal" }
    }
    monitoring = {
      instance_types = ["t3.large"]
      desired_size   = 2
      min_size       = 1
      max_size       = 3
      labels         = { role = "monitoring" }
    }
  }
}
