"""Crew wiring for the sprint-progress agent."""

import logging
import os

from apscheduler.schedulers.blocking import BlockingScheduler
from crewai import Crew

from .agents import sprint_progress_agent
from .tasks import collect_jira_metrics_task, forecast_delivery_task, publish_alert_task
from .tools.jira_client import JiraSprintMetricsTool
from .tools.slack_notifier import SlackNotifierTool


def build_crew():
    jira_tool = JiraSprintMetricsTool()
    slack_tool = SlackNotifierTool()

    agent = sprint_progress_agent(slack_tool)

    tasks = [
        collect_jira_metrics_task(agent, jira_tool),
        forecast_delivery_task(agent),
        publish_alert_task(agent, slack_tool),
    ]

    return Crew(agents=[agent], tasks=tasks)


def run():
    crew = build_crew()
    return crew.kickoff()


def _run_with_scheduler():
    interval_hours = int(os.getenv("FORECAST_INTERVAL_HOURS", "12"))

    # Run once at startup, then keep a fixed interval cadence.
    run()

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run,
        trigger="interval",
        hours=interval_hours,
        max_instances=1,
        coalesce=True,
    )

    logging.info("Scheduler started: running every %s hour(s).", interval_hours)
    scheduler.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _run_with_scheduler()
