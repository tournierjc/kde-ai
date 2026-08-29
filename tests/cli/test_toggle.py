from __future__ import annotations

from kde_ai.toggle import close_window, open_window, window_pids


def test_open_window_launches(monkeypatch):
    launched: list[list[str]] = []

    def fake_popen(argv, **kwargs):
        launched.append(list(argv))
        return None

    monkeypatch.setattr("kde_ai.toggle.window_pids", lambda: [])
    monkeypatch.setattr("kde_ai.toggle.shutil.which", lambda name: "/usr/bin/kde-ai-ui" if name == "kde-ai-ui" else None)
    monkeypatch.setattr("kde_ai.toggle.subprocess.Popen", fake_popen)
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")

    assert open_window() == 0
    assert launched == [["/usr/bin/kde-ai-ui"]]


def test_open_window_activates_existing(monkeypatch):
    activated: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        activated.append(list(cmd))
        return None

    monkeypatch.setattr("kde_ai.toggle.window_pids", lambda: [1234])
    monkeypatch.setattr("kde_ai.toggle.shutil.which", lambda name: "/usr/bin/kstart6" if name == "kstart6" else None)
    monkeypatch.setattr("kde_ai.toggle.subprocess.run", fake_run)
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")

    assert open_window() == 0
    assert activated == [["kstart6", "--activate", "org.kde.kdeai"]]
    assert close_window() is False
