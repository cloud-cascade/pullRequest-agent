"""DevUI entry point for PR Agent.

Launches the Agent Framework DevUI for interactive testing and debugging
of the PR analysis agents and workflow.

Usage:
    python devui.py

Or via CLI:
    devui ./agents --port 8080
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from dotenv import load_dotenv
from agent_framework import WorkflowBuilder, ChatAgent
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework_devui import serve, register_cleanup

# Load environment variables
load_dotenv()

# Import agent creation functions
from agents import create_code_analyzer_agent, create_security_scanner_agent

# Import executors for workflow
from executors import PRAnalysisDispatcher, PRAnalysisAggregator

# Import tools for standalone agents
from tools.code_analyzer import analyze_code_changes_tool
from tools.generic_security_scanner import scan_security_tool
from tools.github_api import get_pr_diff_tool


def create_azure_client() -> AzureOpenAIChatClient:
    """Create Azure OpenAI client from environment variables."""
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

    if not endpoint or not api_key:
        raise ValueError(
            "Missing Azure OpenAI configuration. "
            "Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY environment variables."
        )

    return AzureOpenAIChatClient(
        azure_endpoint=endpoint,
        api_key=api_key,
        deployment_name=deployment,
        api_version=api_version
    )


async def create_entities():
    """Create all agents and workflows for DevUI."""
    client = create_azure_client()

    # Create individual agents for standalone testing
    code_analyzer = await create_code_analyzer_agent(client)
    security_scanner = await create_security_scanner_agent(client)

    # Create the PR Analysis workflow (fan-out/fan-in pattern)
    dispatcher = PRAnalysisDispatcher(id="dispatcher")
    aggregator = PRAnalysisAggregator(id="aggregator")

    # Create fresh agents for workflow (each agent instance should be separate)
    workflow_code_agent = await create_code_analyzer_agent(client)
    workflow_security_agent = await create_security_scanner_agent(client)

    workflow = (
        WorkflowBuilder()
        .set_start_executor(dispatcher)
        .add_fan_out_edges(dispatcher, [workflow_code_agent, workflow_security_agent])
        .add_fan_in_edges([workflow_code_agent, workflow_security_agent], aggregator)
        .build()
    )
    # Give workflow a name for DevUI display
    workflow.name = "PRAnalysisWorkflow"

    return [code_analyzer, security_scanner, workflow]


def main():
    """Launch DevUI with PR Agent entities."""
    print("=" * 60)
    print("PR Agent - DevUI")
    print("Interactive Development & Testing Interface")
    print("=" * 60)

    # Create entities
    print("\nInitializing agents and workflows...")
    entities = asyncio.run(create_entities())

    print(f"\nLoaded {len(entities)} entities:")
    for entity in entities:
        name = getattr(entity, 'name', entity.__class__.__name__)
        entity_type = "Workflow" if hasattr(entity, 'run_stream') and not isinstance(entity, ChatAgent) else "Agent"
        print(f"  - {name} ({entity_type})")

    # Get port from environment or use default
    port = int(os.getenv("DEVUI_PORT", "8080"))

    print(f"\nStarting DevUI on http://localhost:{port}")
    print("Press Ctrl+C to stop\n")

    # Launch DevUI
    serve(
        entities=entities,
        port=port,
        auto_open=True,
        mode="developer"  # Full developer mode with debugging
    )


if __name__ == "__main__":
    main()
