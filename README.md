# Claude Code Template - AI Developer Workflows & Agent Experts

A template repository for building production-ready AI agent systems with Claude Code. This template includes:

1. **AI Developer Workflows (ADW)** - Autonomous multi-step workflows that plan, build, review, and fix code
2. **Agent Experts** - Self-improving agents that learn from their actions and build domain expertise
3. **Claude Code Configuration** - Pre-configured hooks, commands, agents, and skills

---

## What's Included

```
.
├── .claude/                 # Claude Code configuration
│   ├── agents/              # Specialized sub-agent definitions
│   ├── commands/            # Slash command workflows (/plan, /build, /review, etc.)
│   ├── hooks/               # Event hooks for tool use, notifications, etc.
│   ├── skills/              # User-invocable skills
│   └── output-styles/       # Output formatting templates
│
├── adws/                    # AI Developer Workflows infrastructure
│   ├── adw_modules/         # Core modules (SDK wrapper, logging, WebSocket, etc.)
│   ├── adw_workflows/       # Multi-step workflow implementations
│   └── adw_triggers/        # CLI triggers for testing workflows
│
├── CLAUDE.md                # Engineering rules for AI agents
├── .env.example             # Environment configuration template
└── .gitignore               # Git ignore patterns
```

---

## Quick Start

### 1. Prerequisites

- **Python 3.12+**
- **[Astral UV](https://docs.astral.sh/uv/)** - Python package manager
- **Anthropic API key** ([Get one here](https://console.anthropic.com/))

### 2. Setup

```bash
# Clone this template
git clone <your-repo-url>
cd <your-repo>

# Copy environment template
cp .env.example .env

# Edit .env and add your API key
code .env
```

### 3. Required Environment Variables

```bash
# API Key (required)
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Database (optional - required for ADW features)
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

---

## AI Developer Workflows (ADW)

> **The highest leverage point of agentic coding**: deterministic orchestration meets non-deterministic intelligence.

AI Developer Workflows represent a fundamental shift in how we build with AI agents:

**Raw agents are unreliable. Raw code is inflexible. Combined, they're unstoppable.**

### The Core Insight: Composable Workflow Steps

Each workflow is built from **interchangeable, composable steps**:

```
/plan   : always creates a spec file at a known path
/build  : agent implements creatively based on spec
/review : always outputs risk-tiered report with PASS/FAIL
/fix    : agent resolves issues based on review
```

The **orchestration is deterministic** (step order, file paths, status updates). The **execution is non-deterministic** (agent reasoning, code generation, problem-solving).

### Workflow Types

| Workflow                | Steps | Use Case                                                    |
| ----------------------- | ----- | ----------------------------------------------------------- |
| `plan_build`            | 2     | Quick features—plan the implementation, then build it       |
| `plan_build_review`     | 3     | Quality-focused—adds risk-tiered code review after building |
| `plan_build_review_fix` | 4     | Full automation—automatically fixes issues found in review  |

### ADW Architecture

```
adws/
├── adw_modules/           # Core infrastructure
│   ├── adw_agent_sdk.py   # Typed Pydantic wrapper for Claude Agent SDK
│   ├── adw_logging.py     # Step lifecycle logging
│   ├── adw_websockets.py  # Real-time WebSocket broadcasting
│   ├── adw_summarizer.py  # AI-powered event summaries
│   └── adw_database.py    # PostgreSQL operations
│
├── adw_workflows/         # Multi-step workflow implementations
│   ├── adw_plan_build.py           # 2-step: /plan → /build
│   ├── adw_plan_build_review.py    # 3-step: /plan → /build → /review
│   └── adw_plan_build_review_fix.py # 4-step: /plan → /build → /review → /fix
│
└── adw_triggers/          # How workflows get started
    ├── adw_manual_trigger.py  # CLI trigger for testing
    └── adw_scripts.py         # Spawns background processes
```

### Running an ADW

```bash
# Via CLI (for testing)
uv run adws/adw_triggers/adw_manual_trigger.py \
  "feature-name" \
  "plan_build_review" \
  "Create a markdown preview app with live rendering" \
  "/path/to/project"
```

---

## Agent Experts

> Finally, agents that actually learn.

The massive problem with agents is this: **your agents forget**. Traditional software improves as it's used—storing analytics, patterns, and data. Agents don't.

**Agent Experts** solve this with a three-step workflow:

### The Core Pattern: ACT → LEARN → REUSE

```
ACT    →  Agent takes a useful action (builds, fixes, answers)
LEARN  →  Agent stores new information in its expertise file
REUSE  →  Agent uses that expertise on the next execution
```

### Building Your Own Agent Expert

#### Step 1: Create the Expertise File

```yaml
# .claude/commands/experts/<domain>/expertise.yaml
overview:
  description: "What this system does"
  key_files:
    - "path/to/critical/file.py"

core_implementation:
  # Structure your domain knowledge here
```

#### Step 2: Create Domain-Specific Commands

Each expert can have:
- `expertise.yaml` - The mental model (structured knowledge)
- `question.md` - Query the expert without making changes
- `self-improve.md` - Sync expertise against the codebase
- `plan.md` - Create domain-aware implementation plans

#### Step 3: Run Self-Improve

```bash
# Run until your agent stops finding new things to update
/experts:<domain>:self-improve true
```

### Included Experts

This template includes starter experts for:
- **ADW** - AI Developer Workflows expertise (populated)
- **Database** - Database schema and operations (template)
- **WebSocket** - Real-time communication patterns (template)

---

## Claude Code Configuration

### Slash Commands

| Command | Description |
|---------|-------------|
| `/plan` | Create detailed implementation specification |
| `/build` | Implement from specification |
| `/review` | Risk-tiered code review |
| `/fix` | Fix issues from review |
| `/question` | Answer questions without coding |
| `/prime` | Understand the codebase |

### Agents

Pre-configured specialized agents in `.claude/agents/`:
- `build-agent.md` - File implementation specialist
- `scout-report-suggest.md` - Codebase analysis
- `planner.md` - Implementation planning
- `docs-scraper.md` - Documentation fetching
- `meta-agent.md` - Agent configuration generator

### Hooks

Event hooks in `.claude/hooks/` for:
- `pre_tool_use.py` - Before tool execution
- `post_tool_use.py` - After tool execution
- `notification.py` - Notification handling
- `stop.py` - Session completion
- `user_prompt_submit.py` - User input processing

---

## Customization

### Adding a New Workflow

1. Copy an existing workflow file (e.g., `adw_plan_build.py`)
2. Add/remove steps as needed
3. Update the `TOTAL_STEPS` constant
4. Create corresponding slash commands if needed

### Adding a New Expert

1. Create directory: `.claude/commands/experts/<domain>/`
2. Add `expertise.yaml` with initial knowledge structure
3. Add `question.md` for querying
4. Add `self-improve.md` for learning
5. Run `/experts:<domain>:self-improve` to populate

### Adding a New Skill

1. Create directory: `.claude/skills/<skill-name>/`
2. Add `SKILL.md` with skill definition
3. The skill will be available via `/<skill-name>`

---

## Engineering Rules

See `CLAUDE.md` for engineering rules including:
- Use real database connections (no mocking)
- Use Astral UV for Python management
- Use Pydantic models over dicts
- Read files completely in chunks

---

## Resources

- **Claude Code Docs**: https://docs.claude.com/en/docs/claude-code
- **Claude Agent SDK**: https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/sdk-overview
- **Astral UV**: https://docs.astral.sh/uv/

---

## License

This template is provided as-is for building AI agent systems with Claude Code.
