# 🔒 KINGPIN CASINO SECURITY GUIDE

## Critical Security Update: P0-1 Configuration Security

**This update implements fail-fast startup validation to prevent insecure defaults in production environments.**

### 🚨 Breaking Changes

1. **No Default Fallbacks in Production**: All critical configuration must be explicitly set via environment variables
2. **Fail-Fast Startup**: Application will exit with error code 1 if required configuration is missing
3. **Enhanced Validation**: Configuration values are validated for security and correctness at startup

### 📋 Production Requirements

All production deployments **MUST** set the following environment variables:

#### Required Environment Variables

```bash
# Environment
FLASK_ENV=production
FLASK_DEBUG=False

# Database (choose one option)
DATABASE_URL=postgresql://user:password@host:port/database
# OR individual components:
# DB_HOST=localhost
# DB_PORT=5432
# DB_NAME=kingpin_casino
# DB_USER=kingpin_user
# DB_PASSWORD=secure_password

# JWT Security
JWT_SECRET_KEY=your_64_character_secret_key  # Generate with secrets.token_urlsafe(64)
JWT_ACCESS_TOKEN_EXPIRES=3600
JWT_REFRESH_TOKEN_EXPIRES=604800
JWT_COOKIE_SECURE=True

# Admin Credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=very_strong_password_here
ADMIN_EMAIL=admin@yourdomain.com

# Encryption
ENCRYPTION_SECRET=your_32_character_encryption_key  # Generate with secrets.token_urlsafe(32)

# Service Authentication
SERVICE_API_TOKEN=your_service_api_token  # Generate with secrets.token_urlsafe(32)

# Rate Limiting (Redis required for production)
RATELIMIT_STORAGE_URI=redis://localhost:6379/0

# CORS (Frontend domains)
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### 🔧 Development vs Production

#### Development Mode
- Uses secure fallbacks when environment variables are missing
- Shows warnings for missing configuration
- Allows memory-based rate limiting
- Debug mode can be enabled

#### Production Mode
- **Fails immediately** if any required configuration is missing
- **No fallback values** - all configuration must be explicit
- Requires Redis for rate limiting
- Debug mode is forced to False
- Enhanced security validation

### 🚀 Deployment Steps

1. **Copy Environment Template**:
   ```bash
   cp .env.example .env
   ```

2. **Generate Secure Secrets**:
   ```bash
   python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(64))"
   python -c "import secrets; print('ENCRYPTION_SECRET=' + secrets.token_urlsafe(32))"
   python -c "import secrets; print('SERVICE_API_TOKEN=' + secrets.token_urlsafe(32))"
   ```

3. **Configure Environment Variables**:
   - Edit `.env` file with your production values
   - Never commit `.env` to version control

4. **Validate Configuration**:
   ```bash
   FLASK_ENV=production python -c "from config import Config; print('✅ Configuration valid')"
   ```

5. **Setup Database**:
   ```bash
   flask db upgrade
   ```

6. **Create Admin User**:
   ```bash
   flask create-admin
   ```

### 🔍 Security Validation Features

#### Startup Validation
- **JWT Secret**: Must be at least 32 characters in production
- **Database**: Validates connection string format and required components
- **Admin Credentials**: Enforces strong password requirements in production
- **Encryption**: Validates encryption secret length and strength
- **Rate Limiting**: Requires Redis in production (memory storage not allowed)
- **CORS**: Validates origin format and requires explicit configuration

#### Production-Specific Checks
- Debug mode must be disabled
- JWT cookies must be secure
- Rate limiting must use persistent storage
- All secrets must meet minimum length requirements

### 🚨 Error Handling

#### Configuration Validation Failed
If you see this error during startup:
```
🚨 CONFIGURATION VALIDATION FAILED 🚨
```

**Solution**:
1. Check the specific error messages
2. Set the missing environment variables
3. Ensure all values meet security requirements
4. Refer to `.env.example` for proper format

#### Common Issues

1. **JWT_SECRET_KEY too short**: Must be at least 32 characters
2. **Missing database configuration**: Set DATABASE_URL or all DB_* variables
3. **Rate limiting in production**: Must use Redis, not memory://
4. **Invalid CORS origins**: Must include protocol (http:// or https://)

### 📊 Testing Configuration

#### Test Development Mode
```bash
FLASK_ENV=development FLASK_DEBUG=True python -c "from config import Config; print('Dev mode OK')"
```

#### Test Production Mode
```bash
# This should fail if configuration is incomplete
FLASK_ENV=production python -c "from config import Config; print('Prod mode OK')"
```

### 🔄 Migration from Previous Version

If you're upgrading from a previous version:

1. **Review your current configuration** - identify any default values being used
2. **Set explicit environment variables** for all production values
3. **Test in staging environment** before deploying to production
4. **Update deployment scripts** to include all required environment variables

### 🛡️ Security Best Practices

1. **Use strong, unique secrets** generated with cryptographically secure methods
2. **Rotate secrets regularly** (JWT keys, encryption keys, API tokens)
3. **Use environment-specific configurations** (separate secrets for dev/staging/prod)
4. **Monitor startup logs** for any security warnings
5. **Regular security audits** of environment variable configurations

### 📚 Related Documentation

- [Environment Variables Reference](.env.example)
- [Production Deployment Checklist](docs/deployment.md)
- [Security Audit Guidelines](docs/security-audit.md)

---

**⚠️ IMPORTANT**: This security update is mandatory for all production deployments. Applications with insecure default configurations will fail to start in production mode.
