"""GitHub API integration for PR operations."""

import requests
import json
import os
from typing import Dict, List, Union
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from agent_framework import ai_function


# Maximum patch size in characters to avoid overwhelming the AI
MAX_PATCH_SIZE = 10000


def sanitize_patch(patch: str) -> str:
    """Sanitize and limit patch size to avoid JSON encoding issues.

    Args:
        patch: The raw patch string from GitHub

    Returns:
        Sanitized and potentially truncated patch
    """
    if not patch:
        return ""

    # Limit patch size
    if len(patch) > MAX_PATCH_SIZE:
        lines = patch.split('\n')
        truncated_lines = []
        current_size = 0

        for line in lines:
            if current_size + len(line) > MAX_PATCH_SIZE:
                truncated_lines.append(f"\n... [Patch truncated - total size: {len(patch)} chars, showing first {MAX_PATCH_SIZE} chars] ...")
                break
            truncated_lines.append(line)
            current_size += len(line) + 1  # +1 for newline

        return '\n'.join(truncated_lines)

    return patch


def get_pr_diff(repo: str, pr_number: int, github_token: str) -> List[Dict]:
    """Fetch PR file changes using GitHub API.

    Args:
        repo: Repository in format 'owner/repo'
        pr_number: Pull request number
        github_token: GitHub authentication token

    Returns:
        List of dictionaries containing file changes with their diffs

    Raises:
        Exception: If API request fails
    """
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files"

    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        files = response.json()

        result = []
        for file in files:
            raw_patch = file.get('patch', '')
            result.append({
                'filename': file.get('filename', ''),
                'status': file.get('status', ''),  # added, removed, modified, renamed
                'additions': file.get('additions', 0),
                'deletions': file.get('deletions', 0),
                'changes': file.get('changes', 0),
                'patch': sanitize_patch(raw_patch)  # Sanitized diff
            })

        print(f"Fetched {len(result)} changed files from PR #{pr_number}")
        return result

    except requests.exceptions.RequestException as e:
        print(f"Error fetching PR diff: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        sys.exit(1)


def post_pr_comment(repo: str, pr_number: int, comment: str, github_token: str) -> bool:
    """Post a markdown comment to a pull request.

    Args:
        repo: Repository in format 'owner/repo'
        pr_number: Pull request number
        comment: Markdown-formatted comment text
        github_token: GitHub authentication token

    Returns:
        True if comment was posted successfully, False otherwise
    """
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"

    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    payload = {
        "body": comment
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        print(f"Successfully posted comment to PR #{pr_number}")
        return True

    except requests.exceptions.RequestException as e:
        print(f"Error posting PR comment: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        return False


@ai_function(
    name="get_pr_diff",
    description="Fetch PR file changes from GitHub API. Call this tool to get the list of changed files with their diffs. Parameters can be passed explicitly or will be read from environment variables if not provided."
)
def get_pr_diff_tool(
    repository: str = "",
    pr_number: Union[int, str] = "",
    github_token: str = ""
) -> str:
    """Agent-callable tool function for fetching PR diff from GitHub.
    
    This tool allows agents to autonomously fetch PR data. If parameters are not provided,
    it will attempt to read them from environment variables.

    Args:
        repository: Repository in format 'owner/repo' (or reads GITHUB_REPOSITORY env var)
        pr_number: Pull request number as int or string (or reads PR_NUMBER env var)
        github_token: GitHub authentication token (or reads GITHUB_TOKEN env var)

    Returns:
        JSON string containing list of file changes with their diffs
    """
    try:
        # Use environment variables as fallback if parameters not provided
        repo = repository or os.getenv("GITHUB_REPOSITORY", "")
        pr_num_str = str(pr_number) if pr_number else os.getenv("PR_NUMBER", "")
        token = github_token or os.getenv("GITHUB_TOKEN", "")
        
        # Validate required parameters
        if not repo:
            return json.dumps({
                "error": "Repository parameter is required. Either pass 'repository' parameter or set GITHUB_REPOSITORY environment variable.",
                "files": []
            })
        
        if not pr_num_str:
            return json.dumps({
                "error": "PR number parameter is required. Either pass 'pr_number' parameter or set PR_NUMBER environment variable.",
                "files": []
            })
        
        if not token:
            return json.dumps({
                "error": "GitHub token parameter is required. Either pass 'github_token' parameter or set GITHUB_TOKEN environment variable.",
                "files": []
            })
        
        # Convert PR number to int
        try:
            pr_num = int(pr_num_str)
        except ValueError:
            return json.dumps({
                "error": f"Invalid PR number: {pr_num_str}. Must be a valid integer.",
                "files": []
            })
        
        # Call the underlying function
        files = get_pr_diff(repo, pr_num, token)

        # Return as JSON string
        result = {
            "pr_number": pr_num,
            "repository": repo,
            "file_count": len(files),
            "files": files
        }

        # Try to encode as JSON with special character handling
        try:
            # Use ensure_ascii=False to handle Unicode and special characters properly
            return json.dumps(result, indent=2, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            # If JSON encoding fails, return simplified version without patches
            print(f"Warning: JSON encoding failed, returning simplified response: {e}")
            simplified = {
                "pr_number": pr_num,
                "repository": repo,
                "file_count": len(files),
                "error": "JSON encoding error - patch data may contain problematic characters",
                "files": [
                    {
                        "filename": f.get("filename"),
                        "status": f.get("status"),
                        "additions": f.get("additions"),
                        "deletions": f.get("deletions"),
                        "changes": f.get("changes"),
                        "patch": "[Removed due to encoding issues]"
                    }
                    for f in files
                ]
            }
            return json.dumps(simplified, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"Failed to fetch PR diff: {str(e)}",
            "files": []
        })

