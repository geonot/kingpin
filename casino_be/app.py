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
import click # For CLI commands
import re # For password validation

# Password validation function (moved from manage.py)
def is_password_strong(password):
    """Checks if the password meets complexity requirements."""
    if len(password) < 12:
        return False, "Password must be at least 12 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."
    if not re.search(r"[!@#$%^&*()-_=+[\]{}|;:'\",.<>/?]", password):
        return False, "Password must contain at least one special character (e.g., !@#$%^&*)."
    return True, ""

def create_app(config_class=Config):
    """Application factory pattern."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # --- Logger Setup (early, so it's available for config warnings) ---
    if not app.debug:
        # Configure JSON logging for production
        logger = app.logger # Get Flask's default logger
        handler = logging.StreamHandler()
        formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(levelname)s %(request_id)s %(module)s %(funcName)s %(lineno)d %(message)s'
        )
        handler.setFormatter(formatter)
        request_id_filter = RequestIdFilter() # Defined below or ensure it's defined before this point
        handler.addFilter(request_id_filter)
        if logger.hasHandlers():
            logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    else:
        # Basic logging for debug mode if not already configured
        if not app.logger.handlers: # Avoid adding handlers if already configured by Flask/extensions
            logging.basicConfig(level=logging.DEBUG)

    # --- Request ID Generation (needs to be before logging request_id) ---
    @app.before_request
    def add_request_id():
        g.request_id = str(uuid.uuid4())

    # --- Production Warnings ---
    log_production_warnings(app)

    # --- CORS Setup ---
    default_cors_origins = ["http://localhost:8080", "http://127.0.0.1:8080", "http://localhost:8082", "http://127.0.0.1:8082"]
    cors_allowed_origins_env = os.getenv('CORS_ALLOWED_ORIGINS')

    if cors_allowed_origins_env:
        cors_origins = [origin.strip() for origin in cors_allowed_origins_env.split(',')]
    else:
        cors_origins = default_cors_origins
        if not app.debug: # FLASK_DEBUG is called app.debug in Flask
            app.logger.warning(
                "CORS_ALLOWED_ORIGINS environment variable not set. "
                f"Defaulting to {default_cors_origins}. This is insecure for production."
            )
    CORS(app, origins=cors_origins, supports_credentials=True)


    # --- Rate Limiter Setup ---
    # Ensure RATELIMIT_STORAGE_URI is taken from app.config, which was loaded from config_class
    # No need to access config_class directly here if it's already in app.config
    # app.config['RATELIMIT_STORAGE_URI'] will be used by Flask-Limiter

    # The following logic seems to be fine, Flask-Limiter will use app.config['RATELIMIT_STORAGE_URI']
    # which is set from config_class by app.config.from_object(config_class)
    # Ensure RATELIMIT_STORAGE_URI is correctly referenced from app.config if needed by Limiter setup.
    # Limiter setup below seems to correctly use app.config.

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

        default_csp = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; base-uri 'self';"
        csp_header_value = os.getenv('CONTENT_SECURITY_POLICY', default_csp)
        response.headers['Content-Security-Policy'] = csp_header_value

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

    # --- CLI command for creating an admin user (moved from manage.py) ---
    @app.cli.command("create-admin")
    @click.option('-u', '--username', default=None, help='Admin username')
    @click.option('-e', '--email', default=None, help='Admin email')
    @click.option('-p', '--password', default=None, help='Admin password (will be prompted if not provided)')
    @click.option('-b', '--balance', type=int, default=100_000, help='Initial balance in satoshis (default: 100,000)')
    def create_admin_command(username, email, password, balance):
        """Creates an admin user with the given credentials and balance."""
        # Imports are already available: User, db, generate_bitcoin_wallet, click, re

        if not username:
            username = click.prompt("Enter admin username")

        if not email:
            while True:
                email_input = click.prompt("Enter admin email")
                if re.match(r"[^@]+@[^@]+\.[^@]+", email_input):
                    email = email_input
                    break
                else:
                    click.echo("Invalid email format. Please try again.")

        if not password:
            while True:
                password_input = click.prompt("Enter admin password", hide_input=True, confirmation_prompt=False)
                is_strong, message = is_password_strong(password_input)
                if not is_strong:
                    click.echo(f"Password validation failed: {message}")
                    click.echo("Please try again.")
                    continue

                password_confirmation = click.prompt("Confirm admin password", hide_input=True)
                if password_input == password_confirmation:
                    password = password_input
                    break
                else:
                    click.echo("Passwords do not match. Please try again.")
        else:
            is_strong, message = is_password_strong(password)
            if not is_strong:
                click.echo(f"Error: The provided password does not meet strength requirements: {message}")
                click.echo("Admin user creation aborted.")
                return

        with app.app_context(): # Ensure we are within application context for db operations
            existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
            if existing_user:
                if existing_user.username == username:
                    click.echo(f"Error: User with username '{username}' already exists.")
                if existing_user.email == email:
                    click.echo(f"Error: User with email '{email}' already exists.")
                return

            click.echo(f"Creating admin user: {username}")
            try:
                admin_wallet_addr = generate_bitcoin_wallet()
                if not admin_wallet_addr:
                    click.echo("Failed to generate wallet address for admin user. Aborting.")
                    return

                admin_user = User(
                    username=username,
                    email=email,
                    password=User.hash_password(password),
                    is_admin=True,
                    balance=balance,
                    deposit_wallet_address=admin_wallet_addr
                )
                db.session.add(admin_user)
                db.session.commit()
                click.echo(f"Admin user '{username}' created successfully with email '{email}'.")
            except Exception as e:
                db.session.rollback()
                click.echo(f"Failed to create admin user: {e}")

    return app

def log_production_warnings(app):
    if not app.debug: # Corresponds to FLASK_DEBUG=False
        # JWT_SECRET_KEY check
        if app.config.get('JWT_SECRET_KEY') == 'dev-secret-key-change-in-production':
            app.logger.critical(
                "CRITICAL SECURITY WARNING: Default JWT_SECRET_KEY is used in a production environment. "
                "Please set a strong, unique JWT_SECRET_KEY environment variable."
            )

        # ADMIN_PASSWORD check - As per instruction, this might be less relevant due to create_admin CLI.
        # However, if there's any fallback or direct use, it's still a risk.
        # For now, focusing on the direct config values as requested for other keys.
        # If create_admin is the *only* way admin is created, this check on config value might be noise.
        # Re-evaluating based on "For now, focus on JWT_SECRET_KEY and SERVICE_API_TOKEN."
        # Let's include it as per original broader instruction, but with a note.
        if app.config.get('ADMIN_PASSWORD') == 'admin123':
             app.logger.critical(
                "CRITICAL SECURITY WARNING: Default ADMIN_PASSWORD is set in the configuration. "
                "While admin creation might use a CLI, ensure this default is not used elsewhere and is changed."
            )

        # SERVICE_API_TOKEN check
        if app.config.get('SERVICE_API_TOKEN') == 'default_service_token_please_change':
            app.logger.critical(
                "CRITICAL SECURITY WARNING: Default SERVICE_API_TOKEN is used in a production environment. "
                "Please set a strong, unique SERVICE_API_TOKEN environment variable for internal service authentication."
            )

        # RATELIMIT_STORAGE_URI check
        if app.config.get('RATELIMIT_STORAGE_URI') == 'memory://':
            app.logger.warning(
                "PERFORMANCE/SCALABILITY WARNING: RATELIMIT_STORAGE_URI is set to 'memory://' in a production environment. "
                "This is not suitable for multi-process or multi-instance deployments. "
                "Consider using a persistent store like Redis (e.g., 'redis://localhost:6379/0')."
            )


# Create the app instance for direct usage
# app = create_app() # This line is usually present for Gunicorn/uWSGI or direct run.
                    # If manage.py or similar is the entry point, it might call create_app().
                    # For running directly with `python app.py`, it's needed.

# Add main section to run the app
if __name__ == '__main__':
    # When running app.py directly, create_app() is called here.
    # Ensure app.debug is correctly set based on FLASK_DEBUG env var for this direct run scenario.
    # The create_app() function already handles app.debug based on config_class.DEBUG,
    # which in turn reads FLASK_DEBUG.
    current_app_instance = create_app() # Use a different variable name to avoid confusion with flask.current_app proxy
    current_app_instance.run(host='0.0.0.0', port=5000) # debug is controlled by FLASK_DEBUG in Config

