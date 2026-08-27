# Never

These are hard product locks. Implementation and skills must not regress them.

- Privileged actions without TTY sudo **or** session polkit
- Passwords in transcripts, logs, journal, RPC, GGUF prompts, or RAG index
- Shared root daemon / cross-uid sessions
- Second always-resident GPU model (embedder, teacher, etc.) on the desktop
- Unrestricted shell (`sh -c` with model-supplied string)
- Editing `~/.ssh`, `~/.gnupg`, `~/.pki`, `/etc/sudoers*`
- Force-push, `--no-verify`, or skipping polkit “for convenience”
- User skills that add privileged argv or disable allowlists (skills may only **subset** existing tools)
