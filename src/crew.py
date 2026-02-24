"""Crew wiring for the sprint-progress agent."""

import logging
import os
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from crewai import Crew

from .agents import sprint_explorer_agent, sprint_manager_agent
from .tasks import (
    collect_jira_metrics_task,
    explore_issue_risks_task,
    manager_action_plan_task,
    publish_alert_task,
)
from .tools.jira_client import JiraSprintMetricsTool
from .tools.slack_notifier import SlackNotifierTool


def build_crew():
    jira_tool = JiraSprintMetricsTool()
    slack_tool = SlackNotifierTool()

    manager_agent = sprint_manager_agent(slack_tool)
    explorer_agent = sprint_explorer_agent(jira_tool)

    metrics_task = collect_jira_metrics_task(manager_agent, jira_tool)
    explorer_task = explore_issue_risks_task(explorer_agent, metrics_task)
    manager_plan_task = manager_action_plan_task(manager_agent, metrics_task, explorer_task)

    tasks = [
        metrics_task,
        explorer_task,
        manager_plan_task,
        publish_alert_task(manager_agent, slack_tool, manager_plan_task),
    ]

    return Crew(agents=[manager_agent, explorer_agent], tasks=tasks)


def _extract_output_text(run_output: Any) -> str:
    if isinstance(run_output, str):
        return run_output

    for attr in ("raw", "result", "output", "final_output"):
        value = getattr(run_output, attr, None)
        if isinstance(value, str) and value.strip():
            return value

    rendered = str(run_output)
    return rendered if rendered else ""


def _is_board_green_line(text: str) -> bool:
    return (
        (text.startswith("Board ") and "all monitored sprints are on track." in text)
        or (text.startswith("Доска ") and "все отслеживаемые спринты идут по плану." in text)
        or (text.startswith("Команда ") and "все отслеживаемые спринты идут по плану." in text)
    )


def _extract_board_messages(raw_text: str) -> list[str]:
    lines = raw_text.splitlines()
    messages: list[str] = []
    idx = 0
    board_headers = (
        "Sprint Health Update | Board ",
        "Отчет о здоровье спринтов | Доска ",
        "Отчет о здоровье спринтов | Команда ",
    )

    while idx < len(lines):
        stripped = lines[idx].strip()

        if _is_board_green_line(stripped):
            messages.append(stripped)
            idx += 1
            continue

        if stripped.startswith(board_headers):
            block = [stripped]
            idx += 1
            while idx < len(lines):
                current = lines[idx].rstrip()
                current_stripped = current.strip()
                if current_stripped.startswith(board_headers) or _is_board_green_line(current_stripped):
                    break
                block.append(current)
                idx += 1

            message = "\n".join(block).strip()
            if message:
                messages.append(message)
            continue

        idx += 1

    return messages


def _force_publish_slack_updates(run_output: Any) -> None:
    text_output = _extract_output_text(run_output)
    messages = _extract_board_messages(text_output)

    if not messages:
        logging.warning("No board-level messages found for forced Slack publish.")
        return

    slack_tool = SlackNotifierTool()
    for message in messages:
        result = slack_tool._run(message)
        logging.info("Forced Slack publish result: %s", result)


def run():
    crew = build_crew()
    output = crew.kickoff()
    _force_publish_slack_updates(output)
    return output


def _compute_schedule_hours(
    notify_start_hour: int,
    notify_end_hour: int,
    interval_hours: int,
) -> list[int]:
    if not 0 <= notify_start_hour <= 23:
        raise ValueError("NOTIFY_START_HOUR must be in range 0..23.")
    if not 0 <= notify_end_hour <= 23:
        raise ValueError("NOTIFY_END_HOUR must be in range 0..23.")
    if interval_hours <= 0:
        raise ValueError("FORECAST_INTERVAL_HOURS must be a positive integer.")

    # start == end means full-day scheduling window.
    window_length = (notify_end_hour - notify_start_hour) % 24 or 24
    offsets = range(0, window_length, interval_hours)
    hours = sorted({(notify_start_hour + offset) % 24 for offset in offsets})

    if not hours:
        raise ValueError("No schedule hours computed from current settings.")

    return hours


def _run_with_scheduler():
    interval_hours = int(os.getenv("FORECAST_INTERVAL_HOURS", "12"))
    notify_start_hour = int(os.getenv("NOTIFY_START_HOUR", "12"))
    notify_end_hour = int(os.getenv("NOTIFY_END_HOUR", "22"))
    timezone = ZoneInfo(os.getenv("QUIET_HOURS_TZ", "Asia/Ho_Chi_Minh"))
    schedule_hours = _compute_schedule_hours(
        notify_start_hour=notify_start_hour,
        notify_end_hour=notify_end_hour,
        interval_hours=interval_hours,
    )

    # Run once at startup, then keep a fixed interval cadence.
    run()

    scheduler = BlockingScheduler(timezone=timezone)
    scheduler.add_job(
        run,
        trigger="cron",
        hour=",".join(str(hour) for hour in schedule_hours),
        minute=0,
        second=0,
        max_instances=1,
        coalesce=True,
    )

    logging.info(
        "Scheduler started (%s): immediate run done; daily slots=%s "
        "(start=%02d end=%02d interval=%sh).",
        timezone.key,
        schedule_hours,
        notify_start_hour,
        notify_end_hour,
        interval_hours,
    )
    scheduler.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _run_with_scheduler()
