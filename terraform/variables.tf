# Variables for insecure test infrastructure
# WARNING: This configuration is intentionally insecure for PR testing purposes

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
  default     = "rg-insecure-test"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus"
}

variable "vm_admin_username" {
  description = "Admin username for the VM"
  type        = string
  default     = "adminuser"
}

# SECURITY ISSUE: Hardcoded password in variable default
variable "vm_admin_password" {
  description = "Admin password for the VM"
  type        = string
  default     = "P@ssw0rd123!"  # Intentionally insecure for testing
  sensitive   = true
}

variable "test_user_object_id" {
  description = "Object ID of the test user for RBAC"
  type        = string
  default     = "00000000-0000-0000-0000-000000000000"
}

variable "storage_account_name" {
  description = "Name of the storage account"
  type        = string
  default     = "stinsecuretest123"
}

variable "environment" {
  description = "Environment tag"
  type        = string
  default     = "test"
}
