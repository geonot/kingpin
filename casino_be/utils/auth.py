from flask_jwt_extended import get_jwt_identity, get_jti
from casino_be.models import db, User, TokenBlacklist # Make sure models are imported correctly
from datetime import datetime, timezone

def user_identity_lookup(user):
    return str(user.id)

def user_lookup_callback(_jwt_header, jwt_data):
    identity = jwt_data["sub"]
    user_obj = User.query.get(identity)
    return user_obj

def check_if_token_in_blacklist(jwt_header, jwt_payload):
    jti = jwt_payload['jti']
    now = datetime.now(timezone.utc)
    token = db.session.query(TokenBlacklist.id).filter_by(jti=jti).scalar()
    # Could add a check here: .filter(TokenBlacklist.expires_at > now)
    # However, the current logic simply checks if the JTI exists,
    # relying on a separate cleanup process for expired tokens.
    # For now, let's keep it as it was in app.py after the previous fix.
    return token is not None

def register_jwt_handlers(jwt):
    jwt.user_identity_loader(user_identity_lookup)
    jwt.user_lookup_loader(user_lookup_callback)
    jwt.token_in_blocklist_loader(check_if_token_in_blacklist)
