from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, current_user

from ..models import db, User, BlackjackTable # Relative import
from ..schemas import ( # Relative import
    BlackjackTableSchema, JoinBlackjackSchema, BlackjackActionRequestSchema,
    UserSchema, BlackjackHandSchema
)
from ..utils.blackjack_helper import handle_join_blackjack, handle_blackjack_action # Relative import

blackjack_bp = Blueprint('blackjack', __name__, url_prefix='/api/blackjack')

@blackjack_bp.route('/tables', methods=['GET'])
def get_blackjack_tables(): # Renamed from get_tables to be specific
    try:
        tables = BlackjackTable.query.filter_by(is_active=True).order_by(BlackjackTable.id).all()
        result = BlackjackTableSchema(many=True).dump(tables)
        return jsonify({'status': True, 'tables': result}), 200
    except Exception as e:
        current_app.logger.error(f"Failed to retrieve blackjack tables list: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Could not retrieve blackjack table information.'}), 500

@blackjack_bp.route('/join', methods=['POST'])
@jwt_required()
def join_blackjack_table(): # Renamed from join_blackjack to be specific
    data = request.get_json()
    errors = JoinBlackjackSchema().validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400

    table_id = data['table_id']
    bet_amount = data['bet_amount'] # Assuming schema validates this is an int/Decimal

    table = BlackjackTable.query.get(table_id)
    if not table:
        return jsonify({'status': False, 'status_message': f'Table with ID {table_id} not found'}), 404
    if not table.is_active:
        return jsonify({'status': False, 'status_message': f'Table with ID {table_id} is not active'}), 400

    try:
        # handle_join_blackjack is expected to manage db session commit/rollback
        result_hand_data = handle_join_blackjack(current_user, table, bet_amount)

        # Schemas for response (UserSchema for updated balance, BlackjackHandSchema for hand details)
        user_data = UserSchema().dump(current_user)
        # The result from handle_join_blackjack should be compatible with BlackjackHandSchema
        # If it returns a Hand object, schema will dump it. If dict, ensure it matches.

        current_app.logger.info(f"User {current_user.id} joined blackjack table {table_id} with bet {bet_amount}")
        # Assuming result_hand_data is the hand object/dict to be serialized by BlackjackHandSchema
        return jsonify({'status': True, 'hand': result_hand_data, 'user': user_data }), 201
    except ValueError as ve:
        # Specific error from game logic (e.g., insufficient balance, table full if not handled by helper)
        return jsonify({'status': False, 'status_message': str(ve)}), 400
    except Exception as e:
        # General error, helper should ideally rollback
        db.session.rollback() # Ensure rollback if helper didn't or error was outside helper
        current_app.logger.error(f"Error joining blackjack: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Error joining blackjack game.'}), 500

@blackjack_bp.route('/action', methods=['POST'])
@jwt_required()
def perform_blackjack_action(): # Renamed from blackjack_action
    data = request.get_json()
    errors = BlackjackActionRequestSchema().validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400

    hand_id = data['hand_id']
    action_type = data['action_type']
    hand_index = data.get('hand_index', 0) # Default to 0 if not provided (for non-split hands)

    try:
        # handle_blackjack_action is expected to manage db session commit/rollback
        action_result_data = handle_blackjack_action(current_user, hand_id, action_type, hand_index)

        user_data = UserSchema().dump(current_user)
        # action_result_data could be complex; ensure it's serializable.
        # It might include updated hand(s), game state, outcome messages etc.

        current_app.logger.info(f"User {current_user.id} action {action_type} on hand {hand_id}")
        return jsonify({'status': True, 'action_result': action_result_data, 'user': user_data }), 200
    except ValueError as ve:
        # Specific error from game logic (e.g., invalid action, not user's turn)
        return jsonify({'status': False, 'status_message': str(ve)}), 400
    except Exception as e:
        db.session.rollback() # Ensure rollback
        current_app.logger.error(f"Error in blackjack action: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Error in blackjack action.'}), 500
