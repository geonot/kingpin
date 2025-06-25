from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, current_user
from marshmallow import ValidationError
from datetime import datetime, timezone

from ..models import db, User, SpacecrashGame, SpacecrashBet # Relative import
from ..schemas import ( # Relative import
    SpacecrashBetSchema, SpacecrashGameSchema,
    SpacecrashGameHistorySchema, SpacecrashPlayerBetSchema
)
from ..utils import spacecrash_handler # Relative import
from .admin import is_admin # Relative import for sibling module

def get_websocket_manager():
    """Get WebSocket manager instance"""
    try:
        from services.websocket_manager import websocket_manager
        return websocket_manager
    except ImportError:
        return None

spacecrash_bp = Blueprint('spacecrash', __name__, url_prefix='/api/spacecrash')

@spacecrash_bp.route('/bet', methods=['POST'])
@jwt_required()
def spacecrash_place_bet():
    data = request.get_json()
    try:
        validated_data = SpacecrashBetSchema().load(data)
    except ValidationError as err:
        return jsonify({'status': False, 'status_message': err.messages}), 400

    user = current_user
    bet_amount = validated_data['bet_amount']
    auto_eject_at = validated_data.get('auto_eject_at')

    if user.balance < bet_amount:
        return jsonify({'status': False, 'status_message': 'Insufficient balance.'}), 400

    current_game = SpacecrashGame.query.filter_by(status='betting').order_by(SpacecrashGame.created_at.desc()).first()
    if not current_game:
        return jsonify({'status': False, 'status_message': 'No active game accepting bets at the moment.'}), 404

    existing_bet = SpacecrashBet.query.filter_by(user_id=user.id, game_id=current_game.id).first()
    if existing_bet:
        return jsonify({'status': False, 'status_message': 'You have already placed a bet for this game.'}), 400

    try:
        new_bet = SpacecrashBet(
            user_id=user.id, game_id=current_game.id,
            bet_amount=bet_amount, auto_eject_at=auto_eject_at, status='placed'
        )
        user.balance -= bet_amount
        db.session.add(new_bet)
        db.session.commit()

        # Broadcast game state update via WebSocket
        websocket_manager = get_websocket_manager()
        if websocket_manager:
            try:
                # Get updated game data with new bet
                updated_game = SpacecrashGame.query.get(current_game.id)
                game_data = SpacecrashGameSchema().dump(updated_game)
                
                # Add current bets to game data
                bets_query = SpacecrashBet.query.filter_by(game_id=updated_game.id).all()
                game_data['player_bets'] = SpacecrashPlayerBetSchema(many=True).dump(bets_query)
                
                websocket_manager.broadcast_spacecrash_update(game_data)
            except Exception as e:
                current_app.logger.warning(f"Failed to broadcast Spacecrash bet update: {e}")

        current_app.logger.info(f"User {user.id} placed Spacecrash bet {new_bet.id} for {bet_amount} on game {current_game.id}")
        return jsonify({'status': True, 'status_message': 'Bet placed successfully.', 'bet': SpacecrashPlayerBetSchema().dump(new_bet)}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error placing Spacecrash bet for user {user.id}: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to place bet due to an internal error.'}), 500

@spacecrash_bp.route('/eject', methods=['POST'])
@jwt_required()
def spacecrash_eject_bet():
    user = current_user
    active_bet = SpacecrashBet.query.join(SpacecrashGame).filter(
        SpacecrashBet.user_id == user.id,
        SpacecrashGame.status == 'in_progress',
        SpacecrashBet.status == 'placed' # Ensure bet is active (not already ejected/busted)
    ).first()

    if not active_bet:
        return jsonify({'status': False, 'status_message': 'No active bet to eject or game is not in progress.'}), 404

    # Game status check (redundant due to join filter, but good for safety)
    if active_bet.game.status != 'in_progress':
        return jsonify({'status': False, 'status_message': 'Game is no longer in progress.'}), 400

    # Ensure crash_point is checked before attempting to get current_multiplier if game is in_progress
    # This is a defensive check; crash_point should ideally always be set when a game starts.
    # However, get_current_multiplier might rely on game_start_time and if crash_point is None when game is in_progress,
    # it might indicate an inconsistent state that get_current_multiplier isn't designed to handle gracefully.
    if active_bet.game.crash_point is None: # Should not happen if game is 'in_progress' and properly initialized
        current_app.logger.error(f"CRITICAL: Game {active_bet.game.id} is in_progress but crash_point is None during eject by {user.id} before multiplier calculation.")
        return jsonify({'status': False, 'status_message': 'Cannot process eject: game data inconsistent (crash point missing).'}), 500

    current_multiplier = spacecrash_handler.get_current_multiplier(active_bet.game)

    # Check if already crashed before current_multiplier could be determined or if eject is too late
    # Note: The previous check for active_bet.game.crash_point is None handles if crash_point is missing.
    # Here, we assume crash_point is not None and proceed.
    if current_multiplier >= active_bet.game.crash_point:
        active_bet.status = 'busted'
        active_bet.ejected_at = active_bet.game.crash_point
        active_bet.win_amount = 0
        message = 'Eject failed, game crashed before or at your eject point.'
        current_app.logger.info(f"User {user.id} busted Spacecrash bet {active_bet.id}. Game crashed at {active_bet.game.crash_point}x.")
    else:
        active_bet.ejected_at = current_multiplier
        active_bet.win_amount = int(active_bet.bet_amount * active_bet.ejected_at)
        active_bet.status = 'ejected'
        user.balance += active_bet.win_amount
        message = 'Successfully ejected.'
        current_app.logger.info(f"User {user.id} ejected Spacecrash bet {active_bet.id} at {active_bet.ejected_at}x, won {active_bet.win_amount}")

    try:
        db.session.commit()
        
        # Broadcast game state update via WebSocket
        websocket_manager = get_websocket_manager()
        if websocket_manager:
            try:
                # Get updated game data with ejected bet
                updated_game = SpacecrashGame.query.get(active_bet.game_id)
                game_data = SpacecrashGameSchema().dump(updated_game)
                
                # Add current bets to game data
                bets_query = SpacecrashBet.query.filter_by(game_id=updated_game.id).all()
                game_data['player_bets'] = SpacecrashPlayerBetSchema(many=True).dump(bets_query)
                
                websocket_manager.broadcast_spacecrash_update(game_data)
            except Exception as e:
                current_app.logger.warning(f"Failed to broadcast Spacecrash eject update: {e}")
        
        return jsonify({
            'status': True, 'status_message': message,
            'ejected_at': active_bet.ejected_at,
            'win_amount': active_bet.win_amount,
            'bet': SpacecrashPlayerBetSchema().dump(active_bet)
        }), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error ejecting Spacecrash bet for user {user.id}: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to eject bet due to an internal error.'}), 500

@spacecrash_bp.route('/current_game', methods=['GET'])
def spacecrash_current_game_state():
    """Get current SpaceCrash game state with real-time multiplier"""
    game = SpacecrashGame.query.filter(
        SpacecrashGame.status.in_(['in_progress', 'betting'])
    ).order_by(
        db.case(
            (SpacecrashGame.status == 'in_progress', 0),
            (SpacecrashGame.status == 'betting', 1),
            else_=2 # Should not happen with the filter but good practice
        ),
        SpacecrashGame.created_at.desc()
    ).first()

    if not game: # If no betting or in_progress, show last completed
        game = SpacecrashGame.query.filter_by(status='completed').order_by(SpacecrashGame.game_end_time.desc()).first()
        if not game:
            return jsonify({'status': False, 'status_message': 'No current or recent game found.'}), 404

    game_data = SpacecrashGameSchema().dump(game)

    # Add real-time multiplier and timing information
    if game.status == 'in_progress' and game.game_start_time:
        game_data['current_multiplier'] = spacecrash_handler.get_current_multiplier(game)
    elif game.status == 'betting': # Game is betting, multiplier is 1.0 before start
        game_data['current_multiplier'] = 1.0
        # Add betting time remaining
        if game.betting_start_time:
            from services.spacecrash_game_loop import spacecrash_game_loop
            betting_elapsed = (datetime.now(timezone.utc) - game.betting_start_time).total_seconds()
            time_remaining = max(0, spacecrash_game_loop.BETTING_PHASE_DURATION - betting_elapsed)
            game_data['betting_time_remaining'] = time_remaining
    elif game.status == 'completed': # Game is completed, show actual crash point
        game_data['current_multiplier'] = game.crash_point

    bets_query = SpacecrashBet.query.filter_by(game_id=game.id).all()
    game_data['player_bets'] = SpacecrashPlayerBetSchema(many=True).dump(bets_query)
    return jsonify({'status': True, 'game': game_data}), 200

@spacecrash_bp.route('/history', methods=['GET'])
def spacecrash_game_history():
    recent_games = SpacecrashGame.query.filter_by(status='completed').order_by(SpacecrashGame.game_end_time.desc()).limit(20).all()
    if not recent_games:
        return jsonify({'status': True, 'history': []}), 200
    history_data = SpacecrashGameHistorySchema(many=True).dump(recent_games)
    return jsonify({'status': True, 'history': history_data}), 200

@spacecrash_bp.route('/admin/next_phase', methods=['POST'])
@jwt_required()
def spacecrash_admin_next_phase():
    if not is_admin():
        return jsonify({'status': False, 'status_message': 'Access denied. Admin rights required.'}), 403

    data = request.get_json()
    game_id = data.get('game_id')
    target_phase = data.get('target_phase') # e.g., 'betting', 'in_progress', 'completed'
    # Optional params for specific phase transitions, e.g., client_seed for 'in_progress'
    client_seed_param = data.get('client_seed', 'default_client_seed_for_testing_123')
    nonce_param = data.get('nonce', 1)


    game = None
    if game_id: # If a specific game ID is provided
        game = SpacecrashGame.query.get(game_id)
    else: # Try to find a suitable game based on target_phase
        if target_phase == 'betting': # Start betting for a 'pending' game or create new if last was 'completed'
            game = SpacecrashGame.query.filter_by(status='pending').order_by(SpacecrashGame.created_at.desc()).first()
            if not game: # Or if last game is completed/cancelled, create a new one
                 last_game = SpacecrashGame.query.order_by(SpacecrashGame.created_at.desc()).first()
                 if not last_game or last_game.status in ['completed', 'cancelled']:
                    game = spacecrash_handler.create_new_game()
                    db.session.add(game) # Add to session, commit will be handled by handler or at end
                 else: # A game is in a state that doesn't allow new game creation (e.g. betting/in_progress)
                    return jsonify({'status': False, 'status_message': f'Cannot start new game; game {last_game.id} is currently {last_game.status}.'}), 400
        elif target_phase == 'in_progress':
            game = SpacecrashGame.query.filter_by(status='betting').order_by(SpacecrashGame.created_at.desc()).first()
        elif target_phase == 'completed':
            game = SpacecrashGame.query.filter_by(status='in_progress').order_by(SpacecrashGame.created_at.desc()).first()

    if not game:
        return jsonify({'status': False, 'status_message': f'No suitable game found to transition for ID {game_id or "any"} to phase {target_phase}.'}), 404

    original_status = game.status
    success = False
    message = f"Game {game.id} already in {game.status} state or invalid transition to {target_phase}."

    try:
        if target_phase == 'betting':
            if game.status == 'pending' or game.status == 'completed' or game.status == 'cancelled':
                # If game was 'completed' or 'cancelled', we should be operating on a NEW game instance.
                # This logic assumes 'game' is the correct instance to move to betting.
                # If 'game' is an old completed game, create_new_game should have been called before this.
                if game.status != 'pending': # If it's completed/cancelled, implies we want a new game cycle
                    game = spacecrash_handler.create_new_game()
                    db.session.add(game)
                    db.session.flush() # Ensure game has ID if new
                success = spacecrash_handler.start_betting_phase(game)
                message = f"Game {game.id} moved to betting phase." if success else f"Failed to move game {game.id} to betting."
        elif target_phase == 'in_progress':
            if game.status == 'betting':
                # Ensure client_seed is set if not already (e.g. for testing)
                current_client_seed = game.client_seed or client_seed_param
                success = spacecrash_handler.start_game_round(game, current_client_seed, nonce_param)
                message = f"Game {game.id} started (in progress). Crash point: {game.crash_point}" if success else f"Failed to start game {game.id}."
        elif target_phase == 'completed':
            if game.status == 'in_progress':
                success = spacecrash_handler.end_game_round(game) # This will set crash_point if not already set (e.g. natural end)
                message = f"Game {game.id} ended. Final crash point: {game.crash_point}" if success else f"Failed to end game {game.id}."
        else:
            return jsonify({'status': False, 'status_message': f'Invalid target phase: {target_phase}.'}), 400

        if success:
            db.session.commit() # Commit changes made by handlers
            current_app.logger.info(f"Admin {current_user.id} transitioned Spacecrash game {game.id} from {original_status} to {target_phase}.")
            return jsonify({'status': True, 'status_message': message, 'game_state': SpacecrashGameSchema().dump(game)}), 200
        else:
            # No rollback here as handlers should manage their own partial commits or full rollbacks on failure.
            return jsonify({'status': False, 'status_message': message, 'current_status': original_status}), 400
    except Exception as e:
        db.session.rollback() # Catch-all rollback
        current_app.logger.error(f"Error transitioning Spacecrash game {game.id} to {target_phase} by admin {current_user.id}: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': f'Failed to transition game phase due to an internal error: {str(e)}'}), 500
