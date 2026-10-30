#!/bin/bash
# Pull the latest code and (re)build the stack. Safe to run repeatedly.
#   sudo bash /opt/freereel/infrastructure/aws/deploy.sh                       # redeploy
#   sudo bash /opt/freereel/infrastructure/aws/deploy.sh https://dxxxx.cloudfront.net   # also set the site URL
set -euo pipefail

APP_DIR=/opt/freereel
cd "$APP_DIR/infrastructure/aws"
ENV_FILE=.env.prod
COMPOSE=(docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE")

git -C "$APP_DIR" pull --ff-only || echo "git pull failed; deploying the current checkout"

# Secrets are generated here on the server, once, and never leave it.
if [ ! -f "$ENV_FILE" ]; then
  umask 077
  cat > "$ENV_FILE" <<EOF
POSTGRES_PASSWORD=$(openssl rand -hex 24)
SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n/+=')
SITE_URL=http://localhost
EOF
fi

if [ "${1:-}" != "" ]; then
  sed -i "s|^SITE_URL=.*|SITE_URL=${1%/}|" "$ENV_FILE"
fi

"${COMPOSE[@]}" up -d --build --remove-orphans

echo "Waiting for the API to become healthy..."
for _ in $(seq 1 60); do
  if "${COMPOSE[@]}" exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" 2>/dev/null; then
    break
  fi
  sleep 5
done

# First deploy only: demo catalogue + an admin account with a random password.
CRED_FILE=/root/freereel-admin-password.txt
if [ ! -f "$CRED_FILE" ]; then
  "${COMPOSE[@]}" exec -T api python -m app.cli seed
  ADMIN_PASSWORD=$(openssl rand -base64 18 | tr -d '\n/+=')
  "${COMPOSE[@]}" exec -T -e ADMIN_PASSWORD="$ADMIN_PASSWORD" api python -m app.cli create-admin --username admin
  umask 077
  echo "$ADMIN_PASSWORD" > "$CRED_FILE"
fi

docker image prune -f >/dev/null
"${COMPOSE[@]}" ps
echo "Deploy finished."
