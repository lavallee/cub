"""
Dead code detection for Python using AST analysis.

Detects unused imports, functions, classes, methods, and variables by comparing
definitions against references.
"""

import ast
import json
import re
import subprocess
from pathlib import Path
from typing import Literal, NamedTuple

from .models import DeadCodeFinding, DeadCodeReport


class Definition(NamedTuple):
    """A definition found in the AST."""

    name: str
    kind: Literal["import", "function", "class", "variable", "method"]
    line_number: int
    file_path: str


class ASTDefinitionVisitor(ast.NodeVisitor):
    """
    AST visitor that collects all definitions.

    Finds:
    - Import statements (import foo, from foo import bar)
    - Function and method definitions
    - Class definitions
    - Variable assignments at module/class level
    """

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.definitions: list[Definition] = []
        self._class_stack: list[str] = []  # Track nested classes

    def visit_Import(self, node: ast.Import) -> None:
        """Collect imports: import foo, bar"""
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            self.definitions.append(
                Definition(
                    name=name,
                    kind="import",
                    line_number=node.lineno,
                    file_path=self.file_path,
                )
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Collect from imports: from foo import bar"""
        for alias in node.names:
            # Skip wildcard imports
            if alias.name == "*":
                continue
            name = alias.asname if alias.asname else alias.name
            self.definitions.append(
                Definition(
                    name=name,
                    kind="import",
                    line_number=node.lineno,
                    file_path=self.file_path,
                )
            )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Collect function definitions."""
        kind: Literal["method", "function"] = "method" if self._class_stack else "function"
        self.definitions.append(
            Definition(
                name=node.name,
                kind=kind,
                line_number=node.lineno,
                file_path=self.file_path,
            )
        )
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Collect async function definitions."""
        kind: Literal["method", "function"] = "method" if self._class_stack else "function"
        self.definitions.append(
            Definition(
                name=node.name,
                kind=kind,
                line_number=node.lineno,
                file_path=self.file_path,
            )
        )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Collect class definitions."""
        self.definitions.append(
            Definition(
                name=node.name,
                kind="class",
                line_number=node.lineno,
                file_path=self.file_path,
            )
        )
        # Track class scope for method detection
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        """Collect module-level variable assignments."""
        # Only track module-level and class-level variables
        # Skip function-level variables (too many false positives)
        if not self._is_in_function_scope(node):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.definitions.append(
                        Definition(
                            name=target.id,
                            kind="variable",
                            line_number=node.lineno,
                            file_path=self.file_path,
                        )
                    )
        self.generic_visit(node)

    def _is_in_function_scope(self, node: ast.AST) -> bool:
        """Check if node is inside a function (not just class)."""
        # This is a simplified check - we only care about module/class level
        # For now, we'll rely on not being in a function def context
        # This would need enhancement for proper scope tracking
        return False  # Simplified: treat all assigns at module/class level


class ASTReferenceVisitor(ast.NodeVisitor):
    """
    AST visitor that collects all name references.

    Finds all places where names are used (not defined).
    """

    def __init__(self) -> None:
        self.references: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        """Collect name references (excluding Store context which is assignment)."""
        if isinstance(node.ctx, ast.Load):
            self.references.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Collect attribute access (e.g., foo.bar uses 'foo')."""
        # Only add the base name, not the attribute
        if isinstance(node.value, ast.Name):
            self.references.add(node.value.id)
        self.generic_visit(node)


def find_python_definitions(file_path: Path) -> list[Definition]:
    """
    Parse a Python file and extract all definitions.

    Args:
        file_path: Path to the Python file to analyze

    Returns:
        List of Definition objects found in the file

    Raises:
        SyntaxError: If the file contains invalid Python syntax
    """
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))

    visitor = ASTDefinitionVisitor(str(file_path))
    visitor.visit(tree)

    return visitor.definitions


def find_python_references(file_path: Path) -> set[str]:
    """
    Parse a Python file and extract all name references.

    Args:
        file_path: Path to the Python file to analyze

    Returns:
        Set of referenced names

    Raises:
        SyntaxError: If the file contains invalid Python syntax
    """
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))

    visitor = ASTReferenceVisitor()
    visitor.visit(tree)

    return visitor.references


def get_module_exports(file_path: Path) -> set[str]:
    """
    Get names explicitly exported via __all__.

    Args:
        file_path: Path to the Python file to check

    Returns:
        Set of exported names (empty if no __all__ is defined)
    """
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    # Extract list values
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        exports = set()
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                exports.add(elt.value)
                        return exports

    return set()


def should_exclude_definition(definition: Definition, exports: set[str]) -> bool:
    """
    Determine if a definition should be excluded from dead code analysis.

    Args:
        definition: The definition to check
        exports: Set of names exported via __all__

    Returns:
        True if the definition should be excluded
    """
    # Exclude if explicitly exported
    if definition.name in exports:
        return True

    # Exclude special methods and magic variables
    if definition.name.startswith("__") and definition.name.endswith("__"):
        return True

    # Exclude private names starting with _ (convention: internal API)
    # Note: This is debatable - some teams want to detect unused private functions
    # For now, we'll flag them but could make this configurable
    # if definition.name.startswith("_"):
    #     return True

    return False


def detect_unused(
    project_root: Path,
    exclude_patterns: list[str] | None = None,
) -> DeadCodeReport:
    """
    Detect unused code in a Python project.

    Args:
        project_root: Root directory of the project to analyze
        exclude_patterns: List of glob patterns to exclude (e.g., ["**/test_*.py"])

    Returns:
        DeadCodeReport containing all findings
    """
    if exclude_patterns is None:
        exclude_patterns = []

    # Collect all Python files
    python_files = list(project_root.rglob("*.py"))

    # Apply exclusions
    excluded_paths: set[Path] = set()
    for pattern in exclude_patterns:
        excluded_paths.update(project_root.glob(pattern))

    python_files = [f for f in python_files if f not in excluded_paths]

    # Collect all definitions across all files
    all_definitions: list[Definition] = []
    all_references: set[str] = set()
    files_scanned = 0

    for py_file in python_files:
        try:
            definitions = find_python_definitions(py_file)
            references = find_python_references(py_file)
            exports = get_module_exports(py_file)

            # Filter out excluded definitions
            definitions = [d for d in definitions if not should_exclude_definition(d, exports)]

            all_definitions.extend(definitions)
            all_references.update(references)
            files_scanned += 1

        except (SyntaxError, UnicodeDecodeError):
            # Skip files with syntax errors or encoding issues
            continue

    # Find unused definitions
    findings: list[DeadCodeFinding] = []
    for definition in all_definitions:
        if definition.name not in all_references:
            findings.append(
                DeadCodeFinding(
                    file_path=definition.file_path,
                    line_number=definition.line_number,
                    name=definition.name,
                    kind=definition.kind,
                    reason="No references found in project",
                )
            )

    return DeadCodeReport(
        findings=findings,
        files_scanned=files_scanned,
        total_definitions=len(all_definitions),
    )


# ============================================================================
# Bash Dead Code Detection
# ============================================================================


class BashDefinition(NamedTuple):
    """A Bash function definition."""

    name: str
    line_number: int
    file_path: str


def find_bash_functions(file_path: Path) -> list[BashDefinition]:
    """
    Find all function definitions in a Bash script using regex.

    Matches both styles:
    - function_name() { ... }
    - function function_name() { ... }
    - function function_name { ... }

    Args:
        file_path: Path to the Bash script to analyze

    Returns:
        List of BashDefinition objects found in the file
    """
    try:
        source = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError, FileNotFoundError):
        return []

    definitions: list[BashDefinition] = []

    # Regex patterns for Bash function definitions
    # Pattern 1: function_name() {
    pattern1 = re.compile(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*\)\s*\{", re.MULTILINE)
    # Pattern 2: function function_name() {  or  function function_name {
    pattern2 = re.compile(
        r"^\s*function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\(\s*\))?\s*\{", re.MULTILINE
    )

    # Find all matches with line numbers
    for match in pattern1.finditer(source):
        func_name = match.group(1)
        # Find where the function name starts, not where the pattern starts
        # The pattern may match leading whitespace or newlines
        func_name_pos = match.start() + match.group(0).index(func_name)
        line_number = source[:func_name_pos].count("\n") + 1
        definitions.append(
            BashDefinition(name=func_name, line_number=line_number, file_path=str(file_path))
        )

    for match in pattern2.finditer(source):
        func_name = match.group(1)
        # Find where the function name starts
        func_name_pos = match.start() + match.group(0).index(func_name)
        line_number = source[:func_name_pos].count("\n") + 1
        # Check if already added by pattern1 (function name() { syntax)
        if not any(d.name == func_name and d.line_number == line_number for d in definitions):
            definitions.append(
                BashDefinition(name=func_name, line_number=line_number, file_path=str(file_path))
            )

    return definitions


def find_bash_calls(file_path: Path) -> set[str]:
    """
    Find all function calls in a Bash script using regex.

    This is a heuristic approach that looks for:
    - Word boundaries followed by function names
    - Excludes calls inside strings and comments

    Args:
        file_path: Path to the Bash script to analyze

    Returns:
        Set of function names that appear to be called
    """
    try:
        source = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError, FileNotFoundError):
        return set()

    # Remove comments, strings, and function definitions
    lines = []
    # Regex patterns to identify function definition lines
    func_def_pattern1 = re.compile(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*\)\s*\{")
    func_def_pattern2 = re.compile(r"^\s*function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\(\s*\))?\s*\{")

    for line in source.split("\n"):
        # Skip function definition lines entirely
        if func_def_pattern1.match(line) or func_def_pattern2.match(line):
            continue

        # Remove everything after # (basic comment removal)
        # This is a simple heuristic that doesn't handle # in strings properly
        # but is good enough for dead code detection
        if "#" in line:
            # Find first # not inside quotes (simplified)
            in_single_quote = False
            in_double_quote = False
            for i, char in enumerate(line):
                if char == "'" and not in_double_quote:
                    in_single_quote = not in_single_quote
                elif char == '"' and not in_single_quote:
                    in_double_quote = not in_double_quote
                elif char == "#" and not in_single_quote and not in_double_quote:
                    line = line[:i]
                    break

        # Remove string literals (simplified - remove content between quotes)
        # This prevents matching function names in strings like "call unused_function"
        line = re.sub(r'"[^"]*"', '""', line)  # Remove double-quoted strings
        line = re.sub(r"'[^']*'", "''", line)  # Remove single-quoted strings

        lines.append(line)
    source = "\n".join(lines)

    # Find all potential function calls
    # Look for identifiers that aren't part of assignments or definitions
    # Pattern: word boundary + identifier + optional whitespace + (
    # Or: word boundary + identifier at end of line or before ;, |, &&, ||, etc
    pattern = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b")

    calls: set[str] = set()
    for match in pattern.finditer(source):
        func_name = match.group(1)
        # Exclude common Bash keywords and builtins
        if func_name not in {
            "if",
            "then",
            "else",
            "elif",
            "fi",
            "for",
            "while",
            "do",
            "done",
            "case",
            "esac",
            "function",
            "local",
            "export",
            "return",
            "echo",
            "printf",
            "read",
            "cd",
            "pwd",
            "source",
            "set",
            "shift",
            "test",
            "true",
            "false",
            "exit",
            "break",
            "continue",
            "readonly",
            "declare",
            "typeset",
            "unset",
            "eval",
            "exec",
            "trap",
            "wait",
            "kill",
            "sleep",
            "date",
            "grep",
            "sed",
            "awk",
            "sort",
            "uniq",
            "wc",
            "cut",
            "tr",
            "find",
            "xargs",
            "cat",
            "head",
            "tail",
            "tee",
            "touch",
            "mkdir",
            "rm",
            "mv",
            "cp",
            "ln",
            "chmod",
            "chown",
            "ls",
            "du",
            "df",
            "mount",
            "umount",
        }:
            calls.add(func_name)

    return calls


def run_shellcheck(file_path: Path) -> list[dict[str, object]]:
    """
    Run shellcheck on a Bash script and return warnings.

    Args:
        file_path: Path to the Bash script to check

    Returns:
        List of shellcheck warnings as dictionaries (empty if shellcheck not available)
    """
    try:
        result = subprocess.run(
            ["shellcheck", "--format=json", str(file_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode in (0, 1):  # 0 = no issues, 1 = issues found
            return json.loads(result.stdout) if result.stdout else []
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        # shellcheck not installed or timed out or invalid JSON
        pass

    return []


def detect_unused_bash(
    project_root: Path,
    exclude_patterns: list[str] | None = None,
) -> DeadCodeReport:
    """
    Detect unused Bash functions in a project.

    Args:
        project_root: Root directory of the project to analyze
        exclude_patterns: List of glob patterns to exclude (e.g., ["**/test_*.sh"])

    Returns:
        DeadCodeReport containing all findings
    """
    if exclude_patterns is None:
        exclude_patterns = []

    # Collect all Bash files
    bash_files = list(project_root.rglob("*.sh"))

    # Apply exclusions
    excluded_paths: set[Path] = set()
    for pattern in exclude_patterns:
        excluded_paths.update(project_root.glob(pattern))

    bash_files = [f for f in bash_files if f not in excluded_paths]

    # Collect all definitions and calls across all files
    all_definitions: list[BashDefinition] = []
    all_calls: set[str] = set()
    files_scanned = 0

    for bash_file in bash_files:
        try:
            definitions = find_bash_functions(bash_file)
            calls = find_bash_calls(bash_file)

            all_definitions.extend(definitions)
            all_calls.update(calls)
            files_scanned += 1
        except Exception:
            # Skip files that can't be processed
            continue

    # Integrate shellcheck warnings (optional)
    shellcheck_unused: set[tuple[str, int]] = set()
    for bash_file in bash_files:
        warnings = run_shellcheck(bash_file)
        for warning in warnings:
            # SC2317: Command appears to be unreachable (shellcheck unused function detection)
            if isinstance(warning, dict) and warning.get("code") == 2317:
                line = warning.get("line")
                if isinstance(line, int):
                    shellcheck_unused.add((str(bash_file), line))

    # Find unused definitions
    findings: list[DeadCodeFinding] = []
    for definition in all_definitions:
        # Check if function is called anywhere
        is_unused = definition.name not in all_calls

        # Also check shellcheck results
        is_flagged_by_shellcheck = (
            definition.file_path,
            definition.line_number,
        ) in shellcheck_unused

        if is_unused or is_flagged_by_shellcheck:
            reason = "No references found in project"
            if is_flagged_by_shellcheck:
                reason = "Flagged by shellcheck as unreachable"

            findings.append(
                DeadCodeFinding(
                    file_path=definition.file_path,
                    line_number=definition.line_number,
                    name=definition.name,
                    kind="bash_function",
                    reason=reason,
                )
            )

    return DeadCodeReport(
        findings=findings,
        files_scanned=files_scanned,
        total_definitions=len(all_definitions),
    )
