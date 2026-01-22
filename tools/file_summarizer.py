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


def extract_bicep_terraform_info(added_lines: List[str], removed_lines: List[str], filename: str) -> Dict:
    """Extract infrastructure resource information from Bicep/Terraform files.

    Args:
        added_lines: Lines added in the diff
        removed_lines: Lines removed in the diff
        filename: The filename for context

    Returns:
        Dictionary with extracted information
    """
    info = {
        'resources_added': [],
        'resources_modified': [],
        'parameters_changed': [],
        'outputs_changed': [],
        'config_changes': []
    }

    # Bicep patterns
    bicep_resource = re.compile(r"resource\s+(\w+)\s+'([^']+)'")
    bicep_param = re.compile(r"param\s+(\w+)")
    bicep_var = re.compile(r"var\s+(\w+)")
    bicep_output = re.compile(r"output\s+(\w+)")

    # Terraform patterns
    tf_resource = re.compile(r'resource\s+"([^"]+)"\s+"([^"]+)"')
    tf_data = re.compile(r'data\s+"([^"]+)"\s+"([^"]+)"')
    tf_variable = re.compile(r'variable\s+"([^"]+)"')
    tf_output = re.compile(r'output\s+"([^"]+)"')

    for line in added_lines:
        # Bicep
        match = bicep_resource.search(line)
        if match:
            info['resources_added'].append(f"{match.group(1)} ({match.group(2)})")
            continue
        match = bicep_param.search(line)
        if match:
            info['parameters_changed'].append(match.group(1))
            continue
        match = bicep_output.search(line)
        if match:
            info['outputs_changed'].append(match.group(1))
            continue

        # Terraform
        match = tf_resource.search(line)
        if match:
            info['resources_added'].append(f"{match.group(2)} ({match.group(1)})")
            continue
        match = tf_variable.search(line)
        if match:
            info['parameters_changed'].append(match.group(1))
            continue
        match = tf_output.search(line)
        if match:
            info['outputs_changed'].append(match.group(1))
            continue

        # Config values
        if '=' in line or ':' in line:
            # Extract key-value patterns
            kv_match = re.search(r"(\w+)\s*[=:]\s*['\"]?([^'\"}\n]+)", line)
            if kv_match:
                key, value = kv_match.groups()
                if key.lower() in ['sku', 'tier', 'capacity', 'size', 'retention', 'location', 'name']:
                    info['config_changes'].append(f"{key}={value.strip()}")

    return info


def extract_python_info(added_lines: List[str], removed_lines: List[str]) -> Dict:
    """Extract Python code information from diff.

    Args:
        added_lines: Lines added in the diff
        removed_lines: Lines removed in the diff

    Returns:
        Dictionary with extracted information
    """
    info = {
        'functions_added': [],
        'functions_removed': [],
        'classes_added': [],
        'classes_removed': [],
        'imports_added': [],
        'imports_removed': [],
        'decorators': [],
        'async_functions': [],
        'variables_added': [],
        'patterns_detected': [],
        'docstrings': []
    }

    # Patterns
    func_pattern = re.compile(r'def\s+(\w+)\s*\(([^)]*)\)')
    async_func_pattern = re.compile(r'async\s+def\s+(\w+)\s*\(([^)]*)\)')
    class_pattern = re.compile(r'class\s+(\w+)(?:\s*\(([^)]*)\))?')
    import_pattern = re.compile(r'(?:from\s+(\S+)\s+)?import\s+(.+)')
    decorator_pattern = re.compile(r'@(\w+)(?:\(([^)]*)\))?')
    variable_pattern = re.compile(r'^(\w+)\s*[=:]\s*(.+)$')
    docstring_pattern = re.compile(r'"""([^"]+)"""')

    # Semantic patterns for better understanding
    api_patterns = ['route', 'endpoint', 'api', 'get', 'post', 'put', 'delete', 'patch']
    db_patterns = ['query', 'execute', 'commit', 'rollback', 'session', 'cursor', 'fetch']
    auth_patterns = ['auth', 'login', 'logout', 'token', 'credential', 'password', 'permission']
    error_patterns = ['exception', 'error', 'raise', 'try', 'except', 'catch', 'handle']

    all_added_text = ' '.join(added_lines).lower()

    for line in added_lines:
        # Check for async functions
        match = async_func_pattern.search(line)
        if match:
            func_name = match.group(1)
            params = match.group(2).strip()
            info['async_functions'].append(func_name)
            info['functions_added'].append(f"{func_name}(async)")
            continue

        # Check for regular functions
        match = func_pattern.search(line)
        if match:
            func_name = match.group(1)
            params = match.group(2).strip()
            # Add context based on function name
            func_desc = func_name
            if any(p in func_name.lower() for p in api_patterns):
                func_desc = f"{func_name} (API)"
            elif any(p in func_name.lower() for p in db_patterns):
                func_desc = f"{func_name} (DB)"
            elif any(p in func_name.lower() for p in auth_patterns):
                func_desc = f"{func_name} (auth)"
            info['functions_added'].append(func_desc)
            continue

        # Check for classes with inheritance
        match = class_pattern.search(line)
        if match:
            class_name = match.group(1)
            parent = match.group(2) if match.group(2) else None
            if parent:
                info['classes_added'].append(f"{class_name}({parent.strip()})")
            else:
                info['classes_added'].append(class_name)
            continue

        # Check for imports
        match = import_pattern.search(line)
        if match:
            module = match.group(1) or match.group(2)
            info['imports_added'].append(module.split(',')[0].strip())
            continue

        # Check for decorators with arguments
        match = decorator_pattern.search(line)
        if match:
            decorator_name = match.group(1)
            decorator_args = match.group(2) if match.group(2) else None
            if decorator_args and 'name=' in decorator_args:
                # Extract tool/route name from decorator
                name_match = re.search(r'name\s*=\s*["\']([^"\']+)', decorator_args)
                if name_match:
                    info['decorators'].append(f"{decorator_name}:{name_match.group(1)}")
                else:
                    info['decorators'].append(decorator_name)
            else:
                info['decorators'].append(decorator_name)
            continue

        # Check for variable assignments (constants, configs)
        match = variable_pattern.search(line.strip())
        if match:
            var_name = match.group(1)
            var_value = match.group(2)
            # Only capture significant variables (UPPER_CASE constants or specific patterns)
            if var_name.isupper() or any(p in var_name.lower() for p in ['config', 'setting', 'option', 'default']):
                info['variables_added'].append(var_name)
            continue

        # Check for docstrings
        match = docstring_pattern.search(line)
        if match:
            docstring = match.group(1).strip()[:100]  # Limit length
            if docstring:
                info['docstrings'].append(docstring)

    # Detect semantic patterns in added code
    if any(p in all_added_text for p in api_patterns):
        info['patterns_detected'].append('API endpoints')
    if any(p in all_added_text for p in db_patterns):
        info['patterns_detected'].append('database operations')
    if any(p in all_added_text for p in auth_patterns):
        info['patterns_detected'].append('authentication')
    if any(p in all_added_text for p in error_patterns):
        info['patterns_detected'].append('error handling')
    if 'async' in all_added_text or 'await' in all_added_text:
        info['patterns_detected'].append('async/await')
    if 'logging' in all_added_text or 'logger' in all_added_text:
        info['patterns_detected'].append('logging')
    if 'cache' in all_added_text:
        info['patterns_detected'].append('caching')
    if 'test' in all_added_text or 'assert' in all_added_text or 'mock' in all_added_text:
        info['patterns_detected'].append('testing')

    # Process removed lines
    for line in removed_lines:
        match = async_func_pattern.search(line) or func_pattern.search(line)
        if match:
            info['functions_removed'].append(match.group(1))
            continue
        match = class_pattern.search(line)
        if match:
            info['classes_removed'].append(match.group(1))
            continue
        match = import_pattern.search(line)
        if match:
            module = match.group(1) or match.group(2)
            info['imports_removed'].append(module.split(',')[0].strip())

    return info


def extract_js_ts_info(added_lines: List[str], removed_lines: List[str]) -> Dict:
    """Extract JavaScript/TypeScript code information from diff.

    Args:
        added_lines: Lines added in the diff
        removed_lines: Lines removed in the diff

    Returns:
        Dictionary with extracted information
    """
    info = {
        'functions_added': [],
        'functions_removed': [],
        'classes_added': [],
        'exports_added': [],
        'imports_added': []
    }

    func_pattern = re.compile(r'(?:async\s+)?function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(|(\w+)\s*[=:]\s*(?:async\s*)?\([^)]*\)\s*=>')
    class_pattern = re.compile(r'class\s+(\w+)')
    export_pattern = re.compile(r'export\s+(?:default\s+)?(?:const|let|var|function|class)\s+(\w+)')
    import_pattern = re.compile(r"import\s+.*from\s+['\"]([^'\"]+)")

    for line in added_lines:
        match = func_pattern.search(line)
        if match:
            name = match.group(1) or match.group(2) or match.group(3)
            if name:
                info['functions_added'].append(name)
            continue
        match = class_pattern.search(line)
        if match:
            info['classes_added'].append(match.group(1))
            continue
        match = export_pattern.search(line)
        if match:
            info['exports_added'].append(match.group(1))
            continue
        match = import_pattern.search(line)
        if match:
            info['imports_added'].append(match.group(1))

    for line in removed_lines:
        match = func_pattern.search(line)
        if match:
            name = match.group(1) or match.group(2) or match.group(3)
            if name:
                info['functions_removed'].append(name)

    return info


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

    # Infrastructure files (Bicep, Terraform)
    if language in ('bicep', 'terraform'):
        info = extract_bicep_terraform_info(added_lines, removed_lines, filename)

        if info['resources_added']:
            resources = ', '.join(info['resources_added'][:3])
            summary_parts.append(f"adds {len(info['resources_added'])} resource(s): {resources}")

        if info['parameters_changed']:
            params = ', '.join(info['parameters_changed'][:3])
            summary_parts.append(f"configures parameters: {params}")

        if info['config_changes']:
            configs = ', '.join(info['config_changes'][:4])
            summary_parts.append(f"sets {configs}")

        if info['outputs_changed']:
            outputs = ', '.join(info['outputs_changed'][:2])
            summary_parts.append(f"outputs: {outputs}")

    # Python files
    elif language == 'python':
        info = extract_python_info(added_lines, removed_lines)

        # Check for AI/agent tool definitions first (most specific)
        ai_tool_decorators = [d for d in info['decorators'] if 'ai_function' in d or 'tool' in d.lower()]
        if ai_tool_decorators:
            tool_names = [d.split(':')[1] if ':' in d else d for d in ai_tool_decorators]
            summary_parts.append(f"defines AI agent tool(s): {', '.join(tool_names[:2])}")

        # Classes with context
        if info['classes_added']:
            classes = ', '.join(info['classes_added'][:3])
            summary_parts.append(f"adds class(es): {classes}")

        # Functions with semantic context (API, DB, auth markers)
        if info['functions_added']:
            funcs = ', '.join(info['functions_added'][:4])
            summary_parts.append(f"adds function(s): {funcs}")

        # Async functions specifically
        if info['async_functions'] and 'async' not in str(info['functions_added']):
            async_funcs = ', '.join(info['async_functions'][:3])
            summary_parts.append(f"async: {async_funcs}")

        # Removed functions
        if info['functions_removed']:
            funcs = ', '.join(info['functions_removed'][:3])
            summary_parts.append(f"removes: {funcs}")

        # Constants/config variables
        if info['variables_added']:
            vars_list = ', '.join(info['variables_added'][:3])
            summary_parts.append(f"defines: {vars_list}")

        # Detected semantic patterns (provides context about what the code does)
        if info['patterns_detected'] and not summary_parts:
            patterns = ', '.join(info['patterns_detected'][:3])
            summary_parts.append(f"implements {patterns}")

        # Use docstrings for context if no other summary
        if info['docstrings'] and not summary_parts:
            summary_parts.append(info['docstrings'][0][:80])

        # Fall back to imports if nothing else
        if info['imports_added'] and not summary_parts:
            imports = ', '.join(info['imports_added'][:3])
            summary_parts.append(f"imports: {imports}")

    # JavaScript/TypeScript files
    elif language in ('javascript', 'typescript'):
        info = extract_js_ts_info(added_lines, removed_lines)

        if info['classes_added']:
            classes = ', '.join(info['classes_added'][:3])
            summary_parts.append(f"adds class(es): {classes}")

        if info['functions_added']:
            funcs = ', '.join(info['functions_added'][:4])
            summary_parts.append(f"adds function(s): {funcs}")

        if info['exports_added']:
            exports = ', '.join(info['exports_added'][:3])
            summary_parts.append(f"exports: {exports}")

    # YAML files (workflows, configs)
    elif language == 'yaml':
        info = extract_yaml_info(added_lines, removed_lines, filename)

        if info['steps_added']:
            steps = ', '.join(info['steps_added'][:3])
            summary_parts.append(f"adds workflow step(s): {steps}")

        if info['env_vars_changed']:
            vars = ', '.join(info['env_vars_changed'][:4])
            summary_parts.append(f"configures env vars: {vars}")

        if info['config_keys_changed'] and not summary_parts:
            keys = ', '.join(info['config_keys_changed'][:4])
            summary_parts.append(f"updates config: {keys}")

    # JSON files
    elif language == 'json':
        # Look for common patterns in added lines
        key_pattern = re.compile(r'"(\w+)":\s*')
        keys_changed = []
        for line in added_lines[:20]:
            match = key_pattern.search(line)
            if match:
                keys_changed.append(match.group(1))

        if keys_changed:
            keys = ', '.join(list(set(keys_changed))[:4])
            summary_parts.append(f"modifies config keys: {keys}")

    # SQL files
    elif language == 'sql':
        for line in added_lines:
            line_lower = line.lower()
            if 'create table' in line_lower:
                match = re.search(r'create\s+table\s+(\w+)', line_lower)
                if match:
                    summary_parts.append(f"creates table: {match.group(1)}")
            elif 'alter table' in line_lower:
                summary_parts.append("alters table schema")
            elif 'create index' in line_lower:
                summary_parts.append("adds database index")
            elif 'insert into' in line_lower:
                summary_parts.append("inserts data")

    # Fallback for other languages or if no patterns matched
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
    """Determine the impact level of a file change.

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

    total_changes = additions + deletions

    # High impact indicators
    high_impact_patterns = [
        'main.', 'app.', 'index.',  # Entry points
        'config', 'settings', 'env',  # Configuration
        'auth', 'security', 'credential',  # Security
        'database', 'migration', 'schema',  # Database
        'deploy', 'ci', 'workflow',  # CI/CD
        '.bicep', '.tf',  # Infrastructure
        'api', 'endpoint', 'router',  # API
    ]

    for pattern in high_impact_patterns:
        if pattern in filename:
            return 'HIGH'

    # Infrastructure files are high impact
    if language in ('bicep', 'terraform'):
        return 'HIGH'

    # Large changes are high impact
    if total_changes > 200:
        return 'HIGH'

    # New files with substantial content
    if status == 'added' and additions > 50:
        return 'MEDIUM'

    # Medium impact for moderate changes
    if total_changes > 50:
        return 'MEDIUM'

    # Test files and documentation are usually low impact
    low_impact_patterns = [
        'test', 'spec', '__test__',
        'readme', '.md', 'docs/',
        'example', 'sample',
    ]

    for pattern in low_impact_patterns:
        if pattern in filename:
            return 'LOW'

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
    """Generate an overall summary of all changes in the PR.

    Args:
        files: List of file info dictionaries with summaries

    Returns:
        Overall PR summary string
    """
    if not files:
        return "No significant code changes detected."

    # Group by category
    categories = {
        'infrastructure': [],
        'source_code': [],
        'config': [],
        'tests': [],
        'docs': [],
        'ci_cd': []
    }

    for f in files:
        filename = f.get('filename', '').lower()
        language = f.get('language', '')
        summary = f.get('summary', '')

        if language in ('bicep', 'terraform') or 'infra' in filename:
            categories['infrastructure'].append(summary)
        elif 'test' in filename or 'spec' in filename:
            categories['tests'].append(summary)
        elif '.github' in filename or 'workflow' in filename or 'ci' in filename:
            categories['ci_cd'].append(summary)
        elif language in ('markdown', 'rst') or 'readme' in filename or 'doc' in filename:
            categories['docs'].append(summary)
        elif language in ('json', 'yaml', 'toml', 'ini') and 'config' in filename:
            categories['config'].append(summary)
        else:
            categories['source_code'].append(summary)

    # Build summary parts
    parts = []

    if categories['infrastructure']:
        parts.append(f"Infrastructure: {len(categories['infrastructure'])} file(s) - {categories['infrastructure'][0]}")

    if categories['source_code']:
        parts.append(f"Source code: {len(categories['source_code'])} file(s) modified")

    if categories['ci_cd']:
        parts.append(f"CI/CD: {len(categories['ci_cd'])} workflow file(s) updated")

    if categories['config']:
        parts.append(f"Configuration: {len(categories['config'])} file(s) changed")

    if categories['tests']:
        parts.append(f"Tests: {len(categories['tests'])} test file(s) modified")

    if categories['docs']:
        parts.append(f"Documentation: {len(categories['docs'])} file(s) updated")

    if not parts:
        return f"Modified {len(files)} file(s) across the codebase."

    return ". ".join(parts) + "."


@ai_function(
    name="summarize_file_changes",
    description="Generate semantic summaries for each changed file in a PR. Returns file contexts with patches for LLM analysis. Can auto-fetch PR data from GitHub if not provided."
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
