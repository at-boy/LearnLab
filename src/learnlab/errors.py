from __future__ import annotations


class LearnLabError(Exception):
    """Base exception for user-safe LearnLab errors."""


class ConfigurationError(LearnLabError):
    """Raised when configuration is absent, malformed, or unusable."""


class ProviderError(LearnLabError):
    """Base exception for failures while using an infrastructure provider."""


class ProviderAuthenticationError(ProviderError):
    """Raised when a provider rejects the configured credentials."""


class ProviderAuthorizationError(ProviderError):
    """Raised when authenticated credentials lack required permissions."""


class ProviderOperationError(ProviderError):
    """Raised when a provider operation cannot be completed."""


class ProviderTaskFailed(ProviderError):
    """Raised when an asynchronous provider task has a non-OK result."""


class ProviderTimeoutError(ProviderError):
    """Raised when a provider operation does not complete before its deadline."""


def redact(text: str, secrets: set[str]) -> str:
    """Replace literal, nonempty secrets with a safe placeholder."""
    for secret in sorted((value for value in secrets if value), key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    return text
