#!/usr/bin/env bash
# Sets up Box Box inside the Debian system (proot-distro) on the phone.
# Called by install.sh and `boxbox update`; safe to run again.
#
# Same stack as the Docker image: Python 3.11 (via uv) and Node 20 to build
# the frontend. Team radio captions (Whisper) are left out: too heavy here.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Wedrock/Projetos-F1.git}"
BRANCH="${BRANCH:-main}"
APP_DIR="${APP_DIR:-/root/Projetos-F1}"
DATA_DIR="${BOXBOX_DATA:-/root/boxbox-data}"
VENV="$APP_DIR/box-box/.venv"
NODE_DIR=/opt/node
SKIP_TAILSCALE="${SKIP_TAILSCALE:-}"
export DEBIAN_FRONTEND=noninteractive NEXT_TELEMETRY_DISABLED=1

say() { printf '\n\033[1;31m▶\033[0m \033[1m%s\033[0m\n' "$*"; }

case "$(uname -m)" in
  aarch64|arm64) NODE_ARCH=arm64; TS_ARCH=arm64 ;;
  x86_64) NODE_ARCH=x64; TS_ARCH=amd64 ;;
  *) echo "Processador não suportado: $(uname -m) (precisa ser 64 bits)"; exit 1 ;;
esac

say "Pacotes do sistema"
apt-get update -q
apt-get install -y -q git curl ca-certificates openssl xz-utils procps >/dev/null

say "Código do Box Box"
if [ -d "$APP_DIR/.git" ]; then
  # FETCH_HEAD works in the shallow, single-branch clone, even for a new branch
  git -C "$APP_DIR" fetch -q --depth 1 origin "$BRANCH"
  git -C "$APP_DIR" checkout -q -f -B "$BRANCH" FETCH_HEAD
else
  git clone -q --depth 1 --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi
BOX="$APP_DIR/box-box"

say "Python 3.11 e dependências do servidor"
if ! command -v uv >/dev/null && [ ! -x /root/.local/bin/uv ]; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh >/dev/null
fi
export PATH="/root/.local/bin:$PATH"
[ -x "$VENV/bin/python" ] || uv venv -q --python 3.11 "$VENV"
grep -v -i '^faster-whisper' "$BOX/backend/requirements.txt" > /tmp/boxbox-requirements.txt
uv pip install -q --python "$VENV/bin/python" -r /tmp/boxbox-requirements.txt

say "Node 20 e a interface"
if [ ! -x "$NODE_DIR/bin/node" ]; then
  file=$(curl -fsSL https://nodejs.org/dist/latest-v20.x/SHASUMS256.txt | grep -o "node-v[0-9.]*-linux-$NODE_ARCH.tar.xz" | head -1)
  mkdir -p "$NODE_DIR"
  curl -fsSL "https://nodejs.org/dist/latest-v20.x/$file" | tar -xJ -C "$NODE_DIR" --strip-components=1
fi
export PATH="$NODE_DIR/bin:$PATH"
# Rebuilt only when the frontend's code changed (its git tree hash)
tree=$(git -C "$APP_DIR" rev-parse HEAD:box-box/frontend)
if [ "$(cat "$BOX/frontend/out/.boxbox-build" 2>/dev/null)" != "$tree" ]; then
  (cd "$BOX/frontend" && npm ci --no-audit --no-fund --loglevel=error && npm run build >/dev/null)
  echo "$tree" > "$BOX/frontend/out/.boxbox-build"
else
  echo "Interface já está atualizada"
fi

say "Configuração"
if [ ! -f "$BOX/.env" ]; then
  cat > "$BOX/.env" <<EOF
# Box Box no celular. Mais opções em .env.example
DATA_DIR=$DATA_DIR
F1TV_SECRET_KEY=$(openssl rand -hex 32)
# Só o próprio celular e o endereço do Tailscale (*.ts.net) abrem o app
ALLOWED_HOSTS=localhost,127.0.0.1,*.ts.net
# Legendas do rádio em português e inglês: chave grátis em aistudio.google.com
# (ou rode no Termux: boxbox gemini SUA_CHAVE)
# GEMINI_API_KEY=
AUTO_PRECOMPUTE=race+qual
EOF
fi
# Older installs turned captions off (no Whisper here); Gemini makes them now
sed -i '/^# Legendas do rádio usam o Whisper/d; /^TEAM_RADIO_CAPTIONS=false$/d' "$BOX/.env"
mkdir -p "$DATA_DIR/fastf1-cache"
cp -n "$BOX/backend/data/pit_loss.json" "$DATA_DIR/pit_loss.json" 2>/dev/null || true

if [ -n "$SKIP_TAILSCALE" ]; then
  say "Pronto (sem Tailscale)"
  exit 0
fi

say "Tailscale"
if ! command -v tailscaled >/dev/null; then
  tarball=$(curl -fsSL "https://pkgs.tailscale.com/stable/?mode=json" | grep -o "\"$TS_ARCH\": *\"[^\"]*\"" | head -1 | sed 's/.*: *"\(.*\)"/\1/')
  curl -fsSL "https://pkgs.tailscale.com/stable/$tarball" | tar -xz -C /tmp
  mkdir -p /usr/local/lib/boxbox
  install -m 755 /tmp/tailscale_*_"$TS_ARCH"/tailscale /usr/local/lib/boxbox/tailscale
  install -m 755 /tmp/tailscale_*_"$TS_ARCH"/tailscaled /usr/local/bin/tailscaled
  rm -rf /tmp/tailscale_*_"$TS_ARCH"
fi
# The daemon's socket lives in the shared /tmp: the default path, inside
# Termux's long rootfs path, is too long for a Unix socket under proot
printf '#!/bin/sh\nexec /usr/local/lib/boxbox/tailscale --socket=/tmp/tailscaled.sock "$@"\n' > /usr/local/bin/tailscale
chmod 755 /usr/local/bin/tailscale
bash "$BOX/scripts/android/start.sh" tailscale-only

if ! tailscale status >/dev/null 2>&1; then
  echo
  echo "Abra o link abaixo e entre com a MESMA conta do Tailscale do seu iPhone:"
  # `tailscale up` can keep waiting after the login has gone through, so run
  # it in the background and go on as soon as the phone is connected
  tailscale up --hostname=boxbox >/tmp/boxbox-ts-up.log 2>&1 &
  up_pid=$!
  shown=""
  for _ in $(seq 1 900); do
    tailscale status >/dev/null 2>&1 && break
    if [ -z "$shown" ] && grep -q "https://" /tmp/boxbox-ts-up.log; then
      cat /tmp/boxbox-ts-up.log
      shown=1
    fi
    sleep 1
  done
  kill "$up_pid" 2>/dev/null || true
  if tailscale status >/dev/null 2>&1; then echo "Tailscale conectado"; else echo "O login do Tailscale não terminou; rode o instalador de novo"; fi
fi
# HTTPS at https://boxbox.<sua-rede>.ts.net, pointing at the app. Waits if
# HTTPS still has to be turned on for the tailnet (it prints the link).
if ! timeout 600 tailscale serve --bg 8000; then
  echo
  echo "Ative o HTTPS em login.tailscale.com/admin/dns (HTTPS Certificates) e rode 'boxbox update'."
fi

# proot only exits once every process in it has, so stop the daemon here;
# `boxbox start` runs it again for good
pkill -x tailscaled 2>/dev/null || true

say "Box Box instalado"
