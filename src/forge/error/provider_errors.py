"""Errors raised by AI provider configuration and execution."""


class ProviderError(Exception):
    """Base error for provider setup and execution."""


class ProviderConfigurationError(ProviderError):
    """Provider settings or credentials are invalid."""


class ProviderAuthenticationError(ProviderError):
    """The provider rejected authentication."""


class ProviderTimeoutError(ProviderError):
    """The provider request timed out."""


class ProviderRateLimitError(ProviderError):
    """The provider rejected a request due to rate limiting."""


class ProviderExecutionError(ProviderError):
    """The provider request failed or returned unusable output."""
