import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents

PlasmoidItem {
    id: root
    property string page: "chat"
    property string statusText: "idle"
    property bool paused: statusText === "paused"
    property bool awaiting: statusText === "awaiting_confirm"
    preferredRepresentation: compactRepresentation
    toolTipMainText: "KDE AI"
    toolTipSubText: "Open with Meta+Shift+A"

    Component.onCompleted: root.page = "chat"

    compactRepresentation: PlasmaComponents.ToolButton {
        text: paused ? "AI ‖" : (awaiting ? "AI ?" : "AI")
        Accessible.name: paused ? "KDE AI paused" : "KDE AI agent"
        icon.name: paused ? "media-playback-pause" : "help-hint"
        onClicked: root.expanded = !root.expanded
        onPressAndHold: root.expanded = true
    }

    fullRepresentation: Kirigami.Page {
        title: "KDE AI"
        ColumnLayout {
            anchors.fill: parent
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: root.paused
                type: Kirigami.MessageType.Warning
                text: "GPU compute in use — agent paused (not color-only: this banner is the paused state)."
            }
            Kirigami.NavigationTabBar {
                Layout.fillWidth: true
                actions: [
                    Kirigami.Action { text: "Chat"; Accessible.name: "Chat page"; onTriggered: root.page = "chat" },
                    Kirigami.Action { text: "Memory"; Accessible.name: "Memory page"; onTriggered: root.page = "memory" },
                    Kirigami.Action { text: "Skills"; Accessible.name: "Skills page"; onTriggered: root.page = "skills" },
                    Kirigami.Action { text: "Config"; Accessible.name: "Config page"; onTriggered: root.page = "config" }
                ]
            }
            Loader {
                Layout.fillWidth: true
                Layout.fillHeight: true
                source: {
                    if (root.page === "memory") return "pages/MemoryPage.qml"
                    if (root.page === "skills") return "pages/SkillsPage.qml"
                    if (root.page === "config") return "pages/ConfigPage.qml"
                    return "pages/ChatPage.qml"
                }
            }
        }
    }
}
