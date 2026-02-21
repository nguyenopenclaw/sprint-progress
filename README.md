# sprint-progress

CrewAI manager agent that monitors Jira sprints across multiple teams, forecasts delivery health twice per day, and pings managers on Slack when risk materializes.

## Features
- Pulls sprint + issue metrics from Jira boards
- Forecasts likelihood of closing each sprint using velocity + scope delta
- Highlights blockers, aging work, and spillover risk
- Publishes concise alerts to a Slack channel with recommended actions

## Project Structure
```
.
├── .env.example
├── .gitignore
├── README.md
├── config.yaml
└── src
    ├── agents.py
    ├── policies.py
    ├── tasks.py
    └── tools
        ├── jira_client.py
        └── slack_notifier.py
```

## Prerequisites
- Python 3.11+
- Poetry or pip (your choice)
- Jira API token with read access to the target boards
- Slack bot token with permission to post in the alert channel

## Setup
1. **Install dependencies**
   ```bash
   cd sprint-progress
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt  # or `pip install crewai slack_sdk jira`
   ```
2. **Copy environment file**
   ```bash
   cp .env.example .env
   # fill in Slack & Jira details
   ```
3. **Run the agent**
   ```bash
   export $(grep -v '^#' .env | xargs)  # or use direnv
   python -m crewai run config.yaml
   ```

## Environment Variables
See `.env.example` for full list:
- `SLACK_BOT_TOKEN` – Slack bot token (starts with `xoxb-`)
- `SLACK_ALERT_CHANNEL` – channel ID or name
- `JIRA_BASE_URL` – e.g. `https://company.atlassian.net`
- `JIRA_EMAIL` – account email used for the Jira token
- `JIRA_API_TOKEN` – Jira API token
- `JIRA_BOARD_IDS` – comma-separated Agile board IDs to monitor
- `SPRINT_LOOKAHEAD_DAYS` – horizon for forecast context (default 7)
- `FORECAST_INTERVAL_HOURS` – cadence for re-forecasting (default 12)

## Forecasting Logic (high level)
1. Fetch current sprint issues + completed scope
2. Compute remaining capacity vs historical velocity
3. Score each sprint (green / yellow / red) based on closure likelihood
4. Summarize blockers + recommended mitigations
5. Send Slack alert if the score is yellow/red or trend degrades

## TODOs / Next Steps
- [ ] Connect to actual Jira + Slack credentials
- [ ] Schedule via cron/PM2 for twice-daily execution
- [ ] Add persistence layer for historical trend charts (optional)
