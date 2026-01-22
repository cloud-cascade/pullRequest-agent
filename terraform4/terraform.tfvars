# Terraform variables for insecure test infrastructure
# WARNING: Contains intentionally insecure values for PR security testing

resource_group_name  = "rg-insecure-pr-test"
location             = "eastus"
vm_admin_username    = "testadmin"
storage_account_name = "stinsecureprtest2024"
environment          = "testing"

# SECURITY ISSUE: Hardcoded credentials in tfvars
vm_admin_password   = "SuperSecret123!"
test_user_object_id = "12345678-1234-1234-1234-123456789012"

# SECURITY ISSUE: API keys and secrets in plain text
# api_key = "sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
# database_password = "ProductionDbP@ss!"
# jwt_secret = "my-super-secret-jwt-key-12345"
