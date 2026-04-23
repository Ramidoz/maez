# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""
owner_trust.py — per-user trust policy, consumed by the decision pipeline.

Built 2026-04-20 to invert the "card-first default" that had the owner
arguing with a permit desk for every `systemctl is-active` during live
conversation. Policy per `project_bond_styles_dimension.md` (memory):
Rohit's Maez is "liberal" — high trust, friend-with-keys. Other users
would get tighter defaults by policy, not by code path.

What this module DOES:
  - Classify each user_id into a trust tier.
  - Classify each run_shell command as "clearly risky" or not.
  - Expose `should_run_inline(user_id, action, params)` for the
    decision pipeline to consult when deciding card-vs-inline.

What this module EXPLICITLY DOES NOT DO:
  - Touch the covenant gate. Covenant runs BEFORE lane decision.
  - Touch the audit verdict. Audit runs BEFORE lane decision.
  - Touch the will-I check. Will-I runs BEFORE lane execution.
  - Touch the self-mod dialog. ESCALATE verdicts go to dialog
    regardless of tier.
  - Bypass refusals. REFUSE verdicts refuse on all tiers.

This module is a UX policy layer, not a safety layer. Safety rails
remain exactly where they were.
"""
from __future__ import annotations

import re
from typing import Any, Optional

# ── trust tiers ────────────────────────────────────────────────────────

# Liberal tier: owner-level trust, inline-default for non-risky ops.
# Per `project_bond_styles_dimension.md`. Kept as an explicit allowlist
# so other users don't accidentally inherit this stance.
_LIBERAL_USERS = frozenset({"rohit"})

# Future: _STANDARD_USERS, _RESTRICTED_USERS with tighter defaults.


def trust_tier(user_id: Optional[str]) -> str:
    """Return one of: "liberal" | "standard" | "unknown".

    Unknown is the conservative fallback — anything that doesn't match
    a known tier gets the strictest default (card-first, today's
    behavior)."""
    if not user_id:
        return "unknown"
    if user_id in _LIBERAL_USERS:
        return "liberal"
    # Future tiers land here.
    return "unknown"


# ── risky-command classifier ────────────────────────────────────────────

# Fragments that mark a command as "clearly risky, always warrants a
# card" even for a liberal-trust owner. Conservative on what counts as
# risky — the more items we add here, the more friction returns.
#
# Each entry is a LITERAL substring (case-insensitive match on a padded
# cmd). Regex list is separate below for patterns that need boundaries.
_RISKY_FRAGMENTS: tuple[str, ...] = (
    # Privilege escalation — absolute
    " sudo ", " doas ",
    # Destructive filesystem — any form of rm that's not a bare
    # reference in quoted text (we accept some false positives here).
    "rm -r", "rm -f", "rm -rf", "rm -fr",
    " rm /", " rm ~/",
    " dd if", " mkfs", " fdisk ",
    " truncate ",
    # Permission / ownership changes
    " chmod ", " chown ", " setcap ",
    # Package management
    "apt install", "apt remove", "apt purge", "apt upgrade",
    "apt-get install", "apt-get remove", "apt-get purge", "apt-get upgrade",
    "pip install", "pip uninstall",
    "pipx install", "pipx uninstall",
    "npm install", "npm uninstall", "npm ci",
    "yarn add", "yarn remove",
    "snap install", "snap remove",
    "flatpak install", "flatpak remove",
    " yum ", " dnf ", " pacman ",
    # Systemd WRITE ops (read ops like is-active/status/show/list-units
    # remain safe — they're in approval_sessions' read-safe set).
    "systemctl start", "systemctl stop", "systemctl restart",
    "systemctl enable", "systemctl disable", "systemctl reload",
    "systemctl mask", "systemctl unmask",
    "systemctl daemon-reload",
    # Process kills that can disrupt running services
    " kill -", " killall ", " pkill ",
    # Git writes to remote / history rewrites
    "git push", "git reset --hard", "git clean -f",
    "git rebase -i", "git commit --amend",
    "git branch -D", "git force-push",
    # Network writes (matched case-insensitively via padded.lower())
    "curl -x post", "curl -x put", "curl -x delete", "curl -x patch",
    "curl --data", "curl -d ",
    "wget --post",
    # SSH/SCP to other hosts (scp writes; ssh can run remote cmds)
    "ssh ", " scp ",
    "rsync --delete",
    # Mount / umount
    " mount ", " umount ",
    # Shell substitution / eval — can run anything
    "$(", "`",
    " eval ",
    # Tee writes
    " tee ", " tee\t",
)


# Regex patterns for risk classes that need word/boundary precision.
# Kept separate so the simple substring list above stays scannable.
_RISKY_PATTERNS: tuple[re.Pattern, ...] = (
    # Any redirect writing into /home/rohit/maez/ — self-mod
    re.compile(r">+\s*/?home/rohit/maez/", re.IGNORECASE),
    # Redirect writing anywhere outside /tmp or /dev/null. Conservative
    # on redirects — most Maez-proposed cmds don't redirect; the ones
    # that do want human review. Patterns covered:
    #   > /path  (not /tmp or /dev/null)
    #   >> /path
    # Allowed: > /dev/null (common silencing), > /tmp/..., 2>&1, 2>/dev/null.
    # The trailing \S forces a non-whitespace target — a bare `>` with
    # trailing space on a pipeline wouldn't match spuriously.
    re.compile(
        r"(?<![0-9&])>+\s*(?!/dev/null|/tmp/|&)\S",
        re.IGNORECASE,
    ),
)


def is_risky_cmd(cmd: str) -> bool:
    """True iff `cmd` contains a clearly risky fragment or pattern.
    Conservative on the safe side — when in doubt about a fragment,
    ERR TOWARD calling it risky (card) since a liberal-trust flow is
    still reversible via user correction, but an auto-executed risky
    op may not be."""
    if not cmd or not isinstance(cmd, str):
        # Non-string or empty cmd is a weird input; treat as risky so
        # it's not silently inline-run.
        return True
    s = cmd.strip()
    if not s:
        return True
    # 03-m1: normalize runs of whitespace to a single space before
    # substring matching. Previously `rm  -rf /` (double space) would
    # not match the "rm -rf" fragment and a liberal-tier owner would
    # see it run inline. Literal whitespace in fragments is treated as
    # "at least one space" after this collapse.
    normalized = re.sub(r"\s+", " ", s).lower()
    padded = " " + normalized + " "
    for frag in _RISKY_FRAGMENTS:
        if frag in padded:
            return True
    for pat in _RISKY_PATTERNS:
        if pat.search(s):
            return True
    return False


# ── command-validity pre-check ──────────────────────────────────────────

_SYSTEMCTL_WRITE_VERBS = (
    "start", "stop", "restart", "reload", "enable", "disable",
    "mask", "unmask", "kill",
)

# apt verbs that install/upgrade a named package — where a fabricated
# package name would fail opaquely inside an approved card.
# `remove`/`purge` intentionally excluded: removing a non-installed
# package is a no-op, not a fabrication signal.
_APT_INSTALL_VERBS = ("install",)

# pip/pipx verbs that fetch a named package. uninstall excluded:
# same reasoning as apt remove.
_PIP_INSTALL_VERBS = ("install",)


def _systemd_unit_exists(unit: str) -> bool:
    """True iff a systemd unit file with the given name is known to
    systemctl (via `list-unit-files`). Strips a trailing `.service`
    so both `maez` and `maez.service` are handled.

    For a real unit, `list-unit-files X` prints a non-empty table and
    exits 0. For a fabricated unit, it prints nothing and exits 1.
    Only the "systemctl itself is missing" case should fail-open —
    that's an environment issue, not a grounding signal.
    """
    if not unit:
        return False
    import subprocess
    name = unit.strip()
    if "." not in name:
        name = name + ".service"
    try:
        result = subprocess.run(
            ["systemctl", "list-unit-files", name, "--no-pager",
             "--no-legend"],
            timeout=2.0,
            capture_output=True,
            check=False,
            text=True,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # systemctl binary missing or hung — fail-open so tests and
        # non-systemd environments don't refuse real units.
        return True
    except Exception:
        return True
    # exit=1 with no output → unit doesn't exist.
    if result.returncode != 0:
        return False
    out = (result.stdout or "").strip()
    if not out:
        return False
    first_line = out.splitlines()[0].strip()
    return first_line.startswith(name)


def _apt_package_exists(pkg: str) -> bool:
    """True iff `apt-cache show <pkg>` reports a candidate. Fails open
    if apt-cache is missing or errors for environmental reasons — same
    policy as `_systemd_unit_exists`: we only block when we have a
    clear negative signal, never on ambiguity.
    """
    if not pkg:
        return False
    import subprocess
    name = pkg.strip()
    # apt package names: lowercase letters, digits, . + - ~
    # Reject anything that clearly isn't a package token so we don't
    # spend a subprocess on garbage.
    import re as _re
    if not _re.match(r"^[a-z0-9][a-z0-9\.\+\-~]*$", name):
        return False
    try:
        result = subprocess.run(
            ["apt-cache", "show", "--no-all-versions", name],
            timeout=2.0,
            capture_output=True,
            check=False,
            text=True,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return True
    except Exception:
        return True
    if result.returncode != 0:
        return False
    out = (result.stdout or "").strip()
    return bool(out and "Package:" in out)


def _pip_package_exists(pkg: str) -> bool:
    """True iff PyPI has a record for `pkg`, OR the package is already
    installed locally (authoritative). Network lookup has a 2s timeout
    and fails open — a network outage shouldn't trigger a fabrication
    refusal. Two-stage check:

      1. Locally-installed → True (fast, zero network, certain).
      2. Otherwise GET https://pypi.org/pypi/<pkg>/json (HEAD-equivalent)
         with 2s timeout; 200 → True, 404 → False, other/timeout → True.
    """
    if not pkg:
        return False
    import re as _re
    name = pkg.strip()
    # PyPI names: letters, digits, . _ - (PEP 508).
    if not _re.match(r"^[A-Za-z0-9][A-Za-z0-9._\-]*$", name):
        return False
    # Stage 1: locally installed? `importlib.metadata` is stdlib, fast.
    try:
        from importlib import metadata as _md
        try:
            _md.distribution(name)
            return True
        except _md.PackageNotFoundError:
            pass
        # Try the PyPI-normalized form (pip normalizes _ → -).
        normalized = name.replace("_", "-").lower()
        if normalized != name:
            try:
                _md.distribution(normalized)
                return True
            except _md.PackageNotFoundError:
                pass
    except Exception:
        pass
    # Stage 2: PyPI lookup with short timeout.
    try:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(
            f"https://pypi.org/pypi/{name}/json",
            method="HEAD",
        )
        try:
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return 200 <= resp.status < 300
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False
            return True
        except Exception:
            return True
    except Exception:
        return True


def cmd_validity_error(cmd: str) -> Optional[str]:
    """Return an error string if `cmd` targets a systemd unit that
    doesn't exist, else None. Called from the decision pipeline
    before card creation so fabricated unit names never queue a
    meaningless approval card.

    Scope is deliberately narrow — only `systemctl <write-verb> <unit>`
    shapes get validated. Read verbs (`is-active`, `status`, `show`,
    `list-units`) are fine on non-existent units (they return exit
    codes the caller can reason about) and shouldn't be blocked.

    Observed 2026-04-20: Maez fabricated `maez-llm.service`, proposed
    `systemctl start maez-llm.service`, the card pipeline didn't
    validate, and the execution failed ambiguously with an
    auth-required error that masked the real "unit doesn't exist"
    problem.
    """
    if not cmd or not isinstance(cmd, str):
        return None
    s = cmd.strip().lower()
    import re as _re
    # Split on chain operators to catch each sub-command
    pieces = _re.split(r"&&|\|\||;", s)
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        # Match "systemctl [sudo?] <verb> <unit>"
        m = _re.match(
            r"(?:sudo\s+)?systemctl\s+(\w[\w-]*)\s+(\S+)",
            piece,
        )
        if not m:
            continue
        verb, unit = m.group(1), m.group(2)
        if verb not in _SYSTEMCTL_WRITE_VERBS:
            continue
        # Strip any trailing flag-like tokens from the unit
        unit = unit.split()[0].rstrip(";")
        if not _systemd_unit_exists(unit):
            return (
                f"systemd unit {unit!r} does not exist on this system. "
                f"Refusing `systemctl {verb} {unit}` — the unit name "
                f"is fabricated or misremembered. Check "
                f"`systemctl list-unit-files 'maez*'` for real names."
            )

    # Second pass: apt install / apt-get install <pkg ...>. A fabricated
    # package name like `apt install maez-observability` would otherwise
    # queue a card that fails inside the approved execution.
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        m = _re.match(
            r"(?:sudo\s+)?(apt|apt-get)\s+(?:-[a-z]+\s+)*"
            r"(\w[\w-]*)\s+(.+)$",
            piece,
        )
        if not m:
            continue
        _tool, verb, tail = m.group(1), m.group(2), m.group(3)
        if verb not in _APT_INSTALL_VERBS:
            continue
        # Tokenize tail: package names are the non-flag tokens.
        tokens = [t for t in tail.split() if t and not t.startswith("-")]
        for pkg in tokens:
            # Strip version pins: `pkg=1.2` or `pkg/stable`
            pkg_core = pkg.split("=", 1)[0].split("/", 1)[0]
            if not pkg_core:
                continue
            if not _apt_package_exists(pkg_core):
                return (
                    f"apt package {pkg_core!r} was not found in the apt "
                    f"cache on this system. Refusing `{_tool} {verb} "
                    f"{pkg_core}` — the package name is fabricated or "
                    f"misremembered. Check `apt-cache search <keyword>` "
                    f"for real names."
                )

    # Third pass: pip install / pipx install / pip3 install <pkg ...>.
    # Fabricated pip packages are especially dangerous because pip's
    # error ("No matching distribution found") can look like a
    # transient repo issue and lead to retry loops.
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        m = _re.match(
            r"(?:sudo\s+)?(pip3?|pipx)\s+(?:-[a-z]+\s+)*"
            r"(\w[\w-]*)\s+(.+)$",
            piece,
        )
        if not m:
            continue
        _tool, verb, tail = m.group(1), m.group(2), m.group(3)
        if verb not in _PIP_INSTALL_VERBS:
            continue
        # Tokenize tail: skip flags and flag-args like `-r reqs.txt`,
        # `--index-url ...`. Heuristic: stop collecting once we see a
        # token starting with `-`, skip it + the next if it looks like
        # a value.
        raw_tokens = tail.split()
        tokens: list[str] = []
        i = 0
        while i < len(raw_tokens):
            tok = raw_tokens[i]
            if tok.startswith("-"):
                # flags with inline value `--foo=bar` — just skip
                if "=" in tok:
                    i += 1
                    continue
                # flag consumes next token as value (common ones)
                if tok in ("-r", "--requirement", "-c", "--constraint",
                           "-i", "--index-url", "--extra-index-url",
                           "-e", "--editable", "-t", "--target"):
                    i += 2
                    continue
                # bare flag
                i += 1
                continue
            tokens.append(tok)
            i += 1
        for pkg in tokens:
            # Strip version pins: `pkg==1.2`, `pkg>=1.0`, `pkg[extra]`
            pkg_core = _re.split(r"[=<>!~\[]", pkg, maxsplit=1)[0]
            pkg_core = pkg_core.strip()
            if not pkg_core:
                continue
            # Skip local paths and URLs — they're not PyPI names.
            if "/" in pkg_core or pkg_core.startswith(".") or ":" in pkg_core:
                continue
            if not _pip_package_exists(pkg_core):
                return (
                    f"pip package {pkg_core!r} was not found on PyPI and "
                    f"is not installed locally. Refusing `{_tool} {verb} "
                    f"{pkg_core}` — the package name is fabricated or "
                    f"misremembered. Check https://pypi.org/search/ for "
                    f"real names."
                )

    return None


# ── top-level policy decision ───────────────────────────────────────────

def should_run_inline(
    user_id: Optional[str],
    action: str,
    params: Optional[dict],
) -> tuple[bool, str]:
    """Decide whether an APPROVE-verdicted action should run inline
    (Lane 0) or create a card (Lane 2), for THIS user.

    Returns (should_inline, reason). The reason is a short explanation
    the decision pipeline can log, so the lane choice is auditable.

    Pre-conditions the caller must have already enforced:
      - verdict.decision == APPROVE (REFUSE/ESCALATE go elsewhere)
      - covenant gate passed
      - will-I check not yet run (happens at execution time)

    Current policy (2026-04-20):
      - action != "run_shell":
          return False — other actions have their own lane logic,
          don't interfere.
      - tier == "liberal" AND cmd is not risky:
          return True (inline) — friend-with-keys default.
      - tier == "liberal" AND cmd is risky:
          return False (card) — real risk still gets explicit consent.
      - tier != "liberal":
          return False (card) — existing behavior.
    """
    if action != "run_shell":
        return (False, "not_run_shell")
    tier = trust_tier(user_id)
    if tier != "liberal":
        return (False, f"tier={tier}")
    cmd = ""
    if isinstance(params, dict):
        cmd = str(params.get("cmd") or "")
    if is_risky_cmd(cmd):
        return (False, "risky_command")
    return (True, "liberal_owner_nonrisky")


# ── diagnostic helpers ─────────────────────────────────────────────────

def _diag_classify(cmd: str) -> dict[str, Any]:
    """Introspection helper for tests / debug."""
    return {
        "cmd": cmd,
        "risky": is_risky_cmd(cmd),
    }
