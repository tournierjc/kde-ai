import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import ".."

Item {
    id: chatPage
    property bool awaiting: false

    ExecRpc { id: rpc }

    ColumnLayout {
        anchors.fill: parent
        spacing: Kirigami.Units.smallSpacing

        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing
            QQC2.Label { text: "Session" }
            QQC2.ComboBox {
                id: sessions
                Layout.fillWidth: true
                Accessible.name: "Session list"
                model: sessionModel
                textRole: "title"
                valueRole: "sid"
                onActivated: chatPage.useCurrent()
            }
            QQC2.ToolButton {
                icon.name: "list-add"
                Accessible.name: "New session"
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.text: "New session"
                onClicked: {
                    newTitle.text = ""
                    newDlg.open()
                    newTitle.forceActiveFocus()
                }
            }
            QQC2.ToolButton {
                icon.name: "edit-delete"
                Accessible.name: "Delete session"
                enabled: sessionModel.count > 0 && !delDlg.visible
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.text: "Delete session"
                onClicked: delDlg.open()
            }
        }

        QQC2.ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            QQC2.TextArea {
                id: log
                readOnly: true
                wrapMode: TextEdit.Wrap
                Accessible.name: "Chat transcript"
                persistentSelection: true
                placeholderText: "Ask about Plasma, CachyOS, or this machine.\nThe agent runs locally and yields the GPU when other apps need it."
            }
        }

        Kirigami.InlineMessage {
            id: solveCard
            Layout.fillWidth: true
            visible: chatPage.awaiting
            type: Kirigami.MessageType.Information
            text: "Is the problem solved?"
            actions: [
                Kirigami.Action {
                    text: "Yes"
                    Accessible.name: "Problem solved yes"
                    onTriggered: rpc.rpc("confirm yes", function() { solveCard.visible = false })
                },
                Kirigami.Action {
                    text: "No"
                    Accessible.name: "Problem solved no"
                    onTriggered: rpc.rpc("confirm no", function() { solveCard.visible = false })
                }
            ]
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing
            QQC2.TextField {
                id: input
                Layout.fillWidth: true
                placeholderText: "Message"
                Accessible.name: "Chat input"
                enabled: !delDlg.visible && !newDlg.opened
                onAccepted: send()
            }
            QQC2.Button {
                text: "Send"
                Accessible.name: "Send"
                icon.name: "document-send"
                onClicked: send()
            }
            QQC2.ToolButton {
                icon.name: "edit-copy"
                Accessible.name: "Copy bug report"
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.text: "Copy bug report"
                onClicked: rpc.rpc("bug-report", function(r) {
                    log.append("\n" + (typeof r === "object" ? JSON.stringify(r, null, 2) : r))
                })
            }
        }
    }

    ListModel { id: sessionModel }

    Kirigami.PromptDialog {
        id: newDlg
        parent: QQC2.Overlay.overlay
        title: "New session"
        preferredWidth: Kirigami.Units.gridUnit * 22
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: "Create"
                icon.name: "dialog-ok"
                onTriggered: {
                    chatPage.createSession(newTitle.text.trim())
                    newDlg.close()
                }
            },
            Kirigami.Action {
                text: "Cancel"
                icon.name: "dialog-cancel"
                onTriggered: newDlg.close()
            }
        ]
        QQC2.TextField {
            id: newTitle
            Layout.fillWidth: true
            placeholderText: "Name"
            Accessible.name: "New session name"
            onAccepted: {
                chatPage.createSession(newTitle.text.trim())
                newDlg.close()
            }
        }
    }

    // In-page overlay (not a Popup): plasmawindowed never delivers Return to
    // Kirigami/QQC2 dialogs because the chat field keeps focus.
    FocusScope {
        id: delDlg
        anchors.fill: parent
        visible: false
        z: 100
        activeFocusOnTab: true

        function open() {
            input.focus = false
            visible = true
            forceActiveFocus()
            delOkBtn.forceActiveFocus()
        }
        function close() {
            visible = false
        }
        function confirm() {
            chatPage.deleteCurrent()
            close()
        }

        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                delDlg.confirm()
                event.accepted = true
            } else if (event.key === Qt.Key_Escape) {
                delDlg.close()
                event.accepted = true
            }
        }

        Rectangle {
            anchors.fill: parent
            color: Qt.rgba(0, 0, 0, 0.45)
            MouseArea {
                anchors.fill: parent
                onClicked: delDlg.close()
            }
        }

        Rectangle {
            id: delCard
            anchors.centerIn: parent
            width: Math.min(parent.width - Kirigami.Units.gridUnit * 2, Kirigami.Units.gridUnit * 24)
            height: delCardLayout.implicitHeight + Kirigami.Units.largeSpacing * 2
            radius: Kirigami.Units.cornerRadius
            color: Kirigami.Theme.backgroundColor
            border.color: Kirigami.Theme.textColor
            border.width: 1
            opacity: 0.97

            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.AllButtons
            }

            ColumnLayout {
                id: delCardLayout
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: Kirigami.Units.largeSpacing
                spacing: Kirigami.Units.largeSpacing

                QQC2.Label {
                    text: "Delete session"
                    font.bold: true
                    Layout.fillWidth: true
                }
                QQC2.Label {
                    text: "Delete “" + (sessions.currentText || "this session") + "”? This cannot be undone."
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                RowLayout {
                    Layout.alignment: Qt.AlignRight
                    QQC2.Button {
                        id: delOkBtn
                        text: "OK"
                        icon.name: "dialog-ok"
                        highlighted: true
                        Accessible.name: "Confirm delete session"
                        Keys.onReturnPressed: delDlg.confirm()
                        Keys.onEnterPressed: delDlg.confirm()
                        onClicked: delDlg.confirm()
                    }
                    QQC2.Button {
                        text: "Cancel"
                        icon.name: "dialog-cancel"
                        Accessible.name: "Cancel delete session"
                        onClicked: delDlg.close()
                    }
                }
            }
        }
    }

    function send() {
        const msg = input.text.trim()
        if (!msg.length)
            return
        log.append("You\n" + msg + "\n")
        input.text = ""
        const q = "'" + msg.replace(/'/g, "'\\''") + "'"
        const sid = sessions.currentValue ? ("-s " + sessions.currentValue + " ") : ""
        rpc.rpc("chat " + sid + "-- " + q, function(r) {
            if (sessions.currentValue)
                chatPage.loadTranscript(sessions.currentValue)
            else {
                const body = chatReply(r)
                if (body)
                    log.append("KDE AI\n" + body + "\n")
            }
        })
    }

    function loadSessions(selectId) {
        rpc.rpc("sessions list", function(r) {
            const rows = Array.isArray(r) ? r : []
            sessionModel.clear()
            for (let i = 0; i < rows.length; i++) {
                const s = rows[i]
                sessionModel.append({ sid: s.id, title: s.title || s.id })
            }
            if (!sessionModel.count) {
                rpc.rpc("sessions new", function() { chatPage.loadSessions(selectId) })
                return
            }
            let idx = 0
            if (selectId) {
                for (let i = 0; i < sessionModel.count; i++) {
                    if (sessionModel.get(i).sid === selectId) {
                        idx = i
                        break
                    }
                }
            }
            sessions.currentIndex = idx
            chatPage.useCurrent()
        })
    }

    function useCurrent() {
        const sid = sessions.currentValue
        if (!sid)
            return
        rpc.rpc("sessions use " + sid, function() { chatPage.loadTranscript(sid) })
    }

    function loadTranscript(sid) {
        rpc.rpc("sessions transcript " + (sid || sessions.currentValue || ""), function(r) {
            const msgs = (r && r.messages) || []
            let text = ""
            for (let i = 0; i < msgs.length; i++) {
                const m = msgs[i]
                if (!isVisibleChat(m))
                    continue
                const role = m.role === "user" ? "You" : "KDE AI"
                text += role + "\n" + (m.content || "") + "\n\n"
            }
            log.text = text.trim()
        })
    }

    function isVisibleChat(m) {
        if (!m)
            return false
        const role = m.role
        const content = (m.content || "").trim()
        if (!content)
            return false
        if (role === "tool" || role === "system")
            return false
        if (role !== "user" && role !== "assistant")
            return false
        if (content.charAt(0) === "{" && content.indexOf("\"ok\"") !== -1
            && (content.indexOf("\"summary\"") !== -1 || content.indexOf("\"monitors\"") !== -1))
            return false
        return true
    }

    function createSession(title) {
        let args = "sessions new"
        if (title)
            args += " " + title.replace(/[\n\r]+/g, " ")
        rpc.rpc(args, function(r) {
            const sid = r && (r.session_id || r.id)
            chatPage.loadSessions(sid)
        })
    }

    function deleteCurrent() {
        const sid = sessions.currentValue
        if (!sid)
            return
        rpc.rpc("sessions delete " + sid, function() {
            chatPage.loadSessions()
        })
    }

    function chatReply(r) {
        if (!r)
            return ""
        if (typeof r === "string")
            return r
        if (r.error && !r.text)
            return String(r.error)
        if (typeof r.text === "string" && r.text.length)
            return r.text
        if (r.reason === "paused")
            return "Paused — GPU in use" + (r.error ? " (" + r.error + ")" : "")
        if (r.reason === "error")
            return r.error ? String(r.error) : "The agent hit an error."
        return ""
    }

    Component.onCompleted: chatPage.loadSessions()
}
