import os

from pydantic import PrivateAttr
from crewai.tools.base_tool import BaseTool
from jira import JIRA


class JiraSprintMetricsTool(BaseTool):
    name: str = "jira_sprint_metrics"
    description: str = "Collect metrics for active sprints across configured Jira boards."
    _client: JIRA = PrivateAttr()
    _board_ids: list[str] = PrivateAttr(default_factory=list)

    def model_post_init(self, __context):
        super().model_post_init(__context)
        base_url = os.getenv("JIRA_BASE_URL")
        email = os.getenv("JIRA_EMAIL")
        api_token = os.getenv("JIRA_API_TOKEN")
        if not all([base_url, email, api_token]):
            raise ValueError("JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN are required.")

        self._client = JIRA(server=base_url, basic_auth=(email, api_token))
        boards_raw = os.getenv("JIRA_BOARD_IDS", "")
        self._board_ids = [bid.strip() for bid in boards_raw.split(",") if bid.strip()]

    def _run(self) -> list[dict]:
        metrics = []
        for board_id in self._board_ids:
            board_info = {"board_id": board_id, "sprints": []}
            try:
                sprints = self._client.sprints(board_id, state="active")
                for sprint in sprints:
                    issues = self._client.search_issues(
                        f"Sprint = {sprint.id}", maxResults=False
                    )
                    board_info["sprints"].append(
                        {
                            "sprint_name": sprint.name,
                            "completed_issues": len([i for i in issues if i.fields.status.statusCategory.key == "done"]),
                            "total_issues": len(issues),
                            "state": sprint.state,
                        }
                    )
            except Exception as exc:  # noqa: BLE001 - surface upstream
                board_info["error"] = str(exc)
            metrics.append(board_info)
        return metrics
