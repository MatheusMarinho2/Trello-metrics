#!/bin/sh
set -e

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Arquivo .env nao encontrado. Copie .env.example para .env e configure."
  exit 1
fi

docker compose build
docker compose up -d
docker compose ps

echo ""
echo "App disponivel em http://localhost:${APP_PORT:-8080}"
