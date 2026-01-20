# PR Agent - AI-Powered Pull Request Analysis

An intelligent PR review agent built with Microsoft Agent Framework that automatically analyzes code changes and provides detailed, human-readable feedback.

## Features

- **Multi-Language Support**: Analyzes Python, JavaScript, TypeScript, Java, C#, Go, Bicep, Terraform, SQL, and more
- **Intelligent Analysis**: Uses Azure OpenAI (GPT-4) for semantic code understanding
- **Security Scanning**: Detects hardcoded secrets, SQL injection, XSS, and other vulnerabilities
- **Executive Summaries**: Provides business-focused summaries for quick PR understanding
- **Detailed Per-File Analysis**: Explains what each file does and why changes matter
- **Parallel Processing**: Uses fan-out/fan-in workflow pattern for efficient analysis
- **Observability**: Built-in Azure Application Insights integration for monitoring

## Architecture

### Microsoft Agent Framework
The PR agent is built on the [Microsoft Agent Framework](https://microsoft.github.io/agent-framework/), providing:
- Enterprise-grade AI orchestration
- Tool calling capabilities
- Workflow management (fan-out/fan-in pattern)
- Built-in observability support

### Components

```
┌─────────────────────────────────────────────────────────┐
│                     PR Agent Workflow                    │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────┐      ┌─────────────────┐                  │
│  │          │      │   Code Analyzer │                  │
│  │ Dispatch ├─────►│      Agent      │────┐             │
│  │          │      └─────────────────┘    │             │
│  └──────────┘                             │             │
│       │                                    ▼             │
│       │          ┌─────────────────┐  ┌──────────┐      │
│       └─────────►│Security Scanner ├─►│Aggregator│      │
│                  │      Agent      │  └──────────┘      │
│                  └─────────────────┘                     │
└─────────────────────────────────────────────────────────┘
```

**Agents:**
- `CodeAnalyzerAgent` - Analyzes code structure, quality, and patterns
- `SecurityScannerAgent` - Scans for security vulnerabilities

**Executors:**
- `PRAnalysisDispatcher` - Distributes work to agents (fan-out)
- `PRAnalysisAggregator` - Combines agent results (fan-in)

**Tools:**
- `code_analyzer` - Multi-language code parsing and categorization
- `generic_security_scanner` - Secret detection and vulnerability scanning
- `github_api` - PR diff retrieval and comment posting

## Setup

### Prerequisites

- Python 3.11+
- Azure OpenAI resource with GPT-4 deployment
- GitHub repository with Actions enabled
- (Optional) Azure Application Insights for observability

### Installation

1. **Install dependencies:**
   ```bash
   cd .github/scripts
   pip install -r requirements.txt
   ```

2. **Configure GitHub Secrets:**
   
   Navigate to your repository → Settings → Secrets and variables → Actions, and add:

   **Required:**
   - `AZURE_OPENAI_ENDPOINT` - Your Azure OpenAI endpoint (e.g., `https://your-resource.openai.azure.com/`)
   - `AZURE_OPENAI_API_KEY` - Your Azure OpenAI API key
   - `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` - Your GPT-4 deployment name (e.g., `gpt-4o`)

   **Optional (for observability):**
   - `APPLICATIONINSIGHTS_CONNECTION_STRING` - Azure Application Insights connection string
     - Format: `InstrumentationKey=<guid>;IngestionEndpoint=https://<region>.in.applicationinsights.azure.com/;LiveEndpoint=https://<region>.livediagnostics.monitor.azure.com/`
     - Get this from Azure Portal → Application Insights → Properties → Connection String

3. **Configure the workflow:**
   
   The workflow `.github/workflows/pr-agent.yml` is already configured to run on PRs to main, develop, release, and feature branches.

## Usage

### Automatic PR Analysis

The agent automatically runs when:
- A new PR is opened
- Commits are pushed to an existing PR
- A PR is reopened

### Manual Testing

You can test the agent locally:

```bash
cd .github/scripts

# Set environment variables
export GITHUB_TOKEN="your-github-token"
export GITHUB_REPOSITORY="owner/repo"
export PR_NUMBER="123"
export AZURE_OPENAI_ENDPOINT="your-endpoint"
export AZURE_OPENAI_API_KEY="your-key"
export AZURE_OPENAI_CHAT_DEPLOYMENT_NAME="gpt-4o"

# Optional: Enable observability
export APPLICATIONINSIGHTS_CONNECTION_STRING="your-connection-string"
export OTEL_SERVICE_NAME="pr-agent-local"

# Run the agent
python pr-agent.py
```

## Observability

The PR agent includes built-in observability using OpenTelemetry and Azure Application Insights.

### What Gets Traced

**Spans:**
- `invoke_agent <agent_name>` - Top-level span for each agent invocation
- `chat <model_name>` - Azure OpenAI chat completions
- `execute_tool <function_name>` - Tool/function executions

**Metrics:**
- `gen_ai.client.operation.duration` - LLM call duration
- `gen_ai.client.token.usage` - Token consumption
- `agent_framework.function.invocation.duration` - Tool execution time

**Logs:**
- Agent execution logs
- Error traces
- Workflow events

### Setting Up Application Insights

1. **Create Application Insights resource:**
   ```bash
   az monitor app-insights component create \
     --app pr-agent-insights \
     --location eastus \
     --resource-group your-rg \
     --workspace your-log-analytics-workspace
   ```

2. **Get connection string:**
   ```bash
   az monitor app-insights component show \
     --app pr-agent-insights \
     --resource-group your-rg \
     --query connectionString -o tsv
   ```

3. **Add to GitHub Secrets:**
   - Secret name: `APPLICATIONINSIGHTS_CONNECTION_STRING`
   - Value: The connection string from step 2

### Viewing Telemetry

**Azure Portal:**
1. Navigate to your Application Insights resource
2. Click **Transaction search** to see individual traces
3. Click **Application map** to visualize component dependencies
4. Use **Logs** to query custom metrics

**Example Kusto Query:**
```kql
traces
| where timestamp > ago(1h)
| where customDimensions.["gen_ai.operation.name"] == "invoke_agent"
| project timestamp, message, customDimensions
| order by timestamp desc
```

### Sensitive Data Logging

By default, sensitive data (prompts, responses, function arguments) is **NOT** logged.

To enable for debugging (dev/test only):
```bash
export ENABLE_SENSITIVE_DATA=true
```

⚠️ **Warning:** Never enable sensitive data logging in production!

### Local Development with Aspire Dashboard

For local testing without Azure setup:

```bash
# Run Aspire Dashboard
docker run --rm -it -d \
    -p 18888:18888 \
    -p 4317:18889 \
    --name aspire-dashboard \
    mcr.microsoft.com/dotnet/aspire-dashboard:latest

# Configure environment
export ENABLE_INSTRUMENTATION=true
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Run your agent
python pr-agent.py

# View telemetry at http://localhost:18888
```

## Configuration

### Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `GITHUB_TOKEN` | Yes | GitHub Actions token | Auto-provided |
| `GITHUB_REPOSITORY` | Yes | Repository (owner/repo) | Auto-provided |
| `AZURE_OPENAI_ENDPOINT` | Yes | Azure OpenAI endpoint URL | - |
| `AZURE_OPENAI_API_KEY` | Yes | Azure OpenAI API key | - |
| `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` | Yes | GPT-4 deployment name | - |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | No | App Insights connection string | - |
| `ENABLE_SENSITIVE_DATA` | No | Log prompts/responses | `false` |
| `OTEL_SERVICE_NAME` | No | Service name for traces | `agent_framework` |

### File Limits

To prevent token overflow:
- Maximum files analyzed: **50**
- If a PR has more files, only the first 50 are analyzed

Adjust in `pr-agent.py`:
```python
MAX_FILES_TO_ANALYZE = 50  # Change this value
```

## Output Format

The agent posts a PR comment with:

### 1. Executive Summary
- Business-focused overview
- Architecture highlights
- Key capabilities
- Reviewer guidance with approval recommendation

### 2. Detailed Changes
Per-file breakdown with:
- What the file does
- Why changes matter
- Key functionality

### 3. Code Analysis
- Files changed by language/category
- Notable additions (classes, functions)
- Line change statistics

### 4. Security Scan
- Severity-classified issues (HIGH/MEDIUM/LOW)
- Location and context
- Remediation recommendations

## Troubleshooting

### "APPLICATIONINSIGHTS_CONNECTION_STRING not set"
This is a warning, not an error. Observability is optional. To enable it, add the connection string to GitHub Secrets.

### "Missing Azure OpenAI configuration"
Ensure all required secrets are set:
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`

### "Failed to post comment to PR"
Check that:
- The workflow has `pull-requests: write` permission
- `GITHUB_TOKEN` has not expired

### High token usage
- Reduce `MAX_FILES_TO_ANALYZE`
- Filter out large generated files in `tools/code_analyzer.py`

## Cost Estimation

**Azure OpenAI (GPT-4o):**
- Average tokens per PR: 8,000 - 15,000
- Cost per 1K tokens (input): $0.005
- Cost per 1K tokens (output): $0.015
- **Estimated cost per PR: $0.10 - $0.25**

**Application Insights:**
- Free tier: 5 GB/month
- Standard tier: $2.30/GB after free tier
- **Estimated cost: $0 - $10/month** (depending on PR volume)

## Development

### Project Structure

```
.github/scripts/
├── pr-agent.py              # Main orchestrator
├── requirements.txt         # Python dependencies
├── agents/                  # AI agents
│   ├── code_analyzer_agent.py
│   └── security_scanner_agent.py
├── executors/               # Workflow executors
│   ├── dispatcher.py
│   └── aggregator.py
├── tools/                   # Analysis tools
│   ├── code_analyzer.py
│   ├── generic_security_scanner.py
│   └── github_api.py
└── utils/                   # Utilities
    ├── markdown_formatter.py
    └── bicep_utils.py
```

### Adding New Languages

Edit `tools/code_analyzer.py`:

```python
LANGUAGE_EXTENSIONS = {
    'rust': ['.rs'],          # Add your language
    # ...
}
```

### Adding Security Rules

Edit `tools/generic_security_scanner.py`:

```python
LANGUAGE_SECURITY_PATTERNS = {
    'rust': [
        (r'unsafe\s+{', 'Unsafe block', 'MEDIUM', 'Review unsafe code carefully'),
    ],
}
```

## References

- [Microsoft Agent Framework Documentation](https://microsoft.github.io/agent-framework/)
- [Azure OpenAI Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
- [Azure Application Insights](https://learn.microsoft.com/en-us/azure/azure-monitor/app/app-insights-overview)

## License

This project inherits the license from the parent repository.
