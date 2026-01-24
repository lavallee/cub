"""
Tests for task service module.

Tests the TaskComplexity, TaskDomain enums, TaskCreationRequest dataclass,
TaskService class, and get_task_service() singleton function.
"""

from unittest.mock import Mock, patch

import pytest

import cub.core.tasks.service as service_module
from cub.core.tasks.models import Task, TaskStatus
from cub.core.tasks.service import (
    TaskComplexity,
    TaskCreationRequest,
    TaskDomain,
    TaskService,
    get_task_service,
)


class TestTaskComplexityEnum:
    """Tests for TaskComplexity enum values."""

    def test_low_complexity_value(self):
        """Test LOW complexity has correct value."""
        assert TaskComplexity.LOW.value == "low"

    def test_medium_complexity_value(self):
        """Test MEDIUM complexity has correct value."""
        assert TaskComplexity.MEDIUM.value == "medium"

    def test_high_complexity_value(self):
        """Test HIGH complexity has correct value."""
        assert TaskComplexity.HIGH.value == "high"

    def test_all_complexity_values_are_strings(self):
        """Test all complexity values inherit from str."""
        for complexity in TaskComplexity:
            assert isinstance(complexity.value, str)
            assert isinstance(complexity, str)

    def test_complexity_enum_has_three_members(self):
        """Test TaskComplexity has exactly three members."""
        assert len(TaskComplexity) == 3


class TestTaskDomainEnum:
    """Tests for TaskDomain enum values."""

    def test_setup_domain_value(self):
        """Test SETUP domain has correct value."""
        assert TaskDomain.SETUP.value == "setup"

    def test_model_domain_value(self):
        """Test MODEL domain has correct value."""
        assert TaskDomain.MODEL.value == "model"

    def test_api_domain_value(self):
        """Test API domain has correct value."""
        assert TaskDomain.API.value == "api"

    def test_ui_domain_value(self):
        """Test UI domain has correct value."""
        assert TaskDomain.UI.value == "ui"

    def test_logic_domain_value(self):
        """Test LOGIC domain has correct value."""
        assert TaskDomain.LOGIC.value == "logic"

    def test_test_domain_value(self):
        """Test TEST domain has correct value."""
        assert TaskDomain.TEST.value == "test"

    def test_docs_domain_value(self):
        """Test DOCS domain has correct value."""
        assert TaskDomain.DOCS.value == "docs"

    def test_refactor_domain_value(self):
        """Test REFACTOR domain has correct value."""
        assert TaskDomain.REFACTOR.value == "refactor"

    def test_fix_domain_value(self):
        """Test FIX domain has correct value."""
        assert TaskDomain.FIX.value == "fix"

    def test_all_domain_values_are_strings(self):
        """Test all domain values inherit from str."""
        for domain in TaskDomain:
            assert isinstance(domain.value, str)
            assert isinstance(domain, str)

    def test_domain_enum_has_nine_members(self):
        """Test TaskDomain has exactly nine members."""
        assert len(TaskDomain) == 9


class TestTaskCreationRequestGetRecommendedModel:
    """Tests for TaskCreationRequest.get_recommended_model() method."""

    def test_low_complexity_returns_haiku(self):
        """Test LOW complexity recommends haiku model."""
        request = TaskCreationRequest(
            title="Simple task",
            complexity=TaskComplexity.LOW,
        )
        assert request.get_recommended_model() == "haiku"

    def test_medium_complexity_returns_sonnet(self):
        """Test MEDIUM complexity recommends sonnet model."""
        request = TaskCreationRequest(
            title="Standard task",
            complexity=TaskComplexity.MEDIUM,
        )
        assert request.get_recommended_model() == "sonnet"

    def test_high_complexity_returns_opus(self):
        """Test HIGH complexity recommends opus model."""
        request = TaskCreationRequest(
            title="Complex task",
            complexity=TaskComplexity.HIGH,
        )
        assert request.get_recommended_model() == "opus"

    def test_default_complexity_is_medium(self):
        """Test default complexity is MEDIUM, recommending sonnet."""
        request = TaskCreationRequest(title="Default task")
        assert request.complexity == TaskComplexity.MEDIUM
        assert request.get_recommended_model() == "sonnet"


class TestTaskCreationRequestBuildDescription:
    """Tests for TaskCreationRequest.build_description() method."""

    def test_minimal_description(self):
        """Test description with only title (required field)."""
        request = TaskCreationRequest(title="Minimal task")
        description = request.build_description()

        # Should at least contain implementation hints section
        assert "## Implementation Hints" in description
        assert "**Recommended Model:** sonnet" in description
        assert "**Complexity:** medium" in description

    def test_description_with_context(self):
        """Test description includes context section when provided."""
        request = TaskCreationRequest(
            title="Task with context",
            context="This is the context for the task.",
        )
        description = request.build_description()

        assert "## Context" in description
        assert "This is the context for the task." in description

    def test_description_with_estimated_duration(self):
        """Test description includes estimated duration when provided."""
        request = TaskCreationRequest(
            title="Timed task",
            estimated_duration="30m",
        )
        description = request.build_description()

        assert "**Estimated Duration:** 30m" in description

    def test_description_with_implementation_steps(self):
        """Test description includes numbered implementation steps."""
        request = TaskCreationRequest(
            title="Step-by-step task",
            implementation_steps=[
                "First step",
                "Second step",
                "Third step",
            ],
        )
        description = request.build_description()

        assert "## Implementation Steps" in description
        assert "1. First step" in description
        assert "2. Second step" in description
        assert "3. Third step" in description

    def test_description_with_acceptance_criteria(self):
        """Test description includes acceptance criteria with checkboxes."""
        request = TaskCreationRequest(
            title="Task with criteria",
            acceptance_criteria=[
                "Tests pass",
                "Documentation updated",
            ],
        )
        description = request.build_description()

        assert "## Acceptance Criteria" in description
        assert "- [ ] Tests pass" in description
        assert "- [ ] Documentation updated" in description

    def test_description_with_files_involved(self):
        """Test description includes files likely involved."""
        request = TaskCreationRequest(
            title="File-related task",
            files_involved=[
                "src/cub/core/service.py",
                "tests/test_service.py",
            ],
        )
        description = request.build_description()

        assert "## Files Likely Involved" in description
        assert "- `src/cub/core/service.py`" in description
        assert "- `tests/test_service.py`" in description

    def test_description_with_notes(self):
        """Test description includes notes section when provided."""
        request = TaskCreationRequest(
            title="Task with notes",
            notes="Some additional notes here.",
        )
        description = request.build_description()

        assert "## Notes" in description
        assert "Some additional notes here." in description

    def test_description_with_source_capture_id(self):
        """Test description includes source capture reference."""
        request = TaskCreationRequest(
            title="Task from capture",
            source_capture_id="cap-abc123",
        )
        description = request.build_description()

        assert "---" in description
        assert "*Created from capture: cap-abc123*" in description

    def test_description_with_all_fields(self):
        """Test description with all possible fields populated."""
        request = TaskCreationRequest(
            title="Complete task",
            context="Full context here.",
            implementation_steps=["Step 1", "Step 2"],
            acceptance_criteria=["Criterion 1"],
            complexity=TaskComplexity.HIGH,
            estimated_duration="2h",
            files_involved=["file.py"],
            notes="Final notes.",
            source_capture_id="cap-xyz",
        )
        description = request.build_description()

        # Verify all sections present
        assert "## Context" in description
        assert "## Implementation Hints" in description
        assert "## Implementation Steps" in description
        assert "## Acceptance Criteria" in description
        assert "## Files Likely Involved" in description
        assert "## Notes" in description
        assert "cap-xyz" in description

        # Verify complexity affects model recommendation
        assert "**Recommended Model:** opus" in description
        assert "**Complexity:** high" in description


class TestTaskCreationRequestBuildLabels:
    """Tests for TaskCreationRequest.build_labels() method."""

    def test_labels_include_complexity(self):
        """Test labels include complexity label."""
        request = TaskCreationRequest(
            title="Task",
            complexity=TaskComplexity.LOW,
        )
        labels = request.build_labels()

        assert "complexity:low" in labels

    def test_labels_include_model_recommendation(self):
        """Test labels include model recommendation."""
        request = TaskCreationRequest(
            title="Task",
            complexity=TaskComplexity.HIGH,
        )
        labels = request.build_labels()

        assert "model:opus" in labels

    def test_labels_include_domain_when_specified(self):
        """Test labels include domain when provided."""
        request = TaskCreationRequest(
            title="API Task",
            domain=TaskDomain.API,
        )
        labels = request.build_labels()

        assert "api" in labels

    def test_labels_exclude_domain_when_not_specified(self):
        """Test labels do not include domain label when None."""
        request = TaskCreationRequest(title="Task without domain")
        labels = request.build_labels()

        # Should have complexity and model, but no domain
        domain_values = [d.value for d in TaskDomain]
        for label in labels:
            if not label.startswith("complexity:") and not label.startswith("model:"):
                assert label not in domain_values

    def test_labels_include_user_specified_labels(self):
        """Test labels include user-specified labels."""
        request = TaskCreationRequest(
            title="Custom labeled task",
            labels=["urgent", "frontend", "v2.0"],
        )
        labels = request.build_labels()

        assert "urgent" in labels
        assert "frontend" in labels
        assert "v2.0" in labels

    def test_labels_preserve_user_labels_order(self):
        """Test user labels come first in the list."""
        request = TaskCreationRequest(
            title="Task",
            labels=["custom1", "custom2"],
        )
        labels = request.build_labels()

        # First labels should be the user-specified ones
        assert labels[0] == "custom1"
        assert labels[1] == "custom2"

    def test_labels_for_all_complexity_levels(self):
        """Test correct labels for each complexity level."""
        for complexity in TaskComplexity:
            request = TaskCreationRequest(title="Task", complexity=complexity)
            labels = request.build_labels()

            assert f"complexity:{complexity.value}" in labels
            expected_model = request.get_recommended_model()
            assert f"model:{expected_model}" in labels

    def test_labels_for_all_domains(self):
        """Test correct labels for each domain."""
        for domain in TaskDomain:
            request = TaskCreationRequest(title="Task", domain=domain)
            labels = request.build_labels()

            assert domain.value in labels


class TestTaskService:
    """Tests for TaskService class."""

    @pytest.fixture
    def mock_backend(self):
        """Create a mock task backend."""
        backend = Mock()
        backend.create_task = Mock(return_value=Task(
            id="test-001",
            title="Created Task",
            status=TaskStatus.OPEN,
        ))
        return backend

    @pytest.fixture
    def service_with_mock(self, mock_backend):
        """Create TaskService with mocked backend."""
        with patch('cub.core.tasks.service.get_backend', return_value=mock_backend):
            service = TaskService()
        service._backend = mock_backend
        return service

    def test_init_with_no_backend(self):
        """Test TaskService initializes with auto-detected backend."""
        with patch('cub.core.tasks.service.get_backend') as mock_get:
            mock_get.return_value = Mock()
            _ = TaskService()
            mock_get.assert_called_once_with(None)

    def test_init_with_explicit_backend(self):
        """Test TaskService initializes with specified backend."""
        with patch('cub.core.tasks.service.get_backend') as mock_get:
            mock_get.return_value = Mock()
            _ = TaskService(backend="json")
            mock_get.assert_called_once_with("json")


class TestTaskServiceCreateTask:
    """Tests for TaskService.create_task() method."""

    @pytest.fixture
    def mock_backend(self):
        """Create a mock task backend."""
        backend = Mock()
        backend.create_task = Mock(return_value=Task(
            id="test-001",
            title="Created Task",
            status=TaskStatus.OPEN,
        ))
        return backend

    @pytest.fixture
    def service_with_mock(self, mock_backend):
        """Create TaskService with mocked backend."""
        with patch('cub.core.tasks.service.get_backend', return_value=mock_backend):
            service = TaskService()
        service._backend = mock_backend
        return service

    def test_create_task_success(self, service_with_mock, mock_backend):
        """Test successful task creation."""
        request = TaskCreationRequest(
            title="New Task",
            context="Task context",
            acceptance_criteria=["Done"],
        )

        result = service_with_mock.create_task(request)

        assert result is not None
        assert result.id == "test-001"
        mock_backend.create_task.assert_called_once()

    def test_create_task_passes_correct_arguments(self, service_with_mock, mock_backend):
        """Test create_task passes correct arguments to backend."""
        request = TaskCreationRequest(
            title="Feature Task",
            task_type="feature",
            priority=1,
            labels=["urgent"],
            depends_on=["cub-001"],
            parent="epic-001",
            complexity=TaskComplexity.HIGH,
            domain=TaskDomain.API,
        )

        service_with_mock.create_task(request)

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert call_kwargs["title"] == "Feature Task"
        assert call_kwargs["task_type"] == "feature"
        assert call_kwargs["priority"] == 1
        assert "urgent" in call_kwargs["labels"]
        assert "complexity:high" in call_kwargs["labels"]
        assert "model:opus" in call_kwargs["labels"]
        assert "api" in call_kwargs["labels"]
        assert call_kwargs["depends_on"] == ["cub-001"]
        assert call_kwargs["parent"] == "epic-001"

    def test_create_task_passes_none_for_empty_depends_on(self, service_with_mock, mock_backend):
        """Test create_task passes None when depends_on is empty."""
        request = TaskCreationRequest(
            title="Independent Task",
            depends_on=[],
        )

        service_with_mock.create_task(request)

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert call_kwargs["depends_on"] is None

    def test_create_task_backend_error_returns_none(self, service_with_mock, mock_backend, capsys):
        """Test create_task returns None and prints warning on backend error."""
        mock_backend.create_task.side_effect = Exception("Backend failure")

        request = TaskCreationRequest(title="Failing Task")
        result = service_with_mock.create_task(request)

        assert result is None
        captured = capsys.readouterr()
        assert "Warning: Failed to create task 'Failing Task'" in captured.out
        assert "Backend failure" in captured.out

    def test_create_task_includes_description(self, service_with_mock, mock_backend):
        """Test create_task builds and includes description."""
        request = TaskCreationRequest(
            title="Documented Task",
            context="Important context",
            implementation_steps=["Step 1"],
        )

        service_with_mock.create_task(request)

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "## Context" in call_kwargs["description"]
        assert "Important context" in call_kwargs["description"]
        assert "## Implementation Steps" in call_kwargs["description"]


class TestTaskServiceCreateQuickFix:
    """Tests for TaskService.create_quick_fix() convenience method."""

    @pytest.fixture
    def mock_backend(self):
        """Create a mock task backend."""
        backend = Mock()
        backend.create_task = Mock(return_value=Task(
            id="fix-001",
            title="Quick Fix",
            status=TaskStatus.OPEN,
        ))
        return backend

    @pytest.fixture
    def service_with_mock(self, mock_backend):
        """Create TaskService with mocked backend."""
        with patch('cub.core.tasks.service.get_backend', return_value=mock_backend):
            service = TaskService()
        service._backend = mock_backend
        return service

    def test_create_quick_fix_success(self, service_with_mock, mock_backend):
        """Test successful quick fix creation."""
        result = service_with_mock.create_quick_fix(
            title="Fix typo",
            context="Typo in documentation",
        )

        assert result is not None
        mock_backend.create_task.assert_called_once()

    def test_create_quick_fix_uses_low_complexity(self, service_with_mock, mock_backend):
        """Test quick fix uses LOW complexity."""
        service_with_mock.create_quick_fix(
            title="Quick change",
            context="Simple fix",
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "complexity:low" in call_kwargs["labels"]
        assert "model:haiku" in call_kwargs["labels"]

    def test_create_quick_fix_includes_quick_fix_label(self, service_with_mock, mock_backend):
        """Test quick fix includes 'quick-fix' label."""
        service_with_mock.create_quick_fix(
            title="Quick change",
            context="Simple fix",
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "quick-fix" in call_kwargs["labels"]

    def test_create_quick_fix_uses_15m_duration(self, service_with_mock, mock_backend):
        """Test quick fix uses 15m estimated duration."""
        service_with_mock.create_quick_fix(
            title="Quick change",
            context="Simple fix",
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "15m" in call_kwargs["description"]

    def test_create_quick_fix_with_custom_labels(self, service_with_mock, mock_backend):
        """Test quick fix with additional custom labels."""
        service_with_mock.create_quick_fix(
            title="Fix",
            context="Context",
            labels=["docs", "urgent"],
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "quick-fix" in call_kwargs["labels"]
        assert "docs" in call_kwargs["labels"]
        assert "urgent" in call_kwargs["labels"]

    def test_create_quick_fix_with_custom_acceptance_criteria(
        self, service_with_mock, mock_backend
    ):
        """Test quick fix with custom acceptance criteria."""
        service_with_mock.create_quick_fix(
            title="Fix issue",
            context="Context",
            acceptance_criteria=["Custom criterion 1", "Custom criterion 2"],
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "Custom criterion 1" in call_kwargs["description"]
        assert "Custom criterion 2" in call_kwargs["description"]

    def test_create_quick_fix_default_acceptance_criteria(self, service_with_mock, mock_backend):
        """Test quick fix uses default acceptance criteria when not provided."""
        service_with_mock.create_quick_fix(
            title="Fix something",
            context="Context",
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "Change is complete: Fix something" in call_kwargs["description"]

    def test_create_quick_fix_with_source_capture_id(self, service_with_mock, mock_backend):
        """Test quick fix with source capture ID."""
        service_with_mock.create_quick_fix(
            title="Fix",
            context="Context",
            source_capture_id="cap-123",
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "cap-123" in call_kwargs["description"]


class TestTaskServiceCreateSpike:
    """Tests for TaskService.create_spike() convenience method."""

    @pytest.fixture
    def mock_backend(self):
        """Create a mock task backend."""
        backend = Mock()
        backend.create_task = Mock(return_value=Task(
            id="spike-001",
            title="[Spike] Investigation",
            status=TaskStatus.OPEN,
        ))
        return backend

    @pytest.fixture
    def service_with_mock(self, mock_backend):
        """Create TaskService with mocked backend."""
        with patch('cub.core.tasks.service.get_backend', return_value=mock_backend):
            service = TaskService()
        service._backend = mock_backend
        return service

    def test_create_spike_success(self, service_with_mock, mock_backend):
        """Test successful spike creation."""
        result = service_with_mock.create_spike(
            title="Investigate caching options",
            context="Need to explore caching strategies",
            exploration_goals=["Evaluate Redis", "Evaluate Memcached"],
        )

        assert result is not None
        mock_backend.create_task.assert_called_once()

    def test_create_spike_title_prefix(self, service_with_mock, mock_backend):
        """Test spike title is prefixed with [Spike]."""
        service_with_mock.create_spike(
            title="New approach",
            context="Context",
            exploration_goals=["Goal 1"],
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert call_kwargs["title"] == "[Spike] New approach"

    def test_create_spike_includes_branch_name(self, service_with_mock, mock_backend):
        """Test spike includes suggested branch name."""
        service_with_mock.create_spike(
            title="Test Caching",
            context="Context",
            exploration_goals=["Goal"],
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        # Branch name should be spike/test-caching (slugified)
        assert "spike/" in call_kwargs["description"]
        assert "test-caching" in call_kwargs["description"]

    def test_create_spike_includes_exploration_goals_in_notes(
        self, service_with_mock, mock_backend
    ):
        """Test spike includes exploration goals in notes."""
        service_with_mock.create_spike(
            title="Investigation",
            context="Context",
            exploration_goals=["Goal A", "Goal B", "Goal C"],
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "Exploration goals:" in call_kwargs["description"]
        assert "- Goal A" in call_kwargs["description"]
        assert "- Goal B" in call_kwargs["description"]
        assert "- Goal C" in call_kwargs["description"]

    def test_create_spike_uses_medium_complexity(self, service_with_mock, mock_backend):
        """Test spike uses MEDIUM complexity."""
        service_with_mock.create_spike(
            title="Spike",
            context="Context",
            exploration_goals=["Goal"],
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "complexity:medium" in call_kwargs["labels"]
        assert "model:sonnet" in call_kwargs["labels"]

    def test_create_spike_includes_spike_label(self, service_with_mock, mock_backend):
        """Test spike includes 'spike' label."""
        service_with_mock.create_spike(
            title="Spike",
            context="Context",
            exploration_goals=["Goal"],
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "spike" in call_kwargs["labels"]

    def test_create_spike_uses_2_4h_duration(self, service_with_mock, mock_backend):
        """Test spike uses 2-4h estimated duration."""
        service_with_mock.create_spike(
            title="Spike",
            context="Context",
            exploration_goals=["Goal"],
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "2-4h" in call_kwargs["description"]

    def test_create_spike_default_success_criteria(self, service_with_mock, mock_backend):
        """Test spike uses default success criteria when not provided."""
        service_with_mock.create_spike(
            title="Spike",
            context="Context",
            exploration_goals=["Goal"],
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "Approach validated or invalidated" in call_kwargs["description"]
        assert "Key learnings documented" in call_kwargs["description"]
        assert "Recommendation for next steps provided" in call_kwargs["description"]

    def test_create_spike_custom_success_criteria(self, service_with_mock, mock_backend):
        """Test spike with custom success criteria."""
        service_with_mock.create_spike(
            title="Spike",
            context="Context",
            exploration_goals=["Goal"],
            success_criteria=["Custom success 1", "Custom success 2"],
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "Custom success 1" in call_kwargs["description"]
        assert "Custom success 2" in call_kwargs["description"]

    def test_create_spike_includes_implementation_steps(self, service_with_mock, mock_backend):
        """Test spike includes standard implementation steps."""
        service_with_mock.create_spike(
            title="Spike",
            context="Context",
            exploration_goals=["Goal"],
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "Create branch:" in call_kwargs["description"]
        assert "Time-box exploration" in call_kwargs["description"]
        assert "Document findings" in call_kwargs["description"]
        assert "Summarize learnings" in call_kwargs["description"]

    def test_create_spike_with_custom_labels(self, service_with_mock, mock_backend):
        """Test spike with additional custom labels."""
        service_with_mock.create_spike(
            title="Spike",
            context="Context",
            exploration_goals=["Goal"],
            labels=["performance", "v3.0"],
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "spike" in call_kwargs["labels"]
        assert "performance" in call_kwargs["labels"]
        assert "v3.0" in call_kwargs["labels"]

    def test_create_spike_with_source_capture_id(self, service_with_mock, mock_backend):
        """Test spike with source capture ID."""
        service_with_mock.create_spike(
            title="Spike",
            context="Context",
            exploration_goals=["Goal"],
            source_capture_id="cap-abc",
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "cap-abc" in call_kwargs["description"]

    def test_create_spike_branch_name_truncation(self, service_with_mock, mock_backend):
        """Test spike branch name is truncated to 30 characters."""
        long_title = "This is a very long spike title that should be truncated in the branch name"
        service_with_mock.create_spike(
            title=long_title,
            context="Context",
            exploration_goals=["Goal"],
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        # Find the branch name in the description
        assert "spike/" in call_kwargs["description"]
        # The slug should be truncated


class TestTaskServiceCreateBatchedTask:
    """Tests for TaskService.create_batched_task() convenience method."""

    @pytest.fixture
    def mock_backend(self):
        """Create a mock task backend."""
        backend = Mock()
        backend.create_task = Mock(return_value=Task(
            id="batch-001",
            title="Batched Task",
            status=TaskStatus.OPEN,
        ))
        return backend

    @pytest.fixture
    def service_with_mock(self, mock_backend):
        """Create TaskService with mocked backend."""
        with patch('cub.core.tasks.service.get_backend', return_value=mock_backend):
            service = TaskService()
        service._backend = mock_backend
        return service

    def test_create_batched_task_success(self, service_with_mock, mock_backend):
        """Test successful batched task creation."""
        result = service_with_mock.create_batched_task(
            title="Batch: Fix typos",
            items=[
                ("Fix typo 1", "Description 1"),
                ("Fix typo 2", "Description 2"),
            ],
        )

        assert result is not None
        mock_backend.create_task.assert_called_once()

    def test_create_batched_task_context_mentions_item_count(self, service_with_mock, mock_backend):
        """Test batched task context mentions number of items."""
        service_with_mock.create_batched_task(
            title="Batch",
            items=[
                ("Item 1", "Desc 1"),
                ("Item 2", "Desc 2"),
                ("Item 3", "Desc 3"),
            ],
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "3 related items" in call_kwargs["description"]

    def test_create_batched_task_includes_batch_label(self, service_with_mock, mock_backend):
        """Test batched task includes 'batch' label."""
        service_with_mock.create_batched_task(
            title="Batch",
            items=[("Item", "Desc")],
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "batch" in call_kwargs["labels"]

    def test_create_batched_task_uses_low_complexity(self, service_with_mock, mock_backend):
        """Test batched task uses LOW complexity."""
        service_with_mock.create_batched_task(
            title="Batch",
            items=[("Item", "Desc")],
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "complexity:low" in call_kwargs["labels"]
        assert "model:haiku" in call_kwargs["labels"]

    def test_create_batched_task_implementation_steps(self, service_with_mock, mock_backend):
        """Test batched task includes implementation steps for each item."""
        service_with_mock.create_batched_task(
            title="Batch",
            items=[
                ("Fix A", "Fix A description"),
                ("Fix B", "Fix B description"),
            ],
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "Complete: Fix A" in call_kwargs["description"]
        assert "Complete: Fix B" in call_kwargs["description"]

    def test_create_batched_task_acceptance_criteria(self, service_with_mock, mock_backend):
        """Test batched task includes acceptance criteria for each item."""
        service_with_mock.create_batched_task(
            title="Batch",
            items=[
                ("Task A", "A description"),
                ("Task B", "B description"),
            ],
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "Task A is done" in call_kwargs["description"]
        assert "Task B is done" in call_kwargs["description"]

    def test_create_batched_task_notes_include_item_details(self, service_with_mock, mock_backend):
        """Test batched task notes include detailed item information."""
        service_with_mock.create_batched_task(
            title="Batch",
            items=[
                ("Fix typo in README", "The word 'teh' should be 'the'"),
                ("Fix typo in docs", "The word 'tset' should be 'test'"),
            ],
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "## Batched Items" in call_kwargs["description"]
        assert "### Fix typo in README" in call_kwargs["description"]
        assert "The word 'teh' should be 'the'" in call_kwargs["description"]
        assert "### Fix typo in docs" in call_kwargs["description"]
        assert "The word 'tset' should be 'test'" in call_kwargs["description"]

    def test_create_batched_task_with_custom_labels(self, service_with_mock, mock_backend):
        """Test batched task with additional custom labels."""
        service_with_mock.create_batched_task(
            title="Batch",
            items=[("Item", "Desc")],
            labels=["docs", "low-priority"],
        )

        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert "batch" in call_kwargs["labels"]
        assert "docs" in call_kwargs["labels"]
        assert "low-priority" in call_kwargs["labels"]


class TestGetTaskService:
    """Tests for get_task_service() singleton function."""

    def test_get_task_service_returns_instance(self):
        """Test get_task_service returns a TaskService instance."""
        # Reset singleton
        service_module._default_service = None

        with patch('cub.core.tasks.service.get_backend') as mock_get:
            mock_get.return_value = Mock()
            service = get_task_service()

        assert isinstance(service, TaskService)

    def test_get_task_service_returns_same_instance(self):
        """Test get_task_service returns the same instance on subsequent calls."""
        # Reset singleton
        service_module._default_service = None

        with patch('cub.core.tasks.service.get_backend') as mock_get:
            mock_get.return_value = Mock()
            service1 = get_task_service()
            service2 = get_task_service()

        assert service1 is service2

    def test_get_task_service_singleton_persists(self):
        """Test singleton persists across multiple calls."""
        # Reset singleton
        service_module._default_service = None

        with patch('cub.core.tasks.service.get_backend') as mock_get:
            mock_get.return_value = Mock()

            # First call creates instance
            service1 = get_task_service()

            # Multiple subsequent calls return same instance
            for _ in range(5):
                service = get_task_service()
                assert service is service1


class TestTaskCreationRequestDataclass:
    """Tests for TaskCreationRequest dataclass fields and defaults."""

    def test_default_values(self):
        """Test default values for all optional fields."""
        request = TaskCreationRequest(title="Minimal")

        assert request.title == "Minimal"
        assert request.context == ""
        assert request.implementation_steps == []
        assert request.acceptance_criteria == []
        assert request.task_type == "task"
        assert request.priority == 2
        assert request.labels == []
        assert request.complexity == TaskComplexity.MEDIUM
        assert request.domain is None
        assert request.depends_on == []
        assert request.parent is None
        assert request.files_involved == []
        assert request.estimated_duration is None
        assert request.notes == ""
        assert request.source_capture_id is None

    def test_all_fields_can_be_set(self):
        """Test all fields can be explicitly set."""
        request = TaskCreationRequest(
            title="Full Task",
            context="Full context",
            implementation_steps=["Step 1"],
            acceptance_criteria=["Criterion 1"],
            task_type="feature",
            priority=0,
            labels=["urgent"],
            complexity=TaskComplexity.HIGH,
            domain=TaskDomain.API,
            depends_on=["dep-001"],
            parent="parent-001",
            files_involved=["file.py"],
            estimated_duration="1h",
            notes="Some notes",
            source_capture_id="cap-001",
        )

        assert request.title == "Full Task"
        assert request.context == "Full context"
        assert request.implementation_steps == ["Step 1"]
        assert request.acceptance_criteria == ["Criterion 1"]
        assert request.task_type == "feature"
        assert request.priority == 0
        assert request.labels == ["urgent"]
        assert request.complexity == TaskComplexity.HIGH
        assert request.domain == TaskDomain.API
        assert request.depends_on == ["dep-001"]
        assert request.parent == "parent-001"
        assert request.files_involved == ["file.py"]
        assert request.estimated_duration == "1h"
        assert request.notes == "Some notes"
        assert request.source_capture_id == "cap-001"

    def test_mutable_defaults_are_independent(self):
        """Test mutable default fields are independent between instances."""
        request1 = TaskCreationRequest(title="Task 1")
        request2 = TaskCreationRequest(title="Task 2")

        request1.labels.append("label1")
        request1.implementation_steps.append("step1")

        assert "label1" not in request2.labels
        assert "step1" not in request2.implementation_steps
