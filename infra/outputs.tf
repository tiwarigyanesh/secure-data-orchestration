# =============================================================================
# Outputs
# =============================================================================

output "ingress_bucket_name" {
  description = "Name of the S3 bucket for data ingress"
  value       = aws_s3_bucket.ingress.id
}

output "ingress_bucket_arn" {
  description = "ARN of the S3 bucket for data ingress"
  value       = aws_s3_bucket.ingress.arn
}

output "audit_table_name" {
  description = "Name of the DynamoDB audit trail table"
  value       = aws_dynamodb_table.audit_trail.name
}

output "audit_table_arn" {
  description = "ARN of the DynamoDB audit trail table"
  value       = aws_dynamodb_table.audit_trail.arn
}

output "lambda_function_name" {
  description = "Name of the validation Lambda function"
  value       = aws_lambda_function.validation.function_name
}

output "lambda_function_arn" {
  description = "ARN of the validation Lambda function"
  value       = aws_lambda_function.validation.arn
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "ecs_cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = aws_ecs_cluster.main.arn
}

output "ecr_repository_url" {
  description = "URL of the ECR repository for the processor container"
  value       = aws_ecr_repository.processor.repository_url
}

output "ecr_repository_name" {
  description = "Name of the ECR repository"
  value       = aws_ecr_repository.processor.name
}

output "kms_s3_key_arn" {
  description = "ARN of the KMS key for S3 encryption"
  value       = aws_kms_key.s3_encryption.arn
}

output "kms_dynamodb_key_arn" {
  description = "ARN of the KMS key for DynamoDB encryption"
  value       = aws_kms_key.dynamodb_encryption.arn
}


