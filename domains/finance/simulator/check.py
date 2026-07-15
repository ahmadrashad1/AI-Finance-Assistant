"""Consistency-check CLI: ``python -m domains.finance.simulator.check``.

Asserts every simulator invariant (PRD Ch.11 and Ch.19) against the seeded
database and the expectations file. Exit code 0 only at zero violations.
"""
from __future__ import annotations

import asyncio

from domains.finance.simulator.consistency_check import _main

if __name__ == "__main__":
    asyncio.run(_main())
