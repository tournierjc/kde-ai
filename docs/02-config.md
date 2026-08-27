# Config

File: `~/.config/kde-ai/config.toml`. Missing keys use defaults in `kde_ai.config.DEFAULTS`.
Invalid file: daemon starts with defaults and sets `status.config_error`.

Invent token is **not** a config key. Clients write `~/.config/kde-ai/invent.token` mode `0600`. RPC never receives the secret.

## Defaults

```toml
[daemon]
enabled = true
force_run_during_pause = false
idle_unload_s = 15
max_sessions = 50
log_level = "info"
protocol_version = 1

[llm]
gguf = "~/.local/share/kde-ai/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"
llama_server = "llama-server"
host = "127.0.0.1"
ctx = 4096
n_gpu_layers = 99
threads = 8
temperature = 0.3
top_p = 0.9
repeat_penalty = 1.05
max_tool_rounds = 6
request_timeout_s = 120
load_timeout_s = 60

[memory]
solved_tok = 400
pins_tok = 200
summary_tok = 600
rag_tok = 800
tool_result_chars = 2000

[issue]
max_attempts = 3
enter_on_fix_flag = true
patterns = [
  "crash", "broken", "doesn't work", "does not work", "won't", "failed",
  "error", "regression", "after update", "after upgrade", "black screen", "no audio",
]

[gpu]
poll_hz = 2
resume_hold_s = 10
vram_other_mb = 2048
denylist = ["comfy", "comfyui", "blender", "steam", "llama-server", "ollama", "python.*train"]
graphics_allow = ["kwin", "plasmashell", "Xorg", "firefox", "chrome", "chromium", "discord", "openlogi"]

[rag]
enabled = true
k = 5
man_sections = ["1", "5", "7", "8"]
reindex_on_boot = true

[network]
timeout_s = 10
bugzilla_base = "https://bugs.kde.org"
invent_base = "https://invent.kde.org"
offline = false

[privilege]
frontend_default = "auto"
sudo_timestamp_ok = true

[cli]
default_session = "last"
krunner_session = "last"

[plasma]
prefix = "ai "
global_shortcut = ""
default_page = "chat"

[skills]
max_enabled_per_session = 3
prompt_tok_each = 400
enabled = ["kde-desktop", "cachyos", "bugs"]
```

## `config.set` whitelist

`daemon.enabled`, `daemon.idle_unload_s`, `daemon.log_level`, `daemon.force_run_during_pause`, `llm.gguf`, `llm.temperature`, `llm.top_p`, `gpu.denylist`, `rag.enabled`, `rag.reindex_on_boot`, `cli.default_session`, `cli.krunner_session`, `plasma.prefix`, `plasma.global_shortcut`, `plasma.default_page`, `skills.enabled`, `network.offline`, `privilege.frontend_default`.

`plasma.global_shortcut` is empty by default. The Config page applies it as soon as you capture a chord (`kde-ai shortcut Meta+Ctrl+K` / `kde-ai shortcut clear`). `config set` also accepts a bare token (not only JSON) so the plasmoid shell does not strip the quotes off a shortcut string.

Anything else → `VALIDATION`.
