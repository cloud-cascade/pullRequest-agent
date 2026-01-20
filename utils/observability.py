"""OpenTelemetry observability configuration for PR Agent.

Supports three backends:
- disabled: No tracing
- local: Sends traces to local Aspire dashboard via OTLP gRPC
- appinsights: Sends traces to Azure Application Insights
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def configure_observability(
    backend: Optional[str] = None,
    appinsights_connection_string: Optional[str] = None,
    otlp_endpoint: str = "http://localhost:4317",
    enable_sensitive_data: Optional[bool] = None,
) -> bool:
    """Configure OpenTelemetry observability based on backend selection.

    Args:
        backend: Tracing backend - "disabled", "local", or "appinsights".
                 If not provided, reads from TRACING_BACKEND env var.
        appinsights_connection_string: Azure App Insights connection string.
                                       If not provided, reads from environment.
        otlp_endpoint: OTLP endpoint for local backend (default: http://localhost:4317).
                       Can also be set via OTLP_ENDPOINT env var.
        enable_sensitive_data: Whether to log prompts/responses in traces.
                               If not provided, reads from ENABLE_SENSITIVE_DATA env var.

    Returns:
        True if observability was successfully configured, False otherwise.
    """
    # Resolve backend from environment if not provided
    if backend is None:
        backend = os.getenv("TRACING_BACKEND", "disabled").lower()

    # Resolve sensitive data setting from environment if not provided
    if enable_sensitive_data is None:
        enable_sensitive_data = os.getenv("ENABLE_SENSITIVE_DATA", "false").lower() == "true"

    if backend == "disabled":
        logger.info("Observability is disabled")
        print("   Observability: Disabled")
        return False

    if backend == "local":
        # Get OTLP endpoint from environment if not explicitly provided
        endpoint = os.getenv("OTLP_ENDPOINT", otlp_endpoint)
        return _configure_local_observability(endpoint, enable_sensitive_data)
    elif backend == "appinsights":
        # Get connection string from environment if not explicitly provided
        conn_str = appinsights_connection_string or _get_appinsights_connection_string()
        return _configure_appinsights_observability(conn_str, enable_sensitive_data)
    else:
        logger.warning(f"Unknown tracing backend: {backend}, observability disabled")
        print(f"   Warning: Unknown tracing backend '{backend}', observability disabled")
        return False


def _get_appinsights_connection_string() -> Optional[str]:
    """Get Application Insights connection string from environment.

    Checks environment variables in order:
    1. APPLICATIONINSIGHTS_CONNECTION_STRING
    2. APPLICATION_INSIGHTS_CONNECTION_STRING
    3. AZURE_MONITOR_CONNECTION_STRING

    Returns:
        Application Insights connection string or None if not found
    """
    return (
        os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING") or
        os.getenv("APPLICATION_INSIGHTS_CONNECTION_STRING") or
        os.getenv("AZURE_MONITOR_CONNECTION_STRING")
    )


def _configure_local_observability(otlp_endpoint: str, enable_sensitive_data: bool) -> bool:
    """Configure observability for local Aspire dashboard via OTLP gRPC.

    Args:
        otlp_endpoint: OTLP gRPC endpoint (e.g., http://localhost:4317)
        enable_sensitive_data: Whether to include prompts/responses in traces

    Returns:
        True if successfully configured, False otherwise.
    """
    try:
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    except ImportError as e:
        logger.error(f"OTLP exporters not available: {e}")
        print(f"   Error: OTLP exporters not installed. Run: pip install opentelemetry-exporter-otlp-proto-grpc")
        return False

    try:
        from agent_framework.observability import configure_otel_providers
    except ImportError:
        logger.error("agent_framework.observability not available")
        print("   Error: agent_framework.observability not available")
        return False

    try:
        exporters = [
            OTLPSpanExporter(endpoint=otlp_endpoint),
            OTLPLogExporter(endpoint=otlp_endpoint),
            OTLPMetricExporter(endpoint=otlp_endpoint),
        ]
        configure_otel_providers(
            exporters=exporters,
            enable_sensitive_data=enable_sensitive_data,
        )

        logger.info(f"Observability configured for local Aspire dashboard at {otlp_endpoint}")
        print(f"\n   Observability Configured Successfully")
        print(f"   - Backend: Local OTLP")
        print(f"   - Endpoint: {otlp_endpoint}")
        print(f"   - Aspire Dashboard: http://localhost:18888 (if running)")
        print(f"   - Sensitive Data: {'Enabled' if enable_sensitive_data else 'Disabled'}")
        print(f"   - Service Name: {os.getenv('OTEL_SERVICE_NAME', 'pr-agent')}")
        return True

    except Exception as e:
        logger.error(f"Error configuring local observability: {e}")
        print(f"   Error configuring local observability: {e}")
        return False


def _configure_appinsights_observability(
    connection_string: Optional[str],
    enable_sensitive_data: bool,
) -> bool:
    """Configure observability for Azure Application Insights using exporters directly.

    Uses Azure Monitor exporters directly instead of configure_azure_monitor()
    to avoid heavy auto-instrumentation that causes startup delays.

    Args:
        connection_string: Azure Application Insights connection string
        enable_sensitive_data: Whether to include prompts/responses in traces

    Returns:
        True if successfully configured, False otherwise.
    """
    if not connection_string:
        logger.warning("App Insights connection string not provided, observability disabled")
        print("   Warning: App Insights connection string not provided, observability disabled")
        return False

    try:
        from azure.monitor.opentelemetry.exporter import (
            AzureMonitorLogExporter,
            AzureMonitorMetricExporter,
            AzureMonitorTraceExporter,
        )
    except ImportError as e:
        logger.error(f"Azure Monitor exporters not available: {e}")
        print(f"   Error: Azure Monitor exporters not installed. Run: pip install azure-monitor-opentelemetry-exporter")
        return False

    try:
        from agent_framework.observability import configure_otel_providers
    except ImportError:
        logger.error("agent_framework.observability not available")
        print("   Error: agent_framework.observability not available")
        return False

    try:
        exporters = [
            AzureMonitorTraceExporter(connection_string=connection_string),
            AzureMonitorLogExporter(connection_string=connection_string),
            AzureMonitorMetricExporter(connection_string=connection_string),
        ]
        configure_otel_providers(
            exporters=exporters,
            enable_sensitive_data=enable_sensitive_data,
        )

        logger.info("Observability configured for Azure Application Insights")
        print(f"\n   Observability Configured Successfully")
        print(f"   - Backend: Azure Application Insights")
        print(f"   - Sensitive Data: {'Enabled' if enable_sensitive_data else 'Disabled'}")
        print(f"   - Service Name: {os.getenv('OTEL_SERVICE_NAME', 'pr-agent')}")
        return True

    except Exception as e:
        logger.error(f"Error configuring App Insights observability: {e}")
        print(f"   Error configuring App Insights observability: {e}")
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
