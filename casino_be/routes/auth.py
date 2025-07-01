from flask import Blueprint, request, jsonify, current_app, make_response
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required,
    get_jwt_identity, get_jti, current_user, set_access_cookies,
    set_refresh_cookies, unset_jwt_cookies
)
from datetime import datetime, timedelta, timezone
from marshmallow import ValidationError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import secrets

from casino_be.models import db, User, TokenBlacklist
from casino_be.schemas import UserSchema, RegisterSchema, LoginSchema
from casino_be.utils.bitcoin import generate_bitcoin_wallet
from casino_be.utils.security import require_csrf_token, generate_csrf_token
from casino_be.exceptions import AuthenticationException, ValidationException
from casino_be.error_codes import ErrorCodes
from casino_be.app import is_password_strong

auth_bp = Blueprint('auth', __name__, url_prefix='/api')

# Rate limiting decorator for auth endpoints
def rate_limit_auth(func):
    def wrapper(*args, **kwargs):
        limiter = current_app.extensions.get('limiter')
        if limiter:
            limiter.limit("5 per minute")(func)(*args, **kwargs)
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    try:
        user_data = UserSchema().dump(current_user)
        current_app.logger.info(f"User profile fetched: {current_user.username} (ID: {current_user.id})")
        return jsonify({'status': True, 'user': user_data}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching user profile: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to fetch user profile.'}), 500

@auth_bp.route('/register', methods=['POST'])
@rate_limit_auth
@require_csrf_token
def register():
    data = request.get_json()
    try:
        # Use load() which raises ValidationError on failure
        validated_data = RegisterSchema().load(data)
    except ValidationError as err:
        # Let the global handler (@app.errorhandler(ValidationError)) in app.py handle this.
        # It will log and return a 422 response.
        raise err

    # Password strength check
    is_strong, message = is_password_strong(validated_data['password'])
    if not is_strong:
        raise ValidationException(
            status_message=message or "Password does not meet complexity requirements.",
            details={'password': message or "Password does not meet complexity requirements."}
        ) # error_code is set by default

    if User.query.filter_by(username=validated_data['username']).first():
        raise ValidationException(
            status_message="Username already taken.",
            details={'username': 'Username already taken.'}
        ) # error_code is set by default
    
    if User.query.filter_by(email=validated_data['email']).first():
        raise ValidationException(
            status_message="Email already registered.",
            details={'email': 'Email already exists.'}
        ) # error_code is set by default
    
    try:
        # Generate_bitcoin_wallet now returns (address, private_key_wif)
        address, private_key_wif = generate_bitcoin_wallet()

        if not address or not private_key_wif:
            # This should ideally be an InternalServerErrorException if it's a system capability failure
            current_app.logger.error("Failed to generate Bitcoin wallet (address or WIF is None).")
            # Re-throwing as a more generic internal error, or a specific WalletCreationError if defined
            raise Exception("Failed to generate wallet address for user during registration.") # Will be caught by global 500
        
        # Import encryption utilities
        from casino_be.utils.encryption import encrypt_private_key # Absolute import
        
        try:
            # Encrypt the private key
            encrypted_private_key = encrypt_private_key(private_key_wif)
            
            new_user = User(
                username=validated_data['username'],
                email=validated_data['email'],
                password=User.hash_password(validated_data['password']),
                deposit_wallet_address=address  # Store the address
            )
            
            # Try to set private key if column exists
            if hasattr(new_user, 'deposit_wallet_private_key'):
                new_user.deposit_wallet_private_key = encrypted_private_key
                
        except Exception as e:
            current_app.logger.warning(f"Could not store private key (column may not exist): {e}")
            # Continue with just the address for now
            new_user = User(
                username=validated_data['username'],
                email=validated_data['email'],
                password=User.hash_password(validated_data['password']),
                deposit_wallet_address=address  # Store the address
            )
        
        db.session.add(new_user)
        # Note: Private key storage depends on database schema
        current_app.logger.info(
            f"Generated Bitcoin wallet for user {new_user.username}. "
            f"Address: {address}"
        )
        # The polling service or a dedicated wallet management system would need access to this key
        # (e.g., from a secure vault) to sweep funds.

        db.session.commit()
        
        # Create tokens
        access_token = create_access_token(identity=new_user)
        refresh_token = create_refresh_token(identity=new_user)
        user_data = UserSchema().dump(new_user)
        
        # Create response with HTTP-only cookies
        response = make_response(jsonify({
            'status': True, 
            'user': user_data,
            'csrf_token': generate_csrf_token()
        }), 201)
        
        # Set secure cookies
        set_access_cookies(response, access_token)
        set_refresh_cookies(response, refresh_token)
        
        current_app.logger.info(f"User registered: {new_user.username} (ID: {new_user.id})")
        return response
        
    except Exception as e:
        db.session.rollback()
        # Logging is handled by the global error handler
        # Re-raise the exception or a custom one if needed to be more specific
        raise # Reraises the last exception, will be caught by global handler
        # current_app.logger.error(f"Registration failed: {str(e)}", exc_info=True) - Handled globally
        # return jsonify({'status': False, 'status_message': 'Registration failed.'}), 500 - Handled globally

@auth_bp.route('/login', methods=['POST'])
@rate_limit_auth
def login():
    data = request.get_json()
    schema = LoginSchema()
    try:
        validated_data = schema.load(data)
    except ValidationError as err:
        return jsonify({'status': False, 'status_message': err.messages}), 400

    user = User.query.filter_by(username=validated_data['username']).first()
    if not user or not User.verify_password(user.password, validated_data['password']):
        # Logging of failed attempt can be kept here or moved to exception logic if sensitive
        current_app.logger.warning(f"Failed login attempt for username: {validated_data['username']} from IP: {request.remote_addr}")
        raise AuthenticationException(
            status_message="Invalid username or password."
        ) # error_code is set by default in the exception

    # Update last login time
    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()

    # Generate tokens
    access_token = create_access_token(identity=user)
    refresh_token = create_refresh_token(identity=user)
    user_data = UserSchema().dump(user)
    
    # Create response with HTTP-only cookies
    response = make_response(jsonify({
        'status': True, 
        'user': user_data,
        'csrf_token': generate_csrf_token()
    }), 200)
    
    # Set secure cookies
    set_access_cookies(response, access_token)
    set_refresh_cookies(response, refresh_token)
    
    current_app.logger.info(f"User logged in: {user.username} (ID: {user.id})")
    return response

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    new_access_token = create_access_token(identity=current_user)
    
    # Create response with new access token in HTTP-only cookie
    response = make_response(jsonify({
        'status': True,
        'csrf_token': generate_csrf_token()
    }), 200)
    
    set_access_cookies(response, new_access_token)
    
    current_app.logger.info(f"Token refreshed for user: {current_user.username} (ID: {current_user.id})")
    return response

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
@require_csrf_token
def logout():
    try:
        # Get JWT identifier from cookie
        jti = get_jti(request.cookies.get('access_token_cookie', ''))
        if jti:
            now = datetime.now(timezone.utc)
            expires = timedelta(hours=1)
            db.session.add(TokenBlacklist(jti=jti, created_at=now, expires_at=now + expires))
        
        # Also blacklist refresh token if present
        refresh_jti = get_jti(request.cookies.get('refresh_token_cookie', ''))
        if refresh_jti:
            now = datetime.now(timezone.utc)
            expires = timedelta(days=7)
            db.session.add(TokenBlacklist(jti=refresh_jti, created_at=now, expires_at=now + expires))
        
        db.session.commit()
        
        # Create response and clear cookies
        response = make_response(jsonify({
            "status": True, 
            "status_message": "Successfully logged out"
        }), 200)
        
        unset_jwt_cookies(response)
        
        current_app.logger.info(f"User logged out: {current_user.username} (ID: {current_user.id})")
        return response
        
    except Exception as e:
        db.session.rollback()
        # Logging is handled by the global error handler
        raise # Reraises the last exception
        # current_app.logger.error(f"Logout failed: {str(e)}", exc_info=True) - Handled globally
        # return jsonify({'status': False, 'status_message': 'Logout failed.'}), 500 - Handled globally

@auth_bp.route('/csrf-token', methods=['GET'])
def get_csrf_token():
    """Get CSRF token for state-changing operations"""
    return jsonify({
        'status': True,
        'csrf_token': generate_csrf_token()
    }), 200
