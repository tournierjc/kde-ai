import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import ".."

Item {
    id: memoryPage
    ExecRpc { id: rpc }

    property int workingTokens: 0
    property int budget: 4096

    ColumnLayout {
        anchors.fill: parent
        spacing: Kirigami.Units.smallSpacing

        QQC2.Label { text: "Context budget"; font.bold: true }
        QQC2.Label {
            id: stats
            text: "Token budget"
            Accessible.name: "Token budget"
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        QQC2.ProgressBar {
            Layout.fillWidth: true
            from: 0
            to: Math.max(memoryPage.budget, 1)
            value: memoryPage.workingTokens
            Accessible.name: "Working tokens"
        }

        QQC2.Label { text: "Pins"; font.bold: true }
        QQC2.Label {
            text: "Facts the agent should keep across turns."
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            opacity: 0.7
        }
        QQC2.Frame {
            Layout.fillWidth: true
            Layout.fillHeight: true
            ListView {
                id: pinList
                anchors.fill: parent
                anchors.margins: Kirigami.Units.smallSpacing
                clip: true
                Accessible.name: "Pin list"
                model: []
                delegate: QQC2.Label {
                    required property var modelData
                    width: pinList.width
                    text: modelData
                    wrapMode: Text.WordWrap
                }
                Kirigami.PlaceholderMessage {
                    anchors.centerIn: parent
                    width: parent.width - Kirigami.Units.largeSpacing * 2
                    visible: pinList.count === 0
                    text: "No pins yet"
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            QQC2.TextField {
                id: pinText
                Layout.fillWidth: true
                placeholderText: "New pin"
                Accessible.name: "New pin"
                onAccepted: memoryPage.addPin()
            }
            QQC2.Button { text: "Add pin"; Accessible.name: "Add pin"; icon.name: "list-add"; onClicked: memoryPage.addPin() }
            QQC2.Button { text: "Unpin"; Accessible.name: "Unpin"; icon.name: "list-remove"; onClicked: memoryPage.refresh() }
        }

        Flow {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing
            QQC2.Button { text: "Summarize now"; Accessible.name: "Summarize session"; onClicked: rpc.rpc("memory summarize", memoryPage.refresh) }
            QQC2.Button { text: "Export"; Accessible.name: "Export session"; onClicked: rpc.rpc("memory export", memoryPage.refresh) }
            QQC2.Button { text: "Clear working"; Accessible.name: "Clear working memory"; onClicked: rpc.rpc("memory clear working", memoryPage.refresh) }
        }

        QQC2.Label { text: "Solved"; font.bold: true }
        QQC2.Label {
            text: "Confirmed issue → solution pairs stored for this session."
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            opacity: 0.7
        }
        QQC2.Frame {
            Layout.fillWidth: true
            Layout.preferredHeight: Kirigami.Units.gridUnit * 6
            ListView {
                id: solvedList
                anchors.fill: parent
                anchors.margins: Kirigami.Units.smallSpacing
                clip: true
                Accessible.name: "Solved list"
                model: []
                delegate: QQC2.Label {
                    required property var modelData
                    width: solvedList.width
                    text: modelData
                    wrapMode: Text.WordWrap
                }
            }
        }
        RowLayout {
            QQC2.Button { text: "Forget solved"; Accessible.name: "Forget solved"; onClicked: memoryPage.refresh() }
            Item { Layout.fillWidth: true }
        }

        Kirigami.InlineMessage {
            id: overflow
            Layout.fillWidth: true
            type: Kirigami.MessageType.Warning
            text: "Oldest working turns were summarized or trimmed."
            visible: false
        }
    }

    function addPin() {
        if (!pinText.text.trim().length)
            return
        rpc.rpc("memory pin " + pinText.text, refresh)
        pinText.text = ""
    }

    function refresh() {
        rpc.rpc("memory stats", function(r) {
            if (!r || r.error)
                return
            workingTokens = r.working_tokens || 0
            budget = r.budget || 4096
            stats.text = (r.working_tokens || 0) + " working · "
                + (r.summary_tokens || 0) + " summary · "
                + (r.pin_tokens || 0) + " pins · "
                + (r.solved_tokens || 0) + " solved  /  "
                + (r.budget || 4096) + " token budget"
            overflow.visible = !!r.overflow
        })
        rpc.rpc("memory pins", function(r) {
            if (Array.isArray(r))
                pinList.model = r.map(p => p.text)
        })
        rpc.rpc("memory solved", function(r) {
            if (Array.isArray(r))
                solvedList.model = r.map(s => (s.issue || "") + "  →  " + (s.solution || ""))
        })
    }

    Component.onCompleted: refresh()
}
