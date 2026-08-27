import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: win
    title: "KDE AI"
    pageStack.initialPage: Kirigami.Page {
        title: "KDE AI"
        ColumnLayout {
            anchors.fill: parent
            Kirigami.NavigationTabBar {
                Layout.fillWidth: true
                actions: [
                    Kirigami.Action { text: "Chat"; onTriggered: loader.source = "pages/ChatPage.qml" },
                    Kirigami.Action { text: "Memory"; onTriggered: loader.source = "pages/MemoryPage.qml" },
                    Kirigami.Action { text: "Skills"; onTriggered: loader.source = "pages/SkillsPage.qml" },
                    Kirigami.Action { text: "Config"; onTriggered: loader.source = "pages/ConfigPage.qml" }
                ]
            }
            Loader { id: loader; Layout.fillWidth: true; Layout.fillHeight: true; source: "pages/ChatPage.qml" }
        }
    }
}
