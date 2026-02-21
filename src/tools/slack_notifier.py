import os
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

    def run(self, message: str):
        if not self.channel:
            raise ValueError("SLACK_ALERT_CHANNEL is not configured.")

        try:
            self.client.chat_postMessage(channel=self.channel, text=message)
            return "Alert sent to Slack."
        except SlackApiError as exc:
            return f"Failed to send Slack alert: {exc.response['error']}"
