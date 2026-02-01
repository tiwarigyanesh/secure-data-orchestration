"""
Validation Lambda Handler

This Lambda function is triggered by S3 object creation events.
It validates uploaded data packages and triggers containerized processing.

Workflow:
1. Receive S3 event notification
2. Validate organization-id tag exists and is authorized
3. Check basic metadata requirements (file size, extension)
4. Record validation event in audit trail
5. Trigger ECS task for processing if validation passes
"""

import json
import os
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
AUDIT_TABLE_NAME = os.environ.get("AUDIT_TABLE_NAME")
ECS_CLUSTER_ARN = os.environ.get("ECS_CLUSTER_ARN")
ECS_TASK_DEFINITION_ARN = os.environ.get("ECS_TASK_DEFINITION_ARN")
ECS_SUBNET_IDS = os.environ.get("ECS_SUBNET_IDS", "").split(",")
ECS_SECURITY_GROUP_ID = os.environ.get("ECS_SECURITY_GROUP_ID")
ALLOWED_ORGANIZATION_IDS = os.environ.get("ALLOWED_ORGANIZATION_IDS", "").split(",")
INGRESS_BUCKET_NAME = os.environ.get("INGRESS_BUCKET_NAME")
AWS_REGION_NAME = os.environ.get("AWS_REGION_NAME", "us-east-1")

# AWS clients
s3_client = boto3.client("s3", region_name=AWS_REGION_NAME)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION_NAME)
ecs_client = boto3.client("ecs", region_name=AWS_REGION_NAME)


class ValidationError(Exception):
    """Custom exception for validation failures."""
    pass


def get_iso_timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def generate_event_id() -> str:
    """Generate a unique event ID."""
    return str(uuid.uuid4())


def record_audit_event(
    organization_id: str,
    event_type: str,
    file_key: str,
    details: dict[str, Any],
    status: str = "SUCCESS"
) -> None:
    """
    Record an event in the audit trail.
    
    Args:
        organization_id: The organization identifier
        event_type: Type of event (UPLOAD, VALIDATION, PROCESSING_START, PROCESSING_COMPLETE)
        file_key: S3 key of the file being processed
        details: Additional event details
        status: Event status (SUCCESS, FAILURE)
    """
    try:
        table = dynamodb.Table(AUDIT_TABLE_NAME)
        timestamp = get_iso_timestamp()
        event_id = generate_event_id()
        
        item = {
            "pk": f"ORG#{organization_id}",
            "sk": f"EVENT#{timestamp}#{event_type}",
            "event_id": event_id,
            "event_type": event_type,
            "file_key": file_key,
            "timestamp": timestamp,
            "status": status,
            "details": details,
        }
        
        table.put_item(Item=item)
        logger.info(f"Recorded audit event: {event_type} for {file_key}")
        
    except ClientError as e:
        logger.error(f"Failed to record audit event: {e}")
        raise


def get_object_metadata(bucket: str, key: str) -> tuple[dict, dict]:
    """
    Get S3 object metadata and tags.
    
    Returns:
        Tuple of (head_object_response, tags_dict)
    """
    try:
        # Get object metadata
        head_response = s3_client.head_object(Bucket=bucket, Key=key)
        
        # Get object tags
        tags_response = s3_client.get_object_tagging(Bucket=bucket, Key=key)
        tags = {tag["Key"]: tag["Value"] for tag in tags_response.get("TagSet", [])}
        
        return head_response, tags
        
    except ClientError as e:
        logger.error(f"Failed to get object metadata: {e}")
        raise


def validate_organization_id(tags: dict, metadata: dict) -> str:
    """
    Validate that the file has a valid organization-id.
    
    The organization-id can be provided as:
    1. An S3 object tag (preferred)
    2. S3 object metadata header
    
    Args:
        tags: S3 object tags
        metadata: S3 object metadata
        
    Returns:
        The validated organization ID
        
    Raises:
        ValidationError: If organization-id is missing or invalid
    """
    # Check tags first (preferred method)
    org_id = tags.get("organization-id") or tags.get("OrganizationId")
    
    # Fall back to metadata
    if not org_id:
        org_id = metadata.get("organization-id") or metadata.get("organizationid")
    
    if not org_id:
        raise ValidationError("Missing organization-id tag or metadata")
    
    if org_id not in ALLOWED_ORGANIZATION_IDS:
        raise ValidationError(f"Invalid organization-id: {org_id}")
    
    return org_id


def validate_file_requirements(head_response: dict, key: str) -> dict:
    """
    Validate basic file requirements.
    
    Args:
        head_response: S3 head_object response
        key: S3 object key
        
    Returns:
        Dict with file metadata (size, content_type, etc.)
        
    Raises:
        ValidationError: If file doesn't meet requirements
    """
    file_size = head_response.get("ContentLength", 0)
    content_type = head_response.get("ContentType", "")
    
    # Check file extension
    if not key.lower().endswith(".zip"):
        raise ValidationError(f"Invalid file extension. Expected .zip, got: {key}")
    
    # Check file size (example: max 1GB)
    max_size = 1024 * 1024 * 1024  # 1 GB
    if file_size > max_size:
        raise ValidationError(f"File too large: {file_size} bytes (max: {max_size})")
    
    # Check minimum size (must have some content)
    if file_size == 0:
        raise ValidationError("File is empty")
    
    return {
        "file_size": file_size,
        "content_type": content_type,
        "last_modified": str(head_response.get("LastModified", "")),
    }


def trigger_processing_task(
    bucket: str,
    key: str,
    organization_id: str,
    file_metadata: dict
) -> str:
    """
    Trigger the ECS processing task.
    
    Args:
        bucket: S3 bucket name
        key: S3 object key
        organization_id: Organization identifier
        file_metadata: File metadata dict
        
    Returns:
        ECS task ARN
    """
    try:
        response = ecs_client.run_task(
            cluster=ECS_CLUSTER_ARN,
            taskDefinition=ECS_TASK_DEFINITION_ARN,
            launchType="FARGATE",
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": ECS_SUBNET_IDS,
                    "securityGroups": [ECS_SECURITY_GROUP_ID],
                    "assignPublicIp": "ENABLED"  # Required for Fargate in public subnets
                }
            },
            overrides={
                "containerOverrides": [
                    {
                        "name": "processor",
                        "environment": [
                            {"name": "S3_BUCKET", "value": bucket},
                            {"name": "S3_KEY", "value": key},
                            {"name": "ORGANIZATION_ID", "value": organization_id},
                            {"name": "FILE_SIZE", "value": str(file_metadata["file_size"])},
                        ]
                    }
                ]
            },
            tags=[
                {"key": "organization-id", "value": organization_id},
                {"key": "source-file", "value": key},
            ]
        )
        
        task_arn = response["tasks"][0]["taskArn"] if response.get("tasks") else None
        
        if not task_arn:
            failures = response.get("failures", [])
            raise Exception(f"Failed to start task: {failures}")
        
        logger.info(f"Started ECS task: {task_arn}")
        return task_arn
        
    except ClientError as e:
        logger.error(f"Failed to trigger ECS task: {e}")
        raise


def lambda_handler(event: dict, context: Any) -> dict:
    """
    Main Lambda handler for S3 event processing.
    
    Args:
        event: S3 event notification
        context: Lambda context
        
    Returns:
        Response dict with processing status
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    results = []
    
    for record in event.get("Records", []):
        # Extract S3 event details
        s3_event = record.get("s3", {})
        bucket = s3_event.get("bucket", {}).get("name")
        key = s3_event.get("object", {}).get("key")
        
        if not bucket or not key:
            logger.warning("Missing bucket or key in event record")
            continue
        
        # URL decode the key (S3 events URL-encode special characters)
        import urllib.parse
        key = urllib.parse.unquote_plus(key)
        
        logger.info(f"Processing file: s3://{bucket}/{key}")
        
        organization_id = "UNKNOWN"
        
        try:
            # Get object metadata and tags
            head_response, tags = get_object_metadata(bucket, key)
            
            # Record upload event
            record_audit_event(
                organization_id="PENDING",
                event_type="UPLOAD",
                file_key=key,
                details={
                    "bucket": bucket,
                    "size": head_response.get("ContentLength", 0),
                    "tags": tags,
                }
            )
            
            # Validate organization ID
            organization_id = validate_organization_id(tags, head_response.get("Metadata", {}))
            logger.info(f"Validated organization: {organization_id}")
            
            # Validate file requirements
            file_metadata = validate_file_requirements(head_response, key)
            logger.info(f"File validation passed: {file_metadata}")
            
            # Record successful validation
            record_audit_event(
                organization_id=organization_id,
                event_type="VALIDATION",
                file_key=key,
                details={
                    "bucket": bucket,
                    "file_metadata": file_metadata,
                    "validation": "PASSED",
                }
            )
            
            # Trigger processing task
            task_arn = trigger_processing_task(bucket, key, organization_id, file_metadata)
            
            # Record processing start
            record_audit_event(
                organization_id=organization_id,
                event_type="PROCESSING_START",
                file_key=key,
                details={
                    "task_arn": task_arn,
                    "cluster": ECS_CLUSTER_ARN,
                }
            )
            
            results.append({
                "file": key,
                "organization_id": organization_id,
                "status": "PROCESSING_STARTED",
                "task_arn": task_arn,
            })
            
        except ValidationError as e:
            logger.warning(f"Validation failed for {key}: {e}")
            
            # Record validation failure
            record_audit_event(
                organization_id=organization_id,
                event_type="VALIDATION",
                file_key=key,
                details={
                    "bucket": bucket,
                    "error": str(e),
                    "validation": "FAILED",
                },
                status="FAILURE"
            )
            
            results.append({
                "file": key,
                "status": "VALIDATION_FAILED",
                "error": str(e),
            })
            
        except Exception as e:
            logger.error(f"Error processing {key}: {e}")
            
            # Record error
            record_audit_event(
                organization_id=organization_id,
                event_type="ERROR",
                file_key=key,
                details={
                    "bucket": bucket,
                    "error": str(e),
                },
                status="FAILURE"
            )
            
            results.append({
                "file": key,
                "status": "ERROR",
                "error": str(e),
            })
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Processing complete",
            "results": results,
        })
    }
