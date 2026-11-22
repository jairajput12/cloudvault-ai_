output "site_url" {
  description = "Where the app is served from."
  value       = local.site_url
}

output "api_url" {
  description = "Base URL of the HTTP API."
  value       = aws_apigatewayv2_api.http.api_endpoint
}

output "region" {
  description = "Region the stack is deployed to."
  value       = local.region
}

output "cognito_user_pool_id" {
  description = "Cognito user pool ID."
  value       = aws_cognito_user_pool.main.id
}

output "cognito_client_id" {
  description = "Cognito app client the page signs in with."
  value       = aws_cognito_user_pool_client.web.id
}

output "site_bucket" {
  description = "Bucket the frontend files are synced to."
  value       = aws_s3_bucket.site.bucket
}

output "uploads_bucket" {
  description = "Bucket user files are stored in."
  value       = aws_s3_bucket.uploads.bucket
}

output "cloudfront_distribution_id" {
  description = "Distribution to invalidate after a frontend deploy."
  value       = aws_cloudfront_distribution.site.id
}
