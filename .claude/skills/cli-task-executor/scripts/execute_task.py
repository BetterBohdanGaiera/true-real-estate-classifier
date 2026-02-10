#!/usr/bin/env python3
"""
CLI Task Executor - Execute tasks via Claude Code CLI instances.

This module provides programmatic execution of tasks by spawning `claude -p` CLI instances.
Mimics Claude Agent SDK behavior with support for:
- Permission bypass (dangerously-skip-permissions)
- Multi-step execution (max-turns)
- Session management (resume, fork, continue)
- System prompt control (override, append)
- Tool control (allowed, disallowed)
- Custom agents
- MCP servers
- Structured output (json-schema)
- Budget limits
- Streaming I/O
"""

import asyncio
import json
import os
import re
import subprocess
import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

load_dotenv()

console = Console()


class OutputFormat(str, Enum):
    """Supported output formats for Claude CLI."""

    TEXT = "text"
    JSON = "json"
    STREAM_JSON = "stream-json"


class InputFormat(str, Enum):
    """Supported input formats for Claude CLI."""

    TEXT = "text"
    STREAM_JSON = "stream-json"


class PermissionMode(str, Enum):
    """Permission modes available in Claude CLI."""

    DEFAULT = "default"
    BYPASS_PERMISSIONS = "bypassPermissions"
    ACCEPT_EDITS = "acceptEdits"
    DONT_ASK = "dontAsk"
    PLAN = "plan"
    DELEGATE = "delegate"


@dataclass
class TaskConfig:
    """Configuration for a Claude CLI task execution.

    Supports all Claude Code CLI options for mimicking Agent SDK behavior.
    """

    prompt: str

    # Working directory
    cwd: str | None = None

    # Permission control
    dangerously_skip_permissions: bool = False
    allow_dangerously_skip_permissions: bool = False
    permission_mode: PermissionMode | str | None = None

    # Multi-step behavior
    max_turns: int | None = None

    # Session management
    session_id: str | None = None
    resume: str | None = None
    fork_session: bool = False
    continue_conversation: bool = False
    no_session_persistence: bool = False

    # System prompt
    system_prompt: str | None = None
    append_system_prompt: str | None = None

    # Tool control
    allowed_tools: list[str] | None = None
    disallowed_tools: list[str] | None = None
    tools: list[str] | None = None  # Specify tools from built-in set

    # Custom agents
    agents: dict[str, dict[str, str]] | None = None
    agent: str | None = None

    # MCP servers
    mcp_configs: list[str] | None = None
    strict_mcp_config: bool = False

    # Structured output
    json_schema: dict[str, Any] | str | None = None

    # Budget control
    max_budget_usd: float | None = None

    # Model selection
    model: str | None = None
    fallback_model: str | None = None

    # Output control
    output_format: OutputFormat | str = OutputFormat.TEXT
    input_format: InputFormat | str | None = None
    include_partial_messages: bool = False

    # Additional directories
    add_dirs: list[str] | None = None

    # Debug and verbose
    verbose: bool = False
    debug: str | None = None
    debug_file: str | None = None

    # Settings
    settings: str | None = None  # Path to settings file or JSON string
    setting_sources: list[str] | None = None  # user, project, local

    # Execution control
    timeout: int = 600  # 10 minutes default

    # Environment variables
    env: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.output_format, str):
            self.output_format = OutputFormat(self.output_format)
        if isinstance(self.input_format, str) and self.input_format:
            self.input_format = InputFormat(self.input_format)
        if isinstance(self.permission_mode, str) and self.permission_mode:
            self.permission_mode = PermissionMode(self.permission_mode)


@dataclass
class TaskResult:
    """Result from a Claude CLI task execution."""

    success: bool
    output: str
    exit_code: int
    duration_ms: float | None = None
    cost_usd: float | None = None
    num_turns: int | None = None
    session_id: str | None = None
    parsed_json: dict[str, Any] | None = None
    error: str | None = None

    @property
    def result(self) -> str | None:
        """Get the result from parsed JSON or raw output."""
        if self.parsed_json and "result" in self.parsed_json:
            return self.parsed_json["result"]
        return self.output if self.success else None


class ClaudeTaskExecutor:
    """Execute tasks via Claude Code CLI instances.

    Mimics Claude Agent SDK behavior by wrapping the CLI with Python.
    """

    def __init__(
        self,
        default_timeout: int = 600,
        default_model: str | None = None,
        default_max_turns: int | None = None,
    ) -> None:
        """
        Initialize the task executor.

        Args:
            default_timeout: Default timeout in seconds for task execution
            default_model: Default model to use for all tasks
            default_max_turns: Default max turns for multi-step execution
        """
        self.default_timeout = default_timeout
        self.default_model = default_model or os.getenv(
            "CLAUDE_MODEL", "claude-opus-4-6"
        )
        self.default_max_turns = default_max_turns
        self._verify_claude_cli()

    def _verify_claude_cli(self) -> None:
        """Verify that claude CLI is available."""
        if not shutil.which("claude"):
            raise RuntimeError(
                "Claude CLI not found. Please install it with: npm install -g @anthropic-ai/claude-code"
            )

    def _build_command(self, config: TaskConfig) -> list[str]:
        """Build the CLI command from configuration."""
        cmd = ["claude", "-p", config.prompt]

        # Note: Working directory is passed via subprocess cwd parameter, not CLI arg

        # Permission control
        if config.dangerously_skip_permissions:
            cmd.append("--dangerously-skip-permissions")
        if config.allow_dangerously_skip_permissions:
            cmd.append("--allow-dangerously-skip-permissions")
        if config.permission_mode:
            mode = (
                config.permission_mode.value
                if isinstance(config.permission_mode, PermissionMode)
                else config.permission_mode
            )
            cmd.extend(["--permission-mode", mode])

        # Multi-step behavior
        max_turns = config.max_turns or self.default_max_turns
        if max_turns:
            cmd.extend(["--max-turns", str(max_turns)])

        # Session management
        if config.session_id:
            cmd.extend(["--session-id", config.session_id])
        if config.resume:
            cmd.extend(["--resume", config.resume])
        if config.fork_session:
            cmd.append("--fork-session")
        if config.continue_conversation:
            cmd.append("--continue")
        if config.no_session_persistence:
            cmd.append("--no-session-persistence")

        # System prompt
        if config.system_prompt:
            cmd.extend(["--system-prompt", config.system_prompt])
        if config.append_system_prompt:
            cmd.extend(["--append-system-prompt", config.append_system_prompt])

        # Tool control
        if config.allowed_tools:
            cmd.extend(["--allowedTools", ",".join(config.allowed_tools)])
        if config.disallowed_tools:
            cmd.extend(["--disallowedTools", ",".join(config.disallowed_tools)])
        if config.tools is not None:
            # Empty list means disable all tools
            tools_str = ",".join(config.tools) if config.tools else ""
            cmd.extend(["--tools", tools_str])

        # Custom agents
        if config.agents:
            cmd.extend(["--agents", json.dumps(config.agents)])
        if config.agent:
            cmd.extend(["--agent", config.agent])

        # MCP servers
        if config.mcp_configs:
            for mcp_config in config.mcp_configs:
                cmd.extend(["--mcp-config", mcp_config])
        if config.strict_mcp_config:
            cmd.append("--strict-mcp-config")

        # Structured output
        if config.json_schema:
            schema_str = (
                json.dumps(config.json_schema)
                if isinstance(config.json_schema, dict)
                else config.json_schema
            )
            cmd.extend(["--json-schema", schema_str])

        # Budget control
        if config.max_budget_usd:
            cmd.extend(["--max-budget-usd", str(config.max_budget_usd)])

        # Model selection
        model = config.model or self.default_model
        if model:
            cmd.extend(["--model", model])
        if config.fallback_model:
            cmd.extend(["--fallback-model", config.fallback_model])

        # Output control
        if config.output_format:
            fmt = (
                config.output_format.value
                if isinstance(config.output_format, OutputFormat)
                else config.output_format
            )
            cmd.extend(["--output-format", fmt])
        if config.input_format:
            fmt = (
                config.input_format.value
                if isinstance(config.input_format, InputFormat)
                else config.input_format
            )
            cmd.extend(["--input-format", fmt])
        if config.include_partial_messages:
            cmd.append("--include-partial-messages")

        # Additional directories
        if config.add_dirs:
            for add_dir in config.add_dirs:
                cmd.extend(["--add-dir", add_dir])

        # Debug and verbose
        if config.verbose:
            cmd.append("--verbose")
        if config.debug:
            cmd.extend(["--debug", config.debug])
        if config.debug_file:
            cmd.extend(["--debug-file", config.debug_file])

        # Settings
        if config.settings:
            cmd.extend(["--settings", config.settings])
        if config.setting_sources:
            cmd.extend(["--setting-sources", ",".join(config.setting_sources)])

        return cmd

    def _build_env(self, config: TaskConfig) -> dict[str, str]:
        """Build environment variables for the subprocess."""
        env = os.environ.copy()
        env.update(config.env)
        return env

    def _parse_json_output(self, output: str) -> dict[str, Any] | None:
        """Parse JSON output from Claude CLI."""
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            # Try to find JSON in the output (might have text before/after)
            match = re.search(r"\{.*\}", output, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return None

    def _parse_stream_json_output(self, output: str) -> list[dict[str, Any]]:
        """Parse stream-json output (newline-delimited JSON)."""
        results = []
        for line in output.strip().split("\n"):
            if line.strip():
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return results

    def _build_task_result(
        self,
        output: str,
        exit_code: int,
        config: TaskConfig,
        error: str | None = None,
    ) -> TaskResult:
        """Build a TaskResult from subprocess output, parsing JSON/stream-json metadata."""
        parsed_json = None
        duration_ms = None
        cost_usd = None
        num_turns = None
        session_id = None

        if config.output_format == OutputFormat.JSON:
            parsed_json = self._parse_json_output(output)
            if parsed_json:
                duration_ms = parsed_json.get("duration_ms")
                cost_usd = parsed_json.get("cost_usd")
                num_turns = parsed_json.get("num_turns")
                session_id = parsed_json.get("session_id")
        elif config.output_format == OutputFormat.STREAM_JSON:
            messages = self._parse_stream_json_output(output)
            for msg in reversed(messages):
                if msg.get("type") == "result":
                    duration_ms = msg.get("duration_ms")
                    cost_usd = msg.get("cost_usd")
                    num_turns = msg.get("num_turns")
                    session_id = msg.get("session_id")
                    break
            parsed_json = {"messages": messages}

        return TaskResult(
            success=exit_code == 0,
            output=output,
            exit_code=exit_code,
            duration_ms=duration_ms,
            cost_usd=cost_usd,
            num_turns=num_turns,
            session_id=session_id,
            parsed_json=parsed_json,
            error=error,
        )

    def execute(self, prompt: str, **kwargs: Any) -> TaskResult:
        """
        Execute a simple task with a prompt.

        Args:
            prompt: The task prompt to execute
            **kwargs: Additional TaskConfig parameters

        Returns:
            TaskResult with execution results
        """
        config = TaskConfig(prompt=prompt, **kwargs)
        return self.execute_with_config(config)

    def execute_with_config(self, config: TaskConfig) -> TaskResult:
        """
        Execute a task with full configuration.

        Args:
            config: TaskConfig with all execution parameters

        Returns:
            TaskResult with execution results
        """
        cmd = self._build_command(config)
        env = self._build_env(config)
        timeout = config.timeout or self.default_timeout

        if config.verbose:
            console.print(
                Panel(
                    f"[bold]Command:[/bold] {' '.join(cmd)}",
                    title="Executing Claude Task",
                    width=console.width,
                )
            )

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task(description="Executing task...", total=None)

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=env,
                    cwd=config.cwd,
                )

            return self._build_task_result(
                output=result.stdout,
                exit_code=result.returncode,
                config=config,
                error=result.stderr if result.returncode != 0 else None,
            )

        except subprocess.TimeoutExpired:
            return TaskResult(
                success=False,
                output="",
                exit_code=-1,
                error=f"Task timed out after {timeout} seconds",
            )
        except Exception as e:
            return TaskResult(
                success=False,
                output="",
                exit_code=-1,
                error=str(e),
            )

    async def execute_async(self, prompt: str, **kwargs: Any) -> TaskResult:
        """
        Execute a task asynchronously.

        Args:
            prompt: The task prompt to execute
            **kwargs: Additional TaskConfig parameters

        Returns:
            TaskResult with execution results
        """
        config = TaskConfig(prompt=prompt, **kwargs)
        return await self.execute_with_config_async(config)

    async def execute_with_config_async(self, config: TaskConfig) -> TaskResult:
        """
        Execute a task with full configuration asynchronously.

        Args:
            config: TaskConfig with all execution parameters

        Returns:
            TaskResult with execution results
        """
        cmd = self._build_command(config)
        env = self._build_env(config)
        timeout = config.timeout or self.default_timeout

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=config.cwd,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return TaskResult(
                    success=False,
                    output="",
                    exit_code=-1,
                    error=f"Task timed out after {timeout} seconds",
                )

            return self._build_task_result(
                output=stdout.decode(),
                exit_code=process.returncode or 0,
                config=config,
                error=stderr.decode() if process.returncode != 0 else None,
            )

        except Exception as e:
            return TaskResult(
                success=False,
                output="",
                exit_code=-1,
                error=str(e),
            )

    async def execute_streaming(
        self, prompt: str, **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """
        Execute a task with streaming output.

        Yields output chunks as they arrive. Useful for long-running tasks.

        Args:
            prompt: The task prompt to execute
            **kwargs: Additional TaskConfig parameters (output_format forced to stream-json)

        Yields:
            Output chunks as strings
        """
        # Force stream-json output for streaming
        kwargs["output_format"] = OutputFormat.STREAM_JSON
        config = TaskConfig(prompt=prompt, **kwargs)
        async for chunk in self._execute_streaming_config(config):
            yield chunk

    async def _execute_streaming_config(
        self, config: TaskConfig
    ) -> AsyncGenerator[str, None]:
        """Execute with streaming output from config."""
        cmd = self._build_command(config)
        env = self._build_env(config)

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=config.cwd,
        )

        if process.stdout:
            async for line in process.stdout:
                yield line.decode()

        await process.wait()

    async def execute_parallel(
        self, configs: list[TaskConfig], max_concurrent: int = 5
    ) -> list[TaskResult]:
        """
        Execute multiple tasks in parallel.

        Args:
            configs: List of TaskConfig objects to execute
            max_concurrent: Maximum number of concurrent executions

        Returns:
            List of TaskResult objects in the same order as configs
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def execute_with_semaphore(config: TaskConfig) -> TaskResult:
            async with semaphore:
                return await self.execute_with_config_async(config)

        tasks = [execute_with_semaphore(config) for config in configs]
        return await asyncio.gather(*tasks)

    def print_result(self, result: TaskResult, title: str = "Task Result") -> None:
        """Print a formatted result to the console."""
        if result.success:
            style = "green"
            status = "SUCCESS"
        else:
            style = "red"
            status = "FAILED"

        table = Table(title=title, width=console.width)
        table.add_column("Property", style="cyan")
        table.add_column("Value")

        table.add_row("Status", f"[{style}]{status}[/{style}]")
        table.add_row("Exit Code", str(result.exit_code))

        if result.session_id:
            table.add_row("Session ID", result.session_id)

        if result.duration_ms:
            table.add_row("Duration", f"{result.duration_ms:.0f}ms")

        if result.cost_usd:
            table.add_row("Cost", f"${result.cost_usd:.4f}")

        if result.num_turns:
            table.add_row("Turns", str(result.num_turns))

        if result.error:
            table.add_row("Error", f"[red]{result.error}[/red]")

        console.print(table)

        if result.output:
            console.print(
                Panel(
                    result.output[:2000] + ("..." if len(result.output) > 2000 else ""),
                    title="Output",
                    width=console.width,
                )
            )


def main() -> None:
    """CLI entry point for testing."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Execute tasks via Claude Code CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Simple task with permission bypass
  uv run execute_task.py "Fix the bug in main.py" --dangerously-skip-permissions

  # Multi-step task
  uv run execute_task.py "Build a REST API" --max-turns 30 --dangerously-skip-permissions

  # Resume session
  uv run execute_task.py "Continue" --resume <session-id>

  # With custom agent
  uv run execute_task.py "Review code" --agents '{"reviewer": {"prompt": "Be strict"}}' --agent reviewer
        """,
    )

    # Required
    parser.add_argument("prompt", help="The task prompt to execute")

    # Working directory
    parser.add_argument("--cwd", help="Working directory")

    # Permission control
    parser.add_argument(
        "--dangerously-skip-permissions",
        action="store_true",
        help="Bypass all permission checks",
    )
    parser.add_argument(
        "--permission-mode",
        choices=["default", "bypassPermissions", "acceptEdits", "dontAsk", "plan", "delegate"],
        help="Permission mode",
    )

    # Multi-step
    parser.add_argument("--max-turns", type=int, help="Maximum conversation turns")

    # Session management
    parser.add_argument("--session-id", help="Use specific session ID")
    parser.add_argument("--resume", help="Resume session by ID")
    parser.add_argument(
        "--fork-session", action="store_true", help="Fork when resuming"
    )
    parser.add_argument(
        "--continue", dest="continue_conversation", action="store_true", help="Continue most recent"
    )
    parser.add_argument(
        "--no-session-persistence", action="store_true", help="Don't save session"
    )

    # System prompt
    parser.add_argument("--system-prompt", help="Override system prompt")
    parser.add_argument("--append-system-prompt", help="Append to system prompt")

    # Tool control
    parser.add_argument("--allowed-tools", help="Comma-separated allowed tools")
    parser.add_argument("--disallowed-tools", help="Comma-separated disallowed tools")

    # Custom agents
    parser.add_argument("--agents", help="Custom agents JSON")
    parser.add_argument("--agent", help="Select agent")

    # MCP
    parser.add_argument("--mcp-config", action="append", help="MCP config file(s)")

    # Structured output
    parser.add_argument("--json-schema", help="JSON schema for structured output")

    # Budget
    parser.add_argument("--max-budget-usd", type=float, help="Maximum spend")

    # Model
    parser.add_argument("--model", help="Model to use")

    # Output
    parser.add_argument(
        "--output-format",
        choices=["text", "json", "stream-json"],
        default="text",
        help="Output format",
    )

    # Execution
    parser.add_argument(
        "--timeout", type=int, default=600, help="Timeout in seconds"
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Build config
    config = TaskConfig(
        prompt=args.prompt,
        cwd=args.cwd,
        dangerously_skip_permissions=args.dangerously_skip_permissions,
        permission_mode=args.permission_mode,
        max_turns=args.max_turns,
        session_id=args.session_id,
        resume=args.resume,
        fork_session=args.fork_session,
        continue_conversation=args.continue_conversation,
        no_session_persistence=args.no_session_persistence,
        system_prompt=args.system_prompt,
        append_system_prompt=args.append_system_prompt,
        allowed_tools=args.allowed_tools.split(",") if args.allowed_tools else None,
        disallowed_tools=args.disallowed_tools.split(",") if args.disallowed_tools else None,
        agents=json.loads(args.agents) if args.agents else None,  # noqa: may raise JSONDecodeError
        agent=args.agent,
        mcp_configs=args.mcp_config,
        json_schema=args.json_schema,
        max_budget_usd=args.max_budget_usd,
        model=args.model,
        output_format=args.output_format,
        timeout=args.timeout,
        verbose=args.verbose,
    )

    executor = ClaudeTaskExecutor()
    result = executor.execute_with_config(config)
    executor.print_result(result)

    exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
