FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install kubectl
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/arm64/kubectl" && \
    install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl && \
    rm kubectl

# Install Node.js for Slack MCP server
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy MAKDO source
COPY src ./src

# Install MAKDO dependencies (ai-six 0.14.6+ includes MCP env var fix)
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --index-url https://pypi.org/simple ai-six==0.14.6 pyyaml python-dotenv requests

# Create required directories
RUN mkdir -p /app/config /app/logs /tmp/makdo/memory /tmp/makdo/tools /tmp/makdo/mcp_tools

# Set Python to run unbuffered so logs appear immediately
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Run MAKDO main entry point
CMD ["python", "-m", "src.makdo.main"]
