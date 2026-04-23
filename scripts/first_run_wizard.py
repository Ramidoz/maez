#!/usr/bin/env python3
"""first_run_wizard.py — interactive setup for a fresh Maez install.

Run once, after `scripts/install.sh` has seeded the config directory.
The wizard walks through three sections:

  1. Owner identity  — what Maez should call you, optional git/telegram IDs
  2. Policies        — jarvis_tier, signal_ingest, proactive_messages
  3. Starting state  — confirms soul.local.md is empty and ready

All answers land in config/identity.yaml. Re-running this is safe:
existing values are shown as defaults, and Enter keeps them. Nothing
overwrites a soul.local.md that already has content.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed in this venv. Run scripts/install.sh first.",
          file=sys.stderr)
    sys.exit(1)

# Resolve repo root from this script's location so the wizard works
# regardless of cwd at invocation time.
REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"
IDENTITY_FILE = CONFIG_DIR / "identity.yaml"
IDENTITY_TEMPLATE = CONFIG_DIR / "identity.template.yaml"
SOUL_LOCAL = CONFIG_DIR / "soul.local.md"
SOUL_LOCAL_TEMPLATE = CONFIG_DIR / "soul.local.template.md"


# ── tiny coloured output helpers ──────────────────────────────────────
def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m"


def section(title: str) -> None:
    print()
    print(_c("1", f"── {title} " + "─" * (60 - len(title))))
    print()


def ok(s: str) -> None:
    print(f"  {_c('32', '[ok]')} {s}")


def warn(s: str) -> None:
    print(f"  {_c('33', '[warn]')} {s}")


def info(s: str) -> None:
    print(f"  [..] {s}")


# ── prompt primitive ──────────────────────────────────────────────────
def ask(prompt: str, default: str = "", allow_empty: bool = True) -> str:
    """Ask the user for a value. Enter keeps the default."""
    shown = f" [{default}]" if default else ""
    while True:
        got = input(f"  {prompt}{shown}: ").strip()
        if got:
            return got
        if default:
            return default
        if allow_empty:
            return ""
        print("    (required)")


def ask_bool(prompt: str, default: bool) -> bool:
    d = "Y/n" if default else "y/N"
    while True:
        got = input(f"  {prompt} [{d}]: ").strip().lower()
        if not got:
            return default
        if got in ("y", "yes"):
            return True
        if got in ("n", "no"):
            return False
        print("    (y or n)")


# ── identity read/write ───────────────────────────────────────────────
def load_identity() -> dict:
    """Read identity.yaml if it exists, else the template, else defaults."""
    for path in (IDENTITY_FILE, IDENTITY_TEMPLATE):
        if path.exists():
            try:
                with path.open() as f:
                    data = yaml.safe_load(f) or {}
                if isinstance(data, dict):
                    return data
            except Exception as e:
                warn(f"failed to read {path}: {e}")
    return {"owner": {}, "policies": {}}


def save_identity(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with IDENTITY_FILE.open("w") as f:
        f.write(
            "# Personal identity file. This file is GITIGNORED.\n"
            "# Regenerated / edited by scripts/first_run_wizard.py.\n"
            "# You can re-run the wizard any time to update these values,\n"
            "# or edit this file by hand.\n\n"
        )
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)
    try:
        IDENTITY_FILE.chmod(0o600)
    except OSError:
        pass
    ok(f"wrote {IDENTITY_FILE}")


# ── sections ──────────────────────────────────────────────────────────
def wizard_owner(data: dict) -> None:
    section("1. Owner identity")
    owner = data.setdefault("owner", {})

    print("  How should Maez refer to you?")
    owner["display_name"] = ask("Display name", owner.get("display_name", "Friend"))

    print()
    print("  Stable identifier for this owner across sessions. Rarely matters;")
    print("  keep the default unless you run multiple Maez installs on one box.")
    owner["user_id"] = ask("User id", owner.get("user_id", "owner"))

    print()
    print("  Where do you mostly live? Used as a weather / time-zone fallback")
    print("  when the iPhone surface hasn't pulsed a recent location.")
    owner["home_place"] = ask("Home place", owner.get("home_place", "Somewhere"))
    try:
        lat_str = ask("Home latitude (decimal, 0 for skip)",
                      str(owner.get("home_lat", 0.0)))
        owner["home_lat"] = float(lat_str)
    except ValueError:
        owner["home_lat"] = 0.0
    try:
        lon_str = ask("Home longitude (decimal, 0 for skip)",
                      str(owner.get("home_lon", 0.0)))
        owner["home_lon"] = float(lon_str)
    except ValueError:
        owner["home_lon"] = 0.0
    owner["timezone"] = ask("Timezone (IANA, e.g. America/Chicago)",
                             owner.get("timezone", "UTC"))

    print()
    print("  Optional — leave blank to opt out of each.")
    owner["git_handle"] = ask("GitHub/GitLab handle (optional)",
                                owner.get("git_handle", ""))
    owner["telegram_user_id"] = ask(
        "Telegram user id (numeric, for the push surface)",
        owner.get("telegram_user_id", ""),
    )
    owner["machine_profile"] = ask(
        "Machine profile (short description, cosmetic only)",
        owner.get("machine_profile", ""),
    )


def wizard_policies(data: dict) -> None:
    section("2. Policies")
    p = data.setdefault("policies", {})

    print("  These shape what Maez is allowed to do. Start conservative;")
    print("  every knob can be flipped later by re-running this wizard.")
    print()
    p["jarvis_tier"] = ask_bool(
        "Allow routing hard tasks to an external API (Claude / OpenAI)?",
        bool(p.get("jarvis_tier", False)),
    )
    p["signal_ingest"] = ask_bool(
        "Accept iPhone ambient signals via POST /api/iphone/ingest?",
        bool(p.get("signal_ingest", False)),
    )
    p["proactive_messages"] = ask_bool(
        "Allow Maez to send unprompted messages when something seems worth saying?",
        bool(p.get("proactive_messages", True)),
    )


def wizard_soul(data: dict) -> None:
    section("3. Starting state")

    if SOUL_LOCAL.exists():
        existing = SOUL_LOCAL.read_text(errors="replace").strip()
        if existing:
            ok("soul.local.md already exists and has content — left as-is.")
            return
        # File exists but is empty — proceed to seed.

    if SOUL_LOCAL_TEMPLATE.exists():
        # Seed with an empty body (the template itself is a doc-only file;
        # dream applies + self-analysis will populate soul.local.md
        # naturally over time).
        SOUL_LOCAL.write_text("")
        ok(f"created empty {SOUL_LOCAL.name} "
           f"(see {SOUL_LOCAL_TEMPLATE.name} for what will accumulate here)")
    else:
        warn(f"{SOUL_LOCAL_TEMPLATE} missing; skipping soul seed.")


# ── entry point ───────────────────────────────────────────────────────
def main() -> int:
    print()
    print(_c("1", "  Maez — first-run wizard"))
    print("  This walks you through the per-user values Maez needs.")
    print("  Re-run any time to update; nothing you already filled in is lost.")

    data = load_identity()
    wizard_owner(data)
    wizard_policies(data)
    wizard_soul(data)

    section("Saving")
    save_identity(data)

    print()
    print(_c("1", "  All set."))
    print("  You can edit config/identity.yaml by hand any time,")
    print("  or re-run this wizard: python3 scripts/first_run_wizard.py")
    print()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print("\n  (cancelled)")
        sys.exit(1)
