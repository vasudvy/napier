#!/bin/bash
set -e

# Function to wait for the Playwright MCP service to be ready
wait_for_playwright() {
  echo "Waiting for Playwright MCP server to be ready..."
  
  # Try to connect to the Playwright service
  while ! nc -z playwright-mcp 8080; do
    echo "Playwright MCP not available yet - sleeping 2s"
    sleep 2
  done
  
  echo "Playwright MCP is up and running!"
}

# Wait for Playwright MCP service
wait_for_playwright

# Start Napier with auto-connect to Playwright
exec python cli.py