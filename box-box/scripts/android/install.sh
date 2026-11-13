#!/data/data/com.termux/files/usr/bin/bash
# Box Box on an Android phone, run from Termux (no root needed).
#
# Installs a Debian system inside Termux (proot-distro), sets up Box Box and
# Tailscale in it, makes it start when the phone boots (Termux:Boot) and adds
# the `boxbox` command. Run it again any time: it only redoes what's missing.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Wedrock/Projetos-F1.git}"
BRANCH="${BRANCH:-main}"
DISTRO=debian
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

say() { printf '\n\033[1;31m▶\033[0m \033[1m%s\033[0m\n' "$*"; }

say "Instalando os pacotes do Termux"
pkg update -y
pkg install -y proot-distro termux-tools

# Where proot-distro keeps the system changes between versions, so ask it
if ! proot-distro login "$DISTRO" -- true >/dev/null 2>&1; then
  say "Instalando o Debian dentro do Termux (só na primeira vez)"
  proot-distro install "$DISTRO"
fi

say "Instalando o Box Box e o Tailscale no Debian (demora uns 10 a 20 minutos na primeira vez)"
# Termux's tmp is the Debian's /tmp with --shared-tmp
cp "$HERE/setup-debian.sh" "$PREFIX/tmp/boxbox-setup.sh"
proot-distro login --shared-tmp "$DISTRO" -- env REPO_URL="$REPO_URL" BRANCH="$BRANCH" bash /tmp/boxbox-setup.sh

say "Configurando para iniciar junto com o celular"
mkdir -p "$HOME/.termux/boot"
cat > "$HOME/.termux/boot/boxbox.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
# Started by Termux:Boot when the phone turns on
termux-wake-lock
boxbox start
EOF
chmod +x "$HOME/.termux/boot/boxbox.sh"

cp "$HERE/boxbox" "$PREFIX/bin/boxbox"
chmod +x "$PREFIX/bin/boxbox"

say "Iniciando o Box Box"
boxbox start
sleep 3
boxbox address || true

cat <<'EOF'

Pronto! Comandos úteis no Termux:
  boxbox status     está rodando?
  boxbox address    endereço para abrir no iPhone
  boxbox logs       últimas linhas do registro
  boxbox restart    reinicia
  boxbox update     baixa a versão nova e reinicia

Não esqueça (veja o guia): instalar o app Termux:Boot e abrir uma vez,
e tirar o Termux da otimização de bateria.
EOF
