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


@ai_function(
    name="scan_security",
    description="Scan code changes for security vulnerabilities including hardcoded secrets and language-specific issues. Pass the entire input message you received as the pr_files parameter."
)
def scan_security_tool(
    pr_files: str = ""
) -> str:
    """Tool function for security scanning that the agent will call.

    Args:
        pr_files: Can be either:
            - JSON string containing PR data: '{"pr_number": ..., "files": [...]}'
            - Direct Python object (dict/list) with PR data
            - Full PR data object: {"pr_number": ..., "files": [...]}
            - Just the files array: [{"filename": ..., "patch": ...}, ...]

    Returns:
        JSON string with security scan results
    """
    try:
        # Validate input is provided
        if not pr_files or len(str(pr_files).strip()) < 10:
            return json.dumps({
                'error': 'No PR data provided. You must pass the PR data from get_pr_diff tool as the pr_files parameter.',
                'findings': [],
                'summary': {
                    'total_issues': 0,
                    'high_severity': 0,
                    'medium_severity': 0,
                    'low_severity': 0,
                }
            })

        # Parse the input - handle both string JSON and direct objects
        parsed_data = None
        if isinstance(pr_files, str):
            try:
                # First try to parse as JSON
                parsed_data = json.loads(pr_files)
            except json.JSONDecodeError as e:
                # If JSON parsing fails, it might be because the LLM passed it incorrectly
                # Try to extract JSON from the string or use it as-is
                error_msg = f'JSON parsing error: {str(e)}'
                
                # Try to find if it's a nested JSON string (double-encoded)
                try:
                    # Sometimes the string is double-quoted, try unescaping
                    import codecs
                    unescaped = codecs.decode(pr_files, 'unicode_escape')
                    parsed_data = json.loads(unescaped)
                except:
                    # If all parsing attempts fail, return helpful error
                    return json.dumps({
                        'error': error_msg,
                        'hint': 'The input JSON may have unescaped special characters. Please pass the exact input message you received without modification.',
                        'input_type': type(pr_files).__name__,
                        'input_preview': pr_files[:200] if len(pr_files) > 200 else pr_files,
                        'findings': [],
                        'summary': {
                            'total_issues': 0,
                            'high_severity': 0,
                            'medium_severity': 0,
                            'low_severity': 0,
                        }
                    })
        elif isinstance(pr_files, dict):
            parsed_data = pr_files
        elif isinstance(pr_files, list):
            parsed_data = pr_files
        else:
            parsed_data = {}

        # Handle both formats: full PR object or just files array
        if isinstance(parsed_data, dict) and 'files' in parsed_data:
            files_data = parsed_data['files']
        elif isinstance(parsed_data, list):
            files_data = parsed_data
        else:
            files_data = []

        result = scan_security(files_data)
        return json.dumps(result, indent=2)
    except Exception as e:
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
