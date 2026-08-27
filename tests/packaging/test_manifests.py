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
    ]
    for rel in required:
        assert (REPO / rel).is_file(), rel
