"""
Parsers for converting source data into DashboardEntity objects.

Each parser handles a specific data source:
- SpecParser: Specs from specs/**/*.md
- PlanParser: Plans from plans//*/plan.jsonl
- TaskParser: Tasks from beads or JSON backend
- LedgerParser: Ledger entries from .cub/ledger/
- ChangelogParser: Releases from CHANGELOG.md

Parsers follow a common pattern:
1. Read/scan source files
2. Parse content into intermediate representation
3. Convert to DashboardEntity with computed stage
4. Extract relationships (spec_id, plan_id, epic_id)
"""

from cub.core.dashboard.sync.parsers.changelog import ChangelogParser
from cub.core.dashboard.sync.parsers.ledger import LedgerParser
from cub.core.dashboard.sync.parsers.plans import PlanParser
from cub.core.dashboard.sync.parsers.specs import SpecParser
from cub.core.dashboard.sync.parsers.tasks import TaskParser

__all__ = [
    "ChangelogParser",
    "LedgerParser",
    "PlanParser",
    "SpecParser",
    "TaskParser",
]
