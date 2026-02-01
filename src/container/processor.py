#!/usr/bin/env python3
"""
Data Package Processor
This container processes data packages uploaded to S3.

"""

import os
import sys
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Environment variables (passed from ECS task)
S3_BUCKET = os.environ.get("S3_BUCKET")
S3_KEY = os.environ.get("S3_KEY")
ORGANIZATION_ID = os.environ.get("ORGANIZATION_ID")
FILE_SIZE = os.environ.get("FILE_SIZE", "0")
AUDIT_TABLE_NAME = os.environ.get("AUDIT_TABLE_NAME")
AWS_REGION_NAME = os.environ.get("AWS_REGION_NAME", "us-east-1")

# AWS clients
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION_NAME)
s3_client = boto3.client("s3", region_name=AWS_REGION_NAME)


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
        event_type: Type of event
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


def process_data_package() -> None:
    """
    Main processing function.    
    """
 
    logger.info("DATA PACKAGE PROCESSOR - STARTING")
    
    # Log configuration
    logger.info(f"S3 Bucket: {S3_BUCKET}")
    logger.info(f"S3 Key: {S3_KEY}")
    logger.info(f"Organization ID: {ORGANIZATION_ID}")
    logger.info(f"File Size: {FILE_SIZE} bytes")
    logger.info(f"Audit Table: {AUDIT_TABLE_NAME}")   
    
    # Validate required environment variables
    if not all([S3_BUCKET, S3_KEY, ORGANIZATION_ID, AUDIT_TABLE_NAME]):
        logger.error("Missing required environment variables")
        record_audit_event(
            organization_id=ORGANIZATION_ID or "UNKNOWN",
            event_type="PROCESSING_ERROR",
            file_key=S3_KEY or "UNKNOWN",
            details={"error": "Missing required environment variables"},
            status="FAILURE"
        )
        sys.exit(1)
    
    try:
        # Record processing in progress
        logger.info("Recording processing start in audit trail...")
        record_audit_event(
            organization_id=ORGANIZATION_ID,
            event_type="PROCESSING_IN_PROGRESS",
            file_key=S3_KEY,
            details={
                "bucket": S3_BUCKET,
                "file_size": FILE_SIZE,
                "status": "Processing data package",
            }
        )
        
        # PROTOTYPE PROCESSING LOGIC
                
        logger.info("PROCESSING DATA PACKAGE")
        logger.info(f"  File Name: {S3_KEY}")
        logger.info(f"  File Size: {FILE_SIZE} bytes")
        logger.info(f"  Organization: {ORGANIZATION_ID}")
        
        # Verify we can access the file
        try:
            head_response = s3_client.head_object(Bucket=S3_BUCKET, Key=S3_KEY)
            actual_size = head_response.get("ContentLength", 0)
            logger.info(f"Verified file access. Actual size: {actual_size} bytes")
        except ClientError as e:
            logger.warning(f"Could not verify file access: {e}")
        
        # Simulate processing time
        import time
        logger.info("Simulating processing... (2 seconds)")
        time.sleep(2)
        
        # Processing complete
        logger.info("Processing completed successfully!")
               
        # END PROTOTYPE PROCESSING LOGIC
            
        # Record successful completion
        record_audit_event(
            organization_id=ORGANIZATION_ID,
            event_type="PROCESSING_COMPLETE",
            file_key=S3_KEY,
            details={
                "bucket": S3_BUCKET,
                "file_size": FILE_SIZE,
                "result": "SUCCESS",
                "message": "Data package processed successfully",
            }
        )
        
        logger.info("DATA PACKAGE PROCESSOR - COMPLETED SUCCESSFULLY")
        
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        
        # Record failure
        record_audit_event(
            organization_id=ORGANIZATION_ID,
            event_type="PROCESSING_COMPLETE",
            file_key=S3_KEY,
            details={
                "bucket": S3_BUCKET,
                "file_size": FILE_SIZE,
                "result": "FAILURE",
                "error": str(e),
            },
            status="FAILURE"
        )
        
        logger.info("DATA PACKAGE PROCESSOR - FAILED")
        
        sys.exit(1)


if __name__ == "__main__":
    process_data_package()
