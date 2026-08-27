import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: win
    title: "KDE AI"
    icon.name: "org.kde.kdeai"
    minimumWidth: 520
    minimumHeight: 560
    width: 720
    height: 680
    pageStack.initialPage: Kirigami.Page {
        title: "KDE AI"
        padding: Kirigami.Units.largeSpacing
        ColumnLayout {
            anchors.fill: parent
            QQC2.TabBar {
                id: tabs
                Layout.fillWidth: true
                QQC2.TabButton { text: "Chat"; icon.name: "org.kde.kdeai" }
                QQC2.TabButton { text: "Memory"; icon.name: "pin" }
                QQC2.TabButton { text: "Skills"; icon.name: "applications-development" }
                QQC2.TabButton { text: "Config"; icon.name: "configure" }
            }
            Loader {
                Layout.fillWidth: true
                Layout.fillHeight: true
                source: {
                    const pages = [
                        "../../plasmoid/contents/ui/pages/ChatPage.qml",
                        "../../plasmoid/contents/ui/pages/MemoryPage.qml",
                        "../../plasmoid/contents/ui/pages/SkillsPage.qml",
                        "../../plasmoid/contents/ui/pages/ConfigPage.qml"
                    ]
                    return Qt.resolvedUrl(pages[tabs.currentIndex])
                }
            }
        }
    }
}
