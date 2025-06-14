from functools import wraps
from flask import request, jsonify, current_app

def service_token_required(f):
    """
    Decorator to protect routes with a service API token.
    Expects the token to be passed in the 'X-Service-Token' header.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('X-Service-Token')
        if not token:
            current_app.logger.warning("Service token missing for protected route.")
            return jsonify({'status': False, 'status_message': 'Service token required.'}), 401

        expected_token = current_app.config.get('SERVICE_API_TOKEN')
        if not expected_token:
            current_app.logger.error("SERVICE_API_TOKEN is not configured in the application.")
            # Return 500 as this is a server configuration issue
            return jsonify({'status': False, 'status_message': 'Internal server error: Service token not configured.'}), 500

        if token == expected_token:
            return f(*args, **kwargs)
        else:
            current_app.logger.warning("Invalid service token received.")
            # Use 403 Forbidden as the client sent a token, but it's not the correct one.
            # 401 is typically for missing or malformed credentials.
            return jsonify({'status': False, 'status_message': 'Invalid service token.'}), 403
    return decorated_function

def feature_flag_required(flag_name):
    """
    Decorator to enable/disable routes based on a feature flag in Flask app config.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_app.config.get(flag_name, False):
                # Return 404 to make it seem like the feature doesn't exist
                # Or 403 Forbidden if you want to indicate it's a restricted feature
                # Using 404 as per subtask description.
                return jsonify({'message': 'This feature is not currently available.'}), 404
            return f(*args, **kwargs)
        return decorated_function
    return decorator
