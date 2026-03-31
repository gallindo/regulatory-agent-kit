variable "project_name" {
  description = "Project name prefix for all resources"
  type        = string
  default     = "rak"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "db_sku_name" {
  description = "PostgreSQL Flexible Server SKU"
  type        = string
  default     = "GP_Standard_D2s_v3"
}

variable "aks_node_vm_size" {
  description = "AKS node VM size"
  type        = string
  default     = "Standard_D2s_v3"
}

variable "aks_node_count" {
  description = "AKS desired node count"
  type        = number
  default     = 2
}

variable "db_password" {
  description = "Database administrator password"
  type        = string
  sensitive   = true
}
