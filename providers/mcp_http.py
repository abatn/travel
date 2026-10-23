"""MCP-Client für Streamable-HTTP-Server (z. B. https://mcp.<anbieter>/mcp).

Der Server kann Antworten als JSON oder als SSE-Stream ("data: {...}") liefern –
beides wird hier verarbeitet. Die Session-ID wird aus dem Initialize-Header übernommen.
"""
from __future__ import annotations

import json
import time
from typing import Any

import requests


class MCPHttpError(RuntimeError):
    pass


class MCPHttpClient:
    def __init__(self, url: str, name: str = "provider", timeout: float = 180.0,
                 headers: dict | None = None) -> None:
        self.url = url
        self.name = name
        self.timeout = timeout
        self.session_id: str | None = None
        self._base_headers = {"Content-Type": "application/json",
                              "Accept": "application/json, text/event-stream"}
        if headers:
            self._base_headers.update(headers)
        self._n = 0
        self.request("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": name, "version": "1"},
        })

    # -- plumbing ---------------------------------------------------------
    def _post(self, payload: dict, timeout: float | None = None) -> tuple[Any, requests.Response]:
        headers = dict(self._base_headers)
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        resp = requests.post(self.url, headers=headers, data=json.dumps(payload),
                             timeout=timeout or self.timeout)
        sid = resp.headers.get("Mcp-Session-Id")
        if sid:
            self.session_id = sid
        if resp.status_code >= 400:
            raise MCPHttpError(f"{self.name}: HTTP {resp.status_code} "
                               f"({resp.text[:160].strip()})")
        return _parse_body(resp.text), resp

    def notify(self, method: str, params: dict | None = None) -> None:
        msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        try:
            self._post(msg, timeout=min(self.timeout, 30))
        except Exception:
            pass  # Notifications dürfen scheitern (Server schließt 202/204)

    def request(self, method: str, params: dict | None = None, timeout: float | None = None) -> Any:
        self._n += 1
        msg: dict[str, Any] = {"jsonrpc": "2.0", "id": self._n, "method": method}
        if params is not None:
            msg["params"] = params
        data, _ = self._post(msg, timeout=timeout)
        if not isinstance(data, dict):
            raise MCPHttpError(f"{self.name}: unerwartete Antwort ({type(data).__name__}): "
                               f"{str(data)[:200]}")
        if "error" in data:
            raise MCPHttpError(f"{self.name}: {data['error']}")
        return data.get("result", {})

    # -- public API -------------------------------------------------------
    def call_tool(self, tool: str, arguments: dict, timeout: float | None = None) -> Any:
        res = self.request("tools/call", {"name": tool, "arguments": arguments}, timeout=timeout)
        texts = [c.get("text", "") for c in res.get("content", []) if c.get("type") == "text"]
        out = "\n".join(texts)
        if res.get("isError"):
            raise RuntimeError(f"{self.name}: Werkzeugfehler: {out.strip()[:300]}")
        structured = res.get("structuredContent")
        if structured:
            # Rohtext mitgeben: manche Server antworten als Markdown-Tabelle im Textfeld
            if isinstance(structured, dict):
                structured = dict(structured)
                structured["__raw_text__"] = out
            return structured
        parsed = _maybe_json(out)
        if isinstance(parsed, dict):
            parsed["__raw_text__"] = out
        return parsed

    def list_tools(self) -> list[dict]:
        res = self.request("tools/list", {})
        if isinstance(res, dict):
            return res.get("tools", []) or []
        return []

    def close(self) -> None:
        return None


def _parse_body(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        return None
    if "data:" in text:
        chunks = [ln[5:].strip() for ln in text.splitlines() if ln.strip().startswith("data:")]
        for chunk in reversed(chunks):
            try:
                return json.loads(chunk)
            except Exception:
                continue
        return text
    try:
        return json.loads(text)
    except Exception:
        return text


def _maybe_json(text: str) -> Any:
    if not text:
        return None
    s = text.strip()
    if s[:1] in "{[":
        try:
            return json.loads(s)
        except Exception:
            return s
    return s
