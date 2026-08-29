from __future__ import annotations


class LearnLabError(Exception):
    """Base exception for user-safe LearnLab errors."""


class ConfigurationError(LearnLabError):
    """Raised when configuration is absent, malformed, or unusable."""


def redact(text: str, secrets: set[str]) -> str:
    """Replace literal, nonempty secrets with a safe placeholder."""
    for secret in sorted((value for value in secrets if value), key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    return text
