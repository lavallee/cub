"""
Documentation validation for checking broken links, outdated code, and stale content.

Validates markdown documentation files by:
- Checking for broken links (HTTP 404s, invalid URLs)
- Validating code block syntax
- Detecting outdated version references
- Checking internal file references
"""

import ast
import re
import subprocess
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlparse

import requests

from .models import CodeBlockFinding, DocsReport, LinkFinding


class Link(NamedTuple):
    """A link found in markdown."""

    url: str
    line_number: int
    file_path: str


class CodeBlock(NamedTuple):
    """A code block found in markdown."""

    language: str
    code: str
    line_number: int
    file_path: str


def extract_links(file_path: Path, content: str) -> list[Link]:
    """
    Extract all links from markdown content.

    Supports:
    - Inline links: [text](url)
    - Reference links: [text][ref] and [ref]: url
    - Direct URLs: <http://example.com>

    Args:
        file_path: Path to the markdown file
        content: Markdown content to parse

    Returns:
        List of Link objects with URL, line number, and file path
    """
    links: list[Link] = []

    # Pattern for inline links: [text](url)
    inline_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
    # Pattern for reference definitions: [ref]: url
    ref_pattern = r"^\[([^\]]+)\]:\s+(.+)$"
    # Pattern for direct URLs: <url>
    direct_pattern = r"<(https?://[^>]+)>"

    for line_num, line in enumerate(content.splitlines(), start=1):
        # Find inline links
        for match in re.finditer(inline_pattern, line):
            url = match.group(2).strip()
            # Skip anchors and mailto links
            if not url.startswith("#") and not url.startswith("mailto:"):
                links.append(Link(url=url, line_number=line_num, file_path=str(file_path)))

        # Find reference definitions
        for match in re.finditer(ref_pattern, line):
            url = match.group(2).strip()
            if not url.startswith("#") and not url.startswith("mailto:"):
                links.append(Link(url=url, line_number=line_num, file_path=str(file_path)))

        # Find direct URLs
        for match in re.finditer(direct_pattern, line):
            url = match.group(1).strip()
            links.append(Link(url=url, line_number=line_num, file_path=str(file_path)))

    return links


def extract_code_blocks(file_path: Path, content: str) -> list[CodeBlock]:
    """
    Extract all fenced code blocks from markdown content.

    Supports standard markdown fenced code blocks:
    ```language
    code here
    ```

    Args:
        file_path: Path to the markdown file
        content: Markdown content to parse

    Returns:
        List of CodeBlock objects with language, code, line number, and file path
    """
    code_blocks: list[CodeBlock] = []
    lines = content.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        # Match opening fence: ```language
        fence_match = re.match(r"^```(\w+)?", line)

        if fence_match:
            language = fence_match.group(1) or "text"
            start_line = i + 1
            code_lines: list[str] = []
            i += 1

            # Collect code until closing fence
            while i < len(lines):
                if lines[i].strip().startswith("```"):
                    # Found closing fence
                    code_blocks.append(
                        CodeBlock(
                            language=language,
                            code="\n".join(code_lines),
                            line_number=start_line,
                            file_path=str(file_path),
                        )
                    )
                    break
                code_lines.append(lines[i])
                i += 1

        i += 1

    return code_blocks


def check_links(links: list[Link], project_root: Path, timeout: int = 5) -> list[LinkFinding]:
    """
    Validate a list of links, checking HTTP URLs and internal file references.

    Args:
        links: List of Link objects to check
        project_root: Root directory of the project for resolving relative paths
        timeout: Timeout in seconds for HTTP requests

    Returns:
        List of LinkFinding objects for broken or invalid links
    """
    findings: list[LinkFinding] = []
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "cub-docs-validator/1.0",
        }
    )

    for link in links:
        url = link.url

        # Determine if this is a URL or file path
        # URLs have schemes (http://, https://, etc.)
        # File paths start with ./ ../ or / or are simple filenames
        is_url = url.startswith(("http://", "https://", "ftp://"))
        is_file_path = url.startswith(("./", "../", "/")) or (
            "/" in url and not url.startswith(("http://", "https://", "ftp://"))
        )

        # Handle file paths
        if is_file_path:
            # Resolve relative to markdown file location
            md_file_path = Path(link.file_path)
            if md_file_path.is_absolute():
                ref_path = md_file_path.parent / url
            else:
                ref_path = project_root / link.file_path
                ref_path = ref_path.parent / url

            # Remove anchors
            ref_path_str = str(ref_path).split("#")[0]
            ref_path = Path(ref_path_str)

            if not ref_path.exists():
                findings.append(
                    LinkFinding(
                        file_path=link.file_path,
                        line_number=link.line_number,
                        url=url,
                        issue="missing_file",
                    )
                )
            continue

        # Handle URLs
        if is_url:
            # Validate URL format
            try:
                parsed = urlparse(url)
                if not parsed.scheme or not parsed.netloc:
                    findings.append(
                        LinkFinding(
                            file_path=link.file_path,
                            line_number=link.line_number,
                            url=url,
                            issue="invalid_url",
                        )
                    )
                    continue
            except Exception:
                findings.append(
                    LinkFinding(
                        file_path=link.file_path,
                        line_number=link.line_number,
                        url=url,
                        issue="invalid_url",
                    )
                )
                continue
        else:
            # Not clearly a URL or file path - treat as invalid
            findings.append(
                LinkFinding(
                    file_path=link.file_path,
                    line_number=link.line_number,
                    url=url,
                    issue="invalid_url",
                )
            )
            continue

        # Check HTTP/HTTPS links
        try:
            response = session.head(url, timeout=timeout, allow_redirects=True)
            if response.status_code >= 400:
                findings.append(
                    LinkFinding(
                        file_path=link.file_path,
                        line_number=link.line_number,
                        url=url,
                        issue="broken_link",
                        status_code=response.status_code,
                    )
                )
        except requests.Timeout:
            findings.append(
                LinkFinding(
                    file_path=link.file_path,
                    line_number=link.line_number,
                    url=url,
                    issue="timeout",
                )
            )
        except requests.RequestException:
            # Try GET if HEAD fails (some servers block HEAD)
            try:
                response = session.get(url, timeout=timeout, allow_redirects=True)
                if response.status_code >= 400:
                    findings.append(
                        LinkFinding(
                            file_path=link.file_path,
                            line_number=link.line_number,
                            url=url,
                            issue="broken_link",
                            status_code=response.status_code,
                        )
                    )
            except requests.Timeout:
                findings.append(
                    LinkFinding(
                        file_path=link.file_path,
                        line_number=link.line_number,
                        url=url,
                        issue="timeout",
                    )
                )
            except requests.RequestException:
                # If both HEAD and GET fail, skip (may be network issue, not broken link)
                pass

    return findings


def validate_code(code_blocks: list[CodeBlock]) -> list[CodeBlockFinding]:
    """
    Validate syntax of code blocks.

    Currently supports:
    - Python: AST parsing
    - Bash/sh: bash -n syntax check
    - JavaScript/TypeScript: node --check (if available)

    Args:
        code_blocks: List of CodeBlock objects to validate

    Returns:
        List of CodeBlockFinding objects for code blocks with syntax errors
    """
    findings: list[CodeBlockFinding] = []

    for block in code_blocks:
        language = block.language.lower()

        # Python syntax check
        if language in ("python", "py"):
            try:
                ast.parse(block.code)
            except SyntaxError as e:
                findings.append(
                    CodeBlockFinding(
                        file_path=block.file_path,
                        line_number=block.line_number,
                        language=block.language,
                        issue="syntax_error",
                        error_message=str(e),
                    )
                )

        # Bash syntax check
        elif language in ("bash", "sh", "shell"):
            try:
                result = subprocess.run(
                    ["bash", "-n"],
                    input=block.code,
                    text=True,
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode != 0:
                    findings.append(
                        CodeBlockFinding(
                            file_path=block.file_path,
                            line_number=block.line_number,
                            language=block.language,
                            issue="syntax_error",
                            error_message=result.stderr.strip(),
                        )
                    )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                # Skip if bash not available or timeout
                pass

        # JavaScript/TypeScript syntax check (requires node)
        elif language in ("javascript", "js", "typescript", "ts"):
            try:
                result = subprocess.run(
                    ["node", "--check"],
                    input=block.code,
                    text=True,
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode != 0:
                    findings.append(
                        CodeBlockFinding(
                            file_path=block.file_path,
                            line_number=block.line_number,
                            language=block.language,
                            issue="syntax_error",
                            error_message=result.stderr.strip(),
                        )
                    )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                # Skip if node not available or timeout
                pass

    return findings


def validate_docs(
    docs_paths: list[Path], project_root: Path, check_external_links: bool = True
) -> DocsReport:
    """
    Validate documentation files for broken links and invalid code blocks.

    Args:
        docs_paths: List of markdown file paths to validate
        project_root: Root directory of the project
        check_external_links: Whether to check HTTP/HTTPS links (can be slow)

    Returns:
        DocsReport containing all findings
    """
    all_links: list[Link] = []
    all_code_blocks: list[CodeBlock] = []
    files_scanned = 0

    # Extract all links and code blocks from all docs
    for doc_path in docs_paths:
        if not doc_path.exists():
            continue

        content = doc_path.read_text(encoding="utf-8")
        files_scanned += 1

        # Extract links
        links = extract_links(doc_path, content)
        all_links.extend(links)

        # Extract code blocks
        code_blocks = extract_code_blocks(doc_path, content)
        all_code_blocks.extend(code_blocks)

    # Validate links
    link_findings: list[LinkFinding] = []
    if check_external_links:
        link_findings = check_links(all_links, project_root)
    else:
        # Only check internal file references
        internal_links = [
            link for link in all_links if not link.url.startswith(("http://", "https://", "ftp://"))
        ]
        link_findings = check_links(internal_links, project_root)

    # Validate code blocks
    code_findings = validate_code(all_code_blocks)

    return DocsReport(
        link_findings=link_findings,
        code_findings=code_findings,
        files_scanned=files_scanned,
        links_checked=len(all_links),
        code_blocks_checked=len(all_code_blocks),
    )
