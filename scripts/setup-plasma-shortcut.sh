#!/usr/bin/env bash
# Register KDE AI's window action with no default shortcut, restore Plasma's
# Meta+Shift+A "previous activity" binding if we previously stole it, and add
# the plasmoid to the first panel if it is missing.
set -euo pipefail

# Qt::META|SHIFT|Key_A — only used to give the chord back to plasmashell.
META_SHIFT_A=301989953

kwrite_bin() {
  command -v kwriteconfig6 || command -v kwriteconfig5 || true
}

kread_bin() {
  command -v kreadconfig6 || command -v kreadconfig5 || true
}

first_field() {
  local value="${1:-}"
  printf '%s' "${value%%,*}"
}

rest_desc() {
  local value="${1:-}" rest
  rest="${value#*,}"
  if [[ "${rest}" == "${value}" ]]; then
    printf '%s' "$2"
    return
  fi
  rest="${rest#*,}"
  if [[ -n "${rest}" ]]; then
    printf '%s' "${rest}"
  else
    printf '%s' "$2"
  fi
}

restore_plasma_previous_activity() {
  local gdbus kwrite kread prev prev_cur desc
  gdbus="$(command -v gdbus || true)"
  kwrite="$(kwrite_bin)"
  kread="$(kread_bin)"
  prev=""
  if [[ -n "${kread}" ]]; then
    prev="$("${kread}" --file kglobalshortcutsrc --group plasmashell --key "previous activity" || true)"
  fi
  prev_cur="$(first_field "${prev}")"
  # Only put Meta+Shift+A back when the action is currently unbound (the state
  # left by the old kde-ai installer). Leave a user's custom chord alone.
  if [[ -n "${prev_cur}" && "${prev_cur}" != "none" ]]; then
    return 0
  fi
  desc="$(rest_desc "${prev}" "Walk through activities (Reverse)")"
  if [[ -n "${kwrite}" ]]; then
    "${kwrite}" --file kglobalshortcutsrc --group plasmashell --key "previous activity" \
      "Meta+Shift+A,none,${desc}"
  fi
  if [[ -n "${gdbus}" ]]; then
    gdbus call --session --dest org.kde.kglobalaccel --object-path /kglobalaccel \
      --method org.kde.KGlobalAccel.setShortcut \
      "['plasmashell', 'previous activity', 'plasmashell', 'previous activity']" \
      "@ai [${META_SHIFT_A}]" 4 >/dev/null 2>&1 || true
  fi
}

register_empty_kdeai_shortcut() {
  local gdbus kwrite kread qdbus current cur
  gdbus="$(command -v gdbus || true)"
  kwrite="$(kwrite_bin)"
  kread="$(kread_bin)"
  qdbus="$(command -v qdbus6 || command -v qdbus || true)"
  current=""
  if [[ -n "${kread}" ]]; then
    current="$("${kread}" --file kglobalshortcutsrc --group org.kde.kdeai.desktop --key _launch || true)"
  fi
  cur="$(first_field "${current}")"
  # Drop the old shipped default. Any other assigned chord is a user choice.
  if [[ -z "${cur}" || "${cur}" == "none" || "${cur}" == "Meta+Shift+A" ]]; then
    if [[ -n "${kwrite}" ]]; then
      "${kwrite}" --file kglobalshortcutsrc --group org.kde.kdeai.desktop --key _k_friendly_name "KDE AI"
      "${kwrite}" --file kglobalshortcutsrc --group org.kde.kdeai.desktop --key _launch \
        "none,none,KDE AI"
    fi
    if [[ -n "${gdbus}" ]]; then
      gdbus call --session --dest org.kde.kglobalaccel --object-path /kglobalaccel \
        --method org.kde.KGlobalAccel.doRegister \
        "['org.kde.kdeai.desktop', '_launch', 'KDE AI', 'KDE AI']" >/dev/null 2>&1 || true
      gdbus call --session --dest org.kde.kglobalaccel --object-path /kglobalaccel \
        --method org.kde.KGlobalAccel.setShortcut \
        "['org.kde.kdeai.desktop', '_launch', 'KDE AI', 'KDE AI']" \
        '@ai []' 4 >/dev/null 2>&1 || true
    fi
  fi
  if [[ -n "${qdbus}" ]]; then
    "${qdbus}" org.kde.kglobalaccel /kglobalaccel org.kde.KGlobalAccel.reconfigure >/dev/null 2>&1 || true
  fi
}

add_panel_widget() {
  local qdbus
  qdbus="$(command -v qdbus6 || command -v qdbus || true)"
  if [[ -z "${qdbus}" ]]; then
    return 0
  fi
  if ! "${qdbus}" org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "var x = 1" >/dev/null 2>&1; then
    return 0
  fi
  "${qdbus}" org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript '
function walk(container, fn) {
    var widgets = container.widgets();
    for (var i = 0; i < widgets.length; i++) {
        fn(widgets[i]);
        if (widgets[i].type === "org.kde.plasma.systemtray") {
            var sid = widgets[i].readConfig("SystrayContainmentId");
            if (sid) {
                var st = desktopById(sid);
                if (st) walk(st, fn);
            }
        }
    }
}
var found = false;
var cons = desktops().concat(panels());
for (var c = 0; c < cons.length; c++) {
    walk(cons[c], function (w) {
        if (w.type === "org.kde.kdeai") found = true;
    });
}
if (!found && panels().length > 0) {
    panels()[0].addWidget("org.kde.kdeai");
}
'
}

restore_plasma_previous_activity
register_empty_kdeai_shortcut
add_panel_widget
