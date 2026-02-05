class AppError(Exception):
    """Base class for application errors."""
    pass

class ConcurrencyError(AppError):
    """Raised when an update fails due to version conflict."""
    def __init__(self, message: str, current_version: int, expected_version: int):
        self.message = message
        self.current_version = current_version
        self.expected_version = expected_version
        super().__init__(message)

class ResourceNotFoundError(AppError):
    """Raised when a requested resource is not found."""
    pass

class ValidationError(AppError):
    """Raised when input data is invalid."""
    pass

class ConflictError(AppError):
    """Raised when an operation conflicts with current state."""
    pass

class GovernanceError(AppError):
    """Raised when an operation violates governance rules."""
    pass
