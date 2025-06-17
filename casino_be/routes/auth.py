from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required,
    get_jwt_identity, get_jti, current_user
)
from datetime import datetime, timedelta, timezone
from marshmallow import ValidationError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from casino_be.models import db, User, TokenBlacklist
from casino_be.schemas import UserSchema, RegisterSchema, LoginSchema
from casino_be.utils.bitcoin import generate_bitcoin_wallet

auth_bp = Blueprint('auth', __name__, url_prefix='/api')

# Get the limiter instance that was initialized in app.py
def get_limiter():
    return current_app.extensions.get('limiter')

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
def register():
    # Rate limiting is handled by Flask-Limiter configuration in app.py
    data = request.get_json()
    errors = RegisterSchema().validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'status': False, 'status_message': 'Username already exists'}), 409
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'status': False, 'status_message': 'Email already exists'}), 409
    try:
        # Generate_bitcoin_wallet now returns (address, private_key_wif)
        address, private_key_wif = generate_bitcoin_wallet()

        if not address or not private_key_wif:
            current_app.logger.error("Failed to generate Bitcoin wallet (address or WIF is None).")
            return jsonify({'status': False, 'status_message': 'Failed to generate wallet address for user.'}), 500

        new_user = User(
            username=data['username'],
            email=data['email'],
            password=User.hash_password(data['password']),
            deposit_wallet_address=address  # Store the address
        )
        db.session.add(new_user)
        # The private_key_wif needs to be handled securely.
        # For this exercise, we log its generation and the need for secure storage.
        # In a production system, this key would be encrypted and stored in a secure vault,
        # or managed via an HSM or dedicated key management service.
        # It should NOT be stored directly on the User model in plain text.
        current_app.logger.info(
            f"Generated Bitcoin private key (WIF) for user {new_user.username} (ID will be {new_user.id} after commit). "
            "This key MUST be stored securely and separately. First 5 chars of WIF: "
            f"{private_key_wif[:5]}..."
        )
        # IMPORTANT: The private_key_wif is NOT being saved to the main user database here for security reasons.
        # The polling service or a dedicated wallet management system would need access to this key
        # (e.g., from a secure vault) to sweep funds.

        db.session.commit()
        access_token = create_access_token(identity=new_user)
        refresh_token = create_refresh_token(identity=new_user)
        user_data = UserSchema().dump(new_user)
        current_app.logger.info(f"User registered: {new_user.username} (ID: {new_user.id})")
        return jsonify({
            'status': True, 'user': user_data,
            'access_token': access_token, 'refresh_token': refresh_token
        }), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Registration failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Registration failed.'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    # Rate limiting is handled by Flask-Limiter configuration in app.py
    data = request.get_json()
    schema = LoginSchema()
    try:
        validated_data = schema.load(data)
    except ValidationError as err:
        return jsonify({'status': False, 'status_message': err.messages}), 400

    user = User.query.filter_by(username=validated_data['username']).first()
    if not user or not User.verify_password(user.password, validated_data['password']):
        current_app.logger.warning(f"Login attempt failed for username: {validated_data['username']}")
        return jsonify({'status': False, 'status_message': 'Invalid credentials.'}), 401

    # Update last login time
    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()

    # Generate tokens
    access_token = create_access_token(identity=user)
    refresh_token = create_refresh_token(identity=user)
    user_data = UserSchema().dump(user)
    current_app.logger.info(f"User logged in: {user.username} (ID: {user.id})")
    return jsonify({
        'status': True, 'user': user_data,
        'access_token': access_token, 'refresh_token': refresh_token
    }), 200

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    new_access_token = create_access_token(identity=current_user)
    current_app.logger.info(f"Token refreshed for user: {current_user.username} (ID: {current_user.id})")
    return jsonify({'status': True, 'access_token': new_access_token}), 200

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or ' ' not in auth_header:
             return jsonify({"status": False, "status_message": "Invalid Authorization header"}), 400
        token = auth_header.split()[1]
        jti = get_jti(token)
        now = datetime.now(timezone.utc)
        expires = timedelta(hours=1)
        db.session.add(TokenBlacklist(jti=jti, created_at=now, expires_at=now + expires))
        db.session.commit()
        current_app.logger.info(f"User logged out: {current_user.username} (ID: {current_user.id})")
        return jsonify({"status": True, "status_message": "Successfully logged out"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Logout failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Logout failed.'}), 500

@auth_bp.route('/logout2', methods=['POST'])
@jwt_required(refresh=True)
def logout2():
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or ' ' not in auth_header:
             return jsonify({"status": False, "status_message": "Invalid Authorization header"}), 400
        token = auth_header.split()[1]
        jti = get_jti(token)
        now = datetime.now(timezone.utc)
        expires = timedelta(days=7)
        db.session.add(TokenBlacklist(jti=jti, created_at=now, expires_at=now + expires))
        db.session.commit()
        current_app.logger.info(f"User refresh token invalidated: {current_user.username} (ID: {current_user.id})")
        return jsonify({"status": True, "status_message": "Refresh token invalidated"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Refresh token invalidation failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Refresh token invalidation failed.'}), 500
