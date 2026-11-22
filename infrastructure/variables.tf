variable "aws_region" {
  description = "Region everything is deployed to. Mumbai (ap-south-1) by default. Bedrock, Textract and the Nova model must be available here."
  type        = string
  default     = "ap-south-1"
}

variable "project" {
  description = "Short name used as the prefix on every resource."
  type        = string
  default     = "cloudvault"
}

variable "environment" {
  description = "Environment name, also part of every resource name."
  type        = string
  default     = "poc"
}

variable "bedrock_model_id" {
  description = "Bedrock model or inference profile the Lambdas call. Mumbai serves Nova Lite through the cross-region APAC profile, so the default is the profile ID. A regional prefix (apac., us., eu.) is stripped to find the underlying model for the IAM policy."
  type        = string
  default     = "apac.amazon.nova-lite-v1:0"
}

variable "log_retention_days" {
  description = "How long Lambda logs are kept."
  type        = number
  default     = 14
}

variable "extra_cors_origins" {
  description = "Extra browser origins allowed to call the API and upload to S3, for example http://localhost:8080 when running the frontend locally."
  type        = list(string)
  default     = []
}

variable "api_throttle_rate" {
  description = "Steady-state requests per second the API accepts. A low default keeps a public POC from running up a Bedrock bill."
  type        = number
  default     = 10
}

variable "api_throttle_burst" {
  description = "Burst limit for the API."
  type        = number
  default     = 20
}
