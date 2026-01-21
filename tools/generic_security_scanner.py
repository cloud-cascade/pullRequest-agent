"""Generic security scanning tool for multiple languages."""

import json
import re
from typing import Dict, List
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from agent_framework import ai_function

from tools.code_analyzer import detect_language, should_analyze_file


# Secret patterns by category
SECRET_PATTERNS = [
    # API Keys
    (r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']([^"\']{10,})["\']', 'API Key', 'HIGH'),
    (r'(?i)(api[_-]?secret|apisecret)\s*[:=]\s*["\']([^"\']{10,})["\']', 'API Secret', 'HIGH'),
    
    # AWS
    (r'AKIA[0-9A-Z]{16}', 'AWS Access Key ID', 'HIGH'),
    (r'(?i)(aws[_-]?secret[_-]?access[_-]?key)\s*[:=]\s*["\']([^"\']{20,})["\']', 'AWS Secret Key', 'HIGH'),
    
    # Azure
    (r'(?i)(azure[_-]?(?:storage[_-]?)?(?:account[_-]?)?key)\s*[:=]\s*["\']([^"\']{20,})["\']', 'Azure Key', 'HIGH'),
    (r'(?i)(connection[_-]?string)\s*[:=]\s*["\']([^"\']*(?:AccountKey|SharedAccessSignature)[^"\']*)["\']', 'Azure Connection String', 'HIGH'),
    
    # Database
    (r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']([^"\']{4,})["\']', 'Password', 'HIGH'),
    (r'(?i)(db[_-]?password|database[_-]?password)\s*[:=]\s*["\']([^"\']{4,})["\']', 'Database Password', 'HIGH'),
    (r'(?i)mysql://[^:]+:([^@]+)@', 'MySQL Connection String', 'HIGH'),
    (r'(?i)postgres(?:ql)?://[^:]+:([^@]+)@', 'PostgreSQL Connection String', 'HIGH'),
    (r'(?i)mongodb(\+srv)?://[^:]+:([^@]+)@', 'MongoDB Connection String', 'HIGH'),
    
    # Generic Tokens
    (r'(?i)(secret|token|auth[_-]?token|access[_-]?token)\s*[:=]\s*["\']([^"\']{10,})["\']', 'Secret/Token', 'HIGH'),
    (r'(?i)(private[_-]?key)\s*[:=]\s*["\']([^"\']{20,})["\']', 'Private Key', 'HIGH'),
    (r'(?i)(client[_-]?secret)\s*[:=]\s*["\']([^"\']{10,})["\']', 'Client Secret', 'HIGH'),
    
    # JWT
    (r'eyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+', 'JWT Token', 'HIGH'),
    
    # GitHub
    (r'ghp_[A-Za-z0-9]{36}', 'GitHub Personal Access Token', 'HIGH'),
    (r'github_pat_[A-Za-z0-9]{22}_[A-Za-z0-9]{59}', 'GitHub Fine-grained PAT', 'HIGH'),
    
    # Slack
    (r'xox[baprs]-[0-9A-Za-z]{10,}', 'Slack Token', 'HIGH'),
    
    # SSH Keys
    (r'-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----', 'SSH Private Key', 'HIGH'),
]

# Patterns to exclude (false positives)
EXCLUSION_PATTERNS = [
    r'@secure',                    # Bicep secure decorator
    r'param\s+\w+',               # Parameter declarations
    r'environment\(',              # Environment functions
    r'process\.env\.',            # Environment variable access
    r'os\.environ',               # Python env access
    r'os\.getenv',                # Python env access
    r'\$\{',                      # Variable interpolation
    r'\$\(',                      # Command substitution
    r'getenv\(',                  # Generic env access
    r'System\.getenv',            # Java env access
    r'Environment\.',             # .NET env access
    r'config\.',                  # Config references
    r'settings\.',                # Settings references
    r'secrets\.',                 # Secret manager references
    r'vault\.',                   # Vault references
    r'keyVault',                  # Azure Key Vault
    r'SecretClient',              # Azure SDK
    r'#\s*',                      # Comments (hash)
    r'//\s*',                     # Comments (double slash)
    r'/\*',                       # Multi-line comment
    r'<!--',                      # HTML comment
    r'TODO',                      # TODO markers
    r'FIXME',                     # FIXME markers
    r'example',                   # Example text
    r'placeholder',               # Placeholder text
    r'your[-_]',                  # Documentation placeholders
    r'xxx+',                      # Placeholder pattern
    r'changeme',                  # Default placeholder
    r'\*\*\*',                    # Masked secrets
    # Pattern definitions in security scanners (regex patterns as strings)
    r"r'[^']*\\s\*\\\\?\(",       # Regex pattern definitions like r'eval\s*\('
    r'r"[^"]*\\s\*\\\\?\(',       # Regex pattern definitions with double quotes
    r"'[^']*,\s*'[^']*',\s*'(HIGH|MEDIUM|LOW)'",  # Pattern tuples in security rules
    r'"[^"]*,\s*"[^"]*",\s*"(HIGH|MEDIUM|LOW)"',  # Pattern tuples with double quotes
    r'LANGUAGE_SECURITY_PATTERNS', # Reference to security patterns dict
    r'SECRET_PATTERNS',           # Reference to secret patterns list
    r'_PATTERNS\s*=',             # Pattern definition assignments
    r'_PATTERNS\s*\[',            # Pattern list access
]

# Language-specific security issues
LANGUAGE_SECURITY_PATTERNS = {
    'python': [
        (r'eval\s*\(', 'Dangerous eval() usage', 'HIGH', 'Avoid using eval() with untrusted input'),
        (r'exec\s*\(', 'Dangerous exec() usage', 'HIGH', 'Avoid using exec() with untrusted input'),
        (r'pickle\.loads?\s*\(', 'Insecure deserialization', 'HIGH', 'Pickle can execute arbitrary code'),
        (r'subprocess\.(?:call|run|Popen)\s*\([^)]*shell\s*=\s*True', 'Shell injection risk', 'MEDIUM', 'Avoid shell=True with user input'),
        (r'assert\s+', 'Assert used for security check', 'LOW', 'Asserts can be disabled with -O flag'),
        (r'import\s+(?:urllib|requests).*verify\s*=\s*False', 'SSL verification disabled', 'MEDIUM', 'Enable SSL certificate verification'),
    ],
    'javascript': [
        (r'eval\s*\(', 'Dangerous eval() usage', 'HIGH', 'Avoid using eval() with untrusted input'),
        (r'innerHTML\s*=', 'Potential XSS vulnerability', 'MEDIUM', 'Use textContent or sanitize input'),
        (r'document\.write\s*\(', 'Potential XSS vulnerability', 'MEDIUM', 'Avoid document.write with user input'),
        (r'dangerouslySetInnerHTML', 'React XSS risk', 'MEDIUM', 'Sanitize HTML before rendering'),
        (r'new\s+Function\s*\(', 'Dynamic code execution', 'HIGH', 'Avoid creating functions from strings'),
    ],
    'typescript': [
        (r'eval\s*\(', 'Dangerous eval() usage', 'HIGH', 'Avoid using eval() with untrusted input'),
        (r'innerHTML\s*=', 'Potential XSS vulnerability', 'MEDIUM', 'Use textContent or sanitize input'),
        (r'dangerouslySetInnerHTML', 'React XSS risk', 'MEDIUM', 'Sanitize HTML before rendering'),
        (r'as\s+any', 'Type safety bypassed', 'LOW', 'Avoid using "as any" type assertions'),
    ],
    'sql': [
        (r'EXECUTE\s+(?:IMMEDIATE\s+)?[\'"]?\s*\+', 'SQL injection risk', 'HIGH', 'Use parameterized queries'),
        (r'GRANT\s+ALL', 'Overly permissive grant', 'MEDIUM', 'Use principle of least privilege'),
        (r'WITH\s+GRANT\s+OPTION', 'Privilege escalation risk', 'MEDIUM', 'Avoid WITH GRANT OPTION'),
        (r'DROP\s+(?:TABLE|DATABASE|SCHEMA)', 'Destructive operation', 'MEDIUM', 'Ensure proper backups exist'),
        (r'TRUNCATE\s+TABLE', 'Destructive operation', 'MEDIUM', 'Ensure proper backups exist'),
    ],
    'java': [
        (r'Runtime\.getRuntime\(\)\.exec\s*\(', 'Command injection risk', 'HIGH', 'Sanitize command inputs'),
        (r'ProcessBuilder', 'Command execution', 'MEDIUM', 'Validate inputs to ProcessBuilder'),
        (r'ObjectInputStream', 'Insecure deserialization', 'HIGH', 'Validate serialized objects'),
        (r'\.createQuery\s*\([^)]*\+', 'SQL injection risk', 'HIGH', 'Use parameterized queries'),
    ],
    'csharp': [
        (r'Process\.Start\s*\(', 'Command execution', 'MEDIUM', 'Validate process arguments'),
        (r'SqlCommand\s*\([^)]*\+', 'SQL injection risk', 'HIGH', 'Use parameterized queries'),
        (r'BinaryFormatter', 'Insecure deserialization', 'HIGH', 'Avoid BinaryFormatter'),
        (r'AllowHtml\]', 'XSS risk', 'MEDIUM', 'Sanitize HTML input'),
    ],
    'go': [
        (r'exec\.Command\s*\(', 'Command execution', 'MEDIUM', 'Validate command arguments'),
        (r'template\.HTML\s*\(', 'XSS risk', 'MEDIUM', 'Sanitize HTML content'),
        (r'InsecureSkipVerify:\s*true', 'SSL verification disabled', 'MEDIUM', 'Enable SSL verification'),
    ],
    'bicep': [
        (r'publicNetworkAccess\s*:\s*["\']?Enabled["\']?', 'Public network access enabled', 'MEDIUM', 'Consider using private endpoints'),
        (r'allowBlobPublicAccess\s*:\s*true', 'Blob public access allowed', 'MEDIUM', 'Set allowBlobPublicAccess to false'),
        (r'defaultAction\s*:\s*["\']?Allow["\']?', 'Network default action is Allow', 'MEDIUM', 'Set defaultAction to Deny'),
        (r'httpsOnly\s*:\s*false', 'HTTPS not enforced', 'MEDIUM', 'Set httpsOnly to true'),
        (r'minimumTlsVersion\s*:\s*["\']?TLS1_0["\']?', 'Weak TLS version', 'MEDIUM', 'Use TLS 1.2 or higher'),
    ],
    'terraform': [
        (r'publicly_accessible\s*=\s*true', 'Resource publicly accessible', 'MEDIUM', 'Restrict public access'),
        (r'acl\s*=\s*["\']public', 'Public ACL configured', 'MEDIUM', 'Use private ACL'),
        (r'encrypted\s*=\s*false', 'Encryption disabled', 'MEDIUM', 'Enable encryption'),
        (r'ssl_policy\s*=\s*["\']ELBSecurityPolicy-2016', 'Outdated SSL policy', 'LOW', 'Use modern SSL policy'),
    ],
    'dockerfile': [
        (r'FROM\s+.*:latest', 'Using latest tag', 'LOW', 'Pin to specific version'),
        (r'USER\s+root', 'Running as root', 'MEDIUM', 'Create non-root user'),
        (r'chmod\s+777', 'Overly permissive permissions', 'MEDIUM', 'Use minimal permissions'),
        (r'--security-opt\s+seccomp:unconfined', 'Seccomp disabled', 'MEDIUM', 'Enable seccomp'),
    ],
    'yaml': [
        (r'!!python/', 'YAML code execution', 'HIGH', 'Use safe YAML loading'),
    ],
}


def is_false_positive(line: str) -> bool:
    """Check if a line is likely a false positive.
    
    Args:
        line: The line to check
        
    Returns:
        True if likely a false positive
    """
    return any(re.search(p, line, re.IGNORECASE) for p in EXCLUSION_PATTERNS)


def scan_for_secrets(filename: str, lines: List[str]) -> List[Dict]:
    """Scan lines for hardcoded secrets.
    
    Args:
        filename: Name of the file
        lines: List of lines from the diff
        
    Returns:
        List of secret findings
    """
    findings = []
    
    for line_num, line in enumerate(lines):
        # Skip removed lines
        if line.startswith('-') and not line.startswith('---'):
            continue
        
        # Clean the line
        clean_line = line[1:] if line.startswith('+') else line
        
        # Skip false positives
        if is_false_positive(clean_line):
            continue
        
        # Check each secret pattern
        for pattern, secret_type, severity in SECRET_PATTERNS:
            if re.search(pattern, clean_line):
                # Double-check not a false positive
                if not is_false_positive(clean_line):
                    findings.append({
                        'file': filename,
                        'line': line_num + 1,
                        'severity': severity,
                        'type': 'secret',
                        'issue': f'Potential hardcoded {secret_type}',
                        'context': clean_line.strip()[:100],
                        'recommendation': f'Move {secret_type} to environment variables or secret manager',
                    })
    
    return findings


def scan_language_specific(filename: str, lines: List[str], language: str) -> List[Dict]:
    """Scan for language-specific security issues.
    
    Args:
        filename: Name of the file
        lines: List of lines from the diff
        language: Detected programming language
        
    Returns:
        List of security findings
    """
    findings = []
    patterns = LANGUAGE_SECURITY_PATTERNS.get(language, [])
    
    if not patterns:
        return findings
    
    for line_num, line in enumerate(lines):
        # Only check added/modified lines
        if line.startswith('-') and not line.startswith('---'):
            continue
        
        clean_line = line[1:] if line.startswith('+') else line
        
        # Skip comments
        if is_false_positive(clean_line):
            continue
        
        for pattern, issue, severity, recommendation in patterns:
            if re.search(pattern, clean_line, re.IGNORECASE):
                findings.append({
                    'file': filename,
                    'line': line_num + 1,
                    'severity': severity,
                    'type': 'code-vulnerability',
                    'issue': issue,
                    'context': clean_line.strip()[:100],
                    'recommendation': recommendation,
                })
    
    return findings


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
        print(f"[SECURITY_SCANNER] Missing env vars: repo={bool(repo)}, pr={bool(pr_number)}, token={bool(token)}")
        return None
    
    try:
        pr_num = int(pr_number)
    except ValueError:
        print(f"[SECURITY_SCANNER] Invalid PR number: {pr_number}")
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
        
        print(f"[SECURITY_SCANNER] Auto-fetched {len(result)} files from PR #{pr_num}")
        return result
    except Exception as e:
        print(f"[SECURITY_SCANNER] Failed to fetch PR data: {e}")
        return None


@ai_function(
    name="scan_security",
    description="Scan code changes for security vulnerabilities. Can auto-fetch PR data from GitHub if not provided. Just call this tool - it will get the PR data automatically from environment variables."
)
def scan_security_tool(
    pr_files: str = ""
) -> str:
    """Tool function for security scanning that the agent will call.

    Args:
        pr_files: Optional - PR data as JSON string. If not provided or invalid,
                  the tool will automatically fetch PR data from GitHub using
                  environment variables (GITHUB_REPOSITORY, PR_NUMBER, GITHUB_TOKEN).

    Returns:
        JSON string with security scan results
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
            print("[SECURITY_SCANNER] No valid input data, auto-fetching from GitHub...")
            files_data = _auto_fetch_pr_files()
            
        if not files_data:
            return json.dumps({
                'error': 'Could not get PR data. Ensure GITHUB_REPOSITORY, PR_NUMBER, and GITHUB_TOKEN environment variables are set.',
                'findings': [],
                'summary': {
                    'total_issues': 0,
                    'high_severity': 0,
                    'medium_severity': 0,
                    'low_severity': 0,
                }
            })

        result = scan_security(files_data)
        result_json = json.dumps(result, indent=2)
        
        # Store the result in a file for the aggregator to pick up as fallback
        try:
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.cache')
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, 'security_scan_result.json')
            with open(cache_file, 'w') as f:
                f.write(result_json)
            print(f"[SECURITY_SCANNER] Cached result with {len(files_data)} files scanned to {cache_file}")
        except Exception as cache_err:
            print(f"[SECURITY_SCANNER] Failed to cache result: {cache_err}")
        
        return result_json
    except Exception as e:
        import traceback
        print(f"[SECURITY_SCANNER] Error: {e}")
        traceback.print_exc()
        return json.dumps({
            'error': str(e),
            'findings': [],
            'summary': {
                'total_issues': 0,
                'high_severity': 0,
                'medium_severity': 0,
                'low_severity': 0,
            }
        })


def scan_security(pr_files: List[Dict]) -> Dict:
    """Scan all files for security issues.

    Args:
        pr_files: List of dictionaries containing file changes

    Returns:
        Structured dictionary with security findings
    """
    all_findings = []
    files_scanned = 0
    
    # Files to exclude from security scanning (security tool definitions)
    excluded_files = [
        'security_scanner.py',
        'generic_security_scanner.py',
        'security_scanner_agent.py',
    ]
    
    for file_data in pr_files:
        filename = file_data.get('filename', '')
        patch = file_data.get('patch', '')
        
        if not should_analyze_file(filename):
            continue
        
        if not patch:
            continue
        
        # Skip security scanner files (they contain pattern definitions, not actual vulnerabilities)
        if any(excluded in filename for excluded in excluded_files):
            continue
        
        files_scanned += 1
        language = detect_language(filename)
        lines = patch.split('\n')
        
        # Scan for secrets
        secret_findings = scan_for_secrets(filename, lines)
        all_findings.extend(secret_findings)
        
        # Scan for language-specific issues
        lang_findings = scan_language_specific(filename, lines, language)
        all_findings.extend(lang_findings)
    
    # Calculate summary
    high = len([f for f in all_findings if f.get('severity') == 'HIGH'])
    medium = len([f for f in all_findings if f.get('severity') == 'MEDIUM'])
    low = len([f for f in all_findings if f.get('severity') == 'LOW'])
    
    # Group by file
    findings_by_file = {}
    for finding in all_findings:
        file = finding.get('file', 'unknown')
        if file not in findings_by_file:
            findings_by_file[file] = []
        findings_by_file[file].append(finding)
    
    # Group by type
    findings_by_type = {}
    for finding in all_findings:
        ftype = finding.get('type', 'unknown')
        if ftype not in findings_by_type:
            findings_by_type[ftype] = []
        findings_by_type[ftype].append(finding)
    
    return {
        'findings': all_findings,
        'findings_by_file': findings_by_file,
        'findings_by_type': findings_by_type,
        'summary': {
            'total_issues': len(all_findings),
            'high_severity': high,
            'medium_severity': medium,
            'low_severity': low,
            'files_scanned': files_scanned,
        }
    }
