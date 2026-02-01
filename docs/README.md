# Secure Data Orchestration & Hybrid Relay

A multi-tenant platform prototype for secure data package processing with full audit trail capabilities. This implementation follows the "Hybrid Backbone" architecture pattern, enabling future migration to on-premises storage and compute resources.

## Architecture Overview

![Architecture Overview](/docs/Architecture_Overview.png)


## Project Structure

```
secure-data-orchestration/
├── infra/                    # Terraform Infrastructure as Code
│   ├── main.tf               # Main configuration & providers
│   ├── variables.tf          # Input variables
│   ├── outputs.tf            # Output values
│   ├── storage.tf            # S3 bucket & encryption
│   ├── database.tf           # DynamoDB audit table
│   ├── iam.tf                # IAM roles (least privilege)
│   ├── lambda.tf             # Lambda function
│   └── compute.tf            # ECS/Fargate cluster
├── src/
│   ├── lambda/               # Serverless validation trigger
│   │   └── handler.py        # Lambda function code
│   └── container/            # Processing container
│       ├── Dockerfile        # Container image definition
│       ├── processor.py      # Processing logic
│       └── requirements.txt  # Python dependencies
└── docs/
    ├── README.md             # This file
    └── HYBRID_STRATEGY.md    # Hybrid architecture strategy
```

## Prerequisites

- **AWS Account** with appropriate permissions
- **AWS CLI** v2 configured with credentials
- **Terraform** >= 1.0.0
- **Docker** for building container images
- **Python** 3.11+ (for local testing)

## Deployment Guide

### Step 1: Initialize Terraform

```bash
cd infra
terraform init
```

### Step 2: Review the Deployment Plan
```bash
terraform plan -var="environment=dev"
```
### Step 3: Deploy Infrastructure
```bash
terraform apply -var="environment=dev"
```
   Save the outputs for the next steps:

```bash
   terraform output -json > ../outputs.json
```
### Step 4: Build and Push the Container Image

# Get ECR repository URL from Terraform output
```bash
ECR_URL=$(terraform output -raw ecr_repository_url)
AWS_REGION=$(terraform output -raw aws_region 2>/dev/null || echo "us-east-1")

# Authenticate Docker to ECR
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $ECR_URL

# Build and push the image
cd ../src/container
docker build -t processor:latest .
docker tag processor:latest $ECR_URL:latest
docker push $ECR_URL:latest
```

### Step 5: Update Lambda (if code changes)

After any Lambda code changes:
```bash
cd infra
terraform apply -var="environment=dev"
```
## Security Features

### Encryption at Rest
- **S3**: Server-side encryption with customer-managed KMS keys
- **DynamoDB**: Server-side encryption with customer-managed KMS keys
- **ECR**: AES-256 encryption for container images

### Least Privilege Access
- **Lambda Role**: Read-only S3 access, write-only DynamoDB access, run-task ECS permission
- **ECS Task Role**: Read-only S3 access, write-only DynamoDB access
- **ECS Execution Role**: Pull-only ECR access, write-only CloudWatch Logs

### Network Security
- S3 bucket blocks all public access
- HTTPS-only access enforced via bucket policy
- ECS tasks run in VPC with security groups

### Data Protection
- S3 versioning enabled
- DynamoDB point-in-time recovery enabled
- CloudWatch log retention policies

## Configuration

### Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `aws_region` | AWS region | `eu-north-1` |
| `environment` | Environment name | `dev` |
| `allowed_organization_ids` | Valid org IDs | `["org-001", "org-002", "org-003"]` |
| `lambda_memory_size` | Lambda memory (MB) | `256` |
| `lambda_timeout` | Lambda timeout (sec) | `60` |
| `container_cpu` | ECS task CPU | `256` |
| `container_memory` | ECS task memory (MB) | `512` |

### Adding New Organizations

Update `terraform.tfvars`:

allowed_organization_ids = ["org-001", "org-002", "org-003", "org-new"]

Then apply:
```bash
terraform apply
```
## Cleanup

To destroy all resources:
```bash
cd infra

# Empty the S3 bucket first
BUCKET_NAME=$(terraform output -raw ingress_bucket_name)
aws s3 rm s3://$BUCKET_NAME --recursive

# Destroy infrastructure
terraform destroy -var="environment=dev"
```