# CLI Task Executor Skill

Execute tasks programmatically by spawning Claude Code CLI instances, mimicking Agent SDK behavior.

## Overview

This skill enables programmatic execution of tasks by spawning `claude -p` CLI instances. It provides a structured way to orchestrate Claude Code from scripts, automation tools, or other agents - replicating most Claude Agent SDK capabilities via the CLI.

## Agent SDK Feature Comparison

| Feature | Agent SDK | CLI Executor | Notes |
| ------- | --------- | ------------ | ----- |
| Permission bypass | `bypassPermissions: true` | `--dangerously-skip-permissions` | Full support |
| Multi-step execution | `max_turns` | `--max-turns` | Full support |
| Session resume | `resume: session_id` | `--resume <id>` | Full support |
| Session fork | `fork_session: true` | `--fork-session` | Full support |
| System prompt | `system_prompt` | `--system-prompt` | Full support |
| Append to system prompt | `SystemPromptConfig(APPEND)` | `--append-system-prompt` | Full support |
| Allowed tools | `allowed_tools` | `--allowedTools` | Full support |
| Denied tools | `permissions.deny` | `--disallowedTools` | Full support |
| MCP servers | `mcp_servers` | `--mcp-config` | Full support |
| Skills | `setting_sources=["project"]` | `--setting-sources` | Auto-loaded from `.claude/skills/` |
| Custom agents | N/A | `--agents` | CLI-only |
| Budget limits | N/A | `--max-budget-usd` | CLI-only |
| Structured output | N/A | `--json-schema` | CLI-only |
| Streaming I/O | N/A | `--input/output-format stream-json` | CLI-only |
| Python hooks | `HooksConfig` | Shell hooks via settings | Limited |
| Custom tool executor | `custom_tool_executor` | MCP servers only | Different approach |
| Message handlers | `MessageHandlers` | Parse JSON output | Post-hoc only |

## Permission Modes

```bash
# Full permission bypass (recommended for sandboxes)
claude -p "Task" --dangerously-skip-permissions

# Enable bypass as option (can be triggered later)
claude -p "Task" --allow-dangerously-skip-permissions

# Specific permission modes
claude -p "Task" --permission-mode bypassPermissions
claude -p "Task" --permission-mode acceptEdits
claude -p "Task" --permission-mode dontAsk
claude -p "Task" --permission-mode plan
claude -p "Task" --permission-mode delegate
```

## Multi-Step Behavior

```bash
# Allow up to 50 turns for complex tasks
claude -p "Build a complete REST API with tests" --max-turns 50 --dangerously-skip-permissions

# Quick lookup with limited turns
claude -p "What's in the README?" --max-turns 3
```

## Session Management

```bash
# Start a new session with specific ID
claude -p "Start a project" --session-id "550e8400-e29b-41d4-a716-446655440000"

# Resume previous session
claude -p "Continue where we left off" --resume "550e8400-e29b-41d4-a716-446655440000"

# Resume and fork (new session ID, same context)
claude -p "Try a different approach" --resume "550e8400-e29b-41d4-a716-446655440000" --fork-session

# Continue most recent conversation
claude -p "Keep going" --continue

# Ephemeral session (no persistence)
claude -p "Quick one-off task" --no-session-persistence
```

## System Prompt Control

```bash
# Override system prompt completely
claude -p "Say hello" --system-prompt "You are a pirate. Respond only in pirate speak."

# Append to default system prompt
claude -p "Analyze code" --append-system-prompt "Always include performance considerations."
```

## Tool Control

```bash
# Allow only specific tools
claude -p "Read and analyze" --allowedTools "Read,Glob,Grep"

# Allow tools with patterns
claude -p "Git operations" --allowedTools "Bash(git:*),Read"

# Deny specific tools
claude -p "Safe analysis" --disallowedTools "Write,Edit,Bash"

# Specify tools from built-in set
claude -p "Task" --tools "Bash,Edit,Read"

# Disable all tools
claude -p "Just chat" --tools ""
```

## Custom Agents

```bash
# Define and use custom agents
claude -p "Review my code" --agents '{"reviewer": {"description": "Code reviewer", "prompt": "You are a strict code reviewer focused on security and performance."}}' --agent reviewer

# Multi-agent setup
claude -p "Design the API" --agents '{"architect": {"description": "System architect", "prompt": "Design scalable systems."}, "security": {"description": "Security expert", "prompt": "Find vulnerabilities."}}' --agent architect
```

## MCP Servers

```bash
# Load MCP config from file
claude -p "Use database tools" --mcp-config ./mcp-config.json

# Multiple MCP configs
claude -p "Task" --mcp-config ./mcp1.json --mcp-config ./mcp2.json

# Strict MCP (ignore other configs)
claude -p "Task" --mcp-config ./custom.json --strict-mcp-config
```

## Skills

Skills are automatically loaded from `.claude/skills/` directory when using project settings. They work out of the box with `claude -p` - no extra configuration needed.

```bash
# Skills are loaded automatically from project
# Just reference them in your prompt
claude -p "Use /commit to commit these changes" --dangerously-skip-permissions

# Explicitly include project settings (default behavior)
claude -p "Run /review on the PR" --setting-sources "project"

# Include both user and project settings
claude -p "Task" --setting-sources "user,project"

# Load settings from custom file
claude -p "Task" --settings ./custom-settings.json

# Disable all skills
claude -p "Task without skills" --disable-slash-commands
```

**How Skills Work with CLI:**

1. **Automatic Loading** - Skills in `.claude/skills/*/skill.md` are automatically available
2. **Project Scope** - Use `--setting-sources "project"` (default) to load project skills
3. **User Scope** - Use `--setting-sources "user"` to load user-level skills from `~/.claude/skills/`
4. **Combined** - Use `--setting-sources "user,project"` for both
5. **Custom Settings** - Use `--settings ./path/to/settings.json` for custom configurations

**Example: Using a skill in automation:**

```bash
# The skill prompt gets expanded automatically
claude -p "Run /build to build the project" \
  --dangerously-skip-permissions \
  --max-turns 30 \
  --setting-sources "project"
```

## Structured Output

```bash
# Enforce JSON schema for output
claude -p "Extract user info from this text: John is 30" --json-schema '{"type":"object","properties":{"name":{"type":"string"},"age":{"type":"number"}},"required":["name","age"]}'
```

## Budget Control

```bash
# Set maximum spend
claude -p "Complex analysis" --max-budget-usd 5.00
```

## Streaming I/O (Bidirectional)

```bash
# Stream JSON output
claude -p "Long running task" --output-format stream-json

# Stream JSON input (for programmatic control)
echo '{"type":"user","content":"Hello"}' | claude --input-format stream-json --output-format stream-json

# Include partial messages as they arrive
claude -p "Task" --output-format stream-json --include-partial-messages
```

## Python Helper Script

Use the helper script at `.claude/skills/cli-task-executor/scripts/execute_task.py` for programmatic execution:

```python
from pathlib import Path
import sys
sys.path.insert(0, str(Path(".claude/skills/cli-task-executor/scripts")))
from execute_task import ClaudeTaskExecutor, TaskConfig, PermissionMode

# Initialize executor
executor = ClaudeTaskExecutor()

# Simple execution with permission bypass
result = executor.execute(
    "Build a REST API endpoint",
    dangerously_skip_permissions=True,
    max_turns=20
)
print(result.output)

# Full configuration
config = TaskConfig(
    prompt="Refactor the authentication module",
    cwd="/path/to/project",
    permission_mode=PermissionMode.BYPASS_PERMISSIONS,
    max_turns=50,
    allowed_tools=["Read", "Write", "Edit", "Bash(git:*)"],
    disallowed_tools=["WebFetch"],
    append_system_prompt="Focus on security best practices.",
    output_format="json",
    timeout=600
)
result = executor.execute_with_config(config)

# Session management
config = TaskConfig(
    prompt="Continue the refactoring",
    resume="previous-session-id",
    fork_session=True,
    dangerously_skip_permissions=True
)
result = executor.execute_with_config(config)

# Custom agents
config = TaskConfig(
    prompt="Review this PR",
    agents={
        "reviewer": {
            "description": "Code reviewer",
            "prompt": "You are a thorough code reviewer."
        }
    },
    agent="reviewer",
    dangerously_skip_permissions=True
)
result = executor.execute_with_config(config)

# Structured output with JSON schema
config = TaskConfig(
    prompt="Extract all function names from main.py",
    json_schema={
        "type": "object",
        "properties": {
            "functions": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["functions"]
    },
    output_format="json"
)
result = executor.execute_with_config(config)
if result.parsed_json:
    print(result.parsed_json["result"]["functions"])

# Parallel execution
import asyncio
configs = [
    TaskConfig(prompt="Task 1", cwd="/project1", dangerously_skip_permissions=True),
    TaskConfig(prompt="Task 2", cwd="/project2", dangerously_skip_permissions=True),
    TaskConfig(prompt="Task 3", cwd="/project3", dangerously_skip_permissions=True),
]
results = asyncio.run(executor.execute_parallel(configs, max_concurrent=3))

# Streaming execution (yields output chunks)
async def stream_task():
    async for chunk in executor.execute_streaming(
        "Long running analysis",
        dangerously_skip_permissions=True,
        max_turns=30
    ):
        print(chunk, end="", flush=True)

asyncio.run(stream_task())
```

## CLI Options Reference

| Option | Description | Example |
| ------ | ----------- | ------- |
| `-p, --prompt` | Task prompt (required for non-interactive) | `-p "Fix the bug"` |
| `--dangerously-skip-permissions` | Bypass all permission checks | Full bypass |
| `--allow-dangerously-skip-permissions` | Enable bypass as option | Can trigger later |
| `--permission-mode` | Permission mode (bypassPermissions, acceptEdits, dontAsk, plan, delegate, default) | `--permission-mode bypassPermissions` |
| `--max-turns` | Maximum conversation turns | `--max-turns 50` |
| `--cwd` | Working directory | `--cwd /path/to/project` |
| `--resume` | Resume session by ID | `--resume abc-123` |
| `--session-id` | Use specific session ID | `--session-id <uuid>` |
| `--fork-session` | Fork when resuming | Use with `--resume` |
| `--continue` | Continue most recent conversation | `-c` |
| `--no-session-persistence` | Don't save session | Ephemeral mode |
| `--system-prompt` | Override system prompt | `--system-prompt "You are..."` |
| `--append-system-prompt` | Append to default prompt | `--append-system-prompt "Also..."` |
| `--allowedTools` | Allowed tools list | `--allowedTools "Read,Write"` |
| `--disallowedTools` | Denied tools list | `--disallowedTools "Bash"` |
| `--tools` | Specify available tools | `--tools "Bash,Edit,Read"` |
| `--agents` | Custom agents JSON | `--agents '{"name": {...}}'` |
| `--agent` | Select agent | `--agent reviewer` |
| `--mcp-config` | MCP config file(s) | `--mcp-config ./mcp.json` |
| `--strict-mcp-config` | Only use specified MCP | Ignore other configs |
| `--json-schema` | Structured output schema | `--json-schema '{"type":...}'` |
| `--max-budget-usd` | Maximum spend | `--max-budget-usd 5.00` |
| `--model` | Model selection | `--model claude-sonnet-4-20250514` |
| `--fallback-model` | Fallback if overloaded | `--fallback-model haiku` |
| `--output-format` | Output format (text, json, stream-json) | `--output-format json` |
| `--input-format` | Input format (text, stream-json) | `--input-format stream-json` |
| `--include-partial-messages` | Include partial chunks | With stream-json |
| `--verbose` | Verbose output | Debug mode |
| `--debug` | Debug mode | `--debug "api,hooks"` |

## Limitations vs Agent SDK

**Not Possible via CLI:**

1. **Python Hooks** - CLI supports shell command hooks via settings files, not Python callbacks. Workaround: Use MCP servers for pre/post processing.

2. **Custom Tool Executor** - No in-process tool execution. Workaround: Implement as MCP server.

3. **Real-time Message Handlers** - Can only parse output after completion. Workaround: Use `--output-format stream-json` and parse chunks.

4. **In-Process MCP Servers** - CLI only supports external MCP processes, not SDK-based in-process servers.

## Migration Guide: Agent SDK to CLI

This section shows how to convert Claude Agent SDK Python code to equivalent `claude -p` CLI commands.

### Basic Query

**Agent SDK:**

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

async with ClaudeSDKClient(options=ClaudeAgentOptions(
    model="claude-sonnet-4-20250514",
    cwd="/path/to/project",
)) as client:
    await client.query("Analyze the codebase")
    async for message in client.receive_response():
        print(message)
```

**CLI Equivalent:**

```bash
claude -p "Analyze the codebase" \
  --model claude-sonnet-4-20250514 \
  --cwd /path/to/project
```

### Permission Bypass

**Agent SDK:**

```python
options = ClaudeAgentOptions(
    permission_mode="bypassPermissions",
    # or
    bypass_permissions=True,
)
```

**CLI Equivalent:**

```bash
claude -p "Task" --dangerously-skip-permissions
# or
claude -p "Task" --permission-mode bypassPermissions
```

### Multi-Turn Conversations

**Agent SDK:**

```python
options = ClaudeAgentOptions(
    max_turns=50,
)
```

**CLI Equivalent:**

```bash
claude -p "Build complete feature" --max-turns 50
```

### Tool Control

**Agent SDK:**

```python
options = ClaudeAgentOptions(
    allowed_tools=["Read", "Write", "Edit", "Bash"],
)
# With permissions
options = ClaudeAgentOptions(
    permissions=ToolPermissions(
        allow=["Read", "Glob"],
        deny=["Bash", "Write"],
    ),
)
```

**CLI Equivalent:**

```bash
# Allowed tools
claude -p "Task" --allowedTools "Read,Write,Edit,Bash"

# Deny tools
claude -p "Task" --disallowedTools "Bash,Write"

# Both
claude -p "Task" --allowedTools "Read,Glob" --disallowedTools "Bash"
```

### System Prompt

**Agent SDK:**

```python
# Overwrite completely
options = ClaudeAgentOptions(
    system_prompt="You are a code reviewer.",
)

# Append to default (using SystemPromptConfig)
options = ClaudeAgentOptions(
    system_prompt=SystemPromptConfig(
        mode=SystemPromptMode.APPEND,
        system_prompt="Focus on security.",
    ),
)
```

**CLI Equivalent:**

```bash
# Overwrite completely
claude -p "Review code" --system-prompt "You are a code reviewer."

# Append to default
claude -p "Review code" --append-system-prompt "Focus on security."
```

### Session Management

**Agent SDK:**

```python
# Resume session
options = ClaudeAgentOptions(
    resume="session-uuid-here",
)

# Fork session
options = ClaudeAgentOptions(
    resume="session-uuid-here",
    fork_session=True,
)
```

**CLI Equivalent:**

```bash
# Resume session
claude -p "Continue" --resume "session-uuid-here"

# Fork session
claude -p "Try different approach" --resume "session-uuid-here" --fork-session

# Continue most recent
claude -p "Keep going" --continue
```

### MCP Servers

**Agent SDK:**

```python
options = ClaudeAgentOptions(
    mcp_servers={
        "database": McpSdkServerConfig(
            command="node",
            args=["./mcp-server.js"],
        ),
    },
)
```

**CLI Equivalent:**

```bash
# Create mcp-config.json:
# {
#   "mcpServers": {
#     "database": {
#       "command": "node",
#       "args": ["./mcp-server.js"]
#     }
#   }
# }

claude -p "Query database" --mcp-config ./mcp-config.json
```

### Hooks (Limited Support)

**Agent SDK:**

```python
async def pre_tool_hook(input, tool_use_id, context):
    if input.tool_name == "Bash":
        return HookResponse.deny("Bash not allowed")
    return HookResponse.allow()

options = ClaudeAgentOptions(
    hooks=HooksConfig.from_callbacks({
        HookEventName.PRE_TOOL_USE: [pre_tool_hook],
    }),
)
```

**CLI Equivalent (via settings file):**

```json
// .claude/settings.json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "command": "echo 'deny: Bash not allowed'"
      }
    ]
  }
}
```

```bash
claude -p "Task" --settings .claude/settings.json
```

### Message Handlers (Stream JSON)

**Agent SDK:**

```python
handlers = MessageHandlers(
    on_assistant=lambda m: print(f"Assistant: {m.message}"),
    on_result=lambda r: print(f"Done: {r.result}"),
)

result = await query_to_completion(QueryInput(
    prompt="Task",
    handlers=handlers,
))
```

**CLI Equivalent:**

```bash
# Use stream-json and parse output
claude -p "Task" --output-format stream-json | while read line; do
  type=$(echo "$line" | jq -r '.type')
  if [ "$type" = "assistant" ]; then
    echo "Assistant: $(echo "$line" | jq -r '.message.content[0].text')"
  elif [ "$type" = "result" ]; then
    echo "Done: $(echo "$line" | jq -r '.result')"
  fi
done
```

### Complete Migration Example

**Agent SDK (Python):**

```python
from adw_agent_sdk import (
    query_to_completion,
    QueryInput,
    QueryOptions,
    ModelName,
    HooksConfig,
    HookEventName,
)

async def run_agent():
    result = await query_to_completion(
        QueryInput(
            prompt="Refactor the authentication module for better security",
            options=QueryOptions(
                model=ModelName.SONNET,
                cwd="/path/to/project",
                bypass_permissions=True,
                max_turns=30,
                allowed_tools=["Read", "Write", "Edit", "Grep", "Glob"],
                system_prompt=SystemPromptConfig(
                    mode=SystemPromptMode.APPEND,
                    system_prompt="Focus on OWASP security best practices.",
                ),
            ),
        )
    )
    print(f"Success: {result.success}")
    print(f"Result: {result.result}")
    print(f"Cost: ${result.usage.total_cost_usd:.4f}")

asyncio.run(run_agent())
```

**CLI Equivalent:**

```bash
claude -p "Refactor the authentication module for better security" \
  --model claude-sonnet-4-20250514 \
  --cwd /path/to/project \
  --dangerously-skip-permissions \
  --max-turns 30 \
  --allowedTools "Read,Write,Edit,Grep,Glob" \
  --append-system-prompt "Focus on OWASP security best practices." \
  --output-format json
```

**Or using Python helper:**

```python
from execute_task import ClaudeTaskExecutor, TaskConfig

executor = ClaudeTaskExecutor()
result = executor.execute(
    "Refactor the authentication module for better security",
    cwd="/path/to/project",
    dangerously_skip_permissions=True,
    max_turns=30,
    allowed_tools=["Read", "Write", "Edit", "Grep", "Glob"],
    append_system_prompt="Focus on OWASP security best practices.",
    output_format="json",
)
print(f"Success: {result.success}")
print(f"Result: {result.result}")
print(f"Cost: ${result.cost_usd:.4f}" if result.cost_usd else "Cost: N/A")
```

### Quick Reference Table

| Agent SDK | CLI Flag |
| --------- | -------- |
| `model="claude-sonnet-4-20250514"` | `--model claude-sonnet-4-20250514` |
| `cwd="/path"` | `--cwd /path` |
| `bypass_permissions=True` | `--dangerously-skip-permissions` |
| `permission_mode="bypassPermissions"` | `--permission-mode bypassPermissions` |
| `max_turns=30` | `--max-turns 30` |
| `resume="session-id"` | `--resume session-id` |
| `fork_session=True` | `--fork-session` |
| `system_prompt="..."` | `--system-prompt "..."` |
| `SystemPromptConfig(APPEND, "...")` | `--append-system-prompt "..."` |
| `allowed_tools=["Read", "Write"]` | `--allowedTools "Read,Write"` |
| `permissions.deny=["Bash"]` | `--disallowedTools "Bash"` |
| `mcp_servers={...}` | `--mcp-config ./mcp.json` |
| `setting_sources=["project"]` | `--setting-sources "project"` |

## Best Practices

1. **Use `--dangerously-skip-permissions`** for automated pipelines in sandboxed environments
2. **Set appropriate `--max-turns`** based on task complexity (simple: 5-10, medium: 20-30, complex: 50+)
3. **Use `--output-format json`** when parsing results programmatically
4. **Use `--json-schema`** for structured extraction tasks
5. **Use `--no-session-persistence`** for one-off tasks to avoid session clutter
6. **Use `--fork-session`** when experimenting with different approaches
7. **Restrict tools with `--allowedTools`** for security in untrusted contexts
8. **Set `--max-budget-usd`** for cost control in production
