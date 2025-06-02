from flask import Flask, request, jsonify

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import (
    JWTManager, create_access_token, create_refresh_token, jwt_required,
    get_jwt_identity, get_jti, current_user
)
from datetime import datetime, timedelta, timezone # Use timezone-aware datetimes
import logging # Add logging

from .models import db, User, GameSession, Transaction, BonusCode, Slot, SlotSymbol, SlotBet, TokenBlacklist, BlackjackTable, BlackjackHand, BlackjackAction
from .schemas import (
    UserSchema, RegisterSchema, LoginSchema, GameSessionSchema, SpinSchema, SpinRequestSchema,
    WithdrawSchema, UpdateSettingsSchema, DepositSchema, SlotSchema, JoinGameSchema,
    BonusCodeSchema, AdminUserSchema, TransactionSchema, UserListSchema, BonusCodeListSchema, TransactionListSchema,
    BalanceTransferSchema, BlackjackTableSchema, BlackjackHandSchema, JoinBlackjackSchema, BlackjackActionRequestSchema,
    AdminCreditDepositSchema
)
from .utils.bitcoin import generate_bitcoin_wallet
from .utils.spin_handler import handle_spin
from .utils.blackjack_helper import handle_join_blackjack, handle_blackjack_action
from .config import Config

# --- App Initialization ---
app = Flask(__name__)
app.config.from_object(Config)

# --- Database Setup ---
db.init_app(app)
migrate = Migrate(app, db, directory='casino_be/migrations')

# --- JWT Setup ---
jwt = JWTManager(app)

# --- Logging Setup ---
# Configure logging with a more informative format and UTC timestamps
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to capture more details; control with env var in prod
    format="%(asctime)s [%(levelname)s] [%(name)s:%(funcName)s:%(lineno)d] - %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z"  # ISO 8601 format for timestamps
)
logger = logging.getLogger(__name__)

# --- JWT Helper Functions ---
@jwt.user_identity_loader
def user_identity_lookup(user):
    return user.id

@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    identity = jwt_data["sub"]
    return User.query.get(identity)

@jwt.token_in_blocklist_loader
def check_if_token_in_blacklist(jwt_header, jwt_payload):
    jti = jwt_payload['jti']
    now = datetime.now(timezone.utc)
    token = db.session.query(TokenBlacklist.id).filter_by(jti=jti).scalar()
    return token is not None

# --- Global Error Handler ---
@app.errorhandler(Exception)
def handle_unhandled_exception(e):
    """
    Global handler for unhandled exceptions.
    Logs the full error and returns a generic 500 response.
    """
    logger.error("Unhandled exception caught by global error handler:", exc_info=True)
    return jsonify({
        'status': False,
        'status_message': 'An unexpected internal server error occurred. Please try again later.'
    }), 500

# --- Response Security Headers ---
@app.after_request
def add_security_headers(response):
    """
    Adds common security headers to all responses.
    """
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    # Basic Content Security Policy:
    # - default-src 'self': Allows content only from the application's own origin.
    # - script-src 'self': Allows scripts only from the application's own origin.
    # - object-src 'none': Disallows plugins (like Flash).
    # - frame-ancestors 'none': Prevents the page from being embedded in iframes on other sites (clickjacking protection).
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none';"

    # HTTP Strict Transport Security (HSTS)
    # This header should only be sent over HTTPS.
    # It tells browsers to only communicate with the site using HTTPS for the specified duration.
    # Enable this if your application is exclusively served over HTTPS in production.
    if request.is_secure and not app.debug: # request.is_secure ensures it's an HTTPS request
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

    return response

# --- Helper Functions ---
def is_admin():
    """Checks if the current JWT user is an admin."""
    return current_user and current_user.is_admin

# --- API Routes ---

# === Authentication ===
@app.route('/api/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get the current user's profile based on JWT"""
    try:
        # current_user is automatically loaded from JWT by the @jwt_required decorator
        user_data = UserSchema().dump(current_user)
        logger.info(f"User profile fetched: {current_user.username} (ID: {current_user.id})")
        return jsonify({
            'status': True,
            'user': user_data
        }), 200
    except Exception as e:
        logger.error(f"Error fetching user profile: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to fetch user profile.'}), 500

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    errors = RegisterSchema().validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400

    if User.query.filter_by(username=data['username']).first():
        logger.warning(f"Registration attempt with existing username: {data['username']} - Path: {request.path}")
        return jsonify({'status': False, 'status_message': 'Username already exists'}), 409 # Conflict
    if User.query.filter_by(email=data['email']).first():
        logger.warning(f"Registration attempt with existing email: {data['email']} - Path: {request.path}")
        return jsonify({'status': False, 'status_message': 'Email already exists'}), 409 # Conflict

    try:
        # Private key is no longer generated or stored here.
        # generate_bitcoin_wallet now only returns an address.
        wallet_address = generate_bitcoin_wallet()

        if not wallet_address:
            logger.error("Failed to generate Bitcoin wallet address during registration.")
            return jsonify({'status': False, 'status_message': 'Failed to generate wallet address for user.'}), 500

        new_user = User(
            username=data['username'],
            email=data['email'],
            password=User.hash_password(data['password']),
            deposit_wallet_address=wallet_address
            # deposit_wallet_private_key is no longer a field in the User model
        )
        db.session.add(new_user)
        db.session.commit()

        access_token = create_access_token(identity=new_user)
        refresh_token = create_refresh_token(identity=new_user)
        user_data = UserSchema().dump(new_user)

        logger.info(f"User registered: {new_user.username} (ID: {new_user.id}) - Path: {request.path}")
        return jsonify({
            'status': True,
            'user': user_data,
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"Registration failed for username {data.get('username')}: {str(e)} - Path: {request.path}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Registration failed due to an internal error.'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    errors = LoginSchema().validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400

    user = User.query.filter_by(username=data['username']).first()
    if not user or not User.verify_password(user.password, data['password']):
        logger.warning(f"Invalid login attempt for username: {data['username']} - Path: {request.path}")
        return jsonify({'status': False, 'status_message': 'Invalid username or password'}), 401

    access_token = create_access_token(identity=user)
    refresh_token = create_refresh_token(identity=user)
    user_data = UserSchema().dump(user)

    logger.info(f"User logged in: {user.username} (ID: {user.id}) - Path: {request.path}")
    return jsonify({
        'status': True,
        'user': user_data,
        'access_token': access_token,
        'refresh_token': refresh_token
    }), 200

@app.route('/api/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    # current_user is automatically loaded from the refresh token
    new_access_token = create_access_token(identity=current_user)
    logger.info(f"Token refreshed for user: {current_user.username} (ID: {current_user.id})")
    return jsonify({'status': True, 'access_token': new_access_token}), 200

@app.route('/api/logout', methods=['POST'])
@jwt_required() # Requires access token
def logout():
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or ' ' not in auth_header:
             return jsonify({"status": False, "status_message": "Invalid Authorization header"}), 400

        token = auth_header.split()[1]
        jti = get_jti(token)
        now = datetime.now(timezone.utc)
        expires = timedelta(hours=1) # Match access token expiry for blocklist entry duration
        db.session.add(TokenBlacklist(jti=jti, created_at=now, expires_at=now + expires))
        db.session.commit()
        logger.info(f"User logged out: {current_user.username} (ID: {current_user.id})")
        return jsonify({"status": True, "status_message": "Successfully logged out"}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Logout failed for user {current_user.id}: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Logout failed.'}), 500

@app.route('/api/logout2', methods=['POST'])
@jwt_required(refresh=True) # Requires refresh token
def logout2():
    # Also blocklist the refresh token
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or ' ' not in auth_header:
             return jsonify({"status": False, "status_message": "Invalid Authorization header"}), 400

        token = auth_header.split()[1]
        jti = get_jti(token)
        now = datetime.now(timezone.utc)
        expires = timedelta(days=7) # Match refresh token expiry
        db.session.add(TokenBlacklist(jti=jti, created_at=now, expires_at=now + expires))
        db.session.commit()
        logger.info(f"User refresh token invalidated: {current_user.username} (ID: {current_user.id})")
        return jsonify({"status": True, "status_message": "Refresh token invalidated"}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Refresh token invalidation failed for user {current_user.id}: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Refresh token invalidation failed.'}), 500


# === Game Play ===
@app.route('/api/end_session', methods=['POST'])
@jwt_required()
def end_session():
    """Explicitly end the current game session"""
    user_id = current_user.id
    now = datetime.now(timezone.utc)

    try:
        # Find and close any active sessions for this user
        active_sessions = GameSession.query.filter_by(user_id=user_id, session_end=None).all()
        if not active_sessions:
            return jsonify({'status': True, 'status_message': 'No active session to end'}), 200

        for session in active_sessions:
            session.session_end = now
            logger.info(f"Explicitly ended game session {session.id} for user {user_id}")

        db.session.commit()
        return jsonify({'status': True, 'status_message': 'Session ended successfully'}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to end session for user {user_id}: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to end session due to an internal error.'}), 500

@app.route('/api/join', methods=['POST'])
@jwt_required()
def join_game():
    data = request.get_json()
    errors = JoinGameSchema().validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400

    game_type = data.get('game_type') # Schema already validates game_type presence and values

    slot_id = None
    table_id = None

    if game_type == 'blackjack':
        # Direct users to the specific endpoint for joining blackjack games
        logger.info(f"Blackjack join attempt via /api/join by user {current_user.id}. Redirecting to /api/join_blackjack.")
        return jsonify({
            'status': False,
            'status_message': 'For blackjack games, please use the /api/join_blackjack endpoint.',
            'use_endpoint': '/api/join_blackjack'
        }), 400

    elif game_type == 'slot':
        slot_id_from_request = data.get('slot_id')
        if slot_id_from_request is None: # Check if None, not just falsy (e.g. 0 if it were valid)
            logger.warning(f"slot_id missing in request for slot game join by user {current_user.id}")
            return jsonify({'status': False, 'status_message': 'slot_id is required for slot games'}), 400

        slot = Slot.query.get(slot_id_from_request)
        if not slot:
            logger.warning(f"Slot with ID {slot_id_from_request} not found for join attempt by user {current_user.id}")
            return jsonify({'status': False, 'status_message': f'Slot with ID {slot_id_from_request} not found'}), 404

        slot_id = slot_id_from_request # Assign validated slot_id
        table_id = None # Explicitly None for slot games

    else:
        # This case should ideally not be reached if JoinGameSchema.game_type has OneOf(['slot', 'blackjack'])
        # and the schema is validated before this logic.
        logger.error(f"Invalid game_type '{game_type}' encountered in /api/join for user {current_user.id} despite schema validation.")
        return jsonify({'status': False, 'status_message': f'Invalid game type: {game_type}'}), 400

    user_id = current_user.id
    now = datetime.now(timezone.utc)

    try:
        # Close any existing active sessions for this user
        active_sessions = GameSession.query.filter_by(user_id=user_id, session_end=None).all()
        for session in active_sessions:
            session.session_end = now
            logger.info(f"Closed previous game session {session.id} for user {user_id}")

        # Create a new session
        new_session = GameSession(
            user_id=user_id,
            slot_id=slot_id,
            table_id=table_id,
            game_type=game_type,
            session_start=now,
            amount_wagered=0,
            amount_won=0,
            num_spins=0
        )
        db.session.add(new_session)
        db.session.commit()

        session_data = GameSessionSchema().dump(new_session)
        logger.info(f"User {user_id} joined {game_type} game, session {new_session.id} created.")

        return jsonify({
            'status': True,
            'game_session': session_data,
            'session_id': new_session.id # Explicit ID for clarity on frontend
        }), 201 # Use 201 Created

    except Exception as e:
        db.session.rollback()
        logger.error(f"Join game failed for user {user_id}, game type {game_type}: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to join game due to an internal error.'}), 500

@app.route('/api/spin', methods=['POST'])
@jwt_required()
def spin():
    data = request.get_json()
    errors = SpinRequestSchema().validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400

    user = current_user # User object is loaded by JWT
    bet_amount_sats = data['bet_amount'] # Expecting satoshis from frontend

    # Validate bet amount (should be positive integer)
    if not isinstance(bet_amount_sats, int) or bet_amount_sats <= 0:
        return jsonify({'status': False, 'status_message': 'Invalid bet amount. Must be a positive integer (satoshis).'}), 400

    # Find the user's active game session
    game_session = GameSession.query.filter_by(user_id=user.id, session_end=None).order_by(GameSession.session_start.desc()).first()

    if not game_session:
        logger.warning(f"No active game session found for user {user.id} during spin attempt. Path: {request.path}")
        return jsonify({'status': False, 'status_message': 'No active game session found. Please join a game first.'}), 404

    slot = Slot.query.get(game_session.slot_id)
    logger.debug(f"Slot details for spin: {slot} - User: {user.id}, Path: {request.path}") # Replaced print with logger.debug
    if not slot:
         logger.error(f"Slot ID {game_session.slot_id} not found for active session {game_session.id}. User: {user.id}. Path: {request.path}")
         return jsonify({'status': False, 'status_message': 'Internal error: Slot associated with session not found.'}), 500

    # Check balance (using Satoshis)
    if user.balance < bet_amount_sats:
        logger.warning(f"Insufficient balance for user {user.id} (Balance: {user.balance}, Bet: {bet_amount_sats}). Path: {request.path}")
        return jsonify({
            'status': False,
            'status_message': 'Insufficient balance'
        }), 400 # Use 400 Bad Request or 402 Payment Required

    try:
        # --- Core Spin Logic ---
        result = handle_spin(user, slot, game_session, bet_amount_sats)
        # --- End Spin Logic ---

        db.session.commit() # Commit changes made within handle_spin (user balance, session stats, spin record)

        # Prepare response data
        user_data = UserSchema().dump(user) # Get updated user data
        session_data = GameSessionSchema().dump(game_session) # Get updated session data

        logger.info(f"Spin successful for user {user.id}, session {game_session.id}. Bet: {bet_amount_sats}, Win: {result['win_amount_sats']}. New Balance: {user.balance}. Path: {request.path}")

        return jsonify({
            'status': True,
            'result': result['spin_result'],
            'win_amount': result['win_amount_sats'], # Return win amount in Satoshis
            'winning_lines': result['winning_lines'],
            'bonus_triggered': result['bonus_triggered'],
            'bonus_active': result['bonus_active'],
            'bonus_spins_remaining': result['bonus_spins_remaining'],
            'bonus_multiplier': result['bonus_multiplier'],
            'game_session': session_data,
            'user': user_data # Send updated user balance back
        }), 200

    except ValueError as ve: # Catch specific validation errors from spin_handler
        db.session.rollback()
        logger.warning(f"Spin validation error for user {user.id}: {str(ve)}. Path: {request.path}")
        return jsonify({'status': False, 'status_message': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error during spin for user {user.id}, session {game_session.id}: {str(e)}. Path: {request.path}", exc_info=True)
        return jsonify({
            'status': False,
            'status_message': 'An internal error occurred while processing your spin.'
        }), 500


# === User Account ===
@app.route('/api/withdraw', methods=['POST'])
@jwt_required()
def withdraw():
    data = request.get_json()
    # Note: WithdrawSchema still uses Float, needs update if we enforce Sats in API
    # For now, assume frontend sends BTC float, convert to Sats here.
    # It's better if frontend sends Sats (integer) directly.
    # Let's update WithdrawSchema to expect integer 'amount_sats'.
    errors = WithdrawSchema().validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400

    user = current_user
    amount_sats = data['amount_sats'] # Expecting integer amount in satoshis
    withdraw_address = data['withdraw_wallet_address'] # Keep address validation basic for now

    if not isinstance(amount_sats, int) or amount_sats <= 0:
         logger.warning(f"Invalid withdrawal amount by user {user.id}: {amount_sats}. Path: {request.path}")
         return jsonify({'status': False, 'status_message': 'Invalid withdrawal amount. Must be a positive integer (satoshis).'}), 400

    if user.balance < amount_sats:
        logger.warning(f"Withdrawal failed for user {user.id}: Insufficient funds (Balance: {user.balance}, Requested: {amount_sats}). Path: {request.path}")
        return jsonify({'status': False, 'status_message': 'Insufficient funds'}), 400

    try:
        # Deduct from balance immediately, mark transaction as pending
        user.balance -= amount_sats

        transaction = Transaction(
            user_id=user.id,
            amount=amount_sats, # Store amount in Satoshis
            transaction_type='withdraw',
            status='pending', # Admin needs to process this
            details={'withdraw_address': withdraw_address} # Store address in details JSON
        )
        db.session.add(transaction)
        db.session.commit()

        logger.info(f"Withdrawal request created for user {user.id}: {amount_sats} sats to {withdraw_address}. Tx ID: {transaction.id}. Path: {request.path}")

        # Return updated user data along with transaction ID
        user_data = UserSchema().dump(user)
        return jsonify({
            'status': True,
            'withdraw_id': transaction.id,
            'user': user_data, # Send updated balance back
            'status_message': 'Withdrawal request submitted successfully. It will be processed shortly.'
            }), 201 # Use 201 Created

    except Exception as e:
        db.session.rollback()
        logger.error(f"Withdrawal failed for user {user.id}: {str(e)}. Path: {request.path}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Withdrawal request failed due to an internal error.'}), 500

@app.route('/api/settings', methods=['POST'])
@jwt_required()
def update_settings():
    data = request.get_json()
    errors = UpdateSettingsSchema().validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400

    user = current_user

    try:
        # Check if email is changing and if it's already taken
        if 'email' in data and data['email'] != user.email:
            if User.query.filter(User.email == data['email'], User.id != user.id).first():
                return jsonify({'status': False, 'status_message': 'Email address is already in use.'}), 409
            user.email = data['email']

        # Check if password is being updated
        if 'password' in data and data['password']: # Ensure password is not empty
             # Add password complexity validation if needed here or in schema
            user.password = User.hash_password(data['password'])

        db.session.commit()
        user_data = UserSchema().dump(user)
        logger.info(f"Settings updated for user {user.id}")
        return jsonify({'status': True, 'user': user_data}), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Settings update failed for user {user.id}: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to update settings due to an internal error.'}), 500


@app.route('/api/deposit', methods=['POST'])
@jwt_required()
def deposit():
    # This endpoint might be primarily for applying bonus codes during a deposit process.
    # Actual deposit crediting should happen via a separate mechanism watching the deposit wallets.
    # For now, it only handles bonus codes.
    data = request.get_json()
    errors = DepositSchema().validate(data) # Validate presence of bonus_code if provided
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400

    user = current_user
    bonus_value_sats = 0 # Renamed from bonus_applied_amount and initialized

    if 'bonus_code' in data and data['bonus_code']:
        bonus_code_str = data['bonus_code'].strip().upper() # Normalize code
        bonus_code = BonusCode.query.filter_by(code_id=bonus_code_str, is_active=True).first()

        if bonus_code:
            # TODO: Add logic here to check if user already redeemed this code, expiry, usage limits etc.
            # Example:
            # existing_tx = Transaction.query.filter_by(user_id=user.id, details={"bonus_code_id": bonus_code.id}).first()
            # if existing_tx:
            #     logger.warning(f"Bonus code '{bonus_code_str}' already used by user {user.id}.")
            #     return jsonify({'status': False, 'status_message': 'Bonus code already used.'}), 400
            # if bonus_code.expires_at and bonus_code.expires_at < datetime.now(timezone.utc):
            #     logger.warning(f"Bonus code '{bonus_code_str}' expired.")
            #     return jsonify({'status': False, 'status_message': 'Bonus code expired.'}), 400
            # if bonus_code.uses_remaining is not None and bonus_code.uses_remaining <= 0:
            #     logger.warning(f"Bonus code '{bonus_code_str}' has no uses remaining.")
            #     return jsonify({'status': False, 'status_message': 'Bonus code has no uses remaining.'}), 400

            try:
                if bonus_code.subtype == 'percentage':
                    # Percentage bonuses require a deposit amount to calculate against.
                    # This endpoint currently doesn't handle actual deposit amounts.
                    logger.warning(f"Percentage bonus code '{bonus_code_str}' (ID: {bonus_code.id}) used by user {user.id}, but this endpoint doesn't process deposit amounts. Bonus not applied.")
                    bonus_value_sats = 0
                    # To implement fully:
                    # deposit_amount_sats = data.get('deposit_amount_sats') # Requires schema update
                    # if not deposit_amount_sats or deposit_amount_sats <= 0:
                    #     return jsonify({'status': False, 'status_message': 'Deposit amount required for percentage bonus.'}), 400
                    # bonus_value_sats = int(deposit_amount_sats * (bonus_code.amount / 100.0))

                elif bonus_code.subtype == 'fixed':
                    if bonus_code.amount_sats is not None and bonus_code.amount_sats > 0:
                        bonus_value_sats = int(bonus_code.amount_sats)
                    else:
                        logger.error(f"Fixed bonus code '{bonus_code_str}' (ID: {bonus_code.id}) has invalid amount_sats: {bonus_code.amount_sats}")
                        bonus_value_sats = 0


                elif bonus_code.subtype == 'spins':
                    logger.warning(f"'spins' subtype bonus code '{bonus_code_str}' (ID: {bonus_code.id}) used at deposit endpoint by user {user.id}. Monetary value not applied here.")
                    bonus_value_sats = 0
                    # Logic for awarding free spins should be handled elsewhere (e.g., game entry, specific bonus claim endpoint)

                else:
                     logger.error(f"Unknown bonus subtype '{bonus_code.subtype}' for code {bonus_code_str} (ID: {bonus_code.id})")
                     return jsonify({'status': False, 'status_message': 'Invalid bonus code type.'}), 400

                if bonus_value_sats > 0:
                    user.balance += bonus_value_sats

                    # Create a transaction record for the bonus
                    bonus_transaction = Transaction(
                        user_id=user.id,
                        amount=bonus_value_sats,
                        transaction_type='bonus', # Or 'deposit_bonus'
                        status='completed',
                        details={
                            'bonus_code_id': bonus_code.id,
                            'bonus_code': bonus_code.code_id,
                            'description': f"Bonus applied: {bonus_code.description or bonus_code.code_id}"
                        }
                    )
                    db.session.add(bonus_transaction)

                    # Update bonus code usage if applicable
                    if bonus_code.uses_remaining is not None:
                        bonus_code.uses_remaining = max(0, bonus_code.uses_remaining - 1)

                    db.session.commit()
                    logger.info(f"Bonus code '{bonus_code_str}' (ID: {bonus_code.id}) applied for user {user.id}. Value: {bonus_value_sats} sats. New balance: {user.balance}")
                elif bonus_code.subtype != 'percentage' and bonus_code.subtype != 'spins': # Don't log warning if value is 0 due to placeholder logic
                    logger.warning(f"Calculated bonus value is zero or negative for code {bonus_code_str} (ID: {bonus_code.id}), user {user.id}. Subtype: {bonus_code.subtype}")

            except Exception as e:
                db.session.rollback()
                logger.error(f"Error applying bonus code '{bonus_code_str}' (ID: {bonus_code.id}) for user {user.id}: {str(e)}", exc_info=True)
                return jsonify({'status': False, 'status_message': 'Failed to apply bonus code due to an internal error.'}), 500
        else:
            logger.warning(f"Invalid or inactive bonus code '{bonus_code_str}' attempted by user {user.id}.")
            return jsonify({'status': False, 'status_message': 'Invalid or expired bonus code'}), 400

    # Return updated user data, even if no bonus was applied
    user_data = UserSchema().dump(user)
    message = f"Bonus of {bonus_value_sats} sats applied." if bonus_value_sats > 0 else "No monetary bonus applied."
    if 'bonus_code' in data and data['bonus_code'] and bonus_value_sats == 0:
        # Provide more specific feedback if a code was entered but resulted in 0 value based on new logic
        bonus_code_obj = BonusCode.query.filter_by(code_id=data['bonus_code'].strip().upper()).first()
        if bonus_code_obj:
            if bonus_code_obj.subtype == 'percentage':
                message = "Percentage bonus code not applied: this endpoint requires deposit amount context."
            elif bonus_code_obj.subtype == 'spins':
                message = "Spins bonus code not applicable for direct monetary value here."
            elif bonus_code_obj.subtype == 'fixed' and (bonus_code_obj.amount_sats is None or bonus_code_obj.amount_sats <= 0):
                 message = "Fixed bonus code has an invalid or zero amount."


    return jsonify({'status': True, 'user': user_data, 'status_message': message, 'bonus_applied_sats': bonus_value_sats}), 200

# === Public Info ===
@app.route('/api/slots', methods=['GET'])
def get_slots():
    try:
        # Preload related symbols and bets for efficiency if needed, though maybe not for listing.
        # Eager loading can be done with options(joinedload(Slot.symbols), joinedload(Slot.bets))
        slots = Slot.query.order_by(Slot.id).all()
        # Use exclude=('symbols', 'bets') if you don't want nested data in the list view
        result = SlotSchema(many=True).dump(slots)
        return jsonify({'status': True, 'slots': result}), 200
    except Exception as e:
        logger.error(f"Failed to retrieve slots list: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Could not retrieve slot information.'}), 500

@app.route('/api/tables', methods=['GET'])
def get_tables():
    try:
        # Get all active blackjack tables
        tables = BlackjackTable.query.filter_by(is_active=True).order_by(BlackjackTable.id).all()
        result = BlackjackTableSchema(many=True).dump(tables)
        return jsonify({'status': True, 'tables': result}), 200
    except Exception as e:
        logger.error(f"Failed to retrieve tables list: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Could not retrieve table information.'}), 500

# === Blackjack Endpoints ===
@app.route('/api/join_blackjack', methods=['POST'])
@jwt_required()
def join_blackjack():
    data = request.get_json()
    errors = JoinBlackjackSchema().validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400

    table_id = data['table_id']
    bet_amount = data['bet_amount']

    # Get the table
    table = BlackjackTable.query.get(table_id)
    if not table:
        return jsonify({'status': False, 'status_message': f'Table with ID {table_id} not found'}), 404

    # Check if the table is active
    if not table.is_active:
        return jsonify({'status': False, 'status_message': f'Table with ID {table_id} is not active'}), 400

    try:
        # Handle joining the blackjack game
        result = handle_join_blackjack(current_user, table, bet_amount)

        # Get updated user data
        user_data = UserSchema().dump(current_user)

        logger.info(f"User {current_user.id} joined blackjack table {table_id} with bet {bet_amount}")

        return jsonify({
            'status': True,
            'hand': result,
            'user': user_data
        }), 201
    except ValueError as ve:
        logger.warning(f"Join blackjack validation error for user {current_user.id}: {str(ve)}")
        return jsonify({'status': False, 'status_message': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error joining blackjack for user {current_user.id}, table {table_id}: {str(e)}", exc_info=True)
        return jsonify({
            'status': False,
            'status_message': 'An internal error occurred while joining the blackjack game.'
        }), 500

@app.route('/api/blackjack_action', methods=['POST'])
@jwt_required()
def blackjack_action():
    data = request.get_json()
    errors = BlackjackActionRequestSchema().validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400

    hand_id = data['hand_id']
    action_type = data['action_type']
    hand_index = data.get('hand_index', 0)

    try:
        # Handle the blackjack action
        result = handle_blackjack_action(current_user, hand_id, action_type, hand_index)

        # Get updated user data
        user_data = UserSchema().dump(current_user)

        logger.info(f"User {current_user.id} performed {action_type} on hand {hand_id}, index {hand_index}")

        return jsonify({
            'status': True,
            'action_result': result,
            'user': user_data
        }), 200
    except ValueError as ve:
        logger.warning(f"Blackjack action validation error for user {current_user.id}: {str(ve)}")
        return jsonify({'status': False, 'status_message': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error processing blackjack action for user {current_user.id}, hand {hand_id}: {str(e)}", exc_info=True)
        return jsonify({
            'status': False,
            'status_message': 'An internal error occurred while processing your blackjack action.'
        }), 500

# === Admin Routes ===
@app.route('/api/admin/dashboard', methods=['GET'])
@jwt_required()
def admin_dashboard():
    if not is_admin():
        logger.warning(f"Non-admin user {current_user.id if current_user else 'Unknown'} attempted to access admin dashboard. Path: {request.path}")
        return jsonify({'status': False, 'status_message': 'Access denied: Administrator privileges required.'}), 403
    try:
        logger.info(f"Admin dashboard accessed by user: {current_user.username} (ID: {current_user.id}). Path: {request.path}")
        total_users = db.session.query(User.id).count()
        total_sessions = db.session.query(GameSession.id).count()
        total_transactions = db.session.query(Transaction.id).count()
        pending_withdrawals = db.session.query(Transaction.id).filter_by(status='pending', transaction_type='withdraw').count()
        total_bonus_codes = db.session.query(BonusCode.id).count()
        active_bonus_codes = db.session.query(BonusCode.id).filter_by(is_active=True).count()
        total_balance_sats = db.session.query(db.func.sum(User.balance)).scalar() or 0
        dashboard_data = {
            'total_users': total_users,
            'total_sessions': total_sessions,
            'total_transactions': total_transactions,
            'pending_withdrawals': pending_withdrawals,
            'total_bonus_codes': total_bonus_codes,
            'active_bonus_codes': active_bonus_codes,
            'total_balance_sats': total_balance_sats
        }
        return jsonify({'status': True, 'dashboard_data': dashboard_data}), 200

    except Exception as e:
        logger.error(f"Admin dashboard data retrieval failed for user {current_user.username} (ID: {current_user.id}): {str(e)}. Path: {request.path}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to retrieve admin dashboard data.'}), 500

# --- Admin User Management ---
@app.route('/api/admin/users', methods=['GET'])
@jwt_required()
def admin_get_users():
    if not is_admin(): return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        users_paginated = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        result = UserListSchema().dump(users_paginated) # Use the pagination schema
        return jsonify({'status': True, 'users': result}), 200
    except Exception as e:
        logger.error(f"Admin get users failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to retrieve users.'}), 500

@app.route('/api/admin/users/<int:user_id>', methods=['GET'])
@jwt_required()
def admin_get_user(user_id):
    if not is_admin(): return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    try:
        user = User.query.get_or_404(user_id)
        result = AdminUserSchema().dump(user) # Use more detailed admin schema
        return jsonify({'status': True, 'user': result}), 200
    except Exception as e:
        logger.error(f"Admin get user {user_id} failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to retrieve user details.'}), 500

@app.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@jwt_required()
def admin_update_user(user_id):
    if not is_admin(): return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    # Use a specific schema for admin updates if needed, or reuse UpdateSettingsSchema carefully
    # For now, allow updating email, is_active, is_admin. Password reset separate?
    schema = AdminUserSchema(partial=True, exclude=('password', 'deposit_wallet_private_key', 'deposit_wallet_address', 'balance')) # Exclude fields admin shouldn't directly set here
    errors = schema.validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400

    try:
        # Check email uniqueness if changed
        if 'email' in data and data['email'] != user.email:
            if User.query.filter(User.email == data['email'], User.id != user_id).first():
                return jsonify({'status': False, 'status_message': 'Email address is already in use.'}), 409

        # Update allowed fields
        for key, value in data.items():
            if hasattr(user, key) and key not in ['password', 'balance', 'deposit_wallet_address', 'deposit_wallet_private_key']: # Prevent direct update of sensitive fields
                setattr(user, key, value)

        db.session.commit()
        logger.info(f"Admin {current_user.id} updated user {user_id}")
        return jsonify({'status': True, 'user': AdminUserSchema().dump(user)}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Admin update user {user_id} failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to update user.'}), 500

# Consider adding DELETE user route (soft delete recommended)

# --- Admin Transaction Management ---
@app.route('/api/admin/transactions', methods=['GET'])
@jwt_required()
def admin_get_transactions():
    if not is_admin(): return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        # Add filtering options (e.g., by user_id, type, status)
        query = Transaction.query.order_by(Transaction.created_at.desc())
        # Example filtering:
        user_id_filter = request.args.get('user_id', type=int)
        type_filter = request.args.get('type')
        status_filter = request.args.get('status')
        if user_id_filter:
            query = query.filter(Transaction.user_id == user_id_filter)
        if type_filter:
            query = query.filter(Transaction.transaction_type == type_filter)
        if status_filter:
            query = query.filter(Transaction.status == status_filter)

        transactions_paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        result = TransactionListSchema().dump(transactions_paginated)
        return jsonify({'status': True, 'transactions': result}), 200
    except Exception as e:
        logger.error(f"Admin get transactions failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to retrieve transactions.'}), 500

@app.route('/api/admin/transactions/<int:tx_id>', methods=['PUT'])
@jwt_required()
def admin_update_transaction(tx_id):
    if not is_admin(): return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    transaction = Transaction.query.get_or_404(tx_id)
    data = request.get_json()

    # Only allow updating specific fields, primarily status for withdrawals
    allowed_updates = ['status', 'details'] # Maybe add admin notes to details?
    update_data = {k: v for k, v in data.items() if k in allowed_updates}

    if not update_data:
        return jsonify({'status': False, 'status_message': 'No valid fields provided for update.'}), 400

    # Specific logic for withdrawal approval/rejection
    if transaction.transaction_type == 'withdraw' and 'status' in update_data:
        new_status = update_data['status']
        if transaction.status == 'pending' and new_status == 'completed':
            # Mark as completed (actual transfer happens externally)
            transaction.status = 'completed'
            # Add admin note to details?
            if 'admin_notes' in data:
                 transaction.details = {**transaction.details, 'admin_notes': data['admin_notes']}
            logger.info(f"Admin {current_user.id} approved withdrawal {tx_id}")
        elif transaction.status == 'pending' and new_status == 'rejected':
            # Reject withdrawal and refund user
            user = User.query.get(transaction.user_id)
            if user:
                user.balance += transaction.amount # Refund the amount
                transaction.status = 'rejected'
                # Add admin note to details?
                if 'admin_notes' in data:
                    transaction.details = {**transaction.details, 'admin_notes': data['admin_notes']}
                logger.info(f"Admin {current_user.id} rejected withdrawal {tx_id}, refunded {transaction.amount} to user {user.id}")
            else:
                 logger.error(f"Cannot reject withdrawal {tx_id}: User {transaction.user_id} not found.")
                 return jsonify({'status': False, 'status_message': 'User not found for refund.'}), 500
        elif transaction.status != 'pending':
             return jsonify({'status': False, 'status_message': f'Cannot change status of already processed withdrawal ({transaction.status}).'}), 400
        else:
             return jsonify({'status': False, 'status_message': f'Invalid status transition for withdrawal: {new_status}'}), 400

    elif 'status' in update_data: # For other transaction types, maybe just allow notes?
         return jsonify({'status': False, 'status_message': 'Status update not allowed for this transaction type.'}), 400

    # Update details if provided
    if 'details' in update_data and isinstance(update_data['details'], dict):
         transaction.details = {**transaction.details, **update_data['details']} # Merge new details

    try:
        db.session.commit()
        return jsonify({'status': True, 'transaction': TransactionSchema().dump(transaction)}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Admin update transaction {tx_id} failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to update transaction.'}), 500


# --- Admin Bonus Code Management ---
@app.route('/api/admin/bonus_codes', methods=['GET'])
@jwt_required()
def admin_get_bonus_codes():
    if not is_admin(): return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        codes_paginated = BonusCode.query.order_by(BonusCode.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        result = BonusCodeListSchema().dump(codes_paginated)
        return jsonify({'status': True, 'bonus_codes': result}), 200
    except Exception as e:
        logger.error(f"Admin get bonus codes failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to retrieve bonus codes.'}), 500

@app.route('/api/admin/bonus_codes', methods=['POST'])
@jwt_required()
def admin_create_bonus_code():
    if not is_admin(): return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    data = request.get_json()
    # Pass context to schema for uniqueness check
    schema = BonusCodeSchema(context={'check_unique': True})
    errors = schema.validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400

    try:
        new_code = schema.load(data, session=db.session) # Load data into model instance
        db.session.add(new_code)
        db.session.commit()
        logger.info(f"Admin {current_user.id} created bonus code {new_code.code_id}")
        return jsonify({'status': True, 'bonus_code': BonusCodeSchema().dump(new_code)}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Admin create bonus code failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to create bonus code.'}), 500

@app.route('/api/admin/bonus_codes/<int:code_id>', methods=['PUT'])
@jwt_required()
def admin_update_bonus_code(code_id):
    if not is_admin(): return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    bonus_code = BonusCode.query.get_or_404(code_id)
    data = request.get_json()
    # Exclude code_id from update schema
    schema = BonusCodeSchema(partial=True, exclude=('code_id',))
    errors = schema.validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400

    try:
        # Load updates onto the existing instance
        updated_code = schema.load(data, instance=bonus_code, session=db.session, partial=True)
        db.session.commit()
        logger.info(f"Admin {current_user.id} updated bonus code {updated_code.code_id}")
        return jsonify({'status': True, 'bonus_code': BonusCodeSchema().dump(updated_code)}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Admin update bonus code {code_id} failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to update bonus code.'}), 500

@app.route('/api/admin/bonus_codes/<int:code_id>', methods=['DELETE'])
@jwt_required()
def admin_delete_bonus_code(code_id):
    if not is_admin(): return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    bonus_code = BonusCode.query.get_or_404(code_id)
    try:
        # Soft delete might be better: bonus_code.is_active = False
        db.session.delete(bonus_code)
        db.session.commit()
        logger.info(f"Admin {current_user.id} deleted bonus code {code_id} ({bonus_code.code_id})")
        return jsonify({'status': True, 'status_message': 'Bonus code deleted successfully.'}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Admin delete bonus code {code_id} failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to delete bonus code.'}), 500

# --- Admin Balance Transfer ---
@app.route('/api/admin/balance_transfer', methods=['POST'])
@jwt_required()
def admin_balance_transfer():
    if not is_admin(): return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    data = request.get_json()
    errors = BalanceTransferSchema().validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400

    from_user_id = data.get('from_user_id') # Can be None for system adjustments
    to_user_id = data['to_user_id']
    amount_sats = data['amount_sats']
    description = data.get('description', 'Admin balance transfer')
    tx_type = data.get('transaction_type', 'transfer')

    # Validate users
    to_user = User.query.get(to_user_id)
    if not to_user:
        return jsonify({'status': False, 'status_message': f'Destination user ID {to_user_id} not found.'}), 404

    from_user = None
    if from_user_id:
        from_user = User.query.get(from_user_id)
        if not from_user:
            return jsonify({'status': False, 'status_message': f'Source user ID {from_user_id} not found.'}), 404
        # Check source balance if debiting from a user
        if amount_sats > 0 and from_user.balance < amount_sats:
             return jsonify({'status': False, 'status_message': f'Source user {from_user_id} has insufficient balance ({from_user.balance} sats).'}), 400

    try:
        # Perform the transfer
        if from_user:
            from_user.balance -= amount_sats
        to_user.balance += amount_sats

        # Create transaction records
        # Debit from source (if applicable)
        if from_user:
            debit_tx = Transaction(
                user_id=from_user_id,
                amount=-amount_sats,
                transaction_type=tx_type,
                status='completed',
                details={'description': description, 'transfer_to': to_user_id, 'admin_id': current_user.id}
            )
            db.session.add(debit_tx)

        # Credit to destination
        credit_tx = Transaction(
            user_id=to_user_id,
            amount=amount_sats,
            transaction_type=tx_type,
            status='completed',
            details={'description': description, 'transfer_from': from_user_id, 'admin_id': current_user.id}
        )
        db.session.add(credit_tx)

        db.session.commit()
        logger.info(f"Admin {current_user.id} transferred {amount_sats} sats from user {from_user_id or 'system'} to user {to_user_id}")
        return jsonify({
            'status': True,
            'status_message': 'Balance transfer successful.',
            'to_user_balance': to_user.balance,
            'from_user_balance': from_user.balance if from_user else None
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Admin balance transfer failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Balance transfer failed.'}), 500

@app.route('/api/admin/credit_deposit', methods=['POST'])
@jwt_required()
def admin_credit_deposit():
    if not is_admin():
        return jsonify({'status': False, 'status_message': 'Access denied: Administrator privileges required.'}), 403

    data = request.get_json()
    schema = AdminCreditDepositSchema()
    errors = schema.validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400

    user_id = data['user_id']
    amount_sats = data['amount_sats']
    external_tx_id = data.get('external_tx_id')
    admin_notes = data.get('admin_notes')

    user = User.query.get(user_id)
    if not user:
        return jsonify({'status': False, 'status_message': f'User with ID {user_id} not found.'}), 404

    try:
        user.balance += amount_sats

        transaction_details = {
            'credited_by_admin_id': current_user.id,
            'credited_by_admin_username': current_user.username
        }
        if external_tx_id:
            transaction_details['external_tx_id'] = external_tx_id
        if admin_notes:
            transaction_details['admin_notes'] = admin_notes

        deposit_tx = Transaction(
            user_id=user.id,
            amount=amount_sats,
            transaction_type='deposit', # Or 'admin_credit_deposit' for more specificity
            status='completed',
            details=transaction_details
        )
        db.session.add(deposit_tx)
        db.session.commit()

        logger.info(f"Admin {current_user.username} credited {amount_sats} sats to user {user.username} (ID: {user.id}). External TX: {external_tx_id or 'N/A'}")

        return jsonify({
            'status': True,
            'status_message': 'Deposit credited successfully.',
            'user_id': user.id,
            'new_balance_sats': user.balance,
            'transaction_id': deposit_tx.id
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Admin credit deposit failed for user {user_id} by admin {current_user.username}: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to credit deposit due to an internal error.'}), 500


# --- Main Execution ---
if __name__ == '__main__':
    # Consider using Flask CLI for running in development: flask run
    # This block is useful for direct execution (python app.py)
    app.run(debug=app.config.get('DEBUG', False), host='0.0.0.0', port=5000)

# --- CLI Commands (Registered with Flask App) ---
@app.cli.command("db_cleanup_expired_tokens")
def db_cleanup_expired_tokens_command():
    """Cleans up expired tokens from the TokenBlacklist table."""
    now = datetime.now(timezone.utc)
    try:
        expired_tokens = TokenBlacklist.query.filter(TokenBlacklist.expires_at < now).all()
        if not expired_tokens:
            print("No expired tokens found to clean up.")
            return

        count = len(expired_tokens)
        for token in expired_tokens:
            db.session.delete(token)

        db.session.commit()
        print(f"Successfully deleted {count} expired token(s).")
    except Exception as e:
        db.session.rollback()
        print(f"Error during token cleanup: {str(e)}")