"""PR Agent for analyzing code changes using Microsoft Agent Framework.

This agent analyzes Pull Requests across multiple programming languages including:
- Python, JavaScript, TypeScript, Java, C#, Go, Rust, Ruby, PHP
- SQL and database migrations
- Infrastructure as Code (Bicep, Terraform)
- Configuration files (YAML, JSON, TOML)
- And more...
"""

import asyncio
import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from dotenv import load_dotenv
from pydantic import ValidationError
from agent_framework import WorkflowBuilder, AgentRunUpdateEvent, WorkflowOutputEvent
from agent_framework.azure import AzureOpenAIChatClient


# Optional observability imports
try:
    from utils.observability import configure_observability, get_tracer
    OBSERVABILITY_AVAILABLE = True
except ImportError:
    configure_observability = None  # type: ignore
    get_tracer = None  # type: ignore
    OBSERVABILITY_AVAILABLE = False

# Import configuration models
from schemas import PRAgentConfig

# Import agents
from agents import create_code_analyzer_agent, create_security_scanner_agent, create_file_summarizer_agent

# Import executors for fan-out/fan-in workflow
from executors import PRAnalysisDispatcher, PRAnalysisAggregator

# Import tools and utilities
from tools.github_api import post_pr_comment
from utils.markdown_formatter import (
    combine_pr_comment, 
    format_code_analysis, 
    format_security_scan, 
    format_error_comment,
    format_executive_summary,
    format_detailed_changes
)

# Load environment variables
load_dotenv()


async def main():
    """Main workflow orchestrator for PR agent."""

    print("=" * 60)
    print("PR Agent - Multi-Language Code Analysis")
    print("Powered by Microsoft Agent Framework")
    print("=" * 60)

    # Load and validate configuration using Pydantic
    try:
        config = PRAgentConfig.from_environment()
    except ValidationError as e:
        print("\nConfiguration Error:")
        for error in e.errors():
            field = " -> ".join(str(loc) for loc in error['loc'])
            print(f"  {field}: {error['msg']}")
        sys.exit(1)
    except ValueError as e:
        print(f"\nConfiguration Error: {e}")
        sys.exit(1)

    print(f"\nAnalyzing PR #{config.github.pr_number} in {config.github.github_repository}")

    # Step 1: Configure Observability
    print("\nStep 1: Configuring Observability...")
    if OBSERVABILITY_AVAILABLE and configure_observability:
        configure_observability()
    else:
        print("   Observability: Not available (module not installed)")

    try:
        # Step 2: Initialize Azure OpenAI Client
        print("\nStep 2: Initializing Azure OpenAI Client...")
        print(f"   Using deployment: {config.azure_openai.deployment_name}")

        # Create the Azure OpenAI client using API key authentication
        client = AzureOpenAIChatClient(
            azure_endpoint=config.azure_openai.azure_openai_endpoint,
            api_key=config.azure_openai.azure_openai_api_key,
            deployment_name=config.azure_openai.deployment_name,
            api_version=config.azure_openai.api_version
        )

        # Step 3: Create Code Analysis Agent
        print("\nStep 3: Creating Code Analysis Agent...")
        code_agent = await create_code_analyzer_agent(client)

        # Step 4: Create Security Scanning Agent
        print("\nStep 4: Creating Security Scanning Agent...")
        security_agent = await create_security_scanner_agent(client)

        # Step 5: Create File Summarizer Agent
        print("\nStep 5: Creating File Summarizer Agent...")
        summarizer_agent = await create_file_summarizer_agent(client)

        # Step 6: Create Dispatcher and Aggregator executors
        print("\nStep 6: Creating Workflow Executors...")
        dispatcher = PRAnalysisDispatcher(id="dispatcher")
        aggregator = PRAnalysisAggregator(id="aggregator")

        # Step 7: Build Workflow with Fan-Out/Fan-In Pattern
        # Dispatcher fans out to all agents, then results are aggregated
        print("\nStep 7: Building Fan-Out/Fan-In Workflow...")
        print("   Workflow: Dispatcher -> [CodeAnalyzer, SecurityScanner, FileSummarizer] -> Aggregator")

        workflow = (
            WorkflowBuilder()
            .set_start_executor(dispatcher)
            .add_fan_out_edges(dispatcher, [code_agent, security_agent, summarizer_agent])
            .add_fan_in_edges([code_agent, security_agent, summarizer_agent], aggregator)
            .build()
        )

        print("\nStep 8: Executing Workflow...")

        # Prepare minimal context for agents - they will fetch PR data themselves using tools
        # Agents are now autonomous and will call get_pr_diff tool on their own
        pr_context = {
            "pr_number": config.github.pr_number,
            "repository": config.github.github_repository,
            "instruction": "Analyze this Pull Request. Use your get_pr_diff tool to fetch the PR changes, then analyze them."
        }
        workflow_input = json.dumps(pr_context, indent=2)

        # Execute the workflow
        print("\n" + "=" * 60)
        print("WORKFLOW EXECUTION")
        print("=" * 60)

        last_executor_id = None
        aggregator_output = None

        # Run the workflow with streaming
        async for event in workflow.run_stream(workflow_input):
            if isinstance(event, AgentRunUpdateEvent):
                # Handle streaming updates from agents
                eid = event.executor_id
                if eid != last_executor_id:
                    if last_executor_id is not None:
                        print()
                    print(f"\n[{eid}]:", end=" ", flush=True)
                    last_executor_id = eid
                if event.data:
                    try:
                        print(event.data, end="", flush=True)
                    except UnicodeEncodeError:
                        # Handle Windows console encoding issues
                        print(event.data.encode('ascii', 'replace').decode('ascii'), end="", flush=True)
            elif isinstance(event, WorkflowOutputEvent):
                print("\n\n===== Workflow Output =====")
                aggregator_output = event.data
                print(aggregator_output if aggregator_output else "No output")

        print("\n" + "=" * 60)
        print("WORKFLOW COMPLETED")
        print("=" * 60)

        # Step 9: Extract results from aggregator and format PR comment
        print("\nStep 9: Extracting results and formatting PR Comment...")

        # Extract analysis, security results, file summaries, and agent interpretations from aggregator output
        agent_interpretations = {}
        file_summaries_result = {}
        if aggregator_output and isinstance(aggregator_output, dict):
            analysis_result = aggregator_output.get("code_analysis", {})
            security_result = aggregator_output.get("security_scan", {})
            file_summaries_result = aggregator_output.get("file_summaries", {})
            agent_interpretations = aggregator_output.get("agent_interpretations", {})
            print(f"   Extracted code_analysis: {len(analysis_result.get('files', []))} files")
            print(f"   Extracted security_scan: {security_result.get('summary', {}).get('total_issues', 0)} issues")
            print(f"   Extracted file_summaries: {file_summaries_result.get('total_files', 0)} files")
            if agent_interpretations:
                print(f"   Extracted agent interpretations: {len(agent_interpretations)} agents")
        else:
            # Fallback to empty results if aggregator didn't return expected structure
            print("   Warning: Aggregator output not in expected format, using empty results")
            analysis_result = {
                "files": [],
                "summary": {
                    "total_files": 0,
                    "total_additions": 0,
                    "total_deletions": 0,
                    "languages": [],
                    "categories": []
                }
            }
            security_result = {
                "findings": [],
                "summary": {
                    "total_issues": 0,
                    "high_severity": 0,
                    "medium_severity": 0,
                    "low_severity": 0
                }
            }

        # Check if we have structured data or need to use agent interpretations
        has_structured_analysis = len(analysis_result.get('files', [])) > 0
        has_structured_security = len(security_result.get('findings', [])) > 0 or security_result.get('summary', {}).get('files_scanned', 0) > 0
        has_file_summaries = file_summaries_result.get('total_files', 0) > 0
        code_interpretation = agent_interpretations.get("code_analyzer", "")
        security_interpretation = agent_interpretations.get("security_scanner", "")
        summarizer_interpretation = agent_interpretations.get("file_summarizer", "")

        # If we have agent interpretations but no structured data, use the interpretations directly
        if (code_interpretation or security_interpretation or summarizer_interpretation) and not (has_structured_analysis or has_structured_security):
            print("   Using agent interpretations (tools did not return structured data)")
            # Build comment from agent interpretations
            comment_parts = ["## PR Analysis Report\n"]
            comment_parts.append(f"*Analysis powered by AI agents using Azure OpenAI*\n\n")

            if summarizer_interpretation:
                comment_parts.append("### File Summaries\n\n")
                comment_parts.append(summarizer_interpretation)
                comment_parts.append("\n\n")

            if code_interpretation:
                comment_parts.append("### Code Analysis\n\n")
                comment_parts.append(code_interpretation)
                comment_parts.append("\n\n")

            if security_interpretation:
                comment_parts.append("### Security Analysis\n\n")
                comment_parts.append(security_interpretation)
                comment_parts.append("\n\n")

            comment_markdown = "".join(comment_parts)
        else:
            # Use structured formatting
            print("   Using structured data formatting")
            # Generate executive summary for easy reading
            executive_summary = format_executive_summary(
                analysis_result,
                security_result,
                file_summaries_result,
                summarizer_interpretation
            )

            # Generate detailed per-file change descriptions
            # Use file summaries from the agent if available
            detailed_changes = format_detailed_changes(
                analysis_result.get('files', []),
                file_summaries_result,
                summarizer_interpretation
            )

            analysis_md = format_code_analysis(analysis_result)
            security_md = format_security_scan(security_result)
            comment_markdown = combine_pr_comment(
                analysis_md,
                security_md,
                False,  # files_truncated - agents handle their own limits
                0,      # max_files - not applicable in agentic mode
                executive_summary,
                detailed_changes
            )

        # Step 10: Post Comment to PR
        print("\nStep 10: Posting Comment to PR...")
        success = post_pr_comment(
            config.github.github_repository, 
            config.github.pr_number, 
            comment_markdown, 
            config.github.github_token
        )

        if success:
            print(f"\nSuccessfully analyzed and commented on PR #{config.github.pr_number}")
            print("\n" + "=" * 60)
            print("ANALYSIS COMPLETE!")
            print("=" * 60)
        else:
            print(f"\nFailed to post comment to PR #{config.github.pr_number}")
            sys.exit(1)

    except Exception as e:
        print(f"\nError during workflow execution: {e}")
        import traceback
        traceback.print_exc()

        # Try to post an error comment
        try:
            error_comment = format_error_comment(str(e))
            post_pr_comment(
                config.github.github_repository, 
                config.github.pr_number, 
                error_comment, 
                config.github.github_token
            )
        except:
            pass

        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
