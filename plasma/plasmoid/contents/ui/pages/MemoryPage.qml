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
        QQC2.Label { text: "Memory"; font.bold: true }
        QQC2.Label { id: stats; text: "Token budget"; Accessible.name: "Token budget"; wrapMode: Text.WordWrap; Layout.fillWidth: true }
        QQC2.ProgressBar { Layout.fillWidth: true; value: 0.3; Accessible.name: "Working tokens" }
        QQC2.Label { text: "Pins"; font.bold: true }
        QQC2.ListView {
            id: pinList
            Layout.fillWidth: true
            Layout.preferredHeight: 80
            Accessible.name: "Pin list"
            model: []
            delegate: QQC2.Label { text: modelData }
        }
        RowLayout {
            QQC2.TextField { id: pinText; Layout.fillWidth: true; placeholderText: "Pin text"; Accessible.name: "New pin" }
            QQC2.Button { text: "Add pin"; Accessible.name: "Add pin"; onClicked: rpc.rpc("memory pin " + pinText.text, refresh) }
            QQC2.Button { text: "Unpin"; Accessible.name: "Unpin"; onClicked: refresh() }
        }
        QQC2.Label { text: "Solved"; font.bold: true }
        QQC2.ListView {
            Layout.fillWidth: true
            Layout.preferredHeight: 80
            Accessible.name: "Solved list"
            model: []
            delegate: QQC2.Label { text: modelData }
        }
        RowLayout {
            QQC2.Button { text: "Summarize now"; Accessible.name: "Summarize session"; onClicked: rpc.rpc("memory summarize", refresh) }
            QQC2.Button { text: "Export"; Accessible.name: "Export session"; onClicked: rpc.rpc("memory export", refresh) }
            QQC2.Button { text: "Clear working"; Accessible.name: "Clear working memory"; onClicked: rpc.rpc("memory clear working", refresh) }
            QQC2.Button { text: "Forget solved"; Accessible.name: "Forget solved"; onClicked: refresh() }
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Warning
            text: "Overflow: oldest working turns were summarized or trimmed."
            visible: false
            id: overflow
        }
    }
    function refresh() {
        rpc.rpc("memory stats", function(r){ stats.text = JSON.stringify(r); overflow.visible = !!(r && r.overflow) })
        rpc.rpc("memory pins", function(r){ if (Array.isArray(r)) pinList.model = r.map(p => p.text) })
    }
    Component.onCompleted: refresh()
}
