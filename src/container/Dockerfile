# Data Package Processor Container

FROM python:3.11-slim as base

# Security: Run as non-root user
RUN groupadd -r processor && useradd -r -g processor processor

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY processor.py .

# Change ownership to non-root user
RUN chown -R processor:processor /app

# Switch to non-root user
USER processor

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import boto3; print('healthy')" || exit 1

# Run the processor
ENTRYPOINT ["python", "processor.py"]
