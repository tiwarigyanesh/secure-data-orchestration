terraform {
  required_version = ">= 1.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "SecureDataOrchestration"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# Random suffix for globally unique resource names
resource "random_id" "suffix" {
  byte_length = 4
}

locals {
  name_prefix = "sdo-${var.environment}"
  bucket_name = "${local.name_prefix}-ingress-${random_id.suffix.hex}"
}

# Data Sources

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Get default VPC and subnets for ECS (in production, use dedicated VPC)
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}
