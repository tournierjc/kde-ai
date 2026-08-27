import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import ".."

Item {
    ExecRpc { id: rpc }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Kirigami.Units.smallSpacing
        QQC2.Label { text: "Agent configuration"; font.bold: true }
        QQC2.Switch { id: en; text: "Enabled"; checked: true; Accessible.name: "Agent enabled" }
        QQC2.Switch { id: rag; text: "RAG"; checked: true; Accessible.name: "RAG enabled" }
        QQC2.Switch { id: force; text: "Force run during GPU pause"; checked: false; Accessible.name: "Force run during pause" }
        QQC2.Label { text: "Idle unload (s)" }
        QQC2.SpinBox { id: idle; from: 5; to: 120; value: 15; Accessible.name: "Idle unload seconds" }
        QQC2.Label { text: "KRunner prefix / shortcut Meta+Shift+A / default page chat" }
        QQC2.Label {
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            text: "Invent token: pick a file in the client and copy to ~/.config/kde-ai/invent.token (0600). Never sent over RPC. Fetch GGUF: scripts/fetch-gguf.sh"
        }
        RowLayout {
            QQC2.Button { text: "Save"; Accessible.name: "Save config"; onClicked: save() }
            QQC2.Button { text: "Reindex RAG"; Accessible.name: "Reindex"; onClicked: rpc.rpc("doctor --reindex", function(r){}) }
            QQC2.Button { text: "Open System Settings KCM"; Accessible.name: "Open KCM"; onClicked: rpc.rpc("status", function(){}) }
        }
        QQC2.Label { id: linger; wrapMode: Text.WordWrap; Layout.fillWidth: true; text: "Linger: see kde-ai doctor" }
    }
    function save() {
        rpc.rpc("config set daemon.enabled " + (en.checked ? "true" : "false"), function(){})
        rpc.rpc("config set rag.enabled " + (rag.checked ? "true" : "false"), function(){})
        rpc.rpc("config set daemon.idle_unload_s " + idle.value, function(){})
        if (force.checked)
            rpc.rpc("config set daemon.force_run_during_pause true", function(){})
    }
    Component.onCompleted: rpc.rpc("config get", function(r) {
        if (r && r.daemon) {
            en.checked = r.daemon.enabled
            rag.checked = r.rag.enabled
            idle.value = r.daemon.idle_unload_s
            force.checked = r.daemon.force_run_during_pause
        }
    })
}
