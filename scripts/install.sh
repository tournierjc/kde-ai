#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PREFIX="${PREFIX:-$HOME/.local}"
if [[ "${1:-}" == "--prefix" ]]; then
  PREFIX="$2"
  shift 2 || true
fi
echo "Installing to $PREFIX"
install -d "$PREFIX/share/plasma/plasmoids/org.kde.kdeai"
cp -a "$ROOT/plasma/plasmoid/." "$PREFIX/share/plasma/plasmoids/org.kde.kdeai/"
install -d "$PREFIX/share/krunner/dbusplugins"
install -m644 "$ROOT/plasma/krunner/plasma-runner-kdeai.desktop" "$PREFIX/share/krunner/dbusplugins/"
install -d "$PREFIX/share/kpackage/kcms/kcm_kdeai" || true
cp -a "$ROOT/plasma/kcm/." "$PREFIX/share/kpackage/kcms/kcm_kdeai/" 2>/dev/null || true
install -d "$PREFIX/share/applications"
install -m644 "$ROOT/packaging/org.kde.kdeai.desktop" "$PREFIX/share/applications/org.kde.kdeai.desktop"
install -d "$HOME/.local/share/kde-ai-shipped-skills"
if [[ "$PREFIX" == "$HOME/.local" ]]; then
  cp -a "$ROOT/skills/." "$HOME/.local/share/kde-ai-shipped-skills/"
else
  install -d "$PREFIX/share/kde-ai/skills"
  cp -a "$ROOT/skills/." "$PREFIX/share/kde-ai/skills/"
fi
install -d "$HOME/.config/systemd/user"
install -m644 "$ROOT/packaging/systemd/kde-ai-agent.service" "$HOME/.config/systemd/user/"
install -m644 "$ROOT/packaging/systemd/kde-ai-reindex.timer" "$HOME/.config/systemd/user/" || true
install -m644 "$ROOT/packaging/systemd/kde-ai-reindex.service" "$HOME/.config/systemd/user/" || true
install -d "$PREFIX/share/man/man1"
install -m644 "$ROOT/packaging/man/kde-ai.1" "$PREFIX/share/man/man1/" || true
install -d "$PREFIX/share/polkit-1/actions"
install -m644 "$ROOT/packaging/polkit/org.kde.kdeai.policy" "$PREFIX/share/polkit-1/actions/" || true
pip install -e "$ROOT"
toggle_bin="$(command -v kde-ai-toggle || true)"
if [[ -n "${toggle_bin}" ]]; then
  tmp_desktop="$(mktemp)"
  sed "s|^Exec=kde-ai-toggle|Exec=${toggle_bin}|" \
    "$ROOT/packaging/org.kde.kdeai.desktop" >"${tmp_desktop}"
  install -m644 "${tmp_desktop}" "$PREFIX/share/applications/org.kde.kdeai.desktop"
  rm -f "${tmp_desktop}"
fi

if ! command -v llama-server >/dev/null 2>&1 && [[ ! -x /usr/bin/llama-server ]]; then
  echo "llama-server is required. Install: sudo pacman -S llama-cpp"
  if command -v sudo >/dev/null && sudo -n true 2>/dev/null; then
    sudo -n pacman -S --noconfirm llama-cpp || true
  fi
fi
if command -v llama-server >/dev/null 2>&1 || [[ -x /usr/bin/llama-server ]]; then
  echo "llama-server: $(command -v llama-server 2>/dev/null || echo /usr/bin/llama-server)"
else
  echo "WARNING: llama-server still missing; the plasmoid cannot answer until llama-cpp is installed."
fi

systemctl --user daemon-reload || true
systemctl --user enable --now kde-ai-agent.service 2>/dev/null || true

if command -v kbuildsycoca6 >/dev/null 2>&1; then
  kbuildsycoca6 >/dev/null 2>&1 || true
fi
bash "$ROOT/scripts/setup-plasma-shortcut.sh" || true

echo "Window shortcut is unset by default. Assign one in the Config page or System Settings → Shortcuts → KDE AI."
if [[ -t 0 ]]; then
  printf "Enable lingering so SSH can reach the user daemon? [y/N] "
  read -r ans
  if [[ "$ans" == "y" || "$ans" == "Y" ]]; then
    loginctl enable-linger "$USER"
  fi
else
  echo "Enable linger for SSH: loginctl enable-linger $USER"
fi
echo "Daemon: systemctl --user enable --now kde-ai-agent.service"
echo "Optional reindex timer: systemctl --user enable --now kde-ai-reindex.timer"
