#!/usr/bin/env bash
# Запуск на VPS под root после: scp iikuznitsa-index.zip -> /tmp/
set -euo pipefail

INDEX_ZIP="${INDEX_ZIP:-/tmp/iikuznitsa-index.zip}"
APP_ROOT="${APP_ROOT:-/opt/iikuznitsa/iikuznitsa-digital-mechanic}"

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y git unzip
if ! command -v docker >/dev/null; then
  DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io
fi
systemctl enable --now docker

mkdir -p /opt/iikuznitsa
cd /opt/iikuznitsa
if [ ! -d iikuznitsa-digital-mechanic/.git ]; then
  git clone https://github.com/Edwards359/iikuznitsa-digital-mechanic.git
fi
cd "$APP_ROOT"

mkdir -p data/index data/manuals
if [ ! -f "$INDEX_ZIP" ]; then
  echo "Нет $INDEX_ZIP — сначала scp с ПК: iikuznitsa-index.zip -> /tmp/"
  exit 1
fi
unzip -o "$INDEX_ZIP" -d data/index
ls -la data/index/

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Создан .env — добавьте ANTHROPIC_API_KEY и ANTHROPIC_MODEL=claude-sonnet-5-5, затем снова: docker compose up"
  exit 0
fi

if ! grep -qE '^ANTHROPIC_API_KEY=.+' .env; then
  echo "В .env пустой ANTHROPIC_API_KEY"
  exit 1
fi

docker compose up --build -d
docker compose ps
curl -s http://127.0.0.1:8080/api/health
echo