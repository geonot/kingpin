import pytest
from casino_be.exceptions import (
    AppException,
    ValidationException,
    AuthenticationException,
    AuthorizationException,
    NotFoundException,
    InsufficientFundsException,
    GameLogicException,
    InternalServerErrorException
)
from casino_be.error_codes import ErrorCodes

def test_app_exception_instantiation():
    error_code = "TEST_001"
    status_message = "Test message"
    status_code = 400
    details = {"field": "value"}
    action_button = {"text": "Retry", "actionType": "RETRY_ACTION"}

    exc = AppException(
        error_code=error_code,
        status_message=status_message,
        status_code=status_code,
        details=details,
        action_button=action_button
    )

    assert exc.error_code == error_code
    assert exc.status_message == status_message
    assert exc.status_code == status_code
    assert exc.details == details
    assert exc.action_button == action_button
    assert str(exc) == status_message

def test_app_exception_defaults():
    exc = AppException(error_code="TEST_002", status_message="Default test", status_code=500)
    assert exc.details == {}
    assert exc.action_button == {}

def test_validation_exception():
    details = {"field": "Invalid format"}
    exc = ValidationException(status_message="Input is invalid", details=details)
    assert exc.error_code == ErrorCodes.VALIDATION_ERROR
    assert exc.status_code == 422
    assert exc.status_message == "Input is invalid"
    assert exc.details == details
    with pytest.raises(ValidationException):
        raise exc

def test_authentication_exception():
    exc = AuthenticationException(status_message="User not authenticated")
    assert exc.error_code == ErrorCodes.UNAUTHENTICATED
    assert exc.status_code == 401
    assert exc.status_message == "User not authenticated"
    with pytest.raises(AuthenticationException):
        raise exc

def test_authorization_exception():
    exc = AuthorizationException(status_message="Action forbidden")
    assert exc.error_code == ErrorCodes.FORBIDDEN
    assert exc.status_code == 403
    assert exc.status_message == "Action forbidden"
    with pytest.raises(AuthorizationException):
        raise exc

def test_not_found_exception():
    exc = NotFoundException(status_message="Item not found")
    assert exc.error_code == ErrorCodes.NOT_FOUND
    assert exc.status_code == 404
    assert exc.status_message == "Item not found"
    with pytest.raises(NotFoundException):
        raise exc

def test_insufficient_funds_exception():
    exc = InsufficientFundsException(status_message="Not enough money")
    assert exc.error_code == ErrorCodes.INSUFFICIENT_FUNDS
    assert exc.status_code == 400
    assert exc.status_message == "Not enough money"
    with pytest.raises(InsufficientFundsException):
        raise exc

def test_game_logic_exception():
    exc = GameLogicException(status_message="Invalid move", status_code=400)
    assert exc.error_code == ErrorCodes.GAME_LOGIC_ERROR
    assert exc.status_code == 400
    assert exc.status_message == "Invalid move"
    with pytest.raises(GameLogicException):
        raise exc

def test_internal_server_error_exception():
    exc = InternalServerErrorException(status_message="Server exploded")
    assert exc.error_code == ErrorCodes.INTERNAL_SERVER_ERROR
    assert exc.status_code == 500
    assert exc.status_message == "Server exploded"
    with pytest.raises(InternalServerErrorException):
        raise exc

# Test raising and catching base AppException
def test_raise_app_exception():
    with pytest.raises(AppException) as excinfo:
        raise AppException(error_code="BASE_ERR", status_message="Base error", status_code=450)
    assert excinfo.value.error_code == "BASE_ERR"
    assert excinfo.value.status_code == 450
    assert str(excinfo.value) == "Base error"
