from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, current_user
import logging
import os # Added for test seam

# Import real function with an alias
from casino_be.utils.bitcoin import generate_bitcoin_wallet, get_address_from_private_key_wif, send_to_hot_wallet as real_send_to_hot_wallet # Absolute
from casino_be.utils.encryption import encrypt_private_key, decrypt_private_key # Absolute
from casino_be.models import db, User, Transaction # Absolute
from sqlalchemy.orm.attributes import flag_modified # Added for JSON field update
from casino_be.utils.security import require_csrf_token, rate_limit_by_ip, log_security_event # Absolute

bitcoin_bp = Blueprint('bitcoin', __name__, url_prefix='/api/bitcoin')
logger = logging.getLogger(__name__)

# Global _send_to_hot_wallet_override is removed as per new strategy

def get_sender_func():
    """Helper to get the sender function, allowing override for testing via current_app."""
    if os.environ.get('TEST_MODE_ACTIVE_FOR_BTC_SENDER') == '1' and hasattr(current_app, 'test_btc_sender_override'):
        sender_override = getattr(current_app, 'test_btc_sender_override')
        if callable(sender_override): # Ensure it's callable
            return sender_override
        else:
            # Log a warning or error if it's set but not callable, and fall back
            logger.warning("TEST_MODE_ACTIVE_FOR_BTC_SENDER is '1' and test_btc_sender_override is set, but it's not callable. Falling back to real sender.")
    return real_send_to_hot_wallet

@bitcoin_bp.route('/deposit-address', methods=['GET'])
@jwt_required()
@rate_limit_by_ip("10 per hour")
def get_deposit_address():
    """Get the user's Bitcoin deposit address"""
    user = current_user
    
    if not user.deposit_wallet_address:
        # Generate a new wallet if user doesn't have one
        try:
            address, private_key_wif = generate_bitcoin_wallet()
            if not address or not private_key_wif:
                return jsonify({
                    'status': False, 
                    'status_message': 'Failed to generate wallet address'
                }), 500
            
            # Encrypt and store the private key
            encrypted_private_key = encrypt_private_key(private_key_wif)
            
            user.deposit_wallet_address = address
            user.deposit_wallet_private_key = encrypted_private_key
            db.session.commit()
            
            logger.info(f"Generated new Bitcoin wallet for user {user.id}: {address}")
            
        except Exception as e:
            logger.error(f"Failed to generate wallet for user {user.id}: {e}")
            return jsonify({
                'status': False,
                'status_message': 'Failed to generate wallet address'
            }), 500
    
    return jsonify({
        'status': True,
        'deposit_address': user.deposit_wallet_address
    })

@bitcoin_bp.route('/check-deposits', methods=['POST'])
@jwt_required()
@require_csrf_token
@rate_limit_by_ip("20 per hour")
def check_deposits():
    """
    Manually check for deposits to user's address.
    In production, this would be automated with blockchain monitoring.
    """
    user = current_user
    
    if not user.deposit_wallet_address:
        return jsonify({
            'status': False,
            'status_message': 'No deposit address found'
        }), 400
    
    # For now, this is a placeholder that would integrate with blockchain APIs
    # In production, use blockchain.info, blockchair, or run your own Bitcoin node
    
    logger.info(f"Checking deposits for user {user.id} address {user.deposit_wallet_address}")
    
    # This would normally query blockchain APIs or Bitcoin Core RPC
    # For now, return that no new deposits were found
    return jsonify({
        'status': True,
        'status_message': 'No new deposits found',
        'deposits_checked': True
    })

@bitcoin_bp.route('/process-withdrawal', methods=['POST'])
@jwt_required()
@require_csrf_token
@rate_limit_by_ip("3 per hour")
def process_withdrawal():
    """
    Process a Bitcoin withdrawal using the stored private key.
    This endpoint would be called after a withdrawal request is approved.
    """
    data = request.get_json()
    
    if not data or 'transaction_id' not in data:
        return jsonify({
            'status': False,
            'status_message': 'Transaction ID required'
        }), 400
    
    transaction_id = data['transaction_id']
    user = current_user
    
    # Get the pending withdrawal transaction
    transaction = Transaction.query.filter_by(
        id=transaction_id,
        user_id=user.id,
        transaction_type='withdraw',
        status='pending'
    ).first()
    
    if not transaction:
        return jsonify({
            'status': False,
            'status_message': 'Transaction not found or not pending'
        }), 404
    
    if not user.deposit_wallet_private_key:
        logger.error(f"No private key found for user {user.id}")
        return jsonify({
            'status': False,
            'status_message': 'Wallet not properly configured'
        }), 500
    
    try:
        # Decrypt the private key
        private_key_wif = decrypt_private_key(user.deposit_wallet_private_key)
        
        # Extract withdrawal details
        withdraw_address = transaction.details.get('withdraw_address')
        amount_sats = transaction.amount
        
        if not withdraw_address:
            return jsonify({
                'status': False,
                'status_message': 'Invalid withdrawal transaction'
            }), 400
        
        # Send the Bitcoin transaction
        # In production, you'd set appropriate fee and use real blockchain
        fee_sats = 5000  # Fixed fee for demo
        hot_wallet_address = withdraw_address  # Direct to user address for now

        sender = get_sender_func()
        txid = sender(private_key_wif, amount_sats, hot_wallet_address, fee_sats)
        
        if txid:
            # Update transaction status
            transaction.status = 'completed'
            # Ensure the details dictionary is mutable and changes are tracked
            if transaction.details is None:
                transaction.details = {}
            transaction.details['txid'] = txid
            flag_modified(transaction, "details") # Mark 'details' field as modified
            db.session.commit()
            
            logger.info(f"Withdrawal processed for user {user.id}: {txid}")
            
            return jsonify({
                'status': True,
                'status_message': 'Withdrawal processed',
                'txid': txid
            })
        else:
            transaction.status = 'failed'
            db.session.commit()
            
            return jsonify({
                'status': False,
                'status_message': 'Failed to broadcast transaction'
            }), 500
            
    except Exception as e:
        logger.error(f"Withdrawal processing failed for user {user.id}: {e}")
        transaction.status = 'failed'
        db.session.commit()
        
        return jsonify({
            'status': False,
            'status_message': 'Transaction processing failed'
        }), 500

@bitcoin_bp.route('/balance', methods=['GET'])
@jwt_required()
@rate_limit_by_ip("30 per hour")
def get_wallet_balance():
    """
    Get the balance of the user's Bitcoin wallet.
    In production, this would query the blockchain.
    """
    user = current_user
    
    if not user.deposit_wallet_address:
        return jsonify({
            'status': True,
            'address': None,
            'balance_sats': 0,
            'status_message': 'No wallet address configured'
        })
    
    # In production, query blockchain APIs for actual balance
    # For now, return placeholder data
    return jsonify({
        'status': True,
        'address': user.deposit_wallet_address,
        'balance_sats': 0,  # Would be real balance from blockchain
        'status_message': 'Balance retrieved (demo mode)'
    })
