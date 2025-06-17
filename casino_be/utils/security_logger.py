"""
Security Event Logging System
Provides comprehensive audit logging for security-critical events
"""

import logging
from datetime import datetime, timezone
from flask import current_app, g, request
from functools import wraps
import json

class SecurityLogger:
    """Centralized security event logging"""
    
    @staticmethod
    def log_authentication_event(event_type: str, user_id: int = None, username: str = None, 
                                success: bool = True, details: dict = None):
        """Log authentication-related events"""
        # Safely get request context information
        try:
            request_id = g.get('request_id', 'N/A')
            ip_address = request.remote_addr if request else None
            user_agent = request.headers.get('User-Agent') if request else None
        except RuntimeError:
            # Outside application context
            request_id = 'N/A'
            ip_address = None
            user_agent = None
        
        event_data = {
            'event_type': 'authentication',
            'sub_type': event_type,
            'user_id': user_id,
            'username': username,
            'success': success,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'request_id': request_id,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'details': details or {}
        }
        
        level = logging.INFO if success else logging.WARNING
        current_app.logger.log(level, f"AUTH_EVENT: {json.dumps(event_data)}")
    
    @staticmethod
    def log_financial_event(event_type: str, user_id: int, amount: int = None, 
                           balance_before: int = None, balance_after: int = None,
                           transaction_id: str = None, details: dict = None):
        """Log financial transaction events"""
        # Safely get request context information
        try:
            request_id = g.get('request_id', 'N/A')
            ip_address = request.remote_addr if request else None
        except RuntimeError:
            # Outside application context
            request_id = 'N/A'
            ip_address = None
        
        event_data = {
            'event_type': 'financial',
            'sub_type': event_type,
            'user_id': user_id,
            'amount_sats': amount,
            'balance_before_sats': balance_before,
            'balance_after_sats': balance_after,
            'transaction_id': transaction_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'request_id': request_id,
            'ip_address': ip_address,
            'details': details or {}
        }
        
        current_app.logger.info(f"FINANCIAL_EVENT: {json.dumps(event_data)}")
    
    @staticmethod
    def log_game_event(event_type: str, user_id: int, game_type: str = None,
                      bet_amount: int = None, win_amount: int = None,
                      game_session_id: int = None, details: dict = None):
        """Log game-related events"""
        # Safely get request context information
        try:
            request_id = g.get('request_id', 'N/A')
            ip_address = request.remote_addr if request else None
        except RuntimeError:
            # Outside application context
            request_id = 'N/A'
            ip_address = None
        
        event_data = {
            'event_type': 'game',
            'sub_type': event_type,
            'user_id': user_id,
            'game_type': game_type,
            'bet_amount_sats': bet_amount,
            'win_amount_sats': win_amount,
            'game_session_id': game_session_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'request_id': request_id,
            'ip_address': ip_address,
            'details': details or {}
        }
        
        current_app.logger.info(f"GAME_EVENT: {json.dumps(event_data)}")
    
    @staticmethod
    def log_security_event(event_type: str, severity: str = 'medium', user_id: int = None,
                          details: dict = None):
        """Log security-related events"""
        # Safely get request context information
        try:
            request_id = g.get('request_id', 'N/A')
            ip_address = request.remote_addr if request else None
            user_agent = request.headers.get('User-Agent') if request else None
        except RuntimeError:
            # Outside application context
            request_id = 'N/A'
            ip_address = None
            user_agent = None
        
        event_data = {
            'event_type': 'security',
            'sub_type': event_type,
            'severity': severity,
            'user_id': user_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'request_id': request_id,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'details': details or {}
        }
        
        level_map = {
            'low': logging.INFO,
            'medium': logging.WARNING,
            'high': logging.ERROR,
            'critical': logging.CRITICAL
        }
        
        level = level_map.get(severity, logging.WARNING)
        current_app.logger.log(level, f"SECURITY_EVENT: {json.dumps(event_data)}")
    
    @staticmethod
    def log_admin_event(event_type: str, admin_user_id: int, target_user_id: int = None,
                       action: str = None, details: dict = None):
        """Log administrative actions"""
        # Safely get request context information
        try:
            request_id = g.get('request_id', 'N/A')
            ip_address = request.remote_addr if request else None
        except RuntimeError:
            # Outside application context
            request_id = 'N/A'
            ip_address = None
        
        event_data = {
            'event_type': 'admin',
            'sub_type': event_type,
            'admin_user_id': admin_user_id,
            'target_user_id': target_user_id,
            'action': action,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'request_id': request_id,
            'ip_address': ip_address,
            'details': details or {}
        }
        
        current_app.logger.warning(f"ADMIN_EVENT: {json.dumps(event_data)}")

def audit_financial_operation(operation_type: str):
    """Decorator to audit financial operations"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = None
            balance_before = None
            
            # Try to extract user info before operation
            try:
                from flask_jwt_extended import current_user
                if current_user:
                    user_id = current_user.id
                    balance_before = current_user.balance
            except:
                pass
            
            # Execute the operation
            result = f(*args, **kwargs)
            
            # Log the operation
            try:
                balance_after = None
                if current_user:
                    balance_after = current_user.balance
                
                SecurityLogger.log_financial_event(
                    event_type=operation_type,
                    user_id=user_id,
                    balance_before=balance_before,
                    balance_after=balance_after,
                    details={'function': f.__name__, 'args_count': len(args)}
                )
            except Exception as e:
                current_app.logger.error(f"Failed to log financial operation: {str(e)}")
            
            return result
        return decorated_function
    return decorator

def audit_game_operation(game_type: str):
    """Decorator to audit game operations"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = None
            
            # Try to extract user info
            try:
                from flask_jwt_extended import current_user
                if current_user:
                    user_id = current_user.id
            except:
                pass
            
            # Execute the operation
            result = f(*args, **kwargs)
            
            # Log the operation
            try:
                SecurityLogger.log_game_event(
                    event_type='operation',
                    user_id=user_id,
                    game_type=game_type,
                    details={'function': f.__name__, 'result_type': type(result).__name__}
                )
            except Exception as e:
                current_app.logger.error(f"Failed to log game operation: {str(e)}")
            
            return result
        return decorated_function
    return decorator