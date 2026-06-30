"""Put the Jetson edge package on sys.path for host-side unit tests.

The package lives at devices/jetson_presence/jetson_presence/ so the Jetson can
deploy + run `python -m jetson_presence.run`. Host tests import it the same way.
"""

import os
import sys

_PKG_PARENT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "devices", "jetson_presence")
)
if _PKG_PARENT not in sys.path:
    sys.path.insert(0, _PKG_PARENT)
