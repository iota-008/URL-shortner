#!/usr/bin/env bash
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/shortly}
COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.prod.yml}

cd "$APP_DIR"

if [ ! -f .env.production ]; then
  echo "Missing .env.production in $APP_DIR"
  echo "Create it from .env.production.example before deploying."
  exit 1
fi

docker compose -f "$COMPOSE_FILE" up -d --build

docker image prune -f

echo "Deployment completed successfully."
