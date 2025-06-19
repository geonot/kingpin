from flask import Blueprint, request, jsonify, current_app, g
from flask_jwt_extended import jwt_required, current_user
from datetime import datetime, timezone
from functools import wraps
import time

from ..models import db, User, GameSession, Slot, SlotBet # Relative import
from ..schemas import SlotSchema, SpinRequestSchema, GameSessionSchema, UserSchema, JoinGameSchema # Relative import
from ..utils.spin_handler_new import handle_spin # Relative import
from ..utils.multiway_helper import handle_multiway_spin # Relative import
from ..utils.game_config_manager import GameConfigManager # Relative import
from ..utils.security_logger import SecurityLogger, audit_financial_operation, audit_game_operation # Relative import
from ..utils.security import require_csrf_token, rate_limit_by_ip, log_security_event # Relative import

slots_bp = Blueprint('slots', __name__, url_prefix='/api/slots')

@slots_bp.route('/', methods=['GET'])
@slots_bp.route('', methods=['GET'])  # Add route without trailing slash to prevent 308 redirects
def get_slots_list(): # Renamed from get_slots to avoid conflict if any other get_slots might exist
    try:
        slots = Slot.query.order_by(Slot.id).all()
        result = SlotSchema(many=True).dump(slots)
        return jsonify({'status': True, 'slots': result}), 200
    except Exception as e:
        current_app.logger.error(f"Failed to retrieve slots list: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Could not retrieve slot information.'}), 500

@slots_bp.route('/<int:slot_id>/config', methods=['GET'])
@jwt_required()
@rate_limit_by_ip("60 per minute")  # Allow more frequent config requests
def get_slot_config(slot_id):
    """
    Get sanitized slot configuration for client-side use
    This replaces direct access to gameConfig.json files
    """
    try:
        # Validate slot exists and user has access
        slot = Slot.query.get(slot_id)
        if not slot:
            return jsonify({'status': False, 'status_message': 'Slot not found'}), 404
        
        # Get sanitized configuration for client
        client_config = GameConfigManager.get_client_config(slot_id)
        if not client_config:
            current_app.logger.error(f"Failed to load client config for slot {slot_id}")
            return jsonify({'status': False, 'status_message': 'Configuration not available'}), 500
        
        # Add allowed bet amounts from database
        allowed_bets = [bet.bet_amount for bet in slot.bets]
        if allowed_bets:
            client_config["game"]["settings"]["betOptions"] = sorted(allowed_bets)
        
        return jsonify({
            'status': True,
            'config': client_config,
            'slot_info': {
                'id': slot.id,
                'name': slot.name,
                'short_name': slot.short_name,
                'is_multiway': slot.is_multiway
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error serving slot config {slot_id}: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Configuration error'}), 500

@slots_bp.route('/spin', methods=['POST'])
@jwt_required()
@require_csrf_token
@rate_limit_by_ip("30 per minute")  # Max 30 spins per minute per user
def spin():
    # Enhanced input validation and security checks
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': False, 'status_message': 'Invalid JSON data'}), 400
    except Exception as e:
        current_app.logger.warning(f"Request ID: {g.get('request_id', 'N/A')} - Invalid JSON in spin request: {str(e)}")
        return jsonify({'status': False, 'status_message': 'Invalid request format'}), 400

    # Validate against schema
    errors = SpinRequestSchema().validate(data)
    if errors:
        current_app.logger.warning(f"Request ID: {g.get('request_id', 'N/A')} - Spin validation errors: {errors}")
        return jsonify({'status': False, 'status_message': errors}), 400

    user = current_user
    bet_amount_sats = data['bet_amount']

    # Additional security validations
    if not isinstance(bet_amount_sats, int):
        current_app.logger.warning(f"Request ID: {g.get('request_id', 'N/A')} - Non-integer bet amount from user {user.id}: {bet_amount_sats}")
        return jsonify({'status': False, 'status_message': 'Bet amount must be an integer'}), 400
    
    if bet_amount_sats <= 0:
        current_app.logger.warning(f"Request ID: {g.get('request_id', 'N/A')} - Non-positive bet amount from user {user.id}: {bet_amount_sats}")
        return jsonify({'status': False, 'status_message': 'Bet amount must be positive'}), 400
    
    # Check for potential overflow attacks
    if bet_amount_sats > 2**31 - 1:
        log_security_event('OVERFLOW_ATTACK_ATTEMPT', user.id, {'bet_amount': bet_amount_sats})
        current_app.logger.warning(f"Request ID: {g.get('request_id', 'N/A')} - Overflow attack attempt from user {user.id}: {bet_amount_sats}")
        return jsonify({'status': False, 'status_message': 'Bet amount exceeds maximum allowed value'}), 400

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

    # Log the spin attempt for security auditing
    SecurityLogger.log_game_event(
        event_type='spin_attempt',
        user_id=user.id,
        game_type='slot',
        bet_amount=bet_amount_sats,
        game_session_id=game_session.id,
        details={
            'slot_id': slot.id,
            'slot_name': slot.name,
            'is_multiway': slot.is_multiway,
            'bonus_active': game_session.bonus_active
        }
    )

    spin_result_data = None
    balance_before = user.balance
    
    try:
        if slot.is_multiway:
            if not slot.reel_configurations:
                SecurityLogger.log_security_event(
                    event_type='invalid_slot_configuration',
                    severity='high',
                    user_id=user.id,
                    details={'slot_id': slot.id, 'issue': 'missing_reel_configurations'}
                )
                current_app.logger.error(f"Spin attempt on multiway slot {slot.id} without reel_configurations by user {user.id}")
                return jsonify({"status": False, "status_message": "Slot is configured as multiway but lacks essential reel configurations."}), 400

            if not slot.symbols:
                SecurityLogger.log_security_event(
                    event_type='invalid_slot_configuration',
                    severity='high',
                    user_id=user.id,
                    details={'slot_id': slot.id, 'issue': 'missing_symbols'}
                )
                current_app.logger.error(f"Spin attempt on multiway slot {slot.id} without slot.symbols loaded by user {user.id}")
                return jsonify({"status": False, "status_message": "Slot configuration incomplete (symbols missing)."}), 400

            spin_result_data = handle_multiway_spin(user, slot, game_session, bet_amount_sats)
        else:
            spin_result_data = handle_spin(user, slot, game_session, bet_amount_sats)

        db.session.commit()
        
        # Log successful spin with financial details
        SecurityLogger.log_financial_event(
            event_type='slot_spin',
            user_id=user.id,
            amount=-bet_amount_sats,  # Negative for bet
            balance_before=balance_before,
            balance_after=user.balance,
            details={
                'slot_id': slot.id,
                'win_amount': spin_result_data['win_amount_sats'],
                'game_session_id': game_session.id
            }
        )
        
        if spin_result_data['win_amount_sats'] > 0:
            SecurityLogger.log_financial_event(
                event_type='slot_win',
                user_id=user.id,
                amount=spin_result_data['win_amount_sats'],
                balance_before=balance_before,
                balance_after=user.balance,
                details={
                    'slot_id': slot.id,
                    'bet_amount': bet_amount_sats,
                    'winning_lines': len(spin_result_data.get('winning_lines', [])),
                    'bonus_triggered': spin_result_data.get('bonus_triggered', False)
                }
            )

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
            'user': UserSchema().dump(user)
        }), 200
        
    except ValueError as ve:
        db.session.rollback()
        SecurityLogger.log_security_event(
            event_type='spin_validation_error',
            severity='medium',
            user_id=user.id,
            details={
                'slot_id': slot.id,
                'bet_amount': bet_amount_sats,
                'error': str(ve)
            }
        )
        current_app.logger.warning(f"Spin ValueError for user {user.id} on slot {slot.id if slot else 'N/A'}: {str(ve)}")
        return jsonify({'status': False, 'status_message': str(ve)}), 400
        
    except Exception as e:
        db.session.rollback()
        SecurityLogger.log_security_event(
            event_type='spin_system_error',
            severity='high',
            user_id=user.id,
            details={
                'slot_id': slot.id,
                'bet_amount': bet_amount_sats,
                'error': str(e),
                'error_type': type(e).__name__
            }
        )
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
