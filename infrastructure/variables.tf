variable "aws_region" {
  description = "Region everything is deployed to. Bedrock, Textract and the Nova model must be available here."
  type        = string
  default     = "ap-southeast-2"
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
  description = "Bedrock model the Lambdas call. The Lambda role is allowed to invoke this one model in this region."
  type        = string
  default     = "amazon.nova-lite-v1:0"
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
