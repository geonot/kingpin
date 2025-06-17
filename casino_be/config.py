import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DB_USER = os.environ.get('DB_USER')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    DB_HOST = os.environ.get('DB_HOST')
    DB_PORT = os.environ.get('DB_PORT', '5432')
    DB_NAME = os.environ.get('DB_NAME')

    if DB_USER and DB_PASSWORD and DB_HOST and DB_NAME:
        SQLALCHEMY_DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    else:
        SQLALCHEMY_DATABASE_URI = None # Explicitly None if not all parts are set

    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

    # Example of other configurations
    SLOTS_CONFIG_PATH = os.environ.get('SLOTS_CONFIG_PATH', 'slot_configs/default_slots.json')
    GAME_CONFIG_PATH = os.environ.get('GAME_CONFIG_PATH', 'game_configs/default_game_config.json')

    # Bitcoin Poller configuration
    BITCOIN_RPC_URL = os.environ.get('BITCOIN_RPC_URL') # e.g., http://user:password@localhost:8332
    MIN_CONFIRMATIONS = int(os.environ.get('MIN_CONFIRMATIONS', '1'))
    POLL_INTERVAL_SECONDS = int(os.environ.get('POLL_INTERVAL_SECONDS', '60'))
    WALLET_NAME = os.environ.get('WALLET_NAME', '') # Optional, for multi-wallet setups

    # Crystal Garden
    CRYSTAL_CONFIG_PATH = os.environ.get('CRYSTAL_CONFIG_PATH', 'game_configs/crystal_garden_config.json')


class DevelopmentConfig(Config):
    DEBUG = True
    # For development, we might use a local SQLite database if PostgreSQL isn't set up
    if not Config.SQLALCHEMY_DATABASE_URI:
        SQLALCHEMY_DATABASE_URI = "sqlite:///./dev_casino_be.db"

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:" # Use in-memory SQLite for tests
    # DATABASE_FILE_PATH = None # Remove or comment out if it exists

    JWT_SECRET_KEY = "test_jwt_secret" # Override for testing
    ADMIN_PASSWORD = "test_admin_password" # Override for testing
    SECRET_KEY = "test_secret_key" # Override for testing

    # Ensure other potentially sensitive or environment-specific configs are set for testing
    BITCOIN_RPC_URL = "http://testuser:testpass@localhost:18332" # Mock RPC URL for testing

    # Make sure slots and game configs point to test/dummy versions if necessary
    SLOTS_CONFIG_PATH = 'tests/fixtures/test_slots.json'
    GAME_CONFIG_PATH = 'tests/fixtures/test_game_config.json'
    CRYSTAL_CONFIG_PATH = 'tests/fixtures/test_crystal_config.json'


class ProductionConfig(Config):
    DEBUG = False
    # In production, ensure SQLALCHEMY_DATABASE_URI is set via environment variables.
    # Additional production-specific settings can go here.

def perform_startup_validation():
    """
    Validates that critical configurations are set.
    Raises ValueError if any critical configuration is missing.
    """
    critical_vars = {
        "JWT_SECRET_KEY": Config.JWT_SECRET_KEY,
        "ADMIN_PASSWORD": Config.ADMIN_PASSWORD,
        "SQLALCHEMY_DATABASE_URI": Config.SQLALCHEMY_DATABASE_URI,
    }

    # For SQLALCHEMY_DATABASE_URI, if it's based on components, check them too if SQLALCHEMY_DATABASE_URI is None
    if not Config.SQLALCHEMY_DATABASE_URI:
        component_based_vars = {
            "DB_USER": Config.DB_USER,
            "DB_PASSWORD": Config.DB_PASSWORD,
            "DB_HOST": Config.DB_HOST,
            "DB_NAME": Config.DB_NAME,
        }
        # If URI is None, all components must be present to form it.
        # This logic is a bit reversed; if URI is None, it means components weren't all there.
        missing_components = [key for key, value in component_based_vars.items() if not value]
        if len(missing_components) > 0 and len(missing_components) < len(component_based_vars): # some but not all
             raise ValueError(f"CRITICAL CONFIGURATION ERROR: SQLALCHEMY_DATABASE_URI is not fully defined. Missing components: {', '.join(missing_components)}")
        elif len(missing_components) == len(component_based_vars) and not os.getenv('FLASK_ENV') == 'testing':
             # If all components are missing AND we are not in testing, then it's an error.
             # TestingConfig provides its own SQLALCHEMY_DATABASE_URI.
             # DevelopmentConfig also provides a fallback.
             # This primarily targets ProductionConfig or if DevelopmentConfig fallback is removed.
             current_flask_env = os.getenv('FLASK_ENV', 'None')
             current_config_class = os.getenv('APP_CONFIG_CLASS', 'None') # You might need to set this in app.py when loading config

             # Only raise if not using TestingConfig and not DevelopmentConfig with its fallback
             is_testing = TestingConfig.TESTING
             is_dev_with_fallback = (current_flask_env == 'development' and DevelopmentConfig.SQLALCHEMY_DATABASE_URI and "sqlite" in DevelopmentConfig.SQLALCHEMY_DATABASE_URI)

             # The validation should only fail if critical secrets are missing AND we are in an environment
             # that doesn't provide its own safe defaults (like TestingConfig or DevelopmentConfig's SQLite fallback)
             # For Production, SQLALCHEMY_DATABASE_URI (or its components) must be set.
             # For Development, if components are not set, it falls back to SQLite.
             # For Testing, it uses its own SQLite.

             # If SQLALCHEMY_DATABASE_URI is still None at this point (meaning no env vars, no components, no dev fallback used)
             # then it's a critical issue unless we are in testing.
             if not is_testing and Config.SQLALCHEMY_DATABASE_URI is None:
                 raise ValueError(
                    "CRITICAL CONFIGURATION ERROR: SQLALCHEMY_DATABASE_URI is not set and no default is available for the current environment."
                 )


    # General check for other critical vars (JWT_SECRET_KEY, ADMIN_PASSWORD)
    # SQLALCHEMY_DATABASE_URI is checked above more thoroughly
    missing_critical_vars = [key for key, value in critical_vars.items() if not value and key != "SQLALCHEMY_DATABASE_URI"]
    if missing_critical_vars:
        raise ValueError(f"CRITICAL CONFIGURATION ERROR: Missing critical environment variables: {', '.join(missing_critical_vars)}")

    # Specific check for Bitcoin poller in production like environments
    if os.getenv('FLASK_ENV') == 'production' and not Config.BITCOIN_RPC_URL:
        raise ValueError("CRITICAL CONFIGURATION ERROR: BITCOIN_RPC_URL must be set in production.")


# Determine which configuration to use
env = os.environ.get("FLASK_ENV", "development")

if env == "testing":
    app_config = TestingConfig()
elif env == "production":
    app_config = ProductionConfig()
else:
    app_config = DevelopmentConfig()

# Perform validation after selecting config, but only if not running under a test runner
# that might be loading this file without intending to start the app (e.g. for discovery)
# However, app.py will call this explicitly.
# if not os.environ.get("PYTEST_CURRENT_TEST"):
#    perform_startup_validation(app_config)

config_by_name = dict(
    dev=DevelopmentConfig,
    test=TestingConfig,
    prod=ProductionConfig
)
