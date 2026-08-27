from __future__ import annotations

import time
from collections import deque
from urllib.parse import quote

from kde_ai.errors import NETWORK, VALIDATION, RpcError
from kde_ai.undo import append_undo

_hits: deque[float] = deque()


def _rate() -> None:
    now = time.monotonic()
    while _hits and now - _hits[0] > 1.0:
        _hits.popleft()
    if len(_hits) >= 2:
        raise RpcError(NETWORK, "rate limited", {"retry-after": 1})
    _hits.append(now)


def _http_get(url: str, timeout: float, headers: dict | None = None) -> dict:
    import httpx

    try:
        r = httpx.get(url, timeout=timeout, headers=headers or {}, follow_redirects=True)
        return {"ok": r.status_code < 400, "status": r.status_code, "text": r.text, "json": None}
    except Exception as exc:
        raise RpcError(NETWORK, str(exc)) from exc


def search_bugzilla(args: dict, ctx) -> dict:
    if ctx.offline:
        raise RpcError(NETWORK, "offline")
    q = args.get("query")
    if not q:
        raise RpcError(VALIDATION, "query required")
    _rate()
    base = ctx.cfg.get("network.bugzilla_base", "https://bugs.kde.org")
    limit = int(args.get("limit") or 10)
    product = args.get("product")
    url = (
        f"{base}/rest/bug?summary={quote(str(q))}&limit={limit}"
        f"&include_fields=id,summary,status"
    )
    if product:
        url += f"&product={quote(str(product))}"
    raw = _http_get(url, ctx.timeout)
    bugs = []
    try:
        import json

        data = json.loads(raw["text"])
        for b in data.get("bugs") or []:
            bid = b.get("id")
            bugs.append(
                {
                    "id": bid,
                    "summary": b.get("summary"),
                    "status": b.get("status"),
                    "url": f"{base}/show_bug.cgi?id={bid}",
                }
            )
    except Exception:
        pass
    if ctx.attempt_dir:
        append_undo(ctx.attempt_dir, {"op": "noop", "reason": "read_only"})
    return {"ok": True, "bugs": bugs}


def search_invent(args: dict, ctx) -> dict:
    if ctx.offline:
        raise RpcError(NETWORK, "offline")
    q = args.get("query")
    if not q:
        raise RpcError(VALIDATION, "query required")
    _rate()
    from kde_ai.paths import invent_token_path

    headers = {}
    tok = invent_token_path()
    if tok.exists():
        headers["PRIVATE-TOKEN"] = tok.read_text(encoding="utf-8").strip()
    base = ctx.cfg.get("network.invent_base", "https://invent.kde.org")
    url = f"{base}/api/v4/search?scope=issues&search={quote(str(q))}"
    project = args.get("project")
    if project:
        url += f"&project={quote(str(project))}"
    raw = _http_get(url, ctx.timeout, headers)
    items = []
    try:
        import json

        data = json.loads(raw["text"])
        if isinstance(data, list):
            for it in data[: int(args.get("limit") or 10)]:
                items.append(
                    {
                        "id": it.get("iid") or it.get("id"),
                        "title": it.get("title"),
                        "web_url": it.get("web_url"),
                    }
                )
    except Exception:
        pass
    if ctx.attempt_dir:
        append_undo(ctx.attempt_dir, {"op": "noop", "reason": "read_only"})
    return {"ok": True, "items": items}


BUGZILLA_SCHEMA = {
    "name": "search_bugzilla",
    "description": "Search KDE Bugzilla",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "product": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["query"],
    },
}

INVENT_SCHEMA = {
    "name": "search_invent",
    "description": "Search invent.kde.org issues",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "project": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["query"],
    },
}
