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
        QQC2.Label { text: "Skills (max 3 enabled)"; font.bold: true }
        Repeater {
            id: reps
            model: []
            QQC2.Switch {
                text: modelData.id + " — " + modelData.description
                checked: modelData.enabled
                Accessible.name: "Toggle skill " + modelData.id
                onToggled: rpc.rpc("skills " + (checked ? "enable " : "disable ") + modelData.id, function(){})
            }
        }
        QQC2.TextArea {
            id: body
            Layout.fillWidth: true
            Layout.fillHeight: true
            readOnly: true
            Accessible.name: "Skill body"
            text: "Select a shipped skill. User skills live in ~/.local/share/kde-ai/skills/"
        }
        RowLayout {
            QQC2.Button { text: "Install user skill"; Accessible.name: "Install skill"; onClicked: rpc.rpc("skills list", load) }
            QQC2.Button { text: "Remove user skill"; Accessible.name: "Remove user skill"; onClicked: load() }
        }
    }
    function load() {
        rpc.rpc("skills list", function(r) {
            if (Array.isArray(r)) reps.model = r
        })
    }
    Component.onCompleted: load()
}
