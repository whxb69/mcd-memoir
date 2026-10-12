#!/usr/bin/env python3
"""Minimal McDonald's MCP client (streamable HTTP, JSON-RPC)."""
import json, subprocess, time

BASE = "https://mcp.mcd.cn"

class McdClient:
    def __init__(self, token: str, base: str = BASE, timeout: int = 90):
        self.base = base
        self.timeout = timeout
        self.hdr = ["-H", f"Authorization: Bearer {token}",
                    "-H", "Content-Type: application/json",
                    "-H", "Accept: application/json, text/event-stream"]
        self._id = 0
        self._init_done = False

    def _raw(self, payload: dict):
        cmd = ["curl", "-s", "-m", str(self.timeout), self.base] + self.hdr + \
              ["-d", json.dumps(payload, ensure_ascii=False)]
        out = subprocess.run(cmd, capture_output=True, text=True).stdout
        for line in out.splitlines():
            if line.startswith("data:"):
                try:
                    return json.loads(line[5:].strip())
                except Exception:
                    pass
        try:
            return json.loads(out)
        except Exception:
            return {}

    def init(self):
        self._raw({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "mcd-memoir", "version": "0.1.0"}}})
        self._raw({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self._init_done = True

    def call(self, name: str, args: dict | None = None, retry: int = 2) -> dict:
        if not self._init_done:
            self.init()
        payload = {"jsonrpc": "2.0", "id": self._id + 1, "method": "tools/call",
                   "params": {"name": name, "arguments": args or {}}}
        r = {}
        for attempt in range(retry + 1):
            self._id += 1
            payload["id"] = self._id
            r = self._raw(payload)
            if r.get("result") is not None or r.get("error"):
                break
            time.sleep(0.8)
        res = r.get("result", {})
        if res.get("isError"):
            return {"_error": json.dumps(res, ensure_ascii=False)[:300]}
        texts = [c.get("text", "") for c in res.get("content", []) if c.get("type") == "text"]
        return unwrap("\n".join(texts))

    def list_tools(self) -> list:
        if not self._init_done:
            self.init()
        r = self._raw({"jsonrpc": "2.0", "id": self._id + 1, "method": "tools/list"})
        return r.get("result", {}).get("tools", [])


def unwrap(raw: str):
    """MCP text content sometimes wraps the real JSON after '## Original Response'.
    There may be natural-language lines between the marker and the JSON brace,
    so scan forward from the marker and use a streaming JSON decoder."""
    import json as _json, re as _re
    idx = raw.find("## Original Response")
    start = raw.find("{", idx) if idx >= 0 else raw.find("{")
    while start >= 0:
        try:
            obj, _end = _json.JSONDecoder().raw_decode(raw[start:])
            return obj
        except Exception:
            start = raw.find("{", start + 1)
    try:
        return _json.loads(raw)
    except Exception:
        return raw
