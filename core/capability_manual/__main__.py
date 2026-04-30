# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""``python -m core.capability_manual`` entry — delegates to
``core.infra.capability_manual_cli.main``."""
from core.infra.capability_manual_cli import main

raise SystemExit(main())
