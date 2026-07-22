class AppError(Exception):
    status_code = 400

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class UnauthorizedError(AppError):
    status_code = 401


class ForbiddenError(AppError):
    status_code = 403


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    """Raised on optimistic-lock version mismatch or duplicate-key business rules."""

    status_code = 409


class BusinessRuleError(AppError):
    """Raised when a request is well-formed but violates a domain rule
    (e.g. closing a parent task with incomplete children)."""

    status_code = 422
