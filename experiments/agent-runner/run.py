#!/usr/bin/env python3
"""Unattended long-job runner for AI agents.

One loop, many backends (claude / codex / opencode CLI, any custom command, or a built-in
OpenAI-compatible API tool loop). The runner - not the model - decides when the job is done,
enforces the limits, and always leaves a log + summary behind, whether the run succeeds,
hits a limit, crashes, or is killed by SIGTERM.

    python3 run.py --config config.toml            # normal / cron
    python3 run.py --config config.toml --dry-run  # print prompt + command, run nothing

Exit codes: 0 completed | 1 internal/fatal error | 2 stopped by a limit | 3 stalled
            4 too many consecutive failures | 75 another run holds the lock | 130 interrupted
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import http.client
import json
import logging
import math
import os
import signal
import subprocess
import sys
import time
import tempfile
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ledger import Ledger, LedgerError  # noqa: E402

EXIT_OK, EXIT_ERROR, EXIT_LIMIT, EXIT_STALLED, EXIT_FAILURES, EXIT_LOCKED, EXIT_INTERRUPTED = 0, 1, 2, 3, 4, 75, 130
HERE = Path(__file__).resolve().parent


class Interrupted(BaseException):
    """SIGTERM / SIGINT. BaseException so no `except Exception` swallows it."""


class FatalError(Exception):
    """Misconfiguration that retrying cannot fix (e.g. CLI not installed)."""


# ----------------------------------------------------------------------------- logging
class RunLog:
    def __init__(self, run_dir: Path):
        run_dir.mkdir(parents=True, exist_ok=True)
        self.dir = run_dir
        self.logger = logging.getLogger("runner")
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
        for h in (logging.FileHandler(run_dir / "run.log", encoding="utf-8"), logging.StreamHandler(sys.stderr)):
            h.setFormatter(fmt)
            self.logger.addHandler(h)
        self.events = open(run_dir / "events.jsonl", "a", buffering=1, encoding="utf-8")

    def info(self, msg, *a):
        self.logger.info(msg, *a)

    def warn(self, msg, *a):
        self.logger.warning(msg, *a)

    def event(self, type_, **data):
        rec = {"ts": dt.datetime.now().isoformat(timespec="seconds"), "type": type_, **data}
        self.events.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


# ----------------------------------------------------------------------------- budget
@dataclass
class Usage:
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_create: int = 0
    cost_usd: float | None = None
    estimated: bool = False

    def tokens(self, count_cache_read=False):
        return self.input + self.output + self.cache_create + (self.cache_read if count_cache_read else 0)


class Budget:
    def __init__(self, lim: dict, count_cache_read: bool):
        self.lim = lim
        self.count_cache_read = count_cache_read
        self.t0 = time.monotonic()
        self.u = Usage(cost_usd=0.0)
        self.iterations = 0
        self.cost_unknown = False

    @property
    def tokens(self):
        return self.u.tokens(self.count_cache_read)

    @property
    def elapsed(self):
        return time.monotonic() - self.t0

    def add(self, u: Usage):
        self.u.input += u.input
        self.u.output += u.output
        self.u.cache_read += u.cache_read
        self.u.cache_create += u.cache_create
        self.u.estimated |= u.estimated
        if u.cost_usd is None:
            self.cost_unknown = True
        else:
            self.u.cost_usd += u.cost_usd

    def reason(self, extra: Usage | None = None):
        L = self.lim
        x_tok = extra.tokens(self.count_cache_read) if extra else 0
        x_cost = (extra.cost_usd or 0.0) if extra else 0.0
        if L.get("max_wall_seconds") and self.elapsed >= L["max_wall_seconds"]:
            return "max_wall_seconds"
        if L.get("max_iterations") and self.iterations >= L["max_iterations"]:
            return "max_iterations"
        if L.get("max_total_tokens") and self.tokens + x_tok >= L["max_total_tokens"]:
            return "max_total_tokens"
        if L.get("max_cost_usd") and (self.u.cost_usd or 0.0) + x_cost >= L["max_cost_usd"]:
            return "max_cost_usd"
        return None

    def remaining_cost(self):
        if not self.lim.get("max_cost_usd"):
            return None
        return max(0.0, self.lim["max_cost_usd"] - (self.u.cost_usd or 0.0))

    def remaining_seconds(self):
        if not self.lim.get("max_wall_seconds"):
            return None
        return max(0.0, self.lim["max_wall_seconds"] - self.elapsed)


def price_cost(u: Usage, pricing: dict):
    pin, pout = pricing.get("input_per_mtok"), pricing.get("output_per_mtok")
    if pin is None or pout is None:
        return None
    return (u.input * pin + u.output * pout) / 1e6


# ----------------------------------------------------------------------------- prompt
RULES_COMMON = """You are one batch of a long unattended job. No human will answer questions, so never ask for
confirmation or clarification: pick the most reasonable reading, note the assumption in the item's result, and continue.

Hard rules
- ONLY the ledger records progress. If it is not in the ledger it did not happen.
- Never mark an item done unless you actually opened its page in THIS batch and the result contains every required field: {required}.
- Save the raw page you based the result on under ./evidence/ and pass it as evidence.
- Login wall, CAPTCHA, 401/403/429, robots.txt disallow -> mark the item `blocked` with the reason. Do NOT try to bypass.
- The page genuinely has no such data -> `not-found`. Temporary error (timeout, 5xx) -> `fail` (it will be retried).
- Stay inside these domains: {domains}. Do not visit anything else.
- Do at most {batch} items in this batch, then stop and reply with ONE line summarising what you did.
"""

LEDGER_CLI = """Ledger (use only this; run from the current directory):
  python3 {ledger} claim N                          -> JSON of up to N pending items (marks them in_progress)
  python3 {ledger} done KEY --result '{{"field":"v",...}}' --evidence evidence/FILE   (or --result @file.json)
  python3 {ledger} fail KEY --error "why"
  python3 {ledger} blocked KEY --reason "why"
  python3 {ledger} not-found KEY --reason "why"
  python3 {ledger} add KEY [--payload JSON]         -> register a newly discovered item
  python3 {ledger} meta-set discovery_cursor VALUE  -> remember where enumeration stopped (read via stats)
  python3 {ledger} set-expected N                   -> the total the site itself reports, if it shows one
  python3 {ledger} discovery-complete               -> ONLY when enumeration is exhaustive
  python3 {ledger} stats
"""

LEDGER_TOOLS = """Ledger tools: ledger_claim, ledger_done, ledger_fail, ledger_blocked, ledger_not_found, ledger_add,
ledger_meta_set(key,value) (e.g. discovery_cursor), ledger_set_expected, ledger_discovery_complete, ledger_stats.
Fetch pages ONLY with the `fetch` tool (it saves evidence and returns the evidence path)."""

MODE_DISCOVERY = """Mode: DISCOVERY. The list of items is not complete yet.
Continue enumerating from the cursor in meta (discovery_cursor), register every item with `add`, and keep the cursor updated.
Call discovery-complete ONLY when you reached the true end (last page, no "next", counts agree with any total the site shows;
record that total with set-expected). If unsure, do NOT call it - the next batch will continue.
If discovery needs more than this batch, just stop after updating the cursor.
"""

MODE_PROCESS = """Mode: PROCESSING. Enumeration is complete. Claim up to {batch} items, handle each one, record every outcome."""


def build_prompt(task_text, stats, cfg, interface, ledger_path, feedback):
    run, led = cfg.get("run", {}), cfg.get("ledger", {})
    batch = run.get("batch_size", 10)
    domains = ", ".join(run.get("allowed_domains", [])) or "(see task spec)"
    parts = [
        RULES_COMMON.format(required=", ".join(led.get("required_fields", [])) or "(see task spec)", domains=domains, batch=batch),
        LEDGER_CLI.format(ledger=ledger_path) if interface == "cli" else LEDGER_TOOLS,
        "Current ledger state: " + json.dumps({k: stats[k] for k in ("total", "counts", "discovery_complete", "expected_total", "meta")}, ensure_ascii=False),
        (MODE_PROCESS.format(batch=batch) if stats["discovery_complete"] else MODE_DISCOVERY),
    ]
    if feedback:
        parts.append("The completion check just FAILED with this output - fix the cause in this batch:\n" + feedback[-3000:])
    parts.append("=== TASK SPECIFICATION ===\n" + task_text)
    return "\n\n".join(parts)


# ----------------------------------------------------------------------------- subprocess helpers
def kill_group(proc: subprocess.Popen):
    for sig, wait in ((signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        if proc.poll() is not None:
            return
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=wait)
        except subprocess.TimeoutExpired:
            pass


def run_subprocess(argv, stdin_path, cwd, env, timeout, out_path, err_path):
    """Returns (returncode | None, timed_out). Kills the whole process group on timeout/interrupt."""
    stdin = open(stdin_path, "rb") if stdin_path else subprocess.DEVNULL
    try:
        with open(out_path, "wb") as fo, open(err_path, "wb") as fe:
            try:
                proc = subprocess.Popen(argv, stdin=stdin, stdout=fo, stderr=fe, cwd=cwd, env=env, start_new_session=True)
            except FileNotFoundError:
                raise FatalError(f"command not found: {argv[0]}")
            try:
                return proc.wait(timeout=timeout), False
            except subprocess.TimeoutExpired:
                kill_group(proc)
                return None, True
            finally:
                if proc.poll() is None:
                    kill_group(proc)
    finally:
        if stdin_path:
            stdin.close()


# ----------------------------------------------------------------------------- output parsers
def load_json_loose(text):
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except Exception:
                continue
    return None


def parse_claude(out):
    obj = load_json_loose(out)
    if not isinstance(obj, dict):
        return None
    u = obj.get("usage") or {}
    usage = Usage(
        input=u.get("input_tokens", 0) or 0,
        output=u.get("output_tokens", 0) or 0,
        cache_read=u.get("cache_read_input_tokens", 0) or 0,
        cache_create=u.get("cache_creation_input_tokens", 0) or 0,
        cost_usd=obj.get("total_cost_usd"),
    )
    sub = str(obj.get("subtype", ""))
    note = sub if sub.startswith("error") else ""
    # hitting the per-iteration turn/budget cap is a normal stop, not a failure (the stall check catches no-progress)
    err = bool(obj.get("is_error")) and sub not in ("error_max_turns", "error_max_budget_usd")
    return usage, err, (str(obj.get("result", ""))[:500] or note), note


def _walk_usage(obj, acc):
    if isinstance(obj, dict):
        keys = obj.keys()
        if {"input_tokens", "output_tokens"} & keys or {"prompt_tokens", "completion_tokens"} & keys:
            acc.append(obj)
            return
        for v in obj.values():
            _walk_usage(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _walk_usage(v, acc)


def parse_jsonl(out):
    """codex --json: sum usage from turn.completed events; otherwise any usage-looking dict."""
    events = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except Exception:
                pass
    if not events:
        return None
    turns = [e["usage"] for e in events if e.get("type") == "turn.completed" and isinstance(e.get("usage"), dict)]
    acc = turns or []
    if not acc:
        _walk_usage(events, acc)
    if not acc:
        return None
    usage = Usage()
    for d in acc:
        usage.input += d.get("input_tokens", d.get("prompt_tokens", 0)) or 0
        usage.output += d.get("output_tokens", d.get("completion_tokens", 0)) or 0
    failed = any(e.get("type") == "turn.failed" for e in events)
    return usage, failed, "", ""


def estimate_usage(prompt, out):
    return Usage(input=len(prompt) // 3, output=len(out) // 3, estimated=True)


# ----------------------------------------------------------------------------- iteration result
@dataclass
class IterResult:
    ok: bool
    usage: Usage
    error: str | None = None
    summary: str = ""
    exit_code: int | None = None
    timed_out: bool = False
    note: str = ""


# ----------------------------------------------------------------------------- CLI backends
class CliBackend:
    interface = "cli"

    def __init__(self, name, cfg, log):
        self.name, self.cfg, self.log = name, cfg, log
        self.bcfg = cfg.get(name, {})
        self.pricing = cfg.get("pricing", {})
        self.reports_cost = name == "claude" or bool(self.pricing)

    def build_argv(self, prompt, prompt_file, ctx):
        b = self.bcfg
        model = b.get("model")
        extra = list(b.get("extra_args", []))
        if b.get("cmd"):  # user-supplied template wins
            subs = {"prompt": prompt, "prompt_file": str(prompt_file), "max_turns": str(b.get("max_turns", 40)),
                    "iter_budget_usd": f"{ctx['iter_budget_usd']:.4f}" if ctx["iter_budget_usd"] is not None else "",
                    "model": model or ""}
            argv = [str(x).format_map(_Safe(subs)) for x in b["cmd"]]
            return argv, (prompt_file if b.get("prompt_via") == "stdin" else None)
        if self.name == "claude":
            argv = ["claude", "-p", "--output-format", "json", "--max-turns", str(b.get("max_turns", 40))]
            if ctx["iter_budget_usd"] is not None:
                argv += ["--max-budget-usd", f"{ctx['iter_budget_usd']:.4f}"]
            if model:
                argv += ["--model", model]
            tools = b.get("allowed_tools")
            if tools is None:
                tools = ["Read", "Write", "Edit", "WebFetch", "WebSearch", f"Bash(python3 {ctx['ledger_path']} *)"]
            if tools:
                argv += ["--allowedTools", ",".join(tools)]
            return argv + extra, prompt_file  # prompt on stdin (--allowedTools is variadic; keep prompt out of argv)
        if self.name == "codex":
            argv = ["codex", "exec", "--json", "--full-auto", "--skip-git-repo-check"]
            if model:
                argv += ["--model", model]
            return argv + extra + [prompt], None
        if self.name == "opencode":
            argv = ["opencode", "run", "--format", "json"]
            if model:
                argv += ["--model", model]
            return argv + extra + [prompt], None
        raise FatalError(f"backend {self.name!r} needs [{self.name}].cmd in the config")

    def run(self, prompt, iter_dir: Path, ctx, budget: Budget):
        n = ctx["n"]
        prompt_file = iter_dir / f"iter-{n:03d}.prompt.md"
        prompt_file.write_text(prompt, encoding="utf-8")
        argv, stdin_path = self.build_argv(prompt, prompt_file, ctx)
        shown = [a if len(a) < 200 else a[:200] + "...<trimmed>" for a in argv]
        self.log.event("exec", argv=shown, stdin=bool(stdin_path))
        out_p, err_p = iter_dir / f"iter-{n:03d}.stdout", iter_dir / f"iter-{n:03d}.stderr"
        rc, timed_out = run_subprocess(argv, stdin_path, ctx["cwd"], ctx["env"], ctx["timeout"], out_p, err_p)
        out = out_p.read_text(encoding="utf-8", errors="replace")
        err = err_p.read_text(encoding="utf-8", errors="replace")
        parsed = parse_claude(out) if self.name == "claude" else (parse_jsonl(out) if self.name in ("codex", "opencode") else None)
        if parsed is None:
            usage, is_err, summary, note = estimate_usage(prompt, out), False, out.strip()[-300:], ""
        else:
            usage, is_err, summary, note = parsed
        if usage.cost_usd is None:
            usage.cost_usd = price_cost(usage, self.pricing)
        ok = (rc == 0) and not is_err and not timed_out
        error = None
        if timed_out:
            error = f"timeout after {ctx['timeout']:.0f}s"
        elif rc != 0:
            error = f"exit code {rc}: {err.strip()[-300:]}"
        elif is_err:
            error = "agent reported is_error"
        return IterResult(ok, usage, error, summary, rc, timed_out, note)


class _Safe(dict):
    def __missing__(self, k):
        return "{" + k + "}"


# ----------------------------------------------------------------------------- API backend (fetch + ledger tools)
class _Page(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "table", "ul", "ol", "dd", "dt"}

    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.parts, self.links, self.title = base, [], [], ""
        self._skip, self._href, self._atext, self._in_title = 0, None, [], False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag in self.BLOCK:
            self.parts.append("\n")
        if tag == "a":
            self._href, self._atext = dict(attrs).get("href"), []

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False
        if tag == "a" and self._href:
            self.links.append((urllib.parse.urljoin(self.base, self._href), "".join(self._atext).strip()[:80]))
            self._href = None
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, d):
        if self._in_title:
            self.title += d
        if self._skip:
            return
        self.parts.append(d)
        if self._href is not None:
            self._atext.append(d)


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, allow):
        self.allow = allow

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not self.allow(newurl):
            raise urllib.error.HTTPError(newurl, code, "redirect leaves allowed domains", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Fetcher:
    def __init__(self, cfg, evidence_dir: Path):
        a = cfg.get("api", {})
        self.domains = [d.lower() for d in cfg.get("run", {}).get("allowed_domains", [])]
        self.ua = a.get("user_agent", "agent-runner/1.0")
        self.delay = float(a.get("min_delay_seconds", 1.0))
        self.respect_robots = bool(a.get("respect_robots", True))
        self.max_bytes = int(a.get("max_bytes", 2_000_000))
        self.max_chars = int(a.get("max_tool_chars", 12_000))
        self.evidence_dir = evidence_dir
        self._last, self._robots = {}, {}
        self.opener = urllib.request.build_opener(_SafeRedirect(self.allowed))

    def allowed(self, url):
        host = (urllib.parse.urlparse(url).hostname or "").lower()
        return any(host == d or host.endswith("." + d) for d in self.domains)

    def _robots_ok(self, url):
        if not self.respect_robots:
            return True
        p = urllib.parse.urlparse(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                req = urllib.request.Request(origin + "/robots.txt", headers={"User-Agent": self.ua})
                with self.opener.open(req, timeout=15) as r:
                    rp.parse(r.read().decode("utf-8", "replace").splitlines())
            except urllib.error.HTTPError as e:
                rp = None if 400 <= e.code < 500 else False  # 4xx = no robots (allow); 5xx = be polite
            except Exception:
                rp = False
            self._robots[origin] = rp
        rp = self._robots[origin]
        if rp is None:
            return True
        if rp is False:
            return False
        return rp.can_fetch(self.ua, url)

    def fetch(self, url, timeout=30):
        if not self.allowed(url):
            return {"error": f"domain not allowed: {url}"}
        if not self._robots_ok(url):
            return {"error": "robots.txt disallows (or is unavailable) -> mark item blocked", "blocked": True}
        host = urllib.parse.urlparse(url).netloc
        wait = self._last.get(host, 0) + self.delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self.ua, "Accept": "text/html,application/xhtml+xml,application/json,text/plain,*/*;q=0.5"})
            with self.opener.open(req, timeout=timeout) as r:
                raw = r.read(self.max_bytes + 1)
                status, ctype, final = r.status, r.headers.get("Content-Type", ""), r.geturl()
        except urllib.error.HTTPError as e:
            blocked = e.code in (401, 403, 429)
            return {"status": e.code, "error": f"HTTP {e.code} {e.reason}" + (" -> mark item blocked, do not bypass" if blocked else ""), "blocked": blocked}
        except Exception as e:  # network / timeout: retryable
            return {"error": f"{type(e).__name__}: {e}", "retryable": True}
        finally:
            self._last[host] = time.monotonic()
        truncated = len(raw) > self.max_bytes
        raw = raw[: self.max_bytes]
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        ext = "json" if "json" in ctype else "html" if "html" in ctype else "txt"
        ev = self.evidence_dir / f"{hashlib.sha1(url.encode()).hexdigest()[:16]}.{ext}"
        ev.write_bytes(raw)
        text = raw.decode("utf-8", "replace")
        out = {"status": status, "url": final, "evidence": str(ev), "bytes": len(raw), "truncated_download": truncated}
        if "html" in ctype:
            p = _Page(final)
            p.feed(text)
            body = "\n".join(l.strip() for l in "".join(p.parts).splitlines() if l.strip())
            seen, links = set(), []
            for href, label in p.links:
                href = href.split("#")[0]
                if href and href.startswith("http") and href not in seen and self.allowed(href):
                    seen.add(href)
                    links.append({"url": href, "text": label})
            out.update(title=p.title.strip(), text=body[: self.max_chars], text_truncated=len(body) > self.max_chars, links=links[:200])
        else:
            out.update(text=text[: self.max_chars], text_truncated=len(text) > self.max_chars)
        return out


def _tool(name, desc, props, req=()):
    return {"type": "function", "function": {"name": name, "description": desc,
                                             "parameters": {"type": "object", "properties": props, "required": list(req)}}}


S, I, O = {"type": "string"}, {"type": "integer"}, {"type": "object"}
TOOLS = [
    _tool("fetch", "Fetch a URL (allowed domains only). Saves raw evidence; returns text, title, links.", {"url": S}, ["url"]),
    _tool("ledger_claim", "Claim up to n pending items.", {"n": I}, ["n"]),
    _tool("ledger_done", "Record a finished item. result must contain all required fields.", {"key": S, "result": O, "evidence": S}, ["key", "result"]),
    _tool("ledger_fail", "Retryable failure.", {"key": S, "error": S}, ["key", "error"]),
    _tool("ledger_blocked", "Login wall / CAPTCHA / 403 / robots. Do not bypass.", {"key": S, "reason": S}, ["key", "reason"]),
    _tool("ledger_not_found", "Page genuinely lacks the data.", {"key": S, "reason": S}, ["key"]),
    _tool("ledger_add", "Register a discovered item.", {"key": S, "payload": O}, ["key"]),
    _tool("ledger_meta_set", "Store a value, e.g. discovery_cursor.", {"key": S, "value": S}, ["key", "value"]),
    _tool("ledger_set_expected", "Total the site itself reports.", {"n": I}, ["n"]),
    _tool("ledger_discovery_complete", "Mark enumeration exhaustive. Only when truly at the end.", {}),
    _tool("ledger_stats", "Current ledger counts.", {}),
]


class ApiBackend:
    interface = "tools"

    def __init__(self, cfg, log, ledger: Ledger):
        a = cfg.get("api", {})
        self.cfg, self.log, self.ledger = cfg, log, ledger
        self.pricing = cfg.get("pricing", {})
        self.reports_cost = bool(self.pricing)
        self.model = a.get("model") or os.environ.get("API_MODEL")
        if not self.model:
            raise FatalError("[api].model is required")
        self.base = (os.environ.get(a.get("base_url_env", "OPENAI_BASE_URL")) or a.get("base_url") or "https://api.openai.com/v1").rstrip("/")
        self.key = os.environ.get(a.get("api_key_env", "OPENAI_API_KEY"), "")
        self.max_steps = int(a.get("max_steps", 60))
        self.fetcher = Fetcher(cfg, Path("evidence"))

    # -- tool dispatch
    def _exec(self, name, args, deadline=math.inf):
        L = self.ledger
        try:
            if name == "fetch":
                return self.fetcher.fetch(args["url"], timeout=max(1.0, min(30.0, deadline - time.monotonic())))
            if name == "ledger_claim":
                return {"items": L.claim(int(args.get("n", 10)))}
            if name == "ledger_done":
                L.done(args["key"], args["result"], args.get("evidence"))
                return {"ok": True}
            if name == "ledger_fail":
                return {"status": L.fail(args["key"], args["error"])}
            if name == "ledger_blocked":
                L.blocked(args["key"], args["reason"]); return {"ok": True}
            if name == "ledger_not_found":
                L.not_found(args["key"], args.get("reason", "not found on site")); return {"ok": True}
            if name == "ledger_add":
                return {"added": L.add(args["key"], args.get("payload"))}
            if name == "ledger_meta_set":
                L.meta_set(args["key"], args["value"]); return {"ok": True}
            if name == "ledger_set_expected":
                L.meta_set("expected_total", int(args["n"])); return {"ok": True}
            if name == "ledger_discovery_complete":
                L.meta_set("discovery_complete", "1"); return {"ok": True}
            if name == "ledger_stats":
                return L.stats()
            return {"error": f"unknown tool {name}"}
        except (LedgerError, KeyError, TypeError, ValueError) as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def _chat(self, messages, deadline=math.inf):
        body = json.dumps({"model": self.model, "messages": messages, "tools": TOOLS, "tool_choice": "auto"}).encode()
        for attempt in range(4):
            left = deadline - time.monotonic()
            if left <= 0:
                raise RuntimeError("timeout: iteration deadline reached")
            req = urllib.request.Request(self.base + "/chat/completions", data=body, method="POST",
                                         headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.key}"})
            try:
                with urllib.request.urlopen(req, timeout=min(300.0, left)) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                    time.sleep(min(2 ** (attempt + 2), max(0.0, deadline - time.monotonic())))
                    continue
                raise RuntimeError(f"API HTTP {e.code}: {e.read()[:300]!r}")
            except (urllib.error.URLError, OSError, http.client.HTTPException, json.JSONDecodeError) as e:
                if attempt < 3:
                    time.sleep(min(2 ** (attempt + 2), max(0.0, deadline - time.monotonic())))
                    continue
                raise RuntimeError(f"API network/response error: {type(e).__name__}: {e}")

    def run(self, prompt, iter_dir: Path, ctx, budget: Budget):
        n = ctx["n"]
        messages = [{"role": "system", "content": "You are a careful data-collection agent. Use the tools. Be terse."},
                    {"role": "user", "content": prompt}]
        total = self.usage = Usage(cost_usd=0.0)  # self.usage: still readable by the caller if we raise mid-way
        tpath = iter_dir / f"iter-{n:03d}.transcript.jsonl"
        deadline = time.monotonic() + (ctx["timeout"] or math.inf)
        note, error = "", None
        with open(tpath, "w", encoding="utf-8", buffering=1) as tf:
            tf.write(json.dumps({"role": "user", "content": prompt[:3000]}, ensure_ascii=False) + "\n")
            for step in range(self.max_steps):
                if time.monotonic() > deadline:
                    error = f"timeout after {ctx['timeout']:.0f}s"
                    break
                why = budget.reason(total)
                if why:
                    note = f"stopped mid-batch: {why}"
                    break
                try:
                    resp = self._chat(messages, deadline)
                except RuntimeError as e:
                    error = str(e)
                    break
                u = resp.get("usage") or {}
                total.input += u.get("prompt_tokens", 0) or 0
                total.output += u.get("completion_tokens", 0) or 0
                total.cost_usd = price_cost(total, self.pricing) if self.pricing else None
                msg = resp["choices"][0]["message"]
                messages.append(msg)
                tf.write(json.dumps(msg, ensure_ascii=False, default=str)[:4000] + "\n")
                calls = msg.get("tool_calls") or []
                if not calls:
                    return IterResult(True, total, None, (msg.get("content") or "")[:300], note=note)
                for c in calls:
                    fn = c["function"]
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    res = self._exec(fn["name"], args, deadline)
                    content = json.dumps(res, ensure_ascii=False)[: self.fetcher.max_chars + 4000]
                    tf.write(json.dumps({"tool": fn["name"], "args": args, "result": content[:1500]}, ensure_ascii=False) + "\n")
                    messages.append({"role": "tool", "tool_call_id": c["id"], "content": content})
            else:
                note = f"max_steps ({self.max_steps}) reached"
        return IterResult(error is None, total, error, note=note)


# ----------------------------------------------------------------------------- misc helpers
def run_verify(cmd, cwd, env):
    if not cmd:
        return True, ""
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, env=env, capture_output=True, text=True, timeout=300)
        return p.returncode == 0, (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        return False, "verify command timed out"


def notify(cfg, text, log):
    n = cfg.get("notify", {})
    url = os.environ.get(n.get("discord_webhook_env", "DISCORD_WEBHOOK_URL"), "")
    if url:
        try:
            req = urllib.request.Request(url, data=json.dumps({"content": text[:1900]}).encode(), method="POST",
                                         headers={"Content-Type": "application/json", "User-Agent": "agent-runner"})
            urllib.request.urlopen(req, timeout=15).read()
        except Exception as e:
            log.warn("notify failed: %s", e)


def fmt_dur(s):
    s = int(s)
    return f"{s // 3600}h{(s % 3600) // 60:02d}m{s % 60:02d}s"


class State:
    def __init__(self):
        self.status, self.reason, self.exit_code = "error", "not started", EXIT_ERROR
        self.iterations, self.budget, self.ledger, self.started = [], None, None, dt.datetime.now()
        self.last_check = None


def finalize(st: State, cfg, log: RunLog, run_dir: Path):
    """Runs in `finally`: must never raise and must leave artefacts for every outcome."""
    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(s, signal.SIG_IGN)  # a second signal must not abort the summary
    ended = dt.datetime.now()
    summary = {"run_id": run_dir.name, "name": cfg.get("run", {}).get("name", ""), "status": st.status, "reason": st.reason,
               "exit_code": st.exit_code, "started_at": st.started.isoformat(timespec="seconds"),
               "ended_at": ended.isoformat(timespec="seconds"), "duration_s": round((ended - st.started).total_seconds(), 1),
               "iterations": len(st.iterations), "limits": cfg.get("limits", {})}
    try:
        b = st.budget
        summary["usage"] = {"tokens_counted": b.tokens, "input": b.u.input, "output": b.u.output, "cache_read": b.u.cache_read,
                            "cache_create": b.u.cache_create, "cost_usd": round(b.u.cost_usd or 0.0, 4),
                            "cost_complete": not b.cost_unknown, "estimated": b.u.estimated}
    except Exception:
        summary["usage"] = None
    problems = []
    try:
        L = st.ledger
        summary["ledger"] = L.stats()
        summary["check"] = L.check(cfg.get("run", {}).get("expected_tolerance_pct", 0.0))
        summary["results_written"] = L.export_jsonl(run_dir / "results.jsonl", ("done",))
        summary["problems_written"] = L.export_jsonl(run_dir / "problems.jsonl", ("failed", "blocked", "not_found", "pending", "in_progress"))
        problems = [dict(key=r["key"], status=r["status"], reason=r["last_error"]) for r in L.rows(("failed", "blocked", "not_found"))][:50]
    except Exception as e:
        summary["ledger_error"] = str(e)
    summary["iteration_log"] = st.iterations
    try:
        (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        lg = summary.get("ledger") or {}
        c = lg.get("counts", {})
        lines = [f"# Run {run_dir.name} - {st.status}", "", f"- reason: **{st.reason}**", f"- duration: {fmt_dur(summary['duration_s'])}, iterations: {len(st.iterations)}"]
        if summary.get("usage"):
            u = summary["usage"]
            lines.append(f"- tokens counted: {u['tokens_counted']:,} (in {u['input']:,} / out {u['output']:,} / cache_read {u['cache_read']:,})"
                         f", cost: ${u['cost_usd']}{'' if u['cost_complete'] else ' (incomplete: some iterations had no cost data)'}"
                         f"{', token numbers partly ESTIMATED' if u['estimated'] else ''}")
        lines.append(f"- ledger: total {lg.get('total')}, done {c.get('done')}, pending {c.get('pending')}, in_progress {c.get('in_progress')}, "
                     f"failed {c.get('failed')}, blocked {c.get('blocked')}, not_found {c.get('not_found')}")
        lines.append(f"- completeness check: {summary.get('check')}")
        if problems:
            lines += ["", "## Problems (first 50)"] + [f"- `{p['key']}` {p['status']}: {p['reason']}" for p in problems]
        lines += ["", "Files: summary.json, results.jsonl, problems.jsonl, events.jsonl, run.log, iter-*.{prompt.md,stdout,stderr}"]
        (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        log.info("FINAL %s (%s) exit=%s | done=%s/%s failed=%s blocked=%s | tokens=%s | %s", st.status, st.reason, st.exit_code,
                 c.get("done"), lg.get("total"), c.get("failed"), c.get("blocked"), summary.get("usage", {}) and summary["usage"]["tokens_counted"],
                 fmt_dur(summary["duration_s"]))
        log.event("final", **{k: summary[k] for k in ("status", "reason", "exit_code", "duration_s")})
        notify(cfg, f"[{summary['name'] or run_dir.name}] {st.status}: {st.reason} | done {c.get('done')}/{lg.get('total')} "
                    f"failed {c.get('failed')} blocked {c.get('blocked')} | {fmt_dur(summary['duration_s'])} | {run_dir}", log)
        hook = cfg.get("notify", {}).get("on_finish_cmd")
        if hook:
            subprocess.run([str(x).replace("{summary}", str(run_dir / "summary.json")) for x in hook], timeout=60)
    except Exception as e:  # last resort: still try to say something
        try:
            log.warn("finalize error: %s", e)
        except Exception:
            print(f"finalize error: {e}", file=sys.stderr)


# ----------------------------------------------------------------------------- main loop
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--backend", help="override [run].backend")
    ap.add_argument("--dry-run", action="store_true", help="print the first prompt/command and exit")
    args = ap.parse_args(argv)

    cfg_path = Path(args.config).resolve()
    cfg = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    run_cfg, lim, led_cfg = cfg.setdefault("run", {}), cfg.setdefault("limits", {}), cfg.setdefault("ledger", {})
    workdir = (cfg_path.parent / run_cfg.get("workdir", ".")).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    os.chdir(workdir)
    backend_name = args.backend or run_cfg.get("backend", "claude")

    # one run at a time (cron may start a new one while the previous is still going)
    if not args.dry_run:  # --dry-run must not touch any state
        Path("state").mkdir(exist_ok=True)
        lock_fd = open("state/runner.lock", "w")
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            Path("runs").mkdir(exist_ok=True)
            with open("runs/skipped.log", "a") as f:
                f.write(f"{dt.datetime.now().isoformat(timespec='seconds')} skipped: another run holds the lock\n")
            print("another run is active; skipping", file=sys.stderr)
            return EXIT_LOCKED

    base = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = Path("runs") / base
    k = 1
    while run_dir.exists():
        k += 1
        run_dir = Path("runs") / f"{base}-{k}"
    log = RunLog(Path(tempfile.mkdtemp()) if args.dry_run else run_dir)
    st = State()

    def _sig(signum, _frame):
        raise Interrupted(signal.Signals(signum).name)

    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGHUP, _sig)

    try:
        db = str((workdir / run_cfg.get("db", "state/ledger.db")).resolve())
        os.environ.update(LEDGER_DB=db, LEDGER_MAX_ATTEMPTS=str(led_cfg.get("max_attempts", 3)),
                          LEDGER_REQUIRED_FIELDS=",".join(led_cfg.get("required_fields", [])),
                          LEDGER_REQUIRE_EVIDENCE="1" if led_cfg.get("require_evidence", False) else "0",
                          LEDGER_CLAIM_TIMEOUT=str(led_cfg.get("claim_timeout_seconds", 1800)))
        in_mem = args.dry_run and not Path(db).exists()  # dry-run on a fresh workdir: scratch ledger, no files
        ledger = st.ledger = Ledger(":memory:" if in_mem else None)
        st.budget = Budget(lim, bool(lim.get("count_cache_read_tokens", False)))
        task_text = Path(run_cfg.get("task_file", "task.md")).read_text(encoding="utf-8")
        tol = run_cfg.get("expected_tolerance_pct", 0.0)

        seed = run_cfg.get("seed_file")
        if seed and (in_mem or not args.dry_run) and ledger.stats()["total"] == 0:
            n = ledger.add_lines(Path(seed).read_text(encoding="utf-8").splitlines())
            ledger.meta_set("discovery_complete", "1")
            log.info("seeded ledger with %d items from %s (discovery marked complete)", n, seed)

        if backend_name == "api":
            backend = ApiBackend(cfg, log, ledger)
        else:
            backend = CliBackend(backend_name, cfg, log)
        if lim.get("max_cost_usd") and not backend.reports_cost:
            log.warn("max_cost_usd is set but backend %r reports no cost and [pricing] is empty -> cost limit CANNOT trigger; use token/time limits", backend_name)
        if backend_name != "claude" and lim.get("max_total_tokens"):
            log.warn("token counts for %r are parsed from its output when available, otherwise ESTIMATED; they are checked between iterations only", backend_name)

        env = dict(os.environ)
        ledger_path = str(HERE / "ledger.py")
        log.info("start run=%s backend=%s workdir=%s limits=%s", run_dir.name, backend_name, workdir, json.dumps(lim))
        log.event("start", backend=backend_name, limits=lim, workdir=str(workdir))

        if args.dry_run:
            stats = ledger.stats()
            prompt = build_prompt(task_text, stats, cfg, backend.interface, ledger_path, None)
            print("----- PROMPT -----\n" + prompt)
            if isinstance(backend, CliBackend):
                argv_, stdin_ = backend.build_argv(prompt, Path("<prompt_file>"), {"iter_budget_usd": st.budget.remaining_cost(), "ledger_path": ledger_path})
                print("\n----- COMMAND -----\n" + " ".join(a if len(a) < 120 else "<prompt>" for a in argv_) + (" < prompt_file" if stdin_ else ""))
            st.status, st.reason, st.exit_code = "dry-run", "dry-run", EXIT_OK
            return EXIT_OK

        # we hold the runner lock, so no agent is running: claims left by a killed/crashed previous run are dead
        released = ledger.release_in_progress()
        if released:
            log.info("released %d in_progress items left by a previous run", released)
        stalled = consec_fail = 0
        feedback = None
        verify_cmd = cfg.get("verify", {}).get("cmd", "")
        while True:
            chk = ledger.check(tol)
            st.last_check = chk
            feedback = None
            if chk["complete"]:
                ok, out = run_verify(verify_cmd, workdir, env)
                if ok:
                    st.status, st.reason, st.exit_code = "completed", "ledger complete and verify passed", EXIT_OK
                    break
                feedback = out or "verify command failed with no output"
                log.warn("ledger complete but verify FAILED: %s", feedback[-300:])
            why = st.budget.reason()  # after the completeness check: finishing on the last allowed iteration is success
            if why:
                st.status, st.reason, st.exit_code = "stopped", f"limit: {why}", EXIT_LIMIT
                break
            n = st.budget.iterations + 1
            before = ledger.stats()
            sig_before = (before["terminal"], before["total"], before["discovery_complete"], json.dumps(before["meta"], sort_keys=True))
            timeout = float(lim.get("iteration_timeout_seconds", 1800)) or None  # 0 = no limit
            rem_s = st.budget.remaining_seconds()
            if rem_s is not None:
                timeout = max(30.0, min(timeout or rem_s, rem_s))
            iter_cap = lim.get("max_cost_usd_per_iteration")
            rem_c = st.budget.remaining_cost()
            caps = [x for x in (iter_cap or None, rem_c) if x is not None]
            ctx = {"n": n, "cwd": str(workdir), "env": env, "timeout": timeout, "ledger_path": ledger_path,
                   "iter_budget_usd": min(caps) if caps else None}
            prompt = build_prompt(task_text, before, cfg, backend.interface, ledger_path, feedback)
            log.info("iter %d start | ledger done=%s pending=%s in_progress=%s failed=%s blocked=%s | tokens=%s cost=$%.4f elapsed=%s",
                     n, before["counts"]["done"], before["counts"]["pending"], before["counts"]["in_progress"], before["counts"]["failed"],
                     before["counts"]["blocked"], st.budget.tokens, st.budget.u.cost_usd or 0, fmt_dur(st.budget.elapsed))
            t0 = time.monotonic()
            try:
                res = backend.run(prompt, run_dir, ctx, st.budget)
            except (FatalError, Interrupted):
                raise
            except Exception as e:  # one bad iteration must not kill the whole job: count it as a failure
                log.logger.exception("iteration %d crashed", n)
                res = IterResult(False, getattr(backend, "usage", None) or Usage(), f"{type(e).__name__}: {e}")
            finally:
                st.budget.iterations += 1
            st.budget.add(res.usage)
            after = ledger.stats()
            sig_after = (after["terminal"], after["total"], after["discovery_complete"], json.dumps(after["meta"], sort_keys=True))
            progressed = sig_after != sig_before
            rec = {"n": n, "ok": res.ok, "error": res.error, "timed_out": res.timed_out, "duration_s": round(time.monotonic() - t0, 1),
                   "tokens": res.usage.tokens(st.budget.count_cache_read), "cost_usd": res.usage.cost_usd, "estimated": res.usage.estimated,
                   "progress": progressed, "terminal_after": after["terminal"], "total_after": after["total"], "note": res.note,
                   "summary": res.summary[:200]}
            st.iterations.append(rec)
            log.event("iteration", **rec)
            log.info("iter %d end   | ok=%s progress=%s %s%s | +tokens=%s +cost=$%s | %s", n, res.ok, progressed, f"error={res.error} " if res.error else "",
                     f"note={res.note} " if res.note else "", rec["tokens"], f"{res.usage.cost_usd:.4f}" if res.usage.cost_usd is not None else "?",
                     res.summary[:120].replace("\n", " "))
            if not res.ok:
                ledger.release_in_progress()  # agent is dead (we only run one), its claims would otherwise sit until claim_timeout
            consec_fail = 0 if res.ok else consec_fail + 1
            stalled = 0 if progressed else stalled + 1
            max_cf = lim.get("max_consecutive_failures", 3)
            if max_cf and consec_fail >= max_cf:
                st.status, st.reason, st.exit_code = "stopped", f"{consec_fail} consecutive failed iterations (last: {res.error})", EXIT_FAILURES
                break
            max_st = lim.get("max_stalled_iterations", 3)
            if max_st and stalled >= max_st:
                st.status, st.reason, st.exit_code = "stopped", f"stalled: no ledger progress in {stalled} iterations", EXIT_STALLED
                break
        return st.exit_code
    except Interrupted as e:
        st.status, st.reason, st.exit_code = "interrupted", f"signal {e}", EXIT_INTERRUPTED
        log.warn("interrupted by %s", e)
        return st.exit_code
    except FatalError as e:
        st.status, st.reason, st.exit_code = "error", f"fatal: {e}", EXIT_ERROR
        log.warn("fatal: %s", e)
        return st.exit_code
    except BaseException as e:  # noqa: BLE001 - we must always finalize
        st.status, st.reason, st.exit_code = "error", f"internal error: {type(e).__name__}: {e}", EXIT_ERROR
        log.logger.exception("internal error")
        return st.exit_code
    finally:
        if st.ledger is not None and st.budget is not None and st.status != "dry-run":
            finalize(st, cfg, log, run_dir)
        elif st.status != "dry-run":
            log.warn("run ended before setup finished: %s", st.reason)
            (run_dir / "summary.json").write_text(json.dumps({"status": st.status, "reason": st.reason, "exit_code": st.exit_code}), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
