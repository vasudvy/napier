#!/bin/bash

# Check if .env file exists, create it if not
if [ ! -f .env ]; then
  echo "Creating .env file..."
  echo "# Gemini API Key" > .env
  
  # Prompt for Gemini API key
  read -p "Enter your Gemini API key: " gemini_api_key
  echo "GEMINI_API_KEY=$gemini_api_key" >> .env
fi

# Build and start the docker-compose services
docker-compose up --build