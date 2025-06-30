"""
Configuration validation and startup checks for production security.

This module implements fail-fast validation to ensure critical environment
variables are set before the application starts, preventing insecure defaults
from being used in production.
"""

import os
import sys
import warnings
import secrets
from typing import List, Tuple, Optional


class ConfigValidationError(Exception):
    """Raised when critical configuration is missing or invalid."""
    pass


class ConfigValidator:
    """Validates application configuration and enforces production security."""
    
    def __init__(self, is_production: bool = None):
        """
        Initialize the configuration validator.
        
        Args:
            is_production: If None, auto-detect based on FLASK_ENV and DEBUG settings
        """
        if is_production is None:
            # Auto-detect production environment
            flask_env = os.getenv('FLASK_ENV', '').lower()
            flask_debug = os.getenv('FLASK_DEBUG', 'False').lower()
            is_production = (
                flask_env == 'production' or 
                (flask_env != 'development' and flask_debug not in ('true', '1', 't'))
            )
        
        self.is_production = is_production
        self.is_testing = os.getenv('TESTING', 'False').lower() in ('true', '1', 't')
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_required_env_var(self, var_name: str, description: str = None) -> Optional[str]:
        """
        Validate that a required environment variable is set.
        
        Args:
            var_name: Name of the environment variable
            description: Human-readable description for error messages
            
        Returns:
            The environment variable value if set, None otherwise
        """
        value = os.getenv(var_name)
        if not value:
            desc = description or var_name
            if self.is_production:
                self.errors.append(f"CRITICAL: {desc} ({var_name}) must be set in production environment")
            else:
                self.warnings.append(f"WARNING: {desc} ({var_name}) not set - using development fallback")
        return value

    def validate_jwt_config(self) -> Tuple[str, int, int]:
        """Validate JWT configuration."""
        # JWT Secret Key - CRITICAL for security
        jwt_secret = self.validate_required_env_var(
            'JWT_SECRET_KEY', 
            'JWT Secret Key'
        )
        
        if not jwt_secret:
            if self.is_production:
                # In production, we MUST have a JWT secret
                raise ConfigValidationError("JWT_SECRET_KEY is required in production")
            else:
                # Generate a secure random key for development
                jwt_secret = secrets.token_urlsafe(64)
                warnings.warn(
                    "JWT_SECRET_KEY not set. Generated secure random key for development. "
                    "Set JWT_SECRET_KEY environment variable for production!",
                    UserWarning
                )
        elif len(jwt_secret) < 32:
            error_msg = "JWT_SECRET_KEY must be at least 32 characters long"
            if self.is_production:
                self.errors.append(f"CRITICAL: {error_msg}")
            else:
                self.warnings.append(f"WARNING: {error_msg}")

        # JWT Token Expiration
        try:
            access_expires = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', '3600'))
            refresh_expires = int(os.getenv('JWT_REFRESH_TOKEN_EXPIRES', str(86400 * 7)))
        except ValueError:
            raise ConfigValidationError("JWT token expiration values must be integers")

        return jwt_secret, access_expires, refresh_expires

    def validate_database_config(self) -> str:
        """Validate database configuration."""
        database_url = os.getenv('DATABASE_URL')
        
        if database_url:
            # Validate DATABASE_URL format
            if not database_url.startswith(('postgresql://', 'postgresql+psycopg2://', 'sqlite://')):
                self.errors.append("CRITICAL: DATABASE_URL must use a supported database driver")
            return database_url
        
        # If no DATABASE_URL, validate individual components
        db_components = {
            'DB_HOST': os.getenv('DB_HOST'),
            'DB_PORT': os.getenv('DB_PORT'),
            'DB_NAME': os.getenv('DB_NAME'),
            'DB_USER': os.getenv('DB_USER'),
            'DB_PASSWORD': os.getenv('DB_PASSWORD')
        }
        
        missing_components = [k for k, v in db_components.items() if not v]
        
        if missing_components and self.is_production:
            self.errors.append(
                f"CRITICAL: Database configuration incomplete. Missing: {', '.join(missing_components)}. "
                "Set DATABASE_URL or all individual DB_* variables."
            )
        
        # Use fallbacks for development only
        if not self.is_production and not self.is_testing:
            db_host = db_components['DB_HOST'] or 'localhost'
            db_port = db_components['DB_PORT'] or '5432'
            db_name = db_components['DB_NAME'] or 'kingpin_casino'
            db_user = db_components['DB_USER'] or 'kingpin_user'
            db_password = db_components['DB_PASSWORD'] or 'password123'
            
            if missing_components:
                self.warnings.append(f"Using development database defaults for: {', '.join(missing_components)}")
            
            return f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
        
        return database_url

    def validate_admin_config(self) -> Tuple[str, str, str]:
        """Validate admin configuration."""
        admin_username = self.validate_required_env_var('ADMIN_USERNAME', 'Admin Username')
        admin_password = self.validate_required_env_var('ADMIN_PASSWORD', 'Admin Password')
        admin_email = self.validate_required_env_var('ADMIN_EMAIL', 'Admin Email')
        
        # In production, admin credentials MUST be set via environment
        if self.is_production and not all([admin_username, admin_password, admin_email]):
            raise ConfigValidationError(
                "Admin credentials (ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_EMAIL) must be set in production. "
                "Use the 'flask create-admin' CLI command to create admin users securely."
            )
        
        # Development fallbacks (with warnings)
        if not self.is_production and not self.is_testing:
            admin_username = admin_username or 'admin'
            admin_password = admin_password or 'admin123'
            admin_email = admin_email or 'admin@kingpincasino.local'
            
            if not all([os.getenv('ADMIN_USERNAME'), os.getenv('ADMIN_PASSWORD'), os.getenv('ADMIN_EMAIL')]):
                self.warnings.append(
                    "Using development admin credential defaults. "
                    "Set ADMIN_USERNAME, ADMIN_PASSWORD, and ADMIN_EMAIL for production!"
                )
        
        return admin_username, admin_password, admin_email

    def validate_encryption_config(self) -> str:
        """Validate encryption configuration."""
        encryption_secret = self.validate_required_env_var(
            'ENCRYPTION_SECRET', 
            'Encryption Secret for private key storage'
        )
        
        if not encryption_secret:
            if self.is_production:
                raise ConfigValidationError("ENCRYPTION_SECRET is required in production")
            else:
                encryption_secret = 'default-encryption-secret-change-in-production'
                warnings.warn(
                    "ENCRYPTION_SECRET not set. Using default for development. "
                    "Set ENCRYPTION_SECRET environment variable for production!",
                    UserWarning
                )
        elif len(encryption_secret) < 32:
            error_msg = "ENCRYPTION_SECRET should be at least 32 characters long"
            if self.is_production:
                self.errors.append(f"CRITICAL: {error_msg}")
            else:
                self.warnings.append(f"WARNING: {error_msg}")
        
        return encryption_secret

    def validate_service_config(self) -> str:
        """Validate service API token configuration."""
        service_token = os.getenv('SERVICE_API_TOKEN')
        
        if not service_token:
            if self.is_production:
                self.errors.append(
                    "CRITICAL: SERVICE_API_TOKEN must be set in production for internal service authentication"
                )
                service_token = None
            else:
                service_token = 'default_service_token_please_change'
                self.warnings.append(
                    "SERVICE_API_TOKEN not set - using development default. "
                    "Set a strong, unique token for production!"
                )
        elif service_token == 'default_service_token_please_change':
            if self.is_production:
                self.errors.append(
                    "CRITICAL: Default SERVICE_API_TOKEN detected in production. "
                    "Set a strong, unique SERVICE_API_TOKEN environment variable."
                )
            else:
                self.warnings.append("Using default SERVICE_API_TOKEN in development")
        
        return service_token

    def validate_rate_limiting_config(self) -> str:
        """Validate rate limiting configuration."""
        rate_limit_uri = os.getenv('RATELIMIT_STORAGE_URI', 'memory://')
        
        if rate_limit_uri == 'memory://' and self.is_production:
            self.errors.append(
                "CRITICAL: Rate limiting uses memory:// storage in production. "
                "This is not suitable for multi-process deployments. "
                "Set RATELIMIT_STORAGE_URI to a Redis URL (e.g., redis://localhost:6379/0)"
            )
        elif rate_limit_uri == 'memory://' and not self.is_production:
            self.warnings.append(
                "Rate limiting uses memory:// storage in development. "
                "Consider using Redis for production."
            )
        
        return rate_limit_uri

    def validate_cors_config(self) -> List[str]:
        """Validate CORS configuration."""
        cors_origins = os.getenv('CORS_ORIGINS', '')
        
        if not cors_origins and self.is_production:
            self.errors.append(
                "CRITICAL: CORS_ORIGINS must be set in production to specify allowed frontend domains"
            )
            return []
        
        if cors_origins:
            origins = [origin.strip() for origin in cors_origins.split(',') if origin.strip()]
            # Validate origin formats
            for origin in origins:
                if not origin.startswith(('http://', 'https://')):
                    self.warnings.append(f"CORS origin '{origin}' should include protocol (http:// or https://)")
            return origins
        
        return []

    def validate_all(self) -> dict:
        """
        Validate all configuration settings.
        
        Returns:
            Dictionary containing validated configuration values
            
        Raises:
            ConfigValidationError: If critical configuration is missing in production
        """
        config = {}
        
        try:
            # Validate each configuration area
            config['JWT_SECRET_KEY'], config['JWT_ACCESS_TOKEN_EXPIRES'], config['JWT_REFRESH_TOKEN_EXPIRES'] = self.validate_jwt_config()
            config['SQLALCHEMY_DATABASE_URI'] = self.validate_database_config()
            config['ADMIN_USERNAME'], config['ADMIN_PASSWORD'], config['ADMIN_EMAIL'] = self.validate_admin_config()
            config['ENCRYPTION_SECRET'] = self.validate_encryption_config()
            config['SERVICE_API_TOKEN'] = self.validate_service_config()
            config['RATELIMIT_STORAGE_URI'] = self.validate_rate_limiting_config()
            config['CORS_ORIGINS'] = self.validate_cors_config()
            
            # Additional configuration
            config['DEBUG'] = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
            config['JWT_COOKIE_SECURE'] = os.getenv('JWT_COOKIE_SECURE', 'True').lower() in ('true', '1', 't')
            config['CRYSTAL_GARDEN_ENABLED'] = os.getenv('CRYSTAL_GARDEN_ENABLED', 'True').lower() in ('true', '1', 't')
            
            # Production-specific validations
            if self.is_production:
                if config['DEBUG']:
                    self.errors.append("CRITICAL: DEBUG mode must be disabled in production (set FLASK_DEBUG=False)")
                
                if not config['JWT_COOKIE_SECURE']:
                    self.errors.append("CRITICAL: JWT cookies must be secure in production (set JWT_COOKIE_SECURE=True)")
            
            # Check for critical errors
            if self.errors:
                error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in self.errors)
                if self.warnings:
                    error_msg += "\n\nWarnings:\n" + "\n".join(f"  - {warning}" for warning in self.warnings)
                raise ConfigValidationError(error_msg)
            
            # Log warnings if any
            if self.warnings:
                for warning in self.warnings:
                    warnings.warn(warning, UserWarning)
            
            return config
            
        except Exception as e:
            if isinstance(e, ConfigValidationError):
                raise
            else:
                raise ConfigValidationError(f"Configuration validation error: {str(e)}") from e


def validate_production_config() -> dict:
    """
    Validate production configuration with fail-fast behavior.
    
    Returns:
        Dictionary of validated configuration values
        
    Raises:
        ConfigValidationError: If critical configuration is missing
        SystemExit: If validation fails and this is called during startup
    """
    try:
        validator = ConfigValidator()
        return validator.validate_all()
    except ConfigValidationError as e:
        print(f"\n🚨 CONFIGURATION VALIDATION FAILED 🚨\n", file=sys.stderr)
        print(str(e), file=sys.stderr)
        print("\n📋 How to fix:", file=sys.stderr)
        print("1. Set required environment variables", file=sys.stderr)
        print("2. Use 'flask create-admin' for admin user creation", file=sys.stderr)
        print("3. Review production deployment checklist", file=sys.stderr)
        print("\n❌ Application startup ABORTED\n", file=sys.stderr)
        
        # Exit with error code to prevent insecure startup
        sys.exit(1)
