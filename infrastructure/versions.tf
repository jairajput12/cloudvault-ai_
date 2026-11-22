terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }

  # The bucket, key and region are passed in at init time by the pipeline
  # (see infrastructure/README.md), so nothing account-specific lives here.
  backend "s3" {
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  name_prefix = "${var.project}-${var.environment}"
  account_id  = data.aws_caller_identity.current.account_id
  region      = data.aws_region.current.region

  # apac.amazon.nova-lite-v1:0 -> amazon.nova-lite-v1:0
  base_model_id = replace(var.bedrock_model_id, "/^(apac|us|eu|global)[.]/", "")
}
