"""Logged connection URLs never carry a password."""

from momentum25.infrastructure.config.settings import redact_url


def test_redact_url_masks_passwords_and_keeps_the_rest() -> None:
    # Regression R3-B: settings_loaded logged the full database URL, password included.
    assert redact_url("postgresql+asyncpg://user:s3cret@db:5432/m25") == (
        "postgresql+asyncpg://user:***@db:5432/m25"
    )
    assert redact_url("redis://:s3cret@cache:6379/0") == "redis://:***@cache:6379/0"
    assert redact_url("redis://cache:6379/0") == "redis://cache:6379/0"
    assert "s3cret" not in redact_url("not a url s3cret")
