"""Markdown formatter for PR comments - supports multiple languages."""

from datetime import datetime
from typing import Dict, List


def generate_file_description(file_info: Dict) -> str:
    """Generate a human-readable description of what a file does.
    
    Args:
        file_info: Dictionary with file analysis data
        
    Returns:
        A description string explaining the file's purpose
    """
    filename = file_info.get('filename', '')
    status = file_info.get('status', 'modified')
    language = file_info.get('language', 'unknown')
    additions = file_info.get('additions', 0)
    deletions = file_info.get('deletions', 0)
    functions_added = file_info.get('functions_added', [])
    classes_added = file_info.get('classes_added', [])
    category = file_info.get('category', 'unknown')
    patch = file_info.get('patch', '')
    
    # Determine status label
    status_label = {
        'added': 'New file',
        'modified': 'Modified',
        'removed': 'Deleted',
        'renamed': 'Renamed'
    }.get(status, 'Changed')
    
    # Generate description based on file type and content
    description = ""
    details = []
    
    filename_lower = filename.lower()
    
    # =========================================================================
    # AGENTS
    # =========================================================================
    if '/agents/' in filename and language == 'python':
        if 'code_analyzer' in filename_lower:
            description = "Python agent for analyzing code changes across multiple languages."
            details.append("Uses Azure OpenAI to understand code semantics and patterns")
            details.append("Provides insights on code quality, complexity, and best practices")
        elif 'security_scanner' in filename_lower:
            description = "Python agent for security vulnerability detection."
            details.append("Scans for hardcoded secrets, SQL injection, XSS, and other vulnerabilities")
            details.append("Provides severity classification (HIGH/MEDIUM/LOW) with recommendations")
        elif 'diff_analyzer' in filename_lower:
            description = "Python agent for analyzing Bicep infrastructure diffs."
            details.append("Specializes in Azure resource changes and IaC best practices")
        elif '__init__' in filename_lower:
            description = "Module initialization for agents package."
            details.append("Exports agent factory functions for workflow integration")
        else:
            agent_name = filename.split('/')[-1].replace('.py', '').replace('_', ' ').title()
            description = f"Python agent: {agent_name}."
            if classes_added:
                details.append(f"Implements: {', '.join(classes_added)}")
    
    # =========================================================================
    # EXECUTORS
    # =========================================================================
    elif '/executors/' in filename and language == 'python':
        if 'dispatcher' in filename_lower:
            description = "Workflow dispatcher for fan-out pattern."
            details.append("Distributes analysis requests to multiple agents in parallel")
            details.append("Entry point for the PR analysis workflow")
        elif 'aggregator' in filename_lower:
            description = "Workflow aggregator for fan-in pattern."
            details.append("Collects and combines results from all agents")
            details.append("Produces unified output for PR comment generation")
        elif '__init__' in filename_lower:
            description = "Module initialization for executors package."
            details.append("Exports dispatcher and aggregator classes")
        else:
            description = "Workflow executor component."
            if classes_added:
                details.append(f"Implements: {', '.join(classes_added)}")
    
    # =========================================================================
    # TOOLS
    # =========================================================================
    elif '/tools/' in filename and language == 'python':
        if 'code_analyzer' in filename_lower:
            description = "Multi-language code analysis tool."
            details.append("Supports 30+ languages including Python, JavaScript, TypeScript, Java, Go, Bicep, Terraform")
            details.append("Extracts functions, classes, and categorizes changes")
        elif 'security_scanner' in filename_lower or 'generic_security' in filename_lower:
            description = "Security scanning tool for vulnerability detection."
            details.append("Detects hardcoded secrets, API keys, and credentials")
            details.append("Language-specific vulnerability patterns (eval, SQL injection, XSS)")
        elif 'github_api' in filename_lower:
            description = "GitHub API integration utilities."
            details.append("Fetches PR diffs and file changes")
            details.append("Posts analysis comments to Pull Requests")
        elif 'diff_analyzer' in filename_lower:
            description = "Bicep infrastructure diff analysis tool."
            details.append("Parses Azure resource changes from Bicep files")
        elif 'bicep_parser' in filename_lower:
            description = "Bicep file parser for Azure infrastructure."
            details.append("Extracts resources, parameters, and modules from Bicep templates")
        elif '__init__' in filename_lower:
            description = "Module initialization for tools package."
            details.append("Exports tool functions for agent use")
        else:
            tool_name = filename.split('/')[-1].replace('.py', '').replace('_', ' ').title()
            description = f"Utility tool: {tool_name}."
    
    # =========================================================================
    # UTILS
    # =========================================================================
    elif '/utils/' in filename and language == 'python':
        if 'markdown_formatter' in filename_lower:
            description = "Markdown formatting utilities for PR comments."
            details.append("Generates executive summaries and detailed file analysis")
            details.append("Formats security findings with severity indicators")
            details.append("Creates collapsible sections for better readability")
        elif 'bicep_utils' in filename_lower:
            description = "Bicep-specific utility functions."
            details.append("Helpers for parsing and analyzing Azure Bicep templates")
        elif '__init__' in filename_lower:
            description = "Module initialization for utils package."
        else:
            util_name = filename.split('/')[-1].replace('.py', '').replace('_', ' ').title()
            description = f"Utility module: {util_name}."
    
    # =========================================================================
    # MAIN SCRIPTS
    # =========================================================================
    elif 'pr-agent.py' in filename_lower or 'pr_agent.py' in filename_lower:
        description = "Main PR analysis orchestrator script."
        details.append("Coordinates the multi-agent workflow using Microsoft Agent Framework")
        details.append("Fetches PR data, runs analysis, and posts results as comments")
        details.append("Implements fan-out/fan-in pattern for parallel agent execution")
    
    # =========================================================================
    # WORKFLOWS
    # =========================================================================
    elif '.github/workflows' in filename:
        workflow_name = filename.split('/')[-1].replace('.yml', '').replace('.yaml', '')
        if 'pr-agent' in filename_lower or 'pr_agent' in filename_lower:
            description = f"GitHub Actions workflow: `{workflow_name}`."
            details.append("Triggers on Pull Request events")
            details.append("Runs AI-powered PR analysis and posts review comments")
        elif 'deploy' in filename_lower:
            description = f"GitHub Actions deployment workflow: `{workflow_name}`."
            details.append("Handles infrastructure deployment to Azure environments")
            if 'eventhub' in filename_lower:
                details.append("Deploys Event Hub resources across dev/qa/prod")
        else:
            description = f"GitHub Actions workflow: `{workflow_name}`."
    
    # =========================================================================
    # BICEP (Infrastructure as Code)
    # =========================================================================
    elif language == 'bicep' or filename.endswith('.bicep'):
        resource_types = []
        patch_lower = patch.lower() if patch else ''
        
        if 'eventhub' in filename_lower or 'microsoft.eventhub' in patch_lower:
            resource_types.append("Event Hub")
        if 'functionapp' in filename_lower or 'function' in filename_lower or 'microsoft.web/sites' in patch_lower:
            resource_types.append("Function App")
        if 'storage' in filename_lower or 'microsoft.storage' in patch_lower:
            resource_types.append("Storage Account")
        if 'vnet' in filename_lower or 'network' in filename_lower or 'microsoft.network' in patch_lower:
            resource_types.append("Virtual Network")
        if 'keyvault' in filename_lower or 'microsoft.keyvault' in patch_lower:
            resource_types.append("Key Vault")
        if 'privateendpoint' in filename_lower:
            resource_types.append("Private Endpoint")
        
        if '/modules/' in filename:
            module_name = filename.split('/')[-2] if filename.endswith('main.bicep') else filename.split('/')[-1].replace('.bicep', '')
            if resource_types:
                description = f"Bicep module for {', '.join(resource_types)}."
            else:
                description = f"Bicep module: `{module_name}`."
            details.append("Reusable infrastructure component for Azure deployments")
        else:
            if resource_types:
                description = f"Azure Bicep template for {', '.join(resource_types)}."
            else:
                description = "Azure Bicep infrastructure template."
    
    # =========================================================================
    # PARAMETER FILES
    # =========================================================================
    elif '/parameters/' in filename or filename.endswith('.parameters.json'):
        env_name = filename.split('/')[-1].replace('.json', '').replace('.parameters', '')
        description = f"Parameter file for `{env_name}` environment."
        details.append("Contains environment-specific configuration values")
        if 'dev' in env_name.lower():
            details.append("Development environment settings")
        elif 'qa' in env_name.lower() or 'test' in env_name.lower():
            details.append("QA/Test environment settings")
        elif 'prod' in env_name.lower():
            details.append("Production environment settings - review carefully")
    
    # =========================================================================
    # CONFIGURATION FILES
    # =========================================================================
    elif filename == 'requirements.txt' or filename.endswith('/requirements.txt'):
        description = "Python dependencies file."
        details.append("Lists required packages for the PR agent")
    elif filename.endswith('.env') or filename.endswith('.env.example'):
        description = "Environment variables configuration."
        details.append("Template for required environment variables")
    elif 'pyproject.toml' in filename:
        description = "Python project configuration."
        details.append("Defines project metadata, dependencies, and build settings")
    elif 'package.json' in filename:
        description = "Node.js project configuration."
        details.append("Defines project dependencies and scripts")
    
    # =========================================================================
    # DOCUMENTATION
    # =========================================================================
    elif filename.endswith('.md'):
        doc_name = filename.split('/')[-1].replace('.md', '')
        if 'readme' in filename_lower:
            description = "Project documentation (README)."
            details.append("Describes project setup, usage, and configuration")
        else:
            description = f"Documentation: `{doc_name}`."
    
    # =========================================================================
    # TEST FILES
    # =========================================================================
    elif '/test' in filename_lower or 'test_' in filename_lower or '_test.' in filename_lower:
        description = "Test file."
        if functions_added:
            details.append(f"Test functions: {', '.join(functions_added[:5])}")
    
    # =========================================================================
    # GENERIC FALLBACK
    # =========================================================================
    else:
        if language and language != 'unknown':
            description = f"{language.title()} source file."
        else:
            description = "Source file."
        
        if classes_added:
            details.append(f"New classes: {', '.join(classes_added[:3])}")
        if functions_added:
            details.append(f"New functions: {', '.join(functions_added[:3])}")
    
    return status_label, description, details


def format_detailed_changes(files: List[Dict]) -> str:
    """Format detailed per-file change descriptions.
    
    Args:
        files: List of file analysis dictionaries
        
    Returns:
        Markdown-formatted detailed changes section
    """
    if not files:
        return ""
    
    md = "## 📝 Detailed Changes\n\n"
    
    # Group files by directory for better organization
    files_by_dir = {}
    for f in files:
        filename = f.get('filename', '')
        parts = filename.rsplit('/', 1)
        if len(parts) == 2:
            directory = parts[0]
        else:
            directory = '(root)'
        
        if directory not in files_by_dir:
            files_by_dir[directory] = []
        files_by_dir[directory].append(f)
    
    # Sort directories for consistent output
    sorted_dirs = sorted(files_by_dir.keys())
    
    for directory in sorted_dirs:
        dir_files = files_by_dir[directory]
        
        for file_info in dir_files:
            filename = file_info.get('filename', 'Unknown')
            additions = file_info.get('additions', 0)
            deletions = file_info.get('deletions', 0)
            
            status_label, description, details = generate_file_description(file_info)
            
            # File header
            md += f"### `{filename}`\n"
            md += f"**{status_label}** (+{additions}/-{deletions}): {description}\n"
            
            # Detail bullets
            if details:
                for detail in details:
                    md += f"- {detail}\n"
            
            md += "\n"
    
    return md


def format_executive_summary(analysis_result: Dict, security_result: Dict) -> str:
    """Generate a human-readable executive summary of the PR changes.
    
    This creates a concise, easy-to-understand overview that tells PR reviewers
    exactly what this PR does, why it matters, and whether it's ready to merge.
    
    Args:
        analysis_result: Dictionary with code analysis results
        security_result: Dictionary with security scan results
        
    Returns:
        Markdown-formatted executive summary
    """
    summary = analysis_result.get('summary', {})
    files = analysis_result.get('files', [])
    by_category = analysis_result.get('files_by_category', {})
    by_language = analysis_result.get('files_by_language', {})
    
    total_files = summary.get('total_files', 0)
    total_additions = summary.get('total_additions', 0)
    total_deletions = summary.get('total_deletions', 0)
    languages = summary.get('languages', [])
    
    security_summary = security_result.get('summary', {})
    total_issues = security_summary.get('total_issues', 0)
    high_issues = security_summary.get('high_severity', 0)
    medium_issues = security_summary.get('medium_severity', 0)
    
    # Collect all filenames for pattern analysis
    all_filenames = [f.get('filename', '').lower() for f in files]
    all_filenames_str = ' '.join(all_filenames)
    
    # Collect all classes and functions
    all_classes = []
    all_functions = []
    for f in files:
        all_classes.extend(f.get('classes_added', []))
        all_functions.extend(f.get('functions_added', []))
    
    # =========================================================================
    # INTELLIGENT PROJECT DETECTION - Determine what this PR is actually about
    # =========================================================================
    
    project_type = None
    project_description = None
    architecture_notes = []
    capabilities = []
    
    # --- Detect PR Agent / AI Agent System ---
    if ('pr-agent' in all_filenames_str or 'pragent' in all_filenames_str) and \
       any('agent' in c.lower() for c in all_classes):
        project_type = "PR Analysis Agent"
        
        # Check for Microsoft Agent Framework
        has_maf = any('agent_framework' in f.get('patch', '').lower() if f.get('patch') else False for f in files) or \
                  any('agentframework' in fn or 'agent_framework' in fn for fn in all_filenames)
        
        # Check for Azure OpenAI
        has_azure_openai = any('azure' in fn and 'openai' in f.get('patch', '').lower() if f.get('patch') else False for f in files) or \
                          any('azureopenai' in all_filenames_str)
        
        # Detect agent types
        agent_classes = [c for c in all_classes if 'agent' in c.lower()]
        executor_classes = [c for c in all_classes if 'executor' in c.lower() or 'dispatcher' in c.lower() or 'aggregator' in c.lower()]
        
        # Detect tools
        tool_files = [f for f in files if '/tools/' in f.get('filename', '')]
        tool_names = []
        for tf in tool_files:
            fn = tf.get('filename', '').split('/')[-1].replace('.py', '').replace('_', ' ').title()
            if fn and fn not in ['__init__', 'Init']:
                tool_names.append(fn)
        
        project_description = "This PR implements an **AI-powered Pull Request analysis agent** that automatically reviews code changes and provides intelligent feedback."
        
        if has_maf:
            architecture_notes.append("Built on **Microsoft Agent Framework (MAF)** for enterprise-grade AI orchestration")
        if has_azure_openai:
            architecture_notes.append("Powered by **Azure OpenAI** (GPT-4) for intelligent code understanding")
        if executor_classes:
            if any('dispatcher' in c.lower() for c in executor_classes) and any('aggregator' in c.lower() for c in executor_classes):
                architecture_notes.append("Uses **fan-out/fan-in workflow pattern** for parallel agent execution")
        
        # Capabilities based on detected components
        if any('code' in c.lower() and 'analyz' in c.lower() for c in agent_classes + all_functions):
            capabilities.append("Multi-language code analysis (Python, JavaScript, TypeScript, Bicep, Terraform, SQL, and more)")
        if any('security' in c.lower() for c in agent_classes + all_functions):
            capabilities.append("Security vulnerability scanning with severity classification")
        if any('github' in fn for fn in all_filenames):
            capabilities.append("GitHub API integration for PR comments and diff retrieval")
        if any('markdown' in fn or 'formatter' in fn for fn in all_filenames):
            capabilities.append("Rich markdown formatting for readable PR comments")
    
    # --- Detect Azure Infrastructure (Bicep) ---
    elif any(f.get('language') == 'bicep' for f in files):
        project_type = "Azure Infrastructure"
        bicep_files = [f for f in files if f.get('language') == 'bicep']
        
        # Analyze infrastructure components
        infra_components = []
        for bf in bicep_files:
            fn = bf.get('filename', '').lower()
            patch = bf.get('patch', '').lower() if bf.get('patch') else ''
            
            if 'functionapp' in fn or 'function' in fn or 'microsoft.web/sites' in patch:
                infra_components.append("Azure Function App")
            if 'eventhub' in fn or 'event-hub' in fn or 'microsoft.eventhub' in patch:
                infra_components.append("Event Hub")
            if 'storage' in fn or 'microsoft.storage' in patch:
                infra_components.append("Storage Account")
            if 'vnet' in fn or 'network' in fn or 'microsoft.network' in patch:
                infra_components.append("Virtual Network")
            if 'keyvault' in fn or 'key-vault' in fn or 'microsoft.keyvault' in patch:
                infra_components.append("Key Vault")
            if 'apim' in fn or 'api-management' in fn or 'microsoft.apimanagement' in patch:
                infra_components.append("API Management")
            if 'cosmos' in fn or 'microsoft.documentdb' in patch:
                infra_components.append("Cosmos DB")
            if 'sql' in fn or 'microsoft.sql' in patch:
                infra_components.append("Azure SQL")
            if 'servicebus' in fn or 'microsoft.servicebus' in patch:
                infra_components.append("Service Bus")
            if 'privateendpoint' in fn or 'private-endpoint' in fn:
                infra_components.append("Private Endpoints")
        
        infra_components = list(set(infra_components))  # Remove duplicates
        
        if infra_components:
            project_description = f"This PR provisions/updates **Azure infrastructure** including: {', '.join(infra_components)}."
        else:
            project_description = f"This PR contains **Azure Bicep infrastructure-as-code** changes ({len(bicep_files)} files)."
        
        architecture_notes.append("Infrastructure-as-Code using **Azure Bicep** templates")
        if any('module' in f.get('filename', '').lower() for f in bicep_files):
            architecture_notes.append("Modular design with reusable Bicep modules")
    
    # --- Detect Terraform Infrastructure ---
    elif any(f.get('language') == 'terraform' for f in files):
        project_type = "Terraform Infrastructure"
        tf_files = [f for f in files if f.get('language') == 'terraform']
        project_description = f"This PR contains **Terraform infrastructure-as-code** changes ({len(tf_files)} files)."
        architecture_notes.append("Infrastructure-as-Code using **Terraform**")
    
    # --- Detect GitHub Actions / CI-CD ---
    elif any('.github/workflows' in f.get('filename', '') for f in files):
        project_type = "CI/CD Pipeline"
        workflow_files = [f for f in files if '.github/workflows' in f.get('filename', '')]
        workflow_names = [f.get('filename', '').split('/')[-1] for f in workflow_files]
        
        project_description = f"This PR adds/updates **GitHub Actions workflows**: {', '.join(workflow_names)}."
        architecture_notes.append("Automated CI/CD using **GitHub Actions**")
    
    # --- Detect API / Backend Service ---
    elif any(kw in all_filenames_str for kw in ['controller', 'router', 'endpoint', 'api', 'handler']):
        project_type = "API/Backend Service"
        project_description = "This PR implements/updates **backend API endpoints**."
    
    # --- Detect Database Changes ---
    elif 'database' in by_category or any(f.get('language') == 'sql' for f in files):
        project_type = "Database Changes"
        sql_files = [f for f in files if f.get('language') == 'sql']
        project_description = f"This PR contains **database schema/migration changes** ({len(sql_files)} SQL files)."
    
    # --- Generic fallback with better description ---
    else:
        # Try to infer from languages and structure
        if 'python' in languages:
            if any('test' in fn for fn in all_filenames):
                project_type = "Python Application with Tests"
            else:
                project_type = "Python Application"
            project_description = f"This PR adds/updates **Python code** across {total_files} files."
        elif 'typescript' in languages or 'javascript' in languages:
            project_type = "JavaScript/TypeScript Application"
            project_description = f"This PR adds/updates **JavaScript/TypeScript code** across {total_files} files."
        else:
            project_type = "Code Changes"
            project_description = f"This PR contains changes across {total_files} files."
    
    # =========================================================================
    # BUILD THE EXECUTIVE SUMMARY
    # =========================================================================
    
    md = "## 📋 Executive Summary\n\n"
    
    # Main description paragraph
    md += f"{project_description}\n\n"
    
    # Architecture section (if we have notes)
    if architecture_notes:
        md += "### Architecture\n\n"
        for note in architecture_notes:
            md += f"- {note}\n"
        md += "\n"
    
    # Capabilities section (if detected)
    if capabilities:
        md += "### Capabilities\n\n"
        for cap in capabilities:
            md += f"- {cap}\n"
        md += "\n"
    
    # Quick stats table
    md += "### Change Summary\n\n"
    md += "| Metric | Value |\n"
    md += "|--------|-------|\n"
    md += f"| **Files Changed** | {total_files} |\n"
    md += f"| **Lines Added** | +{total_additions} |\n"
    md += f"| **Lines Removed** | -{total_deletions} |\n"
    md += f"| **Languages** | {', '.join(languages) if languages else 'N/A'} |\n"
    md += "\n"
    
    # Key components section
    key_components = []
    
    # Agents
    for cls in all_classes:
        if 'agent' in cls.lower():
            key_components.append(f"**Agent:** `{cls}` - AI-powered analysis component")
    
    # Executors
    for cls in all_classes:
        if 'dispatcher' in cls.lower():
            key_components.append(f"**Dispatcher:** `{cls}` - Distributes work to multiple agents")
        elif 'aggregator' in cls.lower():
            key_components.append(f"**Aggregator:** `{cls}` - Combines results from agents")
        elif 'executor' in cls.lower():
            key_components.append(f"**Executor:** `{cls}` - Workflow execution component")
    
    # Tools
    tool_files = [f.get('filename', '').split('/')[-1].replace('.py', '') for f in files if '/tools/' in f.get('filename', '')]
    for tool in tool_files:
        if tool and tool != '__init__':
            tool_display = tool.replace('_', ' ').title()
            key_components.append(f"**Tool:** `{tool_display}` - Utility for {tool_display.lower()}")
    
    # Workflows
    for f in files:
        if '.github/workflows' in f.get('filename', ''):
            wf_name = f.get('filename', '').split('/')[-1]
            key_components.append(f"**Workflow:** `{wf_name}` - GitHub Actions automation")
    
    if key_components:
        md += "### Key Components\n\n"
        for comp in key_components[:12]:  # Limit to 12
            md += f"- {comp}\n"
        if len(key_components) > 12:
            md += f"- *...and {len(key_components) - 12} more components*\n"
        md += "\n"
    
    # =========================================================================
    # APPROVAL RECOMMENDATION
    # =========================================================================
    
    md += "### Reviewer Guidance\n\n"
    
    if high_issues > 0:
        md += f"⚠️ **Action Required:** {high_issues} high-severity security issue(s) must be addressed before merging.\n\n"
        md += "Please review the Security Scan section below for details.\n\n"
    elif medium_issues > 0:
        md += f"🟡 **Review Recommended:** {medium_issues} medium-severity issue(s) found. Consider addressing before merge.\n\n"
        md += "The changes are functional but could benefit from security improvements.\n\n"
    elif total_issues > 0:
        md += f"✅ **Ready for Review:** Only {total_issues} low-severity informational issue(s) found.\n\n"
        md += "This PR is in good shape. Please review the code logic and approve if it meets requirements.\n\n"
    else:
        md += "✅ **Ready for Review:** No security issues detected.\n\n"
        md += "This PR passes all automated security checks. Please review the code logic and approve if it meets requirements.\n\n"
    
    return md


def format_code_analysis(analysis_result: Dict) -> str:
    """Format code analysis results as markdown.

    Args:
        analysis_result: Dictionary with code analysis results

    Returns:
        Markdown-formatted string with analysis summary
    """
    summary = analysis_result.get('summary', {})
    files = analysis_result.get('files', [])
    by_language = analysis_result.get('files_by_language', {})
    by_category = analysis_result.get('files_by_category', {})

    total_files = summary.get('total_files', 0)
    total_additions = summary.get('total_additions', 0)
    total_deletions = summary.get('total_deletions', 0)

    md = f"<details open>\n"
    md += f"<summary>📊 Code Changes ({total_files} files, +{total_additions}/-{total_deletions} lines)</summary>\n\n"

    # Overview table
    md += "### Overview\n\n"
    md += "| Metric | Value |\n"
    md += "|--------|-------|\n"
    md += f"| Files Changed | {total_files} |\n"
    md += f"| Lines Added | +{total_additions} |\n"
    md += f"| Lines Removed | -{total_deletions} |\n"
    md += f"| Languages | {len(by_language)} |\n"
    md += "\n"

    # Changes by category
    if by_category:
        md += "### Changes by Category\n\n"
        category_icons = {
            'source-code': '💻',
            'tests': '🧪',
            'infrastructure': '🏗️',
            'database': '🗃️',
            'documentation': '📝',
            'configuration': '⚙️',
            'ci-cd': '🔄',
        }
        md += "| Category | Files | Icon |\n"
        md += "|----------|-------|------|\n"
        for category, cat_files in by_category.items():
            icon = category_icons.get(category, '📁')
            md += f"| {category.replace('-', ' ').title()} | {len(cat_files)} | {icon} |\n"
        md += "\n"

    # Changes by language
    if by_language:
        md += "### Changes by Language\n\n"
        md += "| Language | Files | Additions | Deletions |\n"
        md += "|----------|-------|-----------|------------|\n"
        for language, lang_files in sorted(by_language.items(), key=lambda x: -len(x[1])):
            additions = sum(f.get('additions', 0) for f in lang_files)
            deletions = sum(f.get('deletions', 0) for f in lang_files)
            md += f"| {language.title()} | {len(lang_files)} | +{additions} | -{deletions} |\n"
        md += "\n"

    # Notable changes (functions/classes added)
    notable_files = [f for f in files if f.get('functions_added') or f.get('classes_added')]
    if notable_files:
        md += "### Notable Additions\n\n"
        for file_info in notable_files[:10]:  # Limit to first 10
            filename = file_info.get('filename', 'Unknown')
            funcs = file_info.get('functions_added', [])
            classes = file_info.get('classes_added', [])
            
            md += f"**`{filename}`**\n"
            if classes:
                md += f"- Classes: `{'`, `'.join(classes[:5])}`"
                if len(classes) > 5:
                    md += f" (+{len(classes) - 5} more)"
                md += "\n"
            if funcs:
                md += f"- Functions: `{'`, `'.join(funcs[:5])}`"
                if len(funcs) > 5:
                    md += f" (+{len(funcs) - 5} more)"
                md += "\n"
            md += "\n"

    # File list (collapsed if many files)
    if files:
        md += "<details>\n"
        md += f"<summary>📁 All Changed Files ({len(files)})</summary>\n\n"
        md += "| File | Language | Status | Changes |\n"
        md += "|------|----------|--------|----------|\n"
        for file_info in files[:50]:  # Limit to first 50
            filename = file_info.get('filename', 'Unknown')
            language = file_info.get('language', 'unknown')
            status = file_info.get('status', 'modified')
            additions = file_info.get('additions', 0)
            deletions = file_info.get('deletions', 0)
            status_icon = {'added': '🆕', 'modified': '📝', 'removed': '🗑️', 'renamed': '📛'}.get(status, '📄')
            md += f"| `{filename}` | {language} | {status_icon} {status} | +{additions}/-{deletions} |\n"
        if len(files) > 50:
            md += f"\n*... and {len(files) - 50} more files*\n"
        md += "\n</details>\n"

    md += "</details>\n"
    return md


def format_security_scan(security_result: Dict) -> str:
    """Format security scan results as markdown.

    Args:
        security_result: Dictionary with security scan results

    Returns:
        Markdown-formatted string with security findings
    """
    summary = security_result.get('summary', {})
    findings = security_result.get('findings', [])
    
    total_issues = summary.get('total_issues', 0)
    high = summary.get('high_severity', 0)
    medium = summary.get('medium_severity', 0)
    low = summary.get('low_severity', 0)

    # Determine if section should be open (only if HIGH issues)
    open_attr = " open" if high > 0 else ""
    
    md = f"<details{open_attr}>\n"
    md += f"<summary>🔒 Security Scan ({total_issues} issue{'s' if total_issues != 1 else ''} found)</summary>\n\n"

    # Summary table
    md += "### Issues by Severity\n\n"
    md += "| Severity | Count | Status |\n"
    md += "|----------|-------|--------|\n"
    md += f"| 🔴 HIGH | {high} | {'⚠️ Action Required' if high > 0 else '✅'} |\n"
    md += f"| 🟡 MEDIUM | {medium} | {'Review Recommended' if medium > 0 else '✅'} |\n"
    md += f"| ⚪ LOW | {low} | {'Informational' if low > 0 else '✅'} |\n"
    md += "\n"

    # Group findings by severity
    high_findings = [f for f in findings if f.get('severity') == 'HIGH']
    medium_findings = [f for f in findings if f.get('severity') == 'MEDIUM']
    low_findings = [f for f in findings if f.get('severity') == 'LOW']

    # High severity issues
    if high_findings:
        md += "### 🔴 High Severity Issues\n\n"
        md += "> ⚠️ **These issues should be addressed before merging**\n\n"
        for finding in high_findings:
            file = finding.get('file', 'Unknown')
            line = finding.get('line', 0)
            issue = finding.get('issue', 'Unknown issue')
            context = finding.get('context', '')
            recommendation = finding.get('recommendation', 'Review and fix')
            ftype = finding.get('type', 'unknown')
            
            md += f"**{issue}**\n"
            md += f"- **Location:** `{file}:{line}`\n"
            md += f"- **Type:** {ftype.replace('-', ' ').title()}\n"
            if context:
                md += f"- **Context:** `{context[:80]}{'...' if len(context) > 80 else ''}`\n"
            md += f"- **Recommendation:** {recommendation}\n\n"

    # Medium severity issues
    if medium_findings:
        md += "### 🟡 Medium Severity Issues\n\n"
        for finding in medium_findings[:10]:  # Limit to first 10
            file = finding.get('file', 'Unknown')
            line = finding.get('line', 0)
            issue = finding.get('issue', 'Unknown issue')
            recommendation = finding.get('recommendation', 'Review and consider fixing')
            
            md += f"**{issue}**\n"
            md += f"- **Location:** `{file}:{line}`\n"
            md += f"- **Recommendation:** {recommendation}\n\n"
        
        if len(medium_findings) > 10:
            md += f"*... and {len(medium_findings) - 10} more medium severity issues*\n\n"

    # Low severity issues (collapsed)
    if low_findings:
        md += "<details>\n"
        md += f"<summary>⚪ Low Severity Issues ({len(low_findings)})</summary>\n\n"
        for finding in low_findings[:10]:
            file = finding.get('file', 'Unknown')
            line = finding.get('line', 0)
            issue = finding.get('issue', 'Unknown issue')
            md += f"- `{file}:{line}` - {issue}\n"
        if len(low_findings) > 10:
            md += f"\n*... and {len(low_findings) - 10} more*\n"
        md += "\n</details>\n\n"

    # No issues found
    if total_issues == 0:
        md += "### ✅ No Security Issues Detected\n\n"
        md += "The changes look good from a security perspective.\n\n"

    md += "</details>\n"
    return md


def combine_pr_comment(
    analysis_md: str, 
    security_md: str, 
    files_truncated: bool = False, 
    max_files: int = 0,
    executive_summary: str = "",
    detailed_changes: str = ""
) -> str:
    """Combine code analysis and security scan into a single PR comment.

    Args:
        analysis_md: Markdown-formatted code analysis
        security_md: Markdown-formatted security scan
        files_truncated: Whether the file list was truncated
        max_files: Maximum number of files analyzed
        executive_summary: Optional executive summary to include at top
        detailed_changes: Optional detailed per-file changes section

    Returns:
        Complete markdown comment for PR
    """
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

    comment = f"## 🤖 PR Analysis Report\n\n"
    comment += f"**Analyzed:** {timestamp}\n\n"
    
    # Truncation warning
    if files_truncated:
        comment += f"> **Note:** This PR contains more than {max_files} files. "
        comment += f"Only the first {max_files} files were analyzed.\n\n"
    
    # Add executive summary if provided
    if executive_summary:
        comment += "---\n\n"
        comment += executive_summary
    
    # Add detailed changes section if provided
    if detailed_changes:
        comment += "---\n\n"
        comment += detailed_changes
    
    comment += "---\n\n"
    comment += analysis_md
    comment += "\n"
    comment += security_md
    comment += "\n---\n\n"
    
    comment += "### 📋 Next Steps\n\n"
    comment += "1. Review the code changes and their impact\n"
    comment += "2. Address any HIGH severity security issues before merging\n"
    comment += "3. Consider the MEDIUM severity recommendations\n"
    comment += "4. Ensure adequate test coverage for new code\n\n"
    
    comment += "*Powered by Microsoft Agent Framework & Azure OpenAI*\n"

    return comment


def format_error_comment(error_message: str) -> str:
    """Format an error message as a PR comment.

    Args:
        error_message: The error message to display

    Returns:
        Markdown-formatted error comment
    """
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

    comment = f"## ❌ PR Analysis Failed\n\n"
    comment += f"**Time:** {timestamp}\n\n"
    comment += f"**Error:**\n```\n{error_message}\n```\n\n"
    comment += "Please check the GitHub Actions logs for more details.\n\n"
    comment += "*Powered by Microsoft Agent Framework & Azure OpenAI*\n"

    return comment


# Legacy function names for backward compatibility
def format_diff_analysis(diff_result: Dict) -> str:
    """Legacy function - redirects to format_code_analysis."""
    return format_code_analysis(diff_result)
