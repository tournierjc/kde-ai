import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.plasma5support as Plasma5Support
import "pages" as Pages

PlasmoidItem {
    id: root

    property string page: "chat"
    property string statusText: "idle"
    property string uiSurface: "panel"
    property bool paused: statusText === "paused"
    property bool awaiting: statusText === "awaiting_confirm"
    property bool agentStopped: statusText === "stopped"
    readonly property bool onPanel: Plasmoid.formFactor === PlasmaCore.Types.Horizontal
        || Plasmoid.formFactor === PlasmaCore.Types.Vertical
    readonly property bool inSystemTray: Plasmoid.containment
        && Plasmoid.containment.pluginName === "org.kde.plasma.systemtray"
    readonly property bool onPanelWidget: Plasmoid.containment
        && Plasmoid.containment.pluginName === "org.kde.panel"

    function applyUiSurface() {
        if (uiSurface === "none") {
            Plasmoid.status = PlasmaCore.Types.HiddenStatus
        } else if (uiSurface === "panel" && inSystemTray) {
            Plasmoid.status = PlasmaCore.Types.HiddenStatus
        } else if (uiSurface === "tray" && onPanelWidget) {
            Plasmoid.status = PlasmaCore.Types.HiddenStatus
        } else {
            Plasmoid.status = PlasmaCore.Types.ActiveStatus
        }
    }

    onUiSurfaceChanged: applyUiSurface()
    Component.onCompleted: {
        trayRpc.rpc("config get", function(r) {
            if (r && r.plasma && r.plasma.ui_surface)
                root.uiSurface = r.plasma.ui_surface
            else
                root.applyUiSurface()
        })
    }

    // Panel keeps the compact "AI" chip. plasmawindowed / desktop must use the
    // full pages — locking compact left an empty window with overlays off-canvas.
    switchWidth: Kirigami.Units.gridUnit * 16
    switchHeight: Kirigami.Units.gridUnit * 16
    preferredRepresentation: onPanel ? compactRepresentation : fullRepresentation

    toolTipMainText: "KDE AI"
    toolTipSubText: agentStopped
        ? "Stopped — right-click to start"
        : (paused ? "Paused — GPU in use · click to open" : "Click to open the agent window")
    Plasmoid.icon: "org.kde.kdeai"

    ExecRpc { id: trayRpc }

    Plasma5Support.DataSource {
        id: windowExe
        engine: "executable"
        function openAgentWindow() {
            connectSource("kde-ai open")
        }
    }

    Timer {
        interval: 2000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: trayRpc.rpc("status", function(r) {
            if (r && r.state)
                root.statusText = r.state
        })
    }

    Plasmoid.contextualActions: [
        PlasmaCore.Action {
            text: "Start agent"
            icon.name: "media-playback-start"
            enabled: root.agentStopped
            onTriggered: trayRpc.rpc("start", function(r) {
                root.statusText = (r && r.state) ? r.state : "idle_unloaded"
            })
        },
        PlasmaCore.Action {
            text: "Quit"
            icon.name: "application-exit"
            enabled: !root.agentStopped
            onTriggered: trayRpc.rpc("quit", function() {
                root.statusText = "stopped"
            })
        }
    ]

    compactRepresentation: PlasmaComponents.ToolButton {
        readonly property string chipText: root.agentStopped ? "AI ·"
            : (root.paused ? "AI ‖" : (root.awaiting ? "AI ?" : "AI"))

        display: root.inSystemTray
            ? PlasmaComponents.AbstractButton.IconOnly
            : PlasmaComponents.AbstractButton.TextOnly
        flat: root.inSystemTray
        text: root.inSystemTray ? "" : chipText
        icon.name: root.paused ? "media-playback-pause" : "org.kde.kdeai"
        icon.width: Kirigami.Units.iconSizes.smallMedium
        icon.height: Kirigami.Units.iconSizes.smallMedium
        Accessible.name: root.agentStopped ? "KDE AI stopped" : (root.paused ? "KDE AI paused" : "KDE AI agent")
        onClicked: {
            root.expanded = false
            windowExe.openAgentWindow()
        }
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
                            "stopped": "Stopped",
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
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: root.agentStopped
                type: Kirigami.MessageType.Information
                text: "Agent is stopped. Right-click the tray icon and choose Start agent, or send a chat."
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
                Pages.ConfigPage {
                    plasmoidRoot: root
                }
            }
        }
    }
}
