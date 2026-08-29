# QA matrix

Manual acceptance list. Automated smoke: `pytest` and `scripts/e2e_smoke.sh`.

- [ ] `kde-ai chat` with no DISPLAY (SSH + linger)
- [ ] Two sessions isolated across daemon restart
- [ ] `--fix` Yes writes `solved.jsonl`; No undoes `edit_config`; 4th attempt blocked
- [ ] Informational chat never shows solve card
- [ ] sudo/pkexec for `id`; password not in journal/jsonl/socket capture
- [ ] Flatpak UI chats; privileged tools tell user to use host CLI/plasmoid
- [ ] `search_docs` hits a real manpage; reindex during `paused`
- [ ] CUDA compute denylist pauses; Firefox and `gpu.graphics_allow` apps do not; idle VRAM 0 after 15s
- [ ] KCM + KRunner (`ai ` / `kdeai `) + optional window shortcut (unset by default)
- [ ] Memory page: pin/unpin/forget-solved/summarize/export
- [ ] Skills page: toggle shipped, install/remove a user skill, max 3
- [ ] Config page persists via `config.set` and matches KCM
- [ ] Gold coverage tests green
- [ ] `data/out/train.jsonl` = 30000, `eval.jsonl` = 500, `dpo.jsonl` = 500; SHA256SUMS
- [ ] SFT on `train.jsonl`; holdout metrics file stored with GGUF
- [ ] PKGBUILD / Flatpak manifest install on CachyOS
