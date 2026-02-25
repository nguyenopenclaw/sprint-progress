from crewai import Task


def collect_jira_metrics_task(manager_agent, jira_client):
    return Task(
        description=(
            "Collect a high-level snapshot of each active sprint from Jira: "
            "overall progress by original estimate, on-track vs at-risk outlook, "
            "and candidate bottleneck statuses. Stay at summary level. "
            "All analysis notes and outputs must be in Russian."
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
            "how much time budget remains against original estimate, and concrete risks. "
            "For every risky issue include key, issue summary, and direct Jira link from issue_url. "
            "Write the full report in Russian."
        ),
        expected_output=(
            "Explorer report with issue-level risk evidence: time in work, "
            "remaining time budget, risk factors per issue, and a direct Jira URL "
            "plus issue title for each problematic issue."
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
            "Do not merge all boards into one global plan. Build one compact plan per board. "
            "For each board include a short 'Проблемные задачи' section listing risky "
            "issues with key, title, and direct Jira link. "
            "The full action plan must be in Russian."
        ),
        expected_output=(
            "Ordered per-board manager plans (not a single merged report): "
            "on-time confidence, stuck status, current progress, prioritized actions, "
            "and problematic issues with keys, titles, and links."
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
            "Use Russian language for all Slack messages.\n\n"
            "Board-level iteration is mandatory:\n"
            "1) Send a separate Slack message for each board.\n"
            "2) Follow board order exactly as returned by Jira metrics (first board first).\n"
            "3) Finish sending for current board before moving to the next board.\n"
            "4) Never combine multiple boards into one message.\n\n"
            "Strict Slack format (must follow):\n"
            "1) First line: '📊 Отчет о здоровье спринтов | Команда <TEAM_NAME>'.\n"
            "2) Then one bullet per sprint of that board in this pattern:\n"
            "   - <SPRINT_NAME> | <RAG> | Прогресс <DONE_EST>/<TOTAL_EST> (<PERCENT>%) | "
            "Блокер: <STATUS_OR_NONE>\n"
            "3) Then section 'Действия (следующие 24ч):' with max 3 bullets total.\n"
            "   Each bullet must be tied to a concrete issue and strictly follow this format:\n"
            "   - <URL|KEY> — <TITLE>: <CONCRETE_ACTION_OR_REASON>\n"
            "   Use Slack link markup so KEY is clickable (example: <https://.../VALUE-4637|VALUE-4637>).\n"
            "   If reason says the issue is stuck in status, обязательно укажи точную длительность в статусе "
            "(часы/дни), например: 'Задача 18ч в Need Test' / 'Задача 3д 4ч в In Progress' / "
            "'Задача 2д в код-ревью'.\n"
            "4) Do not add a separate 'Проблемные задачи' summary line; issue context must be "
            "embedded directly inside action bullets.\n"
            "5) Do not include issue-level deep details, exact timestamps/dates, or long explanations.\n"
            "6) Total message length <= 1200 characters.\n"
            "7) If all sprints of the current board are green and stable, send one short line: "
            "'✅ Команда <TEAM_NAME>: все отслеживаемые спринты идут по плану.'"
        ),
        expected_output=(
            "Slack delivery log showing one sent executive message per board in order."
        ),
        agent=manager_agent,
        tools=[slack_notifier],
        context=[manager_plan_task],
    )
