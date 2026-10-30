# ── Feature: DynamoDB ────────────────────────────────────────────────────────
# Single table, pay-per-request.

resource "aws_dynamodb_table" "bot_table" {
  name         = "${var.app_name}-data-${var.deployment_env}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK" # "SERVER#<server_id>" — every record for one Discord server
  range_key    = "SK" # Record kind + id, e.g. "NOTE#<name>"

  # Only key attributes (and GSI keys) are declared; every other attribute is
  # schemaless and written by the bot as needed.
  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  # Expire short-lived records automatically: set expires_at (epoch seconds) on
  # an item. Items without it are unaffected.
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  # Add a global_secondary_index here when you need to look records up by
  # something other than PK/SK (Adomi's EventNameIndex is a worked example).
}

resource "aws_iam_role_policy" "lambda_dynamodb_policy" {
  name = "LambdaDynamoDBPolicy-${var.app_name}-${var.deployment_env}"
  role = aws_iam_role.lambda_exec_role.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid    = "DynamoDBCrudAccess",
        Effect = "Allow",
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem",
          "dynamodb:DescribeTable"
        ],
        Resource = [
          aws_dynamodb_table.bot_table.arn,
          "${aws_dynamodb_table.bot_table.arn}/index/*"
        ]
      }
    ]
  })
}

# [feature:deferred_worker]
# Deferred worker's table access.
resource "aws_iam_role_policy" "deferred_worker_dynamodb_policy" {
  name = "LambdaDynamoDBPolicy-${local.deferred_worker_name}-${var.deployment_env}"
  role = aws_iam_role.deferred_worker_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDBAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query"
        ]
        Resource = [
          aws_dynamodb_table.bot_table.arn,
          "${aws_dynamodb_table.bot_table.arn}/index/*"
        ]
      }
    ]
  })
}
# [/feature:deferred_worker]
