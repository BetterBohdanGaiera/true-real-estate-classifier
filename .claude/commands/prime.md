# Prime

Execute the `Run`, `Read` and `Report` sections to understand the codebase then summarize your understanding.

## Focus
- Primary focus: Claude Code template configuration and AI Developer Workflows

## Run
git ls-files

## Read

### Core (always read these):
- @README.md
- @CLAUDE.md
- @.env.example

### Claude Code Configuration:
- .claude/settings.json
- .claude/agents/ (all agent definitions)
- .claude/commands/ (all command prompts)
- .claude/skills/ (all skill definitions)
- .claude/output-styles/ (output format templates)

### AI Developer Workflows (ADW):
- adws/adw_modules/adw_agent_sdk.py
- adws/adw_modules/adw_database.py
- adws/adw_modules/adw_logging.py
- adws/adw_modules/adw_websockets.py
- adws/adw_workflows/ (workflow implementations)
- adws/adw_triggers/ (workflow triggers)

### Hooks:
- .claude/hooks/ (all hook scripts)

## Report
Summarize your understanding of the codebase structure and capabilities.
