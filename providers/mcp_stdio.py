"""Minimaler MCP-Client (stdio) für die Provider-Registry.

Kein Framework nötig: JSON-RPC 2.0 über stdin/stdout, Protokollversion 2024-11-05.
"""
from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from typing import Any


class MCPError(RuntimeError):
    pass


class MCPStdioClient:
    def __init__(self, command: list[str], name: str = "provider", env: dict | None = None,
                 timeout: float = 180.0) -> None:
        self.command = command
        self.name = name
        self.timeout = timeout
        self._id = 0
        self._q: queue.Queue = queue.Queue()
        self._p = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1, env=env,
        )
        threading.Thread(target=self._reader, daemon=True).start()
        self.request("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": name, "version": "1"},
        })
        self.notify("notifications/initialized")

    # -- plumbing ---------------------------------------------------------
    def _reader(self) -> None:
        for line in self._p.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                self._q.put(json.loads(line))
            except Exception:
                continue

    def _send(self, payload: dict) -> None:
        if self._p.poll() is not None:
            raise MCPError(f"{self.name}: MCP-Prozess beendet (exit {self._p.returncode})")
        try:
            self._p.stdin.write(json.dumps(payload) + "\n")
            self._p.stdin.flush()
        except Exception as exc:  # pragma: no cover
            raise MCPError(f"{self.name}: Schreiben fehlgeschlagen: {exc}") from exc

    def notify(self, method: str, params: dict | None = None) -> None:
        msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self._send(msg)

    def request(self, method: str, params: dict | None = None, timeout: float | None = None) -> dict:
        self._id += 1
        rid = self._id
        msg: dict[str, Any] = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            msg["params"] = params
        self._send(msg)
        deadline = time.time() + (timeout or self.timeout)
        while time.time() < deadline:
            try:
                data = self._q.get(timeout=max(0.1, deadline - time.time()))
            except queue.Empty:
                break
            if data.get("id") == rid:
                if "error" in data:
                    raise MCPError(f"{self.name}: {data['error']}")
                return data.get("result", {})
        raise MCPError(f"{self.name}: Timeout bei {method} ({timeout or self.timeout}s)")

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
        try:
            self._p.stdin.close()
        except Exception:
            pass
        try:
            self._p.terminate()
        except Exception:
            pass


def _maybe_json(text: str) -> Any:
    """MCP-Antworten sind oft JSON im Text; dann parsen, sonst Rohtext."""
    if not text:
        return None
    stripped = text.strip()
    if stripped[:1] in "{[":
        try:
            return json.loads(stripped)
        except Exception:
            return stripped
    return stripped
