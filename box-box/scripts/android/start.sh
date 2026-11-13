#!/usr/bin/env bash
# Runs Box Box inside the Debian system on the phone: Tailscale (userspace
# networking, so no root or VPN slot is needed) and the server, restarted if
# it ever stops. `start.sh tailscale-only` just makes sure Tailscale runs.
set -uo pipefail

APP_DIR="${APP_DIR:-/root/Projetos-F1}"
BOX="$APP_DIR/box-box"

if command -v tailscaled >/dev/null && ! pgrep -x tailscaled >/dev/null; then
  mkdir -p /var/lib/tailscale
  nohup tailscaled --tun=userspace-networking --statedir=/var/lib/tailscale \
    --socket=/tmp/tailscaled.sock >/root/tailscaled.log 2>&1 &
  for _ in $(seq 1 20); do
    [ -S /tmp/tailscaled.sock ] && break
    sleep 1
  done
fi
[ "${1:-}" = "tailscale-only" ] && exit 0

if pgrep -f "uvicorn main:app" >/dev/null; then
  echo "O Box Box já está rodando"
  exit 0
fi

set -a
# shellcheck disable=SC1091
. "$BOX/.env"
set +a
export STATIC_DIR="$BOX/frontend/out" PORT=8000

cd "$BOX/backend"
while true; do
  echo "[$(date '+%F %T')] Iniciando o Box Box"
  "$BOX/.venv/bin/uvicorn" main:app --host 127.0.0.1 --port 8000
  echo "[$(date '+%F %T')] O servidor parou; reiniciando em 5 s"
  sleep 5
done
