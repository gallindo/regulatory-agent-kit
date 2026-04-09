variable "environment" {
  description = "Deployment environment (e.g. dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "domain_name" {
  description = "Name of the OpenSearch domain"
  type        = string
}

variable "instance_type" {
  description = "OpenSearch instance type"
  type        = string
  default     = "r6g.large.search"
}

variable "instance_count" {
  description = "Number of data nodes in the OpenSearch cluster"
  type        = number
  default     = 3
}

variable "ebs_volume_size" {
  description = "EBS volume size in GiB per data node"
  type        = number
  default     = 50
}

variable "subnet_ids" {
  description = "List of subnet IDs for the VPC endpoint (one per AZ, must match instance_count)"
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group ID to attach to the OpenSearch domain"
  type        = string
}
