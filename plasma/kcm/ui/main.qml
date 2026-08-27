import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    title: "KDE AI"
    Kirigami.FormLayout {
        QQC2.Label {
            Kirigami.FormData.isSection: true
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            text: "Local agent"
        }
        QQC2.Switch {
            Kirigami.FormData.label: "Agent"
            text: "Run the local agent"
            checked: true
            Accessible.name: "Agent enabled"
        }
        QQC2.Switch {
            Kirigami.FormData.label: "RAG"
            text: "Search man pages and local docs"
            checked: true
            Accessible.name: "RAG enabled"
        }
        QQC2.Switch {
            Kirigami.FormData.label: "GPU yield"
            text: "Force run during GPU pause (unsafe)"
            checked: false
            Accessible.name: "Force run during pause"
        }
        QQC2.SpinBox {
            Kirigami.FormData.label: "Idle unload"
            from: 5
            to: 120
            value: 15
            Accessible.name: "Idle unload seconds"
        }
        QQC2.Button { text: "Apply"; Accessible.name: "Apply config"; icon.name: "document-save" }
    }
}
