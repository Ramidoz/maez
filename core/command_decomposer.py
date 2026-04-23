"""Phase 3 shim — delegates to core.actions.command_decomposer."""
import sys
from core.actions import command_decomposer as _real
sys.modules[__name__] = _real
