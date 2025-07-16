from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.orm import joinedload
from datetime import datetime, timezone

from casino_be.models import db, Sport, League, Team, Event, Market, Odds, SportsBet, Transaction
from casino_be.utils.security import require_csrf_token # Assuming admin actions require CSRF
from casino_be.exceptions import AuthorizationException, ValidationException, GameLogicException

# A decorator to check for admin privileges might be needed here
# For now, we can use a simplified check within each route.
def admin_required(fn):
    @jwt_required()
    def wrapper(*args, **kwargs):
        from flask_jwt_extended import current_user
        if not current_user.is_admin:
            raise AuthorizationException("Admin access required.")
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper

admin_sportsbook_bp = Blueprint('admin_sportsbook', __name__, url_prefix='/api/admin/sportsbook')

@admin_sportsbook_bp.route('/status', methods=['GET'])
@admin_required
def status():
    """A simple status check for the admin sportsbook blueprint."""
    return jsonify({'status': True, 'message': 'Admin Sportsbook API is active.'}), 200

# Placeholder for creating a sport
@admin_sportsbook_bp.route('/sports', methods=['POST'])
@admin_required
@require_csrf_token
def create_sport():
    # TODO: Implement sport creation logic
    data = request.get_json()
    # Basic validation
    if not data or 'name' not in data or 'slug' not in data:
        return jsonify({'status': False, 'message': 'Name and slug are required.'}), 400

    new_sport = Sport(name=data['name'], slug=data['slug'])
    db.session.add(new_sport)
    db.session.commit()

    return jsonify({'status': True, 'message': 'Sport created.', 'sport_id': new_sport.id}), 201

# Add other admin CRUD endpoints for League, Team, Event, Market, Odds as placeholders
# ...

# Placeholder for settling an event
@admin_sportsbook_bp.route('/events/<int:event_id>/settle', methods=['POST'])
@admin_required
@require_csrf_token
def settle_event(event_id):
    """
    Settle an event by providing the final scores.
    This will process all pending bets for the event.
    """
    data = request.get_json()
    home_score = data.get('home_score')
    away_score = data.get('away_score')

    if home_score is None or away_score is None:
        raise ValidationException("home_score and away_score are required.")

    event = Event.query.get(event_id)
    if not event:
        raise ValidationException(f"Event with id {event_id} not found.")
    if event.status not in ['Scheduled', 'InProgress']:
        raise GameLogicException(f"Event is already settled or in a non-resettable state ({event.status}).")

    try:
        # 1. Update Event
        event.home_score = home_score
        event.away_score = away_score
        event.status = 'Finished'
        event.settled_at = datetime.now(timezone.utc)

        winner_team_id = None
        if home_score > away_score:
            winner_team_id = event.home_team_id
        elif away_score > home_score:
            winner_team_id = event.away_team_id
        # if scores are equal, winner_team_id remains None (a draw)
        event.winner_team_id = winner_team_id

        # 2. Find all pending bets for this event
        pending_bets = SportsBet.query.join(Odds).join(Market).filter(
            Market.event_id == event_id,
            SportsBet.status == 'Pending'
        ).options(
            joinedload(SportsBet.user) # Eager load user to avoid N+1 query for balance updates
        ).all()

        settled_count = 0
        for bet in pending_bets:
            market = bet.odds_line.market
            is_winner = False

            # --- Settlement Logic ---
            # For now, we only handle Moneyline. Spread and Totals would need more logic here.
            if market.market_type == 'moneyline_2way':
                # 'selection_identifier' for moneyline should be 'home' or 'away'
                selected_team_id = event.home_team_id if bet.odds_line.selection_identifier == 'home' else event.away_team_id
                if selected_team_id == winner_team_id:
                    is_winner = True

            # --- Update Bet and User Balance ---
            if is_winner:
                bet.status = 'Won'
                payout = bet.potential_payout_satoshis
                bet.actual_winnings_satoshis = payout

                # Credit user balance
                bet.user.balance += payout

                # Create transaction log for the win
                win_transaction = Transaction(
                    user_id=bet.user_id,
                    amount=payout,
                    transaction_type='sportsbook_bet_won',
                    status='completed',
                    sports_bet_id=bet.id,
                    details={'description': f"Win from bet ID {bet.id}"}
                )
                db.session.add(win_transaction)
            else:
                # This also covers draws in a 2-way moneyline, which are losses.
                bet.status = 'Lost'
                bet.actual_winnings_satoshis = 0

            bet.settled_at = datetime.now(timezone.utc)
            settled_count += 1

        db.session.commit()

        return jsonify({
            'status': True,
            'message': f"Event {event_id} settled successfully. {settled_count} bets processed."
        }), 200

    except Exception as e:
        db.session.rollback()
        # The global error handler will catch this
        raise e
```
