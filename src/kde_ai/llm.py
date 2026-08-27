from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import httpx

from kde_ai.errors import LLM_ERROR, RpcError
from kde_ai.logutil import log
from kde_ai.paths import cache_dir, data_dir
from kde_ai.tools.registry import SCHEMAS

_LLAMA_SERVER_NAMES = ("llama-server", "llama.cpp-server")


def find_llama_server(configured: str | None = None) -> str | None:
    """Resolve llama-server: config path, PATH, then well-known install locations."""
    candidates: list[str] = []
    if configured:
        candidates.append(os.path.expanduser(str(configured)))
    candidates.extend(_LLAMA_SERVER_NAMES)
    for raw in candidates:
        path = Path(raw)
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
        found = shutil.which(raw)
        if found:
            return found
    extras = [
        Path("/usr/bin/llama-server"),
        Path("/usr/local/bin/llama-server"),
        Path.home() / ".local/bin/llama-server",
        data_dir() / "bin" / "llama-server",
    ]
    for path in extras:
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return None


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class LlamaRuntime:
    def __init__(self, cfg) -> None:
        self.cfg = cfg
        self.proc: subprocess.Popen | None = None
        self.port: int | None = None
        self.last_used = 0.0
        self.on_spawn = None

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def loaded(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def unload(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
        self.port = None

    def ensure(self) -> None:
        if self.loaded():
            self.last_used = time.time()
            return
        gguf = Path(os.path.expanduser(self.cfg.get("llm.gguf")))
        if not gguf.exists():
            raise RpcError(
                LLM_ERROR,
                f"GGUF missing at {gguf}; run scripts/fetch-gguf.sh",
            )
        binary = find_llama_server(self.cfg.get("llm.llama_server") or "llama-server")
        if not binary:
            raise RpcError(
                LLM_ERROR,
                "llama-server not found; install llama-cpp (sudo pacman -S llama-cpp)",
            )
        self.port = _free_port()
        cache_dir().mkdir(parents=True, exist_ok=True)
        cmd = [
            binary,
            "-m",
            str(gguf),
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
            "--ctx-size",
            str(self.cfg.get("llm.ctx", 4096)),
            "-ngl",
            str(self.cfg.get("llm.n_gpu_layers", 99)),
            "--jinja",
        ]
        log.info("starting llama-server on %s", self.port)
        self.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if self.proc.pid and self.on_spawn:
            self.on_spawn(self.proc.pid)
        deadline = time.time() + int(self.cfg.get("llm.load_timeout_s", 60))
        while time.time() < deadline:
            if self.proc.poll() is not None:
                self.proc = None
                raise RpcError(LLM_ERROR, "llama-server exited")
            try:
                r = httpx.get(f"{self.base}/health", timeout=1.0)
                if r.status_code < 500:
                    self.last_used = time.time()
                    return
            except Exception:
                time.sleep(0.25)
        self.unload()
        raise RpcError(LLM_ERROR, "llama-server health timeout")

    def chat(self, messages: list[dict], tools: list[dict] | None, allowed_tool_names: list[str] | None) -> dict:
        if os.environ.get("KDE_AI_FAKE_LLM") == "1":
            last = messages[-1].get("content") if messages else ""
            if "Plasma version" in str(last) or "plasma" in str(last).lower():
                return {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "c1",
                                        "type": "function",
                                        "function": {
                                            "name": "system_info",
                                            "arguments": "{}",
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }
            if any(m.get("role") == "tool" for m in messages):
                return {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "Your system looks healthy. I used live tools rather than guessing versions.",
                            }
                        }
                    ]
                }
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "I'm the local kde-ai helper. Ask about Plasma, CachyOS, or bugs.",
                        }
                    }
                ]
            }
        self.ensure()
        payload = {
            "model": "kde-ai",
            "messages": messages,
            "temperature": float(self.cfg.get("llm.temperature", 0.3)),
            "top_p": float(self.cfg.get("llm.top_p", 0.9)),
            "repeat_penalty": float(self.cfg.get("llm.repeat_penalty", 1.05)),
            "stream": False,
        }
        schemas = tools if tools is not None else SCHEMAS
        if allowed_tool_names is not None:
            schemas = [s for s in schemas if s["name"] in allowed_tool_names]
        if schemas:
            payload["tools"] = [
                {"type": "function", "function": s} for s in schemas
            ]
        try:
            r = httpx.post(
                f"{self.base}/v1/chat/completions",
                json=payload,
                timeout=float(self.cfg.get("llm.request_timeout_s", 120)),
            )
            r.raise_for_status()
            data = r.json()
        except RpcError:
            raise
        except Exception as exc:
            raise RpcError(LLM_ERROR, str(exc)) from exc
        self.last_used = time.time()
        return data
