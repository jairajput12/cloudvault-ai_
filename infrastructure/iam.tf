# One execution role shared by every function, as the app was built. Each
# statement is scoped to the resources this stack creates.

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.name_prefix}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "lambda_access" {
  statement {
    sid = "Tables"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:Scan",
    ]
    resources = [
      aws_dynamodb_table.documents.arn,
      aws_dynamodb_table.folders.arn,
      aws_dynamodb_table.shares.arn,
    ]
  }

  statement {
    sid       = "UploadsObjects"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.uploads.arn}/*"]
  }

  statement {
    sid       = "InvokeModel"
    actions   = ["bedrock:InvokeModel"]
    resources = ["arn:aws:bedrock:${local.region}::foundation-model/${var.bedrock_model_id}"]
  }

  # Textract has no resource-level permissions for this action.
  statement {
    sid       = "ReadPdfText"
    actions   = ["textract:DetectDocumentText"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "lambda_access" {
  name   = "access"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda_access.json
}
