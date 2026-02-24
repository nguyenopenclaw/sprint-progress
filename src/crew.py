"""Crew wiring for the sprint-progress agent."""

import logging
import os

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
