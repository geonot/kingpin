from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, current_user
from datetime import datetime, timezone

from ..models import db, User, GameSession, Slot, SlotBet # SlotBet imported
from ..schemas import SlotSchema, SpinRequestSchema, GameSessionSchema, UserSchema, JoinGameSchema
from ..utils.spin_handler import handle_spin
from ..utils.multiway_helper import handle_multiway_spin
from ..app import limiter # Assuming limiter can be imported directly

slots_bp = Blueprint('slots', __name__, url_prefix='/api/slots')

@slots_bp.route('/', methods=['GET'])
def get_slots_list(): # Renamed from get_slots to avoid conflict if any other get_slots might exist
    try:
        slots = Slot.query.order_by(Slot.id).all()
        result = SlotSchema(many=True).dump(slots)
        return jsonify({'status': True, 'slots': result}), 200
    except Exception as e:
        current_app.logger.error(f"Failed to retrieve slots list: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Could not retrieve slot information.'}), 500

@slots_bp.route('/spin', methods=['POST'])
@jwt_required()
def spin():
    data = request.get_json()
    errors = SpinRequestSchema().validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400

    user = current_user
    bet_amount_sats = data['bet_amount']

    if not isinstance(bet_amount_sats, int) or bet_amount_sats <= 0:
        return jsonify({'status': False, 'status_message': 'Invalid bet amount.'}), 400

    # Ensure there's an active game session for a slot game
    game_session = GameSession.query.filter_by(user_id=user.id, game_type='slot', session_end=None).order_by(GameSession.session_start.desc()).first()
    if not game_session:
        return jsonify({'status': False, 'status_message': 'No active slot game session. Please join a slot game first.'}), 404

    slot = Slot.query.get(game_session.slot_id)
    if not slot:
         return jsonify({'status': False, 'status_message': 'Slot not found for session.'}), 500

    # --- Bet Amount Validation against SlotBet ---
    allowed_bets_query = SlotBet.query.filter_by(slot_id=slot.id).all()
    if not allowed_bets_query:
        current_app.logger.warning(f"No SlotBet entries configured for slot {slot.id} (name: {slot.name}). Spin denied for user {user.id}.")
        return jsonify({'status': False, 'status_message': 'No valid bet amounts configured for this slot.'}), 400

    allowed_bet_values = [b.bet_amount for b in allowed_bets_query]
    if bet_amount_sats not in allowed_bet_values:
        current_app.logger.warning(f"Invalid bet amount {bet_amount_sats} for slot {slot.id} by user {user.id}. Allowed: {allowed_bet_values}")
        return jsonify({'status': False, 'status_message': f'Invalid bet amount for this slot. Allowed bets are: {sorted(list(set(allowed_bet_values)))} satoshis.'}), 400
    # --- End Bet Amount Validation ---

    if user.balance < bet_amount_sats and not (game_session.bonus_active and game_session.bonus_spins_remaining > 0):
        return jsonify({'status': False, 'status_message': 'Insufficient balance'}), 400

    spin_result_data = None
    try:
        if slot.is_multiway:
            if not slot.reel_configurations:
                current_app.logger.error(f"Spin attempt on multiway slot {slot.id} without reel_configurations by user {user.id}")
                return jsonify({"status": False, "status_message": "Slot is configured as multiway but lacks essential reel configurations."}), 400

            if not slot.symbols: # Make sure symbols are loaded for multiway slot
                 current_app.logger.error(f"Spin attempt on multiway slot {slot.id} without slot.symbols loaded by user {user.id}")
                 return jsonify({"status": False, "status_message": "Slot configuration incomplete (symbols missing)."}), 400

            spin_result_data = handle_multiway_spin(user, slot, game_session, bet_amount_sats)
        else:
            spin_result_data = handle_spin(user, slot, game_session, bet_amount_sats)

        db.session.commit()

        return jsonify({
            'status': True,
            'result': spin_result_data['spin_result'],
            'win_amount': spin_result_data['win_amount_sats'],
            'winning_lines': spin_result_data['winning_lines'],
            'bonus_triggered': spin_result_data['bonus_triggered'],
            'bonus_active': spin_result_data['bonus_active'],
            'bonus_spins_remaining': spin_result_data['bonus_spins_remaining'],
            'bonus_multiplier': spin_result_data['bonus_multiplier'],
            'game_session': GameSessionSchema().dump(game_session),
            'user': UserSchema().dump(user) # Ensure user balance is up-to-date
        }), 200
    except ValueError as ve:
        db.session.rollback()
        current_app.logger.warning(f"Spin ValueError for user {user.id} on slot {slot.id if slot else 'N/A'}: {str(ve)}")
        return jsonify({'status': False, 'status_message': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Spin error: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Spin processing error.'}), 500

@slots_bp.route('/join', methods=['POST'])
@jwt_required()
def join_slot_game():
    data = request.get_json()
    # Using JoinGameSchema, ensure 'game_type' is 'slot' and 'slot_id' is present
    errors = JoinGameSchema().validate(data)
    if errors:
        return jsonify({'status': False, 'status_message': errors}), 400

    game_type = data.get('game_type')
    if game_type != 'slot':
        return jsonify({'status': False, 'status_message': f"Invalid game type for this endpoint: {game_type}. Expected 'slot'."}), 400

    slot_id_from_request = data.get('slot_id')
    if slot_id_from_request is None:
        return jsonify({'status': False, 'status_message': 'slot_id is required for slot games'}), 400

    slot = Slot.query.get(slot_id_from_request)
    if not slot:
        return jsonify({'status': False, 'status_message': f'Slot with ID {slot_id_from_request} not found'}), 404

    user_id = current_user.id
    now = datetime.now(timezone.utc)

    try:
        # End any other active sessions for the user
        active_sessions = GameSession.query.filter_by(user_id=user_id, session_end=None).all()
        for session in active_sessions:
            session.session_end = now

        # Create new slot game session
        new_session = GameSession(
            user_id=user_id,
            slot_id=slot.id,
            table_id=None, # Not applicable for slots
            game_type='slot',
            session_start=now
        )
        db.session.add(new_session)
        db.session.commit()

        current_app.logger.info(f"User {user_id} joined slot game {slot.id}, session {new_session.id} created.")
        return jsonify({'status': True, 'game_session': GameSessionSchema().dump(new_session), 'session_id': new_session.id}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Join slot game failed: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to join slot game.'}), 500
