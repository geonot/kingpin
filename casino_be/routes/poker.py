from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, current_user
from datetime import datetime, timezone

from casino_be.models import db, User, PokerTable, PokerHand, PokerPlayerState # Absolute import
from casino_be.schemas import ( # Absolute import
    PokerTableSchema, JoinPokerTableSchema, PokerActionSchema,
    UserSchema, PokerHandSchema, PokerPlayerStateSchema
)
from casino_be.utils import poker_helper # Absolute import
from sqlalchemy.orm import joinedload # For optimized querying

def get_websocket_manager():
    """Get WebSocket manager instance"""
    try:
        from services.websocket_manager import websocket_manager
        return websocket_manager
    except ImportError:
        return None

poker_bp = Blueprint('poker', __name__, url_prefix='/api/poker')

@poker_bp.route('/tables', methods=['GET'])
def list_poker_tables():
    try:
        tables = PokerTable.query.filter_by(is_active=True).order_by(PokerTable.id).all()
        result = PokerTableSchema(many=True).dump(tables)
        return jsonify({'status': True, 'tables': result}), 200
    except Exception as e:
        current_app.logger.error(f"Failed to retrieve poker tables list: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Could not retrieve poker table information.'}), 500

@poker_bp.route('/tables/<int:table_id>/join', methods=['POST'])
@jwt_required()
def join_poker_table(table_id):
    data = request.get_json()
    schema = JoinPokerTableSchema()
    try:
        validated_data = schema.load(data)
    except ValidationError as err:
        return jsonify({'status': False, 'status_message': err.messages}), 400

    user = current_user
    buy_in_amount = validated_data['buy_in_amount']
    seat_id = validated_data.get('seat_id')

    if not seat_id:
        poker_table_obj = PokerTable.query.options(joinedload(PokerTable.player_states)).get(table_id)
        if not poker_table_obj:
            return jsonify({'status': False, 'status_message': f'Poker table {table_id} not found.'}), 404
        if not poker_table_obj.is_active:
            return jsonify({'status': False, 'status_message': f'Poker table {table_id} is not active.'}), 400

        occupied_seat_ids = {ps.seat_id for ps in poker_table_obj.player_states if ps.user_id is not None}
        available_seat = next((i for i in range(1, poker_table_obj.max_seats + 1) if i not in occupied_seat_ids), None)

        if available_seat is None:
            return jsonify({'status': False, 'status_message': f'No available seats at poker table {table_id}.'}), 400
        seat_id = available_seat
        current_app.logger.info(f"User {user.id} joining poker table {table_id}, automatically assigned to seat {seat_id}.")

    result = poker_helper.handle_sit_down(user_id=user.id, table_id=table_id, seat_id=seat_id, buy_in_amount=buy_in_amount)

    if "error" in result:
        status_code = 400
        error_msg_lower = result["error"].lower()
        if "insufficient balance" in error_msg_lower: status_code = 402
        elif "not found" in error_msg_lower: status_code = 404
        elif "occupied" in error_msg_lower or "already seated" in error_msg_lower or "invalid seat" in error_msg_lower: status_code = 409
        elif "buy-in amount must be between" in error_msg_lower : status_code = 400
        return jsonify({'status': False, 'status_message': result['error']}), status_code

    updated_user_data = UserSchema().dump(user)
    
    # Broadcast poker table state update via WebSocket
    websocket_manager = get_websocket_manager()
    if websocket_manager:
        try:
            # Get updated table state after join
            current_hand = PokerHand.query.filter_by(table_id=table_id)\
                .filter(PokerHand.status.in_(['betting', 'preflop', 'flop', 'turn', 'river', 'showdown', 'in_progress'])) \
                .order_by(PokerHand.start_time.desc())\
                .first()
            hand_id_to_pass = current_hand.id if current_hand else None
            state_data = poker_helper.get_table_state(table_id=table_id, hand_id=hand_id_to_pass, user_id=user.id)
            if "error" not in state_data:
                websocket_manager.broadcast_poker_update(table_id, state_data)
        except Exception as e:
            current_app.logger.warning(f"Failed to broadcast poker join update: {e}")
    
    current_app.logger.info(f"User {user.id} successfully joined poker table {table_id} at seat {seat_id} with buy-in {buy_in_amount}.")
    return jsonify({
        'status': True,
        'message': result.get("message", "Successfully joined table."),
        'player_state': result.get("player_state"),
        'user': updated_user_data
    }), 200

@poker_bp.route('/tables/<int:table_id>/leave', methods=['POST'])
@jwt_required()
def leave_poker_table(table_id):
    user = current_user
    result = poker_helper.handle_stand_up(user_id=user.id, table_id=table_id)

    if "error" in result:
        status_code = 400
        if "not found" in result["error"].lower(): status_code = 404
        return jsonify({'status': False, 'status_message': result['error']}), status_code

    updated_user_data = UserSchema().dump(user)
    
    # Broadcast poker table state update via WebSocket
    websocket_manager = get_websocket_manager()
    if websocket_manager:
        try:
            # Get updated table state after leave
            current_hand = PokerHand.query.filter_by(table_id=table_id)\
                .filter(PokerHand.status.in_(['betting', 'preflop', 'flop', 'turn', 'river', 'showdown', 'in_progress'])) \
                .order_by(PokerHand.start_time.desc())\
                .first()
            hand_id_to_pass = current_hand.id if current_hand else None
            state_data = poker_helper.get_table_state(table_id=table_id, hand_id=hand_id_to_pass, user_id=user.id)
            if "error" not in state_data:
                websocket_manager.broadcast_poker_update(table_id, state_data)
        except Exception as e:
            current_app.logger.warning(f"Failed to broadcast poker leave update: {e}")
    
    current_app.logger.info(f"User {user.id} successfully left poker table {table_id}.")
    return jsonify({
        'status': True,
        'message': result.get("message", "Successfully left table."),
        'user': updated_user_data
    }), 200

@poker_bp.route('/tables/<int:table_id>/state', methods=['GET'])
@jwt_required()
def get_poker_table_state(table_id):
    user = current_user
    current_hand = PokerHand.query.filter_by(table_id=table_id)\
        .filter(PokerHand.status.in_(['betting', 'preflop', 'flop', 'turn', 'river', 'showdown', 'in_progress'])) \
        .order_by(PokerHand.start_time.desc())\
        .first()
    hand_id_to_pass = current_hand.id if current_hand else None
    state_data = poker_helper.get_table_state(table_id=table_id, hand_id=hand_id_to_pass, user_id=user.id)

    if "error" in state_data:
        status_code = 404 if "not found" in state_data["error"].lower() else 400
        return jsonify({'status': False, 'status_message': state_data['error']}), status_code
    return jsonify({'status': True, 'table_state': state_data}), 200

@poker_bp.route('/tables/<int:table_id>/start_hand', methods=['POST'])
@jwt_required()
def start_poker_hand_route(table_id):
    user = current_user
    current_app.logger.info(f"User {user.id} attempting to start a new hand at table {table_id}.")
    table = PokerTable.query.get(table_id)
    if not table:
        current_app.logger.warning(f"Start hand attempt failed: Table {table_id} not found.")
        return jsonify({'status': False, 'status_message': f'Poker table {table_id} not found.'}), HTTPStatus.NOT_FOUND

    player_state = PokerPlayerState.query.filter_by(user_id=user.id, table_id=table_id).first()
    if not player_state or player_state.is_sitting_out:
        current_app.logger.warning(f"User {user.id} attempt to start hand at table {table_id} failed: User not actively seated.")
        return jsonify({'status': False, 'status_message': 'User not actively seated at this table.'}), HTTPStatus.FORBIDDEN

    active_hand = PokerHand.query.filter(
        PokerHand.table_id == table_id,
        PokerHand.status.notin_(['completed', 'showdown'])
    ).first()
    if active_hand:
        current_app.logger.warning(f"User {user.id} attempt to start hand at table {table_id} failed: Active hand {active_hand.id} already in progress (status: {active_hand.status}).")
        return jsonify({'status': False, 'status_message': f'An active hand ({active_hand.status}) is already in progress.'}), HTTPStatus.CONFLICT

    active_player_count = PokerPlayerState.query.filter(
        PokerPlayerState.table_id == table_id,
        PokerPlayerState.is_sitting_out == False,
        PokerPlayerState.stack_sats > 0
    ).count()
    if active_player_count < 2: # MIN_PLAYERS_TO_START
        current_app.logger.warning(f"User {user.id} attempt to start hand at table {table_id} failed: Insufficient active players ({active_player_count}).")
        return jsonify({'status': False, 'status_message': f'Not enough active players ({active_player_count}) to start a new hand. Minimum 2 required.'}), HTTPStatus.CONFLICT

    try:
        current_app.logger.info(f"All checks passed for table {table_id}. User {user.id} initiating start_new_hand.")
        result = poker_helper.start_new_hand(table_id=table_id)
        if "error" in result:
            current_app.logger.error(f"Error starting new hand for table {table_id} by user {user.id}: {result['error']}")
            error_msg_lower = result["error"].lower()
            status_code = HTTPStatus.BAD_REQUEST
            if "not enough active players" in error_msg_lower: status_code = HTTPStatus.CONFLICT
            elif "table not found" in error_msg_lower: status_code = HTTPStatus.NOT_FOUND
            return jsonify({'status': False, 'status_message': result['error']}), status_code
        current_app.logger.info(f"New hand {result.get('hand_id')} started successfully at table {table_id} by user {user.id}.")
        return jsonify({'status': True, 'message': 'New hand started.', 'hand_details': result}), HTTPStatus.CREATED
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Unexpected exception when starting new hand for table {table_id} by user {user.id}: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': f'An unexpected server error occurred: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR

@poker_bp.route('/tables/<int:table_id>/hands/<int:hand_id>/action', methods=['POST'])
@jwt_required()
def poker_hand_action(table_id, hand_id):
    data = request.get_json()
    schema = PokerActionSchema()
    try:
        validated_data = schema.load(data)
    except ValidationError as err:
        return jsonify({'status': False, 'status_message': err.messages}), 400

    user = current_user
    action_type = validated_data['action_type'].lower()
    amount = validated_data.get('amount')

    hand = PokerHand.query.filter_by(id=hand_id, table_id=table_id).first()
    if not hand:
        return jsonify({'status': False, 'status_message': f'Hand {hand_id} not found or not associated with table {table_id}.'}), HTTPStatus.NOT_FOUND

    current_app.logger.debug(f"Hand {hand_id} on table {table_id}: Checking for player timeouts before action by user {user.id}.")
    timeout_action_taken = poker_helper.check_and_handle_player_timeouts(table_id=table_id, session=db.session)
    if timeout_action_taken:
        current_app.logger.info(f"Hand {hand_id} on table {table_id}: Timeout action was processed. Re-fetching hand state.")
        db.session.refresh(hand)
        if hand.status in ['completed', 'showdown']:
            current_app.logger.info(f"Hand {hand_id} is now '{hand.status}' after timeout processing. Action by {user.id} may no longer be valid or needed.")

    if hand.current_turn_user_id != user.id:
        if hand.status not in ['betting', 'preflop', 'flop', 'turn', 'river', 'in_progress']:
             return jsonify({'status': False, 'status_message': f'Betting is over for hand {hand_id}. Current status: {hand.status}'}), HTTPStatus.BAD_REQUEST
        return jsonify({'status': False, 'status_message': "It's not your turn."}), HTTPStatus.FORBIDDEN

    result = None
    if action_type == 'fold': result = poker_helper.handle_fold(user_id=user.id, table_id=table_id, hand_id=hand_id)
    elif action_type == 'check': result = poker_helper.handle_check(user_id=user.id, table_id=table_id, hand_id=hand_id)
    elif action_type == 'call': result = poker_helper.handle_call(user_id=user.id, table_id=table_id, hand_id=hand_id)
    elif action_type == 'bet':
        if amount is None: return jsonify({'status': False, 'status_message': 'Amount is required for a bet.'}), HTTPStatus.BAD_REQUEST
        result = poker_helper.handle_bet(user_id=user.id, table_id=table_id, hand_id=hand_id, amount=amount)
    elif action_type == 'raise':
        if amount is None: return jsonify({'status': False, 'status_message': 'Amount is required for a raise.'}), HTTPStatus.BAD_REQUEST
        result = poker_helper.handle_raise(user_id=user.id, table_id=table_id, hand_id=hand_id, amount=amount)
    else:
        return jsonify({'status': False, 'status_message': f'Invalid action type: {action_type}'}), HTTPStatus.BAD_REQUEST

    if result and "error" in result:
        status_code = HTTPStatus.BAD_REQUEST
        error_msg_lower = result["error"].lower()
        if "not found" in error_msg_lower: status_code = HTTPStatus.NOT_FOUND
        elif "not active in hand" in error_msg_lower: status_code = HTTPStatus.FORBIDDEN
        elif "insufficient stack" in error_msg_lower: status_code = HTTPStatus.PAYMENT_REQUIRED
        return jsonify({'status': False, 'status_message': result['error'], 'details': result.get('details')}), status_code

    updated_user_data = UserSchema().dump(user)
    game_flow_data = result.get("game_flow", {}) if result else {}
    
    # Broadcast poker action via WebSocket
    websocket_manager = get_websocket_manager()
    if websocket_manager:
        try:
            # Get updated table state
            state_data = poker_helper.get_table_state(table_id=table_id, hand_id=hand_id, user_id=user.id)
            if "error" not in state_data:
                websocket_manager.broadcast_poker_update(table_id, state_data)
                
                # Also broadcast the specific action
                action_data = {
                    'user_id': user.id,
                    'action_type': action_type,
                    'amount': amount,
                    'hand_id': hand_id
                }
                websocket_manager.broadcast_poker_action(table_id, action_data)
        except Exception as e:
            current_app.logger.warning(f"Failed to broadcast poker action update: {e}")
    
    current_app.logger.info(f"User {user.id} performed action '{action_type}' (amount: {amount if amount is not None else 'N/A'}) on hand {hand_id} at table {table_id}.")
    return jsonify({
        'status': True,
        'message': result.get("message", f"Action '{action_type}' processed successfully."),
        'user': updated_user_data,
        'game_flow': game_flow_data
    }), HTTPStatus.OK
