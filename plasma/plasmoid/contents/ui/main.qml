import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents
import "pages" as Pages

PlasmoidItem {
    id: root

    property string page: "chat"
    property string statusText: "idle"
    property bool paused: statusText === "paused"
    property bool awaiting: statusText === "awaiting_confirm"
    readonly property bool onPanel: Plasmoid.formFactor === PlasmaCore.Types.Horizontal
        || Plasmoid.formFactor === PlasmaCore.Types.Vertical

    // Panel keeps the compact "AI" chip. plasmawindowed / desktop must use the
    // full pages — locking compact left an empty window with overlays off-canvas.
    switchWidth: Kirigami.Units.gridUnit * 16
    switchHeight: Kirigami.Units.gridUnit * 16
    preferredRepresentation: onPanel ? compactRepresentation : fullRepresentation

    toolTipMainText: "KDE AI"
    toolTipSubText: paused ? "Paused — GPU in use" : "Local KDE/CachyOS agent"

    compactRepresentation: PlasmaComponents.ToolButton {
        text: paused ? "AI ‖" : (awaiting ? "AI ?" : "AI")
        Accessible.name: paused ? "KDE AI paused" : "KDE AI agent"
        icon.name: paused ? "media-playback-pause" : "org.kde.kdeai"
        onClicked: root.expanded = !root.expanded
        onPressAndHold: root.expanded = true
    }

    fullRepresentation: Item {
        id: full
        anchors.fill: parent
        Layout.minimumWidth: Kirigami.Units.gridUnit * 34
        Layout.minimumHeight: Kirigami.Units.gridUnit * 38
        Layout.preferredWidth: Kirigami.Units.gridUnit * 42
        Layout.preferredHeight: Kirigami.Units.gridUnit * 48

        Kirigami.Theme.colorSet: Kirigami.Theme.View
        Kirigami.Theme.inherit: false

        Rectangle {
            anchors.fill: parent
            color: Kirigami.Theme.backgroundColor
        }

        ExecRpc { id: statusRpc }

        Timer {
            interval: 2000
            running: true
            repeat: true
            triggeredOnStart: true
            onTriggered: statusRpc.rpc("status", function(r) {
                if (r && r.state)
                    root.statusText = r.state
            })
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.smallSpacing

            RowLayout {
                Layout.fillWidth: true
                QQC2.Label {
                    text: "KDE AI"
                    font.bold: true
                }
                Item { Layout.fillWidth: true }
                QQC2.Label {
                    text: {
                        const labels = {
                            "ready": "Ready",
                            "idle_unloaded": "Ready · model unloaded",
                            "loading": "Loading model…",
                            "answering": "Answering…",
                            "awaiting_confirm": "Waiting for Yes / No",
                            "awaiting_privilege": "Waiting for privilege",
                            "paused": "Paused — GPU in use",
                            "disabled": "Disabled",
                            "busy": "Busy"
                        }
                        return labels[root.statusText] || root.statusText
                    }
                    opacity: 0.7
                }
            }

            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: root.paused
                type: Kirigami.MessageType.Warning
                text: "GPU compute in use — the agent is paused until the other job yields."
            }

            QQC2.TabBar {
                id: tabs
                Layout.fillWidth: true
                QQC2.TabButton { text: "Chat"; icon.name: "org.kde.kdeai"; Accessible.name: "Chat page" }
                QQC2.TabButton { text: "Memory"; icon.name: "pin"; Accessible.name: "Memory page" }
                QQC2.TabButton { text: "Skills"; icon.name: "applications-development"; Accessible.name: "Skills page" }
                QQC2.TabButton { text: "Config"; icon.name: "configure"; Accessible.name: "Config page" }
                onCurrentIndexChanged: {
                    const names = ["chat", "memory", "skills", "config"]
                    root.page = names[currentIndex] || "chat"
                }
            }

            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: tabs.currentIndex
                Pages.ChatPage { awaiting: root.awaiting }
                Pages.MemoryPage {}
                Pages.SkillsPage {}
                Pages.ConfigPage {}
            }
        }
    }
}
