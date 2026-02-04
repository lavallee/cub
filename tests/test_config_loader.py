"""
Unit tests for configuration loader.

Tests multi-layer config merging, environment variable overrides,
caching, and XDG directory handling.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from cub.core.config import (
    clear_cache,
    get_legacy_config_path,
    get_project_config_path,
    get_user_config_path,
    has_legacy_config,
    load_config,
)
from cub.core.config.loader import (
    apply_env_overrides,
    deep_merge,
    get_default_config,
    get_xdg_config_home,
    load_json_file,
)
from cub.core.config.models import CubConfig

# ==============================================================================
# Helper Functions Tests
# ==============================================================================


class TestDeepMerge:
    """Test the deep_merge helper function."""

    def test_simple_merge(self):
        """Test merging two simple dicts."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        """Test merging nested dicts."""
        base = {"a": 1, "b": {"x": 10, "y": 20}}
        override = {"b": {"y": 30, "z": 40}, "c": 3}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": {"x": 10, "y": 30, "z": 40}, "c": 3}

    def test_override_replaces_non_dict(self):
        """Test that non-dict values are replaced, not merged."""
        base = {"a": [1, 2, 3]}
        override = {"a": [4, 5]}
        result = deep_merge(base, override)
        assert result == {"a": [4, 5]}

    def test_empty_dicts(self):
        """Test merging with empty dicts."""
        assert deep_merge({}, {"a": 1}) == {"a": 1}
        assert deep_merge({"a": 1}, {}) == {"a": 1}
        assert deep_merge({}, {}) == {}

    def test_deeply_nested_merge(self):
        """Test merging deeply nested structures."""
        base = {"level1": {"level2": {"level3": {"a": 1, "b": 2}}}}
        override = {"level1": {"level2": {"level3": {"b": 99, "c": 3}}}}
        result = deep_merge(base, override)
        assert result["level1"]["level2"]["level3"] == {"a": 1, "b": 99, "c": 3}


class TestLoadJsonFile:
    """Test JSON file loading."""

    def test_load_existing_file(self, tmp_path):
        """Test loading a valid JSON file."""
        config_file = tmp_path / "config.json"
        config_data = {"key": "value", "number": 42}
        config_file.write_text(json.dumps(config_data))

        result = load_json_file(config_file)
        assert result == config_data

    def test_load_nonexistent_file(self, tmp_path):
        """Test loading a file that doesn't exist returns None."""
        result = load_json_file(tmp_path / "nonexistent.json")
        assert result is None

    def test_load_invalid_json(self, tmp_path, capsys):
        """Test loading invalid JSON returns None and prints warning."""
        config_file = tmp_path / "invalid.json"
        config_file.write_text("{ invalid json }")

        result = load_json_file(config_file)
        assert result is None

        # Check warning was printed
        captured = capsys.readouterr()
        assert "Warning" in captured.out
        assert "Failed to parse" in captured.out


class TestApplyEnvOverrides:
    """Test environment variable override logic."""

    def test_cub_dev_mode_true(self, monkeypatch):
        """Test CUB_DEV_MODE=true sets dev_mode."""
        monkeypatch.setenv("CUB_DEV_MODE", "true")
        config = {}

        result = apply_env_overrides(config)
        assert result["dev_mode"] is True

    def test_cub_dev_mode_false(self, monkeypatch):
        """Test CUB_DEV_MODE=false/0 sets dev_mode to false."""
        for value in ["false", "0"]:
            monkeypatch.setenv("CUB_DEV_MODE", value)
            config = {}

            result = apply_env_overrides(config)
            assert result["dev_mode"] is False

    def test_cub_budget_override(self, monkeypatch):
        """Test CUB_BUDGET env var overrides budget.default."""
        monkeypatch.setenv("CUB_BUDGET", "100")
        config = {"review": {"plan_strict": False}}

        result = apply_env_overrides(config)
        assert result["budget"]["default"] == 100

    def test_cub_budget_invalid(self, monkeypatch, capsys):
        """Test invalid CUB_BUDGET is ignored with warning."""
        monkeypatch.setenv("CUB_BUDGET", "not-a-number")
        config = {}

        result = apply_env_overrides(config)
        assert "budget" not in result

        # Check warning
        captured = capsys.readouterr()
        assert "Warning" in captured.out
        assert "CUB_BUDGET" in captured.out

    def test_cub_review_strict_true(self, monkeypatch):
        """Test CUB_REVIEW_STRICT=true sets review.plan_strict."""
        monkeypatch.setenv("CUB_REVIEW_STRICT", "true")
        config = {}

        result = apply_env_overrides(config)
        assert result["review"]["plan_strict"] is True

    def test_cub_review_strict_false(self, monkeypatch):
        """Test CUB_REVIEW_STRICT=false/0 sets review.plan_strict to false."""
        for value in ["false", "0"]:
            monkeypatch.setenv("CUB_REVIEW_STRICT", value)
            config = {}

            result = apply_env_overrides(config)
            assert result["review"]["plan_strict"] is False

    def test_cub_review_strict_truthy(self, monkeypatch):
        """Test CUB_REVIEW_STRICT with truthy values."""
        for value in ["1", "yes", "True", "anything"]:
            monkeypatch.setenv("CUB_REVIEW_STRICT", value)
            config = {}

            result = apply_env_overrides(config)
            assert result["review"]["plan_strict"] is True

    def test_multiple_env_overrides(self, monkeypatch):
        """Test applying multiple env var overrides together."""
        monkeypatch.setenv("CUB_BUDGET", "500")
        monkeypatch.setenv("CUB_REVIEW_STRICT", "true")
        config = {"guardrails": {"max_task_iterations": 3}}

        result = apply_env_overrides(config)
        assert result["budget"]["default"] == 500
        assert result["review"]["plan_strict"] is True
        assert result["guardrails"]["max_task_iterations"] == 3

    def test_no_env_overrides(self):
        """Test that config is unchanged when no env vars are set."""
        config = {"review": {"plan_strict": False}}
        result = apply_env_overrides(config)
        assert result == config

    def test_circuit_breaker_enabled_true(self, monkeypatch):
        """Test CUB_CIRCUIT_BREAKER_ENABLED=true sets circuit_breaker.enabled."""
        monkeypatch.setenv("CUB_CIRCUIT_BREAKER_ENABLED", "true")
        config = {}

        result = apply_env_overrides(config)
        assert result["circuit_breaker"]["enabled"] is True

    def test_circuit_breaker_enabled_false(self, monkeypatch):
        """Test CUB_CIRCUIT_BREAKER_ENABLED=false sets circuit_breaker.enabled to false."""
        for value in ["false", "0"]:
            monkeypatch.setenv("CUB_CIRCUIT_BREAKER_ENABLED", value)
            config = {}

            result = apply_env_overrides(config)
            assert result["circuit_breaker"]["enabled"] is False

    def test_circuit_breaker_timeout_valid(self, monkeypatch):
        """Test CUB_CIRCUIT_BREAKER_TIMEOUT sets timeout_minutes."""
        monkeypatch.setenv("CUB_CIRCUIT_BREAKER_TIMEOUT", "60")
        config = {}

        result = apply_env_overrides(config)
        assert result["circuit_breaker"]["timeout_minutes"] == 60

    def test_circuit_breaker_timeout_invalid_zero(self, monkeypatch, capsys):
        """Test CUB_CIRCUIT_BREAKER_TIMEOUT=0 is rejected with warning."""
        monkeypatch.setenv("CUB_CIRCUIT_BREAKER_TIMEOUT", "0")
        config = {}

        result = apply_env_overrides(config)
        assert "circuit_breaker" not in result

        # Check warning
        captured = capsys.readouterr()
        assert "Warning" in captured.out
        assert "CUB_CIRCUIT_BREAKER_TIMEOUT" in captured.out

    def test_circuit_breaker_timeout_invalid_negative(self, monkeypatch, capsys):
        """Test CUB_CIRCUIT_BREAKER_TIMEOUT with negative value is rejected."""
        monkeypatch.setenv("CUB_CIRCUIT_BREAKER_TIMEOUT", "-5")
        config = {}

        result = apply_env_overrides(config)
        assert "circuit_breaker" not in result

        # Check warning
        captured = capsys.readouterr()
        assert "Warning" in captured.out

    def test_circuit_breaker_timeout_invalid_non_integer(self, monkeypatch, capsys):
        """Test CUB_CIRCUIT_BREAKER_TIMEOUT with non-integer is ignored."""
        monkeypatch.setenv("CUB_CIRCUIT_BREAKER_TIMEOUT", "not-a-number")
        config = {}

        result = apply_env_overrides(config)
        assert "circuit_breaker" not in result

        # Check warning
        captured = capsys.readouterr()
        assert "Warning" in captured.out
        assert "CUB_CIRCUIT_BREAKER_TIMEOUT" in captured.out

    def test_circuit_breaker_combined_overrides(self, monkeypatch):
        """Test both circuit breaker env vars together."""
        monkeypatch.setenv("CUB_CIRCUIT_BREAKER_ENABLED", "true")
        monkeypatch.setenv("CUB_CIRCUIT_BREAKER_TIMEOUT", "45")
        config = {}

        result = apply_env_overrides(config)
        assert result["circuit_breaker"]["enabled"] is True
        assert result["circuit_breaker"]["timeout_minutes"] == 45


class TestGetDefaultConfig:
    """Test default configuration generation."""

    def test_default_config_structure(self):
        """Test that default config has expected structure."""
        config = get_default_config()

        assert "guardrails" in config
        assert "review" in config

    def test_default_guardrails(self):
        """Test default guardrails values."""
        config = get_default_config()
        guardrails = config["guardrails"]

        assert guardrails["max_task_iterations"] == 3
        assert guardrails["max_run_iterations"] == 50
        assert guardrails["iteration_warning_threshold"] == 0.8
        assert "api" in " ".join(guardrails["secret_patterns"])

    def test_default_review(self):
        """Test default review values."""
        config = get_default_config()
        review = config["review"]

        assert review["plan_strict"] is False
        assert review["block_on_concerns"] is False


class TestXdgDirectories:
    """Test XDG directory helpers."""

    def test_get_xdg_config_home_default(self, monkeypatch):
        """Test XDG_CONFIG_HOME defaults to ~/.config."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        result = get_xdg_config_home()
        assert result == Path.home() / ".config"

    def test_get_xdg_config_home_custom(self, monkeypatch, tmp_path):
        """Test XDG_CONFIG_HOME respects env var."""
        custom_path = tmp_path / "custom-config"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(custom_path))
        result = get_xdg_config_home()
        assert result == custom_path

    def test_get_user_config_path(self, monkeypatch, tmp_path):
        """Test user config path construction."""
        custom_path = tmp_path / "config"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(custom_path))
        result = get_user_config_path()
        assert result == custom_path / "cub" / "config.json"

    def test_get_project_config_path_default(self):
        """Test project config path defaults to cwd/.cub/config.json."""
        result = get_project_config_path()
        assert result == Path.cwd() / ".cub" / "config.json"

    def test_get_project_config_path_custom(self, tmp_path):
        """Test project config path with custom directory."""
        result = get_project_config_path(tmp_path)
        assert result == tmp_path / ".cub" / "config.json"


# ==============================================================================
# Integration Tests
# ==============================================================================


class TestLoadConfig:
    """Test the main load_config function."""

    def test_load_config_defaults_only(self, tmp_path, monkeypatch):
        """Test loading config with only defaults (no config files)."""
        # Set custom XDG path to avoid loading user config
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        # Use non-existent project dir
        monkeypatch.chdir(tmp_path)

        clear_cache()
        config = load_config(project_dir=tmp_path)

        assert isinstance(config, CubConfig)
        assert config.guardrails.max_task_iterations == 3
        assert config.review.plan_strict is False

    def test_load_config_user_overrides_defaults(self, tmp_path, monkeypatch):
        """Test that user config overrides defaults."""
        # Setup user config
        user_config_dir = tmp_path / "config" / "cub"
        user_config_dir.mkdir(parents=True)
        user_config_file = user_config_dir / "config.json"
        user_config_file.write_text(json.dumps({"guardrails": {"max_task_iterations": 10}}))

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        clear_cache()
        config = load_config(project_dir=project_dir)

        # User config overrides default
        assert config.guardrails.max_task_iterations == 10
        # Default still applies for other values
        assert config.guardrails.max_run_iterations == 50

    def test_load_config_project_overrides_user(self, tmp_path, monkeypatch):
        """Test that project config overrides user config."""
        # Setup user config
        user_config_dir = tmp_path / "config" / "cub"
        user_config_dir.mkdir(parents=True)
        user_config_file = user_config_dir / "config.json"
        user_config_file.write_text(json.dumps({"guardrails": {"max_task_iterations": 10}}))

        # Setup project config
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        project_config_file = project_dir / ".cub.json"
        project_config_file.write_text(json.dumps({"guardrails": {"max_task_iterations": 20}}))

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        clear_cache()
        config = load_config(project_dir=project_dir)

        # Project config wins
        assert config.guardrails.max_task_iterations == 20

    def test_load_config_env_overrides_all(self, tmp_path, monkeypatch):
        """Test that env vars override all config files."""
        # Setup project config
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        project_config_file = project_dir / ".cub.json"
        project_config_file.write_text(json.dumps({"budget": {"default": 100}}))

        # Set env var
        monkeypatch.setenv("CUB_BUDGET", "999")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        clear_cache()
        config = load_config(project_dir=project_dir)

        # Env var wins over project config
        assert config.budget.default == 999

    def test_load_config_deep_merge(self, tmp_path, monkeypatch):
        """Test that nested config values are deep merged, not replaced."""
        # User config sets some guardrails
        user_config_dir = tmp_path / "config" / "cub"
        user_config_dir.mkdir(parents=True)
        user_config_file = user_config_dir / "config.json"
        user_config_file.write_text(json.dumps({"guardrails": {"max_task_iterations": 10}}))

        # Project config sets different guardrails
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        project_config_file = project_dir / ".cub.json"
        project_config_file.write_text(json.dumps({"guardrails": {"max_run_iterations": 100}}))

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        clear_cache()
        config = load_config(project_dir=project_dir)

        # Both values should be present (deep merge)
        assert config.guardrails.max_task_iterations == 10  # from user
        assert config.guardrails.max_run_iterations == 100  # from project
        # Default still applies
        assert config.guardrails.iteration_warning_threshold == 0.8

    def test_load_config_caching(self, tmp_path, monkeypatch):
        """Test that config is cached and reused."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        clear_cache()

        # First load
        config1 = load_config(project_dir=project_dir)
        # Second load should return cached instance
        config2 = load_config(project_dir=project_dir)

        assert config1 is config2  # Same object reference

    def test_load_config_clear_cache(self, tmp_path, monkeypatch):
        """Test that clear_cache forces reload."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        clear_cache()

        config1 = load_config(project_dir=project_dir)
        clear_cache()
        config2 = load_config(project_dir=project_dir)

        # Different instances after cache clear
        assert config1 is not config2
        # But same values
        assert config1.guardrails.max_task_iterations == config2.guardrails.max_task_iterations

    def test_load_config_no_cache(self, tmp_path, monkeypatch):
        """Test loading without cache."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        clear_cache()

        config1 = load_config(project_dir=project_dir, use_cache=False)
        config2 = load_config(project_dir=project_dir, use_cache=False)

        # Different instances when cache disabled
        assert config1 is not config2

    def test_load_config_invalid_json_ignored(self, tmp_path, monkeypatch, capsys):
        """Test that invalid config files are ignored with warning."""
        # Create invalid project config
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        project_config_file = project_dir / ".cub.json"
        project_config_file.write_text("{ invalid json }")

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        clear_cache()
        config = load_config(project_dir=project_dir)

        # Should still load with defaults
        assert config.guardrails.max_task_iterations == 3

        # Warning should be printed
        captured = capsys.readouterr()
        assert "Warning" in captured.out

    def test_load_config_validation_error(self, tmp_path, monkeypatch):
        """Test that invalid config values raise ValidationError."""
        # Create config with invalid value
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        project_config_file = project_dir / ".cub.json"
        project_config_file.write_text(
            json.dumps(
                {
                    "guardrails": {
                        "max_task_iterations": 0  # Invalid: must be >= 1
                    }
                }
            )
        )

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        clear_cache()
        with pytest.raises(ValidationError):
            load_config(project_dir=project_dir)

    def test_load_config_full_precedence(self, tmp_path, monkeypatch):
        """Test complete precedence chain: defaults < user < project < env."""
        # User config
        user_config_dir = tmp_path / "config" / "cub"
        user_config_dir.mkdir(parents=True)
        user_config_file = user_config_dir / "config.json"
        user_config_file.write_text(
            json.dumps(
                {
                    "guardrails": {
                        "max_task_iterations": 5,  # Override default (3)
                        "max_run_iterations": 75,  # Override default (50)
                    },
                    "review": {
                        "plan_strict": True  # Override default (False)
                    },
                }
            )
        )

        # Project config
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        project_config_file = project_dir / ".cub.json"
        project_config_file.write_text(
            json.dumps(
                {
                    "guardrails": {
                        "max_run_iterations": 100  # Override user (75)
                    },
                    "budget": {"default": 200},
                }
            )
        )

        # Env vars
        monkeypatch.setenv("CUB_BUDGET", "500")  # Override project (200)
        monkeypatch.setenv("CUB_REVIEW_STRICT", "false")  # Override user (True)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        clear_cache()
        config = load_config(project_dir=project_dir)

        # Check precedence:
        # - max_task_iterations: user config (5) wins over default (3)
        assert config.guardrails.max_task_iterations == 5
        # - max_run_iterations: project config (100) wins over user (75)
        assert config.guardrails.max_run_iterations == 100
        # - budget.default: env var (500) wins over project (200)
        assert config.budget.default == 500
        # - review.plan_strict: env var (False) wins over user (True)
        assert config.review.plan_strict is False
        # - iteration_warning_threshold: default (0.8) remains
        assert config.guardrails.iteration_warning_threshold == 0.8

    def test_load_config_circuit_breaker_defaults(self, tmp_path, monkeypatch):
        """Test circuit breaker config loads with defaults."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        clear_cache()
        config = load_config(project_dir=project_dir)

        # Should have circuit breaker with defaults
        assert config.circuit_breaker.enabled is True
        assert config.circuit_breaker.timeout_minutes == 30

    def test_load_config_circuit_breaker_project_override(self, tmp_path, monkeypatch):
        """Test circuit breaker config can be overridden in project config."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        project_config_file = project_dir / ".cub.json"
        project_config_file.write_text(
            json.dumps(
                {
                    "circuit_breaker": {
                        "enabled": False,
                        "timeout_minutes": 60,
                    }
                }
            )
        )

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        clear_cache()
        config = load_config(project_dir=project_dir)

        assert config.circuit_breaker.enabled is False
        assert config.circuit_breaker.timeout_minutes == 60

    def test_load_config_circuit_breaker_env_override(self, tmp_path, monkeypatch):
        """Test circuit breaker env vars override config files."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        project_config_file = project_dir / ".cub.json"
        project_config_file.write_text(
            json.dumps({"circuit_breaker": {"timeout_minutes": 60}})
        )

        monkeypatch.setenv("CUB_CIRCUIT_BREAKER_ENABLED", "false")
        monkeypatch.setenv("CUB_CIRCUIT_BREAKER_TIMEOUT", "90")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        clear_cache()
        config = load_config(project_dir=project_dir)

        # Env vars override project config
        assert config.circuit_breaker.enabled is False
        assert config.circuit_breaker.timeout_minutes == 90

    def test_load_config_map_defaults(self, tmp_path, monkeypatch):
        """Test map config loads with defaults."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        clear_cache()
        config = load_config(project_dir=project_dir)

        # Should have map config with defaults
        assert config.map.token_budget == 1500
        assert config.map.max_depth == 4
        assert config.map.include_code_intel is True
        assert config.map.include_ledger_stats is True
        assert "node_modules/**" in config.map.exclude_patterns
        assert ".git/**" in config.map.exclude_patterns

    def test_load_config_map_project_override(self, tmp_path, monkeypatch):
        """Test map config can be overridden in project config."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        project_config_file = project_dir / ".cub.json"
        project_config_file.write_text(
            json.dumps(
                {
                    "map": {
                        "token_budget": 3000,
                        "max_depth": 6,
                        "include_code_intel": False,
                        "include_ledger_stats": False,
                        "exclude_patterns": ["custom/**"],
                    }
                }
            )
        )

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        clear_cache()
        config = load_config(project_dir=project_dir)

        assert config.map.token_budget == 3000
        assert config.map.max_depth == 6
        assert config.map.include_code_intel is False
        assert config.map.include_ledger_stats is False
        assert config.map.exclude_patterns == ["custom/**"]

    def test_load_config_map_validation(self, tmp_path, monkeypatch):
        """Test map config validation for invalid values."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        project_config_file = project_dir / ".cub.json"
        project_config_file.write_text(
            json.dumps(
                {
                    "map": {
                        "token_budget": 0,  # Invalid: must be >= 1
                    }
                }
            )
        )

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        clear_cache()
        with pytest.raises(ValidationError):
            load_config(project_dir=project_dir)

    def test_load_config_map_deep_merge(self, tmp_path, monkeypatch):
        """Test map config deep merges with user config."""
        # User config sets some map settings
        user_config_dir = tmp_path / "config" / "cub"
        user_config_dir.mkdir(parents=True)
        user_config_file = user_config_dir / "config.json"
        user_config_file.write_text(
            json.dumps(
                {
                    "map": {
                        "token_budget": 2000,
                        "max_depth": 5,
                    }
                }
            )
        )

        # Project config sets different map settings
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        project_config_file = project_dir / ".cub.json"
        project_config_file.write_text(
            json.dumps(
                {
                    "map": {
                        "include_code_intel": False,
                    }
                }
            )
        )

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        clear_cache()
        config = load_config(project_dir=project_dir)

        # User config should be merged with project config
        assert config.map.token_budget == 2000  # from user
        assert config.map.max_depth == 5  # from user
        assert config.map.include_code_intel is False  # from project
        assert config.map.include_ledger_stats is True  # default


# ==============================================================================
# Backwards Compatibility Tests
# ==============================================================================


class TestConfigConsolidation:
    """Test consolidated config in .cub/config.json with legacy .cub.json fallback."""

    def test_get_project_config_path_returns_new_location(self, tmp_path):
        """Test that get_project_config_path returns .cub/config.json."""
        result = get_project_config_path(tmp_path)
        assert result == tmp_path / ".cub" / "config.json"

    def test_get_legacy_config_path_returns_old_location(self, tmp_path):
        """Test that get_legacy_config_path returns .cub.json."""
        result = get_legacy_config_path(tmp_path)
        assert result == tmp_path / ".cub.json"

    def test_has_legacy_config_true_when_exists(self, tmp_path):
        """Test has_legacy_config returns True when .cub.json exists."""
        legacy_file = tmp_path / ".cub.json"
        legacy_file.write_text('{"harness": "claude"}')
        assert has_legacy_config(tmp_path) is True

    def test_has_legacy_config_false_when_missing(self, tmp_path):
        """Test has_legacy_config returns False when .cub.json doesn't exist."""
        assert has_legacy_config(tmp_path) is False

    def test_load_config_prefers_new_location(self, tmp_path, monkeypatch):
        """Test that .cub/config.json is preferred over .cub.json."""
        # Setup both config files with different values
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        new_config = cub_dir / "config.json"
        new_config.write_text(json.dumps({"guardrails": {"max_task_iterations": 99}}))

        legacy_config = tmp_path / ".cub.json"
        legacy_config.write_text(json.dumps({"guardrails": {"max_task_iterations": 11}}))

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        clear_cache()
        config = load_config(project_dir=tmp_path)

        # New location should be used
        assert config.guardrails.max_task_iterations == 99

    def test_load_config_falls_back_to_legacy(self, tmp_path, monkeypatch, capsys):
        """Test that .cub.json is used when .cub/config.json doesn't exist."""
        # Only setup legacy config
        legacy_config = tmp_path / ".cub.json"
        legacy_config.write_text(json.dumps({"guardrails": {"max_task_iterations": 77}}))

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        clear_cache()
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            config = load_config(project_dir=tmp_path)

            # Legacy config should be used
            assert config.guardrails.max_task_iterations == 77

            # Deprecation warning should be issued
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 1
            assert "deprecated" in str(deprecation_warnings[0].message).lower()

    def test_load_config_deprecation_warning_only_once(self, tmp_path, monkeypatch, capsys):
        """Test that deprecation warning is only shown once per session."""
        # Only setup legacy config
        legacy_config = tmp_path / ".cub.json"
        legacy_config.write_text(json.dumps({"harness": "claude"}))

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        clear_cache()
        import warnings

        # First load should show warning
        with warnings.catch_warnings(record=True) as w1:
            warnings.simplefilter("always")
            load_config(project_dir=tmp_path, use_cache=False)
            first_count = len([x for x in w1 if issubclass(x.category, DeprecationWarning)])

        # Second load without cache clear should not show warning
        with warnings.catch_warnings(record=True) as w2:
            warnings.simplefilter("always")
            load_config(project_dir=tmp_path, use_cache=False)
            second_count = len([x for x in w2 if issubclass(x.category, DeprecationWarning)])

        assert first_count == 1
        assert second_count == 0

    def test_load_config_legacy_with_internal_state(self, tmp_path, monkeypatch):
        """Test loading legacy config that includes internal state fields."""
        # Legacy config with all field types
        legacy_config = tmp_path / ".cub.json"
        legacy_config.write_text(
            json.dumps(
                {
                    "harness": "codex",
                    "budget": {"max_tokens_per_task": 100000},
                    "project_id": "test",
                    "dev_mode": True,
                }
            )
        )

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        clear_cache()
        import warnings

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            config = load_config(project_dir=tmp_path)

            # All fields should be loaded
            assert config.harness.name == "codex"
            assert config.budget.max_tokens_per_task == 100000
            assert config.project_id == "test"
            assert config.dev_mode is True

    def test_load_config_no_warning_for_new_location(self, tmp_path, monkeypatch, capsys):
        """Test that no deprecation warning when using new location."""
        # Setup only new config location
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        new_config = cub_dir / "config.json"
        new_config.write_text(json.dumps({"guardrails": {"max_task_iterations": 50}}))

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        clear_cache()
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            config = load_config(project_dir=tmp_path)

            # Config should load correctly
            assert config.guardrails.max_task_iterations == 50

            # No deprecation warning
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 0

    def test_clear_cache_resets_warning_flag(self, tmp_path, monkeypatch):
        """Test that clear_cache resets the legacy warning flag."""
        # Setup legacy config
        legacy_config = tmp_path / ".cub.json"
        legacy_config.write_text(json.dumps({"harness": "claude"}))

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        clear_cache()
        import warnings

        # First load shows warning
        with warnings.catch_warnings(record=True) as w1:
            warnings.simplefilter("always")
            load_config(project_dir=tmp_path, use_cache=False)
            first_count = len([x for x in w1 if issubclass(x.category, DeprecationWarning)])

        # Clear cache and load again
        clear_cache()

        with warnings.catch_warnings(record=True) as w2:
            warnings.simplefilter("always")
            load_config(project_dir=tmp_path, use_cache=False)
            after_clear_count = len([x for x in w2 if issubclass(x.category, DeprecationWarning)])

        # Warning should appear again after cache clear
        assert first_count == 1
        assert after_clear_count == 1
