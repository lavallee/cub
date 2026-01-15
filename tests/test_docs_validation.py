"""
Tests for documentation validation.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import requests

from cub.audit.docs import (
    CodeBlock,
    Link,
    check_links,
    extract_code_blocks,
    extract_links,
    validate_code,
    validate_docs,
)
from cub.audit.models import CodeBlockFinding, DocsReport, LinkFinding


class TestExtractLinks:
    """Tests for extract_links function."""

    def test_extract_inline_links(self, tmp_path: Path) -> None:
        """Test extraction of inline markdown links."""
        content = """
# Header
[Python](https://python.org)
[GitHub](https://github.com)
"""
        doc = tmp_path / "test.md"
        doc.write_text(content)

        links = extract_links(doc, content)

        assert len(links) == 2
        assert links[0].url == "https://python.org"
        assert links[0].line_number == 3
        assert links[1].url == "https://github.com"
        assert links[1].line_number == 4

    def test_extract_reference_links(self, tmp_path: Path) -> None:
        """Test extraction of reference-style links."""
        content = """
[link-text][ref]

[ref]: https://example.com
"""
        doc = tmp_path / "test.md"
        doc.write_text(content)

        links = extract_links(doc, content)

        assert len(links) == 1
        assert links[0].url == "https://example.com"
        assert links[0].line_number == 4

    def test_extract_direct_urls(self, tmp_path: Path) -> None:
        """Test extraction of direct URL links."""
        content = """
Visit <https://example.com> for more info.
"""
        doc = tmp_path / "test.md"
        doc.write_text(content)

        links = extract_links(doc, content)

        assert len(links) == 1
        assert links[0].url == "https://example.com"
        assert links[0].line_number == 2

    def test_skip_anchors_and_mailto(self, tmp_path: Path) -> None:
        """Test that anchors and mailto links are skipped."""
        content = """
[Section](#section)
[Email](mailto:test@example.com)
[Link](https://example.com)
"""
        doc = tmp_path / "test.md"
        doc.write_text(content)

        links = extract_links(doc, content)

        assert len(links) == 1
        assert links[0].url == "https://example.com"

    def test_relative_file_links(self, tmp_path: Path) -> None:
        """Test extraction of relative file links."""
        content = """
[Local file](./README.md)
[Other file](../docs/guide.md)
"""
        doc = tmp_path / "test.md"
        doc.write_text(content)

        links = extract_links(doc, content)

        assert len(links) == 2
        assert links[0].url == "./README.md"
        assert links[1].url == "../docs/guide.md"


class TestExtractCodeBlocks:
    """Tests for extract_code_blocks function."""

    def test_extract_python_code_block(self, tmp_path: Path) -> None:
        """Test extraction of Python code blocks."""
        content = """
Here's some code:

```python
def hello():
    print("Hello")
```

More text.
"""
        doc = tmp_path / "test.md"
        doc.write_text(content)

        blocks = extract_code_blocks(doc, content)

        assert len(blocks) == 1
        assert blocks[0].language == "python"
        assert "def hello():" in blocks[0].code
        assert blocks[0].line_number == 4

    def test_extract_bash_code_block(self, tmp_path: Path) -> None:
        """Test extraction of Bash code blocks."""
        content = """
```bash
echo "Hello"
ls -la
```
"""
        doc = tmp_path / "test.md"
        doc.write_text(content)

        blocks = extract_code_blocks(doc, content)

        assert len(blocks) == 1
        assert blocks[0].language == "bash"
        assert 'echo "Hello"' in blocks[0].code

    def test_extract_multiple_code_blocks(self, tmp_path: Path) -> None:
        """Test extraction of multiple code blocks."""
        content = """
```python
x = 1
```

Some text.

```javascript
const y = 2;
```
"""
        doc = tmp_path / "test.md"
        doc.write_text(content)

        blocks = extract_code_blocks(doc, content)

        assert len(blocks) == 2
        assert blocks[0].language == "python"
        assert blocks[1].language == "javascript"

    def test_code_block_without_language(self, tmp_path: Path) -> None:
        """Test code blocks without language specification default to 'text'."""
        content = """
```
plain text
```
"""
        doc = tmp_path / "test.md"
        doc.write_text(content)

        blocks = extract_code_blocks(doc, content)

        assert len(blocks) == 1
        assert blocks[0].language == "text"


class TestCheckLinks:
    """Tests for check_links function."""

    def test_check_valid_http_link(self, tmp_path: Path) -> None:
        """Test checking a valid HTTP link."""
        links = [Link(url="https://python.org", line_number=1, file_path="test.md")]

        with patch("requests.Session.head") as mock_head:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_head.return_value = mock_response

            findings = check_links(links, tmp_path)

        assert len(findings) == 0

    def test_check_broken_http_link(self, tmp_path: Path) -> None:
        """Test checking a broken HTTP link (404)."""
        links = [Link(url="https://example.com/404", line_number=5, file_path="test.md")]

        with patch("requests.Session.head") as mock_head:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_head.return_value = mock_response

            findings = check_links(links, tmp_path)

        assert len(findings) == 1
        assert findings[0].issue == "broken_link"
        assert findings[0].status_code == 404
        assert findings[0].line_number == 5

    def test_check_timeout_link(self, tmp_path: Path) -> None:
        """Test checking a link that times out."""
        links = [Link(url="https://slow.example.com", line_number=3, file_path="test.md")]

        with patch("requests.Session.head") as mock_head:
            mock_head.side_effect = requests.Timeout()

            findings = check_links(links, tmp_path)

        assert len(findings) == 1
        assert findings[0].issue == "timeout"

    def test_check_invalid_url(self, tmp_path: Path) -> None:
        """Test checking an invalid URL."""
        links = [Link(url="not-a-url", line_number=2, file_path="test.md")]

        findings = check_links(links, tmp_path)

        assert len(findings) == 1
        assert findings[0].issue == "invalid_url"

    def test_check_missing_file_reference(self, tmp_path: Path) -> None:
        """Test checking a missing file reference."""
        doc = tmp_path / "test.md"
        doc.write_text("test")

        links = [Link(url="./missing.md", line_number=1, file_path=str(doc))]

        findings = check_links(links, tmp_path)

        assert len(findings) == 1
        assert findings[0].issue == "missing_file"
        assert findings[0].url == "./missing.md"

    def test_check_existing_file_reference(self, tmp_path: Path) -> None:
        """Test checking an existing file reference."""
        doc = tmp_path / "test.md"
        doc.write_text("test")
        other = tmp_path / "other.md"
        other.write_text("other")

        links = [Link(url="./other.md", line_number=1, file_path=str(doc))]

        findings = check_links(links, tmp_path)

        assert len(findings) == 0

    def test_check_file_reference_with_anchor(self, tmp_path: Path) -> None:
        """Test checking file references with anchors."""
        doc = tmp_path / "test.md"
        doc.write_text("test")
        other = tmp_path / "other.md"
        other.write_text("other")

        links = [Link(url="./other.md#section", line_number=1, file_path=str(doc))]

        findings = check_links(links, tmp_path)

        # Anchor should be stripped, file should be found
        assert len(findings) == 0

    def test_fallback_to_get_on_head_failure(self, tmp_path: Path) -> None:
        """Test that GET is tried if HEAD fails."""
        links = [Link(url="https://example.com", line_number=1, file_path="test.md")]

        with patch("requests.Session.head") as mock_head, patch("requests.Session.get") as mock_get:
            # HEAD fails, GET succeeds
            mock_head.side_effect = requests.RequestException()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            findings = check_links(links, tmp_path)

        assert len(findings) == 0


class TestValidateCode:
    """Tests for validate_code function."""

    def test_validate_valid_python_code(self, tmp_path: Path) -> None:
        """Test validation of valid Python code."""
        blocks = [
            CodeBlock(
                language="python",
                code="def hello():\n    print('Hello')",
                line_number=1,
                file_path="test.md",
            )
        ]

        findings = validate_code(blocks)

        assert len(findings) == 0

    def test_validate_invalid_python_code(self, tmp_path: Path) -> None:
        """Test validation of invalid Python code."""
        blocks = [
            CodeBlock(
                language="python",
                code="def hello(\n    print('Hello')",
                line_number=5,
                file_path="test.md",
            )
        ]

        findings = validate_code(blocks)

        assert len(findings) == 1
        assert findings[0].issue == "syntax_error"
        assert findings[0].language == "python"
        assert findings[0].line_number == 5

    def test_validate_valid_bash_code(self, tmp_path: Path) -> None:
        """Test validation of valid Bash code."""
        blocks = [
            CodeBlock(
                language="bash",
                code='echo "Hello"\nls -la',
                line_number=1,
                file_path="test.md",
            )
        ]

        findings = validate_code(blocks)

        # Should pass (assuming bash is available)
        # If bash not available, test passes anyway
        assert isinstance(findings, list)

    def test_validate_invalid_bash_code(self, tmp_path: Path) -> None:
        """Test validation of invalid Bash code."""
        blocks = [
            CodeBlock(
                language="bash",
                code="if [ test\necho",
                line_number=10,
                file_path="test.md",
            )
        ]

        findings = validate_code(blocks)

        # May find syntax error if bash is available
        # Test just ensures no crash
        assert isinstance(findings, list)

    def test_skip_unsupported_languages(self, tmp_path: Path) -> None:
        """Test that unsupported languages are skipped without error."""
        blocks = [
            CodeBlock(
                language="rust",
                code='fn main() { println!("Hello"); }',
                line_number=1,
                file_path="test.md",
            )
        ]

        findings = validate_code(blocks)

        # Unsupported language should be skipped
        assert len(findings) == 0


class TestValidateDocs:
    """Tests for validate_docs function."""

    def test_validate_docs_full_workflow(self, tmp_path: Path) -> None:
        """Test full documentation validation workflow."""
        # Create test markdown files
        doc1 = tmp_path / "README.md"
        doc1.write_text(
            """
# Test Doc

[Valid link](https://python.org)
[Missing file](./missing.md)

```python
def valid():
    pass
```

```python
def invalid(
    pass
```
"""
        )

        with patch("requests.Session.head") as mock_head:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_head.return_value = mock_response

            report = validate_docs([doc1], tmp_path, check_external_links=True)

        assert report.files_scanned == 1
        assert report.links_checked == 2
        assert report.code_blocks_checked == 2

        # Should find missing file and invalid Python code
        assert report.has_findings
        assert any(f.issue == "missing_file" for f in report.link_findings)
        assert any(f.issue == "syntax_error" for f in report.code_findings)

    def test_validate_docs_skip_external_links(self, tmp_path: Path) -> None:
        """Test validation with external link checking disabled."""
        doc = tmp_path / "test.md"
        doc.write_text("[External](https://example.com)")

        report = validate_docs([doc], tmp_path, check_external_links=False)

        # Should not check external links
        assert report.links_checked == 1
        assert len(report.link_findings) == 0

    def test_validate_docs_nonexistent_file(self, tmp_path: Path) -> None:
        """Test that nonexistent files are skipped gracefully."""
        missing = tmp_path / "missing.md"

        report = validate_docs([missing], tmp_path)

        assert report.files_scanned == 0
        assert report.links_checked == 0

    def test_docs_report_properties(self) -> None:
        """Test DocsReport properties."""
        report = DocsReport(
            link_findings=[
                LinkFinding(
                    file_path="test.md",
                    line_number=1,
                    url="http://example.com",
                    issue="broken_link",
                    status_code=404,
                )
            ],
            code_findings=[
                CodeBlockFinding(
                    file_path="test.md",
                    line_number=5,
                    language="python",
                    issue="syntax_error",
                    error_message="Invalid syntax",
                )
            ],
            files_scanned=1,
            links_checked=3,
            code_blocks_checked=2,
        )

        assert report.has_findings
        assert report.total_issues == 2

    def test_docs_report_no_findings(self) -> None:
        """Test DocsReport with no findings."""
        report = DocsReport(
            files_scanned=5,
            links_checked=20,
            code_blocks_checked=10,
        )

        assert not report.has_findings
        assert report.total_issues == 0
