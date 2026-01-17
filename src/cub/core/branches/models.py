"""
Models for branch-epic bindings.

Provides Pydantic models for representing branch bindings stored
in .beads/branches.yaml.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BranchBinding(BaseModel):
    """
    Represents a binding between a git branch and a beads epic.

    Branch bindings are stored in .beads/branches.yaml and track the
    relationship between feature branches and their associated epics.
    """

    epic_id: str = Field(..., description="The beads epic ID this branch is bound to")
    branch_name: str = Field(..., description="The git branch name")
    base_branch: str = Field(default="main", description="The target branch for merging")
    status: str = Field(default="active", description="Binding status: active, merged, or closed")
    created_at: datetime = Field(
        default_factory=lambda: datetime.utcnow(),
        description="When the binding was created",
    )
    pr_number: int | None = Field(default=None, description="Associated PR number if created")
    merged: bool = Field(default=False, description="Whether the branch has been merged")


class BranchBindingsFile(BaseModel):
    """
    Root model for the branches.yaml file.

    Contains a list of all branch-epic bindings.
    """

    bindings: list[BranchBinding] = Field(default_factory=list)


class ResolvedTarget(BaseModel):
    """
    Result of resolving a user-provided target (epic ID, branch, or PR number).

    Used by PR and merge commands to determine what entity the user is referring to.
    """

    type: str = Field(
        ...,
        description="Type of resolved target: 'epic', 'branch', or 'pr'",
    )
    epic_id: str | None = Field(default=None, description="Epic ID if resolved")
    branch: str | None = Field(default=None, description="Branch name if resolved")
    pr_number: int | None = Field(default=None, description="PR number if resolved")
    binding: BranchBinding | None = Field(default=None, description="Associated binding if found")
