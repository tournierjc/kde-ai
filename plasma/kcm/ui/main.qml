import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    title: "KDE AI"
    ColumnLayout {
        QQC2.Label {
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            text: "Same keys as the plasmoid Config page. Changes go through config.get / config.set (no invent token over RPC)."
        }
        QQC2.Switch { id: en; text: "Enabled"; checked: true; Accessible.name: "Agent enabled" }
        QQC2.Switch { text: "RAG"; checked: true; Accessible.name: "RAG enabled" }
        QQC2.Switch { text: "Force run during GPU pause (unsafe)"; checked: false; Accessible.name: "Force run during pause" }
        QQC2.Label { text: "Idle unload seconds" }
        QQC2.SpinBox { from: 5; to: 120; value: 15; Accessible.name: "Idle unload seconds" }
        QQC2.Label { text: "Shortcut default: Meta+Shift+A · KRunner prefix: ai " }
        QQC2.Label { wrapMode: Text.WordWrap; Layout.fillWidth: true; text: "Linger (SSH): loginctl enable-linger $USER · GGUF: scripts/fetch-gguf.sh" }
        QQC2.Button { text: "Apply"; Accessible.name: "Apply config" }
    }
}
