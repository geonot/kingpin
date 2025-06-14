from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

from flask import Flask, request, jsonify, Blueprint, current_app, g
import uuid
import werkzeug.exceptions
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, create_refresh_token, jwt_required,
    get_jwt_identity, get_jti, current_user
)
from flask_jwt_extended.exceptions import NoAuthorizationError # For JWT specific errors
from sqlalchemy.exc import SQLAlchemyError # For database errors
from werkzeug.exceptions import HTTPException # For generic HTTP errors
from datetime import datetime, timedelta, timezone
import logging
from pythonjsonlogger import jsonlogger
from marshmallow import ValidationError

# Custom Logging Filter for Request ID
class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = g.get('request_id', 'N/A')
        return True

# Import all models - combining Spacecrash, Poker, and Plinko models
from models import (
    db, User, GameSession, Transaction, BonusCode, Slot, SlotSymbol, SlotBet, TokenBlacklist,
    BlackjackTable, BlackjackHand, BlackjackAction, UserBonus,
    SpacecrashGame, SpacecrashBet,  # Spacecrash models
    PokerTable, PokerHand, PokerPlayerState,  # Poker models
    PlinkoDropLog, RouletteGame,  # Plinko models, added RouletteGame
    BaccaratTable, BaccaratHand, BaccaratAction, # Baccarat models
    # Crystal Garden Models
    CrystalSeed, PlayerGarden, CrystalFlower, CrystalCodexEntry
)
from schemas import (
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
from utils.auth import register_jwt_handlers
from utils.bitcoin import generate_bitcoin_wallet
from utils.spin_handler import handle_spin
from utils.multiway_helper import handle_multiway_spin
from utils.blackjack_helper import handle_join_blackjack, handle_blackjack_action
from utils import spacecrash_handler
from utils import poker_helper
from utils import roulette_helper # Import the new helper
from utils.plinko_helper import validate_plinko_params, calculate_winnings, STAKE_CONFIG, PAYOUT_MULTIPLIERS
from utils import baccarat_helper
from config import Config
from sqlalchemy.orm import joinedload # Added for poker join logic
from decimal import Decimal
from services.bonus_service import apply_bonus_to_deposit
from http import HTTPStatus

def create_app(config_class=Config):
    """Application factory pattern."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # --- CORS Setup ---
    CORS(app, origins=["http://localhost:8080", "http://127.0.0.1:8080", "http://localhost:8082", "http://127.0.0.1:8082"], supports_credentials=True)

    if not app.debug:
        # Configure JSON logging for production
        logger = app.logger
        handler = logging.StreamHandler()
        # Updated formatter to include request_id
        formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(levelname)s %(request_id)s %(module)s %(funcName)s %(lineno)d %(message)s'
        )
        handler.setFormatter(formatter)
        # Add the custom filter to the handler
        request_id_filter = RequestIdFilter()
        handler.addFilter(request_id_filter)
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    # --- Request ID Generation ---
    @app.before_request
    def add_request_id():
        g.request_id = str(uuid.uuid4())

    # --- Rate Limiter Setup ---
    app.config['RATELIMIT_STORAGE_URI'] = config_class.RATELIMIT_STORAGE_URI if hasattr(config_class, 'RATELIMIT_STORAGE_URI') else 'memory://'

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
    migrate = Migrate(app, db, directory='migrations')

    # --- JWT Setup ---
    jwt = JWTManager(app)
    register_jwt_handlers(jwt)

    # --- Specific Error Handlers ---
    @app.errorhandler(ValidationError)
    def handle_validation_error(e):
        current_app.logger.warning(f"Validation error: {e.messages}")
        return jsonify({
            'status': False,
            'status_message': 'Input validation failed.',
            'errors': e.messages
        }), HTTPStatus.UNPROCESSABLE_ENTITY

    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(e):
        current_app.logger.error("Database error:", exc_info=True)
        return jsonify({
            'status': False,
            'status_message': 'A database error occurred. Please try again later.'
        }), HTTPStatus.INTERNAL_SERVER_ERROR

    @app.errorhandler(NoAuthorizationError)
    def handle_no_auth_error(e):
        current_app.logger.warning(f"Authorization error: {str(e)}")
        return jsonify({
            'status': False,
            'status_message': 'Missing or invalid authorization token.'
        }), HTTPStatus.UNAUTHORIZED

    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        current_app.logger.warning(f"HTTP exception: {e.code} - {e.name}: {e.description}")
        # Ensure response is JSON, using Flask's built-in way to get response from HTTPException
        response = e.get_response()
        # Override content type and set JSON body
        response.data = jsonify({
            'status': False,
            'status_message': e.name,
            'description': e.description
        }).data # .data gets the byte string from jsonify's Response object
        response.content_type = "application/json"
        return response

    # --- Global Error Handlers (catch-alls) ---
    @app.errorhandler(404) # Equivalent to werkzeug.exceptions.NotFound
    def handle_not_found(e):
        # This will be caught by handle_http_exception if not defined separately,
        # but having it separate allows for specific 404 logging or custom page if needed.
        # For JSON API, ensuring it goes through handle_http_exception for consistent format is good.
        # However, Flask prioritizes more specific handlers.
        # If handle_http_exception is defined, it will catch NotFound unless this specific one is here.
        current_app.logger.warning(f"404 Not Found: {request.url}") # Request ID will be added by the filter
        return jsonify({
            'status': False,
            'status_message': 'The requested resource was not found.'
        }), 404

    @app.errorhandler(Exception)
    def handle_unhandled_exception(e):
        # If it's an HTTPException, it should have been caught by handle_http_exception
        # or a more specific one like handle_not_found.
        # This check ensures that if an HTTPException (that isn't a standard one like 404, 500 if they have own handlers)
        # somehow reaches here, it gets processed by our JSON-formatting HTTPException handler.
        if isinstance(e, HTTPException):
            return handle_http_exception(e) # Ensure JSON response for all HTTP errors

        # For truly unhandled exceptions (not HTTPExceptions)
        current_app.logger.error("Unhandled exception caught by global error handler:", exc_info=True) # Request ID will be added by the filter
        return jsonify({
            'status': False,
            'status_message': 'An unexpected internal server error occurred. Please try again later.'
        }), HTTPStatus.INTERNAL_SERVER_ERROR

    # --- Response Security Headers ---
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; base-uri 'self';"
        if request.is_secure and not app.debug:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    # --- Blueprint Imports ---
    from routes.auth import auth_bp
    from routes.user import user_bp
    from routes.admin import admin_bp
    from routes.slots import slots_bp
    from routes.blackjack import blackjack_bp
    from routes.poker import poker_bp
    from routes.plinko import plinko_bp
    from routes.roulette import roulette_bp
    from routes.spacecrash import spacecrash_bp
    from routes.meta_game import meta_game_bp
    from routes.baccarat import baccarat_bp # New Baccarat import
    from routes.internal import internal_bp # New Internal import
    from casino_be.routes.crystal_garden import crystal_garden_bp # Crystal Garden import

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
    app.register_blueprint(internal_bp) # Register internal blueprint
    app.register_blueprint(crystal_garden_bp) # Register Crystal Garden blueprint

    return app

# Create the app instance for direct usage
app = create_app()

# Add main section to run the app
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

