"""Jira API helpers plus forecasting heuristics."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import List, Sequence

from jira import JIRA

from .monitor import SprintForecast


@dataclass
class IssueSample:
    key: str
    status: str
    remaining_estimate: float


class JiraClient:
    def __init__(self, *, server_url: str, email: str, api_token: str, board_ids: Sequence[int]) -> None:
        self._client = JIRA(server=server_url, basic_auth=(email, api_token))
        self._board_ids = list(board_ids)
        self.cached_forecasts: List[SprintForecast] = []

    def fetch_forecasts(self) -> List[SprintForecast]:
        forecasts: List[SprintForecast] = []
        for board_id in self._board_ids:
            sprint = self._active_sprint(board_id)
            if not sprint:
                continue
            issues = self._issues_for_sprint(board_id, sprint.id)
            forecast = self._forecast(board_id, sprint.name, issues, sprint)
            forecasts.append(forecast)
        self.cached_forecasts = forecasts
        return forecasts

    # Helpers ------------------------------------------------------------------
    def _active_sprint(self, board_id: int):
        sprints = self._client.sprints(board_id, state="active")
        return sprints[0] if sprints else None

    def _issues_for_sprint(self, board_id: int, sprint_id: int) -> List[IssueSample]:
        jql = f"sprint = {sprint_id} AND board = {board_id}"
        search = self._client.search_issues(jql, maxResults=500)
        issues: List[IssueSample] = []
        for issue in search:
            status = issue.fields.status.name.lower()
            remaining = getattr(issue.fields, "timeestimate", None) or 0
            issues.append(IssueSample(key=issue.key, status=status, remaining_estimate=remaining / 3600))
        return issues

    def _forecast(self, board_id: int, sprint_name: str, issues: List[IssueSample], sprint) -> SprintForecast:
        total = len(issues)
        done = len([issue for issue in issues if "done" in issue.status])
        remaining = total - done
        remaining_hours = sum(issue.remaining_estimate for issue in issues if issue.status not in {"done", "closed"})

        start_date = getattr(sprint, "startDate", None)
        end_date = getattr(sprint, "endDate", None)
        today = dt.datetime.utcnow()
        if start_date and end_date:
            start = dt.datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            end = dt.datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            elapsed = max((today - start).total_seconds(), 1)
            total_span = (end - start).total_seconds()
            burn = done / max(elapsed / total_span, 0.01)
            completion_probability = min(1.0, burn)
            time_left_days = (end - today).total_seconds() / 86400
        else:
            completion_probability = 0.5
            time_left_days = 2

        velocity_gap = done - (total * (1 - (time_left_days / max((time_left_days + 1), 1))))

        return SprintForecast(
            board_id=board_id,
            sprint_name=sprint_name,
            completion_probability=max(0.0, min(1.0, completion_probability)),
            velocity_gap=velocity_gap,
            total_issues=total,
            remaining_issues=remaining,
            eta_days=max(0, time_left_days),
        )
