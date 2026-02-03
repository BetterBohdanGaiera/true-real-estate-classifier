# Plan: Codebase Refactoring and Docker Image Optimization

## Task Description
Major refactoring of the Classifier codebase to remove redundant files and folders, decrease Docker image size, and consolidate code for better maintainability. The codebase contains a Telegram sales agent daemon that is currently working with one test account and config.

## Objective
Reduce Docker image size and codebase complexity by:
1. Removing unnecessary files and directories not required for production
2. Eliminating code duplication between `.claude/skills/telegram/scripts/` and `src/sales_agent/`
3. Adding proper `.dockerignore` to exclude development artifacts
4. Consolidating dependencies and configuration

## Problem Statement
The codebase has evolved organically with several issues:
1. **Massive data directory (2.1GB)** - Contains video files only needed for knowledge extraction, not runtime
2. **Duplicate code** - ~7,500 lines in `.claude/skills/telegram/scripts/` duplicate functionality now in `src/sales_agent/` (~7,900 lines)
3. **Development-only directories** - `adws/`, `scripts/`, `specs/`, `knowledge_base/` are not needed in production
4. **Unused skills** - Many `.claude/skills/` subdirectories (cloudflare-manager: 24MB with node_modules!) are not used by the daemon
5. **Missing .dockerignore** - No `.dockerignore` file, risking accidental inclusion of large/sensitive files
6. **Session data pollution** - `.claude/data/` contains ephemeral session data that shouldn't be in version control

## Solution Approach
1. Create comprehensive `.dockerignore` to exclude all non-essential files
2. Refactor `telegram_fetch.py` into `src/sales_agent/` to eliminate the last dependency on `.claude/skills/telegram/scripts/`
3. Document which directories are production vs development only
4. Clean up unused dependencies from `pyproject.toml` if any

## Relevant Files

### Production-Essential Files (KEEP)
- `src/sales_agent/**/*.py` - Core application code (824KB)
- `src/sales_agent/config/` - Runtime configuration (JSON files)
- `src/sales_agent/migrations/` - Database schema
- `deployment/docker/Dockerfile` - Docker build
- `deployment/docker/docker-compose.yml` - Orchestration
- `knowledge_base_final/` - Curated knowledge (152KB) - **USED by agent at runtime**
- `.claude/skills/tone-of-voice/` - **USED by agent** (76KB)
- `.claude/skills/how-to-communicate/` - **USED by agent** (160KB)
- `.claude/skills/telegram/scripts/telegram_fetch.py` - **USED** but should be refactored into src/
- `pyproject.toml` + `uv.lock` - Dependencies

### Development-Only Files (EXCLUDE from Docker)
- `data/` - **2.1GB** of video files for knowledge extraction - NOT needed at runtime
- `knowledge_base/` - **38MB** intermediate knowledge base (Final/ version copied to knowledge_base_final/)
- `scripts/` - **344KB** of one-time pipeline scripts (extract_pdf.py, process_video.py, etc.)
- `specs/` - **316KB** of planning documents
- `adws/` - **376KB** AI Developer Workflow system - development tooling only
- `.claude/agents/` - Claude Code agent configs (dev only)
- `.claude/commands/` - Claude Code slash commands (dev only)
- `.claude/hooks/` - Claude Code hooks (dev only)
- `.claude/output-styles/` - Claude Code output formatting
- `.claude/status_lines/` - Claude Code status line
- `.claude/data/` - Ephemeral session cache (already gitignored)
- `logs/` - Runtime logs (already gitignored)
- `ai_docs/` - Documentation directory

### Skills NOT Used by Daemon (EXCLUDE from Docker)
- `.claude/skills/cloudflare-manager/` - **24MB** (has node_modules!)
- `.claude/skills/brand-agency/` - 60KB
- `.claude/skills/docx/` - 364KB
- `.claude/skills/eleven-labs/` - 24KB
- `.claude/skills/frontend-design/` - 16KB
- `.claude/skills/google-calendar/` - 104KB (optional, not currently used by daemon)
- `.claude/skills/meta-skill/` - 72KB
- `.claude/skills/pdf/` - 136KB
- `.claude/skills/video-analysis/` - 12KB
- `.claude/skills/video-processor/` - 28KB
- `.claude/skills/zoom/` - 72KB (optional zoom integration)

### Skills Used for Calendar Setup (KEEP for full functionality)
- `.claude/skills/zoom-calendar-meeting/` - 8KB - **USED** for setting up calendar meetings

### Files NOT Needed in Docker (EXCLUDE)
- `.env2` - Duplicate environment file (5.6KB)
- `ЛичныйКакФоллоуАпитьТонОфВойс.md` - Russian personal notes in root
- `follow-up-update.md` - Notes in root directory

### New Files to Create
- `.dockerignore` - Comprehensive exclusion list

## Implementation Phases

### Phase 1: Docker Optimization (No Code Changes)
- Add `.dockerignore` file to exclude all non-essential files
- Verify Docker image builds correctly with exclusions
- Measure image size reduction

### Phase 2: Code Consolidation
- Move `telegram_fetch.py` functionality into `src/sales_agent/telegram/`
- Update imports in `daemon.py`, `telegram_service.py`, and `manual_test.py`
- Remove path manipulation hacks (`sys.path.insert`)

### Phase 3: Cleanup & Documentation
- Remove or move root-level stray files
- Add README to document directory purposes
- Consider moving development scripts to a `dev/` directory

## Step by Step Tasks

### 1. Create .dockerignore File
- Create `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/.dockerignore`
- Exclude `data/` directory (2.1GB)
- Exclude `knowledge_base/` (keep `knowledge_base_final/`)
- Exclude `scripts/`, `specs/`, `adws/`, `ai_docs/`
- Exclude all `.claude/` except required skills
- Exclude `logs/`, `.git/`, `.venv/`, `__pycache__/`
- Exclude documentation files `*.md` in root (except CLAUDE.md)

### 2. Verify Docker Build
- Run `docker build` with new `.dockerignore`
- Verify image still functions correctly
- Compare image size before/after

### 3. Refactor telegram_fetch.py into src/sales_agent/
- Copy `telegram_fetch.py` to `src/sales_agent/telegram/telegram_fetch.py`
- Update imports to use relative package imports
- Update `daemon.py` to import from package instead of skills dir
- Update `telegram_service.py` similarly
- Update `testing/manual_test.py` similarly
- Test that the daemon still works

### 4. Remove Redundant Skills From Docker
- Update Dockerfile COPY commands to only include:
  - `.claude/skills/tone-of-voice/`
  - `.claude/skills/how-to-communicate/`
  - `.claude/skills/zoom-calendar-meeting/`
- Remove COPY of `.claude/skills/telegram/scripts/` after refactor
- Verify PYTHONPATH no longer needs skills directory

### 5. Clean Up Root Directory
- Move `ЛичныйКакФоллоуАпитьТонОфВойс.md` to `data/how_to_communicate/` or `docs/`
- Move `follow-up-update.md` to `specs/` or delete if obsolete
- Remove `.env2` if no longer needed

### 6. Update Dockerfile
- Remove references to `.claude/skills/telegram/scripts/` from PYTHONPATH
- Simplify the COPY commands after refactoring
- Add multi-stage build optimization if not already present

### 7. Validate Complete Solution
- Build Docker image
- Run container with docker-compose
- Verify agent starts and responds correctly
- Check that all knowledge/skills are loaded

## Testing Strategy
1. **Pre-refactor baseline**: Record current Docker image size
2. **After .dockerignore**: Verify build succeeds, measure size reduction
3. **After code refactor**: Run `uv run python src/sales_agent/daemon.py` locally to verify imports
4. **Integration test**: Use docker-compose to start full stack (postgres + agent)
5. **Functional test**: Send test message to verify agent responds correctly

## Acceptance Criteria
- [ ] Docker image size reduced by at least 50% (from including data/)
- [ ] `.dockerignore` file prevents accidental inclusion of sensitive/large files
- [ ] No `sys.path.insert` hacks in production code
- [ ] All telegram functionality imported from `src/sales_agent/` package
- [ ] Agent daemon starts and operates correctly in Docker container
- [ ] Root directory has no stray documentation files

## Validation Commands
- `docker build -f deployment/docker/Dockerfile -t telegram-agent:test .` - Build image
- `docker images telegram-agent:test --format "{{.Size}}"` - Check image size
- `docker run --rm telegram-agent:test python -c "from sales_agent.daemon import TelegramDaemon"` - Verify imports
- `docker-compose -f deployment/docker/docker-compose.yml config` - Validate compose file
- `uv run python -c "from sales_agent.telegram import TelegramService"` - Test local imports

## Notes
- The `telegram_fetch.py` script (932 lines) contains essential Telethon client setup and message fetching logic that the daemon depends on
- Consider keeping `.claude/skills/telegram/scripts/` as a fallback during transition
- The `data/` directory with 2.1GB of videos is already gitignored but will be excluded from Docker context with `.dockerignore`
- The `.claude/skills/cloudflare-manager/` has 24MB of `node_modules/` that should never have been committed - this is a separate cleanup task
- Some files in `.claude/skills/telegram/scripts/` are duplicates of files now in `src/sales_agent/` (e.g., `telegram_service.py`, `models.py`, `prospect_manager.py`) - after refactor these can be removed

### Directory Size Summary (Current)
| Directory | Size | Status |
|-----------|------|--------|
| data/ | 2.1GB | EXCLUDE |
| knowledge_base/ | 38MB | EXCLUDE |
| .claude/ | 29MB | PARTIAL |
| src/ | 824KB | INCLUDE |
| knowledge_base_final/ | 152KB | INCLUDE |
| scripts/ | 344KB | EXCLUDE |
| specs/ | 316KB | EXCLUDE |
| adws/ | 376KB | EXCLUDE |

### Expected Docker Image Contents
After refactoring, the Docker image should only contain:
- `src/sales_agent/` - Application code
- `knowledge_base_final/` - Runtime knowledge
- `.claude/skills/tone-of-voice/` - Tone skill
- `.claude/skills/how-to-communicate/` - Communication skill
- `.claude/skills/zoom-calendar-meeting/` - Calendar meeting setup
- `.venv/` - Python dependencies (built in image)
- Config files: `pyproject.toml`, `uv.lock`
