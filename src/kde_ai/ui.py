"""Four-page Qt UI (Flatpak / standalone) over the same JSON-RPC socket as the CLI."""

from __future__ import annotations

import json
import os
import sys
import time

from kde_ai.chatlog import visible_chat_messages
from kde_ai.client import RpcClient
from kde_ai.errors import RpcError


def _kind() -> str:
    if os.environ.get("FLATPAK_ID"):
        return "flatpak-ui"
    return "plasmoid"


def _connect() -> RpcClient:
    rpc = RpcClient()
    rpc.connect()
    rpc.hello(client=_kind(), auth="none" if os.environ.get("FLATPAK_ID") else "polkit")
    return rpc


def _muted(label) -> None:
    pal = label.palette()
    pal.setColor(label.foregroundRole(), pal.color(pal.ColorRole.PlaceholderText))
    label.setPalette(pal)


def _app_icon():
    from importlib.resources import files

    from PySide6.QtGui import QIcon

    svg = files("kde_ai").joinpath("icons/org.kde.kdeai.svg")
    if svg.is_file():
        return QIcon(str(svg))
    return QIcon.fromTheme("org.kde.kdeai")


def _heading(text: str):
    from PySide6.QtWidgets import QLabel

    lab = QLabel(text)
    font = lab.font()
    font.setBold(True)
    lab.setFont(font)
    return lab


def main() -> None:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QIcon, QKeySequence, QTextCursor
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QFileDialog,
            QFormLayout,
            QFrame,
            QHBoxLayout,
            QInputDialog,
            QKeySequenceEdit,
            QLabel,
            QLineEdit,
            QListWidget,
            QListWidgetItem,
            QMessageBox,
            QPlainTextEdit,
            QProgressBar,
            QPushButton,
            QSizePolicy,
            QSpinBox,
            QSplitter,
            QStyleFactory,
            QTabWidget,
            QVBoxLayout,
            QWidget,
        )
    except ImportError:
        print("PySide6 is required for kde-ai-ui. Use: kde-ai  (CLI)", file=sys.stderr)
        raise SystemExit(2)

    app = QApplication(sys.argv)
    app.setApplicationName("KDE AI")
    app.setDesktopFileName("org.kde.kdeai")
    icon = _app_icon()
    app.setWindowIcon(icon)
    if "Breeze" in QStyleFactory.keys():
        app.setStyle("Breeze")

    rpc = _connect()
    win = QWidget()
    win.setWindowTitle("KDE AI")
    win.setWindowIcon(icon)
    win.setMinimumSize(560, 580)
    root = QVBoxLayout(win)
    root.setContentsMargins(16, 16, 16, 16)
    root.setSpacing(10)

    pause_banner = QLabel("GPU compute in use — the agent is paused until the other job yields.")
    pause_banner.setWordWrap(True)
    pause_banner.setVisible(False)
    pause_banner.setContentsMargins(10, 8, 10, 8)
    root.addWidget(pause_banner)

    tabs = QTabWidget()
    tabs.setAccessibleName("KDE AI pages")
    tabs.setDocumentMode(True)
    root.addWidget(tabs)

    def theme_icon(*names: str) -> QIcon:
        for name in names:
            icon = QIcon.fromTheme(name)
            if not icon.isNull():
                return icon
        return QIcon()

    def sid() -> str:
        st = rpc.call("status.get")
        if st.get("active_session_id"):
            return st["active_session_id"]
        return rpc.call("session.create", {"title": "General"})["session_id"]

    def apply_status(st: dict | None = None) -> None:
        st = st or rpc.call("status.get")
        state = st.get("state") or "ready"
        labels = {
            "ready": "Ready",
            "idle_unloaded": "Ready · model unloaded",
            "loading": "Loading model…",
            "answering": "Answering…",
            "awaiting_confirm": "Waiting for Yes / No",
            "awaiting_privilege": "Waiting for privilege prompt",
            "paused": "Paused — GPU in use",
            "disabled": "Disabled",
            "busy": "Busy",
        }
        status_chip.setText(labels.get(state, state.replace("_", " ").title()))
        pause_banner.setVisible(state == "paused")
        solve_card.setVisible(state == "awaiting_confirm")

    chat = QWidget()
    cl = QVBoxLayout(chat)
    cl.setContentsMargins(8, 12, 8, 8)
    cl.setSpacing(8)

    chat_top = QHBoxLayout()
    sessions = QComboBox()
    sessions.setAccessibleName("Session list")
    sessions.setMinimumWidth(200)
    sessions.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    status_chip = QLabel("Ready")
    _muted(status_chip)
    chat_top.addWidget(QLabel("Session"))
    chat_top.addWidget(sessions, 1)
    new_sess = QPushButton()
    new_sess.setIcon(theme_icon("list-add"))
    new_sess.setAccessibleName("New session")
    new_sess.setToolTip("New session")
    del_sess = QPushButton()
    del_sess.setIcon(theme_icon("edit-delete", "list-remove"))
    del_sess.setAccessibleName("Delete session")
    del_sess.setToolTip("Delete session")
    chat_top.addWidget(new_sess)
    chat_top.addWidget(del_sess)
    chat_top.addWidget(status_chip)
    cl.addLayout(chat_top)

    transcript = QPlainTextEdit()
    transcript.setReadOnly(True)
    transcript.setAccessibleName("Chat transcript")
    transcript.setPlaceholderText(
        "Ask about Plasma, CachyOS, or this machine.\n"
        "The agent runs locally and yields the GPU when other apps need it."
    )
    cl.addWidget(transcript, 1)

    solve_card = QFrame()
    solve_card.setObjectName("solveCard")
    solve_card.setVisible(False)
    solve_card.setFrameShape(QFrame.Shape.StyledPanel)
    slay = QHBoxLayout(solve_card)
    slay.setContentsMargins(10, 8, 10, 8)
    solve_lab = QLabel("Is the problem solved?")
    solve_lab.setWordWrap(True)
    yes = QPushButton("Yes")
    yes.setAccessibleName("Problem solved yes")
    no = QPushButton("No")
    no.setAccessibleName("Problem solved no")
    slay.addWidget(solve_lab, 1)
    slay.addWidget(yes)
    slay.addWidget(no)
    cl.addWidget(solve_card)

    row = QHBoxLayout()
    row.setSpacing(8)
    entry = QLineEdit()
    entry.setPlaceholderText("Message")
    entry.setAccessibleName("Chat input")
    send = QPushButton("Send")
    send.setAccessibleName("Send")
    send.setDefault(True)
    send.setIcon(theme_icon("document-send", "mail-send"))
    bug = QPushButton("Copy bug report")
    bug.setAccessibleName("Copy bug report")
    bug.setIcon(theme_icon("edit-copy"))
    row.addWidget(entry, 1)
    row.addWidget(send)
    row.addWidget(bug)
    cl.addLayout(row)

    def refresh_sessions(keep: str | None = None) -> None:
        current = keep or (sessions.currentData() if sessions.count() else None)
        sessions.blockSignals(True)
        sessions.clear()
        rows = rpc.call("session.list", {}) or []
        if not rows:
            created = rpc.call("session.create", {"title": "General"})
            rows = [{"id": created["session_id"], "title": "General"}]
        for s in rows:
            sessions.addItem(s.get("title") or s["id"], s["id"])
        idx = sessions.findData(current or sid())
        sessions.setCurrentIndex(max(idx, 0))
        sessions.blockSignals(False)

    def on_session(i: int) -> None:
        ident = sessions.itemData(i)
        if ident:
            rpc.call("session.set_active", {"session_id": ident})
            try:
                tr = rpc.call("session.transcript", {"session_id": ident, "limit": 50, "offset": 0})
                msgs = visible_chat_messages(tr.get("messages") if isinstance(tr, dict) else [])
                transcript.clear()
                for m in msgs:
                    role = "You" if m.get("role") == "user" else "KDE AI"
                    transcript.appendPlainText(f"{role}\n{m.get('content') or ''}\n")
            except RpcError:
                pass
        apply_status()

    def do_send() -> None:
        msg = entry.text().strip()
        if not msg:
            return
        transcript.appendPlainText("You\n" + msg + "\n")
        entry.clear()
        send.setEnabled(False)
        try:
            rpc.call("chat.send", {"session_id": sid(), "message": msg})
            transcript.appendPlainText("KDE AI")
            cursor = transcript.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            transcript.setTextCursor(cursor)
            for _ in range(400):
                rpc.drain(0.12)
                QApplication.processEvents()
                for n in rpc.notifications:
                    if n.get("method") == "stream.token":
                        transcript.insertPlainText(n["params"].get("text") or "")
                    if n.get("method") == "issue.awaiting":
                        solve_lab.setText(
                            "Is the problem solved?\n" + (n["params"].get("issue_summary") or "")
                        )
                        solve_card.setVisible(True)
                    if n.get("method") == "status.changed":
                        apply_status(n.get("params"))
                if any(n.get("method") == "stream.done" for n in rpc.notifications):
                    break
                time.sleep(0.04)
            rpc.notifications.clear()
            transcript.appendPlainText("")
        except RpcError as exc:
            transcript.appendPlainText(f"{exc.code}: {exc.message}")
        finally:
            send.setEnabled(True)
            apply_status()
            entry.setFocus()

    def confirm(solved: bool) -> None:
        sess = next(s for s in rpc.call("session.list", {}) if s["id"] == sid())
        rpc.call(
            "issue.confirm",
            {"session_id": sid(), "attempt_id": sess.get("open_attempt_id"), "solved": solved},
        )
        transcript.appendPlainText("Saved to memory." if solved else "Retrying with a different approach.")
        solve_card.setVisible(False)
        apply_status()

    def copy_bug() -> None:
        try:
            md = rpc.call("session.bug_report", {"session_id": sid()})
            text = md.get("markdown") if isinstance(md, dict) else str(md)
            app.clipboard().setText(text or "")
            QMessageBox.information(win, "Bug report", "Copied a draft report to the clipboard.")
        except RpcError as exc:
            QMessageBox.warning(win, "Bug report", f"{exc.code}: {exc.message}")

    def new_session() -> None:
        title, ok = QInputDialog.getText(win, "New session", "Name:")
        if not ok:
            return
        created = rpc.call("session.create", {"title": title.strip() or None})
        refresh_sessions(created["session_id"])
        on_session(sessions.currentIndex())

    def delete_session() -> None:
        ident = sessions.currentData()
        if not ident:
            return
        name = sessions.currentText() or "this session"
        box = QMessageBox(win)
        box.setWindowTitle("Delete session")
        box.setText(f"Delete “{name}”? This cannot be undone.")
        box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Ok)
        if box.exec() != QMessageBox.StandardButton.Ok:
            return
        rpc.call("session.delete", {"session_id": ident})
        refresh_sessions()
        if sessions.count():
            on_session(sessions.currentIndex())
        else:
            transcript.clear()

    new_sess.clicked.connect(new_session)
    del_sess.clicked.connect(delete_session)
    send.clicked.connect(do_send)
    entry.returnPressed.connect(do_send)
    yes.clicked.connect(lambda: confirm(True))
    no.clicked.connect(lambda: confirm(False))
    bug.clicked.connect(copy_bug)
    sessions.currentIndexChanged.connect(on_session)
    tabs.addTab(chat, icon, "Chat")

    mem = QWidget()
    ml = QVBoxLayout(mem)
    ml.setContentsMargins(8, 12, 8, 8)
    ml.setSpacing(8)
    stats = QLabel("Token budget")
    stats.setAccessibleName("Token budget")
    bar = QProgressBar()
    bar.setAccessibleName("Working tokens")
    bar.setRange(0, 4096)
    bar.setValue(0)
    bar.setTextVisible(True)
    bar.setFormat("%v / %m working tokens")
    ml.addWidget(_heading("Context budget"))
    ml.addWidget(stats)
    ml.addWidget(bar)
    ml.addWidget(_heading("Pins"))
    pin_hint = QLabel("Facts the agent should keep across turns.")
    pin_hint.setWordWrap(True)
    _muted(pin_hint)
    ml.addWidget(pin_hint)
    pins = QListWidget()
    pins.setAccessibleName("Pins")
    pins.setAlternatingRowColors(True)
    ml.addWidget(pins, 1)
    pin_row = QHBoxLayout()
    pin_edit = QLineEdit()
    pin_edit.setPlaceholderText("New pin")
    pin_edit.setAccessibleName("New pin")
    addp = QPushButton("Pin")
    addp.setAccessibleName("Add pin")
    addp.setIcon(theme_icon("list-add", "bookmark-new"))
    unp = QPushButton("Unpin")
    unp.setAccessibleName("Unpin")
    unp.setIcon(theme_icon("list-remove"))
    pin_row.addWidget(pin_edit, 1)
    pin_row.addWidget(addp)
    pin_row.addWidget(unp)
    ml.addLayout(pin_row)
    mem_actions = QHBoxLayout()
    summ = QPushButton("Summarize now")
    summ.setAccessibleName("Summarize session")
    exp = QPushButton("Export")
    exp.setAccessibleName("Export session")
    clr = QPushButton("Clear working")
    clr.setAccessibleName("Clear working memory")
    for b in (summ, exp, clr):
        mem_actions.addWidget(b)
    mem_actions.addStretch()
    ml.addLayout(mem_actions)
    ml.addWidget(_heading("Solved"))
    solved_hint = QLabel("Confirmed issue → solution pairs stored for this session.")
    solved_hint.setWordWrap(True)
    _muted(solved_hint)
    ml.addWidget(solved_hint)
    solved = QListWidget()
    solved.setAccessibleName("Solved issues")
    solved.setAlternatingRowColors(True)
    ml.addWidget(solved, 1)
    forget_row = QHBoxLayout()
    forget = QPushButton("Forget solved")
    forget.setAccessibleName("Forget solved")
    forget_row.addWidget(forget)
    forget_row.addStretch()
    ml.addLayout(forget_row)
    overflow = QLabel("Oldest working turns were summarized or trimmed.")
    overflow.setWordWrap(True)
    overflow.setVisible(False)
    ml.addWidget(overflow)

    def refresh_mem() -> None:
        s = sid()
        st = rpc.call("memory.stats", {"session_id": s})
        working = int(st.get("working_tokens") or 0)
        budget = int(st.get("budget") or 4096)
        bar.setRange(0, max(budget, 1))
        bar.setValue(min(working, budget))
        stats.setText(
            f"{working} working · {st.get('summary_tokens', 0)} summary · "
            f"{st.get('pin_tokens', 0)} pins · {st.get('solved_tokens', 0)} solved"
            f"  /  {budget} token budget"
        )
        overflow.setVisible(bool(st.get("overflow")))
        pins.clear()
        for p in rpc.call("memory.pins", {"session_id": s}):
            item = QListWidgetItem(p.get("text") or p["id"])
            item.setData(Qt.ItemDataRole.UserRole, p["id"])
            pins.addItem(item)
        solved.clear()
        for row_ in rpc.call("memory.solved", {"session_id": s}):
            item = QListWidgetItem(f"{row_.get('issue')}  →  {row_.get('solution')}")
            item.setData(Qt.ItemDataRole.UserRole, row_["id"])
            item.setToolTip(item.text())
            solved.addItem(item)

    addp.clicked.connect(
        lambda: (
            rpc.call("memory.pin", {"session_id": sid(), "text": pin_edit.text()})
            if pin_edit.text().strip()
            else None,
            pin_edit.clear(),
            refresh_mem(),
        )
    )
    pin_edit.returnPressed.connect(addp.click)
    unp.clicked.connect(
        lambda: (
            rpc.call(
                "memory.unpin",
                {
                    "session_id": sid(),
                    "pin_id": pins.currentItem().data(Qt.ItemDataRole.UserRole) if pins.currentItem() else "",
                },
            ),
            refresh_mem(),
        )
    )
    summ.clicked.connect(lambda: (rpc.call("memory.summarize", {"session_id": sid()}), refresh_mem()))
    exp.clicked.connect(
        lambda: QMessageBox.information(
            win, "Export", json.dumps(rpc.call("session.export", {"session_id": sid()}), indent=2)
        )
    )
    clr.clicked.connect(lambda: (rpc.call("memory.clear", {"session_id": sid(), "scope": "working"}), refresh_mem()))
    forget.clicked.connect(
        lambda: (
            rpc.call(
                "memory.forget_solved",
                {
                    "session_id": sid(),
                    "solved_id": solved.currentItem().data(Qt.ItemDataRole.UserRole) if solved.currentItem() else "",
                },
            ),
            refresh_mem(),
        )
    )
    tabs.addTab(mem, theme_icon("pin", "bookmark-new"), "Memory")

    sk = QWidget()
    sl = QVBoxLayout(sk)
    sl.setContentsMargins(8, 12, 8, 8)
    sl.setSpacing(8)
    sl.addWidget(_heading("Skills (max 3 enabled)"))
    sk_hint = QLabel("Enabled skills are injected into the prompt. Shipped skills cannot be removed.")
    sk_hint.setWordWrap(True)
    _muted(sk_hint)
    sl.addWidget(sk_hint)
    split = QSplitter(Qt.Orientation.Vertical)
    slist = QListWidget()
    slist.setAccessibleName("Skills")
    slist.setAlternatingRowColors(True)
    detail = QPlainTextEdit()
    detail.setReadOnly(True)
    detail.setAccessibleName("Skill body")
    detail.setPlaceholderText("Select a skill to read its instructions.")
    split.addWidget(slist)
    split.addWidget(detail)
    split.setStretchFactor(0, 1)
    split.setStretchFactor(1, 1)
    sl.addWidget(split, 1)
    sk_row = QHBoxLayout()
    ten = QPushButton("Toggle enabled")
    inst = QPushButton("Install…")
    inst.setAccessibleName("Install skill")
    rem = QPushButton("Remove user skill")
    rem.setAccessibleName("Remove user skill")
    sk_row.addWidget(ten)
    sk_row.addWidget(inst)
    sk_row.addWidget(rem)
    sk_row.addStretch()
    sl.addLayout(sk_row)

    def refresh_sk() -> None:
        current = slist.currentItem().data(Qt.ItemDataRole.UserRole) if slist.currentItem() else None
        slist.clear()
        for row_ in rpc.call("skills.list", {"session_id": sid()}):
            name = row_.get("name") or row_["id"]
            state = "on" if row_["enabled"] else "off"
            src = row_.get("source") or "shipped"
            item = QListWidgetItem(f"{name}  ·  {state}  ·  {src}")
            item.setData(Qt.ItemDataRole.UserRole, row_["id"])
            item.setToolTip(row_.get("description") or "")
            slist.addItem(item)
            if current and row_["id"] == current:
                slist.setCurrentItem(item)

    def show_skill() -> None:
        item = slist.currentItem()
        if not item:
            detail.clear()
            return
        sid_ = item.data(Qt.ItemDataRole.UserRole)
        try:
            info = rpc.call("skills.get", {"id": sid_})
            fm = info.get("frontmatter") or {}
            body = info.get("body") or ""
            detail.setPlainText(f"{fm.get('name') or sid_}\n{fm.get('description') or ''}\n\n{body}".strip())
        except RpcError as exc:
            detail.setPlainText(f"{exc.code}: {exc.message}")

    def toggle_sk() -> None:
        item = slist.currentItem()
        if not item:
            return
        sid_ = item.data(Qt.ItemDataRole.UserRole)
        on = "off" in item.text()
        rpc.call("skills.set_enabled", {"id": sid_, "enabled": on, "session_id": sid()})
        refresh_sk()

    def install_sk() -> None:
        path, _ = QFileDialog.getOpenFileName(win, "Install user skill", "", "Skill (SKILL.md)")
        if not path:
            return
        try:
            rpc.call("skills.install", {"path": path})
            refresh_sk()
        except RpcError as exc:
            QMessageBox.warning(win, "Install", f"{exc.code}: {exc.message}")

    ten.clicked.connect(toggle_sk)
    inst.clicked.connect(install_sk)
    rem.clicked.connect(
        lambda: (
            rpc.call("skills.remove", {"id": slist.currentItem().data(Qt.ItemDataRole.UserRole)})
            if slist.currentItem()
            else None,
            refresh_sk(),
        )
    )
    slist.currentItemChanged.connect(lambda *_: show_skill())
    slist.itemDoubleClicked.connect(lambda *_: toggle_sk())
    tabs.addTab(sk, theme_icon("applications-development", "games-config-custom"), "Skills")

    cfgp = QWidget()
    cfl = QVBoxLayout(cfgp)
    cfl.setContentsMargins(8, 12, 8, 8)
    cfl.setSpacing(12)
    cfl.addWidget(_heading("Agent configuration"))
    form = QFormLayout()
    form.setSpacing(10)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    enabled = QCheckBox("Run the local agent")
    enabled.setAccessibleName("Agent enabled")
    rag = QCheckBox("Search man pages and local docs")
    rag.setAccessibleName("RAG enabled")
    force = QCheckBox("Force run during GPU pause (unsafe)")
    force.setAccessibleName("Force run during pause")
    idle = QSpinBox()
    idle.setRange(5, 120)
    idle.setValue(15)
    idle.setSuffix(" s")
    idle.setAccessibleName("Idle unload seconds")
    form.addRow("Agent", enabled)
    form.addRow("RAG", rag)
    form.addRow("GPU yield", force)
    form.addRow("Idle unload", idle)
    shortcut = QKeySequenceEdit()
    shortcut.setAccessibleName("Open window shortcut")
    form.addRow("Open window", shortcut)
    cfl.addLayout(form)
    cfl.addWidget(_heading("GPU"))
    gpu_help = QLabel(
        "The agent pauses while another CUDA app uses the GPU. Names below are "
        "process fragments that may share the GPU (one per line)."
    )
    gpu_help.setWordWrap(True)
    _muted(gpu_help)
    cfl.addWidget(gpu_help)
    allow = QPlainTextEdit()
    allow.setPlaceholderText("kwin\nfirefox\ndiscord")
    allow.setAccessibleName("GPU allow list")
    allow.setFixedHeight(120)
    deny = QPlainTextEdit()
    deny.setPlaceholderText("comfy\nblender\nsteam")
    deny.setAccessibleName("GPU denylist")
    deny.setFixedHeight(90)
    cfl.addWidget(QLabel("Don't pause for"))
    cfl.addWidget(allow)
    deny_help = QLabel("Regexes matched against process command lines (one per line).")
    deny_help.setWordWrap(True)
    _muted(deny_help)
    cfl.addWidget(QLabel("Always pause for"))
    cfl.addWidget(deny_help)
    cfl.addWidget(deny)
    cfg_row = QHBoxLayout()
    save = QPushButton("Save")
    save.setAccessibleName("Save config")
    save.setDefault(True)
    reindex = QPushButton("Rebuild search index")
    reindex.setAccessibleName("Rebuild search index")
    cfg_row.addWidget(save)
    cfg_row.addWidget(reindex)
    cfg_row.addStretch()
    cfl.addLayout(cfg_row)
    cfl.addStretch()

    def load_cfg() -> None:
        c = rpc.call("config.get")
        enabled.setChecked(bool(c["daemon"]["enabled"]))
        rag.setChecked(bool(c["rag"]["enabled"]))
        force.setChecked(bool(c["daemon"]["force_run_during_pause"]))
        idle.setValue(int(c["daemon"].get("idle_unload_s") or 15))
        shortcut.setKeySequence(QKeySequence(str((c.get("plasma") or {}).get("global_shortcut") or "")))
        gpu = c.get("gpu") or {}
        allow.setPlainText("\n".join(str(x) for x in (gpu.get("graphics_allow") or []) if str(x).strip()))
        deny.setPlainText("\n".join(str(x) for x in (gpu.get("denylist") or []) if str(x).strip()))

    def save_cfg() -> None:
        if force.isChecked():
            QMessageBox.warning(win, "GPU", "Force-run during pause can contend with other CUDA apps.")
        rpc.call(
            "config.set",
            {
                "patch": {
                    "daemon.enabled": enabled.isChecked(),
                    "rag.enabled": rag.isChecked(),
                    "daemon.force_run_during_pause": force.isChecked(),
                    "daemon.idle_unload_s": idle.value(),
                    "plasma.global_shortcut": shortcut.keySequence().toString(QKeySequence.PortableText),
                    "gpu.graphics_allow": allow.toPlainText(),
                    "gpu.denylist": deny.toPlainText(),
                }
            },
        )
        apply_status()

    def do_reindex() -> None:
        try:
            res = rpc.call("rag.reindex", {"force": True})
            QMessageBox.information(win, "RAG", json.dumps(res, indent=2))
        except RpcError as exc:
            QMessageBox.warning(win, "RAG", f"{exc.code}: {exc.message}")

    save.clicked.connect(save_cfg)
    reindex.clicked.connect(do_reindex)
    tabs.addTab(cfgp, theme_icon("configure", "preferences-system"), "Config")

    def on_tab(i: int) -> None:
        apply_status()
        if i == 1:
            refresh_mem()
        if i == 2:
            refresh_sk()
        if i == 3:
            load_cfg()

    tabs.currentChanged.connect(on_tab)
    refresh_sessions()
    if sessions.count():
        on_session(sessions.currentIndex())
    load_cfg()
    refresh_mem()
    refresh_sk()
    apply_status()
    if slist.count():
        slist.setCurrentRow(0)
    win.resize(760, 680)
    win.show()
    code = app.exec()
    rpc.close()
    raise SystemExit(code)


if __name__ == "__main__":
    main()
