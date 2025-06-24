from decimal import Decimal, ROUND_HALF_UP # For precise calculations
from flask import current_app # To access logger if needed, or pass logger
# Assuming 'casino_be' is the root package for the application context
# For tools, direct relative imports like 'from ..models' are usually preferred if the structure is flat.
# If 'casino_be' is not directly in python path but a sub-module is, this might need adjustment.
# For this context, we'll assume the structure allows 'from ..models'.
from casino_be.models import db, User, BonusCode, UserBonus, Transaction

def apply_bonus_to_deposit(user: User, bonus_code_str: str, requested_deposit_amount_sats: int | None):
    '''
    Handles the logic for applying a bonus code during a deposit.

    Args:
        user: The user object applying for the bonus.
        bonus_code_str: The bonus code string entered by the user.
        requested_deposit_amount_sats: The amount of the deposit, if relevant for the bonus.

    Returns:
        A dictionary with:
        - 'success': True if bonus applied successfully or no bonus was applicable, False on error.
        - 'bonus_value_sats': The value of the bonus awarded in satoshis.
        - 'user_bonus_id': The ID of the created UserBonus record, if any.
        - 'message': A status message (e.g., 'Bonus applied', 'Invalid code', 'User has active bonus').
        - 'status_code': HTTP status code suggestion for the response.
        - 'bonus_code_obj': The BonusCode object if found and valid (optional, for logging or further use by caller)
    '''
    logger = current_app.logger # Use Flask's current_app logger

    bonus_code = BonusCode.query.filter_by(code_id=bonus_code_str.strip().upper(), is_active=True).first()

    if not bonus_code:
        return {'success': False, 'bonus_value_sats': 0, 'user_bonus_id': None, 'message': 'Invalid or expired bonus code', 'status_code': 400, 'bonus_code_obj': None}

    # Check if user already has an active, non-cancelled bonus
    active_user_bonus = UserBonus.query.filter_by(
        user_id=user.id,
        is_active=True,
        is_cancelled=False
    ).first()
    if active_user_bonus:
        logger.warning(f"User {user.id} attempted to apply bonus '{bonus_code_str}' while already having an active bonus {active_user_bonus.id}.")
        return {'success': False, 'bonus_value_sats': 0, 'user_bonus_id': None, 'message': 'You already have an active bonus. Please complete or cancel it before applying a new one.', 'status_code': 400, 'bonus_code_obj': bonus_code}

    bonus_value_sats = 0
    calculated_wagering_req_sats = 0
    new_user_bonus_id = None

    if bonus_code.subtype == 'percentage':
        if requested_deposit_amount_sats and requested_deposit_amount_sats > 0:
            if bonus_code.amount and bonus_code.amount > 0:
                # Use Decimal for precision with percentages
                bonus_val = (Decimal(requested_deposit_amount_sats) * (Decimal(bonus_code.amount) / Decimal(100))).to_integral_value(rounding=ROUND_HALF_UP)
                bonus_value_sats = int(bonus_val)
                logger.info(f"Calculated percentage bonus: {bonus_value_sats} sats from {requested_deposit_amount_sats} sats at {bonus_code.amount}%.")
            else:
                logger.warning(f"Percentage bonus code {bonus_code.code_id} has invalid percentage amount: {bonus_code.amount}. Bonus value set to 0.")
        else: # Percentage bonus requires a deposit amount to calculate against
            logger.warning(f"Percentage bonus code {bonus_code.code_id} applied, but no valid deposit_amount_sats provided for user {user.id}. Bonus value set to 0.")
            return {'success': True, 'bonus_value_sats': 0, 'user_bonus_id': None, 'message': 'Percentage bonus not applied: deposit_amount_sats is required for this bonus.', 'status_code': 200, 'bonus_code_obj': bonus_code}

    elif bonus_code.subtype == 'fixed':
        if bonus_code.amount_sats and bonus_code.amount_sats > 0:
            bonus_value_sats = int(bonus_code.amount_sats)
        else:
            logger.warning(f"Fixed bonus code {bonus_code.code_id} has invalid amount_sats: {bonus_code.amount_sats}. Bonus value set to 0.")

    elif bonus_code.subtype == 'spins':
        logger.info(f"Bonus code {bonus_code.code_id} is for 'spins' and does not award a direct monetary value via this function for user {user.id}.")
        return {'success': True, 'bonus_value_sats': 0, 'user_bonus_id': None, 'message': "Spins bonus code does not award direct monetary value here.", 'status_code': 200, 'bonus_code_obj': bonus_code}

    else:
        logger.error(f"Unknown bonus subtype '{bonus_code.subtype}' for code {bonus_code_str} (ID: {bonus_code.id}) user {user.id}")
        return {'success': False, 'bonus_value_sats': 0, 'user_bonus_id': None, 'message': 'Invalid bonus code type.', 'status_code': 400, 'bonus_code_obj': bonus_code}

    if bonus_value_sats > 0:
        multiplier = bonus_code.wagering_requirement_multiplier
        if multiplier is not None and multiplier > 0:
            calculated_wagering_req_sats = int(Decimal(bonus_value_sats) * Decimal(multiplier))

        new_user_bonus = UserBonus(
            user_id=user.id,
            bonus_code_id=bonus_code.id,
            bonus_amount_awarded_sats=bonus_value_sats,
            wagering_requirement_sats=calculated_wagering_req_sats,
            is_active=True,
            is_completed=False,
            is_cancelled=False
        )
        db.session.add(new_user_bonus)
        db.session.flush() # To get new_user_bonus.id
        new_user_bonus_id = new_user_bonus.id

        user.balance += bonus_value_sats # Modify user object directly

        transaction_details = {
            'bonus_code_id': bonus_code.id,
            'bonus_code': bonus_code.code_id,
            'description': f"Bonus applied: {bonus_code.description or bonus_code.code_id}",
            'user_bonus_id': new_user_bonus_id
        }
        bonus_transaction = Transaction(
            user_id=user.id, amount=bonus_value_sats, transaction_type='bonus',
            status='completed', details=transaction_details
        )
        db.session.add(bonus_transaction)

        if bonus_code.uses_remaining is not None:
            bonus_code.uses_remaining = max(0, bonus_code.uses_remaining - 1)

        logger.info(f"Bonus code '{bonus_code_str}' (UserBonus ID: {new_user_bonus_id}) applied for user {user.id}. Value: {bonus_value_sats} sats. Session will be committed by caller.")
        return {'success': True, 'bonus_value_sats': bonus_value_sats, 'user_bonus_id': new_user_bonus_id, 'message': f'Bonus of {bonus_value_sats} sats applied.', 'status_code': 200, 'bonus_code_obj': bonus_code}

    elif bonus_code.subtype == 'fixed': # Only for fixed, as percentage already returned if deposit amount was missing.
         logger.warning(f"Calculated bonus value is zero for fixed bonus code {bonus_code_str}, user {user.id}.")
         # This is a success=True case because the code was valid, just yielded no value.
         return {'success': True, 'bonus_value_sats': 0, 'user_bonus_id': None, 'message': 'No monetary bonus value for this code.', 'status_code': 200, 'bonus_code_obj': bonus_code}

    # Fallback for any other case where bonus_value_sats is 0 but not an error or specific message handled above.
    # This can happen if a percentage bonus has 0 amount, or fixed bonus has 0 amount_sats.
    logger.info(f"No monetary bonus applied with code {bonus_code_str} for user {user.id} (value was zero).")
    return {'success': True, 'bonus_value_sats': 0, 'user_bonus_id': None, 'message': 'No monetary bonus applied with this code.', 'status_code': 200, 'bonus_code_obj': bonus_code}
