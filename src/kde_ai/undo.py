from __future__ import annotations

import json
import shutil
from pathlib import Path

from kde_ai.errors import FS, IRREVERSIBLE, RpcError
from kde_ai.logutil import log


def append_undo(attempt_dir: Path, op: dict) -> None:
    path = attempt_dir / "undo.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(op, ensure_ascii=False) + "\n")


def load_undo(attempt_dir: Path) -> list[dict]:
    path = attempt_dir / "undo.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def replay_undo(attempt_dir: Path) -> None:
    ops = list(reversed(load_undo(attempt_dir)))
    for op in ops:
        kind = op.get("op")
        try:
            if kind == "restore_file":
                blob = Path(op["blob"])
                dest = Path(op["path"])
                if blob.exists():
                    shutil.copy2(blob, dest)
            elif kind == "kwriteconfig":
                from kde_ai.tools.plasma_script import restore_kwriteconfig

                restore_kwriteconfig(op)
            elif kind == "pacman":
                from kde_ai.tools.pacman_mutate import undo_pacman

                undo_pacman(op)
            elif kind in ("noop", "irreversible"):
                if kind == "irreversible" and not op.get("user_acked"):
                    raise RpcError(IRREVERSIBLE, op.get("reason", "irreversible"))
            elif kind == "delete_file":
                Path(op["path"]).unlink(missing_ok=True)
        except RpcError:
            raise
        except Exception as exc:
            log.warning("undo failed: %s", exc)
            raise RpcError(FS, f"undo failed: {exc}")
