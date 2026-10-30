#!/bin/bash
# EC2 user-data for Amazon Linux 2023: runs once, as root, on first boot.
# Installs Docker, adds swap (builds need more than 1-2 GB RAM), clones the repo and deploys.
# REPO_URL is substituted by the provisioning script before launch.
set -euxo pipefail
exec > >(tee -a /var/log/freereel-setup.log) 2>&1

REPO_URL="__REPO_URL__"
APP_DIR=/opt/freereel

dnf install -y docker git
systemctl enable --now docker

# Docker Compose + Buildx plugins (not packaged for AL2023).
case "$(uname -m)" in
  x86_64)  COMPOSE_ARCH=x86_64;  BUILDX_ARCH=amd64 ;;
  aarch64) COMPOSE_ARCH=aarch64; BUILDX_ARCH=arm64 ;;
esac
PLUGINS=/usr/local/lib/docker/cli-plugins
mkdir -p "$PLUGINS"
curl -fsSL "https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-${COMPOSE_ARCH}" -o "$PLUGINS/docker-compose"
curl -fsSL "https://github.com/docker/buildx/releases/download/v0.17.1/buildx-v0.17.1.linux-${BUILDX_ARCH}" -o "$PLUGINS/docker-buildx"
chmod +x "$PLUGINS/docker-compose" "$PLUGINS/docker-buildx"

# 2 GB swap so `next build` and pip installs don't run out of memory on small instances.
if [ ! -f /swapfile ]; then
  dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile swap swap defaults 0 0' >> /etc/fstab
fi

if [ ! -d "$APP_DIR/.git" ]; then
  git clone "$REPO_URL" "$APP_DIR"
fi

bash "$APP_DIR/infrastructure/aws/deploy.sh"
