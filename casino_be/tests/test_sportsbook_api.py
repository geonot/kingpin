import unittest
import json
from datetime import datetime, timezone, timedelta

from casino_be.app import db
from casino_be.models import User, Sport, League, Team, Event, Market, Odds, SportsBet, Transaction
from casino_be.tests.test_api import BaseTestCase
from casino_be.exceptions import InsufficientFundsException, ValidationException, GameLogicException
from casino_be.error_codes import ErrorCodes

class SportsbookApiTests(BaseTestCase):
    """Tests for sportsbook related API endpoints."""

    def _create_sport(self, name="Basketball", slug="nba"):
        sport = Sport(name=name, slug=slug, is_active=True)
        db.session.add(sport)
        db.session.commit()
        return sport

    def _create_league(self, sport, name="National Basketball Association", slug="nba"):
        league = League(sport_id=sport.id, name=name, slug=slug, is_active=True)
        db.session.add(league)
        db.session.commit()
        return league

    def _create_team(self, league, name, short_name, slug):
        team = Team(league_id=league.id, name=name, short_name=short_name, slug=slug, is_active=True)
        db.session.add(team)
        db.session.commit()
        return team

    def _create_event(self, league, home_team, away_team, hours_from_now=1, status='Scheduled'):
        event = Event(
            league_id=league.id,
            home_team_id=home_team.id,
            away_team_id=away_team.id,
            event_datetime=datetime.now(timezone.utc) + timedelta(hours=hours_from_now),
            status=status
        )
        db.session.add(event)
        db.session.commit()
        return event

    def _create_market_and_odds(self, event):
        market = Market(event_id=event.id, market_type='moneyline_2way', is_active=True)
        db.session.add(market)
        db.session.commit()

        odds_home = Odds(
            market_id=market.id,
            selection_identifier='home',
            display_name=event.home_team.name,
            decimal_value=1.91,
            is_active=True
        )
        odds_away = Odds(
            market_id=market.id,
            selection_identifier='away',
            display_name=event.away_team.name,
            decimal_value=2.10,
            is_active=True
        )
        db.session.add_all([odds_home, odds_away])
        db.session.commit()
        return odds_home, odds_away

    def test_place_bet_success(self):
        """Test a successful bet placement."""
        _, user_id = self._login_and_get_token()
        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = 10000
            db.session.commit()
            initial_balance = user.balance

            sport = self._create_sport()
            league = self._create_league(sport)
            team1 = self._create_team(league, name="Team A", slug="team-a", short_name="TA")
            team2 = self._create_team(league, name="Team B", slug="team-b", short_name="TB")
            event = self._create_event(league, team1, team2)
            odds_home, _ = self._create_market_and_odds(event)

            stake = 500
            payload = {
                "odds_id": odds_home.id,
                "stake_satoshis": stake
            }

        response = self.client.post('/api/sportsbook/bets', json=payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(data['stake_satoshis'], stake)
        self.assertEqual(data['status'], 'Pending')

        with self.app.app_context():
            user_after_bet = User.query.get(user_id)
            self.assertEqual(user_after_bet.balance, initial_balance - stake)

            bet = SportsBet.query.filter_by(user_id=user_id).first()
            self.assertIsNotNone(bet)
            self.assertEqual(bet.stake_satoshis, stake)

            transaction = Transaction.query.filter_by(sports_bet_id=bet.id).first()
            self.assertIsNotNone(transaction)
            self.assertEqual(transaction.amount, -stake)
            self.assertEqual(transaction.transaction_type, 'sportsbook_bet_placed')

    def test_place_bet_insufficient_funds(self):
        """Test placing a bet with insufficient funds."""
        _, user_id = self._login_and_get_token()
        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = 100  # User has only 100 satoshis
            db.session.commit()

            sport = self._create_sport()
            league = self._create_league(sport)
            team1 = self._create_team(league, name="Team C", slug="team-c", short_name="TC")
            team2 = self._create_team(league, name="Team D", slug="team-d", short_name="TD")
            event = self._create_event(league, team1, team2)
            odds_home, _ = self._create_market_and_odds(event)

            payload = {
                "odds_id": odds_home.id,
                "stake_satoshis": 500  # Try to bet 500
            }

        response = self.client.post('/api/sportsbook/bets', json=payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(data['error_code'], ErrorCodes.INSUFFICIENT_FUNDS)

    def test_place_bet_on_started_event(self):
        """Test placing a bet on an event that has already started."""
        _, user_id = self._login_and_get_token()
        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = 10000
            db.session.commit()

            sport = self._create_sport()
            league = self._create_league(sport)
            team1 = self._create_team(league, name="Team E", slug="team-e", short_name="TE")
            team2 = self._create_team(league, name="Team F", slug="team-f", short_name="TF")
            event = self._create_event(league, team1, team2, hours_from_now=-1) # Event started 1 hour ago
            odds_home, _ = self._create_market_and_odds(event)

            payload = {
                "odds_id": odds_home.id,
                "stake_satoshis": 500
            }

        response = self.client.post('/api/sportsbook/bets', json=payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(data['error_code'], ErrorCodes.GAME_LOGIC_ERROR)
        self.assertEqual(data['status_message'], "Cannot place a bet on an event that has already started.")

    def test_settle_event_and_pay_winner(self):
        """Test settling an event and paying a winning bet."""
        # Create admin user and log in
        admin_user = self._create_user(username="test_admin", email="admin@test.com", password="password123")
        admin_user.is_admin = True
        db.session.commit()
        self.client.post('/api/login', json={"username": "test_admin", "password": "password123"})

        # Create regular user and place a bet
        _, user_id = self._login_and_get_token(username_prefix="winner")
        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = 10000
            db.session.commit()
            initial_balance = user.balance

            sport = self._create_sport()
            league = self._create_league(sport)
            team1 = self._create_team(league, name="Team G", slug="team-g", short_name="TG")
            team2 = self._create_team(league, name="Team H", slug="team-h", short_name="TH")
            event = self._create_event(league, team1, team2)
            odds_home, _ = self._create_market_and_odds(event)

            stake = 1000
            bet = SportsBet(user_id=user.id, odds_id=odds_home.id, stake_satoshis=stake, potential_payout_satoshis=int(stake * odds_home.decimal_value), status='Pending')
            user.balance -= stake # Debit stake
            db.session.add(bet)
            db.session.commit()

            # Settle the event with Team G (home team) winning
            settle_payload = {
                "home_score": 2,
                "away_score": 1
            }

        response = self.client.post(f'/api/admin/sportsbook/events/{event.id}/settle', json=settle_payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['status'])

        with self.app.app_context():
            user_after_settle = User.query.get(user_id)
            bet_after_settle = SportsBet.query.filter_by(user_id=user_id).first()

            self.assertEqual(bet_after_settle.status, 'Won')
            expected_balance = initial_balance - stake + bet_after_settle.potential_payout_satoshis
            self.assertEqual(user_after_settle.balance, expected_balance)

            win_transaction = Transaction.query.filter_by(sports_bet_id=bet.id, transaction_type='sportsbook_bet_won').first()
            self.assertIsNotNone(win_transaction)
            self.assertEqual(win_transaction.amount, bet_after_settle.potential_payout_satoshis)

    def test_settle_event_losing_bet(self):
        """Test settling an event where the user's bet loses."""
        # Create admin user and log in
        admin_user = self._create_user(username="test_admin_2", email="admin2@test.com", password="password123")
        admin_user.is_admin = True
        db.session.commit()
        self.client.post('/api/login', json={"username": "test_admin_2", "password": "password123"})

        # Create regular user and place a bet
        _, user_id = self._login_and_get_token(username_prefix="loser")
        with self.app.app_context():
            user = User.query.get(user_id)
            user.balance = 10000
            db.session.commit()

            sport = self._create_sport()
            league = self._create_league(sport)
            team1 = self._create_team(league, name="Team I", slug="team-i", short_name="TI")
            team2 = self._create_team(league, name="Team J", slug="team-j", short_name="TJ")
            event = self._create_event(league, team1, team2)
            odds_home, _ = self._create_market_and_odds(event)

            stake = 1000
            bet = SportsBet(user_id=user.id, odds_id=odds_home.id, stake_satoshis=stake, potential_payout_satoshis=int(stake * odds_home.decimal_value), status='Pending')
            user.balance -= stake
            db.session.add(bet)
            db.session.commit()
            balance_after_bet = user.balance

            # Settle the event with Team J (away team) winning
            settle_payload = {
                "home_score": 1,
                "away_score": 2
            }

        response = self.client.post(f'/api/admin/sportsbook/events/{event.id}/settle', json=settle_payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['status'])

        with self.app.app_context():
            user_after_settle = User.query.get(user_id)
            bet_after_settle = SportsBet.query.filter_by(user_id=user_id).first()

            self.assertEqual(bet_after_settle.status, 'Lost')
            self.assertEqual(user_after_settle.balance, balance_after_bet) # Balance should not change

            win_transaction = Transaction.query.filter_by(sports_bet_id=bet.id, transaction_type='sportsbook_bet_won').first()
            self.assertIsNone(win_transaction) # No win transaction should exist

if __name__ == '__main__':
    unittest.main()
