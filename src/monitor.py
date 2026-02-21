"""Background monitoring + forecasting logic."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, List

from slack_sdk import WebClient


@dataclass
class SprintForecast:
    board_id: int
    sprint_name: str
    completion_probability: float
    velocity_gap: float
    total_issues: int
    remaining_issues: int
    eta_days: float


class SprintMonitor:
    def __init__(self, *, jira, config: dict, slack_client: WebClient) -> None:
        self._jira = jira
        self._config = config
        self._interval = config.get("monitor", {}).get("interval_minutes", 720) * 60
        self._threshold = config.get("monitor", {}).get("alert_threshold", 0.7)
        self._slack_channel = config.get("monitor", {}).get("manager_channel", "#alerts")
        self._slack_client = slack_client
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._stop_event = threading.Event()
        self._subscribers: Dict[str, str] = {}

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)

    # Slack interface -----------------------------------------------------------
    def subscribe(self, user_id: str, channel_id: str) -> None:
        self._subscribers[user_id] = channel_id

    def unsubscribe(self, user_id: str) -> None:
        self._subscribers.pop(user_id, None)

    def last_forecast(self) -> List[SprintForecast]:
        return self._jira.cached_forecasts

    # Core loop -----------------------------------------------------------------
    def _loop(self) -> None:
        while not self._stop_event.is_set():
            forecasts = self._jira.fetch_forecasts()
            self._notify(forecasts)
            self._stop_event.wait(self._interval)

    def _notify(self, forecasts: List[SprintForecast]) -> None:
        alert_lines = []
        for forecast in forecasts:
            probability = forecast.completion_probability
            line = (
                f"Board {forecast.board_id} · {forecast.sprint_name}: "
                f"{probability:.0%} chance to finish, gap {forecast.velocity_gap:+.1f} pts"
            )
            alert_lines.append(line)
        message = "\n".join(alert_lines)
        if not message:
            return

        self._slack_client.chat_postMessage(channel=self._slack_channel, text=message)

        for channel in self._subscribers.values():
            self._slack_client.chat_postMessage(channel=channel, text=message)

        for forecast in forecasts:
            if forecast.completion_probability < self._threshold:
                self._slack_client.chat_postMessage(
                    channel=self._slack_channel,
                    text=(
                        f"⚠️ Спринт '{forecast.sprint_name}' отстаёт: {forecast.completion_probability:.0%} вероятность."
                        f" Осталось {forecast.remaining_issues}/{forecast.total_issues}."
                    ),
                )
