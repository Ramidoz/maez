# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Test-only helpers. NOT importable from production code.

Modules here exist to make tests easier to write. They do not import
anything from ``core``, ``daemon``, or ``skills`` — keeping them
production-free means a helper-bug can't bring down the daemon, and
a daemon-refactor can't silently break test infrastructure.
"""
