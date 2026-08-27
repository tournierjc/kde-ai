from __future__ import annotations

import os
import re
import time
from pathlib import Path

from kde_ai.logutil import log

try:
    import pynvml  # type: ignore
except Exception:
    pynvml = None


class GpuWatchdog:
    def __init__(self, cfg, self_pids: set[int]) -> None:
        self.cfg = cfg
        self.self_pids = set(self_pids)
        self.paused = False
        self.reason = ""
        self.blocker_pid: int | None = None
        self._clear_since: float | None = None
        self._nvml_ok = False
        if pynvml:
            try:
                pynvml.nvmlInit()
                self._nvml_ok = True
            except Exception as exc:
                log.info("nvml unavailable: %s", exc)

    def add_pid(self, pid: int) -> None:
        self.self_pids.add(pid)

    def _pid_uses_gpu(self, pid: int) -> bool:
        if self._nvml_ok and pid in self._compute_pids():
            return True
        fd_dir = Path(f"/proc/{pid}/fd")
        if fd_dir.is_dir():
            try:
                for ent in fd_dir.iterdir():
                    try:
                        target = os.readlink(ent)
                    except OSError:
                        continue
                    if "nvidia" in target.lower():
                        return True
            except OSError:
                pass
        return False

    def _compute_pids(self) -> set[int]:
        found: set[int] = set()
        if not self._nvml_ok:
            return found
        try:
            count = pynvml.nvmlDeviceGetCount()
            for i in range(count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                try:
                    procs = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
                except Exception:
                    continue
                for p in procs:
                    found.add(int(p.pid))
        except Exception:
            return found
        return found

    def _denylist_hit(self) -> tuple[bool, int | None, str]:
        patterns = [re.compile(p, re.I) for p in (self.cfg.get("gpu.denylist") or [])]
        proc = Path("/proc")
        if not proc.is_dir():
            return False, None, ""
        for d in proc.iterdir():
            if not d.name.isdigit():
                continue
            pid = int(d.name)
            if pid in self.self_pids:
                continue
            try:
                cmd = (d / "cmdline").read_bytes().replace(b"\x00", b" ").decode(errors="ignore")
                comm = (d / "comm").read_text(errors="ignore").strip()
            except Exception:
                continue
            blob = cmd + " " + comm
            for pat in patterns:
                if pat.search(blob) and self._pid_uses_gpu(pid):
                    return True, pid, comm or cmd[:80]
        return False, None, ""

    def _compute_hit(self) -> tuple[bool, int | None, str]:
        if not self._nvml_ok:
            return False, None, ""
        allow = [a.lower() for a in (self.cfg.get("gpu.graphics_allow") or [])]
        try:
            count = pynvml.nvmlDeviceGetCount()
            for i in range(count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                try:
                    procs = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
                except Exception:
                    continue
                for p in procs:
                    pid = int(p.pid)
                    if pid in self.self_pids:
                        continue
                    name = ""
                    try:
                        name = Path(f"/proc/{pid}/comm").read_text().strip()
                    except Exception:
                        pass
                    low = name.lower()
                    if any(a in low for a in allow):
                        continue
                    return True, pid, name or str(pid)
        except Exception:
            return False, None, ""
        return False, None, ""

    def poll(self) -> bool:
        if self.cfg.get("daemon.force_run_during_pause"):
            if self.paused:
                log.warning("force_run_during_pause: ignoring GPU contention")
            self.paused = False
            self.reason = ""
            self.blocker_pid = None
            return False
        hit, pid, why = self._denylist_hit()
        if not hit:
            hit, pid, why = self._compute_hit()
        now = time.time()
        hold = float(self.cfg.get("gpu.resume_hold_s", 10))
        if hit:
            self.paused = True
            self.reason = why
            self.blocker_pid = pid
            self._clear_since = None
            return True
        if self.paused:
            if self._clear_since is None:
                self._clear_since = now
            elif now - self._clear_since >= hold:
                self.paused = False
                self.reason = ""
                self.blocker_pid = None
                self._clear_since = None
        return self.paused
