from __future__ import annotations

from pydantic import ValidationError
import pytest

from app.config import DEFAULT_ALLOWED_ORIGINS, Settings


def test_gemini_model_missing_fails_with_clear_error() -> None:
    """When GEMINI_MODEL is missing, it raises ValidationError with the required guidance."""
    with pytest.raises(
        ValidationError,
        match=r"Set GEMINI_MODEL in \.env \(see Google AI Studio for current model names\)",
    ):
        Settings(_env_file=None)


def test_gemini_model_empty_fails_with_clear_error() -> None:
    """When GEMINI_MODEL is empty string or whitespace, it raises ValidationError with guidance."""
    with pytest.raises(
        ValidationError,
        match=r"Set GEMINI_MODEL in \.env \(see Google AI Studio for current model names\)",
    ):
        Settings(_env_file=None, gemini_model="   ")


def test_gemini_model_valid() -> None:
    """Valid GEMINI_MODEL is accepted and trimmed."""
    settings = Settings(_env_file=None, gemini_model="  gemini-3.8-flash  ")
    assert settings.gemini_model == "gemini-3.8-flash"


def test_allowed_origins_default() -> None:
    """When no origins are specified, the default origin list is used."""
    settings = Settings(_env_file=None, gemini_model="test-model")
    assert settings.allowed_origins == DEFAULT_ALLOWED_ORIGINS


@pytest.mark.parametrize(
    "raw_input",
    [
        "",
        "   ",
        ",",
        "  ,  ,  ",
    ],
)
def test_allowed_origins_empty_inputs(raw_input: str) -> None:
    """Empty, whitespace-only, or empty-comma inputs fall back to default origins."""
    settings = Settings(
        _env_file=None, gemini_model="test-model", allowed_origins=raw_input
    )
    assert settings.allowed_origins == DEFAULT_ALLOWED_ORIGINS


def test_allowed_origins_single_value() -> None:
    """Single origin value is accepted and whitespace is trimmed."""
    settings = Settings(
        _env_file=None,
        gemini_model="test-model",
        allowed_origins="  https://study.example.com  ",
    )
    assert settings.allowed_origins == ["https://study.example.com"]


def test_allowed_origins_multi_value() -> None:
    """Comma-separated origins are split, trimmed, and empty tokens discarded."""
    settings = Settings(
        _env_file=None,
        gemini_model="test-model",
        allowed_origins="http://localhost:5173, http://127.0.0.1:5173, https://app.example.com",
    )
    assert settings.allowed_origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://app.example.com",
    ]


def test_allowed_origins_from_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """pydantic-settings loads comma-separated env values without JSON parsing errors."""
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000, https://client.test")
    settings = Settings(_env_file=None, gemini_model="test-model")
    assert settings.allowed_origins == [
        "http://localhost:3000",
        "https://client.test",
    ]

    # Test empty env value falling back to default
    monkeypatch.setenv("ALLOWED_ORIGINS", "")
    settings_empty = Settings(_env_file=None, gemini_model="test-model")
    assert settings_empty.allowed_origins == DEFAULT_ALLOWED_ORIGINS


def test_llm_retry_and_fallback_defaults() -> None:
    """Config has expected default values for fallback model and retry behavior."""
    settings = Settings(_env_file=None, gemini_model="test-model")
    assert settings.gemini_fallback_model == ""
    assert settings.llm_max_attempts == 4
    assert settings.llm_retry_base_seconds == 2.0


def test_llm_retry_and_fallback_custom() -> None:
    """Custom fallback model and retry parameters are correctly loaded."""
    settings = Settings(
        _env_file=None,
        gemini_model="test-model",
        gemini_fallback_model="backup-model",
        llm_max_attempts=2,
        llm_retry_base_seconds=0.0,
    )
    assert settings.gemini_fallback_model == "backup-model"
    assert settings.llm_max_attempts == 2
    assert settings.llm_retry_base_seconds == 0.0


def test_chunking_config_defaults_and_custom() -> None:
    """Config has expected default values and accepts overrides for chunking parameters."""
    defaults = Settings(_env_file=None, gemini_model="test-model")
    assert defaults.chunk_max_chars == 30000
    assert defaults.max_chunks == 12
    assert defaults.chunk_delay_seconds == 0.0

    custom = Settings(
        _env_file=None,
        gemini_model="test-model",
        chunk_max_chars=15000,
        max_chunks=6,
        chunk_delay_seconds=1.5,
    )
    assert custom.chunk_max_chars == 15000
    assert custom.max_chunks == 6
    assert custom.chunk_delay_seconds == 1.5
