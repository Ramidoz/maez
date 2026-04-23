"""Phase 3 shim — delegates to core.memory.identity_ledger."""
import sys
from core.memory import identity_ledger as _real
sys.modules[__name__] = _real
