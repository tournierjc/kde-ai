import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import ".."

Item {
    id: skillsPage
    ExecRpc { id: rpc }

    property var skills: []

    ColumnLayout {
        anchors.fill: parent
        spacing: Kirigami.Units.smallSpacing

        QQC2.Label { text: "Skills (max 3 enabled)"; font.bold: true }
        QQC2.Label {
            text: "Enabled skills are injected into the prompt. Shipped skills cannot be removed."
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            opacity: 0.7
        }

        QQC2.Frame {
            Layout.fillWidth: true
            Layout.preferredHeight: Kirigami.Units.gridUnit * 12
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Kirigami.Units.smallSpacing
                Repeater {
                    model: skillsPage.skills
                    QQC2.Switch {
                        Layout.fillWidth: true
                        text: (modelData.name || modelData.id) + " — " + (modelData.description || "")
                        checked: !!modelData.enabled
                        Accessible.name: "Toggle skill " + modelData.id
                        onToggled: {
                            rpc.rpc("skills " + (checked ? "enable " : "disable ") + modelData.id, function() {})
                            body.text = (modelData.name || modelData.id) + "\n" + (modelData.description || "")
                        }
                    }
                }
            }
        }

        QQC2.TextArea {
            id: body
            Layout.fillWidth: true
            Layout.fillHeight: true
            readOnly: true
            wrapMode: TextEdit.Wrap
            Accessible.name: "Skill body"
            placeholderText: "Select a shipped skill. User skills live in ~/.local/share/kde-ai/skills/"
        }

        RowLayout {
            QQC2.Button {
                text: "Install user skill"
                Accessible.name: "Install skill"
                icon.name: "list-add"
                onClicked: rpc.rpc("skills list", skillsPage.load)
            }
            QQC2.Button {
                text: "Remove user skill"
                Accessible.name: "Remove user skill"
                icon.name: "list-remove"
                onClicked: skillsPage.load()
            }
            Item { Layout.fillWidth: true }
        }
    }

    function load() {
        rpc.rpc("skills list", function(r) {
            if (!Array.isArray(r))
                return
            skills = r
            if (r.length)
                body.text = (r[0].name || r[0].id) + "\n" + (r[0].description || "")
        })
    }

    Component.onCompleted: load()
}
