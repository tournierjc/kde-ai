# Packaging

- systemd user unit `kde-ai-agent.service`, optional `kde-ai.socket`, `kde-ai-reindex.timer`
- `loginctl enable-linger` (SSH without a seat); `scripts/install.sh` documents and can enable it
- Native prefix: Python package + plasmoid + KCM + KRunner desktop + D-Bus shim + man `kde-ai(1)`
- CachyOS PKGBUILD `packaging/cachyos/PKGBUILD` (depends on `llama-cpp` for `llama-server`)
- Window shortcut unset by default (`org.kde.kdeai.desktop` → `kde-ai-toggle`; assign in Config or System Settings → Shortcuts)
- Flatpak **UI only** `packaging/flatpak/org.kde.kdeai.yml` — Kirigami app talks to the host socket via `--filesystem=xdg-run/kde-ai`. Privileged tools require host CLI or native plasmoid.
- App icon `src/kde_ai/icons/org.kde.kdeai.svg` (hicolor `org.kde.kdeai`)
- AppStream `packaging/org.kde.kdeai.metainfo.xml`
- Polkit: prefer raw `pkexec` of allowlisted binaries; optional `packaging/polkit/org.kde.kdeai.policy`

CLI if the socket is missing: `systemctl --user start kde-ai-agent.service` then retry, else spawn `kde-ai-agent`. `kde-ai status` does not start the daemon. Tray **Quit** (`kde-ai quit`) writes `$XDG_RUNTIME_DIR/kde-ai/stopped` so the plasmoid status poll cannot bring it back until **Start agent** or `kde-ai start` / a chat command.
