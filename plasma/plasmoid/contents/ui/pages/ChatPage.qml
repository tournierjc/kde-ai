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
        QQC2.Label {
            text: "Sessions talk to kde-ai over JSON-RPC. Privilege uses pkexec on the host, never the Flatpak sandbox."
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        QQC2.ComboBox {
            id: sessions
            Layout.fillWidth: true
            Accessible.name: "Session list"
            model: ["(load sessions)"]
        }
        QQC2.TextArea {
            id: log
            Layout.fillWidth: true
            Layout.fillHeight: true
            readOnly: true
            Accessible.name: "Chat transcript"
            wrapMode: TextEdit.Wrap
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: false
            id: solveCard
            type: Kirigami.MessageType.Information
            text: "Is the problem solved?"
            actions: [
                Kirigami.Action { text: "Yes"; onTriggered: rpc.rpc("confirm yes", function(){}) },
                Kirigami.Action { text: "No"; onTriggered: rpc.rpc("confirm no", function(){}) }
            ]
        }
        RowLayout {
            QQC2.TextField {
                id: input
                Layout.fillWidth: true
                placeholderText: "Message"
                Accessible.name: "Chat input"
                onAccepted: send()
            }
            QQC2.Button { text: "Send"; Accessible.name: "Send"; onClicked: send() }
            QQC2.Button { text: "Yes"; Accessible.name: "Problem solved yes"; onClicked: rpc.rpc("confirm yes", function(r){ log.text += "\n" + JSON.stringify(r) }) }
            QQC2.Button { text: "No"; Accessible.name: "Problem solved no"; onClicked: rpc.rpc("confirm no", function(r){ log.text += "\n" + JSON.stringify(r) }) }
            QQC2.Button { text: "Copy bug report"; Accessible.name: "Copy bug report"; onClicked: rpc.rpc("bug-report", function(r){ log.text += "\n" + JSON.stringify(r) }) }
        }
    }
    function send() {
        const msg = input.text
        log.text += "\n> " + msg
        input.text = ""
        const q = "'" + msg.replace(/'/g, "") + "'"
        rpc.rpc("chat -- " + q, function(r){ log.text += "\n" + JSON.stringify(r) })
    }
    Component.onCompleted: rpc.rpc("sessions list", function(r) {
        if (Array.isArray(r)) {
            sessions.model = r.map(s => s.title || s.id)
        }
    })
}
