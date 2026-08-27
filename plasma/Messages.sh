#!/bin/sh
# Extract strings from plasmoid/kcm QML for l10n. Model/skill English bodies are not translated in MVP.
$XGETTEXT `find plasma -name '*.qml' -o -name '*.cpp'` -o $podir/kde-ai.pot
