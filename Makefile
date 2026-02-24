.DEFAULT_GOAL := help

PYTHON ?= python3
VENV_DIR := .venv
PIP := $(VENV_DIR)/bin/pip
RUN_SCRIPT := ./run_agent.sh
PID_FILE := .run_agent.pid
LOG_FILE := agent.log

.PHONY: help venv install run start stop status logs

help:
	@echo "Available targets:"
	@echo "  make venv     - create virtual environment"
	@echo "  make install  - install python dependencies"
	@echo "  make run      - run agent in foreground"
	@echo "  make start    - run agent in background"
	@echo "  make stop     - stop background agent"
	@echo "  make status   - show agent status"
	@echo "  make logs     - tail agent logs"

venv:
	@test -d "$(VENV_DIR)" || $(PYTHON) -m venv "$(VENV_DIR)"

install: venv
	@$(PIP) install -r requirements.txt

run:
	@$(RUN_SCRIPT)

start:
	@if [ ! -f ".env" ]; then \
		echo ".env not found. Create it first (cp .env.example .env)."; \
		exit 1; \
	fi
	@nohup $(RUN_SCRIPT) > "$(LOG_FILE)" 2>&1 &
	@sleep 1
	@if [ -f "$(PID_FILE)" ] && kill -0 "$$(cat "$(PID_FILE)")" 2>/dev/null; then \
		echo "Agent started. PID: $$(cat "$(PID_FILE)")"; \
		echo "Logs: $(LOG_FILE)"; \
	else \
		echo "Start failed. Check $(LOG_FILE)."; \
		exit 1; \
	fi

stop:
	@if [ -f "$(PID_FILE)" ] && kill -0 "$$(cat "$(PID_FILE)")" 2>/dev/null; then \
		pid="$$(cat "$(PID_FILE)")"; \
		kill "$$pid"; \
		rm -f "$(PID_FILE)"; \
		echo "Stopped agent PID $$pid"; \
	else \
		echo "Agent is not running."; \
	fi

status:
	@if [ -f "$(PID_FILE)" ] && kill -0 "$$(cat "$(PID_FILE)")" 2>/dev/null; then \
		echo "Agent is running. PID: $$(cat "$(PID_FILE)")"; \
	else \
		echo "Agent is not running."; \
	fi

logs:
	@touch "$(LOG_FILE)"
	@tail -f "$(LOG_FILE)"
