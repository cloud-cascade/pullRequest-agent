"""Markdown formatter for PR comments - supports multiple languages."""

from datetime import datetime
from typing import Dict, List, Tuple


def generate_file_description(file_info: Dict) -> Tuple[str, str, List[str]]:
    """Generate a human-readable description of what a file does.
    
    Args:
        file_info: Dictionary with file analysis data
        
    Returns:
        A tuple of (status_label, description, details) where:
        - status_label: Short label like "New file", "Modified", etc.
        - description: A description string explaining the file's purpose
        - details: List of additional detail strings
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
    # WORKFLOWS
    # =========================================================================
    if '.github/workflows' in filename:
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
    # TERRAFORM (Infrastructure as Code)
    # =========================================================================
    elif language in ('terraform', 'terraform-vars', 'hcl') or filename.endswith('.tf') or filename.endswith('.tfvars'):
        resource_types = []
        cloud_provider = None
        patch_lower = patch.lower() if patch else ''

        # Detect cloud provider and resources
        # AWS
        if 'aws_' in patch_lower or 'aws_' in filename_lower:
            cloud_provider = "AWS"
            if 'aws_instance' in patch_lower or 'aws_ec2' in patch_lower:
                resource_types.append("EC2 Instances")
            if 'aws_s3' in patch_lower:
                resource_types.append("S3 Buckets")
            if 'aws_rds' in patch_lower or 'aws_db_instance' in patch_lower:
                resource_types.append("RDS Databases")
            if 'aws_vpc' in patch_lower or 'aws_subnet' in patch_lower:
                resource_types.append("VPC Networking")
            if 'aws_security_group' in patch_lower:
                resource_types.append("Security Groups")
            if 'aws_lambda' in patch_lower:
                resource_types.append("Lambda Functions")
            if 'aws_iam' in patch_lower:
                resource_types.append("IAM Roles/Policies")
            if 'aws_elb' in patch_lower or 'aws_lb' in patch_lower or 'aws_alb' in patch_lower:
                resource_types.append("Load Balancers")

        # Azure
        elif 'azurerm_' in patch_lower or 'azurerm_' in filename_lower:
            cloud_provider = "Azure"
            if 'azurerm_virtual_machine' in patch_lower or 'azurerm_linux_virtual_machine' in patch_lower:
                resource_types.append("Virtual Machines")
            if 'azurerm_storage' in patch_lower:
                resource_types.append("Storage Accounts")
            if 'azurerm_sql' in patch_lower or 'azurerm_mssql' in patch_lower:
                resource_types.append("SQL Databases")
            if 'azurerm_virtual_network' in patch_lower or 'azurerm_subnet' in patch_lower:
                resource_types.append("Virtual Networks")
            if 'azurerm_network_security_group' in patch_lower:
                resource_types.append("Network Security Groups")
            if 'azurerm_function_app' in patch_lower:
                resource_types.append("Function Apps")
            if 'azurerm_key_vault' in patch_lower:
                resource_types.append("Key Vaults")

        # GCP
        elif 'google_' in patch_lower or 'google_' in filename_lower:
            cloud_provider = "GCP"
            if 'google_compute_instance' in patch_lower:
                resource_types.append("Compute Instances")
            if 'google_storage_bucket' in patch_lower:
                resource_types.append("Storage Buckets")
            if 'google_sql_database_instance' in patch_lower:
                resource_types.append("Cloud SQL")
            if 'google_compute_network' in patch_lower or 'google_compute_subnetwork' in patch_lower:
                resource_types.append("VPC Networks")
            if 'google_compute_firewall' in patch_lower:
                resource_types.append("Firewall Rules")

        # Categorize by file type
        if '/modules/' in filename or '/module/' in filename:
            module_name = filename.split('/')[-2] if filename.endswith('main.tf') else filename.split('/')[-1].replace('.tf', '')
            if resource_types:
                description = f"Terraform module for {cloud_provider or 'cloud'} {', '.join(resource_types)}."
            else:
                description = f"Terraform module: `{module_name}`."
            details.append("Reusable infrastructure component")
        elif 'variable' in filename_lower or filename.endswith('.tfvars'):
            description = f"Terraform variables file."
            details.append("Defines input parameters for infrastructure")
        elif 'output' in filename_lower:
            description = f"Terraform outputs file."
            details.append("Exposes infrastructure values for cross-stack references")
        elif 'provider' in filename_lower or 'backend' in filename_lower:
            description = f"Terraform provider/backend configuration."
            if cloud_provider:
                details.append(f"Configures {cloud_provider} provider")
            details.append("Manages state backend and provider versions")
        else:
            if cloud_provider and resource_types:
                description = f"{cloud_provider} Terraform configuration for {', '.join(resource_types[:3])}."
            elif cloud_provider:
                description = f"{cloud_provider} Terraform infrastructure."
            else:
                description = "Terraform infrastructure configuration."

    # =========================================================================
    # DOCUMENTATION
    # =========================================================================
    elif filename.endswith('.md'):
        doc_name = filename.split('/')[-1].replace('.md', '')
        if 'readme' in filename_lower:
            description = "Project documentation (README)."
            details.append("Describes project setup, usage, and configuration")
        elif 'claude' in filename_lower:
            description = "Claude Code instructions."
            details.append("Guidance for Claude Code AI assistant")
        else:
            description = f"Documentation: `{doc_name}`."

    # =========================================================================
    # GENERIC FALLBACK
    # =========================================================================
    else:
        if language and language != 'unknown':
            description = f"{language.title()} file."
        else:
            description = "File."

        # For Terraform files, show resources/modules added
        if functions_added:  # In our code_analyzer, functions_added maps to resources
            details.append(f"Resources: {', '.join(functions_added[:3])}")
        if classes_added:  # In our code_analyzer, classes_added maps to modules
            details.append(f"Modules: {', '.join(classes_added[:3])}")
    
    return status_label, description, details


def format_detailed_changes(
    files: List[Dict],
    file_summaries: Dict = None,
    summarizer_interpretation: str = ""
) -> str:
    """Format detailed per-file change descriptions.

    Args:
        files: List of file analysis dictionaries
        file_summaries: Optional dictionary with AI-generated file summaries
        summarizer_interpretation: Optional interpretation from the FileSummarizer agent

    Returns:
        Markdown-formatted detailed changes section
    """
    if not files:
        return ""

    md = "## 📝 Detailed Changes\n\n"

    # If we have AI-generated summaries from the FileSummarizer agent, use those first
    if summarizer_interpretation and len(summarizer_interpretation.strip()) > 100:
        md += "### AI-Generated Summaries\n\n"
        md += summarizer_interpretation
        md += "\n\n---\n\n"
        md += "### File-by-File Details\n\n"

    # Build a lookup map for file summaries if available
    summary_map = {}
    if file_summaries and 'files' in file_summaries:
        for fs in file_summaries['files']:
            filename = fs.get('filename', '')
            if filename:
                summary_map[filename] = {
                    'impact': fs.get('impact', 'MEDIUM'),
                    'context': fs.get('context', '')
                }

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

            # Get AI-generated impact level if available
            ai_summary = summary_map.get(filename, {})
            impact = ai_summary.get('impact', '')

            # File header
            md += f"### `{filename}`\n"

            # Add impact badge if available
            if impact:
                impact_badge = {
                    'HIGH': '🔴 HIGH',
                    'MEDIUM': '🟡 MEDIUM',
                    'LOW': '🟢 LOW'
                }.get(impact, impact)
                md += f"**{status_label}** (+{additions}/-{deletions}) | Impact: {impact_badge}\n\n"
            else:
                md += f"**{status_label}** (+{additions}/-{deletions}): {description}\n"

            # Detail bullets
            if details:
                for detail in details:
                    md += f"- {detail}\n"

            md += "\n"

    return md


def format_executive_summary(
    analysis_result: Dict,
    security_result: Dict,
    file_summaries: Dict = None,
    summarizer_interpretation: str = ""
) -> str:
    """Generate a human-readable executive summary of the PR changes.

    This creates a concise, easy-to-understand overview that tells PR reviewers
    exactly what this PR does, why it matters, and whether it's ready to merge.

    Args:
        analysis_result: Dictionary with code analysis results
        security_result: Dictionary with security scan results
        file_summaries: Optional dictionary with AI-generated file summaries
        summarizer_interpretation: Optional interpretation from the FileSummarizer agent

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
    
    # --- Detect Terraform Infrastructure ---
    if any(f.get('language') in ('terraform', 'terraform-vars', 'hcl') for f in files):
        project_type = "Terraform Infrastructure"
        tf_files = [f for f in files if f.get('language') in ('terraform', 'terraform-vars', 'hcl')]

        # Detect cloud provider
        cloud_providers = set()
        infra_components = []

        for tf in tf_files:
            patch = tf.get('patch', '').lower() if tf.get('patch') else ''
            fn = tf.get('filename', '').lower()

            # AWS
            if 'aws_' in patch or 'aws_' in fn:
                cloud_providers.add("AWS")
                if 'aws_instance' in patch or 'aws_ec2' in patch:
                    infra_components.append("Compute (EC2)")
                if 'aws_s3' in patch:
                    infra_components.append("Storage (S3)")
                if 'aws_rds' in patch or 'aws_db_instance' in patch:
                    infra_components.append("Databases (RDS)")
                if 'aws_vpc' in patch or 'aws_subnet' in patch or 'aws_security_group' in patch:
                    infra_components.append("Networking (VPC)")
                if 'aws_lambda' in patch:
                    infra_components.append("Serverless (Lambda)")
                if 'aws_iam' in patch:
                    infra_components.append("Security (IAM)")

            # Azure
            if 'azurerm_' in patch or 'azurerm_' in fn:
                cloud_providers.add("Azure")
                if 'azurerm_virtual_machine' in patch or 'azurerm_linux_virtual_machine' in patch:
                    infra_components.append("Compute (VMs)")
                if 'azurerm_storage' in patch:
                    infra_components.append("Storage (Blob)")
                if 'azurerm_sql' in patch or 'azurerm_mssql' in patch:
                    infra_components.append("Databases (SQL)")
                if 'azurerm_virtual_network' in patch or 'azurerm_subnet' in patch:
                    infra_components.append("Networking (VNet)")
                if 'azurerm_function_app' in patch:
                    infra_components.append("Serverless (Functions)")
                if 'azurerm_key_vault' in patch:
                    infra_components.append("Security (Key Vault)")

            # GCP
            if 'google_' in patch or 'google_' in fn:
                cloud_providers.add("GCP")
                if 'google_compute_instance' in patch:
                    infra_components.append("Compute (GCE)")
                if 'google_storage_bucket' in patch:
                    infra_components.append("Storage (GCS)")
                if 'google_sql_database_instance' in patch:
                    infra_components.append("Databases (Cloud SQL)")
                if 'google_compute_network' in patch or 'google_compute_subnetwork' in patch:
                    infra_components.append("Networking (VPC)")

        infra_components = list(set(infra_components))  # Remove duplicates
        cloud_providers_str = ', '.join(sorted(cloud_providers)) if cloud_providers else "multi-cloud"

        if infra_components:
            project_description = f"This PR modifies **{cloud_providers_str} Terraform infrastructure** affecting: {', '.join(infra_components[:6])}."
        else:
            project_description = f"This PR contains **{cloud_providers_str} Terraform infrastructure-as-code** changes ({len(tf_files)} files)."

        architecture_notes.append(f"Infrastructure-as-Code using **Terraform** for {cloud_providers_str}")
        if any('module' in f.get('filename', '').lower() for f in tf_files):
            architecture_notes.append("Modular design with reusable Terraform modules")
    
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

    # If we have an AI-generated overall summary, show it prominently
    ai_overall_summary = ""
    if summarizer_interpretation:
        # Try to extract an overall summary from the agent's interpretation
        # Look for "Overall Summary" section or similar
        import re
        overall_match = re.search(
            r'(?:###?\s*)?Overall\s+Summary[:\s]*\n+(.*?)(?:\n\n|\n###|\n##|$)',
            summarizer_interpretation,
            re.IGNORECASE | re.DOTALL
        )
        if overall_match:
            ai_overall_summary = overall_match.group(1).strip()

    if ai_overall_summary:
        md += f"> **AI Summary:** {ai_overall_summary}\n\n"

    # Main description paragraph
    md += f"{project_description}\n\n"

    # Show file impact breakdown if available from file_summaries
    if file_summaries and 'by_impact' in file_summaries:
        by_impact = file_summaries['by_impact']
        high_count = by_impact.get('high', 0)
        medium_count = by_impact.get('medium', 0)
        low_count = by_impact.get('low', 0)

        if high_count > 0 or medium_count > 0 or low_count > 0:
            md += "### Impact Assessment\n\n"
            md += "| Impact Level | Files |\n"
            md += "|--------------|-------|\n"
            if high_count > 0:
                md += f"| 🔴 HIGH | {high_count} |\n"
            if medium_count > 0:
                md += f"| 🟡 MEDIUM | {medium_count} |\n"
            if low_count > 0:
                md += f"| 🟢 LOW | {low_count} |\n"
            md += "\n"
    
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
            'terraform-resources': '🏗️',
            'terraform-modules': '📦',
            'terraform-variables': '⚙️',
            'terraform-outputs': '📤',
            'terraform-providers': '🔌',
            'unknown': '📁',
        }
        md += "| Category | Files | Icon |\n"
        md += "|----------|-------|------|\n"
        for category, cat_files in by_category.items():
            icon = category_icons.get(category, '📁')
            category_display = category.replace('terraform-', '').replace('-', ' ').title()
            md += f"| {category_display} | {len(cat_files)} | {icon} |\n"
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
