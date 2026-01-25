"""
Tool approval service for managing execution permissions.

This module provides ApprovalService, which manages tool approval configurations
and enforces approval requirements based on the freedom level setting. The service
loads approval settings from user configuration and provides methods to check
whether a tool requires approval before execution.

The freedom dial controls autonomy level:
- LOW: Prompt before every tool execution (maximum safety)
- MEDIUM: Prompt only for risky/unknown tools (balanced)
- HIGH: Execute tools without prompting (maximum autonomy)

Example:
    >>> from pathlib import Path
    >>> from cub.core.tools.approvals import ApprovalService
    >>> from cub.core.tools.models import FreedomLevel
    >>>
    >>> # Initialize with default settings
    >>> service = ApprovalService()
    >>>
    >>> # Check if tool requires approval
    >>> if service.requires_approval("rm", action="delete"):
    ...     print("Tool requires user approval")
    >>>
    >>> # Update freedom level
    >>> service.set_freedom_level(FreedomLevel.HIGH)
    >>>
    >>> # Mark a tool as safe
    >>> service.mark_safe("grep")
    >>>
    >>> # Mark a tool as risky
    >>> service.mark_risky("kubectl")
    >>>
    >>> # Save approval settings
    >>> service.save()
"""

import json
import os
import tempfile
from pathlib import Path

from cub.core.tools.models import FreedomLevel, ToolApprovals


class ApprovalService:
    """
    Service for managing tool approval configurations.

    ApprovalService manages the tool approval settings stored in user configuration
    and provides methods to check approval requirements, update freedom levels,
    and classify tools as safe or risky.

    The approval configuration is stored at:
    - ~/.config/cub/tools/approvals.json (or XDG_CONFIG_HOME equivalent)

    Attributes:
        approvals_file: Path to the approvals configuration file
        approvals: Current ToolApprovals configuration

    Example:
        >>> # Initialize service (loads from disk)
        >>> service = ApprovalService()
        >>>
        >>> # Check if tool requires approval
        >>> if service.requires_approval("kubectl", action="delete"):
        ...     print("Requires approval")
        >>>
        >>> # Change freedom level
        >>> service.set_freedom_level(FreedomLevel.HIGH)
        >>> service.save()
        >>>
        >>> # Mark tools as safe or risky
        >>> service.mark_safe("grep")
        >>> service.mark_risky("rm")
        >>> service.save()
    """

    def __init__(self, approvals_file: Path | None = None) -> None:
        """
        Initialize the approval service.

        Args:
            approvals_file: Path to approvals configuration file.
                If None, defaults to ~/.config/cub/tools/approvals.json
        """
        if approvals_file is None:
            config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
            approvals_file = config_home / "cub" / "tools" / "approvals.json"

        self.approvals_file = Path(approvals_file)
        self.approvals = self._load()

    def _load(self) -> ToolApprovals:
        """
        Load approval configuration from disk.

        Returns an empty configuration with default freedom level (MEDIUM)
        if the file doesn't exist yet.

        Returns:
            ToolApprovals configuration

        Raises:
            ValueError: If configuration file is malformed
            json.JSONDecodeError: If configuration contains invalid JSON
        """
        if not self.approvals_file.exists():
            # Return default approvals with MEDIUM freedom level
            return ToolApprovals(
                freedom_level=FreedomLevel.MEDIUM,
                risky_tools=[],
                safe_tools=[],
                always_prompt_tools=[],
            )

        with open(self.approvals_file, encoding="utf-8") as f:
            data = json.load(f)
            return ToolApprovals.model_validate(data)

    def save(self) -> Path:
        """
        Save approval configuration to disk with atomic write.

        Creates parent directories if they don't exist.
        Uses atomic write (write to temp file, then rename) to prevent corruption.

        Returns:
            Path to the saved configuration file

        Raises:
            OSError: If file cannot be written

        Example:
            >>> service = ApprovalService()
            >>> service.mark_safe("grep")
            >>> service.save()
            PosixPath('/home/user/.config/cub/tools/approvals.json')
        """
        # Ensure parent directory exists
        self.approvals_file.parent.mkdir(parents=True, exist_ok=True)

        # Serialize approvals to JSON with nice formatting
        json_str = json.dumps(self.approvals.model_dump(mode="json"), indent=2)

        # Atomic write: write to temp file in same directory, then rename
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.approvals_file.parent,
            delete=False,
            suffix=".tmp",
        ) as tmp:
            tmp.write(json_str)
            tmp.flush()
            tmp_path = Path(tmp.name)

        # Atomic rename (replaces existing file)
        tmp_path.replace(self.approvals_file)

        return self.approvals_file

    def requires_approval(self, tool_id: str, action: str = "") -> bool:
        """
        Check if a tool requires approval before execution.

        Delegates to ToolApprovals.requires_approval() with current configuration.

        Args:
            tool_id: Tool identifier to check
            action: Optional action being performed (for future action-based rules)

        Returns:
            True if approval is required, False otherwise

        Example:
            >>> service = ApprovalService()
            >>> service.requires_approval("rm")
            True
            >>> service.set_freedom_level(FreedomLevel.HIGH)
            >>> service.requires_approval("rm")
            False
        """
        return self.approvals.requires_approval(tool_id, action)

    def set_freedom_level(self, level: FreedomLevel) -> None:
        """
        Set the freedom level for tool execution.

        Args:
            level: FreedomLevel to set (LOW, MEDIUM, or HIGH)

        Example:
            >>> service = ApprovalService()
            >>> service.set_freedom_level(FreedomLevel.HIGH)
            >>> service.save()
        """
        self.approvals.freedom_level = level

    def get_freedom_level(self) -> FreedomLevel:
        """
        Get the current freedom level.

        Returns:
            Current FreedomLevel

        Example:
            >>> service = ApprovalService()
            >>> service.get_freedom_level()
            <FreedomLevel.MEDIUM: 'medium'>
        """
        return self.approvals.freedom_level

    def mark_safe(self, tool_id: str) -> None:
        """
        Mark a tool as safe for automatic execution.

        Args:
            tool_id: Tool identifier to mark as safe

        Example:
            >>> service = ApprovalService()
            >>> service.mark_safe("grep")
            >>> service.save()
        """
        self.approvals.mark_safe(tool_id)

    def mark_risky(self, tool_id: str) -> None:
        """
        Mark a tool as risky (requires approval at medium freedom).

        Args:
            tool_id: Tool identifier to mark as risky

        Example:
            >>> service = ApprovalService()
            >>> service.mark_risky("kubectl")
            >>> service.save()
        """
        self.approvals.mark_risky(tool_id)

    def mark_always_prompt(self, tool_id: str) -> None:
        """
        Mark a tool to always require approval.

        Args:
            tool_id: Tool identifier to mark as always requiring approval

        Example:
            >>> service = ApprovalService()
            >>> service.mark_always_prompt("rm")
            >>> service.save()
        """
        self.approvals.mark_always_prompt(tool_id)

    def get_safe_tools(self) -> list[str]:
        """
        Get list of tools marked as safe.

        Returns:
            List of tool IDs marked as safe
        """
        return self.approvals.safe_tools.copy()

    def get_risky_tools(self) -> list[str]:
        """
        Get list of tools marked as risky.

        Returns:
            List of tool IDs marked as risky
        """
        return self.approvals.risky_tools.copy()

    def get_always_prompt_tools(self) -> list[str]:
        """
        Get list of tools that always require approval.

        Returns:
            List of tool IDs that always require approval
        """
        return self.approvals.always_prompt_tools.copy()

    @classmethod
    def user(cls) -> "ApprovalService":
        """
        Create an approval service for user-level configuration.

        The user-level configuration is stored at:
        - ~/.config/cub/tools/approvals.json (or XDG_CONFIG_HOME equivalent)

        Returns:
            ApprovalService for user-level configuration

        Example:
            >>> service = ApprovalService.user()
            >>> service.get_freedom_level()
            <FreedomLevel.MEDIUM: 'medium'>
        """
        return cls()

    @classmethod
    def project(cls, project_dir: Path | None = None) -> "ApprovalService":
        """
        Create an approval service for project-level configuration.

        The project-level configuration is stored at:
        - .cub/tools/approvals.json (relative to project root)

        Args:
            project_dir: Project directory (defaults to current directory)

        Returns:
            ApprovalService for project-level configuration

        Example:
            >>> service = ApprovalService.project()
            >>> service.get_freedom_level()
            <FreedomLevel.MEDIUM: 'medium'>
        """
        if project_dir is None:
            project_dir = Path.cwd()
        approvals_file = project_dir / ".cub" / "tools" / "approvals.json"
        return cls(approvals_file)
