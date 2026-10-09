FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user "sandbox"
RUN useradd -u 1001 -m -s /bin/sh sandbox

# Install python analysis and testing tools
RUN pip install --no-cache-dir \
    pytest \
    pytest-json-report \
    bandit \
    semgrep \
    ruff

# Setup workspace
RUN mkdir /workspace && chown sandbox:sandbox /workspace
WORKDIR /workspace

USER sandbox

ENTRYPOINT ["/bin/sh"]
