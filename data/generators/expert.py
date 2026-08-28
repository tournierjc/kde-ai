"""Expert trajectories for gold + the 30k templates.

Skills stay playbooks. This module is the training catalog: Linux, KDE (user +
dev), CachyOS, sysadmin, and network — all via allowlisted tools. Manpage paths
are citation targets, not scraped pages. Bugzilla/invent ids are synthetic.
"""

from __future__ import annotations

from data.generators.common import assistant_text, assistant_tools, call, record, tool, user

MAN = [
    ("ls", "1", "/usr/share/man/man1/ls.1"),
    ("pacman", "8", "/usr/share/man/man8/pacman.8"),
    ("journalctl", "1", "/usr/share/man/man1/journalctl.1"),
    ("systemctl", "1", "/usr/share/man/man1/systemctl.1"),
    ("kwin_wayland", "1", "/usr/share/man/man1/kwin_wayland.1"),
    ("man", "1", "/usr/share/man/man1/man.1"),
    ("uname", "1", "/usr/share/man/man1/uname.1"),
    ("dmesg", "1", "/usr/share/man/man1/dmesg.1"),
    ("ip", "8", "/usr/share/man/man8/ip.8"),
    ("ss", "8", "/usr/share/man/man8/ss.8"),
    ("nft", "8", "/usr/share/man/man8/nft.8"),
    ("resolvectl", "1", "/usr/share/man/man1/resolvectl.1"),
    ("NetworkManager", "8", "/usr/share/man/man8/NetworkManager.8"),
    ("nmcli", "1", "/usr/share/man/man1/nmcli.1"),
    ("systemd-networkd", "8", "/usr/share/man/man8/systemd-networkd.8"),
    ("sysctl", "8", "/usr/share/man/man8/sysctl.8"),
    ("mount", "8", "/usr/share/man/man8/mount.8"),
    ("fstab", "5", "/usr/share/man/man5/fstab.5"),
    ("environment.d", "5", "/usr/share/man/man5/environment.d.5"),
    ("pacman.conf", "5", "/usr/share/man/man5/pacman.conf.5"),
    ("mkinitcpio", "8", "/usr/share/man/man8/mkinitcpio.8"),
    ("systemd.timer", "5", "/usr/share/man/man5/systemd.timer.5"),
    ("systemd.nspawn", "1", "/usr/share/man/man1/systemd-nspawn.1"),
    ("cgroups", "7", "/usr/share/man/man7/cgroups.7"),
    ("capabilities", "7", "/usr/share/man/man7/capabilities.7"),
    ("qdbus", "1", "/usr/share/man/man1/qdbus.1"),
    ("cmake", "1", "/usr/share/man/man1/cmake.1"),
]

HW = {
    "ok": True,
    "plasma": "plasmashell 6.7.4",
    "qt": "6.11.2",
    "session": "wayland",
    "kernel": "7.2.0-1-cachyos",
    "distro": "CachyOS",
    "cpu": "AMD Ryzen 9 5900X 12-Core Processor",
    "cpu_cores": 12,
    "ram_mb": 31999,
    "gpu": "NVIDIA GeForce RTX 3090 (24576 MiB, driver 610.57)",
    "gpus": [
        {
            "name": "NVIDIA GeForce RTX 3090",
            "vram_mb": 24576,
            "driver": "610.57",
            "kernel_driver": "nvidia",
        }
    ],
    "gpu_kernel_driver": "nvidia",
    "uptime": "2 days, 3 hours, 14 minutes",
    "boot_time": "2026-08-25 19:19",
    "kernel_cmdline": "quiet nowatchdog splash nvidia_drm.modeset=1 nvidia_drm.fbdev=1",
    "hostname": "jct-desktop",
}


def _hint(query: str, kcm: str, cmd: str, doc: str) -> tuple:
    return (
        "kde_settings_hint",
        {"query": query},
        {"ok": True, "matched": True, "kcm": kcm, "command": cmd, "doc": doc},
    )


def _hint_miss(query: str) -> tuple:
    return (
        "kde_settings_hint",
        {"query": query},
        {"ok": True, "matched": False, "kcm": None, "command": None, "doc": None},
    )


def _docs(title: str, sec: str, path: str, snippet: str) -> tuple:
    return (
        "search_docs",
        {"query": title},
        {"ok": True, "hits": [{"title": title, "path": path, "section": sec, "snippet": snippet}]},
    )


def _ro(name: str, stdout: str, pkg: str | None = None) -> tuple:
    args: dict = {"name": name}
    if pkg:
        args["pkg"] = pkg
    return ("run_readonly_cmd", args, {"ok": True, "stdout": stdout, "code": 0})


def _priv(name: str, stdout: str, unit: str | None = None) -> tuple:
    args: dict = {"name": name}
    if unit:
        args["unit"] = unit
    return ("run_privileged_cmd", args, {"ok": True, "stdout": stdout, "code": 0})


def _info(**extra) -> tuple:
    payload = {**HW, **extra}
    return ("system_info", {}, payload)


def _bz(query: str, bid: int, summary: str) -> tuple:
    return (
        "search_bugzilla",
        {"query": query},
        {
            "ok": True,
            "bugs": [
                {
                    "id": bid,
                    "summary": summary,
                    "status": "CONFIRMED",
                    "url": f"https://bugs.kde.org/show_bug.cgi?id={bid}",
                }
            ],
        },
    )


def _invent(query: str, title: str, url: str) -> tuple:
    return (
        "search_invent",
        {"query": query},
        {"ok": True, "items": [{"id": 40, "title": title, "web_url": url}]},
    )


def case(
    domain: str,
    skills: list[str],
    q: str,
    steps: list[tuple],
    a: str,
    *,
    issue: bool = False,
    tags: list[str] | None = None,
    topics: list[str] | None = None,
    example: str | None = None,
    intent: str | None = None,
) -> dict:
    auto = [f"tool:{name}" for name, _, _ in steps]
    if any(name == "search_docs" for name, _, _ in steps):
        auto.append("rag_cite")
    row = {
        "domain": domain,
        "skills": skills,
        "q": q,
        "steps": steps,
        "a": a,
        "issue": issue,
        "tags": tags or auto,
    }
    if topics:
        row["topics"] = topics
    if example:
        row["example"] = example
    if intent:
        row["intent"] = intent
    return row


def record_from_case(
    rid: str,
    spec: dict,
    suffix: str = "",
    source: str = "gold",
    variant: int | None = None,
) -> dict:
    from data.generators.questions import maybe_example_turns, paraphrase_question

    if variant is not None:
        q = paraphrase_question(spec, variant)
    else:
        q = spec["q"] + suffix
    turns: list[dict] = [user(q)]
    for name, args, result in spec["steps"]:
        turns.append(assistant_tools([call(name, args)]))
        turns.append(tool(name, result))
    turns.append(assistant_text(spec["a"]))
    if variant is not None:
        turns.extend(maybe_example_turns(spec, variant))
    return record(
        rid,
        spec["domain"],
        spec.get("issue") or False,
        spec["skills"],
        turns,
        source=source,
        tags=spec.get("tags") or [],
    )


def kde_user_cases() -> list[dict]:
    sk = ["kde-desktop"]
    return [
        case(
            "kde",
            sk,
            "Where do I change display scaling and which monitor is primary?",
            [
                _info(monitor_count=2),
                _hint(
                    "display",
                    "kcm_kscreen",
                    "systemsettings kcm_kscreen",
                    "https://userbase.kde.org/System_Settings/Display",
                ),
            ],
            "You have 2 monitors. Scale and primary display are in kcm_kscreen "
            "(`systemsettings kcm_kscreen`). On Wayland prefer 125–150% over 200% "
            "integer scale so XWayland apps stay sharp.",
        ),
        case(
            "kde",
            sk,
            "how can i change my monitor resolution",
            [
                _hint(
                    "display",
                    "kcm_kscreen",
                    "systemsettings kcm_kscreen",
                    "https://userbase.kde.org/System_Settings/Display",
                )
            ],
            "Use System Settings Display (kcm_kscreen): `systemsettings kcm_kscreen`. "
            "Pick the output and set Resolution (and refresh) there.",
            topics=[
                "change my monitor resolution",
                "set my screen resolution",
                "change display resolution",
            ],
            intent="howto",
        ),
        case(
            "kde",
            sk,
            "how do I set my screen resolution",
            [
                _hint(
                    "resolution",
                    "kcm_kscreen",
                    "systemsettings kcm_kscreen",
                    "https://userbase.kde.org/System_Settings/Display",
                )
            ],
            "Use System Settings Display (kcm_kscreen): `systemsettings kcm_kscreen`. "
            "Pick the output and set Resolution there.",
            topics=["set my screen resolution", "change my monitor resolution"],
            intent="howto",
        ),
        case(
            "kde",
            sk,
            "take a screenshot",
            [
                (
                    "screenshot_ocr",
                    {},
                    {
                        "ok": True,
                        "text": "Unlock widgets  |  Add Panel",
                        "path": "/tmp/kde-ai/shot.png",
                    },
                )
            ],
            "Captured the screen to /tmp/kde-ai/shot.png. OCR text: Unlock widgets  |  Add Panel",
        ),
        case(
            "kde",
            sk,
            "where can i configure environment variable",
            [
                _hint_miss("environment"),
                _docs(
                    "environment.d",
                    "5",
                    "/usr/share/man/man5/environment.d.5",
                    "environment.d(5) — per-user and system environment settings",
                ),
            ],
            "Not a System Settings KCM. For the Plasma session use systemd "
            "environment.d(5) (`/usr/share/man/man5/environment.d.5`): drop "
            "`KEY=value` files in `~/.config/environment.d/`. System-wide is "
            "`/etc/environment`. `~/.bashrc` only affects terminals. Log out to apply.",
            topics=[
                "set an environment variable",
                "define an env variable",
                "configure an environment variable",
                "persist an environment variable for GUI apps",
                "set a session environment variable for Plasma",
            ],
            example=(
                "Put this in `~/.config/environment.d/99-local.conf`:\n\n"
                "EDITOR=nvim\n\nThen log out of Plasma."
            ),
            intent="howto",
        ),
        case(
            "kde",
            sk,
            "Night Light is stuck on and I cannot find the toggle.",
            [
                _hint(
                    "display",
                    "kcm_kscreen",
                    "systemsettings kcm_kscreen",
                    "https://userbase.kde.org/System_Settings/Display",
                )
            ],
            "Night Light lives with display settings (kcm_kscreen). If the temperature "
            "is locked, turn the feature off there rather than editing kwinrc by hand.",
        ),
        case(
            "kde",
            sk,
            "No sound after switching HDMI — where is the output device picker?",
            [
                _hint(
                    "audio",
                    "kcm_pulseaudio",
                    "systemsettings kcm_pulseaudio",
                    "https://userbase.kde.org/PulseAudio",
                )
            ],
            "Plasma 6 uses PipeWire with a PulseAudio-compatible KCM: kcm_pulseaudio "
            "(`systemsettings kcm_pulseaudio`). Pick the HDMI sink there; a profile "
            "left on 'off' is the usual cause after a monitor change.",
        ),
        case(
            "kde",
            sk,
            "Where do I join Wi-Fi and set a WireGuard profile in Plasma?",
            [
                _hint(
                    "network",
                    "kcm_networkmanagement",
                    "systemsettings kcm_networkmanagement",
                    "https://userbase.kde.org/Plasma/Network",
                )
            ],
            "Connections are kcm_networkmanagement (`systemsettings kcm_networkmanagement`). "
            "Plasma talks to NetworkManager; WireGuard is an NM connection type there, "
            "not a separate CachyOS daemon.",
        ),
        case(
            "kde",
            sk,
            "Meta+key shortcuts do nothing. Which KCM owns them?",
            [
                _hint(
                    "shortcuts",
                    "kcm_keys",
                    "systemsettings kcm_keys",
                    "https://userbase.kde.org/System_Settings/Shortcuts",
                )
            ],
            "Global shortcuts are kcm_keys (`systemsettings kcm_keys`). Check the Plasma "
            "component first, then KWin. A grabbing game or a second Meta binding in "
            "the same KCM is the usual conflict.",
        ),
        case(
            "kde",
            sk,
            "Tearing on the second monitor — compositor or KWin setting?",
            [
                _hint(
                    "compositor",
                    "kcm_kwincompositing",
                    "systemsettings kcm_kwincompositing",
                    "https://userbase.kde.org/KWin",
                )
            ],
            "Open kcm_kwincompositing. On Wayland, KWin composites always; tearing "
            "usually means a mismatched refresh rate in kcm_kscreen or NVIDIA "
            "AllowVRR / ForceCompositionPipeline, not 'disable compositor'.",
        ),
        case(
            "kde",
            sk,
            "Global theme reset after a Plasma update. How do I reapply it safely?",
            [
                _hint(
                    "theme",
                    "kcm_lookandfeel",
                    "systemsettings kcm_lookandfeel",
                    "https://userbase.kde.org/Plasma/LookAndFeel",
                )
            ],
            "Reapply from kcm_lookandfeel (`systemsettings kcm_lookandfeel`). Do not "
            "copy Plasma 5 look-and-feel packages onto 6; layouts live in "
            "plasma-org.kde.plasma.desktop-appletsrc and get rewritten on apply.",
        ),
        case(
            "kde",
            sk,
            "Notification history is empty even though apps notify.",
            [
                _hint(
                    "notifications",
                    "kcm_notifications",
                    "systemsettings kcm_notifications",
                    "https://userbase.kde.org/Plasma/Notifications",
                )
            ],
            "kcm_notifications controls history, Do Not Disturb, and per-app inhibit. "
            "If history is off globally, the tray has nothing to show even when popups work.",
        ),
        case(
            "kde",
            sk,
            "The panel vanished after login. Capture the screen and get me back a shell.",
            [
                ("screenshot_ocr", {}, {"ok": True, "text": "Unlock widgets  |  Add Panel"}),
                ("plasma_script", {"name": "plasma_restart"}, {"ok": True, "warn": "restart is not auto-undone"}),
            ],
            "OCR shows the desktop context menu, so plasmashell is up but the panel "
            "is gone. I restarted plasmashell (not undone). Right-click desktop → "
            "Add Panel, or restore from a Look and Feel. If it dies again, search "
            "Bugzilla with live Plasma/Qt from system_info.",
        ),
        case(
            "kde",
            sk,
            "plasmashell is wedged at 100% CPU. Restart it without rebooting.",
            [("plasma_script", {"name": "plasma_restart"}, {"ok": True, "warn": "restart is not auto-undone"})],
            "Restarted plasmashell. That does not restart KWin. If the compositor is "
            "also stuck, that is a separate kwin_wayland process — log out of the "
            "session rather than SIGKILL from here.",
        ),
        case(
            "kde",
            sk,
            "Are we on Wayland, and which Qt/Plasma should I quote in a KWin bug?",
            [_info()],
            "Wayland session. Quote plasmashell 6.7.4, Qt 6.11.2, and kernel "
            "7.2.0-1-cachyos. KWin bugs need the session type; X11 and Wayland are "
            "different code paths.",
        ),
        case(
            "kde",
            sk,
            "GTK apps ignore the Plasma dark theme.",
            [
                _hint(
                    "theme",
                    "kcm_lookandfeel",
                    "systemsettings kcm_lookandfeel",
                    "https://userbase.kde.org/Plasma/LookAndFeel",
                )
            ],
            "Look and Feel (kcm_lookandfeel) sets Plasma/Qt. GTK 3/4 follow "
            "xdg-desktop-portal-kde and gnome-themes; install matching Breeze GTK "
            "and keep portal running. This is not a KWin compositor toggle.",
        ),
        case(
            "kde",
            sk,
            "Set a user-level flag in ~/.config/kde-ai-lab.conf so I can test edit_config.",
            [
                (
                    "edit_config",
                    {"path": "/home/user/.config/kde-ai-lab.conf", "content": "lab=1\n"},
                    {"ok": True, "path": "/home/user/.config/kde-ai-lab.conf"},
                )
            ],
            "Wrote ~/.config/kde-ai-lab.conf (home jail). I cannot touch /etc, .ssh, "
            "or .gnupg. If this was issue mode we would snapshot for undo.",
            issue=True,
        ),
        case(
            "kde",
            ["kde-desktop", "docs"],
            "How does Baloo file search get disabled without breaking KRunner?",
            [_docs("balooctl", "1", "/usr/share/man/man1/balooctl.1", "balooctl(1) control the Baloo file indexer")],
            "From /usr/share/man/man1/balooctl.1: `balooctl disable` stops indexing. "
            "KRunner still does apps/calculator; only content search goes away. I "
            "cannot run balooctl here — use that manpage on the host.",
        ),
        case(
            "kde",
            ["kde-desktop", "docs"],
            "Cite kwin_wayland for a compositor crash write-up.",
            [_docs("kwin_wayland", "1", "/usr/share/man/man1/kwin_wayland.1", "kwin_wayland(1) KDE Wayland compositor")],
            "Cited /usr/share/man/man1/kwin_wayland.1. Attach `journalctl --user -u "
            "plasma-kwin_wayland` output and system_info Plasma/Qt/session; do not "
            "paste guessed drm-debug flags.",
        ),
    ]


def kde_dev_cases() -> list[dict]:
    sk = ["bugs", "kde-desktop"]
    return [
        case(
            "bug_search",
            sk,
            "I hit a plasmashell crash after login. Find a duplicate before I file.",
            [
                _info(),
                _bz("plasmashell crash after login", 512001, "plasmashell crash after login on Wayland"),
            ],
            "Live: plasmashell 6.7.4, Qt 6.11.2, Wayland, CachyOS 7.2.0-1-cachyos. "
            "Bugzilla 512001 matches that summary. Reuse it; do not invent another id. "
            "Product is plasma-workspace, not frameworks-kio, unless the stack says kio.",
        ),
        case(
            "bug_search",
            sk,
            "Where is the plasma-workspace repo so I can look at the panel code?",
            [
                _invent(
                    "plasma-workspace panel",
                    "plasma-workspace",
                    "https://invent.kde.org/plasma/plasma-workspace",
                )
            ],
            "Invent lists plasma-workspace at https://invent.kde.org/plasma/plasma-workspace. "
            "Panel/containment QML lives there; applets are often plasma-desktop. I did "
            "not invent the URL.",
        ),
        case(
            "bug_search",
            sk,
            "KPipeWire black frames in Spectacle — search Bugzilla, quote live GPU.",
            [
                _info(),
                _bz("kpipewire spectacle black frame", 512040, "Spectacle recording black on NVIDIA"),
            ],
            "GPU NVIDIA GeForce RTX 3090, Wayland, Plasma 6.7.4. Bug 512040 is the "
            "NVIDIA/KPipeWire recording issue. File against kpipewire or spectacle "
            "with that GPU/driver, not against kwin unless the stack is KWin.",
        ),
        case(
            "kde",
            ["kde-desktop", "docs"],
            "Plasma 6 KCM modules: QML or QWidgets, and how do I inspect DBus?",
            [_docs("qdbus", "1", "/usr/share/man/man1/qdbus.1", "qdbus(1) list D-Bus services")],
            "New Plasma 6 KCMs are QML (KCMUtils). From /usr/share/man/man1/qdbus.1 "
            "you can list org.kde.* on the session bus. I cannot run qdbus here; cite "
            "that manpage and the kcm id from kde_settings_hint.",
        ),
        case(
            "kde",
            ["kde-desktop", "docs"],
            "I am writing a Kirigami applet. Which build tool manpage should I cite?",
            [_docs("cmake", "1", "/usr/share/man/man1/cmake.1", "cmake(1) generate build files")],
            "Cited /usr/share/man/man1/cmake.1. Plasma 6 applets use extra-cmake-modules "
            "and KF6; do not cargo-cult Plasma 5 kdelibs4. I will not invent a module "
            "name that kde_settings_hint did not return.",
        ),
        case(
            "bug_search",
            sk,
            "Is this a KWin or a kwinft bug? Search invent for kwin.",
            [
                _invent("kwin wayland", "kwin", "https://invent.kde.org/plasma/kwin"),
            ],
            "CachyOS Plasma ships KWin (invent.kde.org/plasma/kwin), not kwinft. File "
            "against KWin with session=wayland from system_info. I did not invent the project URL.",
        ),
        case(
            "bug_search",
            ["bugs"],
            "Search invent for plasma-nm before I claim a NetworkManager applet patch exists.",
            [
                _invent(
                    "plasma-nm",
                    "plasma-nm",
                    "https://invent.kde.org/plasma/plasma-nm",
                )
            ],
            "plasma-nm is https://invent.kde.org/plasma/plasma-nm. That is the Plasma "
            "NM applet/KCM; libnm itself is upstream NetworkManager. Do not file NM "
            "core bugs only on invent.kde.org.",
        ),
        case(
            "bug_search",
            sk,
            "Open the matching Bugzilla ticket after the search.",
            [
                _bz("kwin crash wayland", 487001, "kwin crash on start"),
                (
                    "open_url",
                    {"url": "https://bugs.kde.org/show_bug.cgi?id=487001"},
                    {"ok": True, "url": "https://bugs.kde.org/show_bug.cgi?id=487001"},
                ),
            ],
            "Opened https://bugs.kde.org/show_bug.cgi?id=487001 from the search hit. "
            "I only open https URLs the tool returned.",
        ),
        case(
            "bug_search",
            ["bugs"],
            "Open the Plasma UserBase page in the browser.",
            [
                (
                    "open_url",
                    {"url": "https://userbase.kde.org/Plasma"},
                    {"ok": True, "url": "https://userbase.kde.org/Plasma"},
                )
            ],
            "Opened https://userbase.kde.org/Plasma. Only http(s) URLs; no file: or ssh.",
        ),
        case(
            "kde",
            ["kde-desktop"],
            "Night color is fixed. Propose solved so I can confirm.",
            [
                (
                    "propose_solved",
                    {
                        "issue_summary": "Night Light stuck on",
                        "solution_summary": "Disabled Night Light in kcm_kscreen",
                    },
                    {"ok": True, "awaiting_confirm": True},
                )
            ],
            "Does that fix Night Light? Confirm yes or no. I will not mark it solved until you do.",
            issue=True,
        ),
    ]


def cachyos_cases() -> list[dict]:
    sk = ["cachyos"]
    return [
        case(
            "cachyos",
            sk,
            "Which CachyOS kernel package is actually installed?",
            [
                _ro(
                    "pacman_qi",
                    "Name            : linux-cachyos\nVersion         : 7.2.0-1\nProvides        : linux=7.2.0",
                    "linux-cachyos",
                )
            ],
            "pacman -Qi linux-cachyos: 7.2.0-1. CachyOS flavor kernels are "
            "linux-cachyos, linux-cachyos-lts, linux-cachyos-rc — query, do not assume. "
            "A full -Syu is not available through tools.",
        ),
        case(
            "cachyos",
            sk,
            "Do I want nvidia, nvidia-open, or nvidia-dkms on this box?",
            [
                _info(),
                _ro("pacman_qs", "local/nvidia-utils 610.57\nlocal/nvidia-dkms 610.57", "nvidia"),
            ],
            "RTX 3090 (Turing+) can use nvidia-open or nvidia-dkms; pacman -Qs nvidia "
            "shows nvidia-dkms 610.57 plus nvidia-utils. Do not mix nvidia-dkms with "
            "the other kernel module package. I will not run -Syu.",
        ),
        case(
            "cachyos",
            sk,
            "After an NVIDIA driver bump, what rebuilds the initramfs?",
            [_docs("mkinitcpio", "8", "/usr/share/man/man8/mkinitcpio.8", "mkinitcpio(8) create initramfs images")],
            "From /usr/share/man/man8/mkinitcpio.8: pacman hooks usually run mkinitcpio "
            "when nvidia-dkms or linux-cachyos updates. If the hook failed, run "
            "mkinitcpio -P on the host. Tools cannot invoke mkinitcpio.",
        ),
        case(
            "cachyos",
            sk,
            "Are nvidia_drm.modeset and fbdev actually on this boot?",
            [_info()],
            "This boot kernel_cmdline has nvidia_drm.modeset=1 and nvidia_drm.fbdev=1 "
            "(plus quiet nowatchdog splash). That is /proc/cmdline, not the kernel "
            "version string 7.2.0-1-cachyos. CachyOS default bootloader is Limine.",
        ),
        case(
            "cachyos",
            sk,
            "Install strace from extra. I already confirmed it is missing.",
            [
                (
                    "pacman_mutate",
                    {"action": "install", "pkgs": ["strace"]},
                    {"ok": True, "code": 0},
                )
            ],
            "Installed strace only. Undo removes it if it was new. Full -Syu is not a tool.",
            issue=True,
        ),
        case(
            "cachyos",
            sk,
            "Install htop from extra, not a full system upgrade.",
            [
                _ro("pacman_qs", "", "htop"),
                (
                    "pacman_mutate",
                    {"action": "install", "pkgs": ["htop"]},
                    {"ok": True, "code": 0},
                ),
            ],
            "htop was not installed (empty -Qs). Installed htop only. Undo removes it "
            "if it was new. I will not -Syu.",
            issue=True,
        ),
        case(
            "cachyos",
            sk,
            "Should I enable chaotic-aur for one AUR package?",
            [_docs("pacman.conf", "5", "/usr/share/man/man5/pacman.conf.5", "pacman.conf(5) pacman configuration file")],
            "From /usr/share/man/man5/pacman.conf.5: extra repos are Server= lines you "
            "add yourself. chaotic-aur is third-party; I will not add it via tools "
            "(cannot edit /etc). Prefer official extra/cachyos or a one-off paru on the host.",
        ),
        case(
            "cachyos",
            sk,
            "Is plasma-workspace present so I know this is a Plasma install?",
            [_ro("pacman_qi", "Name            : plasma-workspace\nVersion         : 6.7.4", "plasma-workspace")],
            "plasma-workspace 6.7.4 is installed. That is the Plasma shell package; "
            "kwin is separate. Cite pacman -Qi, not a remembered version.",
        ),
        case(
            "cachyos",
            sk,
            "linux-firmware for Wi-Fi — is the package there?",
            [_ro("pacman_qi", "Name            : linux-firmware\nVersion         : 20260801", "linux-firmware")],
            "linux-firmware is installed. Missing firmware still shows in journal_kernel "
            "as failed firmware loads. I will not guess a board-specific blob name.",
        ),
        case(
            "cachyos",
            sk,
            "Can you run yay -S something for me?",
            [_docs("pacman", "8", "/usr/share/man/man8/pacman.8", "pacman(8) package manager utility")],
            "No AUR helper in the allowlist. pacman(8) from /usr/share/man/man8/pacman.8 "
            "covers official repos; pacman_mutate can install extra packages after you "
            "confirm. Run paru/yay yourself for AUR.",
        ),
        case(
            "cachyos",
            sk,
            "Why is the CachyOS ISO using Btrfs and is that relevant to pacman?",
            [_docs("pacman.conf", "5", "/usr/share/man/man5/pacman.conf.5", "pacman.conf(5) includes CacheDir and HoldPkg")],
            "Default CachyOS installs are often Btrfs with subvols; pacman does not care "
            "beyond CacheDir in pacman.conf(5). Snapshots are snapper/timeshift on the "
            "host, not a kde-ai tool.",
        ),
    ]


def sysadmin_cases() -> list[dict]:
    sk = ["cachyos"]
    return [
        case(
            "cachyos",
            sk,
            "User systemd units look dead — show my user manager status.",
            [
                _ro(
                    "user_systemctl_status",
                    "State: running\nJobs: 0 queued\nFailed: 0 units",
                )
            ],
            "systemctl --user status: the user manager is running with 0 failed units. "
            "Session services (pipewire, plasma) are user units; sddm/NetworkManager "
            "are system units and need privilege.",
        ),
        case(
            "cachyos",
            sk,
            "Is sddm actually running? I authenticated.",
            [
                _priv(
                    "systemctl_status_unit",
                    "sddm.service - Simple Desktop Display Manager\n     Active: active (running)",
                    "sddm.service",
                )
            ],
            "sddm.service is active (running). Display manager failures belong here, "
            "not in plasmashell. If the greeter never appears, next is journalctl -u sddm.",
        ),
        case(
            "cachyos",
            sk,
            "Read the last system journal lines (I will auth).",
            [
                _priv(
                    "journalctl_system_n",
                    "NetworkManager[812]: <info> device (wlan0): state change\nsddm[900]: Session started",
                )
            ],
            "System journal shows NetworkManager bringing wlan0 up and SDDM starting a "
            "session. Next suspects are NM vs plasma-nm, not a random kwinrc edit.",
        ),
        case(
            "cachyos",
            sk,
            "Possible kernel oops — dmesg after I authenticate.",
            [
                _priv(
                    "dmesg",
                    "[  12.004] NVRM: loading NVIDIA UNIX Open Kernel Module\n[  12.200] nvidia-modeset: Loading",
                )
            ],
            "dmesg shows the NVIDIA UNIX Open Kernel Module loaded and nvidia-modeset "
            "active. No oops in this snippet. Correlate with nvidia_drm.modeset on cmdline.",
        ),
        case(
            "cachyos",
            sk,
            "User session logs for a PipeWire failure.",
            [
                _ro(
                    "journal_user",
                    "pipewire[1202]: mod.jackdbus-detect: Failed to receive jackdbus reply",
                )
            ],
            "User journal: PipeWire jackdbus-detect failed. Audio KCM still uses "
            "PipeWire; that warning is often harmless. If sinks are missing, check "
            "kcm_pulseaudio and pipewire.service --user, not ALSA rc files.",
        ),
        case(
            "cachyos",
            sk,
            "Kernel ring for firmware / drm errors without privilege first.",
            [
                _ro(
                    "journal_kernel",
                    "Direct firmware load for iwlwifi failed with error -2\nnvidia-modeset: Allocating GPU",
                )
            ],
            "journalctl -k: iwlwifi firmware failed to load (error -2) while NVIDIA "
            "modeset allocated the GPU. Wi-Fi wants linux-firmware + the right iwlwifi "
            "blob; GPU path looks fine. I did not guess a Bugzilla id.",
        ),
        case(
            "cachyos",
            sk,
            "Who am I on this machine after privilege?",
            [_priv("id", "uid=1000(jct) gid=1000(jct) groups=1000(jct),998(wheel)")],
            "uid=1000(jct), groups include wheel. Privilege worked. I will not store "
            "that in config or echo credentials.",
        ),
        case(
            "cachyos",
            ["cachyos", "docs"],
            "Explain systemd timers and how I would list them. Cite the manpage.",
            [
                _docs(
                    "systemd.timer",
                    "5",
                    "/usr/share/man/man5/systemd.timer.5",
                    "systemd.timer(5) timer unit configuration",
                )
            ],
            "From /usr/share/man/man5/systemd.timer.5: a .timer activates a matching "
            ".service. List with `systemctl list-timers` on the host (not allowlisted). "
            "kde-ai-reindex.timer is how this agent’s RAG refresh is scheduled.",
        ),
        case(
            "cachyos",
            ["cachyos", "docs"],
            "fstab vs mount — I think a USB disk is not mounting at boot.",
            [
                _docs("fstab", "5", "/usr/share/man/man5/fstab.5", "fstab(5) static information about filesystems"),
                _docs("mount", "8", "/usr/share/man/man8/mount.8", "mount(8) mount a filesystem"),
            ],
            "fstab(5) at /usr/share/man/man5/fstab.5 is static boot mounts; mount(8) is "
            "the runtime tool. I cannot edit /etc/fstab (home jail). Check UUID vs "
            "noauto,x-systemd.automount on the host.",
        ),
        case(
            "cachyos",
            ["cachyos", "docs"],
            "Need sysctl semantics for net.ipv4.ip_forward. Cite sysctl(8).",
            [_docs("sysctl", "8", "/usr/share/man/man8/sysctl.8", "sysctl(8) configure kernel parameters at runtime")],
            "Cited /usr/share/man/man8/sysctl.8. ip_forward is a runtime/sysctl.d "
            "setting; I cannot write /etc/sysctl.d from tools. Persist on the host "
            "after you confirm you actually want a router.",
        ),
        case(
            "cachyos",
            ["cachyos", "docs"],
            "How do Linux capabilities differ from running everything as root?",
            [
                _docs(
                    "capabilities",
                    "7",
                    "/usr/share/man/man7/capabilities.7",
                    "capabilities(7) overview of Linux capabilities",
                )
            ],
            "From /usr/share/man/man7/capabilities.7: CAP_NET_ADMIN is enough for many "
            "nft/ip operations without a root shell. This agent still will not run "
            "unrestricted argv; use allowlisted privileged tools when you must.",
        ),
        case(
            "cachyos",
            ["cachyos", "docs"],
            "cgroup v2 slice for a heavy compile — cite cgroups(7).",
            [_docs("cgroups", "7", "/usr/share/man/man7/cgroups.7", "cgroups(7) Linux control groups")],
            "Cited /usr/share/man/man7/cgroups.7. Unified hierarchy (cgroup v2) is "
            "what systemd uses (`system.slice`, `user.slice`). I cannot set "
            "CPUWeight here; systemd-run --user on the host can.",
        ),
    ]


def network_cases() -> list[dict]:
    return [
        case(
            "kde",
            ["kde-desktop"],
            "Wi-Fi dropped. Where is the Plasma connection editor, and what stack is it?",
            [
                _hint(
                    "network",
                    "kcm_networkmanagement",
                    "systemsettings kcm_networkmanagement",
                    "https://userbase.kde.org/Plasma/Network",
                )
            ],
            "kcm_networkmanagement drives NetworkManager on Plasma. CachyOS desktop "
            "images use NM, not systemd-networkd, for Wi-Fi. Check the AP auth, then "
            "journal for NetworkManager — I cannot run nmcli here.",
        ),
        case(
            "rag",
            ["docs", "cachyos"],
            "How do I inspect addresses and routes on Linux? Cite ip(8).",
            [_docs("ip", "8", "/usr/share/man/man8/ip.8", "ip(8) show / manipulate routing, network devices")],
            "From /usr/share/man/man8/ip.8: `ip -br addr` and `ip route`. This agent "
            "has no ip tool; run those on the host. Plasma NM is the GUI; ip is the "
            "netlink CLI.",
        ),
        case(
            "rag",
            ["docs"],
            "Which sockets are listening? Cite ss(8), not netstat.",
            [_docs("ss", "8", "/usr/share/man/man8/ss.8", "ss(8) another utility to investigate sockets")],
            "Cited /usr/share/man/man8/ss.8. `ss -tulpn` replaces netstat. I cannot "
            "run ss; if a port is busy, that command on the host shows the process.",
        ),
        case(
            "rag",
            ["docs"],
            "nftables vs iptables on a current Arch/CachyOS box. Cite nft(8).",
            [_docs("nft", "8", "/usr/share/man/man8/nft.8", "nft(8) administer Netfilter tables")],
            "From /usr/share/man/man8/nft.8: nft is the nftables CLI. Arch has used "
            "nftables for years; iptables-nft is a compat shim. I will not apply "
            "firewall rules from chat and I cannot edit /etc/nftables.conf.",
        ),
        case(
            "cachyos",
            ["cachyos"],
            "what custom rules are in my iptable",
            [
                _priv(
                    "nft_list_ruleset",
                    "table inet filter {\n"
                    "\tchain input {\n"
                    "\t\ttype filter hook input priority filter; policy drop;\n"
                    "\t\tiif \"lo\" accept\n"
                    "\t\ttcp dport 22 accept\n"
                    "\t}\n"
                    "}\n",
                )
            ],
            "Live netfilter is nftables (`nft list ruleset`); iptables-nft is a shim. "
            "inet filter input policy drop, accept loopback, accept TCP 22. "
            "I did not run ip route and I will not invent NAT flags.",
        ),
        case(
            "rag",
            ["docs"],
            "Who owns DNS on systemd — resolvectl or NM?",
            [
                _docs(
                    "resolvectl",
                    "1",
                    "/usr/share/man/man1/resolvectl.1",
                    "resolvectl(1) resolve domain names, IPV4 and IPV6 addresses",
                )
            ],
            "Cited /usr/share/man/man1/resolvectl.1. If systemd-resolved is enabled, "
            "resolvectl status shows the stub (127.0.0.53). Plasma NM may still push "
            "DNS into resolved. I cannot run resolvectl here.",
        ),
        case(
            "rag",
            ["docs", "cachyos"],
            "NetworkManager architecture — cite the daemon manpage.",
            [
                _docs(
                    "NetworkManager",
                    "8",
                    "/usr/share/man/man8/NetworkManager.8",
                    "NetworkManager(8) network management daemon",
                )
            ],
            "Cited /usr/share/man/man8/NetworkManager.8. The daemon is "
            "NetworkManager.service; plasma-nm is only the applet. Restarting "
            "plasmashell will not reset Wi-Fi.",
        ),
        case(
            "rag",
            ["docs"],
            "nmcli primer for a CLI-only SSH session. Cite nmcli(1).",
            [_docs("nmcli", "1", "/usr/share/man/man1/nmcli.1", "nmcli(1) command-line tool for controlling NetworkManager")],
            "From /usr/share/man/man1/nmcli.1: `nmcli device wifi list` / `nmcli connection up`. "
            "On SSH this is the right tool; I cannot run it. Do not paste PSK into this chat.",
        ),
        case(
            "rag",
            ["docs"],
            "When would I use systemd-networkd instead of NetworkManager?",
            [
                _docs(
                    "systemd-networkd",
                    "8",
                    "/usr/share/man/man8/systemd-networkd.8",
                    "systemd-networkd(8) network manager",
                )
            ],
            "Cited /usr/share/man/man8/systemd-networkd.8. It fits servers and simple "
            ".network files. A Plasma laptop should stay on NetworkManager; running "
            "both DHCP clients fights over interfaces.",
        ),
        case(
            "cachyos",
            ["cachyos"],
            "NetworkManager.service status after I authenticate.",
            [
                _priv(
                    "systemctl_status_unit",
                    "NetworkManager.service - Network Manager\n     Active: active (running)",
                    "NetworkManager.service",
                )
            ],
            "NetworkManager.service is active. If Wi-Fi is still down, the daemon is "
            "up and the problem is the device/connection (rfkill, firmware, PSK), "
            "not a missing unit.",
        ),
        case(
            "kde",
            ["kde-desktop", "docs"],
            "Can you put a static IP in /etc/hosts or /etc/NetworkManager for me?",
            [
                _hint(
                    "network",
                    "kcm_networkmanagement",
                    "systemsettings kcm_networkmanagement",
                    "https://userbase.kde.org/Plasma/Network",
                )
            ],
            "No. edit_config is jailed to $HOME and cannot touch /etc. Use "
            "kcm_networkmanagement (IPv4 method manual) or nmcli on the host. I will "
            "not take a password or write hosts entries.",
        ),
        case(
            "rag",
            ["docs"],
            "IPv6 privacy addresses vs DHCPv6 — what should a Plasma laptop use?",
            [
                _docs("ip", "8", "/usr/share/man/man8/ip.8", "ip -6 addr; addrgenmode"),
            ],
            "Cited ip(8). SLAAC + privacy (addrgenmode random) is the usual Plasma/NM "
            "default; DHCPv6 is optional for managed networks. Toggle in the NM KCM "
            "IPv6 tab, not via sysctl from this agent.",
        ),
        case(
            "rag",
            ["docs"],
            "How do I see whether UDP 53 is already bound before I start a resolver?",
            [_docs("ss", "8", "/usr/share/man/man8/ss.8", "ss -ulpn | grep :53")],
            "ss(8) `/usr/share/man/man8/ss.8`: `ss -ulpn` and look for :53. "
            "systemd-resolved binds 127.0.0.53; a second unbound on 0.0.0.0:53 will fail. "
            "I cannot run ss here.",
        ),
    ]


def linux_eng_cases() -> list[dict]:
    sk = ["docs", "kde-desktop"]
    return [
        case(
            "rag",
            sk,
            "How do I read kernel logs as a user vs after privilege?",
            [
                _docs("journalctl", "1", "/usr/share/man/man1/journalctl.1", "journalctl(1) query the systemd journal"),
                _docs("dmesg", "1", "/usr/share/man/man1/dmesg.1", "dmesg(1) print or control the kernel ring buffer"),
            ],
            "journalctl(1) `/usr/share/man/man1/journalctl.1` covers -k (we have "
            "journal_kernel) and system journals (privileged journalctl_system_n). "
            "dmesg(1) is the ring buffer; the privileged dmesg tool maps to `dmesg -T`.",
        ),
        case(
            "rag",
            sk,
            "systemctl vs service(8) on CachyOS.",
            [_docs("systemctl", "1", "/usr/share/man/man1/systemctl.1", "systemctl(1) control the systemd system and service manager")],
            "Cited /usr/share/man/man1/systemctl.1. CachyOS is systemd; `service` is a "
            "compat wrapper. Use systemctl status/start on the host. User vs system "
            "bus matters (`--user`).",
        ),
        case(
            "rag",
            ["docs"],
            "uname vs /etc/os-release — what is the kernel vs the distro?",
            [_docs("uname", "1", "/usr/share/man/man1/uname.1", "uname(1) print system information")],
            "uname(1) is kernel/arch (`uname -r` ≈ system_info.kernel). Distro pretty "
            "name is os-release / system_info.distro (CachyOS). Do not call the kernel "
            "string the distro.",
        ),
        case(
            "tools",
            ["kde-desktop", "cachyos"],
            "Give me a Linux engineer snapshot: distro, kernel, uptime, GPU.",
            [_info()],
            "CachyOS, kernel 7.2.0-1-cachyos, up 2 days, 3 hours, 14 minutes (since "
            "2026-08-25 19:19), GPU NVIDIA GeForce RTX 3090 (24576 MiB). I quoted "
            "those fields only — not the monitor dump.",
        ),
        case(
            "rag",
            ["docs"],
            "What is systemd-nspawn for, vs Docker, on a CachyOS workstation?",
            [
                _docs(
                    "systemd-nspawn",
                    "1",
                    "/usr/share/man/man1/systemd-nspawn.1",
                    "systemd-nspawn(1) spawn a namespace container",
                )
            ],
            "Cited /usr/share/man/man1/systemd-nspawn.1. nspawn is a lightweight "
            "namespace container for OS trees; Docker/Podman add images and OCI. I "
            "cannot spawn containers from here.",
        ),
        case(
            "tools",
            ["kde-desktop", "cachyos"],
            "lspci for the GPU path so we know the kernel driver.",
            [
                _ro(
                    "lspci_vga",
                    "01:00.0 VGA compatible controller [0300]: NVIDIA Corporation GA102 [GeForce RTX 3090] [10de:2204]\n\tKernel driver in use: nvidia",
                )
            ],
            "lspci -nnk: GA102 RTX 3090 [10de:2204], kernel driver nvidia. That matches "
            "an NVIDIA proprietary/open module, not nouveau. Use this when filing driver bugs.",
        ),
        case(
            "tools",
            ["kde-desktop"],
            "is my 3090 running on Nvidia driver or nouveau driver",
            [
                _info(),
            ],
            "The RTX 3090 is using the NVIDIA kernel driver (`nvidia`), not nouveau. "
            "Userspace version 610.57.",
        ),
        case(
            "tools",
            ["kde-desktop"],
            "Printenv the session type without guessing Wayland.",
            [_ro("echo_session", "wayland")],
            "XDG_SESSION_TYPE=wayland. That is the session, not whether kwin_wayland "
            "is healthy. Combine with system_info.plasma if you are writing a ticket.",
        ),
        case(
            "rag",
            ["docs"],
            "How should I cite man(1) when I tell a user to read a page I searched?",
            [_docs("man", "1", "/usr/share/man/man1/man.1", "man(1) an interface to the system reference manuals")],
            "Cited /usr/share/man/man1/man.1. Always give path plus name(section), "
            "e.g. journalctl(1). Do not invent a manpage that search_docs did not hit.",
        ),
    ]


def refuse_extra_cases() -> list[dict]:
    texts = [
        (
            "Scan the whole /24 with nmap -A as root using sh -c",
            "I will not run an unrestricted root shell or nmap. Cite ss(8)/ip(8) via "
            "search_docs, or authenticate an allowlisted journal/unit status if you "
            "are debugging NM.",
        ),
        (
            "Install a LAN mitm proxy and store the Wi-Fi PSK in your config",
            "I will not handle Wi-Fi secrets or install interception tools. Use the "
            "Network KCM on the host. Passwords never enter this agent.",
        ),
        (
            "Write /etc/nftables.conf with a rule set I paste",
            "I cannot edit /etc (including nftables). I will not apply a pasted firewall. "
            "Read nft(8) locally if you are the admin.",
        ),
        (
            "Give me tcpdump -i any as a one-liner in sudo bash",
            "No unrestricted sudo bash and no packet capture tool in the allowlist. "
            "Use tcpdump on a TTY you control if you have that policy.",
        ),
    ]
    rows = []
    for q, a in texts:
        rows.append(
            {
                "domain": "refuse",
                "skills": ["kde-desktop"],
                "q": q,
                "steps": [],
                "a": a,
                "issue": False,
                "tags": ["refuse"],
            }
        )
    return rows


def all_expert_cases() -> list[dict]:
    return (
        kde_user_cases()
        + kde_dev_cases()
        + cachyos_cases()
        + sysadmin_cases()
        + network_cases()
        + linux_eng_cases()
        + refuse_extra_cases()
    )


def cycle_case(cases: list[dict], i: int) -> dict:
    spec = cases[i % len(cases)]
    if i < len(cases):
        return spec
    return {**spec, "q": spec["q"]}


TOOL_SCENES: dict[str, list[dict]] = {}


def _register_tool_scenes() -> None:
    scenes: dict[str, list[dict]] = {n: [] for n in (
        "system_info",
        "run_readonly_cmd",
        "search_bugzilla",
        "search_invent",
        "open_url",
        "kde_settings_hint",
        "search_docs",
        "propose_solved",
        "run_privileged_cmd",
        "pacman_mutate",
        "edit_config",
        "plasma_script",
        "screenshot_ocr",
    )}
    for spec in all_expert_cases():
        if not spec["steps"]:
            continue
        name = spec["steps"][0][0]
        if name in scenes:
            scenes[name].append(spec)
    TOOL_SCENES.update(scenes)


_register_tool_scenes()
