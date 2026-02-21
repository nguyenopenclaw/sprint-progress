from crewai import Task


def collect_jira_metrics_task(agent, jira_client):
    return Task(
        description=(
            "Pull the latest sprint data for every configured Jira board, capture "
            "issue states, remaining estimates, blockers, and velocity deltas."
        ),
        expected_output="Structured JSON snapshot of sprint metrics for all teams.",
        agent=agent,
        tools=[jira_client],
    )


def forecast_delivery_task(agent):
    return Task(
        description=(
            "Analyze sprint metrics and forecast the likelihood of closing each sprint "
            "on time. Identify top drivers for risk (scope churn, blockers, low "
            "throughput) and assign a red/yellow/green status."
        ),
        expected_output="Forecast scorecard per sprint with supporting evidence.",
        agent=agent,
    )


def publish_alert_task(agent, slack_notifier):
    return Task(
        description=(
            "If any sprint is yellow or red—or if trend worsens—craft a concise Slack "
            "message outlining risks, blockers, and recommended actions."
        ),
        expected_output="Slack-ready message with summary bullets and owners.",
        agent=agent,
        tools=[slack_notifier],
    )
