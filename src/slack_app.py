"""Slack Bolt wiring for sprint-progress."""
from __future__ import annotations

from typing import Any, Dict

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler


def build_slack_handler(
    *,
    bot_token: str,
    app_token: str,
    signing_secret: str,
    monitor,
    config: Dict[str, Any],
) -> SocketModeHandler:
    app = App(token=bot_token, signing_secret=signing_secret)

    @app.event("app_mention")
    def handle_mentions(body, event, say):  # type: ignore[override]
        text = (event.get("text") or "").lower()
        channel = event.get("channel")
        user = event.get("user")
        if "forecast" in text or "status" in text:
            forecasts = monitor.last_forecast()
            if not forecasts:
                forecasts = monitor._jira.fetch_forecasts()
            say(_format_forecasts(forecasts))
            return
        if "subscribe" in text:
            monitor.subscribe(user, channel)
            say("Подписал на обновления каждые полдня.")
            return
        if "unsubscribe" in text:
            monitor.unsubscribe(user)
            say("Убрал из списка рассылки.")
            return
        say("Команды: forecast, subscribe, unsubscribe.")

    @app.command("/sprint-progress")
    def slash_progress(ack, body, respond):  # type: ignore[override]
        ack()
        forecasts = monitor._jira.fetch_forecasts()
        respond(_format_forecasts(forecasts))

    return SocketModeHandler(app, app_token)


def _format_forecasts(forecasts) -> str:
    if not forecasts:
        return "Нет активных спринтов."
    lines = ["*Прогноз завершения спринтов*:"]
    for forecast in forecasts:
        lines.append(
            f"• Board {forecast.board_id} · {forecast.sprint_name}: {forecast.completion_probability:.0%} вероятности, "
            f"ETA {forecast.eta_days:.1f}d, осталось {forecast.remaining_issues}/{forecast.total_issues}."
        )
    return "\n".join(lines)
