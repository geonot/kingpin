"""
Security utilities for CSRF protection and other security measures
"""
import secrets
import hashlib
import hmac
from functools import wraps
from flask import request, jsonify, current_app, session
from datetime import datetime, timedelta
import jwt


def generate_csrf_token():
    """Generate a cryptographically secure CSRF token"""
    return secrets.token_urlsafe(32)


def verify_csrf_token(token, stored_token):
    """Verify CSRF token using constant-time comparison"""
    if not token or not stored_token:
        return False
    return hmac.compare_digest(token, stored_token)


def require_csrf_token(f):
    """Decorator to require CSRF token for state-changing operations"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            csrf_token = request.headers.get('X-CSRF-Token')
            stored_token = session.get('csrf_token')
            
            if not csrf_token or not verify_csrf_token(csrf_token, stored_token):
                current_app.logger.warning(f"CSRF token validation failed for {request.endpoint} from IP: {request.remote_addr}")
                return jsonify({'status': False, 'status_message': 'Invalid CSRF token'}), 403
        
        return f(*args, **kwargs)
    return decorated


def rate_limit_by_ip(limit="10 per minute"):
    """Enhanced rate limiting decorator with IP tracking"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            limiter = current_app.extensions.get('limiter')
            if limiter:
                # Apply rate limiting
                try:
                    limiter.limit(limit)(f)(*args, **kwargs)
                except Exception as e:
                    current_app.logger.warning(f"Rate limit exceeded for {request.endpoint} from IP: {request.remote_addr}")
                    return jsonify({'status': False, 'status_message': 'Rate limit exceeded'}), 429
            
            return f(*args, **kwargs)
        return decorated
    return decorator


def validate_ip_whitelist(whitelist=None):
    """Validate request IP against whitelist for sensitive operations"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if whitelist:
                client_ip = request.remote_addr
                if client_ip not in whitelist:
                    current_app.logger.warning(f"Unauthorized IP {client_ip} attempted to access {request.endpoint}")
                    return jsonify({'status': False, 'status_message': 'Unauthorized IP address'}), 403
            
            return f(*args, **kwargs)
        return decorated
    return decorator


def sanitize_input(data):
    """Sanitize input data to prevent injection attacks"""
    if isinstance(data, str):
        # Basic XSS prevention
        data = data.replace('<', '&lt;').replace('>', '&gt;')
        # Remove potential SQL injection patterns
        dangerous_patterns = ['--', ';', 'DROP', 'DELETE', 'INSERT', 'UPDATE', 'UNION', 'SELECT']
        for pattern in dangerous_patterns:
            data = data.replace(pattern.lower(), '').replace(pattern.upper(), '')
    elif isinstance(data, dict):
        return {key: sanitize_input(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [sanitize_input(item) for item in data]
    
    return data


def secure_headers(response):
    """Add security headers to response"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response


def log_security_event(event_type, user_id=None, details=None):
    """Log security-related events for monitoring"""
    log_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': event_type,
        'ip_address': request.remote_addr,
        'user_agent': request.headers.get('User-Agent', ''),
        'user_id': user_id,
        'details': details or {}
    }
    
    current_app.logger.warning(f"SECURITY_EVENT: {log_data}")


def validate_password_strength(password):
    """Validate password meets security requirements"""
    errors = []
    
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    
    if not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")
    
    if not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")
    
    if not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one digit")
    
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        errors.append("Password must contain at least one special character")
    
    # Check for common passwords
    common_passwords = ['password', '123456', 'password123', 'admin', 'qwerty']
    if password.lower() in common_passwords:
        errors.append("Password is too common")
    
    return errors


def generate_secure_session_id():
    """Generate a cryptographically secure session ID"""
    return secrets.token_urlsafe(64)
