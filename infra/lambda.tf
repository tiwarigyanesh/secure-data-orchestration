# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda_validation" {
  name              = "/aws/lambda/${local.name_prefix}-validation"
  retention_in_days = 30

  tags = {
    Name = "${local.name_prefix}-lambda-validation-logs"
  }
}

# Lambda function deployment package
data "archive_file" "lambda_validation" {
  type        = "zip"
  source_dir  = "${path.module}/../src/lambda"
  output_path = "${path.module}/lambda_validation.zip"
}

# Lambda function
resource "aws_lambda_function" "validation" {
  function_name    = "${local.name_prefix}-validation"
  filename         = data.archive_file.lambda_validation.output_path
  source_code_hash = data.archive_file.lambda_validation.output_base64sha256
  handler          = "handler.lambda_handler"
  runtime          = "python3.11"
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory_size
  role             = aws_iam_role.lambda_validation.arn

  environment {
    variables = {
      AUDIT_TABLE_NAME         = aws_dynamodb_table.audit_trail.name
      ECS_CLUSTER_ARN          = aws_ecs_cluster.main.arn
      ECS_TASK_DEFINITION_ARN  = aws_ecs_task_definition.processor.arn
      ECS_SUBNET_IDS           = join(",", data.aws_subnets.default.ids)
      ECS_SECURITY_GROUP_ID    = aws_security_group.ecs_tasks.id
      ALLOWED_ORGANIZATION_IDS = join(",", var.allowed_organization_ids)
      INGRESS_BUCKET_NAME      = aws_s3_bucket.ingress.id
      AWS_REGION_NAME          = data.aws_region.current.name
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda_validation,
    aws_iam_role_policy.lambda_logging
  ]

  tags = {
    Name = "${local.name_prefix}-validation"
  }
}

# Permission for S3 to invoke Lambda
resource "aws_lambda_permission" "s3_invoke" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.validation.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.ingress.arn
  source_account = data.aws_caller_identity.current.account_id
}
