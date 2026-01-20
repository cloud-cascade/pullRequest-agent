"""Dispatcher executor for fan-out pattern in PR analysis workflow.

This executor receives raw PR file data as JSON and fans it out to multiple
agents (CodeAnalyzer and SecurityScanner) for autonomous tool-based analysis.
"""

import json
from agent_framework import Executor, WorkflowContext, handler


class PRAnalysisDispatcher(Executor):
    """Dispatcher that fans out raw PR data to multiple agents.

    This executor is the entry point of the workflow. It receives raw PR file
    data as JSON and sends it to all downstream agents (CodeAnalyzer,
    SecurityScanner) which will autonomously call their tools for analysis.
    """

    @handler
    async def handle(self, data: str, ctx: WorkflowContext[str]):
        """Handle incoming workflow input and fan out to agents.

        Args:
            data: The workflow input containing raw PR file data as JSON
            ctx: Workflow context for sending messages to downstream executors
        """
        print(f"\n[Dispatcher] Received raw PR data, fanning out to agents...")

        # Validate and log the input data
        try:
            pr_data = json.loads(data)
            file_count = len(pr_data.get('files', []))
            pr_number = pr_data.get('pr_number', 'unknown')
            repository = pr_data.get('repository', 'unknown')
            print(f"[Dispatcher] PR #{pr_number} in {repository}")
            print(f"[Dispatcher] Distributing {file_count} files to agents for analysis")
        except json.JSONDecodeError as e:
            print(f"[Dispatcher] Warning: Input is not valid JSON: {e}")
            print(f"[Dispatcher] Proceeding with raw data anyway")

        # Fan out the same input to all connected downstream agents
        # Each agent will parse the JSON and call their tools autonomously
        await ctx.send_message(data)

        print(f"[Dispatcher] Fan-out complete - agents will call their tools")
