# Tools

Allowlisted tools only. No model-supplied shell strings. Timeout 30 s unless noted.
Results JSON `{ok, ...}` with stdout/stderr clipped to `memory.tool_result_chars`.

| Tool | Notes |
| --- | --- |
| `system_info` | compact `summary`, GPU, monitors (EDID brand/model), `gpus[].kernel_driver` from sysfs DRM (`nvidia` vs `nouveau`), CPU, RAM, motherboard, hostname, uptime (`/proc/uptime`), `distro`, `kernel` version, `kernel_cmdline` from `/proc/cmdline` plus Limine/GRUB config, Plasma, Qt, session |
| `run_readonly_cmd` | named argv keys only (`user_systemctl_status`, `pacman_qi`, `pacman_qs`, `journal_user`, `journal_kernel`, `lspci_vga`, `echo_session`) |
| `search_bugzilla` | REST, 2 GET/s token bucket |
| `search_invent` | GitLab search, optional `invent.token` |
| `open_url` | `http:` / `https:` only, `xdg-open` |
| `kde_settings_hint` | `kcm_map.json` + optional FTS |
| `search_docs` | CPU FTS5 man/docs |
| `propose_solved` | issue mode only; else `ignored_not_issue_mode` |
| `run_privileged_cmd` | `id`, `systemctl_status_unit`, `journalctl_system_n`, `dmesg`, `nft_list_ruleset` (`nft list ruleset`; iptables-nft is a shim) |
| `pacman_mutate` | install/remove, max 10 pkgs, no `-Syu` |
| `edit_config` | `$HOME` jail, deny `.ssh` `.gnupg` `.pki` `.password-store` `*.key` `/etc` |
| `plasma_script` | `kwin_compositing`, `plasma_restart`, `notify_test` |
| `screenshot_ocr` | spectacle/grim + tesseract, CPU, 20 s |

## Privilege

Daemon emits `privilege.required` with exact argv. CLI runs `sudo argv` on a TTY.
Plasma uses `pkexec` of the same allowlisted binaries. Flatpak UI cannot; privileged tools return `PRIVILEGE_CANCELLED` asking the user to use host `kde-ai` or the native plasmoid.

Passwords never cross the socket.

## Undo

Mutating tools append JSONL before/after snapshot:

```json
{"op":"restore_file","path":"/home/u/.config/foo","blob":"attempts/…/foo.bak"}
{"op":"kwriteconfig","file":"kwinrc","group":"Compositing","key":"Enabled","old":"true"}
{"op":"pacman","action":"remove","pkgs":["foo"],"was_new":true}
{"op":"noop","reason":"read_only"}
```

Replay reverse order. Undo failure → `IRREVERSIBLE`.

## RAG

SQLite FTS5 at `~/.cache/kde-ai/docs.sqlite`. Indexer: `man` sections 1,5,7,8 and `rag.doc_globs`. Skip files > 2 MiB. GPU pause does not block reindex. Timer: `kde-ai-reindex.timer`.
