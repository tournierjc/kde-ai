"""Four-page Qt UI (Flatpak / standalone) over the same JSON-RPC socket as the CLI."""

from __future__ import annotations

import json
import os
import sys

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


def main() -> None:
    try:
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QListWidget,
            QMessageBox,
            QPlainTextEdit,
            QPushButton,
            QTabWidget,
            QVBoxLayout,
            QWidget,
        )
    except ImportError:
        print("PySide6 is required for kde-ai-ui. Use: kde-ai  (CLI)", file=sys.stderr)
        raise SystemExit(2)

    app = QApplication(sys.argv)
    rpc = _connect()
    win = QWidget()
    win.setWindowTitle("KDE AI")
    root = QVBoxLayout(win)
    tabs = QTabWidget()
    tabs.setAccessibleName("KDE AI pages")
    root.addWidget(tabs)

    # --- Chat ---
    chat = QWidget()
    cl = QVBoxLayout(chat)
    transcript = QPlainTextEdit()
    transcript.setReadOnly(True)
    transcript.setAccessibleName("Chat transcript")
    entry = QLineEdit()
    entry.setPlaceholderText("Message")
    entry.setAccessibleName("Chat input")
    send = QPushButton("Send")
    yes = QPushButton("Yes")
    yes.setAccessibleName("Problem solved yes")
    no = QPushButton("No")
    no.setAccessibleName("Problem solved no")
    row = QHBoxLayout()
    row.addWidget(entry)
    row.addWidget(send)
    row.addWidget(yes)
    row.addWidget(no)
    cl.addWidget(transcript)
    cl.addLayout(row)

    def sid() -> str:
        st = rpc.call("status.get")
        if st.get("active_session_id"):
            return st["active_session_id"]
        return rpc.call("session.create", {"title": "General"})["session_id"]

    def do_send():
        msg = entry.text().strip()
        if not msg:
            return
        transcript.appendPlainText("> " + msg)
        entry.clear()
        try:
            rpc.call("chat.send", {"session_id": sid(), "message": msg})
        except RpcError as exc:
            transcript.appendPlainText(f"{exc.code}: {exc.message}")
            return
        import time

        for _ in range(400):
            rpc.drain(0.15)
            for n in rpc.notifications:
                if n.get("method") == "stream.token":
                    transcript.appendPlainText(n["params"].get("text") or "")
                if n.get("method") == "issue.awaiting":
                    transcript.appendPlainText("Awaiting yes/no for proposed solution.")
            if any(n.get("method") == "stream.done" for n in rpc.notifications):
                break
            time.sleep(0.05)
        rpc.notifications.clear()

    def confirm(solved: bool):
        sess = next(s for s in rpc.call("session.list", {}) if s["id"] == sid())
        rpc.call(
            "issue.confirm",
            {"session_id": sid(), "attempt_id": sess.get("open_attempt_id"), "solved": solved},
        )
        transcript.appendPlainText("saved" if solved else "retry")

    send.clicked.connect(do_send)
    entry.returnPressed.connect(do_send)
    yes.clicked.connect(lambda: confirm(True))
    no.clicked.connect(lambda: confirm(False))
    tabs.addTab(chat, "Chat")

    # --- Memory ---
    mem = QWidget()
    ml = QVBoxLayout(mem)
    stats = QLabel("Token budget")
    stats.setAccessibleName("Token budget")
    pins = QListWidget()
    pins.setAccessibleName("Pins")
    pin_edit = QLineEdit()
    pin_edit.setPlaceholderText("New pin")
    solved = QListWidget()
    solved.setAccessibleName("Solved issues")
    ml.addWidget(stats)
    ml.addWidget(QLabel("Pins"))
    ml.addWidget(pins)
    ml.addWidget(pin_edit)
    brow = QHBoxLayout()
    addp = QPushButton("Pin")
    unp = QPushButton("Unpin")
    summ = QPushButton("Summarize now")
    exp = QPushButton("Export")
    clr = QPushButton("Clear working")
    for b in (addp, unp, summ, exp, clr):
        brow.addWidget(b)
    ml.addLayout(brow)
    ml.addWidget(QLabel("Solved"))
    ml.addWidget(solved)
    forget = QPushButton("Forget solved")
    ml.addWidget(forget)

    def refresh_mem():
        s = sid()
        st = rpc.call("memory.stats", {"session_id": s})
        stats.setText(json.dumps(st))
        pins.clear()
        for p in rpc.call("memory.pins", {"session_id": s}):
            pins.addItem(f"{p['id']}: {p.get('text')}")
        solved.clear()
        for row_ in rpc.call("memory.solved", {"session_id": s}):
            solved.addItem(f"{row_['id']}: {row_.get('issue')} → {row_.get('solution')}")

    addp.clicked.connect(
        lambda: (rpc.call("memory.pin", {"session_id": sid(), "text": pin_edit.text()}), refresh_mem())
    )
    unp.clicked.connect(
        lambda: (
            rpc.call(
                "memory.unpin",
                {"session_id": sid(), "pin_id": (pins.currentItem().text().split(":")[0] if pins.currentItem() else "")},
            ),
            refresh_mem(),
        )
    )
    summ.clicked.connect(lambda: (rpc.call("memory.summarize", {"session_id": sid()}), refresh_mem()))
    exp.clicked.connect(lambda: QMessageBox.information(win, "Export", json.dumps(rpc.call("session.export", {"session_id": sid()}))))
    clr.clicked.connect(lambda: (rpc.call("memory.clear", {"session_id": sid(), "scope": "working"}), refresh_mem()))
    forget.clicked.connect(
        lambda: (
            rpc.call(
                "memory.forget_solved",
                {
                    "session_id": sid(),
                    "solved_id": solved.currentItem().text().split(":")[0] if solved.currentItem() else "",
                },
            ),
            refresh_mem(),
        )
    )
    tabs.addTab(mem, "Memory")

    # --- Skills ---
    sk = QWidget()
    sl = QVBoxLayout(sk)
    slist = QListWidget()
    slist.setAccessibleName("Skills")
    sl.addWidget(slist)
    ten = QPushButton("Toggle enabled")
    inst = QPushButton("Install…")
    rem = QPushButton("Remove user skill")
    sl.addWidget(ten)
    sl.addWidget(inst)
    sl.addWidget(rem)
    detail = QPlainTextEdit()
    detail.setReadOnly(True)
    sl.addWidget(detail)

    def refresh_sk():
        slist.clear()
        for row_ in rpc.call("skills.list", {"session_id": sid()}):
            slist.addItem(f"{row_['id']} [{'on' if row_['enabled'] else 'off'}] {row_['source']}")

    def toggle_sk():
        item = slist.currentItem()
        if not item:
            return
        sid_ = item.text().split()[0]
        on = "off" in item.text()
        rpc.call("skills.set_enabled", {"id": sid_, "enabled": on, "session_id": sid()})
        refresh_sk()

    ten.clicked.connect(toggle_sk)
    inst.clicked.connect(
        lambda: QMessageBox.information(win, "Install", "kde-ai skills install /path/to/SKILL.md")
    )
    rem.clicked.connect(
        lambda: (
            rpc.call("skills.remove", {"id": slist.currentItem().text().split()[0]}) if slist.currentItem() else None,
            refresh_sk(),
        )
    )
    tabs.addTab(sk, "Skills")

    # --- Config ---
    cfgp = QWidget()
    cfl = QVBoxLayout(cfgp)
    enabled = QCheckBox("Enabled")
    enabled.setAccessibleName("Agent enabled")
    rag = QCheckBox("RAG")
    rag.setAccessibleName("RAG enabled")
    force = QCheckBox("Force run during GPU pause (unsafe)")
    cfl.addWidget(enabled)
    cfl.addWidget(rag)
    cfl.addWidget(force)
    cfl.addWidget(QLabel("Idle unload 15s · shortcut Meta+Shift+A · token file is local 0600"))
    save = QPushButton("Save config")
    cfl.addWidget(save)

    def load_cfg():
        c = rpc.call("config.get")
        enabled.setChecked(bool(c["daemon"]["enabled"]))
        rag.setChecked(bool(c["rag"]["enabled"]))
        force.setChecked(bool(c["daemon"]["force_run_during_pause"]))

    def save_cfg():
        if force.isChecked():
            QMessageBox.warning(win, "GPU", "Force-run during pause can contend with other CUDA apps.")
        rpc.call(
            "config.set",
            {
                "patch": {
                    "daemon.enabled": enabled.isChecked(),
                    "rag.enabled": rag.isChecked(),
                    "daemon.force_run_during_pause": force.isChecked(),
                }
            },
        )

    save.clicked.connect(save_cfg)
    tabs.addTab(cfgp, "Config")

    def on_tab(i):
        if i == 1:
            refresh_mem()
        if i == 2:
            refresh_sk()
        if i == 3:
            load_cfg()

    tabs.currentChanged.connect(on_tab)
    load_cfg()
    refresh_mem()
    refresh_sk()
    win.resize(640, 520)
    win.show()
    code = app.exec()
    rpc.close()
    raise SystemExit(code)


if __name__ == "__main__":
    main()
