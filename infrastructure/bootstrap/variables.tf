variable "aws_region" {
  description = "Region the state bucket is created in. Use the same region as the main stack."
  type        = string
  default     = "ap-southeast-2"
}

variable "project" {
  description = "Prefix shared with the main stack. The deploy role is limited to resources starting with this."
  type        = string
  default     = "cloudvault"
}

variable "environment" {
  description = "Name of the GitHub environment the deploy job runs in."
  type        = string
  default     = "poc"
}

variable "github_repository" {
  description = "The repository allowed to deploy, as owner/name."
  type        = string
  default     = "jairajput12/cloudvault-ai_"
}

variable "github_subject_prefix" {
  description = "The repository as GitHub writes it in the token subject when it includes numeric IDs, for example repo:owner@216426909/name@1313020993. Leave empty if the repository's tokens use the plain repo:owner/name form. To see which form a repo uses, print the sub claim in a workflow run."
  type        = string
  default     = "repo:jairajput12@216426909/cloudvault-ai_@1313020993"
}

variable "create_oidc_provider" {
  description = "Create the GitHub OIDC provider. Set to false if this account already has one."
  type        = bool
  default     = true
}
