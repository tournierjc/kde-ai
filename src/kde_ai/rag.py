from __future__ import annotations

import glob
import os
import sqlite3
import subprocess
from pathlib import Path

from kde_ai.paths import docs_db
from kde_ai.undo import append_undo


def connect() -> sqlite3.Connection:
    docs_db().parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(docs_db()))
    conn.execute(
        """CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(
        title, body, path, section, tokenize='porter'
    )"""
    )
    conn.execute("CREATE TABLE IF NOT EXISTS meta (path TEXT PRIMARY KEY, mtime REAL)")
    return conn


def _index_file(conn: sqlite3.Connection, path: Path, title: str, section: str, body: str) -> None:
    mtime = path.stat().st_mtime
    row = conn.execute("SELECT mtime FROM meta WHERE path=?", (str(path),)).fetchone()
    if row and row[0] == mtime:
        return
    conn.execute("DELETE FROM docs WHERE path=?", (str(path),))
    conn.execute(
        "INSERT INTO docs(title, body, path, section) VALUES (?,?,?,?)",
        (title, body[:200_000], str(path), section),
    )
    conn.execute("INSERT OR REPLACE INTO meta(path, mtime) VALUES (?,?)", (str(path), mtime))


def reindex(cfg, force: bool = False) -> int:
    conn = connect()
    if force:
        conn.execute("DELETE FROM docs")
        conn.execute("DELETE FROM meta")
    n = 0
    sections = cfg.get("rag.man_sections") or ["1", "5", "7", "8"]
    try:
        proc = subprocess.run(["man", "-k", "."], capture_output=True, text=True, timeout=60)
        for line in (proc.stdout or "").splitlines()[:5000]:
            if "(" not in line:
                continue
            name = line.split("(", 1)[0].strip()
            sec = line.split("(", 1)[1].split(")", 1)[0]
            if sec not in sections:
                continue
            page = subprocess.run(
                ["man", sec, name],
                capture_output=True,
                text=True,
                timeout=10,
                env={**os.environ, "MANPAGER": "cat", "PAGER": "cat"},
            )
            text = page.stdout or ""
            if not text:
                continue
            fake = Path(f"/usr/share/man/man{sec}/{name}.{sec}")
            _index_file(conn, fake if fake.exists() else Path(f"man:{sec}:{name}"), name, sec, text)
            n += 1
    except Exception:
        pass
    for g in cfg.get("rag.doc_globs") or []:
        for path_s in glob.glob(g):
            p = Path(path_s)
            if p.is_dir():
                files = list(p.rglob("*"))
            else:
                files = [p]
            for f in files:
                if not f.is_file() or f.stat().st_size > 2 * 1024 * 1024:
                    continue
                try:
                    body = f.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                _index_file(conn, f, f.name, "doc", body)
                n += 1
    conn.commit()
    conn.close()
    return n


def search(query: str, k: int = 5) -> dict:
    conn = connect()
    count = conn.execute("SELECT count(*) FROM docs").fetchone()[0]
    if count == 0:
        conn.close()
        return {"ok": True, "hits": [], "needs_reindex": True}
    q = query.replace('"', " ")
    rows = conn.execute(
        "SELECT title, path, section, snippet(docs, 1, '[', ']', '…', 12) FROM docs WHERE docs MATCH ? LIMIT ?",
        (q, k),
    ).fetchall()
    conn.close()
    hits = [
        {"title": r[0], "path": r[1], "section": r[2], "snippet": r[3]} for r in rows
    ]
    return {"ok": True, "hits": hits, "needs_reindex": False}


def handle(args: dict, ctx) -> dict:
    q = args.get("query") or ""
    k = int(args.get("k") or ctx.cfg.get("rag.k", 5))
    if ctx.attempt_dir:
        append_undo(ctx.attempt_dir, {"op": "noop", "reason": "read_only"})
    return search(q, k)


SCHEMA = {
    "name": "search_docs",
    "description": "Search local manpages and indexed KDE/CachyOS docs",
    "parameters": {
        "type": "object",
        "properties": {"query": {"type": "string"}, "k": {"type": "integer"}},
        "required": ["query"],
    },
}
