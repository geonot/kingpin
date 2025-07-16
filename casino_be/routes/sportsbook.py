from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, current_user
from datetime import datetime, timezone

from casino_be.models import db, Sport, League, Team, Event, Market, Odds, SportsBet, Transaction
from casino_be.schemas import SportSchema, LeagueSchema, EventSchema, SportsBetSchema
from casino_be.utils.security import require_csrf_token
from casino_be.exceptions import InsufficientFundsException, ValidationException, GameLogicException

sportsbook_bp = Blueprint('sportsbook', __name__, url_prefix='/api/sportsbook')

@sportsbook_bp.route('/sports', methods=['GET'])
def list_sports():
    """List all active sports."""
    sports = Sport.query.filter_by(is_active=True).all()
    return jsonify(SportSchema(many=True).dump(sports)), 200

@sportsbook_bp.route('/sports/<sport_slug>/leagues', methods=['GET'])
def list_leagues(sport_slug):
    """List all active leagues for a given sport."""
    sport = Sport.query.filter_by(slug=sport_slug, is_active=True).first_or_404()
    leagues = League.query.filter_by(sport_id=sport.id, is_active=True).all()
    return jsonify(LeagueSchema(many=True, exclude=("sport",)).dump(leagues)), 200

@sportsbook_bp.route('/leagues/<league_slug>/events', methods=['GET'])
def list_events(league_slug):
    """List upcoming events for a given league."""
    # TODO: Add pagination and filtering by date/status
    league = League.query.filter_by(slug=league_slug, is_active=True).first_or_404()
    events = Event.query.filter(
        Event.league_id == league.id,
        Event.status == 'Scheduled'
    ).order_by(Event.event_datetime.asc()).limit(50).all()

    return jsonify(EventSchema(many=True, exclude=("markets",)).dump(events)), 200

@sportsbook_bp.route('/events/<int:event_id>', methods=['GET'])
def get_event_details(event_id):
    """Get detailed information for a single event, including its markets and odds."""
    event = Event.query.options(
        db.joinedload(Event.markets).joinedload(Market.odds)
    ).get_or_404(event_id)

    return jsonify(EventSchema().dump(event)), 200

@sportsbook_bp.route('/bets', methods=['POST'])
@jwt_required()
@require_csrf_token
def place_bet():
    """Place a new sports bet."""
    data = request.get_json()
    if not data or 'odds_id' not in data or 'stake_satoshis' not in data:
        raise ValidationException("odds_id and stake_satoshis are required.")

    odds_id = data['odds_id']
    stake_satoshis = int(data['stake_satoshis'])

    if stake_satoshis <= 0:
        raise ValidationException("Stake must be a positive amount.")

    # Fetch the selected odds and related event
    odds = Odds.query.options(
        db.joinedload(Odds.market).joinedload(Market.event)
    ).get(odds_id)

    if not odds:
        raise ValidationException(f"Odds with id {odds_id} not found.")
    if not odds.is_active or not odds.market.is_active:
        raise GameLogicException("These odds are no longer available.")

    event = odds.market.event
    if event.event_datetime <= datetime.now(timezone.utc):
        raise GameLogicException("Cannot place a bet on an event that has already started.")

    user = current_user
    if user.balance < stake_satoshis:
        raise InsufficientFundsException("Insufficient balance to place this bet.")

    try:
        # 1. Deduct from user balance
        user.balance -= stake_satoshis

        # 2. Create the SportsBet record
        potential_payout = int(stake_satoshis * odds.decimal_value)
        new_bet = SportsBet(
            user_id=user.id,
            odds_id=odds.id,
            stake_satoshis=stake_satoshis,
            potential_payout_satoshis=potential_payout,
            status='Pending',
            bet_slip_details_json={ # Store a snapshot of the bet details
                'sport': event.league.sport.name,
                'league': event.league.name,
                'event': f"{event.home_team.name} vs {event.away_team.name}",
                'market_type': odds.market.market_type,
                'selection_name': odds.display_name,
                'decimal_odds': float(odds.decimal_value)
            }
        )
        db.session.add(new_bet)

        # 3. Create a transaction log
        bet_transaction = Transaction(
            user_id=user.id,
            amount=-stake_satoshis,  # Negative for debit
            transaction_type='sportsbook_bet_placed',
            status='completed',
            sports_bet=new_bet,
            details={
                'description': f"Bet placed on: {odds.display_name}"
            }
        )
        db.session.add(bet_transaction)

        db.session.commit()

        return jsonify(SportsBetSchema().dump(new_bet)), 201

    except Exception as e:
        db.session.rollback()
        # The global error handler in app.py will catch this and log it
        raise e

# This is a new version of the function to force a file change.
@sportsbook_bp.route('/bets/me', methods=['GET'])
@jwt_required()
def get_my_bets():
    """Fetch the current user's sports bets."""
    user = current_user
    # TODO: Add pagination
    bets = SportsBet.query.filter_by(user_id=user.id).order_by(SportsBet.placed_at.desc()).all()

    return jsonify(SportsBetSchema(many=True).dump(bets)), 200
```
