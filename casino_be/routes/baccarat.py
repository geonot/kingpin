from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, current_user
from marshmallow import ValidationError
from decimal import Decimal
from datetime import datetime, timezone
from http import HTTPStatus

from ..models import db, User, BaccaratTable, BaccaratHand, GameSession, Transaction # Added GameSession, Transaction
from ..schemas import BaccaratTableSchema, BaccaratHandSchema, PlaceBaccaratBetSchema # UserSchema might be needed if returned
from ..utils import baccarat_helper
from ..app import limiter # Assuming limiter can be imported directly

baccarat_bp = Blueprint('baccarat_bp', __name__, url_prefix='/api/baccarat')

@baccarat_bp.route('/tables', methods=['GET'])
@jwt_required()
def get_baccarat_tables():
    try:
        tables = BaccaratTable.query.filter_by(is_active=True).order_by(BaccaratTable.id).all()
        result = BaccaratTableSchema(many=True).dump(tables)
        return jsonify({'status': True, 'tables': result}), HTTPStatus.OK
    except Exception as e:
        current_app.logger.error(f"Failed to retrieve Baccarat tables list: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Could not retrieve Baccarat table information.'}), HTTPStatus.INTERNAL_SERVER_ERROR

@baccarat_bp.route('/tables/<int:table_id>/join', methods=['POST'])
@jwt_required()
def join_baccarat_table(table_id):
    user = current_user
    table = BaccaratTable.query.get(table_id)

    if not table:
        return jsonify({'status': False, 'status_message': f'Baccarat table {table_id} not found.'}), HTTPStatus.NOT_FOUND
    if not table.is_active:
        return jsonify({'status': False, 'status_message': f'Baccarat table {table_id} is not active.'}), HTTPStatus.BAD_REQUEST

    # Minimal response, actual game session joining might occur on first bet or explicitly
    current_app.logger.info(f"User {user.id} viewed/joined Baccarat table {table.id}.")
    return jsonify({'status': True, 'table': BaccaratTableSchema().dump(table)}), HTTPStatus.OK


@baccarat_bp.route('/hands', methods=['POST'])
@jwt_required()
def play_baccarat_hand_route():
    user = current_user
    data = request.get_json()
    schema = PlaceBaccaratBetSchema()
    try:
        validated_data = schema.load(data)
    except ValidationError as err:
        return jsonify({'status': False, 'status_message': err.messages}), HTTPStatus.BAD_REQUEST

    table_id = validated_data['table_id']
    bet_player_sats = validated_data['bet_on_player']
    bet_banker_sats = validated_data['bet_on_banker']
    bet_tie_sats = validated_data['bet_on_tie']
    total_bet_sats = bet_player_sats + bet_banker_sats + bet_tie_sats

    if total_bet_sats <= 0:
        return jsonify({'status': False, 'status_message': 'Total bet amount must be positive.'}), HTTPStatus.BAD_REQUEST

    table = BaccaratTable.query.get(table_id)
    if not table:
        return jsonify({'status': False, 'status_message': f'Baccarat table {table_id} not found.'}), HTTPStatus.NOT_FOUND
    if not table.is_active:
        return jsonify({'status': False, 'status_message': f'Baccarat table {table_id} is not active.'}), HTTPStatus.BAD_REQUEST

    # Simplified bet validation (assuming individual bets are within overall table limits if min/max are for total hand)
    # More granular validation as in original app.py can be added if necessary
    if not (table.min_bet <= total_bet_sats <= table.max_bet): # Basic check against main bet limits
         return jsonify({'status': False, 'status_message': f'Total bet amount out of table limits ({table.min_bet}-{table.max_bet}).'}), HTTPStatus.BAD_REQUEST
    if bet_tie_sats > 0 and not (bet_tie_sats <= table.max_tie_bet): # Check tie bet max if applicable
         return jsonify({'status': False, 'status_message': f'Tie bet amount exceeds table max tie bet ({table.max_tie_bet}).'}), HTTPStatus.BAD_REQUEST

    if user.balance < total_bet_sats: # Assuming balance is in satoshis
        return jsonify({'status': False, 'status_message': 'Insufficient balance.'}), HTTPStatus.BAD_REQUEST

    now = datetime.now(timezone.utc)
    game_session = None
    try:
        active_sessions = GameSession.query.filter_by(user_id=user.id, session_end=None).all()
        for session in active_sessions:
            if session.game_type != 'baccarat' or session.baccarat_table_id != table_id:
                session.session_end = now # End other game sessions

        game_session = GameSession.query.filter_by(user_id=user.id, game_type='baccarat', baccarat_table_id=table_id, session_end=None).first()
        if not game_session:
            game_session = GameSession(user_id=user.id, game_type='baccarat', baccarat_table_id=table_id, session_start=now)
            db.session.add(game_session)
            db.session.flush()

        baccarat_hand = BaccaratHand(
            user_id=user.id, table_id=table_id, game_session_id=game_session.id,
            initial_bet_player=bet_player_sats, initial_bet_banker=bet_banker_sats, initial_bet_tie=bet_tie_sats,
            total_bet_amount=total_bet_sats, status='pending_play', created_at=now, updated_at=now
        )
        db.session.add(baccarat_hand)

        user.balance -= total_bet_sats
        game_session.amount_wagered = (game_session.amount_wagered or 0) + total_bet_sats
        db.session.flush()

        wager_tx = Transaction(
            user_id=user.id, amount=-total_bet_sats, transaction_type='baccarat_wager', status='completed',
            baccarat_hand_id=baccarat_hand.id,
            details={'table_id': table_id, 'player_bet': bet_player_sats, 'banker_bet': bet_banker_sats, 'tie_bet': bet_tie_sats}
        )
        db.session.add(wager_tx)

        helper_result = baccarat_helper.play_baccarat_hand(
            player_bet_amount=Decimal(bet_player_sats), banker_bet_amount=Decimal(bet_banker_sats), tie_bet_amount=Decimal(bet_tie_sats),
            num_decks=table.rules.get('num_decks', 6), commission_rate=table.commission_rate, tie_payout_rate=table.rules.get('tie_payout', 8)
        )

        if "error" in helper_result:
            current_app.logger.error(f"Baccarat helper error for user {user.id} on table {table_id}: {helper_result['error']}")
            db.session.rollback()
            return jsonify({'status': False, 'status_message': f"Game logic error: {helper_result['error']}"}), HTTPStatus.INTERNAL_SERVER_ERROR

        baccarat_hand.player_cards = helper_result['player_cards']
        baccarat_hand.banker_cards = helper_result['banker_cards']
        baccarat_hand.player_score = helper_result['player_score']
        baccarat_hand.banker_score = helper_result['banker_score']
        baccarat_hand.outcome = helper_result['outcome']
        baccarat_hand.win_amount = int(helper_result['net_profit'])
        baccarat_hand.commission_paid = int(helper_result['commission_paid'])
        baccarat_hand.status = 'completed'
        baccarat_hand.completed_at = datetime.now(timezone.utc)
        baccarat_hand.updated_at = baccarat_hand.completed_at
        baccarat_hand.details = helper_result.get('details', {})

        total_winnings_sats = int(helper_result['total_winnings'])
        if total_winnings_sats > 0:
            user.balance += total_winnings_sats
            win_tx = Transaction(
                user_id=user.id, amount=total_winnings_sats, transaction_type='baccarat_win', status='completed',
                baccarat_hand_id=baccarat_hand.id,
                details={'outcome': baccarat_hand.outcome, 'gross_win': total_winnings_sats, 'net_profit': baccarat_hand.win_amount}
            )
            db.session.add(win_tx)
        game_session.amount_won = (game_session.amount_won or 0) + baccarat_hand.win_amount
        db.session.commit()
        current_app.logger.info(f"Baccarat hand {baccarat_hand.id} completed for user {user.id}. Outcome: {baccarat_hand.outcome}, Net Win: {baccarat_hand.win_amount}")

        # For the response, use the BaccaratHandSchema which now includes a nested UserSchema for balance
        return jsonify({'status': True, 'hand': BaccaratHandSchema().dump(baccarat_hand)}), HTTPStatus.OK
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Baccarat play hand error for user {user.id} on table {table_id}: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'status_message': 'Failed to play Baccarat hand due to an internal error.'}), HTTPStatus.INTERNAL_SERVER_ERROR

@baccarat_bp.route('/hands/<int:hand_id>', methods=['GET'])
@jwt_required()
def get_baccarat_hand(hand_id):
    user = current_user
    # Query including user details for schema dump
    hand = db.session.query(BaccaratHand).options(db.joinedload(BaccaratHand.user)).filter(BaccaratHand.id == hand_id).first()

    if not hand:
        return jsonify({'status': False, 'status_message': f'Baccarat hand {hand_id} not found.'}), HTTPStatus.NOT_FOUND

    # Assuming is_admin is available or not needed if endpoint is user-specific
    if hand.user_id != user.id: # Add admin check if needed: and not user.is_admin
        return jsonify({'status': False, 'status_message': 'You are not authorized to view this hand.'}), HTTPStatus.FORBIDDEN

    return jsonify({'status': True, 'hand': BaccaratHandSchema().dump(hand)}), HTTPStatus.OK
