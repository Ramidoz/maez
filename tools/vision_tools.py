"""Local vision analysis helpers for owner-provided cached images."""

from __future__ import annotations

import json


def _result(success: bool, analysis: str = "", error: str = "") -> dict:
    return {"success": bool(success), "analysis": analysis, "error": error}


def _emit(result: dict) -> str:
    return json.dumps(result)
