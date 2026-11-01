class ApiError(Exception):
    """Raised anywhere in the backend to produce a clean JSON error response."""

    def __init__(self, status: int, message: str, **extra):
        super().__init__(message)
        self.status = status
        self.message = message
        self.extra = extra
