from __future__ import annotations


class RpcError(Exception):
    def __init__(self, code: str, message: str, data: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data or {}

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "data": self.data}


PROTOCOL = "PROTOCOL"
UNAUTHORIZED = "UNAUTHORIZED"
NOT_FOUND = "NOT_FOUND"
BUSY = "BUSY"
PAUSED = "PAUSED"
DISABLED = "DISABLED"
VALIDATION = "VALIDATION"
TOOL_DENIED = "TOOL_DENIED"
PRIVILEGE_CANCELLED = "PRIVILEGE_CANCELLED"
PRIVILEGE_TIMEOUT = "PRIVILEGE_TIMEOUT"
LLM_ERROR = "LLM_ERROR"
TIMEOUT = "TIMEOUT"
NETWORK = "NETWORK"
OVERFLOW = "OVERFLOW"
IRREVERSIBLE = "IRREVERSIBLE"
FS = "FS"
INTERNAL = "INTERNAL"
