"""Observability configuration for PR Agent using Azure Monitor and Agent Framework.

This module provides centralized observability setup following the Microsoft
Agent Framework documentation:
https://learn.microsoft.com/en-us/agent-framework/user-guide/observability
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_appinsights_connection_string() -> Optional[str]:
    """Get Application Insights connection string from environment.

    Checks environment variables in order:
    1. APPLICATIONINSIGHTS_CONNECTION_STRING
    2. APPLICATION_INSIGHTS_CONNECTION_STRING
    3. AZURE_MONITOR_CONNECTION_STRING

    Returns:
        Application Insights connection string or None if not found
    """
    conn_str = (
        os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING") or
        os.getenv("APPLICATION_INSIGHTS_CONNECTION_STRING") or
        os.getenv("AZURE_MONITOR_CONNECTION_STRING")
    )

    if conn_str:
        logger.info("Loaded App Insights connection string from environment")

    return conn_str


def setup_pr_agent_observability(
    connection_string: Optional[str] = None,
    enable_live_metrics: bool = True,
    enable_sensitive_data: bool = False,
    otlp_endpoint: Optional[str] = None,
) -> bool:
    """Configure observability for PR Agent using Agent Framework's built-in setup.

    This uses the agent_framework.observability.setup_observability() function which
    handles both Azure Application Insights and OTLP endpoints (e.g., Aspire Dashboard).

    Args:
        connection_string: Azure Application Insights connection string.
                          If not provided, checks environment variables.
        enable_live_metrics: Enable live metrics streaming (currently not used by agent_framework).
                            Default is True for compatibility.
        enable_sensitive_data: Include sensitive data (prompts/responses) in telemetry.
                              Default is False for security. Only enable in dev/test.
        otlp_endpoint: OTLP endpoint for local tracing (e.g., "http://localhost:4317" for Aspire Dashboard).
                      If not provided, checks OTLP_ENDPOINT env var.

    Returns:
        True if observability was successfully configured, False otherwise.

    Example:
        >>> setup_pr_agent_observability(
        ...     connection_string="InstrumentationKey=...",
        ...     enable_live_metrics=True,
        ...     enable_sensitive_data=False,
        ... )
    """
    # Get connection string
    conn_str = connection_string or get_appinsights_connection_string()
    
    # Get OTLP endpoint from parameter or environment
    otlp = otlp_endpoint or os.getenv("OTLP_ENDPOINT")

    # Check if we have at least one observability endpoint
    if not conn_str and not otlp:
        logger.info("No observability endpoints configured (no connection string or OTLP endpoint)")
        print("   No observability endpoints configured")
        return False

    try:
        # Import Agent Framework's setup function
        from agent_framework.observability import setup_observability
    except ImportError:
        logger.warning("agent_framework.observability not available. Skipping observability setup.")
        print("   Warning: agent_framework.observability not available")
        return False

    try:
        # Use Agent Framework's built-in observability setup
        # This handles both Azure Monitor and OTLP exporters internally
        setup_observability(
            applicationinsights_connection_string=conn_str,
            otlp_endpoint=otlp,
            enable_sensitive_data=enable_sensitive_data,
        )

        print("\n   Observability Configured Successfully")
        
        if conn_str:
            print(f"   - Azure Application Insights: Connected")
            # Note: enable_live_metrics is not directly supported by agent_framework.setup_observability
            # but the connection will still provide telemetry data
        
        if otlp:
            print(f"   - OTLP Endpoint: {otlp}")
            print(f"   - Aspire Dashboard: Available at http://localhost:18888 (if running)")
        
        print(f"   - Sensitive Data: {'Enabled' if enable_sensitive_data else 'Disabled (Secure)'}")
        print(f"   - Service Name: {os.getenv('OTEL_SERVICE_NAME', 'pr-agent')}")

        return True

    except Exception as e:
        logger.error(f"Error configuring observability: {e}")
        print(f"   Error configuring observability: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_tracer(name: str = "pr-agent"):
    """Get an OpenTelemetry tracer for manual instrumentation.

    Args:
        name: Name for the tracer (default: "pr-agent")

    Returns:
        OpenTelemetry tracer instance
    """
    try:
        from agent_framework.observability import get_tracer as af_get_tracer
        return af_get_tracer(name)
    except ImportError:
        from opentelemetry import trace
        return trace.get_tracer(name)


def get_current_trace_context() -> Optional[dict]:
    """Get the current OpenTelemetry trace context.

    Useful for correlating logs and traces across services.

    Returns:
        Dictionary with trace_id and span_id if available, None otherwise.
    """
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            ctx = span.get_span_context()
            return {
                "trace_id": format(ctx.trace_id, "032x"),
                "span_id": format(ctx.span_id, "016x"),
                "trace_flags": ctx.trace_flags,
            }
    except Exception:
        pass

    return None
