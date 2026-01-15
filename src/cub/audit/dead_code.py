"""
Dead code detection for Python using AST analysis.

Detects unused imports, functions, classes, methods, and variables by comparing
definitions against references.
"""

import ast
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
