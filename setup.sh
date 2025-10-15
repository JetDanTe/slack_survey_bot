#!/bin/bash
set -e

echo -e "Starting Slack Audit Bot setup (Ubuntu/Linux)...\n"
echo ""

# Load env vars safely (ignore comments and empty lines)
if [ -f .env ]; then
  export $(grep -v '^#' .env | grep -v '^\s*$' | xargs)
else
  echo -e "The .env file not found! Please create one.\n"
  exit 1
fi

# Check if user wants external DB
if [ -n "$EXTERNAL_POSTGRES_HOST" ]; then
  echo -e "Using external PostgreSQL: $EXTERNAL_POSTGRES_HOST:$EXTERNAL_POSTGRES_PORT \n"
  export POSTGRES_HOST=$EXTERNAL_POSTGRES_HOST
  export POSTGRES_PORT=$EXTERNAL_POSTGRES_PORT
  docker compose up -d bot
else
  echo -e "Starting local PostgreSQL with Docker...\n"
  docker compose up -d db
  sleep 5
  echo -e "Starting Slack Bot...\n"
  docker compose up -d bot
fi

echo -e "Setup complete. Use 'docker compose logs -f bot' to see bot logs.\n"
