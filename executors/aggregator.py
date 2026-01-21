"""Aggregator executor for fan-in pattern in PR analysis workflow.

This executor collects results from multiple agents (CodeAnalyzer and
SecurityScanner) and extracts tool call results from their conversations
to provide structured output for the markdown formatter.
"""

import json
import os
from pathlib import Path
from typing import Any, List, Dict
from agent_framework import Executor, WorkflowContext, handler

# Import the AgentExecutorResponse type that agents produce
try:
    from agent_framework._workflows._agent_executor import AgentExecutorResponse
except ImportError:
    # Fallback if internal import path changes
    AgentExecutorResponse = Any


def load_cached_results() -> Dict[str, Any]:
    """Load cached tool results from files.

    The tools cache their results to .cache/ directory as a fallback mechanism.

    Returns:
        Dictionary with 'code_analysis' and 'security_scan' results if available
    """
    cache_dir = Path(__file__).parent.parent / '.cache'
    results = {}

    # Try to load code analysis result
    code_cache = cache_dir / 'code_analysis_result.json'
    if code_cache.exists():
        try:
            with open(code_cache, 'r') as f:
                results['code_analysis'] = json.load(f)
            print(f"[Aggregator] Loaded cached code analysis from {code_cache}")
        except Exception as e:
            print(f"[Aggregator] Failed to load code cache: {e}")

    # Try to load security scan result
    security_cache = cache_dir / 'security_scan_result.json'
    if security_cache.exists():
        try:
            with open(security_cache, 'r') as f:
                results['security_scan'] = json.load(f)
            print(f"[Aggregator] Loaded cached security scan from {security_cache}")
        except Exception as e:
            print(f"[Aggregator] Failed to load security cache: {e}")

    return results


def extract_tool_result_from_conversation(result, debug: bool = True) -> Dict[str, Any]:
    """Extract tool call results from an agent's conversation history.

    This function looks through the agent's conversation to find tool responses
    which contain the structured analysis data we need.

    Args:
        result: The AgentExecutorResponse or similar object
        debug: Whether to print debug information about the result structure

    Returns:
        Dictionary containing executor_id and extracted tool_result
    """
    executor_id = getattr(result, 'executor_id', 'unknown')
    tool_result = None
    agent_interpretation = ""

    # Debug: print available attributes
    if debug:
        attrs = [a for a in dir(result) if not a.startswith('_')]
        print(f"[Aggregator Debug] {executor_id} result attributes: {attrs}")

    # Get agent text response and check for tool results
    if hasattr(result, 'agent_run_response'):
        arr = result.agent_run_response
        if debug:
            arr_attrs = [a for a in dir(arr) if not a.startswith('_')]
            print(f"[Aggregator Debug] agent_run_response attributes: {arr_attrs}")

        # Get the text response directly
        if hasattr(arr, 'text') and arr.text:
            agent_interpretation = arr.text
            if debug:
                print(f"[Aggregator Debug] Found text in agent_run_response: {len(arr.text)} chars")

        # Check messages for tool results
        if hasattr(arr, 'messages') and arr.messages:
            if debug:
                print(f"[Aggregator Debug] Found {len(arr.messages)} messages in agent_run_response")
            for idx, msg in enumerate(arr.messages):
                msg_role = getattr(msg, 'role', None)
                if debug:
                    msg_attrs = [a for a in dir(msg) if not a.startswith('_')]
                    print(f"[Aggregator Debug] Message {idx} role={msg_role}, attrs={msg_attrs}")
                if msg_role == 'tool':
                    msg_content = getattr(msg, 'content', None) or getattr(msg, 'contents', None)
                    if msg_content:
                        try:
                            parsed = json.loads(str(msg_content)) if isinstance(msg_content, str) else msg_content
                            if isinstance(parsed, dict) and ('files' in parsed or 'findings' in parsed):
                                tool_result = parsed
                                if debug:
                                    print(f"[Aggregator Debug] Extracted tool result from message {idx}")
                        except (json.JSONDecodeError, TypeError):
                            pass

    # Try multiple ways to get the conversation/response
    full_conversation = None

    # Method 1: Direct full_conversation attribute
    if hasattr(result, 'full_conversation') and result.full_conversation:
        full_conversation = result.full_conversation
        if debug:
            print(f"[Aggregator Debug] Found full_conversation directly: {len(full_conversation)} messages")

    # Method 2: Through agent_response
    elif hasattr(result, 'agent_response'):
        agent_response = result.agent_response
        if debug:
            ar_attrs = [a for a in dir(agent_response) if not a.startswith('_')]
            print(f"[Aggregator Debug] agent_response attributes: {ar_attrs}")
        if hasattr(agent_response, 'full_conversation') and agent_response.full_conversation:
            full_conversation = agent_response.full_conversation
        elif hasattr(agent_response, 'messages') and agent_response.messages:
            full_conversation = agent_response.messages

    # Method 3: Through response attribute
    elif hasattr(result, 'response'):
        response = result.response
        if debug:
            r_attrs = [a for a in dir(response) if not a.startswith('_')]
            print(f"[Aggregator Debug] response attributes: {r_attrs}")
        if hasattr(response, 'full_conversation'):
            full_conversation = response.full_conversation
        elif hasattr(response, 'messages'):
            full_conversation = response.messages

    if full_conversation:
        if debug:
            print(f"[Aggregator Debug] Processing {len(full_conversation)} messages from conversation")
        for i, msg in enumerate(full_conversation):
            msg_role = getattr(msg, 'role', None)

            # Try both 'content' and 'contents' attributes
            msg_content = getattr(msg, 'content', None) or getattr(msg, 'contents', None) or ''

            # Extract text from contents if it's a list
            if isinstance(msg_content, list):
                text_parts = []
                for part in msg_content:
                    if hasattr(part, 'text'):
                        text_parts.append(part.text)
                    elif hasattr(part, 'content'):
                        text_parts.append(str(part.content))
                    elif isinstance(part, dict):
                        if 'text' in part:
                            text_parts.append(part['text'])
                        elif 'content' in part:
                            text_parts.append(str(part['content']))
                    elif isinstance(part, str):
                        text_parts.append(part)
                    else:
                        # Last resort - convert to string
                        text_parts.append(str(part))
                msg_content = '\n'.join(text_parts)
            elif not isinstance(msg_content, str):
                msg_content = str(msg_content) if msg_content else ''

            # Look for tool response messages
            if msg_role == 'tool':
                if debug:
                    print(f"[Aggregator Debug] Found tool message {i}, content length: {len(msg_content)}")
                try:
                    parsed = json.loads(msg_content)
                    tool_result = parsed
                    if debug:
                        print(f"[Aggregator Debug] Successfully parsed tool result from message {i}")
                except json.JSONDecodeError:
                    if msg_content.strip():
                        tool_result = {"raw": msg_content[:500]}

            # Capture the agent's final interpretation (assistant response)
            # Only overwrite if we have actual content and don't already have a good interpretation
            elif msg_role == 'assistant':
                if msg_content.strip() and len(msg_content.strip()) > len(agent_interpretation):
                    agent_interpretation = msg_content
                    if debug:
                        print(f"[Aggregator Debug] Updated interpretation from message {i}: {len(msg_content)} chars")

    # Fallback: try to extract from agent_response directly
    if tool_result is None and hasattr(result, 'agent_response'):
        agent_response = result.agent_response

        # Check for tool_calls or function_calls in the response
        if hasattr(agent_response, 'tool_calls') and agent_response.tool_calls:
            if debug:
                print(f"[Aggregator Debug] Found {len(agent_response.tool_calls)} tool_calls")
            for tool_call in agent_response.tool_calls:
                if hasattr(tool_call, 'result'):
                    try:
                        tool_result = json.loads(tool_call.result)
                        if debug:
                            print(f"[Aggregator Debug] Extracted result from tool_call")
                    except (json.JSONDecodeError, TypeError):
                        tool_result = {"raw": str(tool_call.result)[:500]}
                    break

    # Additional fallback: check for any JSON in agent interpretation
    if tool_result is None and agent_interpretation:
        # Try to find JSON blocks in the interpretation
        import re
        json_blocks = re.findall(r'```json\s*([\s\S]*?)\s*```', agent_interpretation)
        if debug and json_blocks:
            print(f"[Aggregator Debug] Found {len(json_blocks)} JSON blocks in interpretation")
        for block in json_blocks:
            try:
                tool_result = json.loads(block)
                break
            except json.JSONDecodeError:
                continue

    if debug:
        print(f"[Aggregator Debug] Final: tool_result={'Yes' if tool_result else 'No'}, interpretation={len(agent_interpretation)} chars")

    return {
        "executor_id": executor_id,
        "tool_result": tool_result,
        "interpretation": agent_interpretation
    }


class PRAnalysisAggregator(Executor):
    """Aggregator that collects and combines results from multiple agents.

    This executor is the final node in the workflow. It receives outputs
    from all upstream agents (CodeAnalyzer, SecurityScanner) and extracts
    the tool call results from their conversations to provide structured
    data for the markdown formatter.
    """

    @handler
    async def handle(self, results: List[Any], ctx: WorkflowContext[Dict[str, Any], Dict[str, Any]]):
        """Handle results from all agents and produce combined output.

        Args:
            results: List of AgentExecutorResponse from upstream agents
            ctx: Workflow context for yielding the final output
        """
        print(f"\n[Aggregator] Received {len(results)} results from agents")

        # Initialize output structure
        code_analysis = {}
        security_scan = {}
        agent_interpretations = {}

        for i, result in enumerate(results):
            # Extract tool results from the agent's conversation
            extracted = extract_tool_result_from_conversation(result)
            executor_id = extracted["executor_id"]
            tool_result = extracted["tool_result"]
            interpretation = extracted["interpretation"]

            # Log what we found
            if tool_result:
                print(f"[Aggregator] Extracted tool result from {executor_id}")
                if isinstance(tool_result, dict):
                    if 'files' in tool_result:
                        print(f"   - Code analysis: {len(tool_result.get('files', []))} files")
                    elif 'findings' in tool_result:
                        print(f"   - Security scan: {tool_result.get('summary', {}).get('total_issues', 'N/A')} issues")
            else:
                print(f"[Aggregator] No tool result found from {executor_id}, using fallback")

            # Determine which agent this is and store results appropriately
            executor_lower = executor_id.lower()

            if "code" in executor_lower or "analyzer" in executor_lower:
                if tool_result:
                    code_analysis = tool_result
                agent_interpretations["code_analyzer"] = interpretation
            elif "security" in executor_lower or "scanner" in executor_lower:
                if tool_result:
                    security_scan = tool_result
                agent_interpretations["security_scanner"] = interpretation
            else:
                # Unknown agent type - try to determine by result structure
                if tool_result:
                    if isinstance(tool_result, dict):
                        if 'findings' in tool_result or 'security' in str(tool_result.get('summary', {})).lower():
                            security_scan = tool_result
                        elif 'files' in tool_result:
                            code_analysis = tool_result

        # Try to load from cache if extraction failed
        if not code_analysis or not security_scan:
            print("[Aggregator] Attempting to load from cached tool results...")
            cached = load_cached_results()

            if not code_analysis and 'code_analysis' in cached:
                code_analysis = cached['code_analysis']
                print(f"[Aggregator] Using cached code analysis: {len(code_analysis.get('files', []))} files")

            if not security_scan and 'security_scan' in cached:
                security_scan = cached['security_scan']
                print(f"[Aggregator] Using cached security scan: {security_scan.get('summary', {}).get('total_issues', 0)} issues")

        # Provide fallback empty structures if still no results
        if not code_analysis:
            print("[Aggregator] Warning: No code analysis result extracted, using empty structure")
            code_analysis = {
                "files": [],
                "summary": {
                    "total_files": 0,
                    "total_additions": 0,
                    "total_deletions": 0,
                    "languages": [],
                    "categories": []
                }
            }

        if not security_scan:
            print("[Aggregator] Warning: No security scan result extracted, using empty structure")
            security_scan = {
                "findings": [],
                "summary": {
                    "total_issues": 0,
                    "high_severity": 0,
                    "medium_severity": 0,
                    "low_severity": 0
                }
            }

        # Build the combined output
        combined_output = {
            "code_analysis": code_analysis,
            "security_scan": security_scan,
            "agent_interpretations": agent_interpretations,
            "agent_count": len(results),
            "status": "completed"
        }

        # Log summary
        print(f"[Aggregator] Aggregation complete:")
        print(f"   - Code analysis: {len(code_analysis.get('files', []))} files analyzed")
        print(f"   - Security scan: {security_scan.get('summary', {}).get('total_issues', 0)} issues found")

        # Yield the combined output as the workflow result
        await ctx.yield_output(combined_output)
