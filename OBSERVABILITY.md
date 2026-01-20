# Azure Monitor Observability Setup

This document explains how to use the Azure Monitor observability setup for the PR Agent.

## Overview

The PR Agent now uses **Azure Monitor OpenTelemetry** for comprehensive observability, following Microsoft's recommended patterns. This provides automatic instrumentation for:

- Agent invocations and workflow execution
- Azure OpenAI API calls
- Tool executions
- HTTP requests
- Custom application traces

## Quick Start

### 1. Configuration

The observability is configured via environment variables in `.env`:

```bash
# Required: Application Insights connection string
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...;IngestionEndpoint=...

# Optional: Service identification
OTEL_SERVICE_NAME=pr-agent
OTEL_SERVICE_VERSION=1.0.0
ENVIRONMENT=dev

# Optional: Feature toggles
AZURE_MONITOR_ENABLE_LIVE_METRICS=true
ENABLE_INSTRUMENTATION=true
ENABLE_SENSITIVE_DATA=false  # Keep false for security!
```

### 2. Running the Agent

The observability is automatically configured when you run the PR Agent:

```bash
cd .github/scripts
python3 pr-agent.py
```

You'll see output like:

```
🔍 Azure Monitor Observability Configured Successfully
   ✓ Service Name: pr-agent
   ✓ Live Metrics: Enabled
   ✓ Sensitive Data: Disabled (Secure)
   ✓ Agent Framework Instrumentation: Enabled
   ✓ Service Version: 1.0.0
   ✓ Environment: dev
```

### 3. Testing the Setup

Run the test script to verify everything is configured correctly:

```bash
cd .github/scripts
python3 test_observability.py
```

## Architecture

### Automatic Instrumentation

The following is automatically instrumented by Azure Monitor OpenTelemetry:

1. **Agent Framework Operations**
   - `invoke_agent <agent_name>` - Agent execution spans
   - Workflow state transitions
   - Executor fan-out/fan-in patterns

2. **Azure OpenAI Calls**
   - `chat <model_name>` - LLM interaction spans
   - Token usage metrics
   - Request/response timing

3. **Tool Executions**
   - `execute_tool <function_name>` - Tool invocation spans
   - Tool-specific attributes

4. **HTTP Requests**
   - GitHub API calls
   - External service calls

### Custom Instrumentation

You can add custom spans and metrics using the observability utilities:

#### Creating Custom Spans

```python
from utils.observability import create_custom_span

# Method 1: Context manager
with create_custom_span("my_operation", {"key": "value"}) as span:
    # Your code here
    result = do_something()
    span.set_attribute("result", result)
```

#### Getting Trace Context

Useful for correlating logs with traces:

```python
from utils.observability import get_current_trace_context

context = get_current_trace_context()
if context:
    print(f"Trace ID: {context['trace_id']}")
    print(f"Span ID: {context['span_id']}")
```

## Environment Variables Reference

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Azure Monitor connection string | `InstrumentationKey=...;IngestionEndpoint=...` |

### Optional - Service Identification

| Variable | Default | Description |
|----------|---------|-------------|
| `OTEL_SERVICE_NAME` | `pr-agent` | Name of the service in telemetry |
| `OTEL_SERVICE_VERSION` | None | Version tag for the service |
| `OTEL_SERVICE_NAMESPACE` | None | Namespace for multi-service apps |
| `ENVIRONMENT` | None | Deployment environment (dev/qa/prod) |

### Optional - Feature Toggles

| Variable | Default | Description |
|----------|---------|-------------|
| `AZURE_MONITOR_ENABLE_LIVE_METRICS` | `true` | Enable live metrics streaming |
| `ENABLE_INSTRUMENTATION` | `true` | Enable Agent Framework telemetry |
| `ENABLE_SENSITIVE_DATA` | `false` | Include sensitive data in telemetry (⚠️ security risk) |

## Telemetry Data

### What Gets Tracked

#### Traces (Spans)
- **Agent Execution**: Each agent invocation creates a span with agent name, inputs, outputs
- **LLM Calls**: Azure OpenAI requests with model, prompt tokens, completion tokens
- **Tool Executions**: Each tool call with function name, parameters, results
- **Workflow Steps**: Dispatcher fan-out, agent processing, aggregator fan-in

#### Metrics
- `gen_ai.client.operation.duration` - LLM call duration
- `gen_ai.client.token.usage` - Token consumption per call
- `agent_framework.function.invocation.duration` - Tool execution time
- Custom metrics (if added)

#### Logs
- Application logs with correlation to traces
- Error stack traces
- Workflow execution events

### Viewing Telemetry

1. **Azure Portal**
   - Go to your Application Insights resource
   - Navigate to "Transaction search" for traces
   - Use "Live Metrics" for real-time monitoring
   - Check "Failures" for error analysis

2. **Kusto Queries (Log Analytics)**

   ```kusto
   // View all agent invocations
   traces
   | where operation_Name startswith "invoke_agent"
   | project timestamp, operation_Name, message, customDimensions
   | order by timestamp desc
   
   // View LLM token usage
   dependencies
   | where target == "Azure OpenAI"
   | summarize TotalTokens = sum(toint(customDimensions.["gen_ai.usage.input_tokens"]) + toint(customDimensions.["gen_ai.usage.output_tokens"]))
       by bin(timestamp, 1h)
   
   // Error analysis
   exceptions
   | where timestamp > ago(1d)
   | summarize count() by operation_Name, problemId
   | order by count_ desc
   ```

## Security Considerations

### Sensitive Data

**IMPORTANT**: Keep `ENABLE_SENSITIVE_DATA=false` in production!

When enabled, sensitive data logging includes:
- Full prompt content
- API responses
- User inputs
- Code snippets

This data is sent to Azure Monitor and stored for the configured retention period.

### Recommended Settings

**Development**:
```bash
ENABLE_SENSITIVE_DATA=false  # Or true if debugging specific issues
ENVIRONMENT=dev
```

**Production**:
```bash
ENABLE_SENSITIVE_DATA=false  # MUST be false
ENVIRONMENT=prod
```

## Troubleshooting

### Issue: "azure-monitor-opentelemetry not installed"

**Solution**:
```bash
pip install azure-monitor-opentelemetry
```

### Issue: "No Azure Monitor connection string provided"

**Solution**: Set the connection string in `.env`:
```bash
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...
```

Get the connection string from Azure Portal → Application Insights → Properties

### Issue: No telemetry appearing in Azure Monitor

**Checklist**:
1. ✓ Connection string is correct
2. ✓ Application Insights resource exists and is active
3. ✓ Network connectivity to Azure (check firewall/proxy)
4. ✓ Wait 2-5 minutes for telemetry to propagate
5. ✓ Check Application Insights "Failures" for ingestion errors

### Issue: LSP errors about agent_framework

These are false positives from the language server. The code works correctly at runtime.

## Advanced Usage

### Custom Metrics

```python
from opentelemetry import metrics

meter = metrics.get_meter(__name__)
counter = meter.create_counter(
    "pr_analysis.files_processed",
    description="Number of files processed in PR analysis"
)

# Increment counter
counter.add(1, {"status": "success", "file_type": "python"})
```

### Custom Attributes

Add custom attributes to the current span:

```python
from opentelemetry import trace

span = trace.get_current_span()
span.set_attribute("custom.pr_number", pr_number)
span.set_attribute("custom.repository", repo_name)
```

### Distributed Tracing

The OpenTelemetry context is automatically propagated across:
- Async function calls
- Agent→Tool calls
- HTTP requests (with proper headers)

## Module Reference

### `utils/observability.py`

#### Functions

**`setup_azure_monitor_observability(connection_string, enable_live_metrics, enable_sensitive_data, service_name)`**
- Main setup function
- Returns: `bool` (success/failure)

**`create_resource()`**
- Creates OpenTelemetry resource with service metadata
- Returns: `Resource` object

**`enable_instrumentation(enable_sensitive_data)`**
- Activates Agent Framework instrumentation
- Sets environment variables

**`create_custom_span(name, attributes)`**
- Creates a custom span for manual instrumentation
- Returns: Context manager

**`get_current_trace_context()`**
- Gets current trace ID and span ID
- Returns: `dict` or `None`

## Examples

### Example 1: Basic Usage (Automatic)

```python
from utils.observability import setup_azure_monitor_observability

# Setup once at application start
setup_azure_monitor_observability(
    connection_string="InstrumentationKey=...",
    enable_live_metrics=True,
    enable_sensitive_data=False,
)

# Everything else is automatic!
# Agent calls, LLM interactions, tool executions are all traced
```

### Example 2: Custom Spans

```python
from utils.observability import create_custom_span

def process_pr_files(files):
    with create_custom_span("process_pr_files", {"file_count": len(files)}):
        for file in files:
            with create_custom_span("process_file", {"filename": file.name}):
                analyze_file(file)
```

### Example 3: Correlated Logging

```python
from utils.observability import get_current_trace_context

def log_with_trace(message):
    context = get_current_trace_context()
    if context:
        print(f"[TraceID: {context['trace_id']}] {message}")
    else:
        print(message)
```

## Migration from Old Setup

The new observability module is **backward compatible**. The old `setup_observability()` function still works:

```python
# Old code (still works)
from agent_framework.observability import setup_observability
setup_observability(
    enable_sensitive_data=False,
    applicationinsights_connection_string=conn_str,
)

# New code (recommended)
from utils.observability import setup_azure_monitor_observability
setup_azure_monitor_observability(
    connection_string=conn_str,
    enable_live_metrics=True,
    enable_sensitive_data=False,
)
```

## Support

For issues or questions:
1. Run `python3 test_observability.py` to diagnose configuration issues
2. Check Azure Monitor "Failures" blade for ingestion errors
3. Review Application Insights logs for error traces

---

**Last Updated**: 2026-01-18  
**Version**: 1.0.0
