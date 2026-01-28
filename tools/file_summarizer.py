"""File summarizer tool for generating semantic summaries of PR file changes."""

import json
import os
import re
from typing import Dict, List, Tuple
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from agent_framework import ai_function

from tools.code_analyzer import detect_language, should_analyze_file


def _parse_json_input(input_str):
    """Try multiple methods to parse JSON input.

    Args:
        input_str: String that might contain JSON

    Returns:
        Parsed data or None if all methods fail
    """
    if not isinstance(input_str, str):
        return input_str if isinstance(input_str, (dict, list)) else None

    methods = [
        # Method 1: Direct parse
        lambda s: json.loads(s),
        # Method 2: Strip and parse
        lambda s: json.loads(s.strip().lstrip('\ufeff')),
        # Method 3: Unicode unescape
        lambda s: json.loads(__import__('codecs').decode(s, 'unicode_escape')),
        # Method 4: Extract from markdown
        lambda s: json.loads(__import__('re').search(r'```(?:json)?\s*([\s\S]*?)\s*```', s).group(1)),
        # Method 5: Find JSON object
        lambda s: json.loads(__import__('re').search(r'(\{[\s\S]*\})', s).group(1)),
        # Method 6: Find JSON array
        lambda s: json.loads(__import__('re').search(r'(\[[\s\S]*\])', s).group(1)),
    ]

    for method in methods:
        try:
            result = method(input_str)
            if result:
                return result
        except:
            continue

    return None


def parse_diff_lines(patch: str) -> Tuple[List[str], List[str]]:
    """Parse a patch to extract added and removed lines.

    Args:
        patch: The diff patch string

    Returns:
        Tuple of (added_lines, removed_lines)
    """
    added = []
    removed = []

    if not patch:
        return added, removed

    for line in patch.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            added.append(line[1:].strip())
        elif line.startswith('-') and not line.startswith('---'):
            removed.append(line[1:].strip())

    return added, removed


def extract_terraform_info(added_lines: List[str], removed_lines: List[str], filename: str) -> Dict:
    """Extract infrastructure resource information from Terraform files.

    Args:
        added_lines: Lines added in the diff
        removed_lines: Lines removed in the diff
        filename: The filename for context

    Returns:
        Dictionary with extracted information
    """
    info = {
        'resources_added': [],
        'modules_added': [],
        'data_sources_added': [],
        'variables_changed': [],
        'outputs_changed': [],
        'providers_changed': [],
        'config_changes': []
    }

    # Terraform patterns
    tf_resource = re.compile(r'resource\s+"([^"]+)"\s+"([^"]+)"')
    tf_module = re.compile(r'module\s+"([^"]+)"')
    tf_data = re.compile(r'data\s+"([^"]+)"\s+"([^"]+)"')
    tf_variable = re.compile(r'variable\s+"([^"]+)"')
    tf_output = re.compile(r'output\s+"([^"]+)"')
    tf_provider = re.compile(r'provider\s+"([^"]+)"')

    for line in added_lines:
        # Resources
        match = tf_resource.search(line)
        if match:
            resource_type = match.group(1)
            resource_name = match.group(2)
            info['resources_added'].append(f"{resource_type}.{resource_name}")
            continue

        # Modules
        match = tf_module.search(line)
        if match:
            info['modules_added'].append(match.group(1))
            continue

        # Data sources
        match = tf_data.search(line)
        if match:
            data_type = match.group(1)
            data_name = match.group(2)
            info['data_sources_added'].append(f"{data_type}.{data_name}")
            continue

        # Variables
        match = tf_variable.search(line)
        if match:
            info['variables_changed'].append(match.group(1))
            continue

        # Outputs
        match = tf_output.search(line)
        if match:
            info['outputs_changed'].append(match.group(1))
            continue

        # Providers
        match = tf_provider.search(line)
        if match:
            info['providers_changed'].append(match.group(1))
            continue

        # Important config keys (instance_type, region, encryption, etc.)
        if '=' in line:
            kv_match = re.search(r'(\w+)\s*=\s*["\']?([^"\'\n]+)', line)
            if kv_match:
                key, value = kv_match.groups()
                if key.lower() in ['instance_type', 'sku', 'size', 'region', 'location', 'availability_zone',
                                    'encrypted', 'encryption', 'publicly_accessible', 'cidr_block',
                                    'subnet_ids', 'security_group_ids', 'engine', 'engine_version']:
                    info['config_changes'].append(f"{key}={value.strip()}")

    return info


# Python and JavaScript extractors removed - Terraform-only support


def extract_yaml_info(added_lines: List[str], removed_lines: List[str], filename: str) -> Dict:
    """Extract YAML configuration information from diff.

    Args:
        added_lines: Lines added in the diff
        removed_lines: Lines removed in the diff
        filename: The filename for context

    Returns:
        Dictionary with extracted information
    """
    info = {
        'jobs_added': [],
        'steps_added': [],
        'env_vars_changed': [],
        'config_keys_changed': []
    }

    is_workflow = 'workflow' in filename.lower() or '.github' in filename.lower()

    job_pattern = re.compile(r'^\s*(\w+):\s*$')
    step_pattern = re.compile(r'-\s*name:\s*["\']?([^"\']+)')
    env_pattern = re.compile(r'(\w+):\s*\$\{\{')
    key_value = re.compile(r'^\s*(\w+):\s*(.+)$')

    for line in added_lines:
        if is_workflow:
            match = step_pattern.search(line)
            if match:
                info['steps_added'].append(match.group(1).strip())
                continue
            match = env_pattern.search(line)
            if match:
                info['env_vars_changed'].append(match.group(1))
                continue

        match = key_value.search(line)
        if match:
            key = match.group(1)
            if key not in ['name', 'run', 'uses', 'with', 'if', 'env']:
                info['config_keys_changed'].append(key)

    return info


def generate_semantic_summary(file_info: Dict, language: str) -> str:
    """Generate a semantic summary for a file change.

    Args:
        file_info: Dictionary with file information including patch
        language: The detected language of the file

    Returns:
        A human-readable summary of the changes
    """
    filename = file_info.get('filename', '')
    status = file_info.get('status', 'modified')
    additions = file_info.get('additions', 0)
    deletions = file_info.get('deletions', 0)
    patch = file_info.get('patch', '')

    added_lines, removed_lines = parse_diff_lines(patch)

    # Status-based prefix
    if status == 'added':
        action = "Adds"
    elif status == 'removed':
        action = "Removes"
    elif status == 'renamed':
        action = "Renames"
    else:
        if additions > deletions * 2:
            action = "Extends"
        elif deletions > additions * 2:
            action = "Simplifies"
        else:
            action = "Updates"

    summary_parts = []

    # Terraform infrastructure files
    if language in ('terraform', 'terraform-vars', 'hcl'):
        info = extract_terraform_info(added_lines, removed_lines, filename)

        # Resources
        if info['resources_added']:
            resources = ', '.join(info['resources_added'][:3])
            if len(info['resources_added']) > 3:
                summary_parts.append(f"creates {len(info['resources_added'])} resources: {resources} +{len(info['resources_added'])-3} more")
            else:
                summary_parts.append(f"creates resources: {resources}")

        # Modules
        if info['modules_added']:
            modules = ', '.join(info['modules_added'][:3])
            summary_parts.append(f"adds modules: {modules}")

        # Data sources
        if info['data_sources_added']:
            data_sources = ', '.join(info['data_sources_added'][:3])
            summary_parts.append(f"queries data sources: {data_sources}")

        # Variables
        if info['variables_changed']:
            variables = ', '.join(info['variables_changed'][:3])
            summary_parts.append(f"configures variables: {variables}")

        # Outputs
        if info['outputs_changed']:
            outputs = ', '.join(info['outputs_changed'][:2])
            summary_parts.append(f"exposes outputs: {outputs}")

        # Providers
        if info['providers_changed']:
            providers = ', '.join(info['providers_changed'])
            summary_parts.append(f"configures providers: {providers}")

        # Important config settings
        if info['config_changes']:
            # Group by key type
            encryption_configs = [c for c in info['config_changes'] if 'encrypt' in c.lower()]
            network_configs = [c for c in info['config_changes'] if any(k in c.lower() for k in ['cidr', 'subnet', 'security_group'])]
            compute_configs = [c for c in info['config_changes'] if any(k in c.lower() for k in ['instance_type', 'sku', 'size'])]
            region_configs = [c for c in info['config_changes'] if any(k in c.lower() for k in ['region', 'location', 'availability_zone'])]

            if encryption_configs:
                summary_parts.append(f"encryption: {', '.join(encryption_configs[:2])}")
            if compute_configs:
                summary_parts.append(f"compute: {', '.join(compute_configs[:2])}")
            if network_configs:
                summary_parts.append(f"network: {', '.join(network_configs[:2])}")
            if region_configs:
                summary_parts.append(f"region: {', '.join(region_configs[:1])}")

    # YAML files (GitHub workflows)
    elif language == 'yaml':
        info = extract_yaml_info(added_lines, removed_lines, filename)

        if info['steps_added']:
            steps = ', '.join(info['steps_added'][:3])
            summary_parts.append(f"adds workflow steps: {steps}")

        if info['env_vars_changed']:
            vars = ', '.join(info['env_vars_changed'][:4])
            summary_parts.append(f"configures environment variables: {vars}")

        if info['config_keys_changed'] and not summary_parts:
            keys = ', '.join(info['config_keys_changed'][:4])
            summary_parts.append(f"updates configuration: {keys}")

    # Fallback for other file types
    if not summary_parts:
        # Analyze the general nature of changes
        if status == 'added':
            summary_parts.append(f"new {language} file with {additions} lines")
        elif status == 'removed':
            summary_parts.append(f"removes {language} file ({deletions} lines)")
        else:
            # Look for common code patterns
            has_error_handling = any('error' in l.lower() or 'except' in l.lower() or 'catch' in l.lower() for l in added_lines)
            has_logging = any('log' in l.lower() or 'print' in l.lower() or 'console' in l.lower() for l in added_lines)
            has_config = any('config' in l.lower() or 'setting' in l.lower() or 'env' in l.lower() for l in added_lines)

            if has_error_handling:
                summary_parts.append("improves error handling")
            if has_logging:
                summary_parts.append("adds logging/debugging")
            if has_config:
                summary_parts.append("updates configuration")

            if not summary_parts:
                summary_parts.append(f"modifies {language} code (+{additions}/-{deletions} lines)")

    # Construct final summary
    summary = f"{action} {'; '.join(summary_parts)}" if summary_parts else f"{action} {filename}"

    # Capitalize first letter
    summary = summary[0].upper() + summary[1:] if summary else summary

    return summary


def _auto_fetch_pr_files():
    """Auto-fetch PR files from GitHub using environment variables.

    Returns:
        List of file dicts or None if fetch fails
    """
    import requests

    repo = os.getenv("GITHUB_REPOSITORY", "")
    pr_number = os.getenv("PR_NUMBER", "")
    token = os.getenv("GITHUB_TOKEN", "")

    if not all([repo, pr_number, token]):
        print(f"[FILE_SUMMARIZER] Missing env vars: repo={bool(repo)}, pr={bool(pr_number)}, token={bool(token)}")
        return None

    try:
        pr_num = int(pr_number)
    except ValueError:
        print(f"[FILE_SUMMARIZER] Invalid PR number: {pr_number}")
        return None

    url = f"https://api.github.com/repos/{repo}/pulls/{pr_num}/files"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        files = response.json()

        result = []
        for file in files:
            result.append({
                'filename': file.get('filename', ''),
                'status': file.get('status', ''),
                'additions': file.get('additions', 0),
                'deletions': file.get('deletions', 0),
                'changes': file.get('changes', 0),
                'patch': file.get('patch', '')
            })

        print(f"[FILE_SUMMARIZER] Auto-fetched {len(result)} files from PR #{pr_num}")
        return result
    except Exception as e:
        print(f"[FILE_SUMMARIZER] Failed to fetch PR data: {e}")
        return None


def determine_impact_level(file_info: Dict) -> str:
    """Determine the impact level of a Terraform file change.

    Args:
        file_info: Dictionary with file information

    Returns:
        Impact level: HIGH, MEDIUM, or LOW
    """
    filename = file_info.get('filename', '').lower()
    additions = file_info.get('additions', 0)
    deletions = file_info.get('deletions', 0)
    status = file_info.get('status', 'modified')
    language = file_info.get('language', 'unknown')
    patch = file_info.get('patch', '').lower()

    total_changes = additions + deletions

    # High impact indicators for Terraform
    high_impact_patterns = [
        'main.tf',  # Main infrastructure file
        'provider', 'backend',  # Provider/backend configuration
        'network', 'vpc', 'subnet', 'security_group',  # Networking
        'database', 'rds', 'dynamodb', 'sql',  # Databases
        'iam', 'role', 'policy',  # IAM/Security
        'production', 'prod',  # Production environment
    ]

    for pattern in high_impact_patterns:
        if pattern in filename:
            return 'HIGH'

    # Check for high-impact resource changes in patch
    high_risk_resources = [
        'aws_security_group', 'aws_iam', 'aws_rds', 'aws_db_instance',
        'aws_vpc', 'aws_subnet', 'azurerm_virtual_network', 'azurerm_sql',
        'google_compute_network', 'google_sql_database_instance'
    ]
    if any(resource in patch for resource in high_risk_resources):
        return 'HIGH'

    # Large changes are high impact
    if total_changes > 100:
        return 'HIGH'

    # New resource files with substantial content
    if status == 'added' and additions > 30:
        return 'MEDIUM'

    # Medium impact for moderate changes
    if total_changes > 30:
        return 'MEDIUM'

    # Test/example files are low impact
    low_impact_patterns = [
        'test', 'example', 'sample', 'dev', 'development'
    ]

    for pattern in low_impact_patterns:
        if pattern in filename:
            return 'LOW'

    # Default for Terraform files
    return 'MEDIUM'


def generate_file_summary_context(file_info: Dict) -> str:
    """Generate context string for LLM to summarize a file.

    Args:
        file_info: Dictionary with file information including patch

    Returns:
        Context string describing the file changes
    """
    filename = file_info.get('filename', '')
    status = file_info.get('status', 'modified')
    additions = file_info.get('additions', 0)
    deletions = file_info.get('deletions', 0)
    patch = file_info.get('patch', '')
    language = detect_language(filename)

    # Truncate patch if too long
    max_patch_length = 2000
    if len(patch) > max_patch_length:
        patch = patch[:max_patch_length] + "\n... (truncated)"

    context = f"""File: {filename}
Language: {language}
Status: {status}
Lines added: {additions}
Lines deleted: {deletions}

Diff:
{patch}
"""
    return context


def summarize_files(pr_files: List[Dict]) -> Dict:
    """Generate semantic summaries for all files in a PR.

    This function analyzes file patches and generates meaningful summaries
    describing what each change accomplishes.

    Args:
        pr_files: List of dictionaries containing file changes

    Returns:
        Structured dictionary with file summaries
    """
    files_to_summarize = []

    for file_data in pr_files:
        filename = file_data.get('filename', '')
        patch = file_data.get('patch', '')

        if not should_analyze_file(filename):
            continue

        if not patch:
            continue

        language = detect_language(filename)

        file_info = {
            'filename': filename,
            'status': file_data.get('status', 'modified'),
            'additions': file_data.get('additions', 0),
            'deletions': file_data.get('deletions', 0),
            'language': language,
            'patch': patch,
        }

        # Determine impact level heuristically
        impact = determine_impact_level(file_info)
        file_info['impact'] = impact

        # Generate semantic summary by analyzing the patch
        file_info['summary'] = generate_semantic_summary(file_info, language)

        # Generate context for additional LLM processing if needed
        file_info['context'] = generate_file_summary_context(file_info)

        files_to_summarize.append(file_info)

    # Sort by impact level (HIGH first, then MEDIUM, then LOW)
    impact_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
    files_to_summarize.sort(key=lambda x: impact_order.get(x.get('impact', 'LOW'), 2))

    # Generate overall PR summary
    overall_summary = generate_overall_summary(files_to_summarize)

    return {
        'files': files_to_summarize,
        'total_files': len(files_to_summarize),
        'overall_summary': overall_summary,
        'by_impact': {
            'high': len([f for f in files_to_summarize if f.get('impact') == 'HIGH']),
            'medium': len([f for f in files_to_summarize if f.get('impact') == 'MEDIUM']),
            'low': len([f for f in files_to_summarize if f.get('impact') == 'LOW']),
        }
    }


def generate_overall_summary(files: List[Dict]) -> str:
    """Generate an overall summary of all Terraform changes in the PR.

    Args:
        files: List of file info dictionaries with summaries

    Returns:
        Overall PR summary string
    """
    if not files:
        return "No Terraform infrastructure changes detected."

    # Group by Terraform category
    categories = {
        'resources': [],
        'modules': [],
        'variables': [],
        'outputs': [],
        'providers': [],
        'workflows': []
    }

    for f in files:
        filename = f.get('filename', '').lower()
        language = f.get('language', '')
        summary = f.get('summary', '')

        if '.github' in filename or 'workflow' in filename:
            categories['workflows'].append(summary)
        elif language in ('terraform', 'terraform-vars', 'hcl'):
            if 'module' in filename:
                categories['modules'].append(summary)
            elif 'variable' in filename or '.tfvars' in filename:
                categories['variables'].append(summary)
            elif 'output' in filename:
                categories['outputs'].append(summary)
            elif 'provider' in filename or 'backend' in filename:
                categories['providers'].append(summary)
            else:
                categories['resources'].append(summary)

    # Build summary parts
    parts = []

    if categories['resources']:
        parts.append(f"Resources: {len(categories['resources'])} file(s) - {categories['resources'][0]}")

    if categories['modules']:
        parts.append(f"Modules: {len(categories['modules'])} module(s) modified")

    if categories['variables']:
        parts.append(f"Variables: {len(categories['variables'])} variable file(s) updated")

    if categories['outputs']:
        parts.append(f"Outputs: {len(categories['outputs'])} output file(s) changed")

    if categories['providers']:
        parts.append(f"Providers: {len(categories['providers'])} provider config(s) updated")

    if categories['workflows']:
        parts.append(f"CI/CD: {len(categories['workflows'])} workflow(s) modified")

    if not parts:
        return f"Modified {len(files)} Terraform file(s)."

    return ". ".join(parts) + "."


@ai_function(
    name="summarize_file_changes",
    description="Generate semantic summaries for each changed Terraform file in a PR. Returns file contexts with patches for LLM analysis. Can auto-fetch PR data from GitHub if not provided."
)
def summarize_file_changes_tool(
    pr_files: str = ""
) -> str:
    """Tool function for file summarization that the agent will call.

    Args:
        pr_files: Optional - PR data as JSON string. If not provided or invalid,
                  the tool will automatically fetch PR data from GitHub using
                  environment variables (GITHUB_REPOSITORY, PR_NUMBER, GITHUB_TOKEN).

    Returns:
        JSON string with file contexts ready for summarization
    """
    try:
        files_data = None

        # Try to parse provided input first
        if pr_files and len(str(pr_files).strip()) >= 10:
            parsed_data = _parse_json_input(pr_files)
            if parsed_data:
                if isinstance(parsed_data, dict) and 'files' in parsed_data:
                    files_data = parsed_data['files']
                elif isinstance(parsed_data, list):
                    files_data = parsed_data

        # If no valid data, auto-fetch from GitHub
        if not files_data:
            print("[FILE_SUMMARIZER] No valid input data, auto-fetching from GitHub...")
            files_data = _auto_fetch_pr_files()

        if not files_data:
            return json.dumps({
                'error': 'Could not get PR data. Ensure GITHUB_REPOSITORY, PR_NUMBER, and GITHUB_TOKEN environment variables are set.',
                'files': [],
                'total_files': 0,
                'by_impact': {'high': 0, 'medium': 0, 'low': 0}
            })

        result = summarize_files(files_data)
        result_json = json.dumps(result, indent=2)

        # Store the result in a file for the aggregator to pick up as fallback
        try:
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.cache')
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, 'file_summaries_result.json')
            with open(cache_file, 'w') as f:
                f.write(result_json)
            print(f"[FILE_SUMMARIZER] Cached result with {len(files_data)} files to {cache_file}")
        except Exception as cache_err:
            print(f"[FILE_SUMMARIZER] Failed to cache result: {cache_err}")

        return result_json
    except Exception as e:
        import traceback
        print(f"[FILE_SUMMARIZER] Error: {e}")
        traceback.print_exc()
        return json.dumps({
            'error': str(e),
            'files': [],
            'total_files': 0,
            'by_impact': {'high': 0, 'medium': 0, 'low': 0}
        })
