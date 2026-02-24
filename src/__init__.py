"""Sprint Progress CrewAI package."""

import sys


def _ensure_supported_sqlite() -> None:
    """Use pysqlite3 as fallback when stdlib sqlite is too old for Chroma."""
    try:
        import sqlite3

        version_tuple = tuple(int(part) for part in sqlite3.sqlite_version.split("."))
        if version_tuple >= (3, 35, 0):
            return
    except Exception:
        # If sqlite inspection fails, try fallback module below.
        pass

    try:
        import pysqlite3 as sqlite3  # type: ignore[import-not-found]
    except Exception:
        return

    sys.modules["sqlite3"] = sqlite3


_ensure_supported_sqlite()

from .agents import sprint_explorer_agent, sprint_manager_agent  # noqa: F401
from .tasks import (
    collect_jira_metrics_task,
    explore_issue_risks_task,
    manager_action_plan_task,
    publish_alert_task,
)  # noqa: F401
