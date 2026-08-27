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
NVIDIA GPU name and VRAM come from system_info, not from memory.
CPU, RAM, distro, hostname, motherboard, and kernel version also come from system_info.
Kernel boot parameters are kernel_cmdline (/proc/cmdline and Limine KERNEL_CMDLINE), not the kernel version string.
