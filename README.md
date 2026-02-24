# sprint-progress

CrewAI manager agent that monitors Jira sprints across multiple teams, forecasts delivery health twice per day, and pings managers on Slack when risk materializes.

## Features
- Pulls sprint + issue metrics from Jira boards
- Computes sprint progress by original estimates and issue status transitions
- Highlights blockers, aging work, and spillover risk
- Publishes per-board Slack updates in Russian with concrete next actions

## Project Structure
```
.
├── .env.example
├── .gitignore
├── README.md
├── config.yaml
├── Makefile
├── requirements.txt
├── run_agent.sh
└── src
    ├── __init__.py
    ├── agents.py
    ├── crew.py
    ├── policies.py
    ├── tasks.py
    └── tools
        ├── jira_client.py
        └── slack_notifier.py
```

## Prerequisites
- Python 3.11+
- Jira API token with read access to the target boards
- Slack bot token with permission to post in the alert channel

## Setup
1. **Install dependencies**
   ```bash
   cd sprint-progress
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Copy environment file**
   ```bash
   cp .env.example .env
   # fill in Slack & Jira details
   ```
3. **Run the agent (foreground)**
   ```bash
   ./run_agent.sh
   ```
   `run_agent.sh` подхватывает `.venv` и `.env` автоматически.

4. **Use Makefile commands (recommended)**
   ```bash
   make help
   ```

## Make Commands
- `make help` — показать все доступные команды
- `make venv` — создать виртуальное окружение `.venv`
- `make install` — установить зависимости из `requirements.txt`
- `make run` — запустить агента в foreground
- `make start` — запустить агента в background, логи в `agent.log`
- `make stop` — остановить background-процесс агента
- `make status` — показать статус процесса агента
- `make logs` — смотреть логи (`tail -f agent.log`)

Starts immediately, then runs at hour slots anchored to `NOTIFY_START_HOUR`
with step `FORECAST_INTERVAL_HOURS` until `NOTIFY_END_HOUR` (exclusive).

## Environment Variables
See `.env.example` for the authoritative list:
- `SLACK_BOT_TOKEN` – Slack bot token (starts with `xoxb-`)
- `SLACK_ALERT_CHANNEL` – channel ID or name
- `JIRA_BASE_URL` – e.g. `https://company.atlassian.net`
- `JIRA_EMAIL` – account email used for the Jira token
- `JIRA_API_TOKEN` – Jira API token
- `JIRA_BOARD_IDS` – comma-separated Agile board IDs to monitor
- `JIRA_BOARD_NAME_MAP` – optional board ID → team name map (e.g. `123:Payments Team,456:Core Team`)
- `SPRINT_LOOKAHEAD_DAYS` – horizon for forecast context (default 7)
- `FORECAST_INTERVAL_HOURS` – step between scheduled runs inside notify window (default 12)
- `QUIET_HOURS_TZ` – timezone for notification window (default `Asia/Ho_Chi_Minh`)
- `NOTIFY_START_HOUR` – first hour when Slack alerts are allowed (default 12)
- `NOTIFY_END_HOUR` – hour when alerts stop, exclusive (default 22)

## Runtime Behavior (high level)
1. Collect metrics for active sprints across configured Jira boards
2. Aggregate progress by original estimates and detect bottleneck statuses
3. Perform issue-level risk exploration (time in work, status aging, estimate pressure)
4. Build a compact manager plan per board
5. Publish one Slack message per board (or short green-status line if all sprints are stable)

## TODOs / Next Steps
- [ ] Connect to actual Jira + Slack credentials
- [ ] Add persistence layer for historical trend charts (optional)
