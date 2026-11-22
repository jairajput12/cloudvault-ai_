variable "aws_region" {
  description = "Region everything is deployed to. Sydney (ap-southeast-2) by default. Model calls go to bedrock_region instead."
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

variable "bedrock_region" {
  description = "Region the model calls go to. Bedrock daily token quotas are per account and region, and us-east-1 usually has the most headroom on a new account. The text sent to the model leaves the main region when this differs from aws_region."
  type        = string
  default     = "us-east-1"
}

variable "bedrock_model_id" {
  description = "Bedrock model or inference profile the Lambdas call in bedrock_region: a model ID, or a cross-region profile ID such as us.amazon.nova-lite-v1:0. A regional prefix (apac., us., eu.) is stripped to find the underlying model for the IAM policy."
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
