# Hybrid Architecture Strategy

## Executive Summary

This document outlines the strategy for decoupling the Storage and Compute layers in our Secure Data Orchestration platform, enabling Member Organizations to run workloads on their own infrastructure while maintaining centralized orchestration.


## The Hybrid Constraint

**Requirement**: If an Organization requires data to remain on their own local S3-compatible storage and run processing on their own local server, the architecture must handle this without a total rewrite of the Backbone logic.


## Decoupling Strategy: Interface Abstraction

The core principle is **programming to interfaces, not implementations**. Our architecture defines abstract contracts that both cloud and on-premises components implement identically.

### Three Key Abstractions

![Three Key Abstractions](/Abstractions.png)


## Implementation Approach

### 1. Storage Abstraction

**Current**: AWS S3 with native SDK  
**Hybrid**: S3-compatible API (works with MinIO, Ceph, etc.)

# Configuration-driven storage endpoint
STORAGE_ENDPOINT = os.environ.get("STORAGE_ENDPOINT")  # None for AWS, URL for on-prem

s3_client = boto3.client(
    "s3",
    endpoint_url=STORAGE_ENDPOINT,  # MinIO: "http://minio.local:9000"
    # Credentials from environment or IAM
)

**No code changes required** — the boto3 SDK already supports S3-compatible endpoints via the `endpoint_url` parameter.

### 2. Event Abstraction

**Current**: S3 Event Notifications → Lambda  
**Hybrid**: Relay Agent polling or webhook-based triggers

For on-premises storage, deploy a lightweight **Relay Agent** that:
1. Polls the local S3-compatible storage for new objects
2. Sends validated events to the central orchestration layer via HTTPS webhook
3. Maintains event ordering and delivery guarantees

### 3. Compute Abstraction

**Current**: ECS Fargate (cloud-managed containers)  
**Hybrid**: Configuration-driven compute target

COMPUTE_MODE = os.environ.get("COMPUTE_MODE", "ECS")  # "ECS" | "LOCAL_DOCKER"

if COMPUTE_MODE == "ECS":
    # Trigger ECS task (current implementation)
    ecs_client.run_task(...)
elif COMPUTE_MODE == "LOCAL_DOCKER":
    # Send task to on-prem Docker host via secure API
    requests.post(f"{DOCKER_API_ENDPOINT}/tasks", json=task_payload)


## Configuration Matrix

| Deployment Mode | Storage | Events | Compute |
|-----------------|---------|--------|---------|
| **Full Cloud** | AWS S3 | S3 Notifications | ECS Fargate |
| **Hybrid Compute** | AWS S3 | S3 Notifications | Docker (on-prem) |
| **Full On-Prem** | MinIO (on-prem) | Relay Agent → Webhook | Docker (on-prem) |


## What Stays in the Cloud

Regardless of deployment mode, these components remain centralized:

- **Orchestration Logic**: Validation rules, workflow coordination
- **Audit Trail**: DynamoDB (or hybrid-compatible alternative)
- **Identity & Access**: Centralized IAM and organization management
- **Monitoring**: CloudWatch metrics and alerting

This ensures consistent governance, auditability, and security policies across all Member Organizations.


## Migration Path

1. **Phase 1** (Current): Full AWS deployment
2. **Phase 2**: Add `endpoint_url` configuration to storage calls
3. **Phase 3**: Deploy Relay Agent for on-prem event handling
4. **Phase 4**: Add compute abstraction layer
5. **Phase 5**: Per-organization configuration in metadata store


## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| S3-compatible API | Industry standard, many on-prem options (MinIO, Ceph) |
| Relay Agent pattern | Maintains firewall security (outbound-only from on-prem) |
| Environment-based config | No code changes for different deployment modes |
| Centralized audit | Compliance and governance requirements |


## Conclusion

By abstracting Storage, Events, and Compute behind configuration-driven interfaces, our architecture supports the full spectrum from cloud-native to fully on-premises deployments. **The core orchestration logic remains unchanged** — only configuration and infrastructure adapters vary per deployment mode.

This approach delivers on the "Hybrid Backbone" requirement while preserving security, auditability, and maintainability.
