from casino_be.error_codes import ErrorCodes

class AppException(Exception):
    def __init__(self, error_code, status_message, status_code, details=None, action_button=None):
        super().__init__(status_message)
        self.error_code = error_code
        self.status_message = status_message
        self.status_code = status_code
        self.details = details if details is not None else {}
        self.action_button = action_button if action_button is not None else {}

class ValidationException(AppException):
    def __init__(self, status_message="Validation failed", details=None, action_button=None):
        super().__init__(
            error_code=ErrorCodes.VALIDATION_ERROR,
            status_message=status_message,
            status_code=422,
            details=details,
            action_button=action_button
        )

class AuthenticationException(AppException):
    def __init__(self, status_message="Authentication required", details=None, action_button=None):
        super().__init__(
            error_code=ErrorCodes.UNAUTHENTICATED,
            status_message=status_message,
            status_code=401,
            details=details,
            action_button=action_button
        )

class AuthorizationException(AppException):
    def __init__(self, status_message="Forbidden", details=None, action_button=None):
        super().__init__(
            error_code=ErrorCodes.FORBIDDEN,
            status_message=status_message,
            status_code=403,
            details=details,
            action_button=action_button
        )

class NotFoundException(AppException):
    def __init__(self, status_message="Resource not found", details=None, action_button=None):
        super().__init__(
            error_code=ErrorCodes.NOT_FOUND,
            status_message=status_message,
            status_code=404,
            details=details,
            action_button=action_button
        )

class InsufficientFundsException(AppException):
    def __init__(self, status_message="Insufficient funds", details=None, action_button=None):
        super().__init__(
            error_code=ErrorCodes.INSUFFICIENT_FUNDS,
            status_message=status_message,
            status_code=400,
            details=details,
            action_button=action_button
        )

class GameLogicException(AppException):
    def __init__(self, status_message="Game logic error", details=None, action_button=None, status_code=400):
        super().__init__(
            error_code=ErrorCodes.GAME_LOGIC_ERROR,
            status_message=status_message,
            status_code=status_code, # Can be 400 or 500
            details=details,
            action_button=action_button
        )

class InternalServerErrorException(AppException):
    def __init__(self, status_message="Internal server error", details=None, action_button=None):
        super().__init__(
            error_code=ErrorCodes.INTERNAL_SERVER_ERROR,
            status_message=status_message,
            status_code=500,
            details=details,
            action_button=action_button
        )
