from __future__ import annotations

import json
import os
import platform
import re
from pathlib import Path

from kde_ai.tools import run_argv

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_OS_KEEP = ("NAME", "PRETTY_NAME", "ID", "ID_LIKE")
_NVIDIA_LINE = re.compile(r"^GPU\s+\d+:\s+")


def _as_str(value) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value) if value is not None else ""


def _os_release() -> dict[str, str]:
    out: dict[str, str] = {}
    path = Path("/etc/os-release")
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, raw = line.split("=", 1)
        if key in _OS_KEEP:
            out[key] = raw.strip().strip('"')
    return out


_LIMINE_CMDLINE_RE = re.compile(r"^\s*KERNEL_CMDLINE\[([^\]]+)\]\s*(\+?=)\s*(.*)$")
_GRUB_CMDLINE_RE = re.compile(r"^\s*(GRUB_CMDLINE_LINUX(?:_DEFAULT)?)\s*=\s*(.*)$")


def _unquote_shell(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def parse_limine_cmdline(text: str, acc: dict[str, str] | None = None) -> dict[str, str]:
    merged: dict[str, str] = dict(acc or {})
    for raw in text.splitlines():
        line = raw.split("#", 1)[0]
        match = _LIMINE_CMDLINE_RE.match(line)
        if not match:
            continue
        key, op, val = match.group(1).strip(), match.group(2), _unquote_shell(match.group(3))
        if not val:
            if op == "=":
                merged[key] = ""
            continue
        if op == "=":
            merged[key] = val
        else:
            merged[key] = f"{merged[key]} {val}".strip() if merged.get(key) else val
    return merged


def parse_grub_cmdline(text: str) -> str:
    parts: list[str] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0]
        match = _GRUB_CMDLINE_RE.match(line)
        if not match:
            continue
        val = _unquote_shell(match.group(2))
        if val:
            parts.append(val)
    return " ".join(parts).strip()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def collect_kernel_cmdline(
    proc_path: Path | None = None,
    limine_default: Path | None = None,
    limine_dropin: Path | None = None,
    kernel_cmdline_path: Path | None = None,
    grub_path: Path | None = None,
) -> dict:
    active = _read_text(proc_path or Path("/proc/cmdline")).strip()
    acc: dict[str, str] = {}
    dropin = limine_dropin or Path("/etc/limine-entry-tool.d")
    if dropin.is_dir():
        for conf in sorted(dropin.glob("*.conf")):
            acc = parse_limine_cmdline(_read_text(conf), acc)
    default = limine_default or Path("/etc/default/limine")
    if default.is_file():
        acc = parse_limine_cmdline(_read_text(default), acc)
    configured = (acc.get("default") or "").strip()
    if not configured:
        kcmd = _read_text(kernel_cmdline_path or Path("/etc/kernel/cmdline")).strip()
        if kcmd:
            configured = kcmd
        else:
            configured = parse_grub_cmdline(_read_text(grub_path or Path("/etc/default/grub")))
    params = [p for p in active.split() if p]
    return {
        "kernel_cmdline": active,
        "kernel_cmdline_params": params,
        "kernel_cmdline_configured": configured,
    }


def collect_cpu(cpuinfo_path: Path | None = None) -> dict:
    model = ""
    cores = 0
    threads = 0
    for line in _read_text(cpuinfo_path or Path("/proc/cpuinfo")).splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip().lower()
        val = val.strip()
        if key == "model name" and not model:
            model = val
        elif key == "cpu cores" and not cores:
            try:
                cores = int(val)
            except ValueError:
                pass
        elif key == "siblings" and not threads:
            try:
                threads = int(val)
            except ValueError:
                pass
    if not threads:
        threads = os.cpu_count() or 0
    return {"cpu": model, "cpu_cores": cores, "cpu_threads": threads}


def collect_ram(meminfo_path: Path | None = None) -> dict:
    for line in _read_text(meminfo_path or Path("/proc/meminfo")).splitlines():
        if not line.startswith("MemTotal:"):
            continue
        parts = line.split()
        try:
            return {"ram_mb": int(parts[1]) // 1024}
        except (IndexError, ValueError):
            break
    return {"ram_mb": 0}


def collect_board(
    vendor_path: Path | None = None,
    name_path: Path | None = None,
    product_path: Path | None = None,
) -> dict:
    vendor = _read_text(vendor_path or Path("/sys/class/dmi/id/board_vendor")).strip()
    name = _read_text(name_path or Path("/sys/class/dmi/id/board_name")).strip()
    product = _read_text(product_path or Path("/sys/class/dmi/id/product_name")).strip()
    return {"board_vendor": vendor, "board": name or product}


def _distro_name(os_release: dict | None = None) -> str:
    rel = os_release if os_release is not None else _os_release()
    return (rel.get("PRETTY_NAME") or rel.get("NAME") or "").strip()


def _session() -> str:
    val = (os.environ.get("XDG_SESSION_TYPE") or "").strip()
    if val:
        return val
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return ""


def _qt_version(run=run_argv) -> str:
    env = os.environ.get("QT_VERSION", "").strip()
    if env:
        return env
    for argv in (
        ["qtpaths6", "--qt-version"],
        ["qtpaths", "--qt-version"],
        ["qmake6", "-query", "QT_VERSION"],
        ["qmake", "-query", "QT_VERSION"],
    ):
        got = run(argv, timeout=5)
        text = (got.get("stdout") or "").strip()
        if got.get("ok") and text:
            return text.splitlines()[0].strip()
    return ""


def _first_json_object(text: str) -> dict | None:
    candidates = [text]
    start = text.find("{")
    if start > 0:
        candidates.append(text[start:])
    for candidate in candidates:
        if not candidate.strip():
            continue
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def _mode_res_hz(mode_name: str) -> tuple[str, float | None]:
    name = (mode_name or "").strip()
    if "@" in name:
        res, hz = name.rsplit("@", 1)
        try:
            return res, round(float(hz), 2)
        except ValueError:
            return res, None
    return name, None


def _connector(name: str) -> str:
    upper = name.upper()
    if upper.startswith("EDP"):
        return "eDP"
    if upper.startswith("HDMI"):
        return "HDMI"
    if upper.startswith("DVI"):
        return "DVI"
    if upper.startswith("VGA"):
        return "VGA"
    if upper.startswith("DP") or upper.startswith("DISPLAYPORT"):
        return "DisplayPort"
    return ""


# Common EDID PNP IDs → consumer brand. Unknown codes fall back to the 3-letter ID.
_PNP_BRAND = {
    "ACR": "Acer",
    "ACI": "ASUS",
    "AUS": "ASUS",
    "AOC": "AOC",
    "APP": "Apple",
    "AUO": "AU Optronics",
    "BNQ": "BenQ",
    "BOE": "BOE",
    "CMN": "Innolux",
    "CMO": "Innolux",
    "DEL": "Dell",
    "ENC": "Eizo",
    "EIZ": "Eizo",
    "GSM": "LG",
    "HPN": "HP",
    "HWP": "HP",
    "IVM": "Iiyama",
    "LEN": "Lenovo",
    "LGD": "LG",
    "MEI": "Panasonic",
    "MSI": "MSI",
    "NEC": "NEC",
    "ONK": "Onkyo",
    "PHL": "Philips",
    "SAM": "Samsung",
    "SDC": "Samsung",
    "SEC": "Samsung",
    "SHP": "Sharp",
    "SNY": "Sony",
    "TCL": "TCL",
    "VSC": "ViewSonic",
    "VIZ": "Vizio",
}


def parse_edid(edid: bytes) -> dict:
    """Return manufacturer_id / brand / model from a raw EDID blob."""
    out = {"manufacturer_id": "", "brand": "", "model": ""}
    if not edid or len(edid) < 128:
        return out
    if edid[0:8] != b"\x00\xff\xff\xff\xff\xff\xff\x00":
        return out
    b8, b9 = edid[8], edid[9]
    chars = [
        ((b8 >> 2) & 0x1F) + 64,
        (((b8 & 0x03) << 3) | (b9 >> 5)) + 64,
        (b9 & 0x1F) + 64,
    ]
    if all(65 <= c <= 90 for c in chars):
        pnp = "".join(map(chr, chars))
        out["manufacturer_id"] = pnp
        out["brand"] = _PNP_BRAND.get(pnp, pnp)
    for off in (54, 72, 90, 108):
        block = edid[off : off + 18]
        if block[0:3] != b"\x00\x00\x00" or block[3] != 0xFC:
            continue
        name = bytes(b for b in block[5:] if 32 <= b < 127).decode("ascii").strip()
        if name:
            out["model"] = name
            break
    return out


def _drm_connector_name(dirname: str) -> str:
    if dirname.startswith("card") and "-" in dirname:
        return dirname.split("-", 1)[1]
    return dirname


def edid_by_connector(drm_root: Path | None = None) -> dict[str, dict]:
    root = drm_root or Path("/sys/class/drm")
    found: dict[str, dict] = {}
    if not root.is_dir():
        return found
    for conn in root.iterdir():
        edid_path = conn / "edid"
        status_path = conn / "status"
        if not edid_path.is_file() or not status_path.is_file():
            continue
        try:
            if status_path.read_text(encoding="utf-8").strip() != "connected":
                continue
            blob = edid_path.read_bytes()
        except OSError:
            continue
        ident = parse_edid(blob)
        if ident.get("brand") or ident.get("model"):
            found[_drm_connector_name(conn.name)] = ident
    return found


def apply_edid(monitors: list[dict], drm_root: Path | None = None) -> list[dict]:
    by_name = edid_by_connector(drm_root)
    for mon in monitors:
        ident = by_name.get(mon.get("name") or "")
        if not ident:
            continue
        if ident.get("brand"):
            mon["brand"] = ident["brand"]
        if ident.get("model"):
            mon["model"] = ident["model"]
        if ident.get("manufacturer_id"):
            mon["manufacturer_id"] = ident["manufacturer_id"]
    return monitors


def monitors_from_kscreen_json(data: dict) -> list[dict]:
    monitors: list[dict] = []
    for output in data.get("outputs") or []:
        if not output.get("connected"):
            continue
        modes = {str(m.get("id")): m for m in (output.get("modes") or [])}
        current = modes.get(str(output.get("currentModeId") or ""))
        size = output.get("size") or {}
        if current:
            resolution, refresh = _mode_res_hz(str(current.get("name") or ""))
        elif size.get("width") and size.get("height"):
            resolution, refresh = f"{size['width']}x{size['height']}", None
        else:
            resolution, refresh = "", None
        try:
            scale = float(output.get("scale") or 1)
        except (TypeError, ValueError):
            scale = 1.0
        name = str(output.get("name") or "")
        try:
            priority = int(output.get("priority") or 0)
        except (TypeError, ValueError):
            priority = 0
        monitors.append(
            {
                "name": name,
                "connected": True,
                "enabled": bool(output.get("enabled")),
                "primary": priority == 1,
                "resolution": resolution,
                "refresh_hz": refresh,
                "scale": scale,
                "connector": _connector(name),
            }
        )
    return monitors


def monitors_from_kscreen_doctor(text: str) -> list[dict]:
    text = _ANSI_RE.sub("", text)
    monitors: list[dict] = []
    current: dict | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("Output:"):
            if current:
                monitors.append(current)
            parts = line.split()
            name = parts[2] if len(parts) >= 3 else ""
            current = {
                "name": name,
                "connected": False,
                "enabled": False,
                "primary": False,
                "resolution": "",
                "refresh_hz": None,
                "scale": None,
                "connector": _connector(name),
            }
            continue
        if current is None:
            continue
        if line == "enabled":
            current["enabled"] = True
        elif line == "disabled":
            current["enabled"] = False
        elif line == "connected":
            current["connected"] = True
        elif line == "disconnected":
            current["connected"] = False
        elif line.startswith("priority "):
            try:
                current["primary"] = int(line.split()[1]) == 1
            except (IndexError, ValueError):
                pass
        elif line.startswith("Scale:"):
            try:
                current["scale"] = float(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif "Modes:" in line:
            star = re.search(r"(\d+x\d+)@([\d.]+)\*", line)
            if star:
                current["resolution"] = star.group(1)
                try:
                    current["refresh_hz"] = round(float(star.group(2)), 2)
                except ValueError:
                    current["refresh_hz"] = None
    if current:
        monitors.append(current)
    return [m for m in monitors if m.get("connected")]


def monitors_from_drm(drm_root: Path | None = None) -> list[dict]:
    root = drm_root or Path("/sys/class/drm")
    if not root.is_dir():
        return []
    monitors: list[dict] = []
    for conn in sorted(root.iterdir()):
        status_path = conn / "status"
        if not status_path.is_file():
            continue
        try:
            status = status_path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if status != "connected":
            continue
        enabled_path = conn / "enabled"
        enabled = True
        if enabled_path.is_file():
            try:
                enabled = enabled_path.read_text(encoding="utf-8").strip() == "enabled"
            except OSError:
                pass
        resolution = ""
        modes_path = conn / "modes"
        if modes_path.is_file():
            try:
                resolution = modes_path.read_text(encoding="utf-8").splitlines()[0].strip()
            except (OSError, IndexError):
                resolution = ""
        name = _drm_connector_name(conn.name)
        ident = {}
        edid_path = conn / "edid"
        if edid_path.is_file():
            try:
                ident = parse_edid(edid_path.read_bytes())
            except OSError:
                ident = {}
        mon = {
            "name": name,
            "connected": True,
            "enabled": enabled,
            "primary": False,
            "resolution": resolution,
            "refresh_hz": None,
            "scale": None,
            "connector": _connector(name),
        }
        if ident.get("brand"):
            mon["brand"] = ident["brand"]
        if ident.get("model"):
            mon["model"] = ident["model"]
        if ident.get("manufacturer_id"):
            mon["manufacturer_id"] = ident["manufacturer_id"]
        monitors.append(mon)
    return monitors


def collect_monitors(run=run_argv, drm_root: Path | None = None) -> list[dict]:
    js = run(["kscreen-console", "json"], timeout=8)
    data = _first_json_object(js.get("stdout") or "") or _first_json_object(js.get("stderr") or "")
    if data:
        found = monitors_from_kscreen_json(data)
        if found:
            return apply_edid(found, drm_root)
    doctor = run(["kscreen-doctor", "-o"], timeout=8)
    found = monitors_from_kscreen_doctor(doctor.get("stdout") or "")
    if found:
        return apply_edid(found, drm_root)
    return apply_edid(monitors_from_drm(drm_root), drm_root)


def _gpus_nvml() -> list[dict]:
    try:
        import pynvml  # type: ignore
    except Exception:
        return []
    try:
        pynvml.nvmlInit()
        driver = _as_str(pynvml.nvmlSystemGetDriverVersion())
        gpus: list[dict] = []
        for index in range(pynvml.nvmlDeviceGetCount()):
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            gpus.append(
                {
                    "name": _as_str(pynvml.nvmlDeviceGetName(handle)),
                    "vram_mb": int(mem.total // (1024 * 1024)),
                    "vram_used_mb": int(mem.used // (1024 * 1024)),
                    "driver": driver,
                }
            )
        return gpus
    except Exception:
        return []


def _gpus_nvidia_smi(run=run_argv) -> list[dict]:
    got = run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.used,driver_version",
            "--format=csv,noheader,nounits",
        ],
        timeout=8,
    )
    gpus: list[dict] = []
    if got.get("ok"):
        for line in (got.get("stdout") or "").splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2:
                continue
            try:
                vram = int(float(parts[1]))
            except ValueError:
                vram = 0
            used = 0
            if len(parts) >= 3:
                try:
                    used = int(float(parts[2]))
                except ValueError:
                    used = 0
            gpus.append(
                {
                    "name": parts[0],
                    "vram_mb": vram,
                    "vram_used_mb": used,
                    "driver": parts[3] if len(parts) >= 4 else "",
                }
            )
        if gpus:
            return gpus
    listed = run(["nvidia-smi", "-L"], timeout=8)
    if listed.get("ok"):
        for line in (listed.get("stdout") or "").splitlines():
            raw = line.strip()
            if not _NVIDIA_LINE.match(raw):
                continue
            name = raw.split(":", 1)[-1].strip()
            if " (UUID:" in name:
                name = name.split(" (UUID:", 1)[0].strip()
            if name:
                gpus.append({"name": name, "vram_mb": 0, "vram_used_mb": 0, "driver": ""})
    return gpus


def _gpus_lspci(run=run_argv) -> list[dict]:
    got = run(["lspci", "-nn"], timeout=8)
    gpus: list[dict] = []
    if not got.get("ok"):
        return gpus
    for line in (got.get("stdout") or "").splitlines():
        lower = line.lower()
        if "vga compatible controller" not in lower and "3d controller" not in lower:
            continue
        name = line.split(": ", 1)[-1].strip() if ": " in line else line.strip()
        gpus.append({"name": name, "vram_mb": 0, "vram_used_mb": 0, "driver": ""})
    return gpus


def collect_gpus(run=run_argv) -> list[dict]:
    return _gpus_nvml() or _gpus_nvidia_smi(run) or _gpus_lspci(run)


def _gpu_label(gpu: dict) -> str:
    name = gpu.get("name") or "unknown"
    vram = gpu.get("vram_mb") or 0
    driver = gpu.get("driver") or ""
    bits = [name]
    if vram:
        bits.append(f"{vram} MiB")
    if driver:
        bits.append(f"driver {driver}")
    return ", ".join(bits) if len(bits) == 1 else f"{bits[0]} ({', '.join(bits[1:])})"


def _monitor_identity(mon: dict) -> str:
    brand = (mon.get("brand") or "").strip()
    model = (mon.get("model") or "").strip()
    if brand and model:
        if model.lower().startswith(brand.lower()):
            return model
        return f"{brand} {model}"
    return brand or model


def _monitor_label(mon: dict) -> str:
    ident = _monitor_identity(mon)
    bits = [ident or (mon.get("name") or "display")]
    if ident and mon.get("name"):
        bits.append(f"on {mon['name']}")
    if mon.get("resolution"):
        hz = mon.get("refresh_hz")
        bits.append(f"{mon['resolution']}@{int(hz)}Hz" if hz else mon["resolution"])
    if mon.get("primary"):
        bits.append("primary")
    return " ".join(bits)


def _summary(
    gpus: list[dict],
    monitors: list[dict],
    plasma: str,
    session: str,
    cpu: str = "",
    cpu_cores: int = 0,
    cpu_threads: int = 0,
    ram_mb: int = 0,
    distro: str = "",
    kernel: str = "",
) -> str:
    parts: list[str] = []
    if monitors:
        parts.append(f"{len(monitors)} monitor{'s' if len(monitors) != 1 else ''}")
        labels = [_monitor_label(m) for m in monitors]
        parts[-1] += f" ({'; '.join(labels)})"
    else:
        parts.append("monitor count unknown")
    if gpus:
        parts.append("GPU " + "; ".join(_gpu_label(g) for g in gpus))
    else:
        parts.append("GPU unknown")
    if cpu:
        cpu_bits = cpu
        extra = []
        if cpu_cores:
            extra.append(f"{cpu_cores} cores")
        if cpu_threads:
            extra.append(f"{cpu_threads} threads")
        if extra:
            cpu_bits = f"{cpu} ({', '.join(extra)})"
        parts.append(f"CPU {cpu_bits}")
    if ram_mb:
        parts.append(f"RAM {ram_mb // 1024} GiB")
    if distro:
        parts.append(distro)
    if kernel:
        parts.append(f"kernel {kernel}")
    if plasma:
        parts.append(plasma)
    if session:
        parts.append(session)
    return "; ".join(parts)


def handle(_args: dict, ctx) -> dict:
    del ctx
    plasma = (run_argv(["plasmashell", "--version"], timeout=5).get("stdout") or "").strip()
    gpus = collect_gpus()
    monitors = collect_monitors()
    session = _session()
    gpu = _gpu_label(gpus[0]) if gpus else ""
    boot = collect_kernel_cmdline()
    cpu = collect_cpu()
    ram = collect_ram()
    board = collect_board()
    os_release = _os_release()
    distro = _distro_name(os_release)
    kernel = platform.release()
    cpu_name = cpu.get("cpu") or ""
    cpu_cores = int(cpu.get("cpu_cores") or 0)
    cpu_threads = int(cpu.get("cpu_threads") or 0)
    ram_mb = int(ram.get("ram_mb") or 0)
    return {
        "ok": True,
        "summary": _summary(
            gpus,
            monitors,
            plasma,
            session,
            cpu=cpu_name,
            cpu_cores=cpu_cores,
            cpu_threads=cpu_threads,
            ram_mb=ram_mb,
            distro=distro,
            kernel=kernel,
        ),
        "gpu": gpu,
        "gpus": gpus,
        "monitor_count": len(monitors),
        "monitors": monitors,
        "cpu": cpu_name,
        "cpu_cores": cpu_cores,
        "cpu_threads": cpu_threads,
        "ram_mb": ram_mb,
        "distro": distro,
        "plasma": plasma,
        "qt": _qt_version(),
        "session": session,
        "os_release": os_release,
        "kernel": kernel,
        "kernel_cmdline": boot.get("kernel_cmdline") or "",
        "kernel_cmdline_params": boot.get("kernel_cmdline_params") or [],
        "kernel_cmdline_configured": boot.get("kernel_cmdline_configured") or "",
        "board": board.get("board") or "",
        "board_vendor": board.get("board_vendor") or "",
        "hostname": platform.node(),
        "user": os.environ.get("USER", ""),
    }


_HW_GPU_RE = re.compile(r"\bgpu\b|graphics card|video card|\bvram\b|carte graphique", re.I)
_HW_MON_RE = re.compile(r"\bmonitors?\b|\bdisplays?\b|\bscreens?\b|écrans?", re.I)
_HW_BRAND_RE = re.compile(r"\b(brands?|manufacturer|marque|fabricant|models?)\b", re.I)
_HW_COUNT_RE = re.compile(r"how many|number of|combien", re.I)
_HW_CMDLINE_RE = re.compile(
    r"kernel\s+(command\s*line|cmdline|parameters?|params)|"
    r"boot\s+(parameters?|params|cmdline|command\s*line)|"
    r"\bcmdline\b|"
    r"forced at startup|"
    r"paramètres?\s+(du\s+noyau|kernel)",
    re.I,
)
_HW_PLASMA_RE = re.compile(
    r"plasma\s+version|which plasma|what plasma|plasmashell\s+version|\bon plasma\b",
    re.I,
)
_HW_KERNEL_VER_RE = re.compile(
    r"kernel\s+version|which kernel|what kernel(?!\s+(command|cmdline|param))|"
    r"(?:running|using)\s+(?:the\s+)?kernel",
    re.I,
)
_HW_DISTRO_RE = re.compile(
    r"\bdistro\b|distribution|operating system|\bwhich os\b|\bwhat os\b|\bcachyos\b",
    re.I,
)
_HW_CPU_RE = re.compile(r"\bcpu\b|\bprocessor\b|how many cores|combien de cœurs", re.I)
_HW_RAM_RE = re.compile(r"\bram\b|how much memory|how much ram|mémoire vive", re.I)
_HW_HOST_RE = re.compile(r"\bhostname\b|machine name|nom d['’]hôte", re.I)
_HW_SESSION_RE = re.compile(r"\bwayland\b|\bx11\b|session type|display server", re.I)
_HW_QT_RE = re.compile(r"\bqt(?:\s+version)?\b", re.I)
_HW_BOARD_RE = re.compile(r"motherboard|mainboard|carte mère", re.I)
_HW_ANY_RE = (
    _HW_GPU_RE,
    _HW_MON_RE,
    _HW_CMDLINE_RE,
    _HW_PLASMA_RE,
    _HW_KERNEL_VER_RE,
    _HW_DISTRO_RE,
    _HW_CPU_RE,
    _HW_RAM_RE,
    _HW_HOST_RE,
    _HW_SESSION_RE,
    _HW_QT_RE,
    _HW_BOARD_RE,
)


def _history_blob(history: list | None) -> str:
    if not history:
        return ""
    parts = []
    for msg in history[-8:]:
        parts.append(str(msg.get("content") or ""))
    return " ".join(parts)


def is_hardware_question(text: str, history: list | None = None) -> bool:
    blob = text or ""
    if any(rx.search(blob) for rx in _HW_ANY_RE):
        return True
    if _HW_BRAND_RE.search(blob) and _HW_MON_RE.search(_history_blob(history)):
        return True
    return False


_HW_LOOKUP_RE = re.compile(
    r"^\s*(?:what|which|how many|how much|am i|what['’]s|whats)\b",
    re.I,
)


def is_hardware_lookup(text: str, history: list | None = None) -> bool:
    return is_hardware_question(text, history) and bool(_HW_LOOKUP_RE.search(text or ""))


def _brand_answer(payload: dict) -> str:
    bits = []
    for mon in payload.get("monitors") or []:
        ident = _monitor_identity(mon)
        name = mon.get("name") or ""
        if ident and name:
            bits.append(f"{ident} ({name})")
        elif ident:
            bits.append(ident)
        elif name:
            bits.append(name)
    if not bits:
        return payload.get("summary") or ""
    if len(bits) == 1:
        return f"The monitor is {bits[0]}."
    return "The monitors are " + " and ".join(bits) + "."


def _cmdline_tokens(text: str) -> list[str]:
    skip = {"rw", "ro"}
    return [
        tok
        for tok in (text or "").split()
        if tok
        and tok.lower() not in skip
        and not tok.startswith("BOOT_IMAGE=")
        and not tok.startswith("root=")
    ]


def _cmdline_answer(payload: dict) -> str:
    active = (payload.get("kernel_cmdline") or "").strip()
    configured = (payload.get("kernel_cmdline_configured") or "").strip()
    if not active and not configured:
        return ""
    lines = []
    if active:
        lines.append(f"This boot (/proc/cmdline): {active}")
    if configured and configured != active:
        lines.append(f"Configured for Limine (KERNEL_CMDLINE[default]): {configured}")
    return "\n".join(lines)


def _version_token(text: str) -> str:
    match = re.search(r"(\d+\.\d+(?:\.\d+)?)", text or "")
    return match.group(1) if match else ""


def _cpu_needle(cpu: str) -> str:
    skip = {"processor", "core", "cores", "amd", "intel", "cpu", "gen", "with", "radeon", "graphics"}
    for tok in reversed((cpu or "").split()):
        cleaned = tok.strip(",()")
        if re.fullmatch(r"\d+-cores?", cleaned, re.I):
            continue
        if len(cleaned) >= 4 and cleaned.lower() not in skip:
            return cleaned
    return cpu or ""


def _cpu_answer(payload: dict) -> str:
    cpu = payload.get("cpu") or ""
    if not cpu:
        return ""
    extra = []
    cores = payload.get("cpu_cores") or 0
    threads = payload.get("cpu_threads") or 0
    if cores:
        extra.append(f"{cores} cores")
    if threads:
        extra.append(f"{threads} threads")
    suffix = f" ({', '.join(extra)})" if extra else ""
    return f"CPU: {cpu}{suffix}."


def _board_answer(payload: dict) -> str:
    board = payload.get("board") or ""
    vendor = payload.get("board_vendor") or ""
    if vendor and board:
        return f"Motherboard: {vendor} {board}."
    ident = board or vendor
    return f"Motherboard: {ident}." if ident else ""


def prefer_hardware_reply(
    user_text: str,
    model_text: str,
    payload: dict | None,
    history: list | None = None,
) -> str:
    if not payload or not payload.get("ok"):
        return model_text
    q = user_text or ""
    blob = (model_text or "").lower()
    wants_gpu = bool(_HW_GPU_RE.search(q))
    wants_mon = bool(_HW_MON_RE.search(q))
    wants_brand = bool(_HW_BRAND_RE.search(q))
    wants_cmdline = bool(_HW_CMDLINE_RE.search(q))
    wants_plasma = bool(_HW_PLASMA_RE.search(q))
    wants_kernel_ver = bool(_HW_KERNEL_VER_RE.search(q)) and not wants_cmdline
    wants_distro = bool(_HW_DISTRO_RE.search(q))
    wants_cpu = bool(_HW_CPU_RE.search(q))
    wants_ram = bool(_HW_RAM_RE.search(q))
    wants_host = bool(_HW_HOST_RE.search(q))
    wants_session = bool(_HW_SESSION_RE.search(q))
    wants_qt = bool(_HW_QT_RE.search(q))
    wants_board = bool(_HW_BOARD_RE.search(q))
    if wants_brand and not wants_mon and _HW_MON_RE.search(_history_blob(history)):
        wants_mon = True
    wants_count = bool(_HW_COUNT_RE.search(q)) and wants_mon
    idents = [
        (m.get("brand") or "", m.get("model") or "")
        for m in (payload.get("monitors") or [])
        if m.get("brand") or m.get("model")
    ]
    if wants_mon and not wants_count and not wants_brand and idents:
        wants_brand = True
    any_hw = any(
        (
            wants_gpu,
            wants_mon,
            wants_brand,
            wants_count,
            wants_cmdline,
            wants_plasma,
            wants_kernel_ver,
            wants_distro,
            wants_cpu,
            wants_ram,
            wants_host,
            wants_session,
            wants_qt,
            wants_board,
        )
    )
    if not any_hw:
        return model_text
    replacements: list[str] = []
    gpu_name = (payload.get("gpu") or "").split(" (")[0].strip()
    if wants_gpu and not (gpu_name and gpu_name.lower() in blob):
        if payload.get("gpu"):
            replacements.append(f"GPU: {payload['gpu']}.")
        elif payload.get("summary"):
            replacements.append(str(payload["summary"]))
    count = payload.get("monitor_count")
    if wants_count and not (count is not None and str(count) in blob):
        if count is not None:
            replacements.append(f"{count} monitor{'s' if count != 1 else ''}.")
    if wants_brand and idents:
        ok_brand = all(
            (brand and brand.lower() in blob) or (model and model.lower() in blob)
            for brand, model in idents
        )
        if not ok_brand:
            branded = _brand_answer(payload)
            if branded:
                replacements.append(branded)
    cmdline = payload.get("kernel_cmdline") or ""
    interesting = _cmdline_tokens(cmdline)
    if wants_cmdline:
        if cmdline and cmdline.lower() in blob:
            ok_cmdline = True
        elif interesting:
            ok_cmdline = all(tok.lower() in blob for tok in interesting)
        else:
            ok_cmdline = False
        if not ok_cmdline:
            boot = _cmdline_answer(payload)
            if boot:
                replacements.append(boot)
    plasma = payload.get("plasma") or ""
    pver = _version_token(plasma)
    if wants_plasma and not ((pver and pver in blob) or (plasma.lower() in blob)):
        replacements.append(f"Plasma {pver}." if pver else plasma)
    kernel = payload.get("kernel") or ""
    if wants_kernel_ver:
        has_ver = bool(kernel) and kernel.lower() in blob
        cmd_toks = _cmdline_tokens(payload.get("kernel_cmdline") or "")
        leaked = bool(cmd_toks) and any(tok.lower() in blob for tok in cmd_toks)
        if kernel and (not has_ver or leaked):
            replacements.append(f"Kernel version: {kernel}.")
    distro = payload.get("distro") or (payload.get("os_release") or {}).get("PRETTY_NAME") or ""
    if wants_distro and not (distro and distro.lower() in blob):
        if distro:
            replacements.append(f"Distro: {distro}.")
    cpu = payload.get("cpu") or ""
    needle = _cpu_needle(cpu).lower()
    cores = payload.get("cpu_cores") or 0
    if wants_cpu:
        ok_cpu = bool(needle and needle in blob)
        if re.search(r"cores?|cœurs?", q, re.I) and cores:
            ok_cpu = str(cores) in blob
        if not ok_cpu:
            ans = _cpu_answer(payload)
            if ans:
                replacements.append(ans)
    ram_mb = int(payload.get("ram_mb") or 0)
    if wants_ram and ram_mb:
        gib = ram_mb // 1024
        if str(gib) not in blob and str(gib + 1) not in blob:
            replacements.append(f"RAM: {gib} GiB ({ram_mb} MiB).")
    host = payload.get("hostname") or ""
    if wants_host and not (host and host.lower() in blob):
        if host:
            replacements.append(f"Hostname: {host}.")
    session = payload.get("session") or ""
    if wants_session and not (session and session.lower() in blob):
        if session:
            replacements.append(f"Session: {session}.")
    qt = payload.get("qt") or ""
    if wants_qt and not (qt and qt.lower() in blob):
        if qt:
            replacements.append(f"Qt {qt}.")
    board = payload.get("board") or ""
    vendor = payload.get("board_vendor") or ""
    if wants_board:
        ok_board = (board and board.lower() in blob) or (vendor and vendor.lower() in blob)
        if not ok_board:
            ans = _board_answer(payload)
            if ans:
                replacements.append(ans)
    if not replacements and (model_text or "").strip():
        return model_text
    if replacements:
        return "\n".join(replacements)
    return (payload.get("summary") or model_text or "").strip()


SCHEMA = {
    "name": "system_info",
    "description": (
        "Live OS, Plasma, Qt, session, GPU, monitors (count/brand/model), CPU, RAM, "
        "motherboard, hostname, kernel version, and kernel_cmdline (boot parameters from "
        "/proc/cmdline and Limine/GRUB). Call this for hardware or version questions; quote "
        "summary, gpu, monitor_count, brand/model, cpu, ram_mb, distro, and kernel_cmdline. "
        "kernel is the version; kernel_cmdline is the boot parameters."
    ),
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}
