"""Entry point for the sprint-progress agent."""
from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .jira_sync import JiraClient
from .monitor import SprintMonitor
from .slack_app import build_slack_handler


def load_config() -> dict:
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    with config_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main() -> None:
    load_dotenv()
    config = load_config()

    slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
    slack_app_token = os.getenv("SLACK_APP_TOKEN")
    slack_signing_secret = os.getenv("SLACK_SIGNING_SECRET")

    jira_url = os.getenv("JIRA_SERVER_URL")
    jira_email = os.getenv("JIRA_EMAIL")
    jira_token = os.getenv("JIRA_API_TOKEN")
    jira_board_ids = os.getenv("JIRA_BOARD_IDS")

    missing = [
        name
        for name, value in [
            ("SLACK_BOT_TOKEN", slack_bot_token),
            ("SLACK_APP_TOKEN", slack_app_token),
            ("SLACK_SIGNING_SECRET", slack_signing_secret),
            ("JIRA_SERVER_URL", jira_url),
            ("JIRA_EMAIL", jira_email),
            ("JIRA_API_TOKEN", jira_token),
            ("JIRA_BOARD_IDS", jira_board_ids),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    board_ids = [int(part.strip()) for part in jira_board_ids.split(",") if part.strip()]

    jira = JiraClient(server_url=jira_url, email=jira_email, api_token=jira_token, board_ids=board_ids)

    from slack_sdk import WebClient  # local import to avoid hard dependency in tests

    slack_client = WebClient(token=slack_bot_token)
    monitor = SprintMonitor(jira=jira, config=config, slack_client=slack_client)

    slack_handler = build_slack_handler(
        bot_token=slack_bot_token,
        app_token=slack_app_token,
        signing_secret=slack_signing_secret,
        monitor=monitor,
        config=config,
    )

    def _shutdown(signum, frame):  # type: ignore[unused-argument]
        monitor.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    monitor.start()
    slack_handler.start()


if __name__ == "__main__":
    main()
