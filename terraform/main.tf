terraform {
  required_version = ">= 1.4.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "azurerm" {
  features {}
}

variable "prefix" {
  type    = string
  default = "tfm"
}

# Región del Resource Group
variable "location" {
  type    = string
  default = "westeurope"
}

# Región del ACR (separada para esquivar políticas)
variable "acr_location" {
  type    = string
  default = "westeurope"
}

variable "sku" {
  type    = string
  default = "Basic"
}

resource "azurerm_resource_group" "rg" {
  name     = "${var.prefix}-rg"
  location = var.location
}

resource "random_string" "sfx" {
  length  = 6
  numeric = false
  upper   = false
  special = false
}

resource "azurerm_container_registry" "acr" {
  name                = "${var.prefix}acr${random_string.sfx.result}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = var.acr_location
  sku                 = var.sku
  admin_enabled       = true
}

output "acr_name" {
  value = azurerm_container_registry.acr.name
}

output "login_server" {
  value = azurerm_container_registry.acr.login_server
}

output "resource_group" {
  value = azurerm_resource_group.rg.name
}
