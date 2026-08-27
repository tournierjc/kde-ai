from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_packaging_files_exist():
    required = [
        "packaging/systemd/kde-ai-agent.service",
        "packaging/systemd/kde-ai-reindex.timer",
        "packaging/cachyos/PKGBUILD",
        "packaging/flatpak/org.kde.kdeai.yml",
        "packaging/org.kde.kdeai.metainfo.xml",
        "packaging/org.kde.kdeai.desktop",
        "plasma/plasmoid/metadata.json",
        "plasma/krunner/plasma-runner-kdeai.desktop",
        "plasma/kcm/metadata.json",
        "plasma/dbus-shim/CMakeLists.txt",
        "scripts/install.sh",
        "scripts/fetch-gguf.sh",
        "scripts/build_dataset.sh",
        "training/train_sft.py",
        "training/train_dpo.py",
        "training/export_gguf.sh",
        "training/merge_lora.py",
        "scripts/setup-plasma-shortcut.sh",
    ]
    for rel in required:
        assert (REPO / rel).is_file(), rel


def test_desktop_shortcut_opens_toggle():
    desktop = (REPO / "packaging/org.kde.kdeai.desktop").read_text(encoding="utf-8")
    assert "Exec=kde-ai-toggle" in desktop
    assert "X-KDE-Shortcuts" not in desktop
    assert "Meta+Shift+A" not in desktop


def test_setup_script_restores_plasma_previous_activity():
    script = (REPO / "scripts/setup-plasma-shortcut.sh").read_text(encoding="utf-8")
    assert "previous activity" in script
    assert "none,none,KDE AI" in script
    assert "org.kde.kdeai.desktop" in script
    assert "Meta+Shift+A,none" in script


def test_toggle_raises_existing_plasmawindowed():
    src = (REPO / "src/kde_ai/toggle.py").read_text(encoding="utf-8")
    assert "_activate_existing" in src
    assert "org.kde.kdeai" in src
    assert "plasmawindowed" in src


def test_config_page_has_customizable_shortcut():
    qml = (REPO / "plasma/plasmoid/contents/ui/pages/ConfigPage.qml").read_text(encoding="utf-8")
    assert "KeySequenceItem" in qml
    assert "shortcut " in qml
    assert "onKeySequenceModified" in qml
    assert "Méta" in qml
    assert "invent.token" not in qml
    assert "enable-linger" not in qml


def test_pkgbuild_requires_llama_cpp():
    pkg = (REPO / "packaging/cachyos/PKGBUILD").read_text(encoding="utf-8")
    assert "llama-cpp" in pkg
    depends = [ln for ln in pkg.splitlines() if ln.startswith("depends=")][0]
    assert "llama-cpp" in depends


def test_chat_page_shows_reply_text_not_stream_id():
    qml = (REPO / "plasma/plasmoid/contents/ui/pages/ChatPage.qml").read_text(encoding="utf-8")
    assert "chatReply" in qml
    assert "r.text" in qml
    send = qml.split("function send()")[1].split("function chatReply")[0]
    assert "JSON.stringify(r)" not in send
    assert "isVisibleChat" in qml
    assert "role === \"tool\"" in qml


def test_exec_rpc_queues_commands():
    qml = (REPO / "plasma/plasmoid/contents/ui/ExecRpc.qml").read_text(encoding="utf-8")
    assert "_queue" in qml
    assert "_kick" in qml


def test_session_dialogs_keep_fields_inside():
    qml = (REPO / "plasma/plasmoid/contents/ui/pages/ChatPage.qml").read_text(encoding="utf-8")
    assert "PromptDialog" in qml
    assert "width: Kirigami.Units.gridUnit * 18" not in qml
    assert "Layout.fillWidth: true" in qml
    delete = qml.split("id: delDlg")[1].split("function send()")[0]
    assert "function confirm()" in delete
    assert "Qt.Key_Return" in delete
    assert 'text: "OK"' in delete
    assert "forceActiveFocus" in delete
    assert "enabled: !delDlg.visible" in qml
