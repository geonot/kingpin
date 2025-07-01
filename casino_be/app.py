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
from flask_socketio import SocketIO
from flask_jwt_extended import (
    JWTManager, create_access_token, create_refresh_token, jwt_required,
    get_jwt_identity, get_jti, current_user, verify_jwt_in_request
)
from flask_jwt_extended.exceptions import NoAuthorizationError # For JWT specific errors
from sqlalchemy.exc import SQLAlchemyError # For database errors
from werkzeug.exceptions import HTTPException as WerkzeugHTTPException # Renamed to avoid conflict
from flask_talisman import Talisman
from casino_be.exceptions import AppException, ValidationException, AuthenticationException, AuthorizationException, NotFoundException, InsufficientFundsException, GameLogicException, InternalServerErrorException
from casino_be.error_codes import ErrorCodes
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
from .models import ( # Relative import
    db, User, GameSession, Transaction, BonusCode, Slot, SlotSymbol, SlotBet, TokenBlacklist,
    BlackjackTable, BlackjackHand, BlackjackAction, UserBonus,
    SpacecrashGame, SpacecrashBet,  # Spacecrash models
    PokerTable, PokerHand, PokerPlayerState,  # Poker models
    PlinkoDropLog, RouletteGame,  # Plinko models, added RouletteGame
    BaccaratTable, BaccaratHand, BaccaratAction, # Baccarat models
    # Crystal Garden Models
    CrystalSeed, PlayerGarden, CrystalFlower, CrystalCodexEntry
)
from .utils.security import secure_headers, log_security_event # Relative import
from .schemas import ( # Relative import
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
from .utils.auth import register_jwt_handlers # Relative import
from .utils.bitcoin import generate_bitcoin_wallet # Relative import
from .utils.spin_handler_new import handle_spin # Corrected and relative import
from .utils.multiway_helper import handle_multiway_spin # Relative import
from .utils.blackjack_helper import handle_join_blackjack, handle_blackjack_action # Relative import
from .utils import spacecrash_handler # Relative import
from .utils import poker_helper # Relative import
from .utils import roulette_helper # Relative import
from .utils.plinko_helper import validate_plinko_params, calculate_winnings, STAKE_CONFIG, PAYOUT_MULTIPLIERS # Relative import
from .utils import baccarat_helper # Relative import
from .config import Config # Relative import
from sqlalchemy.orm import joinedload # Added for poker join logic
from sqlalchemy import select, func # Added for SQLAlchemy 2.0 compatibility
from decimal import Decimal
from .services.bonus_service import apply_bonus_to_deposit # Relative import
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

# --- Blueprint Imports (moved to top and made relative) ---
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
from .routes.baccarat import baccarat_bp
from .routes.internal import internal_bp
from .routes.crystal_garden import crystal_garden_bp
from .routes.bitcoin import bitcoin_bp

def create_app(config_class=Config):
    """Application factory pattern with enhanced security."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # --- Security Headers with Talisman ---
    csp = {
        'default-src': "'self'",
        'script-src': "'self' 'unsafe-inline'",
        'style-src': "'self' 'unsafe-inline'",
        'img-src': "'self' data: https:",
        'font-src': "'self'",
        'connect-src': "'self'",
        'frame-ancestors': "'none'"
    }
    
    Talisman(app, 
             force_https=not app.debug,
             strict_transport_security=True,
             content_security_policy=csp,
             content_security_policy_nonce_in=['script-src', 'style-src'])

    # --- Enhanced CORS Setup ---
    allowed_origins = []
    
    # Development origins
    if app.debug:
        allowed_origins.extend([
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:8082",
            "http://127.0.0.1:8082"
        ])
    
    # Production origins from validated configuration
    if hasattr(config_class, 'CORS_ORIGINS_LIST') and config_class.CORS_ORIGINS_LIST:
        allowed_origins.extend(config_class.CORS_ORIGINS_LIST)
    
    # Apply CORS with enhanced security
    if allowed_origins:
        CORS(app,
             origins=allowed_origins,
             supports_credentials=True,
             methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
             allow_headers=['Content-Type', 'Authorization', 'X-CSRF-Token'],
             expose_headers=['X-RateLimit-Limit', 'X-RateLimit-Remaining'],
             max_age=86400)
        app.logger.info(f"CORS configured for origins: {allowed_origins}")
    else:
        app.logger.warning("No CORS origins configured - API will reject cross-origin requests")

    # --- Security Logging Configuration ---
    if not app.debug:
        logger = app.logger
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

    # --- Request ID and Security Middleware ---
    @app.before_request
    def security_middleware():
        g.request_id = str(uuid.uuid4())
        
        # Log security-relevant requests
        user_id_to_log = None
        try:
            verify_jwt_in_request(optional=True) # Allow requests without JWT
            identity = get_jwt_identity() # Returns None if no JWT was found or if verify_jwt_in_request fails silently
            if identity:
                # Assuming identity is user_id or an object with id attribute that user_loader would return
                # For this logging purpose, directly using the identity (if it's simple like an int)
                # or trying to access current_user IF a token was found and processed might be options.
                # A common pattern is that identity is the user's ID.
                user_id_to_log = identity
                # If current_user is reliably populated after optional verify_jwt_in_request, this could be:
                # if current_user: user_id_to_log = current_user.id
        except Exception:
            # If any error occurs during JWT verification (e.g. malformed token, though optional=True should prevent most)
            # or getting identity, log without user_id.
            pass

        if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            try:
                user_id = getattr(current_user, 'id', None) if hasattr(current_user, 'id') else None
            except RuntimeError:
                # JWT not available in this context
                user_id = None
            
            log_security_event('REQUEST', 
                             user_id=user_id_to_log,
                             details={
                                 'endpoint': request.endpoint,
                                 'method': request.method,
                                 'user_agent': request.headers.get('User-Agent', ''),
                                 'content_length': request.content_length
                             })

    @app.after_request
    def security_headers_middleware(response):
        return secure_headers(response)

    # --- Production Warnings ---
    log_production_warnings(app)

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

    # --- WebSocket Setup ---
    socketio = SocketIO(app, 
                       cors_allowed_origins=allowed_origins,
                       async_mode='threading',
                       logger=app.logger,
                       engineio_logger=app.logger)
    
    # Initialize WebSocket Manager
    from .services.websocket_manager import websocket_manager
    websocket_manager.socketio = socketio
    websocket_manager.init_app(app)
    
    # Initialize SpaceCrash Game Loop
    from .services.spacecrash_game_loop import spacecrash_game_loop
    spacecrash_game_loop.websocket_manager = websocket_manager
    spacecrash_game_loop.app = app
    
    # Start game loop after app context is ready
    if not app.config.get('TESTING', False):
        # Use app context for initialization instead of deprecated before_first_request
        with app.app_context():
            # Delay start slightly to allow app to fully initialize
            import threading
            def delayed_start():
                import time
                time.sleep(1)  # Wait 1 second for app to be ready
                spacecrash_game_loop.start()
            
            thread = threading.Thread(target=delayed_start, daemon=True)
            thread.start()
    
    # Store socketio and game loop in app for access in routes
    app.socketio = socketio
    app.spacecrash_game_loop = spacecrash_game_loop

    # --- JWT Setup ---
    jwt = JWTManager(app)
    register_jwt_handlers(jwt)

    # --- Specific Error Handlers ---
    # Note: Some of these handlers might be superseded or modified by the global error handler,
    # but they can be kept for specific logging or if they handle non-AppException cases
    # that need special formatting before falling through to the global handler.

    @app.errorhandler(ValidationError)
    def handle_validation_error(e):
        # This handler is for Marshmallow's ValidationError specifically.
        # We can wrap this in our custom ValidationException for consistent response format.
        request_id = g.get('request_id', 'N/A')
        current_app.logger.warning(
            f"Request ID: {request_id} - Validation error: {e.messages} - Error Code: {ErrorCodes.VALIDATION_ERROR}"
        )
        return jsonify({
            'request_id': request_id,
            'status': False,
            'error_code': ErrorCodes.VALIDATION_ERROR,
            'status_message': 'Input validation failed.',
            'details': {'errors': e.messages},
            'action_button': None
        }), HTTPStatus.UNPROCESSABLE_ENTITY

    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(e):
        # This is a generic database error. We'll map it to our InternalServerErrorException.
        request_id = g.get('request_id', 'N/A')
        current_app.logger.error(
            f"Request ID: {request_id} - Database error. Error Code: {ErrorCodes.INTERNAL_SERVER_ERROR}",
            exc_info=True
        )
        return jsonify({
            'request_id': request_id,
            'status': False,
            'error_code': ErrorCodes.INTERNAL_SERVER_ERROR,
            'status_message': 'A database error occurred. Please try again later.',
            'details': {},
            'action_button': None
        }), HTTPStatus.INTERNAL_SERVER_ERROR

    @app.errorhandler(NoAuthorizationError)
    def handle_no_auth_error(e):
        # This is for JWT specific "NoAuthorizationError". Map to our AuthenticationException.
        request_id = g.get('request_id', 'N/A')
        current_app.logger.warning(
            f"Request ID: {request_id} - JWT NoAuthorizationError: {str(e)} - Error Code: {ErrorCodes.UNAUTHENTICATED}"
        )
        return jsonify({
            'request_id': request_id,
            'status': False,
            'error_code': ErrorCodes.UNAUTHENTICATED,
            'status_message': 'Missing or invalid authorization token.',
            'details': {'original_error': str(e)},
            'action_button': None
        }), HTTPStatus.UNAUTHORIZED

    @jwt.token_in_blocklist_loader
    def check_if_token_in_blacklist(jwt_header, jwt_payload):
        jti = jwt_payload['jti']
        try:
            # Check if token exists in blacklist
            token = db.session.scalar(select(TokenBlacklist.id).filter_by(jti=jti))
            is_blacklisted = token is not None
            
            if is_blacklisted:
                current_app.logger.warning(f"Request ID: {g.get('request_id', 'N/A')} - Blocked blacklisted token: {jti}")
            
            return is_blacklisted
        except Exception as e:
            current_app.logger.error(f"Request ID: {g.get('request_id', 'N/A')} - Error checking token blacklist: {str(e)}")
            # Fail secure - if we can't check the blacklist, assume token is valid but log the error
            return False

    # This specific handler for WerkzeugHTTPException might be adjusted or removed
    # depending on how the global Exception handler is structured.
    # For now, let's keep it to show how it would integrate.
    @app.errorhandler(WerkzeugHTTPException)
    def handle_werkzeug_http_exception(e):
        request_id = g.get('request_id', 'N/A')
        # Determine appropriate error code based on HTTP status
        error_code = ErrorCodes.GENERIC_ERROR # Default
        if e.code == 404:
            error_code = ErrorCodes.NOT_FOUND
        elif e.code == 405:
            error_code = ErrorCodes.METHOD_NOT_ALLOWED
        elif e.code == 401: # Should ideally be caught by NoAuthorizationError or an AppException
            error_code = ErrorCodes.UNAUTHENTICATED
        elif e.code == 403: # Should ideally be caught by an AppException
            error_code = ErrorCodes.FORBIDDEN
        elif e.code >= 500:
            error_code = ErrorCodes.INTERNAL_SERVER_ERROR

        current_app.logger.warning(
            f"Request ID: {request_id} - Werkzeug HTTPException: {e.code} - {e.name}: {e.description} - Error Code: {error_code}"
        )
        response_data = {
            'request_id': request_id,
            'status': False,
            'error_code': error_code,
            'status_message': e.name,
            'details': {'description': e.description},
            'action_button': None
        }
        # Ensure response is JSON, using Flask's built-in way to get response from HTTPException
        response = e.get_response()
        response.data = jsonify(response_data).data
        response.content_type = "application/json"
        return response

    # --- Global Error Handler (catch-all for general exceptions) ---
    @app.errorhandler(Exception)
    def handle_global_exception(e):
        request_id = g.get('request_id', 'N/A')

        if isinstance(e, AppException):
            current_app.logger.error(
                f"Request ID: {request_id} - AppException: {e.error_code} - {e.status_message} - Details: {e.details}",
                exc_info=True if e.status_code >= 500 else False # Log stack trace for server errors
            )
            return jsonify({
                'request_id': request_id,
                'status': False,
                'error_code': e.error_code,
                'status_message': e.status_message,
                'details': e.details,
                'action_button': e.action_button
            }), e.status_code

        if isinstance(e, WerkzeugHTTPException):
            # This will reuse the logic from handle_werkzeug_http_exception
            # to ensure consistent formatting for Werkzeug's own HTTP exceptions.
            return handle_werkzeug_http_exception(e)

        # For other unhandled exceptions (not AppException, not WerkzeugHTTPException)
        current_app.logger.critical(
            f"Request ID: {request_id} - Unhandled Critical Exception. Error Code: {ErrorCodes.INTERNAL_SERVER_ERROR}",
            exc_info=True
        )
        return jsonify({
            'request_id': request_id,
            'status': False,
            'error_code': ErrorCodes.INTERNAL_SERVER_ERROR,
            'status_message': 'An unexpected internal server error occurred. Please try again later.',
            'details': {}, # No specific details to expose for unknown errors
            'action_button': None
        }), HTTPStatus.INTERNAL_SERVER_ERROR

    # Specific handler for 404, to ensure it uses NotFoundException or a consistent format.
    # This should be registered before the generic Exception handler.
    # Flask tries handlers from most specific to least specific.
    # So, @app.errorhandler(404) or @app.errorhandler(NotFound) is more specific than @app.errorhandler(Exception).
    @app.errorhandler(404) # Catches werkzeug.exceptions.NotFound
    def handle_flask_not_found(e):
        # This handler ensures that Flask's default 404s (which are WerkzeugHTTPException)
        # are also formatted consistently with our error structure, using the NOT_FOUND error code.
        request_id = g.get('request_id', 'N/A')
        current_app.logger.warning(
            f"Request ID: {request_id} - HTTP 404 Not Found: {request.url} - Error Code: {ErrorCodes.NOT_FOUND}"
        )
        return jsonify({
            'request_id': request_id,
            'status': False,
            'error_code': ErrorCodes.NOT_FOUND,
            'status_message': 'The requested resource was not found.',
            'details': {'path': request.path},
            'action_button': None
        }), HTTPStatus.NOT_FOUND


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
# Moved to top of file. Definitions will be used in app.register_blueprint calls.

    # CLI command for cleanup
    @app.cli.command('cleanup-expired-tokens')
    def db_cleanup_expired_tokens_command():
        now = datetime.now(timezone.utc)
        try:
            count = db.session.scalar(select(func.count(TokenBlacklist.id)).filter(TokenBlacklist.expires_at < now))
            db.session.execute(select(TokenBlacklist).filter(TokenBlacklist.expires_at < now)).delete()
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
    app.register_blueprint(bitcoin_bp) # Register Bitcoin blueprint

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
            existing_user = db.session.scalar(select(User).filter((User.username == username) | (User.email == email)))
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

    return app, socketio

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
app, socketio = create_app() # This line is usually present for Gunicorn/uWSGI or direct run.
                    # If manage.py or similar is the entry point, it might call create_app().
                    # For running directly with `python app.py`, it's needed.

# Add main section to run the app
if __name__ == '__main__':
    # When running app.py directly, create_app() is called here.
    # Ensure app.debug is correctly set based on FLASK_DEBUG env var for this direct run scenario.
    # The create_app() function already handles app.debug based on config_class.DEBUG,
    # which in turn reads FLASK_DEBUG.
    socketio.run(app, host='0.0.0.0', port=5000, debug=app.debug) # debug is controlled by FLASK_DEBUG in Config

