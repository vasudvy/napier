FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install essential packages and Docker client
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    lsb-release \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI (for running Docker-in-Docker)
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian \
    $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY cli.py .
COPY napier_config.json .
COPY .env .

# Create directory for Playwright MCP server
RUN mkdir -p /app/mcp-servers
COPY Dockerfile.playwright /app/mcp-servers/

# Build the Playwright MCP Docker image
RUN docker build -t mcp/playwright -f /app/mcp-servers/Dockerfile.playwright /app/mcp-servers/

# Make cli.py executable
RUN chmod +x cli.py

# Set environment variable for default server
ENV DEFAULT_MCP_SERVER=playwright

# Command to run when container starts
ENTRYPOINT ["python", "cli.py"]