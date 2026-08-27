import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kquickcontrols as KQuickControls
import ".."

Item {
    id: configPage
    ExecRpc { id: rpc }

    function linesToCsv(text) {
        return (text || "").split(/\n/).map(function (s) { return s.trim() }).filter(function (s) { return s.length }).join(",")
    }

    function listToLines(arr) {
        if (!arr || !arr.length)
            return ""
        return arr.join("\n")
    }

    Flickable {
        id: flick
        anchors.fill: parent
        clip: true
        contentWidth: width
        contentHeight: col.implicitHeight
        boundsBehavior: Flickable.StopAtBounds

        ColumnLayout {
            id: col
            width: flick.width
            spacing: Kirigami.Units.largeSpacing

            QQC2.Label { text: "Agent configuration"; font.bold: true }

            Kirigami.FormLayout {
                Layout.fillWidth: true
                QQC2.Switch {
                    id: en
                    Kirigami.FormData.label: "Agent"
                    text: "Run the local agent"
                    checked: true
                    Accessible.name: "Agent enabled"
                }
                QQC2.Switch {
                    id: rag
                    Kirigami.FormData.label: "RAG"
                    text: "Search man pages and local docs"
                    checked: true
                    Accessible.name: "RAG enabled"
                }
                QQC2.Switch {
                    id: force
                    Kirigami.FormData.label: "GPU yield"
                    text: "Force run during GPU pause"
                    checked: false
                    Accessible.name: "Force run during pause"
                }
                QQC2.SpinBox {
                    id: idle
                    Kirigami.FormData.label: "Idle unload"
                    from: 5
                    to: 120
                    value: 15
                    Accessible.name: "Idle unload seconds"
                }
                KQuickControls.KeySequenceItem {
                    id: shortcut
                    Kirigami.FormData.label: "Open window"
                    showClearButton: true
                    modifierlessAllowed: false
                    Accessible.name: "Open window shortcut"
                    onKeySequenceModified: configPage.applyShortcut()
                }
            }

            QQC2.Label { text: "GPU"; font.bold: true }
            QQC2.Label {
                text: "The agent pauses while another CUDA app uses the GPU. Names here are process fragments that are allowed to share the GPU (one per line)."
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                opacity: 0.75
            }
            QQC2.Label { text: "Don't pause for" }
            QQC2.ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.gridUnit * 8
                QQC2.TextArea {
                    id: allow
                    wrapMode: TextEdit.NoWrap
                    placeholderText: "kwin\nfirefox\ndiscord"
                    Accessible.name: "GPU allow list"
                }
            }
            QQC2.Label { text: "Always pause for" }
            QQC2.Label {
                text: "Regexes matched against process command lines (one per line)."
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                opacity: 0.75
            }
            QQC2.ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.gridUnit * 6
                QQC2.TextArea {
                    id: deny
                    wrapMode: TextEdit.NoWrap
                    placeholderText: "comfy\nblender\nsteam"
                    Accessible.name: "GPU denylist"
                }
            }

            RowLayout {
                QQC2.Button { text: "Save"; Accessible.name: "Save config"; icon.name: "document-save"; onClicked: configPage.save() }
                QQC2.Button { text: "Rebuild search index"; Accessible.name: "Rebuild search index"; onClicked: rpc.rpc("doctor --reindex", function() {}) }
                Item { Layout.fillWidth: true }
            }
        }
    }

    function shortcutText() {
        const seq = shortcut.keySequence
        let text = seq ? seq.toString() : ""
        if (!text || text === "None" || text === "none")
            return ""
        // KeySequenceItem reports NativeText (French: Méta, Maj). KGlobalAccel
        // only understands PortableText (Meta, Shift).
        return text.replace(/Méta/g, "Meta").replace(/Maj/g, "Shift").replace(/Strg/g, "Ctrl").replace(/Umschalt/g, "Shift")
    }

    function applyShortcut() {
        const text = configPage.shortcutText()
        rpc.rpc(text ? ("shortcut " + text) : "shortcut clear", function() {})
    }

    function save() {
        rpc.rpc("config set daemon.enabled " + (en.checked ? "true" : "false"), function() {})
        rpc.rpc("config set rag.enabled " + (rag.checked ? "true" : "false"), function() {})
        rpc.rpc("config set daemon.idle_unload_s " + idle.value, function() {})
        if (force.checked)
            rpc.rpc("config set daemon.force_run_during_pause true", function() {})
        else
            rpc.rpc("config set daemon.force_run_during_pause false", function() {})
        rpc.rpc("config set gpu.graphics_allow " + configPage.linesToCsv(allow.text), function() {})
        rpc.rpc("config set gpu.denylist " + configPage.linesToCsv(deny.text), function() {})
        configPage.applyShortcut()
    }

    Component.onCompleted: rpc.rpc("config get", function(r) {
        if (r && r.daemon) {
            en.checked = r.daemon.enabled
            rag.checked = r.rag.enabled
            idle.value = r.daemon.idle_unload_s
            force.checked = r.daemon.force_run_during_pause
        }
        if (r && r.plasma)
            shortcut.keySequence = r.plasma.global_shortcut || ""
        if (r && r.gpu) {
            allow.text = configPage.listToLines(r.gpu.graphics_allow)
            deny.text = configPage.listToLines(r.gpu.denylist)
        }
    })
}
