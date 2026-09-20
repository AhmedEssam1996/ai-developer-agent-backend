"""Domain errors.

These map to safe, user-facing messages. Raw exceptions must never reach the
client; the API layer converts :class:`AppError` into a structured JSON error
with a stable ``code`` the frontend can branch on.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for expected, user-safe application errors."""

    code: str = "app_error"
    http_status: int = 400
    message: str = "Something went wrong."

    def __init__(self, message: str | None = None, *, details: dict | None = None) -> None:
        self.message = message or self.message
        self.details = details or {}
        super().__init__(self.message)

    def to_payload(self) -> dict:
        return {"code": self.code, "message": self.message, "details": self.details}


class NotFoundError(AppError):
    code = "not_found"
    http_status = 404
    message = "The requested resource was not found."


class ValidationError(AppError):
    code = "validation_error"
    http_status = 422
    message = "The request was invalid."


class AuthenticationError(AppError):
    code = "authentication_error"
    http_status = 401
    message = "Authentication is required."


class PermissionDeniedError(AppError):
    code = "permission_denied"
    http_status = 403
    message = "You do not have permission to perform this action."


class RateLimitedError(AppError):
    code = "rate_limited"
    http_status = 429
    message = "Too many requests. Please slow down."


class IntegrationError(AppError):
    code = "integration_error"
    http_status = 502
    message = "An external integration failed."


class IntegrationNotConfiguredError(IntegrationError):
    code = "integration_not_configured"
    http_status = 409
    message = "This integration is not configured."


class IntegrationAuthExpiredError(IntegrationError):
    code = "integration_auth_expired"
    http_status = 401
    message = "Your connection expired. Reconnect to continue."


class IntegrationUnavailableError(IntegrationError):
    code = "integration_unavailable"
    http_status = 503
    message = "The integration is temporarily unavailable. Retry shortly."


class AIProviderError(AppError):
    code = "ai_provider_error"
    http_status = 502
    message = "The AI provider returned an error. Retry."


class AITimeoutError(AIProviderError):
    code = "ai_timeout"
    http_status = 504
    message = "The AI request timed out. Retry."


class AINotConfiguredError(AIProviderError):
    code = "ai_not_configured"
    http_status = 409
    message = "The AI provider is not configured."


class ApprovalRequiredError(AppError):
    code = "approval_required"
    http_status = 202
    message = "This action requires approval before it can run."