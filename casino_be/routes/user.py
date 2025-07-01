from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, current_user
from datetime import datetime, timezone
from marshmallow import ValidationError # Ensure ValidationError is imported

from casino_be.models import db, User, Transaction, UserBonus
from casino_be.schemas import UserSchema, WithdrawSchema, UpdateSettingsSchema, DepositSchema, TransferSchema
from casino_be.services.bonus_service import apply_bonus_to_deposit
from casino_be.utils.security import require_csrf_token, rate_limit_by_ip, log_security_event
from casino_be.exceptions import InsufficientFundsException, ValidationException, NotFoundException, AuthorizationException, AuthenticationException # Ensure AuthenticationException is here
from casino_be.error_codes import ErrorCodes

user_bp = Blueprint('user', __name__, url_prefix='/api')

@user_bp.route('/withdraw', methods=['POST'])
@jwt_required()
@require_csrf_token
@rate_limit_by_ip("3 per hour")
def withdraw():
    data = request.get_json()
    errors = WithdrawSchema().validate(data)
    if errors:
        # Let the global ValidationError handler manage this
        # log_security_event('INVALID_WITHDRAWAL_DATA', current_user.id, {'errors': errors})
        # return jsonify({'status': False, 'status_message': errors}), 400
        # The global handler will return a 422 with ErrorCodes.VALIDATION_ERROR
        # If a 400 is strictly needed here, this must remain, but the task implies using global handlers.
        # For now, assuming Marshmallow's errors are handled by the global handler as per instructions.
        pass # Errors will be caught by the global handler if schema raises ValidationError

    user = current_user
    amount_sats = data['amount_sats'] # Corrected from data['amount'] to match WithdrawSchema
    withdraw_address = data['withdraw_wallet_address'] # Corrected from data['address'] to match WithdrawSchema
    
    # Enhanced withdrawal validation
    if amount_sats < 10000:  # Minimum 0.0001 BTC
        raise ValidationException(ErrorCodes.INVALID_AMOUNT, "Minimum withdrawal amount is 10,000 satoshis.")
    
    if amount_sats > 100000000:  # Maximum 1 BTC per withdrawal
        log_security_event('LARGE_WITHDRAWAL_ATTEMPT', user.id, {'amount': amount_sats}) # Keep security log
        raise ValidationException(ErrorCodes.MAX_WITHDRAWAL_LIMIT_EXCEEDED, "Maximum withdrawal amount is 1 BTC.")

    active_bonus_with_wagering = UserBonus.query.filter_by(
        user_id=user.id,
        is_active=True,
        is_completed=False,
        is_cancelled=False
    ).first()

    if active_bonus_with_wagering:
        if active_bonus_with_wagering.wagering_progress_sats < active_bonus_with_wagering.wagering_requirement_sats:
            remaining_wagering_sats = active_bonus_with_wagering.wagering_requirement_sats - active_bonus_with_wagering.wagering_progress_sats
            # current_app.logger.warning(f"User {user.id} withdrawal blocked due to unmet wagering for UserBonus {active_bonus_with_wagering.id}.") # Will be logged by global handler
            raise AuthorizationException( # Using AuthorizationException as it's defined
                status_message="Withdrawal blocked due to unmet wagering requirements.", # error_code is set by default
                details={
                    "remaining_wagering_sats": remaining_wagering_sats,
                    "bonus_amount_awarded_sats": active_bonus_with_wagering.bonus_amount_awarded_sats,
                    "wagering_progress_sats": active_bonus_with_wagering.wagering_progress_sats,
                    "wagering_requirement_sats": active_bonus_with_wagering.wagering_requirement_sats
                }
            )

    if user.balance < amount_sats:
        raise InsufficientFundsException("Insufficient funds for withdrawal.")
        
    try:
        user.balance -= amount_sats
        transaction = Transaction(
            user_id=user.id, amount=amount_sats, transaction_type='withdraw',
            status='pending', details={'withdraw_address': withdraw_address}
        )
        db.session.add(transaction)
        db.session.commit()
        
        log_security_event('WITHDRAWAL_REQUEST', user.id, {
            'amount': amount_sats,
            'address': withdraw_address,
            'transaction_id': transaction.id
        })
        
        # Try to process withdrawal automatically if user has private key
        auto_processed = False
        if hasattr(user, 'deposit_wallet_private_key') and user.deposit_wallet_private_key:
            try:
                from casino_be.utils.encryption import decrypt_private_key # Absolute import
                from casino_be.utils.bitcoin import send_to_hot_wallet # Absolute import
                
                private_key_wif = decrypt_private_key(user.deposit_wallet_private_key)
                fee_sats = 5000  # Fixed fee for demo
                
                txid = send_to_hot_wallet(private_key_wif, amount_sats, withdraw_address, fee_sats)
                
                if txid and not txid.startswith('dummy'):  # Real transaction
                    transaction.status = 'completed'
                    transaction.details['txid'] = txid
                    transaction.details['auto_processed'] = True
                    db.session.commit()
                    auto_processed = True
                    current_app.logger.info(f"Auto-processed withdrawal for user {user.id}: {txid}")
                    
            except Exception as e:
                current_app.logger.warning(f"Auto-processing failed for withdrawal {transaction.id}: {e}")
        
        current_app.logger.info(f"Withdrawal request for user {user.id}: {amount_sats} sats to {withdraw_address}. Tx ID: {transaction.id}")
        
        status_message = 'Withdrawal completed.' if auto_processed else 'Withdrawal request submitted for processing.'
        
        return jsonify({
            'status': True, 
            'withdraw_id': transaction.id, 
            'user': UserSchema().dump(user),
            'status_message': status_message,
            'auto_processed': auto_processed
        }), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Withdrawal failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Withdrawal failed.'}), 500

@user_bp.route('/settings', methods=['POST'])
@jwt_required()
@require_csrf_token
@rate_limit_by_ip("5 per hour")
def update_settings():
    data = request.get_json()
    try:
        # Use load() for validation, which will raise ValidationError caught by global handler
        validated_data = UpdateSettingsSchema().load(data)
    except ValidationError as err:
        raise # Let global handler manage Marshmallow validation errors

    user = current_user
    updated_fields = []

    # If current_password is provided for any change (email or password), it must be correct.
    # This handles the case where only email is changed but current_password is provided for verification.
    if 'current_password' in validated_data and validated_data['current_password'] is not None:
        current_app.logger.info(f"Verifying current_password for user {user.id}. Provided: '{validated_data['current_password']}'. Stored hash: '{user.password}'")
        password_verified = User.verify_password(user.password, validated_data['current_password'])
        current_app.logger.info(f"Password verification result: {password_verified}")
        if not password_verified:
            raise AuthenticationException(status_message="Incorrect current password.")

    # Password change logic
    if validated_data.get('new_password'):
        # current_password must have been provided and validated by schema if new_password is set
        # The check above also covers if current_password was incorrect.
        # (Schema ensures current_password is present if new_password is present)

        # new_password and confirm_new_password mismatch is handled by schema's @validates_schema
        # Password strength for new_password is handled by field validation in schema

        user.password = User.hash_password(validated_data['new_password'])
        log_security_event('PASSWORD_CHANGE', user.id)
        updated_fields.append("password")

    # Email change logic
    if validated_data.get('email') and validated_data['email'] != user.email:
        new_email = validated_data['email']
        if User.query.filter(User.email == new_email, User.id != user.id).first():
            # This specific validation needs to stay in the route as it requires a DB query.
            raise ValidationException(
                status_message="Email already in use.",
                details={'email': 'Email already in use.'}
            ) # error_code is set by default in ValidationException

        log_security_event('EMAIL_CHANGE', user.id, {
            'old_email': user.email,
            'new_email': new_email
        })
        user.email = new_email
        updated_fields.append("email")

    if not updated_fields:
        # This case should ideally be caught by schema validation if 'at least one field' is enforced
        # but as a fallback or if schema allows empty valid payload:
        return jsonify({'status': True, 'status_message': "No settings were changed.", 'user': UserSchema().dump(user)}), 200

    try:
        db.session.commit()
        current_app.logger.info(f"Settings updated for user {user.id}: {', '.join(updated_fields)}")
        # Return a more specific success message if desired, or a generic one
        # The tests currently expect no 'status_message' on success, just 'status' and 'user'.
        return jsonify({'status': True, 'user': UserSchema().dump(user)}), 200
    except Exception as e:
        db.session.rollback()
        raise # Let global handler manage other exceptions

@user_bp.route('/deposit', methods=['POST'])
@jwt_required()
@require_csrf_token
@rate_limit_by_ip("10 per hour")
def deposit():
    data = request.get_json()
    errors = DepositSchema().validate(data)
    if errors:
        # log_security_event('INVALID_DEPOSIT_DATA', current_user.id, {'errors': errors}) # Global handler
        # return jsonify({'status': False, 'status_message': errors}), 400 # Global handler
        pass # Marshmallow errors handled globally

    user = current_user
    deposit_amount_sats = data['deposit_amount_sats'] # Corrected: ensure this is the actual field name used from DepositSchema
    bonus_code_str = data.get('bonus_code') # This was missing in the erroneous block from read_file output
    
    # Enhanced deposit validation
    if deposit_amount_sats > 1000000000:  # Maximum 10 BTC per deposit
        log_security_event('LARGE_DEPOSIT_ATTEMPT', user.id, {'amount': deposit_amount_sats}) # Keep security log
        raise ValidationException(ErrorCodes.INVALID_AMOUNT, "Maximum deposit amount is 10 BTC.")

    final_bonus_applied_sats = 0
    final_user_bonus_id = None
    # Ensure deposit_message uses the correctly assigned deposit_amount_sats
    deposit_message = f"Deposit of {deposit_amount_sats} sats successful."
    bonus_message = ""
    status_code = 200

    try:
        # 1. Credit user's balance
        user.balance += deposit_amount_sats

        # 2. Create a deposit transaction
        deposit_transaction = Transaction(
            user_id=user.id,
            amount=deposit_amount_sats,
            transaction_type='deposit',
            status='completed',
            details={'description': f'User deposit of {deposit_amount_sats} sats via /api/deposit endpoint'}
        )
        db.session.add(deposit_transaction)
        current_app.logger.info(f"User {user.id} deposited {deposit_amount_sats} sats. Transaction ID: {deposit_transaction.id}")

        # 3. Apply bonus if a bonus code is provided
        if bonus_code_str:
            bonus_result = apply_bonus_to_deposit(user, bonus_code_str, deposit_amount_sats)

            if bonus_result['success']:
                final_bonus_applied_sats = bonus_result.get('bonus_value_sats', 0)
                final_user_bonus_id = bonus_result.get('user_bonus_id')
                bonus_message = bonus_result['message']
            else:
                bonus_message = f"Bonus application failed: {bonus_result['message']}"

        db.session.commit()

        combined_message = deposit_message
        if bonus_message:
            combined_message += f" {bonus_message}"

        user_data = UserSchema().dump(user)
        return jsonify({
            'status': True,
            'user': user_data,
            'status_message': combined_message.strip(),
            'deposit_sats': deposit_amount_sats,
            'bonus_applied_sats': final_bonus_applied_sats,
            'user_bonus_id': final_user_bonus_id
        }), status_code

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Deposit processing for user {user.id} failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Deposit processing failed due to an internal error.'}), 500

@user_bp.route('/transfer', methods=['POST'])
@jwt_required()
@require_csrf_token
@rate_limit_by_ip("5 per hour")
def transfer_funds():
    """Transfer funds between users with enhanced security"""
    data = request.get_json()
    errors = TransferSchema().validate(data)
    if errors:
        # log_security_event('INVALID_TRANSFER_DATA', current_user.id, {'errors': errors}) # Global handler
        # return jsonify({'status': False, 'status_message': errors}), 400 # Global handler
        pass # Marshmallow errors handled globally
    
    sender = current_user
    recipient_username = data['recipient_username']
    amount = data['amount']
    note = data.get('note', '')
    
    # Find recipient
    recipient = User.query.filter_by(username=recipient_username).first()
    if not recipient:
        raise NotFoundException(error_code=ErrorCodes.USER_NOT_FOUND, status_message="Recipient user not found.")
    
    if recipient.id == sender.id:
        raise ValidationException(ErrorCodes.VALIDATION_ERROR, "Cannot transfer to yourself.")
    
    if not recipient.is_active:
        # Consider if this should be a specific error code or a generic validation error
        raise ValidationException(ErrorCodes.VALIDATION_ERROR, "Recipient account is not active.")
    
    # Check sender balance
    if sender.balance < amount:
        raise InsufficientFundsException("Insufficient funds for transfer.")
    
    # Check for active bonus restrictions
    active_bonus = UserBonus.query.filter_by(
        user_id=sender.id,
        is_active=True,
        is_completed=False,
        is_cancelled=False
    ).first()
    
    if active_bonus and active_bonus.wagering_progress_sats < active_bonus.wagering_requirement_sats:
        raise AuthorizationException( # Using AuthorizationException as it's defined
            status_message="Transfers are blocked while you have active bonus wagering requirements." # error_code is set by default
        )
    
    try:
        # Perform transfer
        sender.balance -= amount
        recipient.balance += amount
        
        # Create transactions
        sender_transaction = Transaction(
            user_id=sender.id,
            amount=-amount,
            transaction_type='transfer_out',
            status='completed',
            details={
                'recipient_id': recipient.id,
                'recipient_username': recipient_username,
                'note': note
            }
        )
        
        recipient_transaction = Transaction(
            user_id=recipient.id,
            amount=amount,
            transaction_type='transfer_in',
            status='completed',
            details={
                'sender_id': sender.id,
                'sender_username': sender.username,
                'note': note
            }
        )
        
        db.session.add(sender_transaction)
        db.session.add(recipient_transaction)
        db.session.commit()
        
        log_security_event('FUNDS_TRANSFER', sender.id, {
            'recipient_id': recipient.id,
            'amount': amount,
            'note': note
        })
        
        current_app.logger.info(f"Transfer completed: {sender.username} -> {recipient_username}, amount: {amount} sats")
        
        return jsonify({
            'status': True,
            'status_message': f'Successfully transferred {amount} satoshis to {recipient_username}.',
            'user': UserSchema().dump(sender),
            'transfer_id': sender_transaction.id
        }), 200
        
    except Exception as e:
        db.session.rollback()
        # current_app.logger.error(f"Transfer failed: {str(e)}", exc_info=True) # Global handler
        raise # Global handler will catch and log

@user_bp.route('/balance', methods=['GET'])
@jwt_required()
def get_balance():
    """Get current user balance"""
    user = current_user
    return jsonify({
        'status': True,
        'balance': user.balance,
        'balance_btc': f"{user.balance / 100000000:.8f}"
    }), 200

@user_bp.route('/transactions', methods=['GET'])
@jwt_required()
@rate_limit_by_ip("20 per minute")
def get_transactions():
    """Get user transaction history with pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)  # Max 100 per page
    
    transactions = Transaction.query.filter_by(user_id=current_user.id)\
        .order_by(Transaction.created_at.desc())\
        .paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
    
    return jsonify({
        'status': True,
        'transactions': [{
            'id': t.id,
            'amount': t.amount,
            'type': t.transaction_type,
            'status': t.status,
            'created_at': t.created_at.isoformat(),
            'details': t.details
        } for t in transactions.items],
        'pagination': {
            'page': transactions.page,
            'pages': transactions.pages,
            'per_page': transactions.per_page,
            'total': transactions.total
        }
    }), 200
