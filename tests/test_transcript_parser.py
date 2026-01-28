"""
Tests for transcript parser module.

Tests cover:
- Basic transcript parsing with single and multiple turns
- Token aggregation across turns
- Cost calculation for different models
- Model name normalization
- Error handling for missing/malformed transcripts
- Edge cases (empty files, no usage data, etc.)
"""

import json

import pytest

from cub.core.ledger.transcript_parser import (
    TranscriptData,
    calculate_cost,
    normalize_model_name,
    parse_transcript,
    to_token_usage,
)


class TestNormalizeModelName:
    """Test model name normalization."""

    def test_normalizes_sonnet_models(self):
        """Test that sonnet models normalize correctly."""
        assert normalize_model_name("claude-sonnet-4-5-20250929") == "sonnet"
        assert normalize_model_name("claude-3-5-sonnet-latest") == "sonnet"
        assert normalize_model_name("claude-sonnet-4-20250514") == "sonnet"

    def test_normalizes_opus_models(self):
        """Test that opus models normalize correctly."""
        assert normalize_model_name("claude-opus-4-5") == "opus"
        assert normalize_model_name("claude-opus-4-5-20251101") == "opus"
        assert normalize_model_name("claude-opus-4-20250514") == "opus"

    def test_normalizes_haiku_models(self):
        """Test that haiku models normalize correctly."""
        assert normalize_model_name("claude-3-5-haiku-latest") == "haiku"
        assert normalize_model_name("claude-3-5-haiku-20241022") == "haiku"
        assert normalize_model_name("claude-3-haiku-20240307") == "haiku"

    def test_handles_unknown_models(self):
        """Test that unknown models return 'unknown'."""
        assert normalize_model_name("gpt-4") == "unknown"
        assert normalize_model_name("claude-future-model") == "unknown"
        assert normalize_model_name("") == "unknown"


class TestCalculateCost:
    """Test cost calculation."""

    def test_calculates_sonnet_cost(self):
        """Test cost calculation for Sonnet model."""
        # 10k input, 5k output, no cache
        cost = calculate_cost(10000, 5000, 0, 0, "claude-sonnet-4-5-20250929")
        # (10000 * 3.00 + 5000 * 15.00) / 1M = (30000 + 75000) / 1M = 0.105
        assert abs(cost - 0.105) < 0.0001

    def test_calculates_opus_cost(self):
        """Test cost calculation for Opus model."""
        # 10k input, 5k output, no cache
        cost = calculate_cost(10000, 5000, 0, 0, "claude-opus-4-5")
        # (10000 * 15.00 + 5000 * 75.00) / 1M = (150000 + 375000) / 1M = 0.525
        assert abs(cost - 0.525) < 0.0001

    def test_calculates_haiku_cost(self):
        """Test cost calculation for Haiku model."""
        # 10k input, 5k output, no cache
        cost = calculate_cost(10000, 5000, 0, 0, "claude-3-5-haiku-latest")
        # (10000 * 1.00 + 5000 * 5.00) / 1M = (10000 + 25000) / 1M = 0.035
        assert abs(cost - 0.035) < 0.0001

    def test_includes_cache_read_tokens(self):
        """Test that cache read tokens are included in cost."""
        # 10k input, 5k output, 8k cache read
        cost = calculate_cost(10000, 5000, 8000, 0, "claude-sonnet-4-5-20250929")
        # (10000 * 3.00 + 5000 * 15.00 + 8000 * 0.30) / 1M
        # = (30000 + 75000 + 2400) / 1M = 0.1074
        assert abs(cost - 0.1074) < 0.0001

    def test_includes_cache_creation_tokens(self):
        """Test that cache creation tokens are included in cost."""
        # 10k input, 5k output, 0 cache read, 2k cache creation
        cost = calculate_cost(10000, 5000, 0, 2000, "claude-sonnet-4-5-20250929")
        # (10000 * 3.00 + 5000 * 15.00 + 2000 * 3.75) / 1M
        # = (30000 + 75000 + 7500) / 1M = 0.1125
        assert abs(cost - 0.1125) < 0.0001

    def test_defaults_to_sonnet_pricing_for_unknown_model(self):
        """Test that unknown models use Sonnet pricing."""
        cost = calculate_cost(10000, 5000, 0, 0, "unknown-model")
        # Should use Sonnet pricing
        assert abs(cost - 0.105) < 0.0001


class TestParseTranscript:
    """Test transcript parsing."""

    def test_parses_single_turn_transcript(self, tmp_path):
        """Test parsing a transcript with a single assistant turn."""
        transcript = tmp_path / "session.jsonl"
        transcript.write_text(
            json.dumps({
                "type": "output",
                "model": "claude-sonnet-4-5-20250929",
                "usage": {
                    "input_tokens": 10000,
                    "output_tokens": 5000,
                    "cache_read_input_tokens": 2000,
                    "cache_creation_input_tokens": 500,
                },
                "timestamp": "2026-01-28T10:30:00Z",
            })
            + "\n"
        )

        data = parse_transcript(transcript)

        assert data.total_input_tokens == 10000
        assert data.total_output_tokens == 5000
        assert data.total_cache_read_tokens == 2000
        assert data.total_cache_creation_tokens == 500
        assert data.model == "claude-sonnet-4-5-20250929"
        assert data.normalized_model == "sonnet"
        assert data.num_turns == 1
        # Cost: (10000*3 + 5000*15 + 2000*0.3 + 500*3.75) / 1M
        # = (30000 + 75000 + 600 + 1875) / 1M = 0.107475
        assert abs(data.total_cost_usd - 0.107475) < 0.0001

    def test_aggregates_multiple_turns(self, tmp_path):
        """Test that multiple assistant turns are aggregated."""
        transcript = tmp_path / "session.jsonl"
        lines = [
            # User input (should be ignored)
            json.dumps({"type": "input", "content": "Hello"}),
            # First assistant turn
            json.dumps({
                "type": "output",
                "model": "claude-sonnet-4-5-20250929",
                "usage": {
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                },
            }),
            # User input (should be ignored)
            json.dumps({"type": "input", "content": "Continue"}),
            # Second assistant turn
            json.dumps({
                "type": "output",
                "model": "claude-sonnet-4-5-20250929",
                "usage": {
                    "input_tokens": 2000,
                    "output_tokens": 1000,
                    "cache_read_input_tokens": 1500,
                    "cache_creation_input_tokens": 0,
                },
            }),
        ]
        transcript.write_text("\n".join(lines) + "\n")

        data = parse_transcript(transcript)

        assert data.total_input_tokens == 3000  # 1000 + 2000
        assert data.total_output_tokens == 1500  # 500 + 1000
        assert data.total_cache_read_tokens == 1500  # 0 + 1500
        assert data.total_cache_creation_tokens == 0
        assert data.num_turns == 2
        assert data.model == "claude-sonnet-4-5-20250929"

    def test_ignores_user_inputs(self, tmp_path):
        """Test that user inputs are ignored."""
        transcript = tmp_path / "session.jsonl"
        lines = [
            json.dumps({"type": "input", "content": "User message"}),
            json.dumps({
                "type": "output",
                "model": "claude-sonnet-4-5-20250929",
                "usage": {"input_tokens": 100, "output_tokens": 50},
            }),
        ]
        transcript.write_text("\n".join(lines) + "\n")

        data = parse_transcript(transcript)

        assert data.num_turns == 1  # Only one output turn

    def test_handles_missing_usage_field(self, tmp_path):
        """Test that missing usage field doesn't crash."""
        transcript = tmp_path / "session.jsonl"
        transcript.write_text(
            json.dumps({
                "type": "output",
                "model": "claude-sonnet-4-5-20250929",
                # No usage field
            })
            + "\n"
        )

        data = parse_transcript(transcript)

        assert data.total_input_tokens == 0
        assert data.total_output_tokens == 0
        assert data.num_turns == 1
        assert data.model == "claude-sonnet-4-5-20250929"

    def test_handles_partial_usage_fields(self, tmp_path):
        """Test that partial usage data is handled correctly."""
        transcript = tmp_path / "session.jsonl"
        transcript.write_text(
            json.dumps({
                "type": "output",
                "model": "claude-sonnet-4-5-20250929",
                "usage": {
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    # Cache fields missing
                },
            })
            + "\n"
        )

        data = parse_transcript(transcript)

        assert data.total_input_tokens == 1000
        assert data.total_output_tokens == 500
        assert data.total_cache_read_tokens == 0
        assert data.total_cache_creation_tokens == 0

    def test_handles_empty_transcript(self, tmp_path):
        """Test that empty transcript returns zero data."""
        transcript = tmp_path / "session.jsonl"
        transcript.write_text("")

        data = parse_transcript(transcript)

        assert data.total_input_tokens == 0
        assert data.total_output_tokens == 0
        assert data.num_turns == 0
        assert data.model == ""
        assert data.normalized_model == ""

    def test_handles_malformed_json_lines(self, tmp_path):
        """Test that malformed lines are skipped."""
        transcript = tmp_path / "session.jsonl"
        lines = [
            "not json",
            json.dumps({
                "type": "output",
                "model": "claude-sonnet-4-5-20250929",
                "usage": {"input_tokens": 100, "output_tokens": 50},
            }),
            "{incomplete json",
            json.dumps({
                "type": "output",
                "model": "claude-sonnet-4-5-20250929",
                "usage": {"input_tokens": 200, "output_tokens": 100},
            }),
        ]
        transcript.write_text("\n".join(lines) + "\n")

        data = parse_transcript(transcript)

        # Should have 2 valid turns
        assert data.num_turns == 2
        assert data.total_input_tokens == 300  # 100 + 200
        assert data.total_output_tokens == 150  # 50 + 100

    def test_handles_blank_lines(self, tmp_path):
        """Test that blank lines are skipped."""
        transcript = tmp_path / "session.jsonl"
        lines = [
            "",
            json.dumps({
                "type": "output",
                "model": "claude-sonnet-4-5-20250929",
                "usage": {"input_tokens": 100, "output_tokens": 50},
            }),
            "   ",
            "",
        ]
        transcript.write_text("\n".join(lines) + "\n")

        data = parse_transcript(transcript)

        assert data.num_turns == 1

    def test_raises_on_missing_file(self, tmp_path):
        """Test that missing file raises FileNotFoundError."""
        transcript = tmp_path / "nonexistent.jsonl"

        with pytest.raises(FileNotFoundError, match="Transcript file not found"):
            parse_transcript(transcript)

    def test_extracts_model_from_first_turn(self, tmp_path):
        """Test that model is extracted from first output turn."""
        transcript = tmp_path / "session.jsonl"
        lines = [
            json.dumps({
                "type": "output",
                "model": "claude-opus-4-5",
                "usage": {"input_tokens": 100, "output_tokens": 50},
            }),
            json.dumps({
                "type": "output",
                # Model field can be omitted in subsequent turns
                "usage": {"input_tokens": 200, "output_tokens": 100},
            }),
        ]
        transcript.write_text("\n".join(lines) + "\n")

        data = parse_transcript(transcript)

        assert data.model == "claude-opus-4-5"
        assert data.normalized_model == "opus"


class TestToTokenUsage:
    """Test conversion to TokenUsage model."""

    def test_converts_transcript_data_to_token_usage(self):
        """Test that TranscriptData converts to TokenUsage correctly."""
        data = TranscriptData(
            total_input_tokens=10000,
            total_output_tokens=5000,
            total_cache_read_tokens=2000,
            total_cache_creation_tokens=500,
        )

        usage = to_token_usage(data)

        assert usage.input_tokens == 10000
        assert usage.output_tokens == 5000
        assert usage.cache_read_tokens == 2000
        assert usage.cache_creation_tokens == 500
        assert usage.total_tokens == 17500

    def test_converts_empty_data(self):
        """Test that empty data converts to zero TokenUsage."""
        data = TranscriptData()

        usage = to_token_usage(data)

        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cache_read_tokens == 0
        assert usage.cache_creation_tokens == 0
        assert usage.total_tokens == 0


class TestTranscriptData:
    """Test TranscriptData dataclass."""

    def test_has_sensible_defaults(self):
        """Test that TranscriptData has sensible default values."""
        data = TranscriptData()

        assert data.total_input_tokens == 0
        assert data.total_output_tokens == 0
        assert data.total_cache_read_tokens == 0
        assert data.total_cache_creation_tokens == 0
        assert data.model == ""
        assert data.normalized_model == ""
        assert data.total_cost_usd == 0.0
        assert data.num_turns == 0
