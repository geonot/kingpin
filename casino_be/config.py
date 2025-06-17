import os

class Config:
    # Database configuration - PostgreSQL for both development and production
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    if DATABASE_URL:
        # Use provided DATABASE_URL
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        # Build from individual components for local development
        DB_HOST = os.getenv('DB_HOST', 'localhost')
        DB_PORT = os.getenv('DB_PORT', '5432')
        DB_NAME = os.getenv('DB_NAME', 'kingpin_casino')
        DB_USER = os.getenv('DB_USER', 'kingpin_user')
        DB_PASSWORD = os.getenv('DB_PASSWORD', 'password123')
        
        SQLALCHEMY_DATABASE_URI = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT Configuration - Enhanced Security
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    if not JWT_SECRET_KEY:
        import secrets
        import warnings
        # Generate a secure random key for development
        JWT_SECRET_KEY = secrets.token_urlsafe(64)
        warnings.warn(
            "JWT_SECRET_KEY not set in environment. Using generated key for development. "
            "Set JWT_SECRET_KEY environment variable for production!",
            UserWarning
        )
    
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', '3600'))  # 1 hour
    JWT_REFRESH_TOKEN_EXPIRES = int(os.getenv('JWT_REFRESH_TOKEN_EXPIRES', str(86400 * 7)))  # 7 days
    JWT_BLACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = ['access', 'refresh']
    
    # JWT Cookie Configuration for enhanced security
    JWT_TOKEN_LOCATION = ['cookies']
    JWT_COOKIE_SECURE = os.getenv('JWT_COOKIE_SECURE', 'True').lower() in ('true', '1', 't')
    JWT_COOKIE_HTTPONLY = True
    JWT_COOKIE_SAMESITE = 'Strict'
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_ACCESS_COOKIE_NAME = 'access_token_cookie'
    JWT_REFRESH_COOKIE_NAME = 'refresh_token_cookie'
    JWT_ACCESS_CSRF_HEADER_NAME = 'X-CSRF-Token'
    JWT_REFRESH_CSRF_HEADER_NAME = 'X-CSRF-Token'
    
    # Session Configuration
    SESSION_COOKIE_SECURE = JWT_COOKIE_SECURE
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    
    # Security Headers
    SECURITY_HEADERS = True

    # Rate Limiter Storage URI
    # For production, set e.g., RATELIMIT_STORAGE_URI='redis://localhost:6379/0'
    RATELIMIT_STORAGE_URI = os.getenv('RATELIMIT_STORAGE_URI', 'memory://')

    # Flask Debug Mode - SECURE DEFAULT
    # Debug mode is DISABLED by default for security
    # Set FLASK_DEBUG=True explicitly for development
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')

    # Satoshi Conversion Factor (1 BTC = 100,000,000 Satoshis)
    SATOSHI_FACTOR = 100_000_000

    # Admin settings - MUST be set in production
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL')
    
    # Validate required admin settings
    if not all([ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_EMAIL]):
        import warnings
        warnings.warn(
            "Admin credentials not fully configured in environment variables. "
            "Set ADMIN_USERNAME, ADMIN_PASSWORD, and ADMIN_EMAIL for production!",
            UserWarning
        )
        # Fallback values for development only
        ADMIN_USERNAME = ADMIN_USERNAME or 'admin'
        ADMIN_PASSWORD = ADMIN_PASSWORD or 'admin123'
        ADMIN_EMAIL = ADMIN_EMAIL or 'admin@kingpincasino.local'

    # Service API Token for internal services (e.g., polling service)
    SERVICE_API_TOKEN = os.getenv('SERVICE_API_TOKEN', 'default_service_token_please_change')

    # Feature Flags
    CRYSTAL_GARDEN_ENABLED = os.getenv('CRYSTAL_GARDEN_ENABLED', 'True').lower() in ('true', '1', 't')


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///./test_casino_be_isolated.db' # File-based for test isolation using SQLite
    # Define a key to store the database file path for easy cleanup
    DATABASE_FILE_PATH = SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '') # Adjusted for SQLite
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = 'test-jwt-secret-key'
    # Disable CSRF protection for tests if applicable (e.g., if using Flask-WTF)
    WTF_CSRF_ENABLED = False
    # Disable rate limiting for tests
    RATELIMIT_ENABLED = False
    RATELIMIT_DEFAULT_LIMITS_ENABLED = False
    # Ensure engine options for SQLite are appropriate if not using in-memory
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'check_same_thread': False}
        # StaticPool is not typically needed for file-based DBs,
        # as file ensures persistence across connections.
    }
