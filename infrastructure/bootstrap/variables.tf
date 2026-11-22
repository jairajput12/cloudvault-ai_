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

variable "create_oidc_provider" {
  description = "Create the GitHub OIDC provider. Set to false if this account already has one."
  type        = bool
  default     = true
}
