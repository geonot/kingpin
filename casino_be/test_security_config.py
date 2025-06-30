#!/usr/bin/env python3
"""
Configuration validation test script.

This script validates that the security configuration system works correctly
in both development and production modes.
"""

import os
import sys
import tempfile
import secrets
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_development_mode():
    """Test configuration loading in development mode."""
    print("🧪 Testing Development Mode...")
    
    # Clear modules from cache to ensure fresh import
    modules_to_clear = ['config', 'config_validator']
    for module in modules_to_clear:
        if module in sys.modules:
            del sys.modules[module]
    
    # Set development environment
    os.environ['FLASK_ENV'] = 'development'
    os.environ['FLASK_DEBUG'] = 'True'
    
    # Clear any production variables that might be set
    prod_vars = [
        'JWT_SECRET_KEY', 'DATABASE_URL', 'ADMIN_USERNAME', 'ADMIN_PASSWORD',
        'ADMIN_EMAIL', 'ENCRYPTION_SECRET', 'SERVICE_API_TOKEN',
        'RATELIMIT_STORAGE_URI', 'CORS_ORIGINS'
    ]
    for var in prod_vars:
        os.environ.pop(var, None)
    
    try:
        # Import and test configuration
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # Suppress expected warnings
            from config import Config
        
        # Validate development behavior
        assert Config.DEBUG == True, "Debug should be enabled in development"
        assert len(Config.JWT_SECRET_KEY) >= 32, "JWT secret should be generated"
        assert Config.ADMIN_USERNAME == 'admin', "Should use development admin defaults"
        assert Config.RATELIMIT_STORAGE_URI == 'memory://', "Should use memory storage in dev"
        
        print("✅ Development mode: All tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Development mode failed: {e}")
        return False

def test_production_mode_failure():
    """Test that production mode fails without proper configuration."""
    print("🧪 Testing Production Mode Failure...")
    
    # Clear modules from cache to ensure fresh import
    modules_to_clear = ['config', 'config_validator']
    for module in modules_to_clear:
        if module in sys.modules:
            del sys.modules[module]
    
    # Set production environment
    os.environ['FLASK_ENV'] = 'production'
    os.environ['FLASK_DEBUG'] = 'False'
    
    # Clear all configuration to force failure
    prod_vars = [
        'JWT_SECRET_KEY', 'DATABASE_URL', 'ADMIN_USERNAME', 'ADMIN_PASSWORD',
        'ADMIN_EMAIL', 'ENCRYPTION_SECRET', 'SERVICE_API_TOKEN',
        'RATELIMIT_STORAGE_URI', 'CORS_ORIGINS'
    ]
    for var in prod_vars:
        os.environ.pop(var, None)
    
    try:
        # This should fail with SystemExit
        from config import Config
        print("❌ Production mode should have failed but didn't")
        return False
        
    except SystemExit as e:
        if e.code == 1:
            print("✅ Production mode: Correctly failed with SystemExit(1)")
            return True
        else:
            print(f"❌ Production mode: Wrong exit code {e.code}")
            return False
            
    except Exception as e:
        print(f"❌ Production mode: Unexpected error {e}")
        return False

def test_production_mode_success():
    """Test that production mode works with proper configuration."""
    print("🧪 Testing Production Mode Success...")
    
    # Set production environment with all required variables
    os.environ.update({
        'FLASK_ENV': 'production',
        'FLASK_DEBUG': 'False',
        'JWT_SECRET_KEY': secrets.token_urlsafe(64),
        'DATABASE_URL': 'postgresql://user:pass@localhost:5432/testdb',
        'ADMIN_USERNAME': 'prodadmin',
        'ADMIN_PASSWORD': 'VeryStrongPassword123!',
        'ADMIN_EMAIL': 'admin@example.com',
        'ENCRYPTION_SECRET': secrets.token_urlsafe(32),
        'SERVICE_API_TOKEN': secrets.token_urlsafe(32),
        'RATELIMIT_STORAGE_URI': 'redis://localhost:6379/0',
        'CORS_ORIGINS': 'https://example.com,https://www.example.com'
    })
    
    try:
        # Remove the module from cache to force reload
        if 'config' in sys.modules:
            del sys.modules['config']
        if 'config_validator' in sys.modules:
            del sys.modules['config_validator']
        
        from config import Config
        
        # Validate production behavior
        assert Config.DEBUG == False, "Debug should be disabled in production"
        assert len(Config.JWT_SECRET_KEY) >= 32, "JWT secret should be set"
        assert Config.ADMIN_USERNAME == 'prodadmin', "Should use provided admin username"
        assert Config.RATELIMIT_STORAGE_URI.startswith('redis://'), "Should use Redis in production"
        assert len(Config.CORS_ORIGINS_LIST) == 2, "Should parse CORS origins correctly"
        
        print("✅ Production mode: All tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Production mode success test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all configuration tests."""
    print("🔒 Kingpin Casino Configuration Security Tests")
    print("=" * 50)
    
    tests = [
        test_development_mode,
        test_production_mode_failure,
        test_production_mode_success
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()  # Blank line between tests
    
    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All security configuration tests PASSED!")
        print("✅ P0-1 Critical Security Fix: IMPLEMENTED SUCCESSFULLY")
        return True
    else:
        print("💥 Some tests FAILED!")
        print("❌ P0-1 Critical Security Fix: IMPLEMENTATION INCOMPLETE")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
