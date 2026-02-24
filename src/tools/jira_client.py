import os
from datetime import datetime, timezone

from pydantic import PrivateAttr
from crewai.tools.base_tool import BaseTool
from jira import JIRA


class JiraSprintMetricsTool(BaseTool):
    name: str = "jira_sprint_metrics"
    description: str = "Collect metrics for active sprints across configured Jira boards."
    _client: JIRA = PrivateAttr()
    _board_ids: list[str] = PrivateAttr(default_factory=list)
    _base_url: str = PrivateAttr(default="")

    def model_post_init(self, __context):
        super().model_post_init(__context)
        base_url = os.getenv("JIRA_BASE_URL")
        email = os.getenv("JIRA_EMAIL")
        api_token = os.getenv("JIRA_API_TOKEN")
        if not all([base_url, email, api_token]):
            raise ValueError("JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN are required.")

        self._client = JIRA(server=base_url, basic_auth=(email, api_token))
        self._base_url = base_url.rstrip("/")
        boards_raw = os.getenv("JIRA_BOARD_IDS", "")
        self._board_ids = [bid.strip() for bid in boards_raw.split(",") if bid.strip()]

    @staticmethod
    def _parse_jira_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            # Jira format example: 2026-02-24T09:12:41.123+0000
            return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z")
        except ValueError:
            return None

    def _extract_status_transitions(self, issue) -> list[dict]:
        transitions: list[dict] = []
        changelog = getattr(issue, "changelog", None)
        if not changelog:
            return transitions

        for history in getattr(changelog, "histories", []):
            changed_at = self._parse_jira_datetime(getattr(history, "created", None))
            for item in getattr(history, "items", []):
                if getattr(item, "field", None) != "status":
                    continue
                transitions.append(
                    {
                        "changed_at": changed_at,
                        "from_status": getattr(item, "fromString", None),
                        "to_status": getattr(item, "toString", None),
                    }
                )
        transitions.sort(key=lambda t: t["changed_at"] or datetime.min.replace(tzinfo=timezone.utc))
        return transitions

    def _issue_original_estimate_seconds(self, issue, subtask_estimates: dict[str, int]) -> tuple[int, bool]:
        issue_original = getattr(issue.fields, "timeoriginalestimate", None)
        if issue_original is not None:
            return int(issue_original), False

        subtask_ids = [getattr(subtask, "id", None) for subtask in getattr(issue.fields, "subtasks", [])]
        subtask_sum = sum(subtask_estimates.get(subtask_id, 0) for subtask_id in subtask_ids if subtask_id)
        return subtask_sum, subtask_sum > 0

    def _to_seconds(self, value: float) -> int:
        return max(int(value), 0)

    def _run(self) -> list[dict]:
        now = datetime.now(timezone.utc)
        metrics = []
        for board_id in self._board_ids:
            board_info = {"board_id": board_id, "sprints": []}
            try:
                sprints = self._client.sprints(board_id, state="active")
                for sprint in sprints:
                    issues = self._client.search_issues(
                        f"Sprint = {sprint.id}",
                        maxResults=False,
                        expand="changelog",
                        fields="summary,status,timeoriginalestimate,subtasks,issuetype,created",
                    )
                    subtask_estimates: dict[str, int] = {}
                    for issue in issues:
                        issue_type = getattr(getattr(issue, "fields", None), "issuetype", None)
                        if not issue_type or not getattr(issue_type, "subtask", False):
                            continue
                        original = getattr(issue.fields, "timeoriginalestimate", None)
                        subtask_estimates[issue.id] = int(original) if original is not None else 0

                    total_original_seconds = 0
                    done_original_seconds = 0
                    in_progress_issues = 0
                    fallback_to_subtasks_count = 0
                    status_bottlenecks: dict[str, dict] = {}
                    issue_snapshots: list[dict] = []

                    for issue in issues:
                        issue_type = getattr(getattr(issue, "fields", None), "issuetype", None)
                        is_subtask = bool(issue_type and getattr(issue_type, "subtask", False))
                        if is_subtask:
                            # Roll up estimate/progress through parent issues to avoid double counting.
                            continue

                        status = getattr(getattr(issue, "fields", None), "status", None)
                        status_name = getattr(status, "name", "Unknown")
                        status_category = getattr(getattr(status, "statusCategory", None), "key", "unknown")
                        transitions = self._extract_status_transitions(issue)

                        current_status_changed_at = transitions[-1]["changed_at"] if transitions else None
                        current_status_duration_seconds = self._to_seconds(
                            (now - current_status_changed_at).total_seconds()
                        ) if current_status_changed_at else 0

                        work_start_at = None
                        for transition in transitions:
                            to_status = transition["to_status"] or ""
                            if to_status.lower() not in {"to do", "open", "backlog", "selected for development"}:
                                work_start_at = transition["changed_at"]
                                break

                        if not work_start_at and status_category == "indeterminate":
                            work_start_at = self._parse_jira_datetime(getattr(issue.fields, "created", None))

                        time_in_work_seconds = self._to_seconds((now - work_start_at).total_seconds()) if work_start_at else 0
                        is_in_progress = status_category == "indeterminate"
                        if is_in_progress:
                            in_progress_issues += 1

                        estimate_seconds, used_subtasks_fallback = self._issue_original_estimate_seconds(
                            issue,
                            subtask_estimates,
                        )
                        if used_subtasks_fallback:
                            fallback_to_subtasks_count += 1

                        total_original_seconds += estimate_seconds
                        if status_category == "done":
                            done_original_seconds += estimate_seconds

                        if status_category != "done":
                            bucket = status_bottlenecks.setdefault(
                                status_name,
                                {"issues": 0, "max_time_in_status_seconds": 0, "avg_time_in_status_seconds": 0},
                            )
                            bucket["issues"] += 1
                            bucket["avg_time_in_status_seconds"] += current_status_duration_seconds
                            bucket["max_time_in_status_seconds"] = max(
                                bucket["max_time_in_status_seconds"],
                                current_status_duration_seconds,
                            )

                        issue_snapshots.append(
                            {
                                "key": issue.key,
                                "summary": getattr(issue.fields, "summary", "") or "",
                                "issue_url": f"{self._base_url}/browse/{issue.key}",
                                "status": status_name,
                                "status_category": status_category,
                                "original_estimate_seconds": estimate_seconds,
                                "used_subtasks_estimate": used_subtasks_fallback,
                                "time_in_work_seconds": time_in_work_seconds,
                                "time_in_current_status_seconds": current_status_duration_seconds,
                            }
                        )

                    for bucket in status_bottlenecks.values():
                        if bucket["issues"] > 0:
                            bucket["avg_time_in_status_seconds"] = int(
                                bucket["avg_time_in_status_seconds"] / bucket["issues"]
                            )

                    stuck_status = None
                    if status_bottlenecks:
                        stuck_status = max(
                            status_bottlenecks.items(),
                            key=lambda item: (
                                item[1]["max_time_in_status_seconds"],
                                item[1]["issues"],
                            ),
                        )[0]

                    board_info["sprints"].append(
                        {
                            "sprint_name": sprint.name,
                            "completed_issues": len(
                                [
                                    i
                                    for i in issues
                                    if not getattr(getattr(i.fields, "issuetype", None), "subtask", False)
                                    and i.fields.status.statusCategory.key == "done"
                                ]
                            ),
                            "total_issues": len(
                                [
                                    i
                                    for i in issues
                                    if not getattr(getattr(i.fields, "issuetype", None), "subtask", False)
                                ]
                            ),
                            "state": sprint.state,
                            "estimate_source": "original_estimate",
                            "total_original_estimate_seconds": total_original_seconds,
                            "done_original_estimate_seconds": done_original_seconds,
                            "completion_by_original_estimate": (
                                round(done_original_seconds / total_original_seconds, 4)
                                if total_original_seconds > 0
                                else None
                            ),
                            "issues_in_progress": in_progress_issues,
                            "issues_with_subtasks_estimate_fallback": fallback_to_subtasks_count,
                            "stuck_status": stuck_status,
                            "status_bottlenecks": status_bottlenecks,
                            "issue_snapshots": issue_snapshots,
                        }
                    )
            except Exception as exc:  # noqa: BLE001 - surface upstream
                board_info["error"] = str(exc)
            metrics.append(board_info)
        return metrics
