from crewai import Agent


def sprint_progress_agent(slack_notifier):
    """Return the primary manager agent for sprint monitoring."""
    return Agent(
        role="Sprint Progress Steward",
        goal=(
            "Maintain continuous visibility into all monitored sprints and "
            "proactively alert stakeholders when delivery risk increases."
        ),
        backstory=(
            "A calm, metrics-obsessed delivery lead with experience coordinating "
            "multiple squads. Expert at translating Jira signals into clear Slack "
            "updates for managers."
        ),
        tools=[slack_notifier],
        allow_delegation=True,
        verbose=True,
    )
