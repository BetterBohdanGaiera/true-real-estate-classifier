# Plan: Update Docker Deployment for Skills-Based Architecture

## Task Description
Update the Docker deployment configuration to support the new skills-based architecture. The current Docker setup references the old `src/sales_agent/daemon.py` path which no longer exists. The code has been migrated to `.claude/skills/telegram/scripts/daemon.py` with a modular, skill-based architecture that requires specific PYTHONPATH configuration and multiple skill directory mounts.

## Objective
Enable local Docker deployment of the Telegram sales agent using the new skills-based architecture, allowing manual testing of the full chat experience via `docker-compose up`.

## Problem Statement
The current Docker configuration is outdated:
1. **Dockerfile** references `src/sales_agent/daemon.py` which doesn't exist
2. **docker-compose.yml** mounts `src/sales_agent/config` which doesn't exist
3. **Health check** imports `from sales_agent.daemon import TelegramDaemon` which fails
4. The new architecture requires:
   - Multiple skill directory mounts (telegram, scheduling, database, humanizer, etc.)
   - Complex PYTHONPATH setup for cross-skill imports
   - Different entry point: `.claude/skills/telegram/scripts/daemon.py`

## Solution Approach
Update the Docker configuration to:
1. Copy all required skills directories into the container
2. Set up correct PYTHONPATH for cross-skill imports
3. Update entry point to the new daemon location
4. Fix volume mounts for config files in the new location
5. Update health check to use new import paths

## Relevant Files

### Files to Modify:
- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/deployment/docker/Dockerfile`
  - Lines: 55-57, 75-84, 94-96, 106-107
  - Update PYTHONPATH, COPY commands, health check, and CMD

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/deployment/docker/docker-compose.yml`
  - Lines: 82-98
  - Update volume mounts to use `.claude/skills/telegram/config/`

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/.claude/skills/testing/scripts/manual_test.py`
  - Lines: 243-247
  - Fix daemon_script path reference

### Reference Files (Read Only):
- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/.claude/skills/telegram/scripts/daemon.py`
  - New daemon entry point with skill imports pattern

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/.claude/skills/telegram/SKILL.md`
  - Documents correct PYTHONPATH and run commands

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/.claude/skills/telegram/config/prospects.json`
  - New config location

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/.claude/skills/telegram/config/agent_config.json`
  - New config location

### Skills Directories Required:
| Skill | Path | Purpose |
|-------|------|---------|
| telegram | `.claude/skills/telegram/` | Main daemon, agent, models |
| scheduling | `.claude/skills/scheduling/` | Follow-up scheduling |
| database | `.claude/skills/database/` | Database init, migrations |
| eleven-labs | `.claude/skills/eleven-labs/` | Voice transcription |
| humanizer | `.claude/skills/humanizer/` | Natural timing |
| zoom | `.claude/skills/zoom/` | Meeting booking |
| register-sales | `.claude/skills/register-sales/` | Calendar integration |
| tone-of-voice | `.claude/skills/tone-of-voice/` | Communication style |
| how-to-communicate | `.claude/skills/how-to-communicate/` | Methodology (BANT) |

## Implementation Phases

### Phase 1: Foundation
- Understand the new skills architecture import pattern
- Identify all required skill directories for the daemon
- Map out the correct PYTHONPATH configuration

### Phase 2: Core Implementation
- Update Dockerfile with new COPY commands and PYTHONPATH
- Update docker-compose.yml volume mounts
- Fix health check import path
- Update entry point command

### Phase 3: Integration & Polish
- Fix manual_test.py daemon path reference
- Test Docker build succeeds
- Test docker-compose up starts correctly
- Verify manual testing workflow works

## Step by Step Tasks

### 1. Update Dockerfile PYTHONPATH
- Change `PYTHONPATH="/app/src"` to include all skill script directories
- New PYTHONPATH should be: `/app/.claude/skills/telegram/scripts:/app/.claude/skills/scheduling/scripts:/app/.claude/skills/database/scripts:/app/.claude/skills/eleven-labs/scripts:/app/.claude/skills/humanizer/scripts:/app/.claude/skills/zoom/scripts:/app/.claude/skills/register-sales/scripts`

### 2. Update Dockerfile COPY Commands
- Remove old `COPY src/ ./src/` line (if src is empty)
- Add COPY commands for each required skills directory:
  ```dockerfile
  # Copy all required skills
  COPY .claude/skills/telegram/ ./.claude/skills/telegram/
  COPY .claude/skills/scheduling/ ./.claude/skills/scheduling/
  COPY .claude/skills/database/ ./.claude/skills/database/
  COPY .claude/skills/eleven-labs/ ./.claude/skills/eleven-labs/
  COPY .claude/skills/humanizer/ ./.claude/skills/humanizer/
  COPY .claude/skills/zoom/ ./.claude/skills/zoom/
  COPY .claude/skills/register-sales/ ./.claude/skills/register-sales/
  COPY .claude/skills/tone-of-voice/ ./.claude/skills/tone-of-voice/
  COPY .claude/skills/how-to-communicate/ ./.claude/skills/how-to-communicate/
  ```

### 3. Update Dockerfile Health Check
- Change from: `from sales_agent.daemon import TelegramDaemon`
- Change to: `from daemon import TelegramDaemon` (since PYTHONPATH includes telegram/scripts)
- Or use a simple Python check: `python -c "import daemon; print('OK')"`

### 4. Update Dockerfile CMD
- Change from: `CMD ["python", "src/sales_agent/daemon.py"]`
- Change to: `CMD ["python", ".claude/skills/telegram/scripts/daemon.py"]`

### 5. Update docker-compose.yml Volume Mounts
- Change config mount from:
  ```yaml
  - ../../src/sales_agent/config:/app/src/sales_agent/config
  ```
- Change to:
  ```yaml
  - ../../.claude/skills/telegram/config:/app/.claude/skills/telegram/config
  ```
- Remove migration mount reference to old path (line 40):
  ```yaml
  # Old: - ../../src/sales_agent/migrations:/docker-entrypoint-initdb.d:ro
  # New: - ../../.claude/skills/database/migrations:/docker-entrypoint-initdb.d:ro
  ```

### 6. Update docker-compose.yml Command
- Update the command block to use new daemon path:
  ```yaml
  command: >
    sh -c "if [ -n \"$$REP_TELEGRAM_ID\" ]; then
      python .claude/skills/telegram/scripts/daemon.py --rep-telegram-id $$REP_TELEGRAM_ID;
    else
      python .claude/skills/telegram/scripts/daemon.py;
    fi"
  ```

### 7. Fix manual_test.py Daemon Path
- Change line 243:
  ```python
  # Old: daemon_script = PROJECT_ROOT / "src" / "sales_agent" / "daemon.py"
  # New: daemon_script = SKILLS_BASE / "telegram" / "scripts" / "daemon.py"
  ```

### 8. Test Docker Build
- Run: `docker-compose -f deployment/docker/docker-compose.yml build telegram-agent`
- Verify build completes without errors

### 9. Test Docker Compose Up
- Run: `docker-compose -f deployment/docker/docker-compose.yml up telegram-agent postgres`
- Verify services start correctly
- Check logs for successful initialization

## Testing Strategy

### Unit Tests
- Verify Dockerfile builds successfully
- Verify health check passes inside container

### Integration Tests
1. **Docker Build Test**:
   ```bash
   docker-compose -f deployment/docker/docker-compose.yml build telegram-agent
   ```
   Expected: Build succeeds without errors

2. **Container Start Test**:
   ```bash
   docker-compose -f deployment/docker/docker-compose.yml up -d postgres
   docker-compose -f deployment/docker/docker-compose.yml up telegram-agent
   ```
   Expected: Daemon initializes, connects to database, shows "Waiting for messages"

3. **Manual Test Workflow**:
   - Set @bohdanpytaichuk status to "new" in `.claude/skills/telegram/config/prospects.json`
   - Start containers
   - Verify initial outreach message sent
   - Reply from Telegram and verify agent responds

4. **Health Check Test**:
   ```bash
   docker exec telegram-agent python -c "from daemon import TelegramDaemon; print('OK')"
   ```
   Expected: Prints "OK"

## Acceptance Criteria
- [ ] Docker build completes without errors
- [ ] `docker-compose up telegram-agent postgres` starts successfully
- [ ] Daemon initializes and connects to database
- [ ] Health check passes
- [ ] Initial outreach message sent to test prospect with status "new"
- [ ] Agent responds to incoming messages
- [ ] Volume mounts correctly persist config changes
- [ ] manual_test.py can start daemon for local testing

## Validation Commands

Execute these commands to validate the task is complete:

```bash
# 1. Build Docker image
docker-compose -f deployment/docker/docker-compose.yml build telegram-agent

# 2. Start postgres and agent
docker-compose -f deployment/docker/docker-compose.yml up -d postgres
sleep 10  # Wait for postgres to be healthy
docker-compose -f deployment/docker/docker-compose.yml up telegram-agent

# 3. In another terminal, check health
docker exec telegram-agent python -c "from daemon import TelegramDaemon; print('OK')"

# 4. Check logs for successful init
docker-compose -f deployment/docker/docker-compose.yml logs telegram-agent | grep -E "(Initializing|Database initialized|Waiting for messages)"

# 5. Stop when done
docker-compose -f deployment/docker/docker-compose.yml down
```

## Notes

### PYTHONPATH Strategy
The daemon.py already adds paths to sys.path dynamically (lines 34-37), so the PYTHONPATH in Dockerfile is primarily for:
1. Health checks that run outside the daemon
2. Any direct Python imports before daemon starts
3. Consistency with the local run pattern

### Volume Mount Strategy
Config files should be mounted read-write to persist changes:
- `prospects.json` - Updated as conversations progress
- `agent_config.json` - Read-only, but mount the whole config dir

### Database Migrations
The migrations are now at `.claude/skills/database/migrations/`. Update the postgres service volume mount to use this new path.

### Compatibility
This change only affects Docker deployment. Local development using:
```bash
PYTHONPATH=.claude/skills/telegram/scripts:... uv run python .claude/skills/telegram/scripts/daemon.py
```
continues to work unchanged.

### Dependencies
All Python dependencies remain in `pyproject.toml` at project root - no changes needed there.
