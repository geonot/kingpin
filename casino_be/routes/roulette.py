from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, current_user
from datetime import datetime, timezone

from models import db, User, RouletteGame
from utils import roulette_helper

roulette_bp = Blueprint('roulette', __name__, url_prefix='/api/roulette')

@roulette_bp.route('/bet', methods=['POST'])
@jwt_required()
def roulette_bet():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing data"}), 400

    bet_amount_req = data.get('bet_amount')
    bet_type_req = data.get('bet_type')
    bet_value_req = data.get('bet_value')

    if not all([bet_amount_req, bet_type_req]):
        return jsonify({"error": "Missing bet_amount or bet_type"}), 400

    try:
        bet_amount = float(bet_amount_req)
        if bet_amount <= 0:
            raise ValueError("Bet amount must be positive.")
    except ValueError:
        return jsonify({"error": "Invalid bet_amount"}), 400

    user = current_user
    # Assuming user.balance is in main currency unit, not satoshis, based on original code.
    # If balance is in satoshis, conversion would be needed here or amounts handled as satoshis throughout.
    if user.balance < bet_amount:
        return jsonify({"error": "Insufficient balance"}), 400

    user.balance -= bet_amount

    winning_number = roulette_helper.spin_wheel()
    multiplier = roulette_helper.get_bet_type_multiplier(bet_type_req, bet_value_req, winning_number)

    payout = 0
    if multiplier > 0:
        payout = roulette_helper.calculate_payout(bet_amount, multiplier)
        user.balance += payout

    stored_bet_type = bet_type_req
    if bet_value_req is not None and bet_type_req in ["straight_up", "column", "dozen"]:
        stored_bet_type = f"{bet_type_req}_{bet_value_req}"
    elif bet_type_req not in ["red", "black", "even", "odd", "low", "high"]:
        if bet_value_req is not None:
             stored_bet_type = f"{bet_type_req}_{bet_value_req}"

    game_record = RouletteGame(
        user_id=user.id,
        bet_amount=bet_amount,
        bet_type=stored_bet_type, # Storing the potentially more descriptive bet type
        winning_number=winning_number,
        payout=payout,
        timestamp=datetime.now(timezone.utc)
    )
    db.session.add(game_record)
    # User balance is already updated in memory, db.session.add(user) stages it for commit.
    db.session.add(user)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Roulette bet by user {user.id} failed: {str(e)}", exc_info=True)
        # Restore balance if commit fails
        user.balance += bet_amount # Add back original bet
        if payout > 0:
            user.balance -= payout # Subtract winnings if they were added
        return jsonify({"error": "Failed to process bet due to a server error."}), 500

    return jsonify({
        "message": "Bet placed successfully!",
        "winning_number": winning_number,
        "your_bet_type": stored_bet_type,
        "your_bet_amount": bet_amount,
        "payout_received": payout,
        "new_balance": user.balance # user.balance is Python float here
    }), 200

@roulette_bp.route('/history', methods=['GET'])
@jwt_required()
def roulette_history():
    user = current_user
    games = RouletteGame.query.filter_by(user_id=user.id).order_by(RouletteGame.timestamp.desc()).limit(20).all()

    history_data = [{
        "id": game.id,
        "bet_amount": game.bet_amount,
        "bet_type": game.bet_type,
        "winning_number": game.winning_number,
        "payout": game.payout,
        "timestamp": game.timestamp.isoformat() if game.timestamp else None
    } for game in games]

    return jsonify(history_data), 200
