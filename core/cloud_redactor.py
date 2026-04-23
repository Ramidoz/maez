"""Phase 3 shim — delegates to core.safety.cloud_redactor.

The real module lives at core/safety/cloud_redactor.py. New code
should import from core.safety directly.
"""
import sys
from core.safety import cloud_redactor as _real
sys.modules[__name__] = _real
