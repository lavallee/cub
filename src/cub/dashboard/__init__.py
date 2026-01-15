"""
Dashboard rendering for cub using Rich.

Provides real-time visual monitoring of cub run sessions via terminal UI.
"""

from cub.dashboard.renderer import DashboardRenderer
from cub.dashboard.status import StatusWatcher

__all__ = ["DashboardRenderer", "StatusWatcher"]
