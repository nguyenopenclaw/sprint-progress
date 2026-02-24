"""Crew wiring for the sprint-progress agent."""

import logging
import os
from datetime import datetime
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


def run():
    crew = build_crew()
    output = crew.kickoff()
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

    # Run once at startup on weekdays only, then keep a fixed interval cadence.
    is_weekday = datetime.now(timezone).weekday() < 5
    if is_weekday:
        run()
    else:
        logging.info("Skipping startup run on weekend (%s).", timezone.key)

    scheduler = BlockingScheduler(timezone=timezone)
    scheduler.add_job(
        run,
        trigger="cron",
        day_of_week="mon-fri",
        hour=",".join(str(hour) for hour in schedule_hours),
        minute=0,
        second=0,
        max_instances=1,
        coalesce=True,
    )

    logging.info(
        "Scheduler started (%s): weekday schedule enabled (Mon-Fri); "
        "daily slots=%s (start=%02d end=%02d interval=%sh).",
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
