from crewai import Task


def collect_jira_metrics_task(manager_agent, jira_client):
    return Task(
        description=(
            "Collect a high-level snapshot of each active sprint from Jira: "
            "overall progress by original estimate, on-track vs at-risk outlook, "
            "and candidate bottleneck statuses. Stay at summary level."
        ),
        expected_output=(
            "Structured sprint-level summary for Manager decisions (JSON or compact table): "
            "progress, deadline confidence, and suspected stuck statuses."
        ),
        agent=manager_agent,
        tools=[jira_client],
    )


def explore_issue_risks_task(explorer_agent, metrics_task):
    return Task(
        description=(
            "Deep-dive into issue-level execution signals using the collected metrics. "
            "For each risky issue, determine: how long it has already been in work, "
            "how much time budget remains against original estimate, and concrete risks."
        ),
        expected_output=(
            "Explorer report with issue-level risk evidence: time in work, "
            "remaining time budget, and risk factors per issue."
        ),
        agent=explorer_agent,
        context=[metrics_task],
    )


def manager_action_plan_task(manager_agent, metrics_task, explorer_task):
    return Task(
        description=(
            "Consolidate high-level sprint metrics with Explorer findings and produce "
            "a manager-oriented action plan. Focus on: will we hit sprint goals, "
            "where exactly work is stuck, and what actions are needed now.\n\n"
            "Process data iteratively by board in the exact order returned by Jira. "
            "Do not merge all boards into one global plan. Build one compact plan per board."
        ),
        expected_output=(
            "Ordered per-board manager plans (not a single merged report): "
            "on-time confidence, stuck status, current progress, and prioritized actions."
        ),
        agent=manager_agent,
        context=[metrics_task, explorer_task],
    )


def publish_alert_task(manager_agent, slack_notifier, manager_plan_task):
    return Task(
        description=(
            "If any sprint is yellow or red—or trend worsens—publish a concise Slack "
            "update for managers. Include only executive-level signals: sprint progress, "
            "stuck status, and required actions. Reference Explorer only as supporting evidence.\n\n"
            "Board-level iteration is mandatory:\n"
            "1) Send a separate Slack message for each board.\n"
            "2) Follow board order exactly as returned by Jira metrics (first board first).\n"
            "3) Finish sending for current board before moving to the next board.\n"
            "4) Never combine multiple boards into one message.\n\n"
            "Strict Slack format (must follow):\n"
            "1) First line: 'Sprint Health Update | Board <BOARD_ID_OR_NAME>'.\n"
            "2) Then one bullet per sprint of that board in this pattern:\n"
            "   - <SPRINT_NAME> | <RAG> | Progress <DONE_EST>/<TOTAL_EST> (<PERCENT>%) | "
            "Stuck: <STATUS_OR_NONE>\n"
            "3) Then section 'Actions (next 24h):' with max 3 bullets total.\n"
            "4) Do not include issue-level deep details, timestamps, or long explanations.\n"
            "5) Total message length <= 1200 characters.\n"
            "6) If all sprints of the current board are green and stable, send one short line: "
            "'Board <BOARD_ID_OR_NAME>: all monitored sprints are on track.'"
        ),
        expected_output=(
            "Slack delivery log showing one sent executive message per board in order."
        ),
        agent=manager_agent,
        tools=[slack_notifier],
        context=[manager_plan_task],
    )
