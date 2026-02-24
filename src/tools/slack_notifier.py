import os
from datetime import datetime
from zoneinfo import ZoneInfo

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackNotifierTool:
    name = "slack_notifier"
    description = "Send formatted sprint risk updates to Slack channels."

    def __init__(self):
        token = os.getenv("SLACK_BOT_TOKEN")
        if not token:
            raise ValueError("SLACK_BOT_TOKEN is required for Slack notifications.")
        self.client = WebClient(token=token)
        self.channel = os.getenv("SLACK_ALERT_CHANNEL")
        self.timezone = ZoneInfo(os.getenv("QUIET_HOURS_TZ", "Asia/Ho_Chi_Minh"))
        self.notify_start_hour = int(os.getenv("NOTIFY_START_HOUR", "12"))
        self.notify_end_hour = int(os.getenv("NOTIFY_END_HOUR", "22"))

    def _is_within_notify_window(self):
        current_hour = datetime.now(self.timezone).hour

        if self.notify_start_hour == self.notify_end_hour:
            return True

        if self.notify_start_hour < self.notify_end_hour:
            return self.notify_start_hour <= current_hour < self.notify_end_hour

        return (
            current_hour >= self.notify_start_hour
            or current_hour < self.notify_end_hour
        )

    def run(self, message: str):
        if not self.channel:
            raise ValueError("SLACK_ALERT_CHANNEL is not configured.")
        if not self._is_within_notify_window():
            return (
                "Skipped Slack alert: quiet hours active "
                f"({self.notify_start_hour:02d}:00-{self.notify_end_hour:02d}:00 "
                f"{self.timezone.key})."
            )

        try:
            self.client.chat_postMessage(channel=self.channel, text=message)
            return "Alert sent to Slack."
        except SlackApiError as exc:
            return f"Failed to send Slack alert: {exc.response['error']}"
