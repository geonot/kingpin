from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from http import HTTPStatus

from ..models import db, User, PlinkoDropLog, Transaction # Relative import
from ..schemas import PlinkoPlayRequestSchema, PlinkoPlayResponseSchema # Relative import
from ..utils.plinko_helper import ( # Relative import
    validate_plinko_params, calculate_winnings,
    PAYOUT_MULTIPLIERS, SATOSHIS_PER_UNIT
)
from casino_be.exceptions import ValidationException, InsufficientFundsException
from casino_be.error_codes import ErrorCodes
from marshmallow import ValidationError # Import ValidationError

plinko_bp = Blueprint('plinko', __name__, url_prefix='/api/plinko')

@plinko_bp.route('/play', methods=['POST'])
@jwt_required()
def plinko_play():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user:
        current_app.logger.error(f"Plinko play attempt by non-existent user ID: {current_user_id}")
        return jsonify({'error': 'User not found after authentication.'}), HTTPStatus.INTERNAL_SERVER_ERROR

    try:
        json_data = request.get_json()
        if not json_data:
            # Let global handler for WerkzeugHTTPException handle this if it's a bad request.
            # Or raise ValidationException for consistent error format.
            raise ValidationException(status_message="Invalid JSON payload.")

        schema = PlinkoPlayRequestSchema()
        # Marshmallow load will raise ValidationError if validation fails
        loaded_data = schema.load(json_data) # This will raise ValidationError on issues
    except ValidationError as e: # Catch Marshmallow's ValidationError specifically
        # Let global handler process this. It expects details to be e.messages.
        raise ValidationException(status_message="Input validation failed.", details=e.messages)
    except Exception as e: # Catch other potential errors during JSON parsing or initial load
        current_app.logger.error(f"Unexpected error during Plinko request parsing for user {current_user_id}: {str(e)}", exc_info=True)
        raise ValidationException(status_message="Invalid request format.")


    stake_amount_float = loaded_data['stake_amount']
    chosen_stake_label = loaded_data['chosen_stake_label']
    slot_landed_label = loaded_data['slot_landed_label']

    # This validation can be removed if schema handles it fully, but good for defense in depth
    # Assuming validate_plinko_params raises ValidationException or returns a dict
    validation_result = validate_plinko_params(stake_amount_float, chosen_stake_label, slot_landed_label)
    if not validation_result['success']:
        # Convert this specific validation error into ValidationException
        specific_error_code = ErrorCodes.VALIDATION_ERROR
        if "Stake amount" in validation_result['error'] and "out of range" in validation_result['error']:
            specific_error_code = ErrorCodes.INVALID_AMOUNT
        raise ValidationException(status_message=validation_result['error'], error_code=specific_error_code)

    stake_amount_sats = int(stake_amount_float * SATOSHIS_PER_UNIT)

    if user.balance < stake_amount_sats:
        current_app.logger.warning(f"User {user.id} insufficient funds for Plinko: Balance {user.balance} sats, Stake {stake_amount_sats} sats")
        raise InsufficientFundsException(status_message='Insufficient funds for Plinko game.')

    try:
        multiplier = PAYOUT_MULTIPLIERS.get(slot_landed_label)
        if multiplier is None: # Should be caught by validate_plinko_params
            current_app.logger.error(f"Invalid slot_landed_label '{slot_landed_label}' made it past validation for user {user.id}.")
            return jsonify(PlinkoPlayResponseSchema().dump({
                'success': False, 'error': 'Internal error: Invalid slot outcome.'
            })), HTTPStatus.INTERNAL_SERVER_ERROR

        plinko_log = PlinkoDropLog(
            user_id=current_user_id,
            stake_amount=stake_amount_sats,
            chosen_stake_label=chosen_stake_label,
            slot_landed_label=slot_landed_label,
            multiplier_applied=multiplier,
            winnings_amount=0
        )
        db.session.add(plinko_log)
        db.session.flush()

        user.balance -= stake_amount_sats
        bet_transaction = Transaction(
            user_id=user.id,
            amount=-stake_amount_sats,
            transaction_type='plinko_bet',
            status='completed',
            details={'description': f'Plinko bet: {chosen_stake_label}, Landed: {slot_landed_label}'},
            plinko_drop_id=plinko_log.id
        )
        db.session.add(bet_transaction)

        winnings_sats = calculate_winnings(stake_amount_sats, slot_landed_label)
        plinko_log.winnings_amount = winnings_sats

        if winnings_sats > 0:
            user.balance += winnings_sats
            win_transaction = Transaction(
                user_id=user.id,
                amount=winnings_sats,
                transaction_type='plinko_win',
                status='completed',
                details={'description': f'Plinko win. Stake: {stake_amount_float}, Landed: {slot_landed_label}'},
                plinko_drop_id=plinko_log.id
            )
            db.session.add(win_transaction)

        db.session.commit()

        winnings_float = float(winnings_sats) / SATOSHIS_PER_UNIT
        new_balance_float = float(user.balance) / SATOSHIS_PER_UNIT

        current_app.logger.info(f"Plinko play successful for user {user.id}: Bet {stake_amount_float}, Won {winnings_float}. New balance: {new_balance_float}")

        response_data = {
            'success': True,
            'winnings': winnings_float,
            'new_balance': new_balance_float,
            'message': f"Bet {stake_amount_float} on {chosen_stake_label}, landed on {slot_landed_label}. Won {winnings_float}."
        }
        return jsonify(PlinkoPlayResponseSchema().dump(response_data)), HTTPStatus.OK

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Plinko play processing error for user {user.id}: {str(e)}", exc_info=True)
        return jsonify(PlinkoPlayResponseSchema().dump({
            'success': False,
            'error': 'An internal error occurred during game processing.'
        })), HTTPStatus.INTERNAL_SERVER_ERROR
