from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import (
    JWTManager, create_access_token, create_refresh_token, jwt_required,
    get_jwt_identity, get_jti, current_user
)
from datetime import datetime, timedelta, timezone
import logging
from marshmallow import ValidationError

# Import all models - combining Spacecrash, Poker, and Plinko models
from models import (
    db, User, GameSession, Transaction, BonusCode, Slot, SlotSymbol, SlotBet, TokenBlacklist,
    BlackjackTable, BlackjackHand, BlackjackAction, UserBonus,
    SpacecrashGame, SpacecrashBet,  # Spacecrash models
    PokerTable, PokerHand, PokerPlayerState,  # Poker models
    PlinkoDropLog  # Plinko models
)
from schemas import (
    UserSchema, RegisterSchema, LoginSchema, GameSessionSchema, SpinSchema, SpinRequestSchema,
    WithdrawSchema, UpdateSettingsSchema, DepositSchema, SlotSchema, JoinGameSchema,
    BonusCodeSchema, AdminUserSchema, TransactionSchema, UserListSchema, BonusCodeListSchema, TransactionListSchema,
    BalanceTransferSchema, BlackjackTableSchema, BlackjackHandSchema, JoinBlackjackSchema, BlackjackActionRequestSchema,
    AdminCreditDepositSchema, UserBonusSchema,
    SpacecrashBetSchema, SpacecrashGameSchema, SpacecrashGameHistorySchema, SpacecrashPlayerBetSchema,  # Spacecrash schemas
    PokerTableSchema, PokerPlayerStateSchema, PokerHandSchema, JoinPokerTableSchema, PokerActionSchema,  # Poker schemas
    PlinkoPlayRequestSchema, PlinkoPlayResponseSchema  # Plinko schemas
)
from utils.bitcoin import generate_bitcoin_wallet
from utils.spin_handler import handle_spin
from utils.multiway_helper import handle_multiway_spin
from utils.blackjack_helper import handle_join_blackjack, handle_blackjack_action
from utils import spacecrash_handler
from utils import poker_helper
from utils.plinko_helper import validate_plinko_params, calculate_winnings, STAKE_CONFIG, PAYOUT_MULTIPLIERS
from config import Config
from services.bonus_service import apply_bonus_to_deposit
from http import HTTPStatus

# Add the missing SATOSHIS_PER_UNIT constant that was referenced in Plinko code
SATOSHIS_PER_UNIT = 100000000  # 1 BTC = 100,000,000 satoshis

# --- App Initialization ---
app = Flask(__name__)
app.config.from_object(Config)

# --- Rate Limiter Setup ---
app.config['RATELIMIT_STORAGE_URI'] = Config.RATELIMIT_STORAGE_URI if hasattr(Config, 'RATELIMIT_STORAGE_URI') else 'memory://'
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# --- Database Setup ---
db.init_app(app)
migrate = Migrate(app, db, directory='casino_be/migrations')

# --- JWT Setup ---
jwt = JWTManager(app)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
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
    logger.error("Unhandled exception caught by global error handler:", exc_info=True)
    return jsonify({
        'status': False,
        'status_message': 'An unexpected internal server error occurred. Please try again later.'
    }), 500

# --- Response Security Headers ---
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none';"
    if request.is_secure and not app.debug:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# --- Helper Functions ---
def is_admin():
    return current_user and current_user.is_admin

# --- API Routes ---

# === Authentication ===
@app.route('/api/me', methods=['GET'])
@jwt_required()
def get_current_user():
    try:
        user_data = UserSchema().dump(current_user)
        logger.info(f"User profile fetched: {current_user.username} (ID: {current_user.id})")
        return jsonify({'status': True, 'user': user_data}), 200
    except Exception as e:
        logger.error(f"Error fetching user profile: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to fetch user profile.'}), 500

@app.route('/api/register', methods=['POST'])
@limiter.limit("10 per hour")
def register():
    data = request.get_json()
    errors = RegisterSchema().validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'status': False, 'status_message': 'Username already exists'}), 409
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'status': False, 'status_message': 'Email already exists'}), 409
    try:
        wallet_address = generate_bitcoin_wallet()
        if not wallet_address:
            return jsonify({'status': False, 'status_message': 'Failed to generate wallet address for user.'}), 500
        new_user = User(
            username=data['username'],
            email=data['email'],
            password=User.hash_password(data['password']),
            deposit_wallet_address=wallet_address
        )
        db.session.add(new_user)
        db.session.commit()
        access_token = create_access_token(identity=new_user)
        refresh_token = create_refresh_token(identity=new_user)
        user_data = UserSchema().dump(new_user)
        logger.info(f"User registered: {new_user.username} (ID: {new_user.id})")
        return jsonify({
            'status': True, 'user': user_data,
            'access_token': access_token, 'refresh_token': refresh_token
        }), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Registration failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Registration failed.'}), 500

@app.route('/api/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    data = request.get_json()
    schema = LoginSchema()
    try:
        validated_data = schema.load(data)
    except ValidationError as err:
        return jsonify({'status': False, 'status_message': err.messages}), 400

    user = User.query.filter_by(username=validated_data['username']).first()
    if not user or not User.verify_password(user.password, validated_data['password']):
        return jsonify({'status': False, 'status_message': 'Invalid credentials.'}), 401

    # Update last login time
    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()

    # Generate tokens
    access_token = create_access_token(identity=user)
    refresh_token = create_refresh_token(identity=user)
    user_data = UserSchema().dump(user)
    logger.info(f"User logged in: {user.username} (ID: {user.id})")
    return jsonify({
        'status': True, 'user': user_data,
        'access_token': access_token, 'refresh_token': refresh_token
    }), 200

@app.route('/api/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    new_access_token = create_access_token(identity=current_user)
    logger.info(f"Token refreshed for user: {current_user.username} (ID: {current_user.id})")
    return jsonify({'status': True, 'access_token': new_access_token}), 200

@app.route('/api/logout', methods=['POST'])
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
        logger.info(f"User logged out: {current_user.username} (ID: {current_user.id})")
        return jsonify({"status": True, "status_message": "Successfully logged out"}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Logout failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Logout failed.'}), 500

@app.route('/api/logout2', methods=['POST'])
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
        logger.info(f"User refresh token invalidated: {current_user.username} (ID: {current_user.id})")
        return jsonify({"status": True, "status_message": "Refresh token invalidated"}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Refresh token invalidation failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Refresh token invalidation failed.'}), 500

# === Game Play ===
@app.route('/api/end_session', methods=['POST'])
@jwt_required()
def end_session():
    user_id = current_user.id
    now = datetime.now(timezone.utc)
    try:
        active_sessions = GameSession.query.filter_by(user_id=user_id, session_end=None).all()
        if not active_sessions:
            return jsonify({'status': True, 'status_message': 'No active session to end'}), 200
        for session in active_sessions:
            session.session_end = now
        db.session.commit()
        logger.info(f"Ended active sessions for user {user_id}")
        return jsonify({'status': True, 'status_message': 'Session ended successfully'}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to end session: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to end session.'}), 500

@app.route('/api/join', methods=['POST'])
@jwt_required()
def join_game():
    data = request.get_json()
    errors = JoinGameSchema().validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400
    game_type = data.get('game_type')
    slot_id = None
    table_id = None
    if game_type == 'blackjack':
        return jsonify({
            'status': False,
            'status_message': 'For blackjack games, please use the /api/join_blackjack endpoint.',
            'use_endpoint': '/api/join_blackjack'
        }), 400
    elif game_type == 'slot':
        slot_id_from_request = data.get('slot_id')
        if slot_id_from_request is None:
            return jsonify({'status': False, 'status_message': 'slot_id is required for slot games'}), 400
        slot = Slot.query.get(slot_id_from_request)
        if not slot:
            return jsonify({'status': False, 'status_message': f'Slot with ID {slot_id_from_request} not found'}), 404
        slot_id = slot_id_from_request
        table_id = None
    else:
        return jsonify({'status': False, 'status_message': f'Invalid game type: {game_type}'}), 400
    user_id = current_user.id
    now = datetime.now(timezone.utc)
    try:
        active_sessions = GameSession.query.filter_by(user_id=user_id, session_end=None).all()
        for session in active_sessions:
            session.session_end = now
        new_session = GameSession(user_id=user_id, slot_id=slot_id, table_id=table_id, game_type=game_type, session_start=now)
        db.session.add(new_session)
        db.session.commit()
        logger.info(f"User {user_id} joined {game_type} game, session {new_session.id} created.")
        return jsonify({'status': True, 'game_session': GameSessionSchema().dump(new_session), 'session_id': new_session.id}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Join game failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to join game.'}), 500

@app.route('/api/spin', methods=['POST'])
@jwt_required()
def spin():
    data = request.get_json()
    errors = SpinRequestSchema().validate(data)
    if errors: 
        return jsonify({'status': False, 'status_message': errors}), 400
    user = current_user
    bet_amount_sats = data['bet_amount']
    if not isinstance(bet_amount_sats, int) or bet_amount_sats <= 0:
        return jsonify({'status': False, 'status_message': 'Invalid bet amount.'}), 400
    game_session = GameSession.query.filter_by(user_id=user.id, session_end=None).order_by(GameSession.session_start.desc()).first()
    if not game_session:
        return jsonify({'status': False, 'status_message': 'No active game session.'}), 404
    slot = Slot.query.get(game_session.slot_id)
    if not slot:
         return jsonify({'status': False, 'status_message': 'Slot not found for session.'}), 500
    if user.balance < bet_amount_sats and not (game_session.bonus_active and game_session.bonus_spins_remaining > 0):
        return jsonify({'status': False, 'status_message': 'Insufficient balance'}), 400
    
    spin_result_data = None
    try:
        if slot.is_multiway:
            if not slot.reel_configurations:
                logger.error(f"Spin attempt on multiway slot {slot.id} without reel_configurations by user {user.id}")
                return jsonify({"status": False, "status_message": "Slot is configured as multiway but lacks essential reel configurations."}), 400
            
            if not slot.symbols:
                 logger.error(f"Spin attempt on multiway slot {slot.id} without slot.symbols loaded by user {user.id}")
                 return jsonify({"status": False, "status_message": "Slot configuration incomplete (symbols missing)."}), 400

            spin_result_data = handle_multiway_spin(user, slot, game_session, bet_amount_sats)
        else:
            spin_result_data = handle_spin(user, slot, game_session, bet_amount_sats)
        
        db.session.commit()

        return jsonify({
            'status': True, 
            'result': spin_result_data['spin_result'],
            'win_amount': spin_result_data['win_amount_sats'],
            'winning_lines': spin_result_data['winning_lines'],
            'bonus_triggered': spin_result_data['bonus_triggered'],
            'bonus_active': spin_result_data['bonus_active'], 
            'bonus_spins_remaining': spin_result_data['bonus_spins_remaining'],
            'bonus_multiplier': spin_result_data['bonus_multiplier'], 
            'game_session': GameSessionSchema().dump(game_session),
            'user': UserSchema().dump(user)
        }), 200
    except ValueError as ve:
        db.session.rollback()
        logger.warning(f"Spin ValueError for user {user.id} on slot {slot.id if slot else 'N/A'}: {str(ve)}")
        return jsonify({'status': False, 'status_message': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Spin error: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Spin processing error.'}), 500

# === User Account ===
@app.route('/api/withdraw', methods=['POST'])
@limiter.limit("5 per hour")
@jwt_required()
def withdraw():
    data = request.get_json()
    errors = WithdrawSchema().validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400
    user = current_user
    amount_sats = data['amount_sats']
    withdraw_address = data['withdraw_wallet_address']
    if not isinstance(amount_sats, int) or amount_sats <= 0:
         return jsonify({'status': False, 'status_message': 'Invalid withdrawal amount.'}), 400

    active_bonus_with_wagering = UserBonus.query.filter_by(
        user_id=user.id,
        is_active=True,
        is_completed=False,
        is_cancelled=False
    ).first()

    if active_bonus_with_wagering:
        if active_bonus_with_wagering.wagering_progress_sats < active_bonus_with_wagering.wagering_requirement_sats:
            remaining_wagering_sats = active_bonus_with_wagering.wagering_requirement_sats - active_bonus_with_wagering.wagering_progress_sats
            logger.warning(f"User {user.id} withdrawal blocked due to unmet wagering for UserBonus {active_bonus_with_wagering.id}.")
            return jsonify({
                'status': False,
                'status_message': f"Withdrawal blocked. You have an active bonus with unmet wagering requirements. "
                                  f"Remaining wagering needed: {remaining_wagering_sats} sats. "
                                  f"Bonus amount: {active_bonus_with_wagering.bonus_amount_awarded_sats} sats. "
                                  f"Wagering progress: {active_bonus_with_wagering.wagering_progress_sats}/{active_bonus_with_wagering.wagering_requirement_sats} sats."
            }), 403

    if user.balance < amount_sats:
        return jsonify({'status': False, 'status_message': 'Insufficient funds'}), 400
    try:
        user.balance -= amount_sats
        transaction = Transaction(
            user_id=user.id, amount=amount_sats, transaction_type='withdraw',
            status='pending', details={'withdraw_address': withdraw_address}
        )
        db.session.add(transaction)
        db.session.commit()
        logger.info(f"Withdrawal request for user {user.id}: {amount_sats} sats to {withdraw_address}. Tx ID: {transaction.id}")
        return jsonify({
            'status': True, 'withdraw_id': transaction.id, 'user': UserSchema().dump(user),
            'status_message': 'Withdrawal request submitted.'
        ), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Withdrawal failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Withdrawal failed.'}), 500

@app.route('/api/settings', methods=['POST'])
@jwt_required()
def update_settings():
    data = request.get_json()
    errors = UpdateSettingsSchema().validate(data)
    if errors: 
        return jsonify({'status': False, 'status_message': errors}), 400
    user = current_user
    try:
        if 'email' in data and data['email'] != user.email:
            if User.query.filter(User.email == data['email'], User.id != user.id).first():
                return jsonify({'status': False, 'status_message': 'Email already in use.'}), 409
            user.email = data['email']
        if 'password' in data and data['password']:
            user.password = User.hash_password(data['password'])
        db.session.commit()
        logger.info(f"Settings updated for user {user.id}")
        return jsonify({'status': True, 'user': UserSchema().dump(user)}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Settings update failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Settings update failed.'}), 500

@app.route('/api/deposit', methods=['POST'])
@jwt_required()
def deposit():
    data = request.get_json()
    errors = DepositSchema().validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400

    user = current_user
    deposit_amount_sats = data['deposit_amount_sats']
    bonus_code_str = data.get('bonus_code')

    final_bonus_applied_sats = 0
    final_user_bonus_id = None
    deposit_message = f"Deposit of {deposit_amount_sats} sats successful."
    bonus_message = ""
    status_code = 200

    try:
        # 1. Credit user's balance
        user.balance += deposit_amount_sats

        # 2. Create a deposit transaction
        deposit_transaction = Transaction(
            user_id=user.id,
            amount=deposit_amount_sats,
            transaction_type='deposit',
            status='completed',
            details={'description': f'User deposit of {deposit_amount_sats} sats via /api/deposit endpoint'}
        )
        db.session.add(deposit_transaction)
        logger.info(f"User {user.id} deposited {deposit_amount_sats} sats. Transaction ID: {deposit_transaction.id}")

        # 3. Apply bonus if a bonus code is provided
        if bonus_code_str:
            bonus_result = apply_bonus_to_deposit(user, bonus_code_str, deposit_amount_sats)

            if bonus_result['success']:
                final_bonus_applied_sats = bonus_result.get('bonus_value_sats', 0)
                final_user_bonus_id = bonus_result.get('user_bonus_id')
                bonus_message = bonus_result['message']
            else:
                bonus_message = f"Bonus application failed: {bonus_result['message']}"

        db.session.commit()

        combined_message = deposit_message
        if bonus_message:
            combined_message += f" {bonus_message}"

        user_data = UserSchema().dump(user)
        return jsonify({
            'status': True,
            'user': user_data,
            'status_message': combined_message.strip(),
            'deposit_sats': deposit_amount_sats,
            'bonus_applied_sats': final_bonus_applied_sats,
            'user_bonus_id': final_user_bonus_id
        }), status_code

    except Exception as e:
        db.session.rollback()
        logger.error(f"Deposit processing for user {user.id} failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Deposit processing failed due to an internal error.'}), 500

# === Public Info ===
@app.route('/api/slots', methods=['GET'])
def get_slots():
    try:
        slots = Slot.query.order_by(Slot.id).all()
        result = SlotSchema(many=True).dump(slots)
        return jsonify({'status': True, 'slots': result}), 200
    except Exception as e:
        logger.error(f"Failed to retrieve slots list: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Could not retrieve slot information.'}), 500

@app.route('/api/tables', methods=['GET'])
def get_tables():
    try:
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
    table = BlackjackTable.query.get(table_id)
    if not table:
        return jsonify({'status': False, 'status_message': f'Table with ID {table_id} not found'}), 404
    if not table.is_active:
        return jsonify({'status': False, 'status_message': f'Table with ID {table_id} is not active'}), 400
    try:
        result = handle_join_blackjack(current_user, table, bet_amount)
        user_data = UserSchema().dump(current_user)
        logger.info(f"User {current_user.id} joined blackjack table {table_id} with bet {bet_amount}")
        return jsonify({'status': True, 'hand': result, 'user': user_data }), 201
    except ValueError as ve:
        return jsonify({'status': False, 'status_message': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error joining blackjack: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Error joining blackjack game.'}), 500

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
        result = handle_blackjack_action(current_user, hand_id, action_type, hand_index)
        user_data = UserSchema().dump(current_user)
        logger.info(f"User {current_user.id} action {action_type} on hand {hand_id}")
        return jsonify({'status': True, 'action_result': result, 'user': user_data }), 200
    except ValueError as ve:
        return jsonify({'status': False, 'status_message': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in blackjack action: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Error in blackjack action.'}), 500


# === Plinko Endpoint ===
@app.route('/api/plinko/play', methods=['POST'])
@jwt_required()
@limiter.limit("120 per minute") # Example: Allow 2 drops per second per user on average
def plinko_play():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user:
        logger.error(f"Plinko play attempt by non-existent user ID: {current_user_id}")
        return jsonify({'error': 'User not found after authentication.'}), HTTPStatus.INTERNAL_SERVER_ERROR

    try:
        json_data = request.get_json()
        if not json_data:
            return jsonify({'error': 'Invalid JSON payload.'}), HTTPStatus.BAD_REQUEST
        
        schema = PlinkoPlayRequestSchema()
        loaded_data = schema.load(json_data)
    except Exception as e:
        logger.warning(f"Plinko play validation error for user {current_user_id}: {str(e)}")
        error_messages = e.messages if hasattr(e, 'messages') else str(e)
        return jsonify({'error': 'Validation failed', 'messages': error_messages}), HTTPStatus.BAD_REQUEST

    stake_amount_float = loaded_data['stake_amount'] # This is in main unit (e.g., BTC)
    chosen_stake_label = loaded_data['chosen_stake_label']
    slot_landed_label = loaded_data['slot_landed_label']

    validation_result = validate_plinko_params(stake_amount_float, chosen_stake_label, slot_landed_label)
    if not validation_result['success']:
        logger.warning(f"Plinko parameter validation failed for user {user.id}: {validation_result['error']}")
        return jsonify(PlinkoPlayResponseSchema().dump({
            'success': False,
            'error': validation_result['error']
        })), HTTPStatus.BAD_REQUEST

    stake_amount_sats = int(stake_amount_float * SATOSHIS_PER_UNIT)
    
    # Ensure user.balance is treated as satoshis (BigInteger)
    if user.balance < stake_amount_sats:
        logger.warning(f"User {user.id} insufficient funds for Plinko: Balance {user.balance} sats, Stake {stake_amount_sats} sats")
        return jsonify(PlinkoPlayResponseSchema().dump({
            'success': False,
            'error': 'Insufficient funds',
            'new_balance': float(user.balance) / SATOSHIS_PER_UNIT 
        })), HTTPStatus.BAD_REQUEST

    try:
        multiplier = PAYOUT_MULTIPLIERS.get(slot_landed_label)
        if multiplier is None:
            logger.error(f"Invalid slot_landed_label '{slot_landed_label}' made it past validation for user {user.id}.")
            return jsonify(PlinkoPlayResponseSchema().dump({
                'success': False, 'error': 'Internal error: Invalid slot outcome.'
            })), HTTPStatus.INTERNAL_SERVER_ERROR

        # 1. Create PlinkoDropLog entry (winnings_amount will be updated later)
        plinko_log = PlinkoDropLog(
            user_id=current_user_id,
            stake_amount=stake_amount_sats,
            chosen_stake_label=chosen_stake_label,
            slot_landed_label=slot_landed_label,
            multiplier_applied=multiplier,
            winnings_amount=0 # Placeholder, updated after calculation
        )
        db.session.add(plinko_log)
        db.session.flush() # To get plinko_log.id for FK in transactions

        # 2. Debit stake
        user.balance -= stake_amount_sats
        bet_transaction = Transaction(
            user_id=user.id, 
            amount=-stake_amount_sats, 
            transaction_type='plinko_bet', 
            status='completed', 
            details={'description': f'Plinko bet: {chosen_stake_label}, Landed: {slot_landed_label}'},
            plinko_drop_id=plinko_log.id # Link to PlinkoDropLog
        )
        db.session.add(bet_transaction)
        
        # 3. Calculate winnings (in satoshis)
        winnings_sats = calculate_winnings(stake_amount_sats, slot_landed_label)
        
        # 4. Update PlinkoDropLog with actual winnings
        plinko_log.winnings_amount = winnings_sats
        
        # 5. Credit winnings (if any)
        if winnings_sats > 0:
            user.balance += winnings_sats
            win_transaction = Transaction(
                user_id=user.id, 
                amount=winnings_sats, 
                transaction_type='plinko_win', 
                status='completed', 
                details={'description': f'Plinko win. Stake: {stake_amount_float}, Landed: {slot_landed_label}'},
                plinko_drop_id=plinko_log.id # Link to PlinkoDropLog
            )
            db.session.add(win_transaction)

        db.session.commit()
        
        # Convert amounts back to main unit for API response
        winnings_float = float(winnings_sats) / SATOSHIS_PER_UNIT
        new_balance_float = float(user.balance) / SATOSHIS_PER_UNIT

        logger.info(f"Plinko play successful for user {user.id}: Bet {stake_amount_float}, Won {winnings_float}. New balance: {new_balance_float}")
        
        response_data = {
            'success': True,
            'winnings': winnings_float,
            'new_balance': new_balance_float,
            'message': f"Bet {stake_amount_float} on {chosen_stake_label}, landed on {slot_landed_label}. Won {winnings_float}."
        }
        return jsonify(PlinkoPlayResponseSchema().dump(response_data)), HTTPStatus.OK

    except Exception as e:
        db.session.rollback()
        logger.error(f"Plinko play processing error for user {user.id}: {str(e)}", exc_info=True)
        return jsonify(PlinkoPlayResponseSchema().dump({
            'success': False,
            'error': 'An internal error occurred during game processing.'
        })), HTTPStatus.INTERNAL_SERVER_ERROR


# === Admin Routes ===
@app.route('/api/admin/dashboard', methods=['GET'])
@jwt_required()
def admin_dashboard():
    if not is_admin():
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    try:
        total_users = db.session.query(User.id).count()
        total_sessions = db.session.query(GameSession.id).count()
        total_transactions = db.session.query(Transaction.id).count()
        pending_withdrawals = db.session.query(Transaction.id).filter_by(status='pending', transaction_type='withdraw').count()
        total_bonus_codes = db.session.query(BonusCode.id).count()
        active_bonus_codes = db.session.query(BonusCode.id).filter_by(is_active=True).count()
        total_balance_sats = db.session.query(db.func.sum(User.balance)).scalar() or 0
        dashboard_data = {
            'total_users': total_users, 'total_sessions': total_sessions,
            'total_transactions': total_transactions, 'pending_withdrawals': pending_withdrawals,
            'total_bonus_codes': total_bonus_codes, 'active_bonus_codes': active_bonus_codes,
            'total_balance_sats': total_balance_sats
        }
        return jsonify({'status': True, 'dashboard_data': dashboard_data}), 200
    except Exception as e:
        logger.error(f"Admin dashboard error: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to retrieve admin dashboard data.'}), 500

@app.route('/api/admin/users', methods=['GET'])
@jwt_required()
def admin_get_users():
    if not is_admin(): 
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        users_paginated = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        return jsonify({'status': True, 'users': UserListSchema().dump(users_paginated)}), 200
    except Exception as e:
        logger.error(f"Admin get users failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to retrieve users.'}), 500

@app.route('/api/admin/users/<int:user_id>', methods=['GET'])
@jwt_required()
def admin_get_user(user_id):
    if not is_admin(): 
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    try:
        user = User.query.get_or_404(user_id)
        return jsonify({'status': True, 'user': AdminUserSchema().dump(user)}), 200
    except Exception as e:
        logger.error(f"Admin get user {user_id} failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to retrieve user details.'}), 500

@app.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@jwt_required()
def admin_update_user(user_id):
    if not is_admin(): 
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    schema = AdminUserSchema(partial=True, exclude=('password', 'deposit_wallet_private_key', 'deposit_wallet_address', 'balance'))
    errors = schema.validate(data)
    if errors: 
        return jsonify({'status': False, 'status_message': errors}), 400
    try:
        if 'email' in data and data['email'] != user.email:
            if User.query.filter(User.email == data['email'], User.id != user_id).first():
                return jsonify({'status': False, 'status_message': 'Email already in use.'}), 409
        for key, value in data.items():
            if hasattr(user, key) and key not in ['password', 'balance', 'deposit_wallet_address', 'deposit_wallet_private_key']:
                setattr(user, key, value)
        db.session.commit()
        logger.info(f"Admin {current_user.id} updated user {user_id}")
        return jsonify({'status': True, 'user': AdminUserSchema().dump(user)}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Admin update user {user_id} failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to update user.'}), 500

@app.route('/api/admin/transactions', methods=['GET'])
@jwt_required()
def admin_get_transactions():
    if not is_admin(): 
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        query = Transaction.query.order_by(Transaction.created_at.desc())
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
        return jsonify({'status': True, 'transactions': TransactionListSchema().dump(transactions_paginated)}), 200
    except Exception as e:
        logger.error(f"Admin get transactions failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to retrieve transactions.'}), 500

@app.route('/api/admin/transactions/<int:tx_id>', methods=['PUT'])
@jwt_required()
def admin_update_transaction(tx_id):
    if not is_admin(): 
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    transaction = Transaction.query.get_or_404(tx_id)
    data = request.get_json()
    allowed_updates = ['status', 'details']
    update_data = {k: v for k, v in data.items() if k in allowed_updates}
    if not update_data:
        return jsonify({'status': False, 'status_message': 'No valid fields for update.'}), 400
    if transaction.transaction_type == 'withdraw' and 'status' in update_data:
        new_status = update_data['status']
        if transaction.status == 'pending' and new_status == 'completed':
            transaction.status = 'completed'
            if 'admin_notes' in data: 
                transaction.details = {**transaction.details, 'admin_notes': data['admin_notes']}
            logger.info(f"Admin {current_user.id} approved withdrawal {tx_id}")
        elif transaction.status == 'pending' and new_status == 'rejected':
            user = User.query.get(transaction.user_id)
            if user:
                user.balance += transaction.amount
                transaction.status = 'rejected'
                if 'admin_notes' in data: 
                    transaction.details = {**transaction.details, 'admin_notes': data['admin_notes']}
                logger.info(f"Admin {current_user.id} rejected withdrawal {tx_id}, refunded {transaction.amount} to user {user.id}")
            else:
                 return jsonify({'status': False, 'status_message': 'User not found for refund.'}), 500
        elif transaction.status != 'pending':
             return jsonify({'status': False, 'status_message': 'Cannot change status of processed withdrawal.'}), 400
        else:
             return jsonify({'status': False, 'status_message': 'Invalid status transition for withdrawal.'}), 400
    elif 'status' in update_data:
         return jsonify({'status': False, 'status_message': 'Status update not allowed for this type.'}), 400
    if 'details' in update_data and isinstance(update_data['details'], dict):
         transaction.details = {**transaction.details, **update_data['details']}
    try:
        db.session.commit()
        return jsonify({'status': True, 'transaction': TransactionSchema().dump(transaction)}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Admin update transaction {tx_id} failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to update transaction.'}), 500

@app.route('/api/admin/credit_deposit', methods=['POST'])
@jwt_required()
def admin_credit_deposit():
    if not is_admin():
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403
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
        return jsonify({'status': False, 'status_message': f'User {user_id} not found.'}), 404
    try:
        user.balance += amount_sats
        transaction_details = {'credited_by_admin_id': current_user.id, 'credited_by_admin_username': current_user.username}
        if external_tx_id: 
            transaction_details['external_tx_id'] = external_tx_id
        if admin_notes: 
            transaction_details['admin_notes'] = admin_notes
        deposit_tx = Transaction(user_id=user.id, amount=amount_sats, transaction_type='deposit', status='completed', details=transaction_details)
        db.session.add(deposit_tx)
        db.session.commit()
        logger.info(f"Admin {current_user.username} credited {amount_sats} to user {user.username} (ID: {user.id})")
        return jsonify({'status': True, 'status_message': 'Deposit credited.', 'user_id': user.id, 'new_balance_sats': user.balance, 'transaction_id': deposit_tx.id}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Admin credit deposit failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to credit deposit.'}), 500

@app.route('/api/admin/bonus_codes', methods=['GET'])
@jwt_required()
def admin_get_bonus_codes():
    if not is_admin(): 
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        codes_paginated = BonusCode.query.order_by(BonusCode.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        return jsonify({'status': True, 'bonus_codes': BonusCodeListSchema().dump(codes_paginated)}), 200
    except Exception as e:
        logger.error(f"Admin get bonus codes failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to retrieve bonus codes.'}), 500

@app.route('/api/admin/bonus_codes', methods=['POST'])
@jwt_required()
def admin_create_bonus_code():
    if not is_admin(): 
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    data = request.get_json()
    schema = BonusCodeSchema(context={'check_unique': True})
    errors = schema.validate(data)
    if errors: 
        return jsonify({'status': False, 'status_message': errors}), 400
    try:
        new_code = schema.load(data, session=db.session)
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
    if not is_admin(): 
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    bonus_code = BonusCode.query.get_or_404(code_id)
    data = request.get_json()
    schema = BonusCodeSchema(partial=True, exclude=('code_id',))
    errors = schema.validate(data)
    if errors: 
        return jsonify({'status': False, 'status_message': errors}), 400
    try:
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
    if not is_admin(): 
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    bonus_code = BonusCode.query.get_or_404(code_id)
    try:
        db.session.delete(bonus_code)
        db.session.commit()
        logger.info(f"Admin {current_user.id} deleted bonus code {code_id}")
        return jsonify({'status': True, 'status_message': 'Bonus code deleted.'}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Admin delete bonus code {code_id} failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to delete bonus code.'}), 500

# CLI command for cleanup
@app.cli.command('cleanup-expired-tokens')
def db_cleanup_expired_tokens_command():
    now = datetime.now(timezone.utc)
    try:
        count = db.session.query(TokenBlacklist).filter(TokenBlacklist.expires_at < now).count()
        db.session.query(TokenBlacklist).filter(TokenBlacklist.expires_at < now).delete()
        db.session.commit()
        print(f"Successfully deleted {count} expired token(s).")
    except Exception as e:
        db.session.rollback()
        print(f"Error during token cleanup: {str(e)}")

# === Spacecrash Game Endpoints ===

@app.route('/api/spacecrash/bet', methods=['POST'])
@jwt_required()
@limiter.limit("30 per minute")
def spacecrash_place_bet():
    data = request.get_json()
    schema = SpacecrashBetSchema()
    try:
        validated_data = schema.load(data)
    except ValidationError as err:
        return jsonify({'status': False, 'status_message': err.messages}), 400

    user = current_user
    bet_amount = validated_data['bet_amount']
    auto_eject_at = validated_data.get('auto_eject_at')

    if user.balance < bet_amount:
        return jsonify({'status': False, 'status_message': 'Insufficient balance.'}), 400

    current_game = SpacecrashGame.query.filter_by(status='betting').order_by(SpacecrashGame.created_at.desc()).first()

    if not current_game:
        return jsonify({'status': False, 'status_message': 'No active game accepting bets at the moment.'}), 404

    existing_bet = SpacecrashBet.query.filter_by(user_id=user.id, game_id=current_game.id).first()
    if existing_bet:
        return jsonify({'status': False, 'status_message': 'You have already placed a bet for this game.'}), 400
        
    try:
        new_bet = SpacecrashBet(
            user_id=user.id,
            game_id=current_game.id,
            bet_amount=bet_amount,
            auto_eject_at=auto_eject_at,
            status='placed'
        )
        user.balance -= bet_amount
        
        db.session.add(new_bet)
        db.session.commit()
        
        bet_dump_schema = SpacecrashPlayerBetSchema()
        logger.info(f"User {user.id} placed Spacecrash bet {new_bet.id} for {bet_amount} on game {current_game.id}")
        return jsonify({'status': True, 'status_message': 'Bet placed successfully.', 'bet': bet_dump_schema.dump(new_bet)}), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error placing Spacecrash bet for user {user.id}: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to place bet due to an internal error.'}), 500


@app.route('/api/spacecrash/eject', methods=['POST'])
@jwt_required()
def spacecrash_eject_bet():
    user = current_user

    active_bet = SpacecrashBet.query.join(SpacecrashGame).filter(
        SpacecrashBet.user_id == user.id,
        SpacecrashGame.status == 'in_progress',
        SpacecrashBet.status == 'placed'
    ).first()

    if not active_bet:
        return jsonify({'status': False, 'status_message': 'No active bet to eject or game is not in progress.'}), 404

    if active_bet.game.status != 'in_progress':
        return jsonify({'status': False, 'status_message': 'Game is no longer in progress.'}), 400

    current_multiplier = spacecrash_handler.get_current_multiplier(active_bet.game)

    if active_bet.game.crash_point is None:
        logger.error(f"CRITICAL: Game {active_bet.game.id} is in_progress but crash_point is None during eject attempt by user {user.id}.")
        return jsonify({'status': False, 'status_message': 'Cannot process eject: game data inconsistent.'}), 500

    if current_multiplier >= active_bet.game.crash_point:
        active_bet.status = 'busted'
        active_bet.ejected_at = active_bet.game.crash_point
        active_bet.win_amount = 0
        message = 'Eject failed, game crashed before or at your eject point.'
        status_code = 400
        logger.info(f"User {user.id} busted Spacecrash bet {active_bet.id}. Attempted eject at {current_multiplier}x, crash was at {active_bet.game.crash_point}x.")
    else:
        active_bet.ejected_at = current_multiplier
        active_bet.win_amount = int(active_bet.bet_amount * active_bet.ejected_at)
        active_bet.status = 'ejected'
        user.balance += active_bet.win_amount
        message = 'Successfully ejected.'
        status_code = 200
        logger.info(f"User {user.id} ejected Spacecrash bet {active_bet.id} at {active_bet.ejected_at}x, won {active_bet.win_amount}")

    try:
        db.session.commit()
        
        bet_dump_schema = SpacecrashPlayerBetSchema()
        return jsonify({
            'status': True, 
            'status_message': 'Successfully ejected.', 
            'ejected_at': active_bet.ejected_at,
            'win_amount': active_bet.win_amount,
            'bet': bet_dump_schema.dump(active_bet)
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error ejecting Spacecrash bet for user {user.id}: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to eject bet due to an internal error.'}), 500

@app.route('/api/spacecrash/current_game', methods=['GET'])
def spacecrash_current_game_state():
    game = SpacecrashGame.query.filter(
        SpacecrashGame.status.in_(['in_progress', 'betting'])
    ).order_by(
        db.case(
            (SpacecrashGame.status == 'in_progress', 0),
            (SpacecrashGame.status == 'betting', 1),
            else_=2
        ),
        SpacecrashGame.created_at.desc()
    ).first()

    if not game:
        game = SpacecrashGame.query.filter_by(status='completed').order_by(SpacecrashGame.game_end_time.desc()).first()
        if not game:
            return jsonify({'status': False, 'status_message': 'No current or recent game found.'}), 404

    game_data = SpacecrashGameSchema().dump(game)
    
    if game.status == 'in_progress' and game.game_start_time:
        game_data['current_multiplier'] = spacecrash_handler.get_current_multiplier(game)
    elif game.status == 'betting':
        game_data['current_multiplier'] = 1.0
    elif game.status == 'completed':
        game_data['current_multiplier'] = game.crash_point

    bets_query = SpacecrashBet.query.filter_by(game_id=game.id).all()
    game_data['player_bets'] = SpacecrashPlayerBetSchema(many=True).dump(bets_query)

    return jsonify({'status': True, 'game': game_data}), 200


@app.route('/api/spacecrash/history', methods=['GET'])
def spacecrash_game_history():
    recent_games = SpacecrashGame.query.filter_by(status='completed').order_by(SpacecrashGame.game_end_time.desc()).limit(20).all()
    
    if not recent_games:
        return jsonify({'status': True, 'history': []}), 200

    history_data = SpacecrashGameHistorySchema(many=True).dump(recent_games)
    return jsonify({'status': True, 'history': history_data}), 200


@app.route('/api/spacecrash/admin/next_phase', methods=['POST'])
@jwt_required()
@limiter.limit("10 per minute")
def spacecrash_admin_next_phase():
    if not is_admin():
        return jsonify({'status': False, 'status_message': 'Access denied. Admin rights required.'}), 403

    data = request.get_json()
    game_id = data.get('game_id')
    target_phase = data.get('target_phase')
    client_seed_param = data.get('client_seed', 'default_client_seed_for_testing_123')
    nonce_param = data.get('nonce', 1)

    game = None
    if game_id:
        game = SpacecrashGame.query.get(game_id)
    else:
        if target_phase == 'betting':
            game = SpacecrashGame.query.filter_by(status='pending').order_by(SpacecrashGame.created_at.desc()).first()
            if not game:
                game = spacecrash_handler.create_new_game()
                db.session.add(game)
        elif target_phase == 'in_progress':
            game = SpacecrashGame.query.filter_by(status='betting').order_by(SpacecrashGame.created_at.desc()).first()
        elif target_phase == 'completed':
            game = SpacecrashGame.query.filter_by(status='in_progress').order_by(SpacecrashGame.created_at.desc()).first()

    if not game:
        return jsonify({'status': False, 'status_message': f'No suitable game found to transition for ID {game_id or "any"}.'}), 404

    original_status = game.status
    success = False
    message = f"Game {game.id} already in {game.status} state or invalid transition."

    try:
        if target_phase == 'betting':
            if game.status == 'pending':
                success = spacecrash_handler.start_betting_phase(game)
                message = f"Game {game.id} moved to betting phase." if success else f"Failed to move game {game.id} to betting."
            elif game.status == 'completed' or game.status == 'cancelled':
                new_game_instance = spacecrash_handler.create_new_game()
                db.session.add(new_game_instance)
                db.session.flush()
                success = spacecrash_handler.start_betting_phase(new_game_instance)
                if success:
                    game = new_game_instance
                    message = f"New game {game.id} created and moved to betting phase."
                else:
                    message = "Failed to create and move new game to betting phase."

        elif target_phase == 'in_progress':
            if game.status == 'betting':
                if not game.client_seed:
                    game.client_seed = client_seed_param 
                
                success = spacecrash_handler.start_game_round(game, game.client_seed or client_seed_param, nonce_param)
                message = f"Game {game.id} started (in progress). Crash point: {game.crash_point}" if success else f"Failed to start game {game.id}."
        
        elif target_phase == 'completed':
            if game.status == 'in_progress':
                success = spacecrash_handler.end_game_round(game)
                message = f"Game {game.id} ended. Final crash point: {game.crash_point}" if success else f"Failed to end game {game.id}."
        
        else:
            return jsonify({'status': False, 'status_message': f'Invalid target phase: {target_phase}.'}), 400

        if success:
            db.session.commit()
            logger.info(f"Admin {current_user.id} transitioned Spacecrash game {game.id} from {original_status} to {target_phase}.")
            return jsonify({'status': True, 'status_message': message, 'game_state': SpacecrashGameSchema().dump(game)}), 200
        else:
            return jsonify({'status': False, 'status_message': message, 'current_status': original_status}), 400

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error transitioning Spacecrash game {game.id} to {target_phase} by admin {current_user.id}: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to transition game phase due to an internal error.'}), 500