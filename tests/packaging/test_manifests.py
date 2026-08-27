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
    assert "X-KDE-Shortcuts=Meta+Shift+A" in desktop


def test_pkgbuild_requires_llama_cpp():
    pkg = (REPO / "packaging/cachyos/PKGBUILD").read_text(encoding="utf-8")
    assert "llama-cpp" in pkg
    depends = [ln for ln in pkg.splitlines() if ln.startswith("depends=")][0]
    assert "llama-cpp" in depends
