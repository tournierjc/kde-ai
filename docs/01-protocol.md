# Protocol

Transport: unix stream, **NDJSON**, JSON-RPC **2.0**, UTF-8. Max line **8 MiB**.
Socket `$XDG_RUNTIME_DIR/kde-ai/kde-ai.sock` mode `0600`, directory `0700`.
Peer uid must equal daemon uid (`SO_PEERCRED`). Protocol version **1**; mismatch → `PROTOCOL`.

## Handshake (required first)

```json
{"jsonrpc":"2.0","id":1,"method":"hello","params":{
  "protocol_version":1,
  "client":"cli",
  "auth_frontend":"tty",
  "pid":1234,
  "locale":"en_US.UTF-8"
}}
```

`client` is one of `cli|plasmoid|krunner|kcm|flatpak-ui`.
`auth_frontend` is `tty|polkit|none`.
Result: `{ok, daemon_version, status}`.

## Methods

| Method | Params | Result |
| --- | --- | --- |
| `hello` | above | `{ok, daemon_version, status}` |
| `status.get` | — | status object |
| `status.set_enabled` | `{enabled}` | status |
| `chat.send` | `{session_id, message, issue_hint?}` | `{stream_id}` |
| `chat.cancel` | `{stream_id}` | `{ok}` |
| `session.create` | `{title?}` | `{session_id}` |
| `session.list` | `{include_archived?}` | `[{...}]` |
| `session.rename` | `{session_id, title}` | `{ok}` |
| `session.delete` | `{session_id}` | `{ok}` |
| `session.archive` | `{session_id, archived}` | `{ok}` |
| `session.transcript` | `{session_id, limit, offset}` | `{messages, total}` |
| `session.set_active` | `{session_id}` | `{ok}` |
| `session.export` | `{session_id, path?}` | `{path}` |
| `session.bug_report` | `{session_id}` | `{markdown}` |
| `memory.clear` | `{session_id, scope}` | `{ok}` |
| `memory.summarize` | `{session_id}` | `{ok}` |
| `memory.pin` | `{session_id, text}` | `{pin_id}` |
| `memory.unpin` | `{session_id, pin_id}` | `{ok}` |
| `memory.pins` | `{session_id}` | `[{id,text}]` |
| `memory.solved` | `{session_id}` | `[{id,issue,solution,ts}]` |
| `memory.forget_solved` | `{session_id, solved_id}` | `{ok}` |
| `memory.stats` | `{session_id}` | token stats |
| `config.get` | — | redacted config (no tokens) |
| `config.set` | `{patch}` | `{ok}` whitelist keys only |
| `skills.list` | `{session_id?}` | skill rows |
| `skills.set_enabled` | `{id, enabled, session_id?}` | `{ok}` |
| `skills.get` | `{id}` | `{frontmatter, body}` |
| `skills.install` | `{path}` | `{id}` |
| `skills.remove` | `{id}` | `{ok}` user skills only |
| `issue.confirm` | `{session_id, attempt_id, solved, note?}` | `{ok, next}` |
| `issue.cancel` | `{session_id}` | `{ok}` |
| `tools.list` | — | tool schemas |
| `privilege.complete` | `{request_id, ok, cancelled, stdout, stderr, code}` | `{ok}` |
| `rag.reindex` | `{force?}` | `{docs_indexed}` |
| `doctor` | — | diagnostics |

## Notifications (no `id`)

- `stream.token` `{stream_id, text}`
- `stream.tool` `{stream_id, name, arguments, result_preview?}`
- `stream.done` `{stream_id, reason: complete|cancel|error|paused, error?}`
- `privilege.required` `{request_id, session_id, argv, reason}`
- `issue.awaiting` `{session_id, attempt_id, issue_summary, solution_summary}`
- `status.changed` `{...status}`
- `config.changed` `{patch_keys}`
- `skills.changed` `{id, enabled}`

## Status

`state`: `ready | loading | answering | awaiting_confirm | awaiting_privilege | paused | idle_unloaded | disabled | busy`

Also: `vram_mb`, `reason`, `active_session_id`, `stream_id`, `gpu_blocker_pid`, `config_error`.

## Errors

`PROTOCOL`, `UNAUTHORIZED`, `NOT_FOUND`, `BUSY`, `PAUSED`, `DISABLED`, `VALIDATION`, `TOOL_DENIED`, `PRIVILEGE_CANCELLED`, `PRIVILEGE_TIMEOUT`, `LLM_ERROR`, `TIMEOUT`, `NETWORK`, `OVERFLOW`, `IRREVERSIBLE`, `FS`, `INTERNAL`.

## Concurrency and privilege

At most one `chat.send` stream. A second `chat.send` → `BUSY` with `active_session_id`. CRUD/status always allowed.

When `awaiting_confirm`, further `chat.send` on that session is `VALIDATION` until `issue.confirm` / `issue.cancel`.

Privilege: tool pauses → `privilege.required` → client has **120 s** to `privilege.complete` → else `PRIVILEGE_TIMEOUT`. stdout/stderr truncated. Passwords never in those fields.

D-Bus shim: service `org.kde.kdeai`, path `/Agent`, interface `org.kde.kdeai.Agent`. Each method maps to JSON-RPC. KRunner uses `/runner`.
