# KMS Key for DynamoDB encryption
resource "aws_kms_key" "dynamodb_encryption" {
  description             = "KMS key for DynamoDB table encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow DynamoDB Service"
        Effect = "Allow"
        Principal = {
          Service = "dynamodb.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:GenerateDataKey*"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name = "${local.name_prefix}-dynamodb-kms"
  }
}

resource "aws_kms_alias" "dynamodb_encryption" {
  name          = "alias/${local.name_prefix}-dynamodb-encryption"
  target_key_id = aws_kms_key.dynamodb_encryption.key_id
}

# Audit Trail Table
resource "aws_dynamodb_table" "audit_trail" {
  name         = "${local.name_prefix}-audit-trail"
  billing_mode = "PAY_PER_REQUEST" # On-demand for variable workloads

  hash_key  = "pk"           # Partition key: ORG#<org-id>
  range_key = "sk"           # Sort key: EVENT#<timestamp>#<event-type>

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  attribute {
    name = "file_key"
    type = "S"
  }

  attribute {
    name = "event_type"
    type = "S"
  }

  # Global Secondary Index for querying by file
  global_secondary_index {
    name            = "file-index"
    hash_key        = "file_key"
    range_key       = "sk"
    projection_type = "ALL"
  }

  # Global Secondary Index for querying by event type
  global_secondary_index {
    name            = "event-type-index"
    hash_key        = "event_type"
    range_key       = "sk"
    projection_type = "ALL"
  }

  # Server-side encryption with KMS
  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.dynamodb_encryption.arn
  }

  # Point-in-time recovery for data protection
  point_in_time_recovery {
    enabled = true
  }

  # TTL for automatic cleanup (optional, disabled by default)
  ttl {
    attribute_name = "ttl"
    enabled        = false
  }

  tags = {
    Name = "${local.name_prefix}-audit-trail"
  }
}
