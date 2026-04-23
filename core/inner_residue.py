"""Phase 3 shim — delegates to core.learning.inner_residue."""
import sys
from core.learning import inner_residue as _real
sys.modules[__name__] = _real
