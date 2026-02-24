"""Crew wiring for the sprint-progress agent."""

import logging
import os
from typing import Any

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
    return text.startswith("Board ") and "all monitored sprints are on track." in text


def _extract_board_messages(raw_text: str) -> list[str]:
    lines = raw_text.splitlines()
    messages: list[str] = []
    idx = 0

    while idx < len(lines):
        stripped = lines[idx].strip()

        if _is_board_green_line(stripped):
            messages.append(stripped)
            idx += 1
            continue

        if stripped.startswith("Sprint Health Update | Board "):
            block = [stripped]
            idx += 1
            while idx < len(lines):
                current = lines[idx].rstrip()
                current_stripped = current.strip()
                if current_stripped.startswith(
                    "Sprint Health Update | Board "
                ) or _is_board_green_line(current_stripped):
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
