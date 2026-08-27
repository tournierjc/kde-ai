---
id: cachyos
name: CachyOS
description: pacman, kernels, NVIDIA on CachyOS
tools:
  - system_info
  - run_readonly_cmd
  - pacman_mutate
  - search_docs
  - propose_solved
enabled_default: true
---
CachyOS is Arch-based. Prefer pacman queries before mutating packages.
Never run a full -Syu via tools. Cite actual package names from tools.
