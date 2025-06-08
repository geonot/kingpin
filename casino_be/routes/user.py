from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, current_user
from datetime import datetime, timezone

from models import db, User, Transaction, UserBonus
from schemas import UserSchema, WithdrawSchema, UpdateSettingsSchema, DepositSchema
from services.bonus_service import apply_bonus_to_deposit

user_bp = Blueprint('user', __name__, url_prefix='/api')

@user_bp.route('/withdraw', methods=['POST'])
@jwt_required()
def withdraw():
    # Apply rate limiting using current_app
    limiter = current_app.extensions.get('limiter')
    if limiter:
        limiter.check()

    data = request.get_json()
    errors = WithdrawSchema().validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400
    user = current_user
    amount_sats = data['amount_sats']
    withdraw_address = data['withdraw_wallet_address']
    if not isinstance(amount_sats, int) or amount_sats <= 0:
         return jsonify({'status': False, 'status_message': 'Invalid withdrawal amount.'}), 400

    active_bonus_with_wagering = UserBonus.query.filter_by(
        user_id=user.id,
        is_active=True,
        is_completed=False,
        is_cancelled=False
    ).first()

    if active_bonus_with_wagering:
        if active_bonus_with_wagering.wagering_progress_sats < active_bonus_with_wagering.wagering_requirement_sats:
            remaining_wagering_sats = active_bonus_with_wagering.wagering_requirement_sats - active_bonus_with_wagering.wagering_progress_sats
            current_app.logger.warning(f"User {user.id} withdrawal blocked due to unmet wagering for UserBonus {active_bonus_with_wagering.id}.")
            return jsonify({
                'status': False,
                'status_message': f"Withdrawal blocked. You have an active bonus with unmet wagering requirements. "
                                  f"Remaining wagering needed: {remaining_wagering_sats} sats. "
                                  f"Bonus amount: {active_bonus_with_wagering.bonus_amount_awarded_sats} sats. "
                                  f"Wagering progress: {active_bonus_with_wagering.wagering_progress_sats}/{active_bonus_with_wagering.wagering_requirement_sats} sats."
            }), 403

    if user.balance < amount_sats:
        return jsonify({'status': False, 'status_message': 'Insufficient funds'}), 400
    try:
        user.balance -= amount_sats
        transaction = Transaction(
            user_id=user.id, amount=amount_sats, transaction_type='withdraw',
            status='pending', details={'withdraw_address': withdraw_address}
        )
        db.session.add(transaction)
        db.session.commit()
        current_app.logger.info(f"Withdrawal request for user {user.id}: {amount_sats} sats to {withdraw_address}. Tx ID: {transaction.id}")
        return jsonify({
            'status': True, 'withdraw_id': transaction.id, 'user': UserSchema().dump(user),
            'status_message': 'Withdrawal request submitted.'
        }), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Withdrawal failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Withdrawal failed.'}), 500

@user_bp.route('/settings', methods=['POST'])
@jwt_required()
def update_settings():
    data = request.get_json()
    errors = UpdateSettingsSchema().validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400
    user = current_user
    try:
        if 'email' in data and data['email'] != user.email:
            if User.query.filter(User.email == data['email'], User.id != user.id).first():
                return jsonify({'status': False, 'status_message': 'Email already in use.'}), 409
            user.email = data['email']
        if 'password' in data and data['password']:
            user.password = User.hash_password(data['password'])
        db.session.commit()
        current_app.logger.info(f"Settings updated for user {user.id}")
        return jsonify({'status': True, 'user': UserSchema().dump(user)}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Settings update failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Settings update failed.'}), 500

@user_bp.route('/deposit', methods=['POST'])
@jwt_required()
def deposit():
    data = request.get_json()
    errors = DepositSchema().validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400

    user = current_user
    deposit_amount_sats = data['deposit_amount_sats']
    bonus_code_str = data.get('bonus_code')

    final_bonus_applied_sats = 0
    final_user_bonus_id = None
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
