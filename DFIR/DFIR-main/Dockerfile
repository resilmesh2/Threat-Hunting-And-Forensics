FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements if exists, otherwise install CAI framework
COPY requirements.txt* ./
RUN if [ -f requirements.txt ]; then \
        pip install --no-cache-dir -r requirements.txt; \
    else \
        echo "⚠️  No requirements.txt found. Install CAI framework manually."; \
    fi

# Install CAI framework and dependencies
# Note: CAI framework should be installed via pip or mounted as volume
RUN pip install --no-cache-dir \
    openai \
    python-dotenv \
    aiofiles \
    pyyaml

# Copy application files
COPY . /app/

# Create necessary directories
RUN mkdir -p /app/logs /app/dfir_reports /app/test_data

# Make start_frontend.sh executable
RUN chmod +x /app/start_frontend.sh 2>/dev/null || true

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Copy entrypoint script
# COPY docker-entrypoint.sh /usr/local/bin/
# RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Use entrypoint script
# ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

