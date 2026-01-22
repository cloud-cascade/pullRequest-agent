# Insecure Terraform Configuration for PR Security Testing
# WARNING: This configuration contains intentional security vulnerabilities
# DO NOT deploy this to production environments

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

# Resource Group
resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location

  tags = {
    environment = var.environment
    purpose     = "security-testing"
  }
}

# ============================================================================
# VIRTUAL NETWORK
# ============================================================================

resource "azurerm_virtual_network" "main" {
  name                = "vnet-insecure-test"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_subnet" "main" {
  name                 = "subnet-main"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.1.0/24"]
}

# ============================================================================
# NETWORK SECURITY GROUP - INTENTIONALLY INSECURE
# ============================================================================

resource "azurerm_network_security_group" "insecure" {
  name                = "nsg-insecure-rdp-open"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  # SECURITY ISSUE: RDP port 3389 exposed to the entire internet
  security_rule {
    name                       = "AllowRDPFromInternet"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "3389"
    source_address_prefix      = "*"  # VULNERABLE: Open to 0.0.0.0/0
    destination_address_prefix = "*"
  }

  # SECURITY ISSUE: SSH port 22 exposed to the entire internet
  security_rule {
    name                       = "AllowSSHFromInternet"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "0.0.0.0/0"  # VULNERABLE: Open to internet
    destination_address_prefix = "*"
  }

  # SECURITY ISSUE: All outbound traffic allowed
  security_rule {
    name                       = "AllowAllOutbound"
    priority                   = 200
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  tags = {
    environment = var.environment
    warning     = "intentionally-insecure"
  }
}

# ============================================================================
# PUBLIC IP - NO DDoS PROTECTION
# ============================================================================

resource "azurerm_public_ip" "vm" {
  name                = "pip-vm-insecure"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Basic"  # SECURITY ISSUE: Basic SKU has no DDoS protection

  tags = {
    environment = var.environment
  }
}

# ============================================================================
# NETWORK INTERFACE
# ============================================================================

resource "azurerm_network_interface" "vm" {
  name                = "nic-vm-insecure"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.main.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.vm.id
  }
}

resource "azurerm_network_interface_security_group_association" "vm" {
  network_interface_id      = azurerm_network_interface.vm.id
  network_security_group_id = azurerm_network_security_group.insecure.id
}

# ============================================================================
# VIRTUAL MACHINE - INTENTIONALLY INSECURE
# ============================================================================

resource "azurerm_windows_virtual_machine" "insecure" {
  name                = "vm-insecure-test"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  size                = "Standard_DS1_v2"
  admin_username      = var.vm_admin_username
  admin_password      = var.vm_admin_password  # SECURITY ISSUE: Password from variable

  # SECURITY ISSUE: No encryption at host
  encryption_at_host_enabled = false

  network_interface_ids = [
    azurerm_network_interface.vm.id,
  ]

  os_disk {
    name                 = "osdisk-vm-insecure"
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
    # SECURITY ISSUE: Disk encryption not enabled
  }

  source_image_reference {
    publisher = "MicrosoftWindowsServer"
    offer     = "WindowsServer"
    sku       = "2019-Datacenter"
    version   = "latest"
  }

  # SECURITY ISSUE: No boot diagnostics enabled
  boot_diagnostics {
    storage_account_uri = null
  }

  tags = {
    environment = var.environment
    warning     = "intentionally-insecure"
  }
}

# ============================================================================
# STORAGE ACCOUNT - INTENTIONALLY INSECURE
# ============================================================================

resource "azurerm_storage_account" "insecure" {
  name                     = var.storage_account_name
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  # SECURITY ISSUE: HTTPS not enforced
  enable_https_traffic_only = false

  # SECURITY ISSUE: Public network access enabled
  public_network_access_enabled = true

  # SECURITY ISSUE: Shared key access enabled
  shared_access_key_enabled = true

  # SECURITY ISSUE: Allow blob public access
  allow_nested_items_to_be_public = true

  # SECURITY ISSUE: Minimum TLS version too low
  min_tls_version = "TLS1_0"

  # SECURITY ISSUE: No infrastructure encryption
  infrastructure_encryption_enabled = false

  network_rules {
    default_action = "Allow"  # SECURITY ISSUE: Allow all by default
    bypass         = ["AzureServices"]
  }

  blob_properties {
    # SECURITY ISSUE: No soft delete configured
    delete_retention_policy {
      days = 0
    }
  }

  tags = {
    environment = var.environment
    warning     = "intentionally-insecure"
  }
}

# SECURITY ISSUE: Public container
resource "azurerm_storage_container" "public" {
  name                  = "public-container"
  storage_account_name  = azurerm_storage_account.insecure.name
  container_access_type = "blob"  # SECURITY ISSUE: Public blob access
}

# Another public container
resource "azurerm_storage_container" "public_full" {
  name                  = "public-full-access"
  storage_account_name  = azurerm_storage_account.insecure.name
  container_access_type = "container"  # SECURITY ISSUE: Full public container access
}

# ============================================================================
# RBAC - INTENTIONALLY OVERPRIVILEGED
# ============================================================================

# SECURITY ISSUE: Owner role assigned to test user at subscription level
resource "azurerm_role_assignment" "test_user_owner" {
  scope                = "/subscriptions/${data.azurerm_subscription.current.subscription_id}"
  role_definition_name = "Owner"  # SECURITY ISSUE: Excessive privileges
  principal_id         = var.test_user_object_id
}

# SECURITY ISSUE: Contributor role on resource group
resource "azurerm_role_assignment" "test_user_contributor" {
  scope                = azurerm_resource_group.main.id
  role_definition_name = "Contributor"
  principal_id         = var.test_user_object_id
}

# SECURITY ISSUE: User Access Administrator role
resource "azurerm_role_assignment" "test_user_uaa" {
  scope                = azurerm_resource_group.main.id
  role_definition_name = "User Access Administrator"  # SECURITY ISSUE: Can grant others access
  principal_id         = var.test_user_object_id
}

# SECURITY ISSUE: Storage Blob Data Owner (full access to all blobs)
resource "azurerm_role_assignment" "test_user_storage" {
  scope                = azurerm_storage_account.insecure.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = var.test_user_object_id
}

# Data source for current subscription
data "azurerm_subscription" "current" {}

# ============================================================================
# OUTPUTS - EXPOSING SENSITIVE DATA
# ============================================================================

# SECURITY ISSUE: Exposing storage account key in outputs
output "storage_account_primary_key" {
  value     = azurerm_storage_account.insecure.primary_access_key
  sensitive = false  # SECURITY ISSUE: Not marked as sensitive
}

output "storage_account_connection_string" {
  value     = azurerm_storage_account.insecure.primary_connection_string
  sensitive = false  # SECURITY ISSUE: Connection string exposed
}

output "vm_public_ip" {
  value = azurerm_public_ip.vm.ip_address
}

output "vm_admin_password" {
  value     = var.vm_admin_password
  sensitive = false  # SECURITY ISSUE: Password exposed in output
}
