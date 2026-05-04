#!/usr/bin/env python3
"""
Maez CLI — surface-agnostic terminal interface.

Usage:
    .venv/bin/python3 cli.py
    .venv/bin/python3 cli.py --no-memory
"""

import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MAEZ_ROOT  = os.path.dirname(os.path.abspath(__file__))

# Load config/.env so MAEZ_LLM_BACKEND=llamacpp is picked up by llm_client
_env_path = os.path.join(MAEZ_ROOT, "config", ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

MODEL      = "gemma-4-26b"
MAX_ITERS  = 12       # up from 6 — gives model more recovery chances

# ── Soul ──────────────────────────────────────────────────────────────────────

def _load_soul() -> str:
    path = os.path.join(MAEZ_ROOT, "config", "soul.md")
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return "You are Maez, a personal AI companion running on the owner's machine."


# ── Lane classification ───────────────────────────────────────────────────────

_READONLY_CMD_RE = re.compile(
    r'^\s*('
    r'ls\b|cat\b|head\b|tail\b|less\b|more\b|file\b|stat\b|'
    r'find\b|locate\b|which\b|whereis\b|type\b|'
    r'echo\b|printf\b|'
    r'grep\b|rg\b|ag\b|ack\b|'
    r'df\b|du\b|lsblk\b|lscpu\b|lspci\b|lsusb\b|lshw\b|'
    r'ps\b|top\b|htop\b|pgrep\b|pstree\b|'
    r'free\b|uptime\b|uname\b|hostname\b|whoami\b|id\b|'
    r'nvidia-smi\b|gpustat\b|sensors\b|'
    r'systemctl\s+(is-active|is-enabled|status|list-units)\b|'
    r'dpkg\s+-l\b|dpkg\s+--list\b|'
    r'apt\s+list\b|apt-cache\b|'
    r'snap\s+list\b|flatpak\s+list\b|'
    r'pip\s+(list|show|freeze)\b|pip3\s+(list|show|freeze)\b|'
    r'git\s+(log|status|diff|show|branch|remote|tag)\b|'
    r'curl\s+(-s|-I|--head)\b|wget\s+-q\b|'
    r'python3?\s+-c\s+["\']print\b|'
    r'wc\b|sort\b|uniq\b|awk\b|sed\s+-n\b|cut\b|tr\b|'
    r'ls\s+/|cat\s+/|'
    r'readlink\b|realpath\b|pwd\b|env\b|printenv\b'
    r')',
    re.IGNORECASE,
)

_SAFE_WRITE_PATHS = (
    "/tmp/",
    "/home/rohit/maez/",
    "/home/rohit/notes",
    "/home/rohit/scratch",
)

def _get_lane(action: str, params: dict) -> int:
    """Return 0 (inline) or 2 (needs consent)."""
    if action in ("web_search", "fetch_url", "read_file", "search_files"):
        return 0
    if action == "search_code":
        return 0
    if action == "run_shell":
        cmd = params.get("cmd", "").strip()
        if _READONLY_CMD_RE.match(cmd):
            return 0
        # sudo ls, sudo cat etc — still readonly
        if re.match(r'sudo\s+', cmd):
            rest = re.sub(r'^sudo\s+', '', cmd)
            if _READONLY_CMD_RE.match(rest):
                return 0
        # Running scripts in safe paths is fine
        _safe_run_re = re.compile(
            r'^(python3?|bash|sh|node|ruby|perl)\s+('
            + '|'.join(re.escape(p) for p in _SAFE_WRITE_PATHS) + r')',
        )
        if _safe_run_re.match(cmd):
            return 0
        return 2
    if action == "write_any_file":
        path = params.get("path", "")
        if any(path.startswith(p) for p in _SAFE_WRITE_PATHS):
            return 0
        return 2
    if action == "edit_file":
        path = params.get("path", "")
        if any(path.startswith(p) for p in _SAFE_WRITE_PATHS):
            return 0
        return 2
    return 2


# ── Plain-English descriptions ────────────────────────────────────────────────

def _infer_what(action: str, params: dict) -> str:
    cmd  = str(params.get("cmd", "")).strip()
    path = str(params.get("path", ""))
    pe   = str(params.get("plain_english", "") or params.get("reason", "")).strip()

    if action == "run_shell" and cmd:
        for mgr, label in [
            ("flatpak install", "Install via Flathub app store"),
            ("snap install",    "Install via Snap"),
            ("apt-get install", "Install package"),
            ("apt install",     "Install package"),
            ("pip install",     "Install Python package"),
            ("npm install",     "Install Node package"),
        ]:
            if mgr in cmd:
                pkg = cmd.split()[-1].split("/")[-1].replace("-y","").strip()
                return f"{label}: {pkg}"
        if "add-apt-repository" in cmd:
            return "Add a third-party software source"
        if re.search(r'systemctl\s+(start|stop|enable|disable|restart)\b', cmd):
            return "Control a system service"
        if pe:
            return pe
        return f"Run: {cmd[:100]}"
    if action in ("write_any_file", "edit_file") and path:
        verb = "Edit" if action == "edit_file" else "Write to"
        return f"{verb} file: {path}"
    return pe or action


def _infer_impact(action: str, params: dict) -> str:
    cmd  = str(params.get("cmd", ""))
    path = str(params.get("path", ""))
    if "flatpak install" in cmd:
        return "Adds an app via Flathub. Sandboxed, easy to remove."
    if "snap install" in cmd:
        return "Adds an app via Snap. Sandboxed, easy to remove."
    if "apt-get install" in cmd or "apt install" in cmd:
        return "Installs a package on your system. Can be uninstalled."
    if "add-apt-repository" in cmd:
        return "Adds a third-party software source."
    if "systemctl" in cmd:
        return "Changes how a system service runs."
    if action in ("write_any_file", "edit_file"):
        if path.startswith("/etc") or path.startswith("/usr"):
            return "Modifies a system config file."
        return "Writes/edits a file. Can be undone."
    if "sudo" in cmd:
        return "Needs admin access to run."
    return "Makes a change to your system."


# ── Tool-call parser ──────────────────────────────────────────────────────────

_TC_RE = re.compile(r'TOOL_CALL\s*[:=]?\s*(\{.*)', re.DOTALL)

def _parse_tool_call(text: str) -> dict | None:
    m = _TC_RE.search(text)
    if not m:
        return None
    blob = m.group(1).strip()
    depth, end = 0, -1
    for i, c in enumerate(blob):
        if c == '{':   depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        return None
    try:
        obj = json.loads(blob[:end])
        if "action" in obj:
            return {"action": str(obj["action"]), "params": dict(obj.get("params", {}))}
    except Exception:
        pass
    return None


# ── Tool execution ────────────────────────────────────────────────────────────

def _execute(actions, action: str, params: dict):
    """Dispatch to ActionEngine or handle locally."""
    from core.action_engine import ActionResult

    reason = str(params.get("reason", action))

    if action == "search_code":
        return _do_search_code(params)

    if action == "edit_file":
        return _do_edit_file(params)

    dispatch = {
        "run_shell":      lambda: actions.run_shell(
            cmd=params.get("cmd", ""), reason=reason),
        "write_any_file": lambda: actions.write_any_file(
            path=params.get("path", ""),
            content=params.get("content", ""),
            reason=reason),
        "read_file":      lambda: actions.read_file(
            path=params.get("path", ""), reasoning=reason),
        "search_files":   lambda: actions.search_files(
            pattern=params.get("pattern", "*"),
            directory=params.get("directory", "."),
            reasoning=reason),
        "web_search":     lambda: actions.web_search(
            query=params.get("query", ""), reasoning=reason),
        "fetch_url":      lambda: actions.fetch_url(
            url=params.get("url", ""), reasoning=reason),
    }
    fn = dispatch.get(action)
    if fn is None:
        return ActionResult(action=action, tier=2, success=False,
                            output="", error=f"unknown action: {action}")
    return fn()


def _do_search_code(params: dict):
    """grep-based code search — much better than find for codebase queries."""
    from core.action_engine import ActionResult
    pattern   = params.get("pattern", "")
    directory = params.get("directory", MAEZ_ROOT)
    file_type = params.get("file_type", "")   # e.g. "py", "js"
    max_lines = int(params.get("max_lines", 80))

    if not pattern:
        return ActionResult(action="search_code", tier=0, success=False,
                            output="", error="pattern required")
    glob = f"*.{file_type}" if file_type else "*"
    cmd = ["grep", "-r", "--include", glob, "-n", "-l", pattern, directory]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        files = r.stdout.strip().splitlines()
        if not files:
            # Try content search
            cmd2 = ["grep", "-r", "--include", glob, "-n", pattern, directory]
            r2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=30)
            out = r2.stdout.strip()[:4000] or f"No matches for {pattern!r}"
        else:
            # Summarise: list files + first match per file
            lines = [f"Files containing {pattern!r} ({len(files)} files):"]
            for f in files[:max_lines]:
                lines.append(f"  {f}")
            if len(files) > max_lines:
                lines.append(f"  ... and {len(files) - max_lines} more")
            out = "\n".join(lines)
        return ActionResult(action="search_code", tier=0, success=True,
                            output=out, error="")
    except Exception as e:
        return ActionResult(action="search_code", tier=0, success=False,
                            output="", error=str(e))


def _do_edit_file(params: dict):
    """Surgical find-and-replace in a file."""
    from core.action_engine import ActionResult
    path    = params.get("path", "")
    old_str = params.get("old", "")
    new_str = params.get("new", "")

    if not path or not old_str:
        return ActionResult(action="edit_file", tier=0, success=False,
                            output="", error="path and old required")
    try:
        with open(path) as f:
            content = f.read()
        if old_str not in content:
            return ActionResult(action="edit_file", tier=0, success=False,
                                output="", error=f"string not found in {path}")
        count = content.count(old_str)
        new_content = content.replace(old_str, new_str, 1)
        with open(path, "w") as f:
            f.write(new_content)
        return ActionResult(action="edit_file", tier=0, success=True,
                            output=f"Replaced 1 of {count} occurrence(s) in {path}",
                            error="")
    except Exception as e:
        return ActionResult(action="edit_file", tier=0, success=False,
                            output="", error=str(e))


# ── Tool manifest ─────────────────────────────────────────────────────────────

_TOOL_MANIFEST = f"""\
TOOLS (running on the owner's machine at {MAEZ_ROOT}):

1. run_shell      {{"cmd":"<bash>","reason":"<why>"}}
   Any shell command. sudo ok. Chains ok.
   Read-only probes run automatically without asking.

2. write_any_file {{"path":"/abs/path","content":"...","reason":"<why>"}}
   ONLY for /home/rohit/ and /tmp/ paths. For /etc/, /usr/, /lib/ use run_shell with sudo tee:
   Example: echo '...' | sudo tee /etc/udev/rules.d/foo.rules

3. edit_file      {{"path":"/abs/path","old":"exact string","new":"replacement"}}
   Surgical single-occurrence find-and-replace in a file.
   Safer than write_any_file for code edits.

4. read_file      {{"path":"/abs/path"}}
   Read up to 5KB of any file.

5. search_code    {{"pattern":"regex","directory":"/abs/path","file_type":"py"}}
   grep-based search. Returns matching file list + line numbers.
   Use this for codebase questions, not search_files.
   Example: find all Python files → {{"pattern":".","directory":"{MAEZ_ROOT}","file_type":"py"}}

6. web_search     {{"query":"..."}}
   DuckDuckGo search.

7. fetch_url      {{"url":"https://...","max_chars":3000}}
   Fetch and strip a webpage.

RULES:
- Hardware/system questions: probe with run_shell FIRST. Never answer without data.
- Codebase questions: use search_code, not search_files. search_files is shallow.
- To count files: run_shell with find . -name "*.py" | wc -l
- Install requests: emit the install TOOL_CALL immediately.
- Emit: TOOL_CALL: {{"action":"<name>","params":{{...}}}}
- Write DONE only when finished.
- ONE TOOL_CALL per turn. No prose. No explanations. Just TOOL_CALL or DONE.
"""


# ── Jarvis loop ───────────────────────────────────────────────────────────────

def _run_jarvis_loop(user_text: str, actions, llm_client, soul: str,
                     history: list, use_memory: bool, memory=None,
                     authority_granted: bool = False) -> list:

    transcript = []
    denied_actions = set()  # track denied (action, cmd_prefix) to stop repeating

    seed = f"the owner just said: {user_text!r}\n\n{_TOOL_MANIFEST}\n\nBegin."
    loop_history = [seed]
    empty_count = 0

    for step in range(MAX_ITERS):
        convo = "\n\n".join(loop_history)
        try:
            resp = llm_client.chat(
                model=MODEL,
                messages=[
                    {"role": "system",
                     "content": "You are Maez. You control the owner's computer. "
                                "Each turn: emit ONE TOOL_CALL line, or write DONE. "
                                "No other text. TOOL_CALL must come first on its own line."},
                    {"role": "user", "content": convo},
                ],
                stream=False, think=False,
                options={"temperature": 0.15, "num_predict": 512},
            )
            text = (resp.message.content or "").strip()
        except Exception as e:
            print(f"\n  [LLM error: {e}]")
            break

        call = _parse_tool_call(text)

        if call is None:
            empty_count += 1
            if empty_count == 1 and text and "DONE" not in text.upper():
                # Retry once with explicit nudge
                loop_history.append(
                    "PARSE_ERROR: No TOOL_CALL found. "
                    "You must emit exactly: TOOL_CALL: {\"action\":\"...\",\"params\":{...}} "
                    "or write DONE."
                )
                continue
            break  # DONE or second empty — exit loop

        action = call["action"]
        params = dict(call.get("params", {}))
        plain_english = params.pop("plain_english", None)

        # Skip repeats of denied actions
        deny_key = (action, params.get("cmd", params.get("path", ""))[:60])
        if deny_key in denied_actions:
            loop_history.append(
                f"SKIP: {action} with similar params was already denied this turn. "
                "Try a different approach or write DONE."
            )
            continue

        lane = _get_lane(action, params)

        # Lane 0 — execute without asking
        if lane == 0:
            try:
                result = _execute(actions, action, params)
                ok  = result.success
                out = (result.output or "").strip()[:2000] or "(no output)"
                if not ok:
                    out = result.error or "error"
            except Exception as e:
                ok, out = False, f"error: {e}"
            transcript.append((action, params, out, ok))
            loop_history.append(
                f"TOOL_CALL: {json.dumps({'action': action, 'params': params})}\nRESULT: {out}"
            )
            empty_count = 0
            continue

        # Lane 2 — ask unless authority granted
        what   = plain_english or _infer_what(action, call.get("params", {}))
        impact = _infer_impact(action, params)

        if not authority_granted:
            print(f"\n  {what}")
            print(f"  {impact}")
            try:
                answer = input("  Go ahead? (y/n/always): ").strip().lower()
            except EOFError:
                answer = "n"

            if answer in ("always", "a"):
                authority_granted = True
            elif answer not in ("y", "yes"):
                denied_actions.add(deny_key)
                transcript.append((action, params, "DENIED by user", False))
                loop_history.append(
                    f"TOOL_CALL: {json.dumps({'action': action, 'params': params})}\n"
                    f"RESULT: User said no. Try a different method or write DONE."
                )
                empty_count = 0
                continue

        print(f"  Running: {what}...", flush=True)
        try:
            result = _execute(actions, action, params)
            ok  = result.success
            out = (result.output or "").strip()[:2000] or "(no output)"
            if not ok:
                out = result.error or "error"
        except Exception as e:
            ok, out = False, f"error: {e}"

        transcript.append((action, params, out, ok))
        loop_history.append(
            f"TOOL_CALL: {json.dumps({'action': action, 'params': params})}\nRESULT: {out}"
        )
        empty_count = 0

    return transcript


# ── Final reply ───────────────────────────────────────────────────────────────

def _final_reply(user_text: str, transcript: list, history: list,
                 llm_client, soul: str) -> str:

    if transcript:
        lines = ["[WHAT HAPPENED THIS TURN — treat as ground truth:"]
        for action, params, out, ok in transcript:
            mark = "✓" if ok else "✗"
            label = _infer_what(action, params)
            if ok == False and out == "DENIED by user":
                lines.append(f"  ✗ {label} — user said no")
            else:
                lines.append(f"  {mark} {label}")
                lines.append(f"     → {out[:400]}")
        lines.append("]")
        lines.append("")
        lines.append("Report results directly. If a ✓ ran, say what you found. "
                     "If ✗ denied, acknowledge it. "
                     "Never say 'waiting for approval' — nothing is pending.\n"
                     "CRITICAL: If only read/probe tools ran (ls, cat, grep, ps, etc.), "
                     "nothing is running in the background. Do NOT say 'I'm working on it', "
                     "'I'll monitor progress', or 'I'll let you know when done' — "
                     "those are lies. Say what you found and stop.")
        grounding = "\n".join(lines)
    else:
        grounding = (
            "[No tools ran this turn. "
            "Answer from knowledge only. "
            "Do NOT claim to have run, proposed, or checked anything.]"
        )

    messages = [
        {"role": "system", "content": soul},
        {"role": "system", "content": grounding},
    ]
    messages.extend(history[-8:])
    messages.append({"role": "user", "content": user_text})

    for attempt in range(2):
        try:
            resp = llm_client.chat(
                model=MODEL,
                messages=messages,
                stream=False, think=False,
                options={"temperature": 0.5, "num_predict": 600},
            )
            reply = (resp.message.content or "").strip()
            # Strip grounding block or soul.md entries if model echoed them back
            reply = re.sub(
                r'\[WHAT HAPPENED THIS TURN.*?\]\s*', '', reply,
                flags=re.DOTALL,
            ).strip()
            reply = re.sub(
                r'\[\d{4}-\d{2}-\d{2}.*?##.*?\n.*?\n.*?\n', '', reply,
                flags=re.DOTALL,
            ).strip()
            if reply:
                return reply
            # Empty reply — add stronger nudge and retry
            messages.append({"role": "assistant", "content": ""})
            messages.append({"role": "user",
                             "content": "Please give a short direct answer based on the results above."})
        except Exception as e:
            return f"[reply error: {e}]"

    return "(no response)"


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Maez CLI")
    parser.add_argument("--no-memory", action="store_true")
    args = parser.parse_args()

    print("Initializing Maez...", end=" ", flush=True)

    soul = _load_soul()

    memory = None
    if not args.no_memory:
        try:
            from memory.memory_manager import MemoryManager
            memory = MemoryManager()
        except Exception as e:
            print(f"\n  [memory: {e}]")

    try:
        from core.action_engine import ActionEngine
        actions = ActionEngine(memory=memory)
    except Exception as e:
        print(f"\n  [ActionEngine: {e}]")
        actions = None

    try:
        from core import llm_client
    except Exception as e:
        print(f"\nFatal: {e}")
        sys.exit(1)

    print("ready.\n")
    print("Commands: 'quit' to exit | type 'always' at any check-in to grant full authority\n")

    history = []
    _AUTHORITY_RE = re.compile(
        r'\b(full\s+authority|do\s+whatever(\s+it\s+takes)?|just\s+do\s+it|'
        r'go\s+for\s+it|full\s+permission|authorize\s+everything|'
        r'you\s+have\s+(full\s+)?control)\b',
        re.IGNORECASE,
    )

    while True:
        try:
            user_text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not user_text:
            continue
        if user_text.lower() in ("quit", "exit", "bye"):
            print("Maez: See you.")
            break

        authority_granted = bool(_AUTHORITY_RE.search(user_text))

        transcript = []
        if actions:
            try:
                transcript = _run_jarvis_loop(
                    user_text, actions, llm_client, soul, history,
                    use_memory=not args.no_memory, memory=memory,
                    authority_granted=authority_granted,
                )
            except Exception as e:
                print(f"  [loop error: {e}]")

        reply = _final_reply(user_text, transcript, history, llm_client, soul)
        print(f"\nMaez: {reply}\n")

        history.append({"role": "user",      "content": user_text})
        history.append({"role": "assistant", "content": reply})
        if len(history) > 24:
            history = history[-24:]


if __name__ == "__main__":
    main()
