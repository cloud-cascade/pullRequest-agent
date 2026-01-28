"""Generic code analysis tool for PR changes across multiple languages."""

import json
import re
from typing import Dict, List, Optional
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from agent_framework import ai_function


# Language detection based on file extension (Terraform-only)
LANGUAGE_MAP = {
    '.tf': 'terraform',
    '.tfvars': 'terraform-vars',
    '.hcl': 'hcl',
}

# Files to always ignore
IGNORED_FILES = {
    'package-lock.json',
    'yarn.lock',
    'poetry.lock',
    'Pipfile.lock',
    'composer.lock',
    'Gemfile.lock',
    '.gitignore',
    '.dockerignore',
    '.terraform.lock.hcl',  # Terraform lock file
    '*.tfstate',  # Terraform state files (pattern)
    '*.tfstate.backup',  # Terraform state backups
}

# Directories to ignore
IGNORED_DIRS = {
    'node_modules',
    '__pycache__',
    '.git',
    'venv',
    '.venv',
    'dist',
    'build',
    'target',
    '.idea',
    '.vscode',
}


def detect_language(filename: str) -> str:
    """Detect Terraform file type from filename.

    Args:
        filename: The filename to analyze

    Returns:
        Language identifier string ('terraform', 'terraform-vars', 'hcl', or 'unknown')
    """
    basename = Path(filename).name.lower()

    # Ignore Terraform state files and lock files
    if basename.endswith('.tfstate') or basename.endswith('.tfstate.backup') or basename == '.terraform.lock.hcl':
        return 'unknown'

    # Check extension
    ext = Path(filename).suffix.lower()
    return LANGUAGE_MAP.get(ext, 'unknown')


def should_analyze_file(filename: str) -> bool:
    """Determine if a file should be analyzed.
    
    Args:
        filename: The filename to check
        
    Returns:
        True if file should be analyzed
    """
    basename = Path(filename).name
    
    # Skip ignored files
    if basename in IGNORED_FILES:
        return False
    
    # Skip files in ignored directories
    for ignored_dir in IGNORED_DIRS:
        if f'/{ignored_dir}/' in filename or filename.startswith(f'{ignored_dir}/'):
            return False
    
    # Skip binary and generated files
    binary_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.zip', '.tar', '.gz', '.exe', '.dll', '.so', '.dylib'}
    if Path(filename).suffix.lower() in binary_extensions:
        return False
    
    return True


def categorize_change(filename: str, language: str) -> str:
    """Categorize Terraform files by their purpose.

    Args:
        filename: The changed file
        language: Detected language

    Returns:
        Category string (terraform-resources, terraform-modules, terraform-variables, terraform-outputs, terraform-providers)
    """
    filename_lower = filename.lower()
    basename = Path(filename).name.lower()

    # Terraform-specific categorization
    if language in ('terraform', 'terraform-vars', 'hcl'):
        # Modules (files in modules/ directories or module definitions)
        if '/modules/' in filename_lower or '/module/' in filename_lower:
            return 'terraform-modules'

        # Variables (variables.tf, *.tfvars, terraform.tfvars)
        if 'variable' in basename or basename.endswith('.tfvars') or basename == 'terraform.tfvars':
            return 'terraform-variables'

        # Outputs (outputs.tf)
        if 'output' in basename:
            return 'terraform-outputs'

        # Providers (providers.tf, provider configurations)
        if 'provider' in basename or 'backend' in basename:
            return 'terraform-providers'

        # Resources (main.tf, *.tf resource definitions)
        return 'terraform-resources'

    # Default fallback
    return 'unknown'


def extract_changes_from_patch(patch: str) -> Dict:
    """Extract added, removed, and modified lines from a git patch.
    
    Args:
        patch: Git diff patch content
        
    Returns:
        Dictionary with added, removed lines and statistics
    """
    if not patch:
        return {
            'added_lines': [],
            'removed_lines': [],
            'additions': 0,
            'deletions': 0,
        }
    
    lines = patch.split('\n')
    added_lines = []
    removed_lines = []
    
    line_num = 0
    for line in lines:
        if line.startswith('@@'):
            # Parse hunk header to get line numbers
            match = re.search(r'@@ -\d+(?:,\d+)? \+(\d+)', line)
            if match:
                line_num = int(match.group(1)) - 1
            continue
        
        if line.startswith('+') and not line.startswith('+++'):
            line_num += 1
            added_lines.append({
                'line_num': line_num,
                'content': line[1:]  # Remove the + prefix
            })
        elif line.startswith('-') and not line.startswith('---'):
            removed_lines.append({
                'content': line[1:]  # Remove the - prefix
            })
        elif not line.startswith('\\'):  # Skip "No newline at end of file"
            line_num += 1
    
    return {
        'added_lines': added_lines,
        'removed_lines': removed_lines,
        'additions': len(added_lines),
        'deletions': len(removed_lines),
    }


def extract_terraform_blocks(patch: str, language: str) -> Dict:
    """Extract Terraform HCL block definitions from changes.

    Args:
        patch: Git diff patch content
        language: Terraform language type

    Returns:
        Dictionary with added/modified Terraform blocks (resources, modules, data sources, variables, outputs)
    """
    resources_added = []
    modules_added = []
    data_sources_added = []
    variables_added = []
    outputs_added = []

    if not patch:
        return {
            'resources': resources_added,
            'modules': modules_added,
            'data_sources': data_sources_added,
            'variables': variables_added,
            'outputs': outputs_added,
        }

    # Only process Terraform files
    if language not in ('terraform', 'terraform-vars', 'hcl'):
        return {
            'resources': resources_added,
            'modules': modules_added,
            'data_sources': data_sources_added,
            'variables': variables_added,
            'outputs': outputs_added,
        }

    # Terraform HCL patterns
    # resource "type" "name"
    resource_pattern = re.compile(r'^\+\s*resource\s+"([^"]+)"\s+"([^"]+)"')
    # module "name"
    module_pattern = re.compile(r'^\+\s*module\s+"([^"]+)"')
    # data "type" "name"
    data_pattern = re.compile(r'^\+\s*data\s+"([^"]+)"\s+"([^"]+)"')
    # variable "name"
    variable_pattern = re.compile(r'^\+\s*variable\s+"([^"]+)"')
    # output "name"
    output_pattern = re.compile(r'^\+\s*output\s+"([^"]+)"')

    for line in patch.split('\n'):
        # Check for resources
        match = resource_pattern.search(line)
        if match:
            resource_type = match.group(1)
            resource_name = match.group(2)
            resources_added.append(f"{resource_type}.{resource_name}")
            continue

        # Check for modules
        match = module_pattern.search(line)
        if match:
            module_name = match.group(1)
            modules_added.append(module_name)
            continue

        # Check for data sources
        match = data_pattern.search(line)
        if match:
            data_type = match.group(1)
            data_name = match.group(2)
            data_sources_added.append(f"{data_type}.{data_name}")
            continue

        # Check for variables
        match = variable_pattern.search(line)
        if match:
            var_name = match.group(1)
            variables_added.append(var_name)
            continue

        # Check for outputs
        match = output_pattern.search(line)
        if match:
            output_name = match.group(1)
            outputs_added.append(output_name)
            continue

    return {
        'resources': resources_added,
        'modules': modules_added,
        'data_sources': data_sources_added,
        'variables': variables_added,
        'outputs': outputs_added,
    }


@ai_function(
    name="analyze_code_changes",
    description="Analyze Terraform infrastructure changes in a PR. Can auto-fetch PR data from GitHub if not provided. Just call this tool - it will get the PR data automatically from environment variables."
)
def analyze_code_changes_tool(
    pr_files: str = ""
) -> str:
    """Tool function for analyzing code changes that the agent will call.

    Args:
        pr_files: Optional - PR data as JSON string. If not provided or invalid,
                  the tool will automatically fetch PR data from GitHub using
                  environment variables (GITHUB_REPOSITORY, PR_NUMBER, GITHUB_TOKEN).

    Returns:
        JSON string with analysis results
    """
    import os
    
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
            print("[CODE_ANALYZER] No valid input data, auto-fetching from GitHub...")
            files_data = _auto_fetch_pr_files()
            
        if not files_data:
            return json.dumps({
                'error': 'Could not get PR data. Ensure GITHUB_REPOSITORY, PR_NUMBER, and GITHUB_TOKEN environment variables are set.',
                'files': [],
                'summary': {
                    'total_files': 0,
                    'total_additions': 0,
                    'total_deletions': 0,
                    'languages': [],
                    'categories': [],
                }
            })

        result = analyze_code_changes(files_data)
        result_json = json.dumps(result, indent=2)
        
        # Store the result in a file for the aggregator to pick up as fallback
        try:
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.cache')
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, 'code_analysis_result.json')
            with open(cache_file, 'w') as f:
                f.write(result_json)
            print(f"[CODE_ANALYZER] Cached result with {len(files_data)} files to {cache_file}")
        except Exception as cache_err:
            print(f"[CODE_ANALYZER] Failed to cache result: {cache_err}")
        
        return result_json
    except Exception as e:
        import traceback
        print(f"[CODE_ANALYZER] Error: {e}")
        traceback.print_exc()
        return json.dumps({
            'error': str(e),
            'files': [],
            'summary': {
                'total_files': 0,
                'total_additions': 0,
                'total_deletions': 0,
                'languages': [],
                'categories': [],
            }
        })


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


def _auto_fetch_pr_files():
    """Auto-fetch PR files from GitHub using environment variables.
    
    Returns:
        List of file dicts or None if fetch fails
    """
    import os
    import requests
    
    repo = os.getenv("GITHUB_REPOSITORY", "")
    pr_number = os.getenv("PR_NUMBER", "")
    token = os.getenv("GITHUB_TOKEN", "")
    
    if not all([repo, pr_number, token]):
        print(f"[CODE_ANALYZER] Missing env vars: repo={bool(repo)}, pr={bool(pr_number)}, token={bool(token)}")
        return None
    
    try:
        pr_num = int(pr_number)
    except ValueError:
        print(f"[CODE_ANALYZER] Invalid PR number: {pr_number}")
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
        
        print(f"[CODE_ANALYZER] Auto-fetched {len(result)} files from PR #{pr_num}")
        return result
    except Exception as e:
        print(f"[CODE_ANALYZER] Failed to fetch PR data: {e}")
        return None


def analyze_code_changes(pr_files: List[Dict]) -> Dict:
    """Analyze code changes across all files in a PR.

    Args:
        pr_files: List of dictionaries containing file changes with their diffs

    Returns:
        Structured dictionary with analysis results
    """
    files_by_language = {}
    files_by_category = {}
    all_files = []
    
    total_additions = 0
    total_deletions = 0
    
    for file_data in pr_files:
        filename = file_data.get('filename', '')
        patch = file_data.get('patch', '')
        status = file_data.get('status', 'modified')
        
        # Skip files we shouldn't analyze
        if not should_analyze_file(filename):
            continue
        
        # Detect language and category
        language = detect_language(filename)
        category = categorize_change(filename, language)

        # Extract changes
        changes = extract_changes_from_patch(patch)
        terraform_blocks = extract_terraform_blocks(patch, language)

        total_additions += changes['additions']
        total_deletions += changes['deletions']

        file_analysis = {
            'filename': filename,
            'language': language,
            'category': category,
            'status': status,
            'additions': changes['additions'],
            'deletions': changes['deletions'],
            'resources_added': terraform_blocks['resources'],
            'modules_added': terraform_blocks['modules'],
            'data_sources_added': terraform_blocks['data_sources'],
            'variables_added': terraform_blocks['variables'],
            'outputs_added': terraform_blocks['outputs'],
            # Keep legacy fields for backward compatibility with markdown_formatter
            'functions_added': terraform_blocks['resources'],  # Map resources to functions for compatibility
            'classes_added': terraform_blocks['modules'],  # Map modules to classes for compatibility
        }
        
        all_files.append(file_analysis)
        
        # Group by language
        if language not in files_by_language:
            files_by_language[language] = []
        files_by_language[language].append(file_analysis)
        
        # Group by category
        if category not in files_by_category:
            files_by_category[category] = []
        files_by_category[category].append(file_analysis)
    
    # Build summary
    summary = {
        'total_files': len(all_files),
        'total_additions': total_additions,
        'total_deletions': total_deletions,
        'languages': list(files_by_language.keys()),
        'categories': list(files_by_category.keys()),
        'language_breakdown': {lang: len(files) for lang, files in files_by_language.items()},
        'category_breakdown': {cat: len(files) for cat, files in files_by_category.items()},
    }
    
    return {
        'files': all_files,
        'files_by_language': files_by_language,
        'files_by_category': files_by_category,
        'summary': summary,
    }
