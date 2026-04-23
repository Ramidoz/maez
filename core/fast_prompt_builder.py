"""Phase 3 shim — delegates to core.infra.fast_prompt_builder."""
import sys
from core.infra import fast_prompt_builder as _real
sys.modules[__name__] = _real
