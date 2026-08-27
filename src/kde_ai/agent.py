from __future__ import annotations

import json
import threading
import uuid

from kde_ai.errors import (
    BUSY,
    DISABLED,
    PAUSED,
    PRIVILEGE_CANCELLED,
    PRIVILEGE_TIMEOUT,
    TOOL_DENIED,
    VALIDATION,
    RpcError,
)
from kde_ai.issue import IssueManager, looks_like_issue
from kde_ai.logutil import log
from kde_ai.prompting import approx_tokens, assemble, clip_tokens, load_system_prompt
from kde_ai.skills import ALL_TOOLS, enabled_ids, load_all_skills
from kde_ai.tools import ToolContext, clip
from kde_ai.tools.registry import HANDLERS, SCHEMAS
from kde_ai.tools.system_info import handle as system_info_handle
from kde_ai.tools.system_info import is_hardware_lookup, is_hardware_question, prefer_hardware_reply


class Agent:
    def __init__(self, cfg, store, llm, watchdog, notify):
        self.cfg = cfg
        self.store = store
        self.llm = llm
        self.watchdog = watchdog
        self.notify = notify
        self.issues = IssueManager(store, int(cfg.get("issue.max_attempts", 3)))
        self._lock = threading.Lock()
        self.stream_id: str | None = None
        self.busy_session: str | None = None
        self._priv_event: threading.Event | None = None
        self._priv_result: dict | None = None
        self._priv_id: str | None = None
        self._cancel = False
        self.awaiting_privilege = False
        self.last_solution = ""

    def busy(self) -> bool:
        return self.stream_id is not None

    def cancel(self, stream_id: str) -> None:
        if self.stream_id == stream_id:
            self._cancel = True

    def privilege_complete(self, request_id: str, payload: dict) -> dict:
        if request_id != self._priv_id:
            raise RpcError(VALIDATION, "unknown privilege request")
        self._priv_result = payload
        if self._priv_event:
            self._priv_event.set()
        return {"ok": True}

    def request_privilege(self, argv: list[str], reason: str) -> dict:
        client = getattr(self, "client_kind", "cli")
        if client == "flatpak-ui":
            raise RpcError(
                PRIVILEGE_CANCELLED,
                "privileged tools require host kde-ai CLI or native plasmoid",
            )
        self._priv_id = str(uuid.uuid4())
        self._priv_event = threading.Event()
        self._priv_result = None
        self.awaiting_privilege = True
        self.notify(
            "privilege.required",
            {
                "request_id": self._priv_id,
                "session_id": self.busy_session,
                "argv": argv,
                "reason": reason,
            },
        )
        ok = self._priv_event.wait(120)
        self.awaiting_privilege = False
        self._priv_id = None
        if not ok:
            raise RpcError(PRIVILEGE_TIMEOUT, "privilege prompt timed out")
        res = self._priv_result or {}
        if res.get("cancelled"):
            raise RpcError(PRIVILEGE_CANCELLED, "user cancelled privilege")
        return {
            "ok": bool(res.get("ok")),
            "stdout": res.get("stdout") or "",
            "stderr": res.get("stderr") or "",
            "code": res.get("code", 1),
        }

    def start_chat(self, session_id: str, message: str, issue_hint: bool, client_kind: str, locale: str) -> str:
        if not self.cfg.get("daemon.enabled", True):
            raise RpcError(DISABLED, "agent disabled")
        self.watchdog.poll()
        if self.watchdog.paused and not self.cfg.get("daemon.force_run_during_pause"):
            raise RpcError(PAUSED, self.watchdog.reason or "GPU in use")
        with self._lock:
            if self.stream_id:
                raise RpcError(BUSY, "busy", {"active_session_id": self.busy_session})
            meta = self.store.load_meta(session_id)
            if meta.get("issue_mode") and meta.get("pending_solution"):
                raise RpcError(VALIDATION, "confirm or cancel the pending solution first")
            self.stream_id = str(uuid.uuid4())
            self.busy_session = session_id
            self._cancel = False
            self.client_kind = client_kind
        threading.Thread(
            target=self._run,
            args=(self.stream_id, session_id, message, issue_hint, locale),
            daemon=True,
        ).start()
        return self.stream_id

    def _finish(self, stream_id: str, reason: str, error: str | None = None) -> None:
        self.notify("stream.done", {"stream_id": stream_id, "reason": reason, "error": error})
        with self._lock:
            if self.stream_id == stream_id:
                self.stream_id = None
                self.busy_session = None

    def _run(self, stream_id: str, sid: str, message: str, issue_hint: bool, locale: str) -> None:
        try:
            self._chat_loop(stream_id, sid, message, issue_hint, locale)
        except RpcError as exc:
            self._finish(stream_id, "error", exc.message)
        except Exception as exc:
            log.exception("agent crash")
            self._finish(stream_id, "error", str(exc))

    def _chat_loop(self, stream_id: str, sid: str, message: str, issue_hint: bool, locale: str) -> None:
        meta = self.store.load_meta(sid)
        patterns = self.cfg.get("issue.patterns")
        if issue_hint or looks_like_issue(message, patterns) or meta.get("issue_mode"):
            meta = self.issues.enter(sid, message if not meta.get("issue_text") else meta.get("issue_text"))
        self.store.append_turn(sid, {"role": "user", "content": message})

        skills = load_all_skills()
        eids = enabled_ids(
            self.cfg.get("skills.enabled") or [],
            meta.get("skills_enabled"),
            skills,
            int(self.cfg.get("skills.max_enabled_per_session", 3)),
        )
        bodies = []
        tool_sets = []
        for eid in eids:
            sk = skills[eid]
            bodies.append(clip_tokens(sk.body, int(self.cfg.get("skills.prompt_tok_each", 400))))
            if sk.tools:
                tool_sets.append(set(sk.tools))
        allowed = None
        if tool_sets:
            allowed = set.intersection(*tool_sets) & ALL_TOOLS
            allowed = list(allowed) if allowed else list(ALL_TOOLS)
        if is_hardware_lookup(message, self.store.working_messages(sid)):
            if allowed is None or "system_info" in allowed:
                allowed = ["system_info"]

        rag_bits: list[str] = []
        failed = ""
        aid = meta.get("open_attempt_id")
        attempt_dir = self.store.attempt_dir(sid, aid) if aid else None
        if aid:
            att_root = self.store.root(sid) / "attempts"
            notes = []
            if att_root.is_dir():
                for d in att_root.iterdir():
                    fp = d / "failed.json"
                    if fp.exists():
                        notes.append(fp.read_text(encoding="utf-8"))
            failed = "Failed attempts:\n" + "\n".join(notes) if notes else ""

        system = load_system_prompt(locale)
        schema_list = [s for s in SCHEMAS if allowed is None or s["name"] in allowed]
        caps = {
            "solved_tok": self.cfg.get("memory.solved_tok", 400),
            "pins_tok": self.cfg.get("memory.pins_tok", 200),
            "summary_tok": self.cfg.get("memory.summary_tok", 600),
            "rag_tok": self.cfg.get("memory.rag_tok", 800),
            "prompt_tok_each": self.cfg.get("skills.prompt_tok_each", 400),
            "tool_reserve": approx_tokens(json.dumps(schema_list, ensure_ascii=False)) + 256,
        }
        sys_text, working, stats = assemble(
            system=system,
            skill_bodies=bodies,
            solved=self.store.solved(sid),
            pins=self.store.pins(sid),
            summary=self.store.summary(sid),
            rag_bits=rag_bits,
            working=self.store.working_messages(sid),
            failed_notes=failed,
            caps=caps,
            ctx=int(self.cfg.get("llm.ctx", 4096)),
        )
        if stats.get("overflow"):
            meta = self.store.load_meta(sid)
            meta["overflow"] = True
            self.store.save_meta(meta)

        messages = [{"role": "system", "content": sys_text}]
        for m in working:
            messages.append(m)

        schemas = schema_list
        max_rounds = int(self.cfg.get("llm.max_tool_rounds", 6))
        final_text = ""
        hw_payload: dict | None = None
        for _ in range(max_rounds + 1):
            if self._cancel:
                self._finish(stream_id, "cancel")
                return
            self.watchdog.poll()
            if self.watchdog.paused and not self.cfg.get("daemon.force_run_during_pause"):
                if self.awaiting_privilege:
                    pass
                else:
                    self.llm.unload()
                    self._finish(stream_id, "paused", self.watchdog.reason)
                    return
            data = self.llm.chat(messages, schemas, allowed)
            choice = (data.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            tool_calls = msg.get("tool_calls") or []
            content = msg.get("content") or ""
            if not tool_calls:
                if not hw_payload and is_hardware_question(message, working):
                    try:
                        hw_payload = system_info_handle({}, None)
                    except Exception:
                        hw_payload = None
                    if hw_payload:
                        preview = clip(json.dumps(hw_payload, ensure_ascii=False), 500)
                        self.notify(
                            "stream.tool",
                            {"stream_id": stream_id, "name": "system_info", "arguments": {}},
                        )
                        self.notify(
                            "stream.tool",
                            {
                                "stream_id": stream_id,
                                "name": "system_info",
                                "arguments": {},
                                "result_preview": preview,
                            },
                        )
                if hw_payload:
                    content = prefer_hardware_reply(message, content, hw_payload, working)
                if content:
                    self.notify("stream.token", {"stream_id": stream_id, "text": content})
                    final_text += content
                    self.store.append_turn(sid, {"role": "assistant", "content": content})
                self._finish(stream_id, "complete")
                return
            if content:
                self.notify("stream.token", {"stream_id": stream_id, "text": content})
                final_text += content
            assistant_msg = {"role": "assistant", "content": content or "", "tool_calls": tool_calls}
            messages.append(assistant_msg)
            self.store.append_turn(sid, assistant_msg)
            for tc in tool_calls:
                fn = (tc.get("function") or {})
                name = fn.get("name")
                raw_args = fn.get("arguments") or "{}"
                try:
                    arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    arguments = {}
                self.notify(
                    "stream.tool",
                    {"stream_id": stream_id, "name": name, "arguments": arguments},
                )
                if name == "propose_solved" and not self.store.load_meta(sid).get("issue_mode"):
                    result = {"ok": True, "ignored_not_issue_mode": True}
                elif name not in HANDLERS:
                    result = {"ok": False, "error": TOOL_DENIED}
                else:
                    ctx = ToolContext(
                        self.cfg,
                        self.store,
                        sid,
                        attempt_dir,
                        self.notify,
                        self.request_privilege,
                    )
                    try:
                        result = HANDLERS[name](arguments, ctx)
                    except RpcError as exc:
                        result = {"ok": False, "error": exc.code, "message": exc.message}
                preview = clip(json.dumps(result, ensure_ascii=False), 500)
                self.notify(
                    "stream.tool",
                    {
                        "stream_id": stream_id,
                        "name": name,
                        "arguments": arguments,
                        "result_preview": preview,
                    },
                )
                tool_msg = {
                    "role": "tool",
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False)[: self.cfg.get("memory.tool_result_chars", 2000)],
                }
                messages.append(tool_msg)
                self.store.append_turn(sid, tool_msg)
                if name == "system_info" and isinstance(result, dict) and result.get("ok"):
                    hw_payload = result
                if name == "search_docs" and result.get("hits"):
                    rag_bits.extend(
                        f"{h.get('path')}: {h.get('snippet')}" for h in result["hits"][:5]
                    )
            meta = self.store.load_meta(sid)
            if meta.get("pending_solution"):
                self.last_solution = meta.get("pending_solution") or ""
                self._finish(stream_id, "complete")
                return
        if final_text:
            self.store.append_turn(sid, {"role": "assistant", "content": final_text})
        self._finish(stream_id, "complete")
