---
name: orch_plan_w_scouts_build_review
description: Three-phase workflow - plan the task with a custom planner, build the solution with a specialist, then validate with a reviewer.
argument-hint: [task-description]
---

# Purpose

Execute a comprehensive three-phase development workflow: first create a custom planner agent to analyze the task and design an implementation plan, then delegate building to multiple parallel build-agents (one per file, via Task tool), and finally validate the work with a review agent. This ensures thorough planning, efficient parallel implementation, and comprehensive validation.

## Variables

TASK_DESCRIPTION: $1
SLEEP_INTERVAL: 15 seconds
PLANNER_AGENT_NAME: (will be generated based on task)
BUILD_AGENT_NAMES: (multiple agents will be created dynamically based on the plan - one per file)
REVIEW_AGENT_NAME: (will be generated based on task)

## Instructions

- You can know a task is completed when you see an `agent_logs` from `check_agent_status` that has a `response` event_category followed by a `hook` with a `Stop` event_type.
- Run this workflow for ALL THREE agents in sequence. Complete each phase entirely before starting the next.
- Phase 1: Planner creates the implementation plan (custom system prompt designed by you)
- Phase 2: Build agents implement in parallel - one build-agent per file, launched via Task tool (mimics `build_in_parallel` workflow)
- Phase 3: Review agent validates the work (uses `review-agent` template)
- Do NOT delete agents after completion - leave them for inspection and debugging. We might have additional work for these agents to complete.
- Pass findings from each phase to the next agent as context.
- When you command each agent, instruct them to use thinking mode with the 'ultrathink' keyword in your prompt.

## Workflow

### Setup: Create All Agents Upfront

- **(Create Planner)** Run `create_agent` to create a planner agent WITHOUT using a subagent_template
  - Name the agent something descriptive like "planner-{task-keyword}"
  - **IMPORTANT**: Design a custom system prompt for the planner based on TASK_DESCRIPTION that instructs the agent to:
    - Analyze the task requirements thoroughly
    - Explore the codebase to understand existing patterns
    - Design a detailed implementation plan
    - Identify all files that need to be created or modified
    - Specify the technical approach and architecture decisions
    - Create a structured plan document in the `specs/` directory
    - The planner should be configured with tools: Read, Glob, Grep, Write, Bash
- **(Build Agents)** Build agents will NOT be created upfront. They will be launched dynamically in Phase 2 as parallel Task tool calls with `subagent_type="build-agent"` - one per file, based on the planner's output.
- **(Create Review Agent)** Run `create_agent` to create a review agent using the `review-agent` subagent_template
  - Name the agent something descriptive like "reviewer-{task-keyword}"
  - Use the same `task-keyword` so agents are clearly related
  - The agent should be configured for analysis and validation work

### Phase 1: Plan (Analysis & Design)

- **(Command Planner)** Run `command_agent` to command the planner agent to analyze and plan the TASK_DESCRIPTION
  - Instruct the agent to create a comprehensive implementation plan
  - Ensure the plan includes: objective, requirements, files to modify, step-by-step tasks, acceptance criteria
- **(Check Planner)** The planner agent will work in the background. While it works use `Bash(sleep ${SLEEP_INTERVAL})` and every `SLEEP_INTERVAL` seconds run `check_agent_status` to check on the planner's progress.
  - If you're interrupted with an additional task, make sure you return to your sleep + check loop after you've completed the additional task.
  - Continue checking until you see a `response` event_category followed by a `hook` with a `Stop` event_type
- **(Report Planner)** Once the planner has completed, retrieve and analyze their plan from the agent logs.
  - Extract key information: plan location, files to modify, implementation approach
  - Read the plan file from `specs/` directory to understand the full context
  - Communicate the planner's findings to the user

### Phase 2: Build (Parallel Implementation)

This phase mimics the `build_in_parallel` workflow. Instead of a single build agent, you launch multiple build-agents in parallel via the Task tool - one per file.

#### Step 2a: Read and Analyze the Plan

- Read the plan file created by the planner in Phase 1 (from `specs/` directory)
- Analyze thoroughly to understand:
  - All files that need to be created or modified
  - Dependencies between files
  - The overall architecture and flow
  - Code style and conventions mentioned

#### Step 2b: Gather Context for Specifications

- Read relevant existing files in the codebase to understand:
  - Coding patterns and conventions
  - Import styles and module organization
  - Error handling approaches
  - Similar implementations that can serve as examples
- Use Grep/Glob to find related files that provide context
- Identify which files can be built in parallel vs which have dependencies

#### Step 2c: Create Detailed File Specifications

For each file that needs to be created/modified, create a comprehensive specification:

```markdown
# File: [absolute/path/to/file.ext]

## Purpose
[What this file does and why it exists]

## Requirements
- [Detailed requirement 1]
- [Detailed requirement 2]

## Related Files
- **[file-path]**: [how it relates and what to reference]

## Code Style & Patterns
- [Pattern 1 to follow]
- [Pattern 2 to follow]

## Dependencies
- [Import/dependency 1]
- [Import/dependency 2]

## Example Code
[Provide similar code from the codebase or pseudocode example]

## Integration Points
[How this file connects with other parts of the system]

## Verification
[How to verify this file works: tests to run, type checks, etc.]
```

#### Step 2d: Identify Parallel vs Sequential Batches

- Group files into batches based on dependencies:
  - **Batch 1**: Files with no dependencies (can be built in parallel)
  - **Batch 2**: Files that depend on Batch 1
  - **Batch 3**: Files that depend on Batch 2
  - [etc.]

#### Step 2e: Launch Build Agents in Parallel

For each batch (starting with Batch 1):

- **IMPORTANT**: Launch multiple build-agent instances in parallel using a **single message** with multiple Task tool calls
- Each Task tool call should:
  - Use `subagent_type: "build-agent"`
  - Provide the complete specification created in Step 2c
  - Include all necessary context for that specific file
  - Include the original TASK_DESCRIPTION for overall context
  - Instruct the agent to use thinking mode with 'ultrathink'
- Wait for all agents in the current batch to complete before moving to the next batch
- Example:
  ```
  In a single message, make multiple Task tool calls:
  - Task(subagent_type="build-agent", prompt="[Full spec for file1]")
  - Task(subagent_type="build-agent", prompt="[Full spec for file2]")
  - Task(subagent_type="build-agent", prompt="[Full spec for file3]")
  ```

#### Step 2f: Monitor and Collect Results

- Review the reports from each build-agent
- Identify any issues or concerns raised
- Note any deviations from specifications
- Check verification results (tests, type checks, etc.)

#### Step 2g: Handle Issues

- If any agents report problems:
  - Review the issue
  - Make necessary adjustments
  - Re-launch the specific agent with updated specifications if needed

#### Step 2h: Final Build Verification

- Run any project-wide checks (e.g., full test suite, build process)
- Verify all files integrate correctly
- Check that all requirements from the plan are met

- **(Report Build)** Once all build agents have completed, report the parallel implementation results to the user.
  - Provide a file-by-file breakdown with status (success/issues/failed)
  - Note total files created or modified and how many agents ran
  - Communicate build completion and key deliverables

### Phase 3: Review (Validation)

- **(Command Review Agent)** Run `command_agent` to command the review agent to validate the work
  - Provide the review agent with:
    - The original TASK_DESCRIPTION
    - The planner's plan for comparison
    - Instructions to analyze git diffs and validate implementation
    - Request a risk-tiered report (Blockers, High Risk, Medium Risk, Low Risk)
  - Instruct the review agent to produce a comprehensive validation report
- **(Check Review Agent)** The review agent will work in the background. While it works use `Bash(sleep ${SLEEP_INTERVAL})` and every `SLEEP_INTERVAL` seconds run `check_agent_status` to check on the review agent's progress.
  - If you're interrupted with an additional task, make sure you return to your sleep + check loop after you've completed the additional task.
  - Continue checking until you see a `response` event_category followed by a `hook` with a `Stop` event_type
- **(Report Review)** Once the review agent has completed, report the validation results to the user.
  - Extract the review findings from agent logs
  - Note the location of the review report
  - Communicate PASS/FAIL verdict and any critical issues
  - Highlight any blockers that need immediate attention

### Final Report

- **(Summary)** Provide a complete summary to the user:
  - Plan phase results: what was planned and where the plan is located
  - Build phase results: file-by-file breakdown of what was implemented, how many parallel agents ran, which files were modified, and any issues encountered
  - Review phase results: validation verdict and any issues found
  - Planner and reviewer agents are available for inspection (not deleted). Build agents were launched as Task sub-agents.
  - Any follow-up recommendations or next steps based on review findings

## Report

Communicate to the user where you are at each step of the workflow:

1. **Setup Starting**: "Creating planner, builder, and reviewer agents for {TASK_DESCRIPTION}..."
2. **Setup Complete**: "Agents created: Planner '{PLANNER_AGENT_NAME}' and reviewer '{REVIEW_AGENT_NAME}'. Build agents will be launched dynamically in Phase 2."
3. **Plan Phase Starting**: "Commanding planner agent to analyze and design implementation..."
4. **Plan Working**: "Planner agent is analyzing the task and designing the implementation plan... (checking every {SLEEP_INTERVAL} seconds)"
5. **Plan Complete**: "Planning complete. Implementation plan saved to: [plan-file-path]. Key approach: [summary of technical approach]"
6. **Build Phase Starting**: "Analyzing plan to create per-file specifications for parallel build..."
7. **Build Specs Ready**: "Created specifications for [N] files across [M] batches. Launching Batch 1 with [K] parallel build-agents..."
8. **Build Batch Progress**: "Batch [X] complete ([K] agents). Launching Batch [X+1]..." (repeat for each batch)
9. **Build Complete**: "Parallel build complete. [N] files implemented by [total] build-agents. Status: [success count] succeeded, [issue count] issues, [fail count] failed."
10. **Review Phase Starting**: "Commanding review agent to validate the implementation..."
11. **Review Working**: "Review agent is analyzing changes and validating work... (checking every {SLEEP_INTERVAL} seconds)"
12. **Review Complete**: "Review complete. Verdict: [PASS/FAIL]. Report location: [review-report-path]. Issues found: [count by risk tier]"
13. **Final Summary**: "Three-phase workflow complete. All agents are available for inspection. [Final recommendation based on review verdict]"
