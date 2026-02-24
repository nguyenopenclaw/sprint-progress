import os
from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import PrivateAttr
from crewai.tools.base_tool import BaseTool
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackNotifierTool(BaseTool):
    name: str = "slack_notifier"
    description: str = "Send formatted sprint risk updates to Slack channels."
    _client: WebClient = PrivateAttr()
    _channel: str | None = PrivateAttr(default=None)
    _timezone: ZoneInfo = PrivateAttr()
    _notify_start_hour: int = PrivateAttr(default=12)
    _notify_end_hour: int = PrivateAttr(default=22)

    def model_post_init(self, __context):
        super().model_post_init(__context)
        token = os.getenv("SLACK_BOT_TOKEN")
        if not token:
            raise ValueError("SLACK_BOT_TOKEN is required for Slack notifications.")
        self._client = WebClient(token=token)
        self._channel = os.getenv("SLACK_ALERT_CHANNEL")
        self._timezone = ZoneInfo(os.getenv("QUIET_HOURS_TZ", "Asia/Ho_Chi_Minh"))
        self._notify_start_hour = int(os.getenv("NOTIFY_START_HOUR", "12"))
        self._notify_end_hour = int(os.getenv("NOTIFY_END_HOUR", "22"))

    def _is_within_notify_window(self):
        current_hour = datetime.now(self._timezone).hour

        if self._notify_start_hour == self._notify_end_hour:
            return True

        if self._notify_start_hour < self._notify_end_hour:
            return self._notify_start_hour <= current_hour < self._notify_end_hour

        return (
            current_hour >= self._notify_start_hour
            or current_hour < self._notify_end_hour
        )

    def _run(self, message: str) -> str:
        if not self._channel:
            raise ValueError("SLACK_ALERT_CHANNEL is not configured.")
        if not self._is_within_notify_window():
            return (
                "Skipped Slack alert: quiet hours active "
                f"({self._notify_start_hour:02d}:00-{self._notify_end_hour:02d}:00 "
                f"{self._timezone.key})."
            )

        try:
            self._client.chat_postMessage(channel=self._channel, text=message)
            return "Alert sent to Slack."
        except SlackApiError as exc:
            return f"Failed to send Slack alert: {exc.response['error']}"
