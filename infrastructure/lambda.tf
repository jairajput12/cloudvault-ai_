locals {
  # One entry per file in backend/. `route` is the API Gateway route key; a
  # function with no route is triggered by S3 instead. `public` routes skip the
  # JWT authorizer (only the share-link lookup, which has to work without an account).
  # Timeouts stay under API Gateway's 30 second limit for anything behind a route.
  functions = {
    upload_handler = { timeout = 90, memory = 512 }

    list_documents          = { route = "GET /documents" }
    generate_upload_url     = { route = "GET /upload-url" }
    get_download_url        = { route = "GET /download-url" }
    delete_document         = { route = "DELETE /delete-document" }
    update_document         = { route = "PATCH /update-document" }
    create_folder           = { route = "POST /create-folder" }
    list_folders            = { route = "GET /folders" }
    delete_folder           = { route = "DELETE /delete-folder" }
    create_share            = { route = "POST /create-share" }
    get_shared_file         = { route = "GET /shared-file", public = true }
    chat_with_document      = { route = "POST /chat", timeout = 29 }
    ask_assistant           = { route = "POST /ask-assistant", timeout = 29 }
    generate_study_material = { route = "POST /generate-study-material", timeout = 29 }
  }

  function_names = { for key in keys(local.functions) : key => "${local.name_prefix}-${replace(key, "_", "-")}" }

  routes = { for key, fn in local.functions : fn.route => {
    function = key
    public   = try(fn.public, false)
  } if try(fn.route, null) != null }

  lambda_environment = {
    DOCUMENTS_TABLE = aws_dynamodb_table.documents.name
    FOLDERS_TABLE   = aws_dynamodb_table.folders.name
    SHARES_TABLE    = aws_dynamodb_table.shares.name
    UPLOADS_BUCKET  = aws_s3_bucket.uploads.bucket
    SITE_URL        = local.site_url
    MODEL_ID        = var.bedrock_model_id
  }
}

data "archive_file" "function" {
  for_each = local.functions

  type        = "zip"
  source_file = "${path.module}/../backend/lambda_${each.key}.py"
  output_path = "${path.module}/build/${each.key}.zip"
}

resource "aws_cloudwatch_log_group" "function" {
  for_each = local.functions

  name              = "/aws/lambda/${local.function_names[each.key]}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "function" {
  for_each = local.functions

  function_name    = local.function_names[each.key]
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  architectures    = ["arm64"]
  handler          = "lambda_${each.key}.lambda_handler"
  filename         = data.archive_file.function[each.key].output_path
  source_code_hash = data.archive_file.function[each.key].output_base64sha256
  timeout          = try(each.value.timeout, 10)
  memory_size      = try(each.value.memory, 256)

  environment {
    variables = local.lambda_environment
  }

  depends_on = [
    aws_cloudwatch_log_group.function,
    aws_iam_role_policy_attachment.lambda_logs,
    aws_iam_role_policy.lambda_access,
  ]
}

# ---- New uploads trigger the AI processing function ----

resource "aws_lambda_permission" "s3_invoke_upload_handler" {
  statement_id   = "AllowS3Invoke"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.function["upload_handler"].function_name
  principal      = "s3.amazonaws.com"
  source_arn     = aws_s3_bucket.uploads.arn
  source_account = local.account_id
}

resource "aws_s3_bucket_notification" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.function["upload_handler"].arn
    events              = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_lambda_permission.s3_invoke_upload_handler]
}
