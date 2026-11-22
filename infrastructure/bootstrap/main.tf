# One-time setup, run by a person with admin rights in the AWS account:
#
#   - the S3 bucket that holds Terraform state for the main stack
#   - the GitHub OIDC trust, so the pipeline signs in without stored AWS keys
#   - the role the pipeline assumes, limited to the services this app uses
#
# It uses local state on purpose: it is created once and rarely touched.
# See infrastructure/README.md.

terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
      Stack     = "bootstrap"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id

  # GitHub puts the repo in the token's `sub` claim either by name
  # (repo:owner/name) or, for newer repos, with the numeric owner and repo IDs
  # (repo:owner@id/name@id). Both exact forms are trusted, never a wildcard.
  github_subs = compact(["repo:${var.github_repository}", var.github_subject_prefix])

  github_sub_patterns = flatten([
    for prefix in local.github_subs : [
      "${prefix}:pull_request",
      "${prefix}:ref:refs/heads/main",
      "${prefix}:environment:${var.environment}",
    ]
  ])
}

# ---- Terraform state ----

resource "aws_s3_bucket" "state" {
  bucket = "${var.project}-tfstate-${local.account_id}"
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ---- GitHub Actions sign-in ----

# An account can hold only one provider for this URL. Set
# create_oidc_provider = false if another stack already created it.
resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_oidc_provider ? 1 : 0

  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.create_oidc_provider ? 0 : 1

  url = "https://token.actions.githubusercontent.com"
}

locals {
  oidc_provider_arn = var.create_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn
}

data "aws_iam_policy_document" "deploy_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Pull requests (plan only), the main branch, and the `poc` environment the
    # deploy job runs in. Nothing else in the repository can assume the role.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = local.github_sub_patterns
    }
  }
}

# Named so it does not match the cloudvault-* pattern its own policy allows
# IAM changes on: the pipeline cannot edit the role it runs as.
resource "aws_iam_role" "deploy" {
  name                 = "gha-${var.project}-deploy"
  assume_role_policy   = data.aws_iam_policy_document.deploy_trust.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "deploy" {
  statement {
    sid       = "ProjectBucketsAndState"
    actions   = ["s3:*"]
    resources = ["arn:aws:s3:::${var.project}-*", "arn:aws:s3:::${var.project}-*/*"]
  }

  statement {
    sid       = "ProjectTables"
    actions   = ["dynamodb:*"]
    resources = ["arn:aws:dynamodb:*:${local.account_id}:table/${var.project}-*"]
  }

  statement {
    sid       = "ProjectFunctions"
    actions   = ["lambda:*"]
    resources = ["arn:aws:lambda:*:${local.account_id}:function:${var.project}-*"]
  }

  statement {
    sid       = "ProjectLogs"
    actions   = ["logs:*"]
    resources = ["arn:aws:logs:*:${local.account_id}:log-group:/aws/lambda/${var.project}-*", "arn:aws:logs:*:${local.account_id}:log-group:/aws/lambda/${var.project}-*:*"]
  }

  statement {
    sid       = "ListLogGroups"
    actions   = ["logs:DescribeLogGroups", "logs:ListTagsForResource"]
    resources = ["*"]
  }

  statement {
    sid       = "ProjectRoles"
    actions   = ["iam:*"]
    resources = ["arn:aws:iam::${local.account_id}:role/${var.project}-*"]
  }

  # These services have no usable resource-level scoping for create calls.
  statement {
    sid = "ApiAuthAndCdn"
    actions = [
      "apigateway:*",
      "cognito-idp:*",
      "cloudfront:*",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "deploy" {
  name   = "deploy"
  role   = aws_iam_role.deploy.id
  policy = data.aws_iam_policy_document.deploy.json
}
