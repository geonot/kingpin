from flask import Flask, request, jsonify, Blueprint, current_app, g
import uuid
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
from pythonjsonlogger import jsonlogger
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

if not app.debug:
    # Configure JSON logging for production
    logger = app.logger
    handler = logging.StreamHandler()
    # Updated formatter to include request_id
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(levelname)s %(request_id)s %(module)s %(funcName)s %(lineno)d %(message)s'
    )
    handler.setFormatter(formatter)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# --- Request ID Generation ---
@app.before_request
def add_request_id():
    g.request_id = str(uuid.uuid4())

# --- Rate Limiter Setup ---
app.config['RATELIMIT_STORAGE_URI'] = Config.RATELIMIT_STORAGE_URI if hasattr(Config, 'RATELIMIT_STORAGE_URI') else 'memory://'

if app.config.get("TESTING"):
    app.config['RATELIMIT_ENABLED'] = False
    app.config['RATELIMIT_DEFAULT_LIMITS_ENABLED'] = False # Disable default limits as well
    app.config['RATELIMIT_DEFAULT_LIMITS'] = "10000 per second" # Set a very high limit
else:
    app.config.setdefault('RATELIMIT_ENABLED', True)
    app.config.setdefault('RATELIMIT_DEFAULT_LIMITS_ENABLED', True)
    app.config.setdefault('RATELIMIT_DEFAULT_LIMITS', "200 per day;50 per hour")

limiter = Limiter(key_func=get_remote_address) # No app, no enabled, no defaults here
limiter.init_app(app) # Rely entirely on app.config values set above

# --- Database Setup ---
db.init_app(app)
migrate = Migrate(app, db, directory='casino_be/migrations')

# --- JWT Setup ---
jwt = JWTManager(app)

# --- JWT Helper Functions ---
@jwt.user_identity_loader
def user_identity_lookup(user):
    return user.id

@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    identity = jwt_data["sub"]
    user_obj = User.query.get(identity)
    return user_obj

@jwt.token_in_blocklist_loader
def check_if_token_in_blacklist(jwt_header, jwt_payload):
    jti = jwt_payload['jti']
    # now = datetime.now(timezone.utc) # Not needed for temporary bypass
    # token = db.session.query(TokenBlacklist.id).filter_by(jti=jti).scalar()
    print(f"DEBUG_APP: check_if_token_in_blacklist called for jti: {jti}. Returning False (token not blocklisted).")
    return False # Temporarily disable blocklist check

# --- Global Error Handler ---
@app.errorhandler(Exception)
def handle_unhandled_exception(e):
    current_app.logger.error(f"Request ID: {g.get('request_id', 'N/A')} - Unhandled exception caught by global error handler:", exc_info=True)
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

