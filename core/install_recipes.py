"""Phase 3 shim — delegates to core.infra.install_recipes."""
import sys
from core.infra import install_recipes as _real
sys.modules[__name__] = _real
