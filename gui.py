#!/usr/bin/env python3
"""
Maez GUI — native Ubuntu desktop chat window.
Same Jarvis loop as cli.py, Tkinter front-end.

Usage:
    .venv/bin/python3 gui.py
"""

import json
import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, scrolledtext

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MAEZ_ROOT = os.path.dirname(os.path.abspath(__file__))

# Load config/.env before llm_client import
_env_path = os.path.join(MAEZ_ROOT, "config", ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

MODEL     = "gemma-4-26b"
MAX_ITERS = 12

# ── Soul ──────────────────────────────────────────────────────────────────────

def _load_soul() -> str:
    try:
        with open(os.path.join(MAEZ_ROOT, "config", "soul.md")) as f:
            return f.read()
    except Exception:
        return "You are Maez, a personal AI companion running on the owner's machine."


# ── Lane classification (same as cli.py) ──────────────────────────────────────

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
    if action in ("web_search", "fetch_url", "read_file", "search_files", "search_code"):
        return 0
    if action == "run_shell":
        cmd = params.get("cmd", "").strip()
        if _READONLY_CMD_RE.match(cmd):
            return 0
        if re.match(r'sudo\s+', cmd):
            rest = re.sub(r'^sudo\s+', '', cmd)
            if _READONLY_CMD_RE.match(rest):
                return 0
        _safe_run_re = re.compile(
            r'^(python3?|bash|sh|node|ruby|perl)\s+('
            + '|'.join(re.escape(p) for p in _SAFE_WRITE_PATHS) + r')',
        )
        if _safe_run_re.match(cmd):
            return 0
        return 2
    if action in ("write_any_file", "edit_file"):
        path = params.get("path", "")
        if any(path.startswith(p) for p in _SAFE_WRITE_PATHS):
            return 0
        return 2
    return 2


def _infer_what(action: str, params: dict) -> str:
    cmd  = str(params.get("cmd", "")).strip()
    path = str(params.get("path", ""))
    pe   = str(params.get("plain_english", "") or params.get("reason", "")).strip()
    if action == "run_shell" and cmd:
        for mgr, label in [
            ("flatpak install", "Install via Flathub"),
            ("snap install",    "Install via Snap"),
            ("apt-get install", "Install package"),
            ("apt install",     "Install package"),
            ("pip install",     "Install Python package"),
        ]:
            if mgr in cmd:
                pkg = cmd.split()[-1].split("/")[-1].replace("-y","").strip()
                return f"{label}: {pkg}"
        if re.search(r'systemctl\s+(start|stop|enable|disable|restart)\b', cmd):
            return "Control a system service"
        if pe:
            return pe
        return f"Run: {cmd[:100]}"
    if action in ("write_any_file", "edit_file") and path:
        verb = "Edit" if action == "edit_file" else "Write to"
        return f"{verb}: {path}"
    return pe or action


def _infer_impact(action: str, params: dict) -> str:
    cmd  = str(params.get("cmd", ""))
    path = str(params.get("path", ""))
    if "apt" in cmd:
        return "Installs a package. Can be uninstalled."
    if "systemctl" in cmd:
        return "Changes how a system service runs."
    if action in ("write_any_file", "edit_file"):
        if path.startswith("/etc") or path.startswith("/usr"):
            return "Modifies a system config file."
        return "Writes/edits a file."
    if "sudo" in cmd:
        return "Needs admin access."
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


# ── Tool execution ─────────────────────────────────────────────────────────────

def _execute(actions, action: str, params: dict):
    from core.action_engine import ActionResult
    reason = str(params.get("reason", action))

    if action == "search_code":
        return _do_search_code(params)
    if action == "edit_file":
        return _do_edit_file(params)

    dispatch = {
        "run_shell":      lambda: actions.run_shell(cmd=params.get("cmd", ""), reason=reason),
        "write_any_file": lambda: actions.write_any_file(
            path=params.get("path", ""), content=params.get("content", ""), reason=reason),
        "read_file":      lambda: actions.read_file(path=params.get("path", ""), reasoning=reason),
        "search_files":   lambda: actions.search_files(
            pattern=params.get("pattern", "*"), directory=params.get("directory", "."), reasoning=reason),
        "web_search":     lambda: actions.web_search(query=params.get("query", ""), reasoning=reason),
        "fetch_url":      lambda: actions.fetch_url(url=params.get("url", ""), reasoning=reason),
    }
    fn = dispatch.get(action)
    if fn is None:
        return ActionResult(action=action, tier=2, success=False, output="", error=f"unknown action: {action}")
    return fn()


def _do_search_code(params: dict):
    from core.action_engine import ActionResult
    pattern   = params.get("pattern", "")
    directory = params.get("directory", MAEZ_ROOT)
    file_type = params.get("file_type", "")
    max_lines = int(params.get("max_lines", 80))
    if not pattern:
        return ActionResult(action="search_code", tier=0, success=False, output="", error="pattern required")
    glob = f"*.{file_type}" if file_type else "*"
    cmd = ["grep", "-r", "--include", glob, "-n", "-l", pattern, directory]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        files = r.stdout.strip().splitlines()
        if not files:
            cmd2 = ["grep", "-r", "--include", glob, "-n", pattern, directory]
            r2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=30)
            out = r2.stdout.strip()[:4000] or f"No matches for {pattern!r}"
        else:
            lines = [f"Files containing {pattern!r} ({len(files)} files):"]
            for f in files[:max_lines]:
                lines.append(f"  {f}")
            if len(files) > max_lines:
                lines.append(f"  ... and {len(files) - max_lines} more")
            out = "\n".join(lines)
        return ActionResult(action="search_code", tier=0, success=True, output=out, error="")
    except Exception as e:
        return ActionResult(action="search_code", tier=0, success=False, output="", error=str(e))


def _do_edit_file(params: dict):
    from core.action_engine import ActionResult
    path    = params.get("path", "")
    old_str = params.get("old", "")
    new_str = params.get("new", "")
    if not path or not old_str:
        return ActionResult(action="edit_file", tier=0, success=False, output="", error="path and old required")
    try:
        with open(path) as f:
            content = f.read()
        if old_str not in content:
            return ActionResult(action="edit_file", tier=0, success=False, output="", error=f"string not found in {path}")
        count = content.count(old_str)
        new_content = content.replace(old_str, new_str, 1)
        with open(path, "w") as f:
            f.write(new_content)
        return ActionResult(action="edit_file", tier=0, success=True,
                            output=f"Replaced 1 of {count} occurrence(s) in {path}", error="")
    except Exception as e:
        return ActionResult(action="edit_file", tier=0, success=False, output="", error=str(e))


# ── Tool manifest ─────────────────────────────────────────────────────────────

_TOOL_MANIFEST = f"""\
TOOLS (running on the owner's machine at {MAEZ_ROOT}):

1. run_shell      {{"cmd":"<bash>","reason":"<why>"}}
2. write_any_file {{"path":"/abs/path","content":"...","reason":"<why>"}}
   ONLY for /home/rohit/ and /tmp/ paths. For /etc/, /usr/, /lib/ use run_shell with sudo tee.
3. edit_file      {{"path":"/abs/path","old":"exact string","new":"replacement"}}
4. read_file      {{"path":"/abs/path"}}
5. search_code    {{"pattern":"regex","directory":"/abs/path","file_type":"py"}}
6. web_search     {{"query":"..."}}
7. fetch_url      {{"url":"https://...","max_chars":3000}}

SYSTEM PATH WRITES — always use run_shell with sudo tee:
  /etc/udev/rules.d/foo.rules  → echo '...' | sudo tee /etc/udev/rules.d/foo.rules
  /etc/systemd/system/foo.service → cat << EOF | sudo tee /etc/systemd/system/foo.service
  Never use write_any_file for paths outside /home/rohit/ or /tmp/.

RULES:
- Hardware/system questions: probe with run_shell FIRST.
- Emit: TOOL_CALL: {{"action":"<name>","params":{{...}}}}
- Write DONE only when finished.
- ONE TOOL_CALL per turn. No prose. Just TOOL_CALL or DONE.

INSTALLATION RECOVERY — follow this order automatically, never ask the owner which to use:
  1. Try apt first. If it fails with "unable to locate" or "no release file" → move on immediately.
  2. Try flatpak: run_shell {{"cmd":"flatpak install -y flathub <app-id>"}}
     Check available: run_shell {{"cmd":"flatpak search <name>"}}
  3. Try snap: run_shell {{"cmd":"sudo snap install <name>"}}
  4. Download AppImage directly with wget/curl.
  Never give up after a single method fails. Never run ls as a recovery step.
  Never tell the owner to install something manually — you do it.
"""


# ── Jarvis loop ───────────────────────────────────────────────────────────────

def _run_jarvis_loop(user_text: str, actions, llm_client, soul: str,
                     history: list, consent_fn) -> list:
    """consent_fn(what, impact) -> bool — called for Lane 2 actions."""
    transcript = []
    denied_actions = set()
    seen_commands = {}  # cmd -> count, to detect infinite repeat loops

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
                                "No other text. TOOL_CALL must come first on its own line. "
                                "If a tool fails, try the next alternative immediately — "
                                "never run ls, never give up, never ask the owner what to do. "
                                "the owner is not technical; you figure out the path forward. "
                                "For USB device discovery use: lsusb (not ls /dev). "
                                "If you already ran a command and got output, do NOT run it again — use the result you have."},
                    {"role": "user", "content": convo},
                ],
                stream=False, think=False,
                options={"temperature": 0.15, "num_predict": 512},
            )
            text = (resp.message.content or "").strip()
        except Exception as e:
            transcript.append(("error", {}, f"LLM error: {e}", False))
            break

        call = _parse_tool_call(text)

        if call is None:
            empty_count += 1
            if empty_count == 1 and text and "DONE" not in text.upper():
                loop_history.append(
                    "PARSE_ERROR: No TOOL_CALL found. "
                    "Do NOT use <run_command> or XML tags — that format is wrong. "
                    "Emit exactly one line: TOOL_CALL: {\"action\":\"run_shell\",\"params\":{\"cmd\":\"<command>\",\"reason\":\"<why>\"}} "
                    "or write the single word DONE."
                )
                continue
            break

        action = call["action"]
        params = dict(call.get("params", {}))
        params.pop("plain_english", None)

        deny_key = (action, params.get("cmd", params.get("path", ""))[:60])
        if deny_key in denied_actions:
            loop_history.append(
                f"SKIP: {action} with similar params was already denied. Try different approach or DONE."
            )
            continue

        # Detect repeat loops — same command 3+ times means the model is stuck
        cmd_key = params.get("cmd", params.get("path", params.get("query", "")))[:80]
        seen_commands[cmd_key] = seen_commands.get(cmd_key, 0) + 1
        if seen_commands[cmd_key] >= 3:
            loop_history.append(
                f"LOOP DETECTED: you have run {cmd_key!r} {seen_commands[cmd_key]} times. "
                "You already have the result. Do NOT run it again. "
                "Use the result you have, try a completely different command, or write DONE."
            )
            continue

        lane = _get_lane(action, params)

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

        # Lane 2 — ask via GUI dialog
        what   = _infer_what(action, call.get("params", {}))
        impact = _infer_impact(action, params)
        approved = consent_fn(what, impact)

        if not approved:
            denied_actions.add(deny_key)
            transcript.append((action, params, "DENIED by user", False))
            loop_history.append(
                f"TOOL_CALL: {json.dumps({'action': action, 'params': params})}\n"
                f"RESULT: User said no. Try a different method or write DONE."
            )
            empty_count = 0
            continue

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
            if ok is False and out == "DENIED by user":
                lines.append(f"  ✗ {label} — user said no")
            else:
                lines.append(f"  {mark} {label}")
                lines.append(f"     → {out[:400]}")
        lines.append("]")
        lines.append("")
        lines.append("Report results directly. If ✓ ran, say what you found. "
                     "If ✗ denied, acknowledge it. Never say 'waiting for approval'.\n"
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
            reply = re.sub(r'\[WHAT HAPPENED THIS TURN.*?\]\s*', '', reply, flags=re.DOTALL).strip()
            reply = re.sub(r'\[\d{4}-\d{2}-\d{2}.*?##.*?\n.*?\n.*?\n', '', reply, flags=re.DOTALL).strip()
            reply = re.sub(r'<run_command>.*?</run_command>', '', reply, flags=re.DOTALL).strip()
            reply = re.sub(r'<run_command>.*', '', reply, flags=re.DOTALL).strip()
            if reply:
                return reply
            messages.append({"role": "assistant", "content": ""})
            messages.append({"role": "user", "content": "Please give a short direct answer."})
        except Exception as e:
            return f"[reply error: {e}]"

    return "(no response)"


# ── GUI ────────────────────────────────────────────────────────────────────────

class MaezApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Maez")
        self.root.geometry("900x650")
        self.root.configure(bg="#1e1e2e")

        self.soul    = _load_soul()
        self.history = []
        self.busy    = False

        try:
            from core.action_engine import ActionEngine
            self.actions = ActionEngine()
        except Exception:
            self.actions = None

        try:
            from memory.memory_manager import MemoryManager
            self.memory = MemoryManager()
        except Exception:
            self.memory = None

        try:
            from core import llm_client
            self.llm = llm_client
        except Exception as e:
            messagebox.showerror("Startup", f"llm_client unavailable: {e}")
            sys.exit(1)

        self._build_ui()
        self._append("system", "Maez is online. Ask me anything.")

    def _build_ui(self):
        # ── Fonts ──────────────────────────────────────────────────────────
        mono  = tkfont.Font(family="JetBrains Mono", size=11)
        sans  = tkfont.Font(family="Ubuntu", size=11)
        small = tkfont.Font(family="Ubuntu", size=9)

        # ── Chat area ──────────────────────────────────────────────────────
        self.chat = scrolledtext.ScrolledText(
            self.root,
            bg="#1e1e2e", fg="#cdd6f4",
            insertbackground="#cdd6f4",
            font=mono,
            wrap=tk.WORD,
            state=tk.DISABLED,
            borderwidth=0,
            padx=12, pady=8,
        )
        self.chat.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Text tags for coloring
        self.chat.tag_config("you",    foreground="#89dceb", font=tkfont.Font(family="Ubuntu", size=11, weight="bold"))
        self.chat.tag_config("maez",   foreground="#cdd6f4")
        self.chat.tag_config("system", foreground="#585b70", font=small)
        self.chat.tag_config("tool",   foreground="#a6e3a1", font=tkfont.Font(family="JetBrains Mono", size=10))
        self.chat.tag_config("error",  foreground="#f38ba8")
        self.chat.tag_config("thinking", foreground="#fab387")

        # ── Status bar ─────────────────────────────────────────────────────
        self.status_var = tk.StringVar(value="Ready")
        status = tk.Label(
            self.root,
            textvariable=self.status_var,
            bg="#181825", fg="#585b70",
            font=small, anchor="w", padx=8,
        )
        status.pack(fill=tk.X, side=tk.BOTTOM)

        # ── Input row ─────────────────────────────────────────────────────
        input_frame = tk.Frame(self.root, bg="#181825")
        input_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=0, pady=0)

        self.entry = tk.Text(
            input_frame,
            bg="#313244", fg="#cdd6f4",
            insertbackground="#cdd6f4",
            font=sans,
            height=3,
            wrap=tk.WORD,
            borderwidth=0,
            padx=10, pady=8,
        )
        self.entry.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.entry.bind("<Return>", self._on_return)
        self.entry.bind("<Shift-Return>", lambda e: None)  # allow newline
        self.entry.focus_set()

        send_btn = tk.Button(
            input_frame,
            text="Send",
            command=self._send,
            bg="#89b4fa", fg="#1e1e2e",
            font=tkfont.Font(family="Ubuntu", size=11, weight="bold"),
            relief=tk.FLAT,
            padx=16, pady=0,
            cursor="hand2",
        )
        send_btn.pack(side=tk.RIGHT, fill=tk.Y)

    def _on_return(self, event):
        if not event.state & 0x1:  # Shift not held
            self._send()
            return "break"

    def _append(self, tag: str, text: str):
        """Thread-safe append to chat window."""
        def _do():
            self.chat.config(state=tk.NORMAL)
            if tag == "you":
                self.chat.insert(tk.END, "\nYou\n", "you")
                self.chat.insert(tk.END, text + "\n", "maez")
            elif tag == "maez":
                self.chat.insert(tk.END, "\nMaez\n", "you")
                self.chat.insert(tk.END, text + "\n", "maez")
            elif tag == "tool":
                self.chat.insert(tk.END, text + "\n", "tool")
            elif tag == "error":
                self.chat.insert(tk.END, text + "\n", "error")
            elif tag == "thinking":
                self.chat.insert(tk.END, text + "\n", "thinking")
            else:
                self.chat.insert(tk.END, text + "\n", "system")
            self.chat.config(state=tk.DISABLED)
            self.chat.update_idletasks()
            self.chat.see(tk.END)
        self.root.after(0, _do)

    def _set_status(self, text: str):
        self.root.after(0, lambda: self.status_var.set(text))

    def _consent(self, what: str, impact: str) -> bool:
        """Show consent dialog for Lane 2 actions — runs in worker thread via main thread."""
        result = [False]
        event  = threading.Event()

        def _ask():
            result[0] = messagebox.askyesno(
                "Maez wants to act",
                f"{what}\n\n{impact}\n\nAllow?",
                parent=self.root,
            )
            event.set()

        self.root.after(0, _ask)
        event.wait(timeout=60)
        return result[0]

    def _send(self):
        text = self.entry.get("1.0", tk.END).strip()
        if not text or self.busy:
            return
        self.entry.delete("1.0", tk.END)
        self._append("you", text)
        self.busy = True
        self._set_status("Thinking…")
        threading.Thread(target=self._process, args=(text,), daemon=True).start()

    def _process(self, user_text: str):
        try:
            # Memory recall
            if self.memory:
                try:
                    recalled = self.memory.recall_for_telegram(user_text)
                    mem_block = self.memory.format_for_prompt(recalled)
                    if mem_block:
                        # Prepend memory context to soul for this call
                        soul_with_mem = f"{self.soul}\n\n{mem_block}"
                    else:
                        soul_with_mem = self.soul
                except Exception:
                    soul_with_mem = self.soul
            else:
                soul_with_mem = self.soul

            # Run Jarvis loop
            self._set_status("Running tools…")
            transcript = _run_jarvis_loop(
                user_text, self.actions, self.llm, soul_with_mem,
                self.history, self._consent,
            )

            # Show tool summary in chat
            for action, params, out, ok in transcript:
                label = _infer_what(action, params)
                mark  = "✓" if ok is True else ("✗" if ok is False else "⏳")
                if ok is False and out == "DENIED by user":
                    self._append("tool", f"{mark} {label} — denied")
                else:
                    short = out[:120].replace("\n", " ")
                    self._append("tool", f"{mark} {label} → {short}")

            # Final reply
            self._set_status("Composing reply…")
            reply = _final_reply(user_text, transcript, self.history, self.llm, soul_with_mem)

            # Update conversation history
            self.history.append({"role": "user",      "content": user_text})
            self.history.append({"role": "assistant",  "content": reply})
            if len(self.history) > 20:
                self.history = self.history[-20:]

            # Store in memory
            if self.memory:
                try:
                    # 5x.B Pass 1: bond transcript; mixed-origin (see 5x.D).
                    self.memory.store_telegram(
                        f"the owner asked: {user_text}\nMaez replied: {reply}",
                        provenance_source="user_utterance",
                        trust_tier="lived",
                        origin_surface="gui",
                        chat_id="gui",
                    )
                except Exception:
                    pass

            self._append("maez", reply)
            self._set_status("Ready")

        except Exception as e:
            self._append("error", f"Error: {e}")
            self._set_status("Error")
        finally:
            self.busy = False


def main():
    root = tk.Tk()
    MaezApp(root)  # registers handlers on root
    root.mainloop()


if __name__ == "__main__":
    main()
