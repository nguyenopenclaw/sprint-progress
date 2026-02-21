"""Crew wiring for the sprint-progress agent."""

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
