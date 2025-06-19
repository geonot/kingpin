import json
import pytest
from flask import Flask, jsonify, g, current_app
from werkzeug.exceptions import MethodNotAllowed, NotFound as WerkzeugNotFound
from marshmallow import ValidationError

from casino_be.app import create_app, db
from casino_be.models import User # For potential auth-related tests if needed
from casino_be.config import TestingConfig
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

# Minimal App for testing error handlers directly if needed,
# but BaseTestCase from test_api.py is preferred for integration-style tests.
# For now, we will create specific routes on the test app.

class TestAppErrorHandlers:

    @pytest.fixture(scope="class")
    def app(self):
        """Create and configure a new app instance for each test class."""
        app = create_app(TestingConfig)

        # Define mock routes directly on the app for testing
        @app.route('/test/app_exception')
        def route_app_exception():
            raise AppException(
                error_code="TEST_APP_EXC",
                status_message="This is an AppException",
                status_code=450,
                details={"info": "some app details"},
                action_button={"text": "Click Me", "actionType": "NAVIGATE", "actionPayload": "/home"}
            )

        @app.route('/test/validation_exception')
        def route_validation_exception():
            raise ValidationException(status_message="Invalid input provided", details={"field": "wrong"})

        @app.route('/test/authentication_exception')
        def route_authentication_exception():
            raise AuthenticationException(status_message="User auth failed")

        @app.route('/test/authorization_exception')
        def route_authorization_exception():
            raise AuthorizationException(status_message="Permission denied")

        @app.route('/test/not_found_exception')
        def route_not_found_exception():
            raise NotFoundException(status_message="Custom resource not found")

        @app.route('/test/insufficient_funds_exception')
        def route_insufficient_funds_exception():
            raise InsufficientFundsException(status_message="Not enough balance")

        @app.route('/test/game_logic_exception')
        def route_game_logic_exception():
            raise GameLogicException(status_message="Invalid game move")

        @app.route('/test/internal_server_error_exception')
        def route_internal_server_error_exception():
            raise InternalServerErrorException(status_message="Custom server error")

        @app.route('/test/unhandled_exception')
        def route_unhandled_exception():
            raise ValueError("A generic unhandled error")

        @app.route('/test/werkzeug_not_found')
        def route_werkzeug_not_found():
            # This won't be hit, Flask handles /test/werkzeug_not_found before it gets here
            # if it's not defined. To test Flask's 404, request a truly undefined route.
            pass

        @app.route('/test/method_not_allowed', methods=['GET'])
        def route_method_not_allowed():
            return jsonify(status=True) # GET is fine

        @app.route('/test/marshmallow_validation_error', methods=['POST'])
        def route_marshmallow_error():
            # Simulate a scenario where Marshmallow ValidationError would be raised
            # and caught by the @app.errorhandler(ValidationError)
            # For this test, we'll raise it directly as if it came from a schema
            raise ValidationError(message="Marshmallow schema validation failed", field_name="test_field")

        app_context = app.app_context()
        app_context.push()
        db.create_all() # Initialize database if any test interacts with it

        yield app # provide the app to the tests

        db.session.remove()
        db.drop_all()
        app_context.pop()


    @pytest.fixture()
    def client(self, app):
        """A test client for the app."""
        return app.test_client()

    def test_app_exception_handler(self, client, caplog):
        response = client.get('/test/app_exception')
        assert response.status_code == 450
        json_data = response.get_json()
        assert json_data['error_code'] == "TEST_APP_EXC"
        assert json_data['status_message'] == "This is an AppException"
        assert json_data['details'] == {"info": "some app details"}
        assert json_data['action_button'] == {"text": "Click Me", "actionType": "NAVIGATE", "actionPayload": "/home"}
        assert 'request_id' in json_data

        # Check logs
        assert any(rec.levelname == 'ERROR' and 'TEST_APP_EXC' in rec.message and json_data['request_id'] in rec.message for rec in caplog.records)

    def test_validation_exception_handler(self, client, caplog):
        response = client.get('/test/validation_exception')
        assert response.status_code == 422
        json_data = response.get_json()
        assert json_data['error_code'] == ErrorCodes.VALIDATION_ERROR
        assert json_data['status_message'] == "Invalid input provided"
        assert json_data['details'] == {"field": "wrong"}
        assert 'request_id' in json_data
        assert any(rec.levelname == 'ERROR' and ErrorCodes.VALIDATION_ERROR in rec.message for rec in caplog.records)


    def test_authentication_exception_handler(self, client, caplog):
        response = client.get('/test/authentication_exception')
        assert response.status_code == 401
        json_data = response.get_json()
        assert json_data['error_code'] == ErrorCodes.UNAUTHENTICATED
        assert json_data['status_message'] == "User auth failed"
        assert 'request_id' in json_data
        assert any(rec.levelname == 'ERROR' and ErrorCodes.UNAUTHENTICATED in rec.message for rec in caplog.records)

    def test_authorization_exception_handler(self, client, caplog):
        response = client.get('/test/authorization_exception')
        assert response.status_code == 403
        json_data = response.get_json()
        assert json_data['error_code'] == ErrorCodes.FORBIDDEN
        assert json_data['status_message'] == "Permission denied"
        assert 'request_id' in json_data
        assert any(rec.levelname == 'ERROR' and ErrorCodes.FORBIDDEN in rec.message for rec in caplog.records)

    def test_not_found_exception_handler(self, client, caplog): # Custom NotFoundException
        response = client.get('/test/not_found_exception')
        assert response.status_code == 404
        json_data = response.get_json()
        assert json_data['error_code'] == ErrorCodes.NOT_FOUND
        assert json_data['status_message'] == "Custom resource not found"
        assert 'request_id' in json_data
        assert any(rec.levelname == 'ERROR' and ErrorCodes.NOT_FOUND in rec.message for rec in caplog.records)

    def test_werkzeug_not_found_handler(self, client, caplog): # Flask's default 404
        response = client.get('/this_route_does_not_exist')
        assert response.status_code == 404
        json_data = response.get_json()
        assert json_data['error_code'] == ErrorCodes.NOT_FOUND
        assert json_data['status_message'] == "The requested resource was not found." # Default message from handler
        assert json_data['details'] == {'path': '/this_route_does_not_exist'}
        assert 'request_id' in json_data
        assert any(rec.levelname == 'WARNING' and ErrorCodes.NOT_FOUND in rec.message for rec in caplog.records)


    def test_method_not_allowed_handler(self, client, caplog):
        response = client.post('/test/method_not_allowed') # Call with POST when only GET is allowed
        assert response.status_code == 405
        json_data = response.get_json()
        assert json_data['error_code'] == ErrorCodes.METHOD_NOT_ALLOWED
        assert json_data['status_message'] == "Method Not Allowed"
        assert 'request_id' in json_data
        assert any(rec.levelname == 'WARNING' and ErrorCodes.METHOD_NOT_ALLOWED in rec.message for rec in caplog.records)

    def test_marshmallow_validation_error_handler(self, client, caplog):
        response = client.post('/test/marshmallow_validation_error', json={}) # POST to trigger the route
        assert response.status_code == 422 # As defined in handle_validation_error
        json_data = response.get_json()
        assert json_data['error_code'] == ErrorCodes.VALIDATION_ERROR
        assert json_data['status_message'] == "Input validation failed."
        # Marshmallow's error structure is preserved in details.errors
        assert 'errors' in json_data['details']
        assert json_data['details']['errors'] == {"test_field": ["Marshmallow schema validation failed"]}
        assert 'request_id' in json_data
        assert any(rec.levelname == 'WARNING' and ErrorCodes.VALIDATION_ERROR in rec.message for rec in caplog.records)

    def test_unhandled_exception_handler(self, client, caplog):
        response = client.get('/test/unhandled_exception')
        assert response.status_code == 500
        json_data = response.get_json()
        assert json_data['error_code'] == ErrorCodes.INTERNAL_SERVER_ERROR
        assert json_data['status_message'] == 'An unexpected internal server error occurred. Please try again later.'
        assert 'request_id' in json_data
        # Check logs for CRITICAL
        assert any(rec.levelname == 'CRITICAL' and ErrorCodes.INTERNAL_SERVER_ERROR in rec.message and "ValueError: A generic unhandled error" in rec.message for rec in caplog.records)

    def test_insufficient_funds_exception_handler(self, client, caplog):
        response = client.get('/test/insufficient_funds_exception')
        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['error_code'] == ErrorCodes.INSUFFICIENT_FUNDS
        assert json_data['status_message'] == "Not enough balance"
        assert 'request_id' in json_data
        assert any(rec.levelname == 'ERROR' and ErrorCodes.INSUFFICIENT_FUNDS in rec.message for rec in caplog.records)

    def test_game_logic_exception_handler(self, client, caplog):
        response = client.get('/test/game_logic_exception')
        assert response.status_code == 400 # Default for GameLogicException if not overridden
        json_data = response.get_json()
        assert json_data['error_code'] == ErrorCodes.GAME_LOGIC_ERROR
        assert json_data['status_message'] == "Invalid game move"
        assert 'request_id' in json_data
        assert any(rec.levelname == 'ERROR' and ErrorCodes.GAME_LOGIC_ERROR in rec.message for rec in caplog.records)

    def test_internal_server_error_exception_handler(self, client, caplog): # Custom InternalServerErrorException
        response = client.get('/test/internal_server_error_exception')
        assert response.status_code == 500
        json_data = response.get_json()
        assert json_data['error_code'] == ErrorCodes.INTERNAL_SERVER_ERROR
        assert json_data['status_message'] == "Custom server error"
        assert 'request_id' in json_data
        assert any(rec.levelname == 'ERROR' and ErrorCodes.INTERNAL_SERVER_ERROR in rec.message for rec in caplog.records)

    # Example of how to test logging for request_id (already integrated into above tests)
    def test_logging_includes_request_id(self, client, caplog):
        # For this test, we make g.request_id predictable if possible, or just check its presence
        # The app.before_request sets g.request_id to a uuid.
        # We can't easily predict it here, but we can check if it's logged.

        # Trigger any error that logs, e.g., a custom AppException
        response = client.get('/test/app_exception')
        json_data = response.get_json()
        request_id_from_response = json_data.get('request_id')
        assert request_id_from_response is not None

        # Check if any log record for this request contains the request_id
        found_log_with_request_id = False
        for record in caplog.records:
            if hasattr(record, 'request_id') and record.request_id == request_id_from_response:
                found_log_with_request_id = True
                break
            # Also check if request_id is part of the formatted message if formatter includes it
            if request_id_from_response in record.getMessage():
                 found_log_with_request_id = True
                 break
        assert found_log_with_request_id, f"No log record found containing request_id {request_id_from_response}"
