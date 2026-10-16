#!/usr/bin/env python3
"""Local test rig for the built-in API backend: a tiny website (port SITE) and a scripted
fake OpenAI-compatible endpoint (port LLM) whose "model" is a rule-based agent that calls tools.
    python3 mock_api.py 8801 8802
"""
import json, re, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

SITE, LLM = int(sys.argv[1]), int(sys.argv[2])
N_ITEMS = 6


class Site(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        if self.path == "/robots.txt":
            self.send_response(404); self.end_headers(); return
        if self.path == "/index.html":
            body = "<html><title>Index</title><body><p>6 results</p>" + "".join(f'<a href="/item/{i}.html">Item {i}</a><br>' for i in range(N_ITEMS)) + "</body></html>"
        elif self.path.startswith("/item/9"):
            self.send_response(403); self.end_headers(); return
        elif self.path.startswith("/item/"):
            i = re.findall(r"\d+", self.path)[0]
            body = f"<html><title>Item {i}</title><body><h1>Item {i}</h1><p>Details about item {i}</p><script>var x=1</script></body></html>"
        else:
            self.send_response(404); self.end_headers(); return
        self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers(); self.wfile.write(body.encode())


def tc(i, name, args):
    return {"id": f"c{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


class Llm(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        msgs = req["messages"]
        prompt = msgs[1]["content"]
        discovery = "Mode: DISCOVERY" in prompt
        tool_msgs = [m for m in msgs if m["role"] == "tool"]
        asst = [m for m in msgs if m["role"] == "assistant"]
        last = msgs[-1]
        msg = {"role": "assistant", "content": None}
        if not asst:
            msg["tool_calls"] = [tc(0, "fetch", {"url": f"http://127.0.0.1:{SITE}/index.html"})] if discovery else [tc(0, "ledger_claim", {"n": 10})]
        elif discovery and len(asst) == 1:
            res = json.loads(last["content"])
            calls = [tc(i, "ledger_add", {"key": l["url"]}) for i, l in enumerate(res["links"])]
            calls += [tc(90, "ledger_set_expected", {"n": N_ITEMS}), tc(91, "ledger_discovery_complete", {})]
            msg["tool_calls"] = calls
        elif not discovery and len(asst) == 1:
            items = json.loads(last["content"])["items"]
            msg["tool_calls"] = [tc(i, "fetch", {"url": it["key"]}) for i, it in enumerate(items)]
        elif not discovery and len(asst) == 2:
            calls, fetch_calls = [], asst[-1]["tool_calls"]
            for c in fetch_calls:
                url = json.loads(c["function"]["arguments"])["url"]
                res = json.loads(next(m["content"] for m in tool_msgs if m["tool_call_id"] == c["id"]))
                if res.get("blocked"):
                    calls.append(tc(len(calls), "ledger_blocked", {"key": url, "reason": res["error"]}))
                else:
                    calls.append(tc(len(calls), "ledger_done", {"key": url, "result": {"title": res["title"], "url": url}, "evidence": res["evidence"]}))
            msg["tool_calls"] = calls
        else:
            msg["content"] = "batch done"
        for i, c in enumerate(msg.get("tool_calls", [])):
            c["id"] = f"s{len(asst)}c{i}"  # unique across the conversation
        out = {"choices": [{"message": msg}], "usage": {"prompt_tokens": 1000, "completion_tokens": 100}}
        body = json.dumps(out).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)


for port, h in ((SITE, Site), (LLM, Llm)):
    Thread(target=ThreadingHTTPServer(("127.0.0.1", port), h).serve_forever, daemon=True).start()
print("ready", flush=True)
import time
while True:
    time.sleep(3600)
