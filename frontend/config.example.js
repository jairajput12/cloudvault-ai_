// Copy this file to config.js to run the frontend locally against a deployed stack.
// The deploy pipeline writes config.js for you from the Terraform outputs:
//   terraform output api_url
//   terraform output region
//   terraform output cognito_client_id
//
// When serving locally, add your origin (for example http://localhost:8080) to
// extra_cors_origins in infrastructure/terraform.tfvars so the API accepts it.
window.CLOUDVAULT_CONFIG = {
  apiBase: "https://xxxxxxxxxx.execute-api.ap-south-1.amazonaws.com",
  cognitoRegion: "ap-south-1",
  cognitoClientId: "xxxxxxxxxxxxxxxxxxxxxxxxxx"
};
