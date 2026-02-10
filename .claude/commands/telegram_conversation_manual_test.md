---
allowed-tools: Bash, Read, Edit, Write, Grep, Glob
description: Start Docker-based manual test - resets prospect, cleans chat, starts containers, sends initial message, listens for responses
model: sonnet
---

# Purpose

This command starts a full Docker-based manual test session for the Telegram sales agent. It resets the conversation between @BetterBohdan (sales agent) and @buddah_lucid (test prospect), starts local Docker containers (postgres + telegram-agent), sends the initial outreach message, and keeps listening for responses. Follow the `Instructions` and `Workflow` sections to execute the test.

## Variables

PROJECT_ROOT: /Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier
COMPOSE_FILE: deployment/docker/docker-compose.yml
MANUAL_TEST_SCRIPT: .claude/skills/testing/scripts/manual_test.py
PROSPECTS_FILE: .claude/skills/telegram/config/prospects.json
TEST_PROSPECT_USERNAME: buddah_lucid
AGENT_USERNAME: BetterBohdan

## Instructions

- This command orchestrates a complete Docker-based manual test of the Telegram sales agent
- The test prospect @buddah_lucid must be reset to "new" status in prospects.json before Docker starts
- The Telegram chat between @BetterBohdan and @buddah_lucid should be cleaned (delete old agent messages)
- Docker containers (postgres + telegram-agent) are started fresh with `down -v` to wipe the database
- The daemon inside Docker reads prospects.json (mounted read-write) and sends the initial outreach message to "new" prospects
- After the initial message is sent, the daemon listens for incoming responses and continues the conversation
- The user interacts as @buddah_lucid via Telegram while watching Docker logs in the terminal
- IMPORTANT: Run the manual_test.py script with `--docker --clean-chat` flags. This handles all reset, cleanup, and Docker orchestration
- IMPORTANT: The script runs `docker compose up` in the foreground so logs stream to the terminal. It blocks until Ctrl+C
- IMPORTANT: Use `uv run` to execute all Python commands per project conventions

## Workflow

1. Verify Docker Desktop is running by executing `docker info --format '{{.ServerVersion}}'` (timeout 10s, fail fast if Docker is down)
2. Stop any existing telegram-agent containers to avoid conflicts: `docker compose -f deployment/docker/docker-compose.yml down -v`
3. Read `PROSPECTS_FILE` to confirm @buddah_lucid exists in the prospect list
4. Run the manual test script with Docker and chat cleanup flags. This single command handles everything:
   ```
   uv run python .claude/skills/testing/scripts/manual_test.py --docker --clean-chat
   ```
   This will:
   - Reset @buddah_lucid to "new" status in prospects.json
   - Delete old agent messages from Telegram chat
   - Run `docker compose down -v` (fresh database)
   - Run `docker compose up --build postgres telegram-agent` (foreground, streams logs)
   - The daemon initializes, finds the "new" prospect, and sends initial outreach message
   - Daemon then listens for incoming messages and responds
5. Monitor the output for these key log lines:
   - `Processing N new prospects...` - daemon found new prospects
   - `Generating initial message for ...` - Claude API call happening
   - `-> Initial message sent to ...` - success, message delivered
   - Any `[red]` errors indicate failures to investigate
6. When the user presses Ctrl+C, the script runs `docker compose down` for cleanup

## Report

- Confirm whether the initial message was successfully sent to @buddah_lucid
- Report any errors seen in Docker logs during initialization or message sending
- If the message was sent, inform the user they can now reply via Telegram as @buddah_lucid and the agent will respond
- If there were errors, summarize what went wrong and suggest fixes
