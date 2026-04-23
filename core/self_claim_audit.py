"""Phase 3 shim — delegates to core.safety.self_claim_audit.

The real module lives at core/safety/self_claim_audit.py. Pre-Phase-3
imports (`from core.self_claim_audit import ...`,
`patch("core.self_claim_audit._find_flags")`, etc.) continue to work
because this shim replaces itself with the real module in sys.modules.
New code should import from core.safety directly.
"""
import sys
from core.safety import self_claim_audit as _real
sys.modules[__name__] = _real
