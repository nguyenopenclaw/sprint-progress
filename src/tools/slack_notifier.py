import os
import time
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from pydantic import PrivateAttr
from crewai.tools.base_tool import BaseTool
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError, SlackRequestError


class SlackNotifierTool(BaseTool):
    name: str = "slack_notifier"
    description: str = "Send formatted sprint risk updates to Slack channels."
    _client: WebClient = PrivateAttr()
    _channel: str | None = PrivateAttr(default=None)
    _timezone: ZoneInfo = PrivateAttr()
    _notify_start_hour: int = PrivateAttr(default=12)
    _notify_end_hour: int = PrivateAttr(default=22)
    _retry_count: int = PrivateAttr(default=2)
    _retry_backoff_seconds: float = PrivateAttr(default=1.0)
    _dedupe_window_seconds: int = PrivateAttr(default=300)
    _recent_message_ids: dict[str, float] = PrivateAttr(default_factory=dict)

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
        self._retry_count = int(os.getenv("SLACK_SEND_RETRIES", "2"))
        self._retry_backoff_seconds = float(os.getenv("SLACK_RETRY_BACKOFF_SECONDS", "1.0"))
        self._dedupe_window_seconds = int(os.getenv("SLACK_DEDUPE_WINDOW_SECONDS", "300"))

    def _message_id(self, message: str) -> str:
        normalized = " ".join(message.split())
        source = f"{self._channel}:{normalized}"
        return str(uuid5(NAMESPACE_URL, source))

    def _prune_recent_ids(self, now_ts: float):
        expired_ids = [
            message_id
            for message_id, sent_at in self._recent_message_ids.items()
            if now_ts - sent_at > self._dedupe_window_seconds
        ]
        for message_id in expired_ids:
            self._recent_message_ids.pop(message_id, None)

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

        now_ts = time.time()
        self._prune_recent_ids(now_ts)
        message_id = self._message_id(message)

        if message_id in self._recent_message_ids:
            return "Skipped duplicate Slack alert."

        transient_errors = {
            "ratelimited",
            "internal_error",
            "fatal_error",
            "service_unavailable",
            "request_timeout",
            "timeout",
        }

        retries = max(0, self._retry_count)
        for attempt in range(retries + 1):
            try:
                self._client.chat_postMessage(
                    channel=self._channel,
                    text=message,
                    client_msg_id=message_id,
                )
                self._recent_message_ids[message_id] = time.time()
                return "Alert sent to Slack."
            except SlackApiError as exc:
                error = exc.response.get("error", "unknown_error")
                if error == "duplicate_message":
                    self._recent_message_ids[message_id] = time.time()
                    return "Alert already delivered (deduplicated)."
                if error in transient_errors and attempt < retries:
                    backoff = self._retry_backoff_seconds * (attempt + 1)
                    time.sleep(backoff)
                    continue
                return f"Failed to send Slack alert: {error}"
            except SlackRequestError as exc:
                if attempt < retries:
                    backoff = self._retry_backoff_seconds * (attempt + 1)
                    time.sleep(backoff)
                    continue
                return f"Failed to send Slack alert: {exc}"
