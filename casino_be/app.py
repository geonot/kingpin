from flask import Flask, request, jsonify, Blueprint
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
from .models import (
    db, User, GameSession, Transaction, BonusCode, Slot, SlotSymbol, SlotBet, TokenBlacklist,
    BlackjackTable, BlackjackHand, BlackjackAction, UserBonus,
    SpacecrashGame, SpacecrashBet,  # Spacecrash models
    PokerTable, PokerHand, PokerPlayerState,  # Poker models
    PlinkoDropLog, RouletteGame,  # Plinko models, added RouletteGame
    BaccaratTable, BaccaratHand, BaccaratAction # Baccarat models
)
from .schemas import (
    UserSchema, RegisterSchema, LoginSchema, GameSessionSchema, SpinSchema, SpinRequestSchema,
    WithdrawSchema, UpdateSettingsSchema, DepositSchema, SlotSchema, JoinGameSchema,
    BonusCodeSchema, AdminUserSchema, TransactionSchema, UserListSchema, BonusCodeListSchema, TransactionListSchema,
    BalanceTransferSchema, BlackjackTableSchema, BlackjackHandSchema, JoinBlackjackSchema, BlackjackActionRequestSchema,
    AdminCreditDepositSchema, UserBonusSchema,
    SpacecrashBetSchema, SpacecrashGameSchema, SpacecrashGameHistorySchema, SpacecrashPlayerBetSchema,  # Spacecrash schemas
    PokerTableSchema, PokerPlayerStateSchema, PokerHandSchema, JoinPokerTableSchema, PokerActionSchema,  # Poker schemas
    PlinkoPlayRequestSchema, PlinkoPlayResponseSchema,  # Plinko schemas
    # Baccarat schemas will be defined below for now, or imported if moved to a separate file
    BaccaratTableSchema, BaccaratHandSchema, PlaceBaccaratBetSchema, BaccaratActionSchema # Actual Baccarat Schemas
)
from .utils.bitcoin import generate_bitcoin_wallet
from .utils.spin_handler import handle_spin
from .utils.multiway_helper import handle_multiway_spin
from .utils.blackjack_helper import handle_join_blackjack, handle_blackjack_action
from .utils import spacecrash_handler
from .utils import poker_helper
from .utils import roulette_helper # Import the new helper
from .utils.plinko_helper import validate_plinko_params, calculate_winnings, STAKE_CONFIG, PAYOUT_MULTIPLIERS
from .utils import baccarat_helper
from .config import Config
from sqlalchemy.orm import joinedload # Added for poker join logic
from decimal import Decimal
from .services.bonus_service import apply_bonus_to_deposit
from http import HTTPStatus

# --- App Initialization ---
app = Flask(__name__)
app.config.from_object(Config)

# --- Rate Limiter Setup ---
app.config['RATELIMIT_STORAGE_URI'] = Config.RATELIMIT_STORAGE_URI if hasattr(Config, 'RATELIMIT_STORAGE_URI') else 'memory://'
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    # storage_uri will be set via app.config later if needed
)
if not app.config.get('RATELIMIT_STORAGE_URI'):
    app.config['RATELIMIT_STORAGE_URI'] = 'memory://' # Default if not in Config
limiter.init_app(app)

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

# --- Blueprint Imports ---
from .routes.auth import auth_bp
from .routes.user import user_bp
from .routes.admin import admin_bp
from .routes.slots import slots_bp
from .routes.blackjack import blackjack_bp
from .routes.poker import poker_bp
from .routes.plinko import plinko_bp
from .routes.roulette import roulette_bp
from .routes.spacecrash import spacecrash_bp
from .routes.meta_game import meta_game_bp
from .routes.baccarat import baccarat_bp # New Baccarat import

# --- API Routes ---

# === Game Play ===
# spin() has been moved to slots_bp
# @app.route('/api/spin', methods=['POST'])
# @jwt_required()
# def spin():
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

# === Public Info ===

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

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(user_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(slots_bp)
app.register_blueprint(blackjack_bp)
app.register_blueprint(poker_bp)
app.register_blueprint(plinko_bp)
app.register_blueprint(roulette_bp)
app.register_blueprint(spacecrash_bp)
app.register_blueprint(meta_game_bp)
app.register_blueprint(baccarat_bp) # Consolidated baccarat registration
