---
id: kde-desktop
name: KDE desktop
description: Plasma, KWin, System Settings paths
tools:
  - system_info
  - kde_settings_hint
  - search_docs
  - plasma_script
  - screenshot_ocr
  - propose_solved
enabled_default: true
---
Where a setting lives: kde_settings_hint, then the kcm id and `systemsettings` command. Do not invent module names.

Visual or hard-to-describe panel/display glitches: screenshot_ocr, then the matching KCM or compositor.

plasmashell stuck or missing: plasma_script `plasma_restart` (not undone). Toggle compositor: plasma_script `kwin_compositing`.
