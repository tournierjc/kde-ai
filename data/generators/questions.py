"""Speech-act paraphrases for the 30k mix.

Gold stays a small reviewed seed. Train/eval rewrite the same trajectories as
how / where / I-want / best-way / example questions so the model can answer
natural how-tos instead of memorizing one gold string or ``Quote foo (42)``.
"""

from __future__ import annotations

from data.generators.common import assistant_text, user

# Infinitive phrases → user questions. Persist is its own topic, not a wrap.
_HOWTO_TEMPLATES = (
    "how do I {topic}",
    "how can i {topic}",
    "where can i {topic}",
    "where can I {topic}?",
    "i want to {topic}, how can i do it",
    "i need to {topic}, what is the best way",
    "what's the best way to {topic}",
    "what is the best way to {topic}",
    "give me an example of how to {topic}",
    "can you explain how to {topic}",
    "I would like to {topic}",
    "please tell me how to {topic}",
    "on this Plasma/CachyOS box, how do I {topic}",
)

_LOOKUP_TEMPLATES = (
    "{q}",
    "{q} Use tools, do not guess.",
    "Tell me, live: {q}",
    "What is the current answer to: {q}",
)

_ACTION_TEMPLATES = (
    "{q}",
    "please {q}",
    "can you {q}",
    "go ahead and {q}",
)

_SEARCH_TEMPLATES = (
    "{q}",
    "Search first: {q}",
    "Find a duplicate for this: {q}",
)

_HOWTO_PREFIXES = (
    "how ",
    "where ",
    "what's the best",
    "what is the best",
    "cite ",
    "explain ",
    "can you ",
)

# Natural how-tos for manpage RAG rows (not "Quote title from local docs").
MAN_HOWTO: dict[str, dict[str, object]] = {
    "ls": {
        "topics": ["list files with ls", "list a directory"],
        "answer": (
            "From /usr/share/man/man1/ls.1 (ls(1)): `ls -l` is the long listing. "
            "This agent has no general ls tool; run it on a TTY."
        ),
    },
    "pacman": {
        "topics": ["query packages with pacman", "use pacman on CachyOS"],
        "answer": (
            "From /usr/share/man/man8/pacman.8 (pacman(8)): `-Qi`/`-Qs` query; "
            "installs are pacman_mutate after you confirm. I will not -Syu."
        ),
    },
    "journalctl": {
        "topics": ["read systemd logs", "query the journal"],
        "answer": (
            "From /usr/share/man/man1/journalctl.1 (journalctl(1)): `-k` is "
            "journal_kernel; system journals need privileged journalctl_system_n."
        ),
    },
    "systemctl": {
        "topics": ["control a systemd service", "use systemctl"],
        "answer": (
            "From /usr/share/man/man1/systemctl.1 (systemctl(1)): CachyOS is systemd. "
            "User vs system bus matters (`--user`). `service` is a compat wrapper."
        ),
    },
    "kwin_wayland": {
        "topics": ["cite the KWin Wayland compositor", "debug kwin_wayland"],
        "answer": (
            "Cited /usr/share/man/man1/kwin_wayland.1 (kwin_wayland(1)). Attach "
            "user journal for plasma-kwin_wayland plus live Plasma/Qt/session."
        ),
    },
    "man": {
        "topics": ["read a manpage", "cite a man page"],
        "answer": (
            "From /usr/share/man/man1/man.1 (man(1)): give path plus name(section). "
            "Do not invent a page search_docs did not hit."
        ),
    },
    "uname": {
        "topics": ["tell kernel from distro", "use uname"],
        "answer": (
            "From /usr/share/man/man1/uname.1 (uname(1)): `uname -r` is the kernel. "
            "Distro pretty-name is os-release / system_info.distro."
        ),
    },
    "dmesg": {
        "topics": ["read the kernel ring buffer", "use dmesg"],
        "answer": (
            "From /usr/share/man/man1/dmesg.1 (dmesg(1)): the privileged dmesg tool "
            "maps to `dmesg -T`. journal_kernel is the user-readable `-k` path."
        ),
    },
    "ip": {
        "topics": ["inspect addresses and routes", "see my IP routes"],
        "answer": (
            "From /usr/share/man/man8/ip.8 (ip(8)): `ip -br addr` and `ip route`. "
            "No ip tool here; run those on the host. Plasma NM is the GUI."
        ),
    },
    "ss": {
        "topics": ["see listening sockets", "check which ports are bound"],
        "answer": (
            "From /usr/share/man/man8/ss.8 (ss(8)): `ss -tulpn` replaces netstat. "
            "I cannot run ss; use it on the host."
        ),
    },
    "nft": {
        "topics": ["inspect nftables rules", "use nft instead of iptables"],
        "answer": (
            "From /usr/share/man/man8/nft.8 (nft(8)): nft is the nftables CLI. "
            "Arch uses nftables; iptables-nft is a shim. Live dump is nft_list_ruleset."
        ),
    },
    "resolvectl": {
        "topics": ["see which DNS systemd is using", "use resolvectl"],
        "answer": (
            "From /usr/share/man/man1/resolvectl.1 (resolvectl(1)): if resolved is "
            "on, `resolvectl status` shows the stub. Plasma NM may still push DNS."
        ),
    },
    "NetworkManager": {
        "topics": ["understand NetworkManager vs plasma-nm", "manage network with NM"],
        "answer": (
            "From /usr/share/man/man8/NetworkManager.8: the daemon is "
            "NetworkManager.service; plasma-nm is only the applet."
        ),
    },
    "nmcli": {
        "topics": ["control NetworkManager from the CLI", "use nmcli"],
        "answer": (
            "From /usr/share/man/man1/nmcli.1 (nmcli(1)): `nmcli device wifi list` / "
            "`connection up`. I cannot run it. Do not paste a PSK into chat."
        ),
    },
    "systemd-networkd": {
        "topics": ["choose networkd vs NetworkManager", "use systemd-networkd"],
        "answer": (
            "From /usr/share/man/man8/systemd-networkd.8: fits servers and .network "
            "files. A Plasma laptop should stay on NetworkManager."
        ),
    },
    "sysctl": {
        "topics": ["set a sysctl", "persist net.ipv4.ip_forward"],
        "answer": (
            "From /usr/share/man/man8/sysctl.8 (sysctl(8)): runtime or sysctl.d. "
            "I cannot write /etc/sysctl.d from tools."
        ),
    },
    "mount": {
        "topics": ["mount a filesystem", "use mount"],
        "answer": (
            "From /usr/share/man/man8/mount.8 (mount(8)): runtime mounts. Static boot "
            "entries are fstab(5). I cannot edit /etc/fstab."
        ),
    },
    "fstab": {
        "topics": ["add a boot mount", "configure fstab"],
        "answer": (
            "From /usr/share/man/man5/fstab.5 (fstab(5)): static boot mounts. "
            "I cannot edit /etc/fstab (home jail). Check UUID vs noauto on the host."
        ),
    },
    "environment.d": {
        "topics": [
            "set an environment variable",
            "define an env variable",
            "configure an environment variable",
            "persist an environment variable for GUI apps",
            "set a session environment variable for Plasma",
        ],
        "answer": (
            "Not a System Settings KCM. For the Plasma session use systemd "
            "environment.d(5) (`/usr/share/man/man5/environment.d.5`): drop "
            "`KEY=value` files in `~/.config/environment.d/`. System-wide is "
            "`/etc/environment`. `export` in `~/.bashrc` only affects terminals. "
            "Log out to apply. Example:\n\nEDITOR=nvim\n"
        ),
    },
    "pacman.conf": {
        "topics": ["add a pacman repo", "edit pacman.conf"],
        "answer": (
            "From /usr/share/man/man5/pacman.conf.5: extra repos are Server= lines. "
            "I will not add chaotic-aur via tools (cannot edit /etc)."
        ),
    },
    "mkinitcpio": {
        "topics": ["rebuild the initramfs", "run mkinitcpio"],
        "answer": (
            "From /usr/share/man/man8/mkinitcpio.8: pacman hooks usually run it on "
            "nvidia-dkms or linux-cachyos updates. Tools cannot invoke mkinitcpio."
        ),
    },
    "systemd.timer": {
        "topics": ["create a systemd timer", "list systemd timers"],
        "answer": (
            "From /usr/share/man/man5/systemd.timer.5: a .timer activates a matching "
            ".service. List with `systemctl list-timers` on the host."
        ),
    },
    "systemd.nspawn": {
        "topics": ["use systemd-nspawn", "spawn a namespace container"],
        "answer": (
            "From /usr/share/man/man1/systemd-nspawn.1: lightweight OS-tree containers. "
            "I cannot spawn containers from here."
        ),
    },
    "cgroups": {
        "topics": ["limit a process with cgroups", "use cgroup v2 slices"],
        "answer": (
            "From /usr/share/man/man7/cgroups.7: systemd uses the unified hierarchy. "
            "I cannot set CPUWeight here; systemd-run --user on the host can."
        ),
    },
    "capabilities": {
        "topics": ["use Linux capabilities instead of root", "understand capabilities"],
        "answer": (
            "From /usr/share/man/man7/capabilities.7: CAP_NET_ADMIN covers many nft/ip "
            "ops without a root shell. This agent still will not run unrestricted argv."
        ),
    },
    "qdbus": {
        "topics": ["inspect Plasma DBus", "list org.kde services"],
        "answer": (
            "From /usr/share/man/man1/qdbus.1 (qdbus(1)): list org.kde.* on the session "
            "bus. I cannot run qdbus; cite that page and a kcm id from kde_settings_hint."
        ),
    },
    "cmake": {
        "topics": ["build a Plasma 6 applet with cmake", "cite cmake for Kirigami"],
        "answer": (
            "From /usr/share/man/man1/cmake.1 (cmake(1)): Plasma 6 applets use "
            "extra-cmake-modules and KF6, not kdelibs4."
        ),
    },
}


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(s.strip() for s in items if s and s.strip()))


def howto_questions(topic: str) -> list[str]:
    topic = topic.strip().rstrip("?.")
    return _dedupe([t.format(topic=topic) for t in _HOWTO_TEMPLATES])


def infer_intent(spec: dict) -> str:
    if spec.get("intent"):
        return str(spec["intent"])
    tags = spec.get("tags") or []
    if spec.get("domain") == "refuse" or "refuse" in tags:
        return "refuse"
    names = [s[0] for s in (spec.get("steps") or [])]
    q = (spec.get("q") or "").strip().lower()
    if not names:
        return "info"
    if names[0] in {
        "screenshot_ocr",
        "plasma_script",
        "edit_config",
        "pacman_mutate",
        "open_url",
    }:
        return "action"
    if "search_bugzilla" in names or "search_invent" in names:
        return "search"
    if "search_docs" in names or "kde_settings_hint" in names:
        return "howto"
    if "propose_solved" in names:
        return "solve"
    if names[0] in {"system_info", "run_readonly_cmd", "run_privileged_cmd"}:
        if q.startswith(_HOWTO_PREFIXES):
            return "howto"
        return "lookup"
    return "howto"


def _topic_from_question(q: str) -> str | None:
    raw = q.strip().rstrip("?")
    lower = raw.lower()
    for prefix in (
        "Where do I ",
        "Where can I ",
        "where can i ",
        "where do i ",
        "How do I ",
        "How can I ",
        "how do I ",
        "how can i ",
        "How does ",
        "Cite ",
        "Explain ",
        "What's the best way to ",
        "What is the best way to ",
        "what's the best way to ",
        "what is the best way to ",
    ):
        if lower.startswith(prefix.lower()):
            rest = raw[len(prefix) :].strip()
            return rest[:1].lower() + rest[1:] if rest else None
    return None


def paraphrase_pool(spec: dict) -> list[str]:
    original = (spec.get("q") or "").strip()
    intent = infer_intent(spec)
    topics = list(spec.get("topics") or [])
    derived = _topic_from_question(original)
    if derived and derived not in topics:
        topics.append(derived)
    if intent == "howto":
        pool: list[str] = [original]
        for topic in topics:
            pool.extend(howto_questions(topic))
        return _dedupe(pool) or [original]
    if intent == "lookup":
        return _dedupe([t.format(q=original) for t in _LOOKUP_TEMPLATES])
    if intent == "action":
        q = original[0].lower() + original[1:] if original else original
        return _dedupe([t.format(q=q) for t in _ACTION_TEMPLATES])
    if intent == "search":
        return _dedupe([t.format(q=original) for t in _SEARCH_TEMPLATES])
    return [original]


def paraphrase_question(spec: dict, index: int) -> str:
    pool = paraphrase_pool(spec)
    return pool[index % len(pool)]


def maybe_example_turns(spec: dict, index: int) -> list[dict]:
    example = spec.get("example")
    if not example or index % 6 != 0:
        return []
    return [user("give me an example"), assistant_text(str(example))]


def manpage_howto(title: str, sec: str, path: str, index: int) -> tuple[str, str]:
    meta = MAN_HOWTO.get(title) or {}
    topics = list(meta.get("topics") or [f"use {title}"])
    pool: list[str] = [f"Cite the local manpage for {title}."]
    for topic in topics:
        pool.extend(howto_questions(str(topic)))
    q = _dedupe(pool)[index % len(_dedupe(pool))]
    answer = str(
        meta.get("answer")
        or f"Cited {path} — {title}({sec}). I am not inventing the path."
    )
    return q, answer
