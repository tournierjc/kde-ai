---
id: cachyos
name: CachyOS
description: pacman, kernels, NVIDIA on CachyOS
tools:
  - system_info
  - run_readonly_cmd
  - pacman_mutate
  - search_docs
  - run_privileged_cmd
  - propose_solved
enabled_default: true
---
CachyOS is Arch. Resolve package and kernel names (`linux-cachyos*`, NVIDIA packages) with pacman_qi / pacman_qs before mutating.

Install or remove with pacman_mutate only after a query. Never a full -Syu (the tool refuses it).

NVIDIA or kernel regressions: installed package versions plus journal_kernel. Default bootloader is Limine.

Live firewall, system journals, and dmesg need privileged tools after you authenticate. Do not invent nft/iptables rules.
