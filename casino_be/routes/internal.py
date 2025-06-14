from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone

from models import db, User, Transaction
from utils.decorators import service_token_required
from schemas import UserSchema # To serialize user output

internal_bp = Blueprint('internal', __name__, url_prefix='/api/internal')

@internal_bp.route('/update_player_balance', methods=['POST'])
@service_token_required
def update_player_balance():
    """
    Updates a player's balance and records a transaction.
    Protected by a service API token.
    Expects JSON: { "user_id": <int>, "sats_amount": <int>, "original_tx_id": <str_optional> }
    """
    data = request.get_json()
    if not data:
        return jsonify({'status': False, 'status_message': 'Invalid JSON payload.'}), 400

    user_id = data.get('user_id')
    sats_amount = data.get('sats_amount')
    original_tx_id = data.get('original_tx_id', 'N/A') # Optional

    # Validate input
    if not isinstance(user_id, int):
        return jsonify({'status': False, 'status_message': 'user_id must be an integer.'}), 400
    if not isinstance(sats_amount, int) or sats_amount <= 0:
        return jsonify({'status': False, 'status_message': 'sats_amount must be a positive integer.'}), 400

    try:
        user = User.query.get(user_id)
        if not user:
            current_app.logger.error(f"User with ID {user_id} not found in update_player_balance.")
            return jsonify({'status': False, 'status_message': f'User with ID {user_id} not found.'}), 404

        current_app.logger.info(f"User {user_id} fetched in update_player_balance. Current balance: {user.balance} sats before update.")

        # Atomically update balance (though true atomicity depends on DB transaction isolation)
        user.balance += sats_amount

        # Create transaction record
        new_transaction = Transaction(
            user_id=user.id,
            amount=sats_amount,
            transaction_type='deposit_btc', # Or more specific like 'deposit_btc_poller'
            status='completed',
            # timestamp is handled by model's default=datetime.now(timezone.utc)
            details={
                'description': f'Bitcoin deposit of {sats_amount} sats credited via polling service.',
                'source': 'polling_service',
                'original_tx_id': original_tx_id,
                'previous_balance_sats': user.balance - sats_amount, # Balance before this transaction
                'new_balance_sats': user.balance
            }
        )

        db.session.add(new_transaction)
        db.session.commit()

        user_data = UserSchema().dump(user) # Serialize user data for response
        current_app.logger.info(
            f"Successfully updated balance for user ID {user_id}. Added {sats_amount} sats. "
            f"New balance: {user.balance} sats. Original TXID: {original_tx_id}"
        )
        return jsonify({
            'status': True,
            'status_message': 'Balance updated successfully.',
            'user': user_data
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error updating player balance for user_id {user_id}: {str(e)}",
            exc_info=True
        )
        return jsonify({'status': False, 'status_message': 'Failed to update balance due to an internal error.'}), 500
