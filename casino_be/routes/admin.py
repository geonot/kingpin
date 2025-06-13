from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, current_user
from datetime import datetime, timezone # Import datetime and timezone
from sqlalchemy.orm.attributes import flag_modified # For JSON field updates if needed

from ..models import db, User, GameSession, Transaction, BonusCode, TransactionStatus # Import TransactionStatus
from ..schemas import (
    AdminUserSchema, UserListSchema, TransactionSchema, TransactionListSchema,
    BonusCodeSchema, BonusCodeListSchema, AdminCreditDepositSchema
)

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# Helper function moved from app.py
def is_admin():
    return current_user and current_user.is_admin

@admin_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def admin_dashboard():
    if not is_admin():
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    try:
        total_users = db.session.query(User.id).count()
        total_sessions = db.session.query(GameSession.id).count()
        total_transactions = db.session.query(Transaction.id).count()
        pending_withdrawals = db.session.query(Transaction.id).filter_by(status='pending', transaction_type='withdraw').count()
        total_bonus_codes = db.session.query(BonusCode.id).count()
        active_bonus_codes = db.session.query(BonusCode.id).filter_by(is_active=True).count()
        total_balance_sats = db.session.query(db.func.sum(User.balance)).scalar() or 0
        dashboard_data = {
            'total_users': total_users, 'total_sessions': total_sessions,
            'total_transactions': total_transactions, 'pending_withdrawals': pending_withdrawals,
            'total_bonus_codes': total_bonus_codes, 'active_bonus_codes': active_bonus_codes,
            'total_balance_sats': total_balance_sats
        }
        return jsonify({'status': True, 'dashboard_data': dashboard_data}), 200
    except Exception as e:
        current_app.logger.error(f"Admin dashboard error: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to retrieve admin dashboard data.'}), 500

@admin_bp.route('/users', methods=['GET'])
@jwt_required()
def admin_get_users():
    if not is_admin():
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        users_paginated = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        return jsonify({'status': True, 'users': UserListSchema().dump(users_paginated)}), 200
    except Exception as e:
        current_app.logger.error(f"Admin get users failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to retrieve users.'}), 500

@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@jwt_required()
def admin_get_user(user_id):
    if not is_admin():
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    try:
        user = User.query.get_or_404(user_id)
        return jsonify({'status': True, 'user': AdminUserSchema().dump(user)}), 200
    except Exception as e:
        current_app.logger.error(f"Admin get user {user_id} failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to retrieve user details.'}), 500

@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@jwt_required()
def admin_update_user(user_id):
    if not is_admin():
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    # Ensure 'balance' is excluded if it's part of AdminUserSchema and should not be updated here.
    # Schemas should ideally control what's loadable.
    schema = AdminUserSchema(partial=True, exclude=('password', 'deposit_wallet_private_key', 'deposit_wallet_address', 'balance'))
    errors = schema.validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400
    try:
        if 'email' in data and data['email'] != user.email:
            if User.query.filter(User.email == data['email'], User.id != user_id).first():
                return jsonify({'status': False, 'status_message': 'Email already in use.'}), 409

        # Iterate over validated data from the schema load, not raw data, if possible.
        # For now, using data.items() and checking hasattr.
        for key, value in data.items():
            # Prevent direct update of sensitive or internally managed fields.
            if hasattr(user, key) and key not in ['password', 'balance', 'deposit_wallet_address', 'deposit_wallet_private_key', 'id', 'created_at', 'updated_at', 'last_login_at']:
                setattr(user, key, value)

        db.session.commit()
        current_app.logger.info(f"Admin {current_user.id} updated user {user_id}")
        return jsonify({'status': True, 'user': AdminUserSchema().dump(user)}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin update user {user_id} failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to update user.'}), 500

@admin_bp.route('/transactions', methods=['GET'])
@jwt_required()
def admin_get_transactions():
    if not is_admin():
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        query = Transaction.query.order_by(Transaction.created_at.desc())

        user_id_filter = request.args.get('user_id', type=int)
        type_filter = request.args.get('type')
        status_filter = request.args.get('status')

        if user_id_filter:
            query = query.filter(Transaction.user_id == user_id_filter)
        if type_filter:
            query = query.filter(Transaction.transaction_type == type_filter)
        if status_filter:
            query = query.filter(Transaction.status == status_filter)

        transactions_paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        return jsonify({'status': True, 'transactions': TransactionListSchema().dump(transactions_paginated)}), 200
    except Exception as e:
        current_app.logger.error(f"Admin get transactions failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to retrieve transactions.'}), 500

@admin_bp.route('/transactions/<int:tx_id>', methods=['PUT'])
@jwt_required()
def admin_update_transaction(tx_id):
    if not is_admin():
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    transaction = Transaction.query.get_or_404(tx_id)
    data = request.get_json()

    allowed_updates = ['status', 'details'] # Define what admin can update
    update_data = {k: v for k, v in data.items() if k in allowed_updates}

    if not update_data:
        return jsonify({'status': False, 'status_message': 'No valid fields for update.'}), 400

    if transaction.transaction_type == 'withdraw' and 'status' in update_data:
        new_status = update_data['status']
        admin_notes = data.get('admin_notes') # Get admin_notes if provided

        details_update = transaction.details or {}
        if admin_notes:
            details_update['admin_notes'] = admin_notes

        if transaction.status == 'pending' and new_status == 'completed':
            transaction.status = 'completed'
            transaction.details = details_update
            current_app.logger.info(f"Admin {current_user.id} approved withdrawal {tx_id}")
        elif transaction.status == 'pending' and new_status == 'rejected':
            user = User.query.get(transaction.user_id)
            if user:
                user.balance += transaction.amount # Refund
                transaction.status = 'rejected'
                transaction.details = details_update
                current_app.logger.info(f"Admin {current_user.id} rejected withdrawal {tx_id}, refunded {transaction.amount} to user {user.id}")
            else:
                 return jsonify({'status': False, 'status_message': 'User not found for refund.'}), 500
        elif transaction.status != 'pending':
             return jsonify({'status': False, 'status_message': 'Cannot change status of processed withdrawal.'}), 400
        else:
             return jsonify({'status': False, 'status_message': 'Invalid status transition for withdrawal.'}), 400
    elif 'status' in update_data:
        # If it's not a withdrawal, but status is in update_data, it's disallowed by current logic
         return jsonify({'status': False, 'status_message': 'Status update not allowed for this transaction type directly.'}), 400

    if 'details' in update_data and isinstance(update_data['details'], dict) and transaction.transaction_type != 'withdraw':
        # For non-withdrawal transactions, allow general detail updates if needed
        # Ensure not to overwrite admin_notes if it was part of withdrawal logic
        current_details = transaction.details or {}
        current_details.update(update_data['details'])
        transaction.details = current_details

    try:
        db.session.commit()
        return jsonify({'status': True, 'transaction': TransactionSchema().dump(transaction)}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin update transaction {tx_id} failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to update transaction.'}), 500

@admin_bp.route('/credit_deposit', methods=['POST'])
@jwt_required()
def admin_credit_deposit():
    if not is_admin():
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    data = request.get_json()
    schema = AdminCreditDepositSchema()
    try:
        validated_data = schema.load(data)
    except Exception as e: # Marshmallow ValidationError
        return jsonify({'status': False, 'status_message': e.messages if hasattr(e, 'messages') else str(e)}), 400

    user_id = validated_data['user_id']
    amount_sats = validated_data['amount_sats']
    external_tx_id = validated_data.get('external_tx_id')
    admin_notes = validated_data.get('admin_notes')

    user = User.query.get(user_id)
    if not user:
        return jsonify({'status': False, 'status_message': f'User {user_id} not found.'}), 404
    try:
        user.balance += amount_sats
        transaction_details = {'credited_by_admin_id': current_user.id, 'credited_by_admin_username': current_user.username}
        if external_tx_id:
            transaction_details['external_tx_id'] = external_tx_id
        if admin_notes:
            transaction_details['admin_notes'] = admin_notes

        deposit_tx = Transaction(user_id=user.id, amount=amount_sats, transaction_type='deposit', status='completed', details=transaction_details)
        db.session.add(deposit_tx)
        db.session.commit()
        current_app.logger.info(f"Admin {current_user.username} credited {amount_sats} to user {user.username} (ID: {user.id})")
        return jsonify({'status': True, 'status_message': 'Deposit credited.', 'user_id': user.id, 'new_balance_sats': user.balance, 'transaction_id': deposit_tx.id}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin credit deposit failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to credit deposit.'}), 500

@admin_bp.route('/bonus_codes', methods=['GET'])
@jwt_required()
def admin_get_bonus_codes():
    if not is_admin():
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        codes_paginated = BonusCode.query.order_by(BonusCode.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        return jsonify({'status': True, 'bonus_codes': BonusCodeListSchema().dump(codes_paginated)}), 200
    except Exception as e:
        current_app.logger.error(f"Admin get bonus codes failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to retrieve bonus codes.'}), 500

@admin_bp.route('/bonus_codes', methods=['POST'])
@jwt_required()
def admin_create_bonus_code():
    if not is_admin():
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    data = request.get_json()
    schema = BonusCodeSchema(context={'check_unique': True}) # Pass context for uniqueness check
    try:
        validated_data = schema.load(data) # Marshmallow handles validation
    except Exception as e: # Marshmallow ValidationError
         return jsonify({'status': False, 'status_message': e.messages if hasattr(e, 'messages') else str(e)}), 400

    try:
        # new_code = schema.load(data, session=db.session) # This was old way before explicit validation
        new_code = BonusCode(**validated_data)
        db.session.add(new_code)
        db.session.commit()
        current_app.logger.info(f"Admin {current_user.id} created bonus code {new_code.id}") # Use new_code.id
        return jsonify({'status': True, 'bonus_code': BonusCodeSchema().dump(new_code)}), 201
    except Exception as e: # Handles potential IntegrityError if code is not unique despite schema check (race condition)
        db.session.rollback()
        current_app.logger.error(f"Admin create bonus code failed: {str(e)}", exc_info=True)
        # Check if it's a known unique constraint violation
        if "UNIQUE constraint failed: bonus_code.code" in str(e) or "Duplicate entry" in str(e):
             return jsonify({'status': False, 'status_message': {'code': ['Bonus code already exists.']}}), 409
        return jsonify({'status': False, 'status_message': 'Failed to create bonus code due to a server error.'}), 500

@admin_bp.route('/bonus_codes/<int:code_id_param>', methods=['PUT']) # Renamed path param to avoid conflict
@jwt_required()
def admin_update_bonus_code(code_id_param):
    if not is_admin():
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403

    bonus_code = BonusCode.query.get_or_404(code_id_param)
    data = request.get_json()

    # Exclude 'code' from updates if it's meant to be immutable after creation
    # Pass instance to schema for update, ensure code uniqueness if it were changeable
    schema = BonusCodeSchema(partial=True, exclude=('id', 'code'), context={'instance_id': bonus_code.id})

    try:
        validated_data = schema.load(data, partial=True)
    except Exception as e: # Marshmallow ValidationError
        return jsonify({'status': False, 'status_message': e.messages if hasattr(e, 'messages') else str(e)}), 400

    try:
        for key, value in validated_data.items():
            setattr(bonus_code, key, value)
        db.session.commit()
        current_app.logger.info(f"Admin {current_user.id} updated bonus code {bonus_code.id}")
        return jsonify({'status': True, 'bonus_code': BonusCodeSchema().dump(bonus_code)}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin update bonus code {code_id_param} failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to update bonus code.'}), 500

@admin_bp.route('/bonus_codes/<int:code_id_param>', methods=['DELETE']) # Renamed path param
@jwt_required()
def admin_delete_bonus_code(code_id_param):
    if not is_admin():
        return jsonify({'status': False, 'status_message': 'Access denied'}), 403
    bonus_code = BonusCode.query.get_or_404(code_id_param)
    try:
        db.session.delete(bonus_code)
        db.session.commit()
        current_app.logger.info(f"Admin {current_user.id} deleted bonus code {code_id_param}")
        return jsonify({'status': True, 'status_message': 'Bonus code deleted.'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin delete bonus code {code_id_param} failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to delete bonus code.'}), 500

@admin_bp.route('/withdrawals/<int:tx_id>/approve', methods=['PUT'])
@jwt_required()
def admin_approve_withdrawal_request(tx_id):
    if not is_admin():
        return jsonify({'status': False, 'status_message': 'Access denied. Admin privileges required.'}), 403

    transaction = Transaction.query.get(tx_id)
    if not transaction:
        return jsonify({'status': False, 'status_message': f'Transaction with ID {tx_id} not found.'}), 404

    if transaction.transaction_type != 'withdraw':
        return jsonify({
            'status': False,
            'status_message': f'Transaction {tx_id} is not a withdrawal type (type: {transaction.transaction_type}). Cannot approve.'
        }), 400

    if transaction.status != TransactionStatus.VALIDATING:
        return jsonify({
            'status': False,
            'status_message': f'Withdrawal request {tx_id} is not in VALIDATING status. Current status: {transaction.status.value}. Cannot approve.'
        }), 400

    try:
        transaction.status = TransactionStatus.PENDING_APPROVAL

        details = transaction.details or {}
        details['admin_stage1_approved_at'] = datetime.now(timezone.utc).isoformat()
        details['admin_stage1_approved_by_id'] = current_user.id
        details['admin_stage1_approved_by_username'] = current_user.username

        transaction.details = details
        # If issues with JSON updates, uncomment the following:
        # flag_modified(transaction, "details")

        db.session.add(transaction) # Ensure transaction is added to session if it was detached or if it's a new context
        db.session.commit()

        current_app.logger.info(f"Admin {current_user.username} (ID: {current_user.id}) approved withdrawal request {tx_id} (Stage 1). Status changed to PENDING_APPROVAL.")
        return jsonify({'status': True, 'transaction': TransactionSchema().dump(transaction)}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during admin approval of withdrawal {tx_id}: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'An error occurred while approving the withdrawal request.'}), 500
