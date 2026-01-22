# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PR Agent is an AI-powered Pull Request analyzer that uses Microsoft Agent Framework with Azure OpenAI (GPT-4) to perform code analysis and security scanning. It posts formatted analysis results as PR comments.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt
# or with uv
uv sync

# Run PR agent (requires environment variables)
python pr-agent.py

# Run interactive DevUI for testing
python devui.py
```

## Required Environment Variables

```
GITHUB_TOKEN, GITHUB_REPOSITORY, PR_NUMBER
AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT_NAME
```

Optional: `APPLICATIONINSIGHTS_CONNECTION_STRING` for observability.

## Architecture

**Workflow Pattern: Fan-Out/Fan-In**

```
Dispatcher → [CodeAnalyzerAgent, SecurityScannerAgent] → Aggregator → PR Comment
```

1. **Dispatcher** (`executors/dispatcher.py`): Entry point, distributes PR data to agents
2. **Agents** (`agents/`): Autonomous AI agents that call their tools independently
3. **Aggregator** (`executors/aggregator.py`): Collects results from agent conversations, combines into structured output
4. **Markdown Formatter** (`utils/markdown_formatter.py`): Converts results to PR comment

**Key Insight**: Agents don't return tool results directly. The aggregator must extract tool results from the agent's `full_conversation` message history. A cache fallback (`.cache/`) exists because message extraction is unreliable.

## Module Structure

| Directory | Purpose |
|-----------|---------|
| `agents/` | ChatAgent definitions with system prompts |
| `executors/` | Workflow executors (Dispatcher, Aggregator) |
| `tools/` | `@ai_function` decorated tools agents call autonomously |
| `schemas/` | Pydantic configuration models (load from env vars) |
| `utils/` | Observability setup, markdown formatting |

## Tool Autonomy Pattern

Agents are instructed to call their tools and tools auto-fetch PR data from GitHub:

```python
# In tools/code_analyzer.py
@ai_function(name="analyze_code_changes", ...)
def analyze_code_changes_tool(pr_files: str = "") -> str:
    # If pr_files empty, auto-fetches from GITHUB_* env vars
```

This means:
- `pr-agent.py` passes minimal context; tools fetch their own data
- `devui.py` can pass full PR JSON; tools use provided data

## Entry Points

- **`pr-agent.py`**: Production runner for GitHub Actions
- **`devui.py`**: Interactive testing UI at localhost:8080

## Observability

Configured in `utils/observability.py`. Supports:
- Disabled (default if no connection string)
- Azure Application Insights (production)
- Local OTLP exporter (development)

## Supported Languages

Python, JavaScript, TypeScript, Java, C#, Go, Rust, SQL, Bicep, Terraform, YAML, and 15+ more (see `tools/code_analyzer.py` LANGUAGE_MAP).
