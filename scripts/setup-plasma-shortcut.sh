#!/usr/bin/env bash
# Add the KDE AI plasmoid to the first panel if it is not already present.
set -euo pipefail
qdbus="$(command -v qdbus6 || command -v qdbus || true)"
if [[ -z "${qdbus}" ]]; then
  exit 0
fi
if ! "${qdbus}" org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "var x = 1" >/dev/null 2>&1; then
  exit 0
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
