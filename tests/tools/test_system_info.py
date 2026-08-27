from __future__ import annotations

from pathlib import Path

from kde_ai.tools.system_info import (
    apply_edid,
    collect_monitors,
    handle,
    monitors_from_drm,
    monitors_from_kscreen_doctor,
    monitors_from_kscreen_json,
    parse_edid,
    prefer_hardware_reply,
)

KSCREEN_JSON = {
    "outputs": [
        {
            "name": "DP-1",
            "connected": True,
            "enabled": True,
            "priority": 1,
            "currentModeId": "2",
            "scale": 1.25,
            "size": {"width": 3840, "height": 2160},
            "modes": [
                {"id": "1", "name": "3840x2160@60"},
                {"id": "2", "name": "3840x2160@120"},
            ],
        },
        {
            "name": "HDMI-A-1",
            "connected": True,
            "enabled": True,
            "priority": 2,
            "currentModeId": "33",
            "scale": 1.25,
            "size": {"width": 3840, "height": 2160},
            "modes": [{"id": "33", "name": "3840x2160@60"}],
        },
        {
            "name": "DP-2",
            "connected": False,
            "enabled": False,
            "priority": 0,
            "currentModeId": "",
            "modes": [],
        },
    ]
}

DOCTOR = """\x1b[01;32mOutput: \x1b[0;0m1 DP-1 uuid
	\x1b[01;32menabled\x1b[0;0m
	\x1b[01;32mconnected\x1b[0;0m
	\x1b[01;32mpriority 1\x1b[0;0m
	\x1b[01;34mModes: \x1b[0;0m 1:3840x2160@60.00!  2:\x1b[01;32m3840x2160@119.91*\x1b[0;0m
	\x1b[01;33mScale: \x1b[0;0m1.25
Output: 2 HDMI-A-1 other
	enabled
	connected
	priority 2
	Modes:  33:3840x2160@60.00*!
	Scale: 1.25
"""


def test_kscreen_json_skips_disconnected():
    mons = monitors_from_kscreen_json(KSCREEN_JSON)
    assert [m["name"] for m in mons] == ["DP-1", "HDMI-A-1"]
    assert mons[0]["primary"] is True
    assert mons[0]["resolution"] == "3840x2160"
    assert mons[0]["refresh_hz"] == 120
    assert mons[0]["connector"] == "DisplayPort"
    assert mons[1]["connector"] == "HDMI"
    assert mons[1]["primary"] is False


def test_kscreen_doctor_strips_ansi_and_star_mode():
    mons = monitors_from_kscreen_doctor(DOCTOR)
    assert len(mons) == 2
    assert mons[0]["name"] == "DP-1"
    assert mons[0]["resolution"] == "3840x2160"
    assert mons[0]["refresh_hz"] == 119.91
    assert mons[0]["primary"] is True
    assert mons[1]["resolution"] == "3840x2160"


def test_drm_connected_only(tmp_path: Path):
    def add(name: str, status: str, enabled: str, mode: str) -> None:
        d = tmp_path / name
        d.mkdir()
        (d / "status").write_text(status + "\n", encoding="utf-8")
        (d / "enabled").write_text(enabled + "\n", encoding="utf-8")
        (d / "modes").write_text(mode + "\n", encoding="utf-8")

    add("card1-DP-1", "connected", "enabled", "3840x2160")
    add("card1-DP-2", "disconnected", "disabled", "")
    add("card1-HDMI-A-1", "connected", "enabled", "1920x1080")
    mons = monitors_from_drm(tmp_path)
    assert [m["name"] for m in mons] == ["DP-1", "HDMI-A-1"]
    assert mons[0]["resolution"] == "3840x2160"
    assert mons[1]["connector"] == "HDMI"


def test_collect_monitors_falls_back_to_drm(tmp_path: Path):
    drm = tmp_path / "drm"
    conn = drm / "card0-eDP-1"
    conn.mkdir(parents=True)
    (conn / "status").write_text("connected\n", encoding="utf-8")
    (conn / "enabled").write_text("enabled\n", encoding="utf-8")
    (conn / "modes").write_text("1920x1080\n", encoding="utf-8")

    def run(argv, timeout=8):
        del timeout
        return {"ok": False, "stdout": "", "stderr": "missing", "code": 127}

    mons = collect_monitors(run=run, drm_root=drm)
    assert len(mons) == 1
    assert mons[0]["name"] == "eDP-1"


def test_nvidia_smi_l_strips_uuid():
    from kde_ai.tools.system_info import _gpus_nvidia_smi

    def run(argv, timeout=8):
        del timeout
        if "--query-gpu" in argv:
            return {"ok": False, "stdout": "", "stderr": "", "code": 1}
        return {
            "ok": True,
            "stdout": "GPU 0: NVIDIA GeForce RTX 3090 (UUID: GPU-41aa7482-dead-beef)\n",
            "stderr": "",
            "code": 0,
        }

    gpus = _gpus_nvidia_smi(run=run)
    assert gpus[0]["name"] == "NVIDIA GeForce RTX 3090"


def test_handle_puts_gpu_and_monitors_first(monkeypatch):
    from kde_ai.tools import system_info as mod

    monkeypatch.setattr(
        mod,
        "collect_gpus",
        lambda run=None: [{"name": "NVIDIA GeForce RTX 3090", "vram_mb": 24576, "vram_used_mb": 2000, "driver": "610.57"}],
    )
    monkeypatch.setattr(
        mod,
        "collect_monitors",
        lambda run=None, drm_root=None: [
            {
                "name": "DP-1",
                "connected": True,
                "enabled": True,
                "primary": True,
                "resolution": "3840x2160",
                "refresh_hz": 120,
                "scale": 1.25,
                "connector": "DisplayPort",
            },
            {
                "name": "HDMI-A-1",
                "connected": True,
                "enabled": True,
                "primary": False,
                "resolution": "3840x2160",
                "refresh_hz": 60,
                "scale": 1.25,
                "connector": "HDMI",
            },
        ],
    )
    monkeypatch.setattr(
        mod,
        "run_argv",
        lambda argv, timeout=5: {"ok": True, "stdout": "plasmashell 6.7.4\n", "stderr": "", "code": 0},
    )
    monkeypatch.setattr(mod, "_qt_version", lambda run=None: "6.11.2")
    monkeypatch.setattr(mod, "_session", lambda: "wayland")
    monkeypatch.setattr(mod, "_os_release", lambda: {"ID": "cachyos", "PRETTY_NAME": "CachyOS"})

    payload = handle({}, None)
    keys = list(payload)
    assert keys[:5] == ["ok", "summary", "gpu", "gpus", "monitor_count"]
    assert payload["monitor_count"] == 2
    assert "RTX 3090" in payload["gpu"]
    assert "24576 MiB" in payload["gpu"]
    assert payload["summary"].startswith("2 monitors")
    assert "RTX 3090" in payload["summary"]
    assert "ANSI_COLOR" not in str(payload.get("os_release"))


def test_prefer_hardware_reply_fills_missing_facts():
    from kde_ai.tools.system_info import prefer_hardware_reply

    payload = {
        "ok": True,
        "summary": "2 monitors (DP-1 3840x2160@120Hz primary); GPU NVIDIA GeForce RTX 3090 (24576 MiB)",
        "gpu": "NVIDIA GeForce RTX 3090 (24576 MiB, driver 610.57)",
        "monitor_count": 2,
    }
    assert "2 monitors" in prefer_hardware_reply("How many monitors?", "I am not sure.", payload)
    assert "RTX 3090" in prefer_hardware_reply("What GPU do I have?", "Your GPU is fine.", payload)
    kept = "You have 2 monitors on an NVIDIA GeForce RTX 3090."
    assert prefer_hardware_reply("GPU and monitors please", kept, payload) == kept


def test_prefer_hardware_reply_monitor_brand_followup():
    payload = {
        "ok": True,
        "summary": "2 monitors (Acer XB273K GP on DP-1; ASUS MG28U on HDMI-A-1)",
        "gpu": "NVIDIA GeForce RTX 3090 (24576 MiB)",
        "monitor_count": 2,
        "monitors": [
            {"name": "DP-1", "brand": "Acer", "model": "XB273K GP", "primary": True},
            {"name": "HDMI-A-1", "brand": "ASUS", "model": "MG28U", "primary": False},
        ],
    }
    history = [
        {"role": "user", "content": "how many monitor do i have"},
        {"role": "assistant", "content": "I have 2 monitors."},
        {"role": "user", "content": "can you give me their brand"},
    ]
    got = prefer_hardware_reply(
        "can you give me their brand",
        "I do not have information about the brand of the monitors.",
        payload,
        history,
    )
    assert "Acer" in got and "ASUS" in got


def test_parse_limine_cmdline_appends_dropins():
    from kde_ai.tools.system_info import parse_limine_cmdline

    acc = parse_limine_cmdline(
        'KERNEL_CMDLINE[default]+="quiet nowatchdog splash rw rootflags=subvol=/@"\n'
    )
    acc = parse_limine_cmdline(
        "KERNEL_CMDLINE[default]+=nvidia_drm.modeset=1 nvidia_drm.fbdev=1\n"
        "KERNEL_CMDLINE[default]+=video=DP-1:D\n",
        acc,
    )
    assert "quiet" in acc["default"]
    assert "nvidia_drm.modeset=1" in acc["default"]
    assert "video=DP-1:D" in acc["default"]


def test_collect_kernel_cmdline_prefers_proc(tmp_path: Path):
    from kde_ai.tools.system_info import collect_kernel_cmdline

    proc = tmp_path / "cmdline"
    proc.write_text("quiet splash nvidia_drm.modeset=1\n", encoding="utf-8")
    default = tmp_path / "limine"
    default.write_text('KERNEL_CMDLINE[default]+="quiet splash extra=1"\n', encoding="utf-8")
    drop = tmp_path / "d"
    drop.mkdir()
    (drop / "nvidia.conf").write_text(
        "KERNEL_CMDLINE[default]+=nvidia_drm.modeset=1\n",
        encoding="utf-8",
    )
    got = collect_kernel_cmdline(proc_path=proc, limine_default=default, limine_dropin=drop)
    assert got["kernel_cmdline"] == "quiet splash nvidia_drm.modeset=1"
    assert "extra=1" in got["kernel_cmdline_configured"]
    assert "nvidia_drm.modeset=1" in got["kernel_cmdline_configured"]


def test_prefer_hardware_reply_kernel_cmdline_not_version():
    from kde_ai.tools.system_info import prefer_hardware_reply

    payload = {
        "ok": True,
        "kernel": "7.2.0-1-cachyos",
        "kernel_cmdline": "quiet nowatchdog splash nvidia_drm.modeset=1 nvidia_drm.fbdev=1",
        "kernel_cmdline_configured": "quiet nowatchdog splash nvidia_drm.modeset=1",
        "summary": "2 monitors; GPU NVIDIA",
    }
    got = prefer_hardware_reply(
        "what are my kernel parameters forced at startup",
        "At startup, your kernel parameters are forced to be 7.2.0-1-cachyos.",
        payload,
    )
    assert "7.2.0-1-cachyos" not in got
    assert "nvidia_drm.modeset=1" in got
    assert "/proc/cmdline" in got
    partial = prefer_hardware_reply(
        "what are my kernel parameters forced at startup",
        "At startup, your kernel parameters are configured as follows:\nnvidia_drm.modeset=1\nnvidia_drm.fbdev=1",
        payload,
    )
    assert "quiet" in partial and "nowatchdog" in partial


def test_collect_cpu_and_ram(tmp_path: Path):
    from kde_ai.tools.system_info import collect_cpu, collect_ram

    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text(
        "processor\t: 0\n"
        "model name\t: AMD Ryzen 9 5900X 12-Core Processor\n"
        "siblings\t: 24\n"
        "cpu cores\t: 12\n",
        encoding="utf-8",
    )
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal:       32771268 kB\nMemFree: 1234 kB\n", encoding="utf-8")
    cpu = collect_cpu(cpuinfo)
    assert cpu["cpu"] == "AMD Ryzen 9 5900X 12-Core Processor"
    assert cpu["cpu_cores"] == 12
    assert cpu["cpu_threads"] == 24
    assert collect_ram(meminfo)["ram_mb"] == 32771268 // 1024


def test_is_hardware_question_covers_linux_facts():
    from kde_ai.tools.system_info import is_hardware_question

    assert is_hardware_question("What Plasma version am I on?")
    assert is_hardware_question("What kernel version am I running?")
    assert is_hardware_question("What distro is this?")
    assert is_hardware_question("What CPU do I have?")
    assert is_hardware_question("How much RAM do I have?")
    assert is_hardware_question("Am I on Wayland or X11?")
    assert is_hardware_question("What is my hostname?")
    assert is_hardware_question("What motherboard do I have?")
    assert is_hardware_question("What Qt version?")
    assert not is_hardware_question("How do I restart plasmashell?")
    from kde_ai.tools.system_info import is_hardware_lookup

    assert is_hardware_lookup("What Qt version?")
    assert is_hardware_lookup("How much RAM do I have?")
    assert not is_hardware_lookup("My GPU driver crashes after login")


FULL_HW = {
    "ok": True,
    "summary": "2 monitors; GPU NVIDIA GeForce RTX 3090",
    "gpu": "NVIDIA GeForce RTX 3090 (24576 MiB, driver 610.57)",
    "monitor_count": 2,
    "monitors": [
        {"name": "DP-1", "brand": "Acer", "model": "XB273K GP"},
        {"name": "HDMI-A-1", "brand": "ASUS", "model": "ASUS MG28U"},
    ],
    "plasma": "plasmashell 6.7.4",
    "qt": "6.11.2",
    "session": "wayland",
    "distro": "CachyOS",
    "kernel": "7.2.0-1-cachyos",
    "kernel_cmdline": "quiet nowatchdog splash nvidia_drm.modeset=1",
    "cpu": "AMD Ryzen 9 5900X 12-Core Processor",
    "cpu_cores": 12,
    "cpu_threads": 24,
    "ram_mb": 31999,
    "hostname": "jct-desktop",
    "board": "MPG X570 GAMING PRO CARBON WIFI (MS-7B93)",
    "board_vendor": "Micro-Star International Co., Ltd.",
}


def test_prefer_hardware_reply_linux_and_machine_facts():
    from kde_ai.tools.system_info import prefer_hardware_reply

    p = FULL_HW
    assert "6.7.4" in prefer_hardware_reply("What Plasma version am I on?", "Plasma 5.27.", p)
    kernel = prefer_hardware_reply("What kernel version am I running?", "You are on kernel 6.12.", p)
    assert "7.2.0-1-cachyos" in kernel
    assert "nvidia_drm" not in kernel
    leaked = prefer_hardware_reply(
        "What kernel version am I running?",
        "Kernel version: 7.2.0-1-cachyos\nKernel_cmdline: quiet nvidia_drm.modeset=1",
        p,
    )
    assert leaked.strip() == "Kernel version: 7.2.0-1-cachyos."
    assert "CachyOS" in prefer_hardware_reply("What distro is this?", "Ubuntu 24.04.", p)
    cpu = prefer_hardware_reply("What CPU do I have?", "Intel Core i5.", p)
    assert "5900X" in cpu
    cores = prefer_hardware_reply("How many cores does my CPU have?", "8 cores.", p)
    assert "12" in cores
    assert "2 monitor" not in cores.lower()
    ram = prefer_hardware_reply("How much RAM do I have?", "8 GB of memory.", p)
    assert "31" in ram
    assert "wayland" in prefer_hardware_reply("Am I on Wayland or X11?", "You are on X11.", p).lower()
    assert "jct-desktop" in prefer_hardware_reply("What is my hostname?", "localhost", p)
    assert "6.11.2" in prefer_hardware_reply("What Qt version?", "Qt 5.15", p)
    board = prefer_hardware_reply("What motherboard do I have?", "ASUS unknown", p)
    assert "X570" in board or "7B93" in board


def test_handle_includes_cpu_ram_distro(monkeypatch):
    from kde_ai.tools import system_info as mod

    monkeypatch.setattr(mod, "collect_gpus", lambda run=None: [])
    monkeypatch.setattr(mod, "collect_monitors", lambda run=None, drm_root=None: [])
    monkeypatch.setattr(
        mod,
        "run_argv",
        lambda argv, timeout=5: {"ok": True, "stdout": "plasmashell 6.7.4\n", "stderr": "", "code": 0},
    )
    monkeypatch.setattr(mod, "_qt_version", lambda run=None: "6.11.2")
    monkeypatch.setattr(mod, "_session", lambda: "wayland")
    monkeypatch.setattr(mod, "_os_release", lambda: {"ID": "cachyos", "PRETTY_NAME": "CachyOS"})
    monkeypatch.setattr(
        mod, "collect_cpu", lambda cpuinfo_path=None: {"cpu": "AMD Ryzen 9 5900X 12-Core Processor", "cpu_cores": 12, "cpu_threads": 24}
    )
    monkeypatch.setattr(mod, "collect_ram", lambda meminfo_path=None: {"ram_mb": 31999})
    monkeypatch.setattr(
        mod,
        "collect_board",
        lambda vendor_path=None, name_path=None, product_path=None: {
            "board_vendor": "Micro-Star International Co., Ltd.",
            "board": "MPG X570 GAMING PRO CARBON WIFI (MS-7B93)",
        },
    )
    payload = handle({}, None)
    assert payload["cpu"].startswith("AMD Ryzen 9 5900X")
    assert payload["ram_mb"] == 31999
    assert payload["distro"] == "CachyOS"
    assert "5900X" in payload["summary"]
    assert "31 GiB" in payload["summary"]
    assert "CachyOS" in payload["summary"]


EDID_ACER = bytes.fromhex(
    "00ffffffffffff0004721c07d58f3211"
    "0d1f0104b53c22783b3ad5ae4e43aa26"
    "0b50542348008140818081c081009500"
    "b300d1c001014dd000a0f0703e803020"
    "350055502100001ab46600a0f0701f80"
    "0820180455502100001a000000fd0c30"
    "90ffff6b010a202020202020000000fc"
    "0058423237334b2047500a202020027e"
)
EDID_ASUS = bytes.fromhex(
    "00ffffffffffff000469a7288fab0100"
    "321c0103803e22783a08a5a2574fa228"
    "0f5054bfef00d1c0814081809500b300"
    "81c08100714f08e80030f2705a80b058"
    "8a006d552100001e04740030f2705a80"
    "b0588a006d552100001a000000fd0017"
    "5018a03c000a202020202020000000fc"
    "0041535553204d473238550a202001f4"
)


def test_parse_edid_brand_and_model():
    acer = parse_edid(EDID_ACER)
    assert acer["manufacturer_id"] == "ACR"
    assert acer["brand"] == "Acer"
    assert acer["model"] == "XB273K GP"
    asus = parse_edid(EDID_ASUS)
    assert asus["manufacturer_id"] == "ACI"
    assert asus["brand"] == "ASUS"
    assert asus["model"] == "ASUS MG28U"


def test_apply_edid_matches_connector_names(tmp_path: Path):
    dp = tmp_path / "card1-DP-1"
    dp.mkdir()
    (dp / "status").write_text("connected\n", encoding="utf-8")
    (dp / "edid").write_bytes(EDID_ACER)
    hdmi = tmp_path / "card1-HDMI-A-1"
    hdmi.mkdir()
    (hdmi / "status").write_text("connected\n", encoding="utf-8")
    (hdmi / "edid").write_bytes(EDID_ASUS)
    mons = apply_edid(
        [{"name": "DP-1", "connected": True}, {"name": "HDMI-A-1", "connected": True}],
        tmp_path,
    )
    assert mons[0]["brand"] == "Acer" and mons[0]["model"] == "XB273K GP"
    assert mons[1]["brand"] == "ASUS" and "MG28U" in mons[1]["model"]
