#!/usr/bin/env python3
"""Minimaler MCP-Testclient (stdio + Streamable-HTTP), JSON-RPC 2.0.

Nutzung:
    python3 mcpcall.py <url> <tool> '<json-args>' [--out datei.json]
    python3 mcpcall.py --stdio '<cmd json-array>' <tool> '<json-args>' [--out datei.json]
"""
from __future__ import annotations

import json
import subprocess
import sys

import requests


def http_call(url: str, tool: str, args: dict, timeout: float = 120.0,
              headers: dict | None = None) -> dict:
    base = {"Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"}
    if headers:
        base.update(headers)
    session = requests.Session()

    def post(payload: dict, t: float = timeout):
        resp = session.post(url, headers=base, data=json.dumps(payload), timeout=t)
        return resp

    def body(resp) -> str:
        # SSE kommt als text/event-stream -> requests rät ISO-8859-1 -> UTF-8 erzwingen
        return resp.content.decode("utf-8", errors="replace")

    r = post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                         "clientInfo": {"name": "ferry-research", "version": "1"}}})
    sid = r.headers.get("Mcp-Session-Id")
    if sid:
        base["Mcp-Session-Id"] = sid
    try:
        session.post(url, headers=base,
                     data=json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
                     timeout=30)
    except Exception:
        pass

    def rpc(method: str, params: dict, rid: int):
        resp = post({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        return resp, parse(body(resp))

    _, res_tools = rpc("tools/list", {}, 2)
    tools = (res_tools or {}).get("result", {}).get("tools", [])
    _, res_call = rpc("tools/call", {"name": tool, "arguments": args}, 3)
    return {"http_status": r.status_code, "session_id": sid,
            "tools": [t.get("name") for t in tools],
            "tool_schemas": tools, "call": res_call,
            "raw_call_text": (res_call.get("result", {}).get("content", [{}])[0].get("text", "")
                              if isinstance(res_call, dict) else "")}


def parse(text: str):
    text = (text or "").strip()
    if "data:" in text:
        # SSE: alle data:-Zeilen eines Events verketten
        chunks: list[str] = []
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("data:"):
                chunks.append(s[5:].strip())
            elif s == "" and chunks:
                joined = "\n".join(chunks)
                try:
                    return json.loads(joined)
                except Exception:
                    chunks = []
        if chunks:
            joined = "\n".join(chunks)
            try:
                return json.loads(joined)
            except Exception:
                return {"__raw__": text[:4000]}
        return {"__raw__": text[:2000]}
    try:
        return json.loads(text)
    except Exception:
        return {"__raw__": text[:2000]}


def stdio_call(cmd: list[str], tool: str, args: dict, timeout: float = 120.0) -> dict:
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, bufsize=1)

    def send(msg: dict):
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()

    def recv() -> dict:
        line = proc.stdout.readline()
        if not line:
            return {"__error__": "no response", "stderr": proc.stderr.read()[:2000]}
        try:
            return json.loads(line)
        except Exception:
            return {"__raw__": line[:2000]}

    send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
          "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                     "clientInfo": {"name": "ferry-research", "version": "1"}}})
    init = recv()
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tools = recv()
    send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
          "params": {"name": tool, "arguments": args}})
    call = recv()
    try:
        proc.stdin.close()
        proc.terminate()
    except Exception:
        pass
    return {"init": init, "tools": tools, "call": call}


def main() -> None:
    argv = sys.argv[1:]
    out = None
    if "--out" in argv:
        i = argv.index("--out")
        out = argv[i + 1]
        del argv[i:i + 2]
    if argv and argv[0] == "--stdio":
        cmd = json.loads(argv[1])
        tool = argv[2]
        args = json.loads(argv[3]) if len(argv) > 3 else {}
        res = stdio_call(cmd, tool, args)
    else:
        url = argv[0]
        tool = argv[1]
        args = json.loads(argv[2]) if len(argv) > 2 else {}
        res = http_call(url, tool, args)
    text = json.dumps(res, indent=2, ensure_ascii=False)
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(text[:12000])


if __name__ == "__main__":
    main()
