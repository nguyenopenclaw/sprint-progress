from crewai import Agent


def sprint_manager_agent(slack_notifier):
    """High-level manager focused on sprint-level decisions."""
    return Agent(
        role="Sprint Delivery Manager",
        goal=(
            "Track whether sprint scope can be delivered on time, identify where "
            "work is stuck, and drive an action plan without deep ticket-level analysis."
        ),
        backstory=(
            "A delivery manager who operates at planning altitude: cares about "
            "timeline confidence, bottlenecks, and overall sprint progress. "
            "Delegates deep issue-level investigation to an Explorer specialist."
        ),
        tools=[slack_notifier],
        allow_delegation=True,
        verbose=True,
    )


def sprint_explorer_agent(jira_client):
    """Issue-level analyst focused on execution risks."""
    return Agent(
        role="Sprint Explorer",
        goal=(
            "Investigate issue-level execution details: how long work has been in "
            "progress, remaining time budget against estimates, and delivery risks."
        ),
        backstory=(
            "A detail-oriented delivery analyst who reads Jira histories and uncovers "
            "risk signals hidden in status transitions and estimate structure."
        ),
        tools=[jira_client],
        allow_delegation=False,
        verbose=True,
    )
