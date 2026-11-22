# On-demand billing: nothing is charged while the tables sit idle.

resource "aws_dynamodb_table" "documents" {
  name         = "${local.name_prefix}-documents"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "document_id"

  attribute {
    name = "document_id"
    type = "S"
  }
}

resource "aws_dynamodb_table" "folders" {
  name         = "${local.name_prefix}-folders"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "folder_name"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "folder_name"
    type = "S"
  }
}

resource "aws_dynamodb_table" "shares" {
  name         = "${local.name_prefix}-shares"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "share_id"

  attribute {
    name = "share_id"
    type = "S"
  }
}
