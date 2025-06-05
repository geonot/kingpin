import unittest
from unittest.mock import patch, MagicMock
from flask import Flask, jsonify
from decimal import Decimal

# Assuming app structure and necessary imports
from casino_be.app import app, db
from casino_be.models import User, BaccaratTable, BaccaratHand, GameSession, Transaction
from casino_be.schemas import BaccaratTableSchema, BaccaratHandSchema, PlaceBaccaratBetSchema

# It's good practice to use a specific test configuration for Flask app
# For simplicity, we'll use the existing app and mock heavily.

class TestBaccaratAPI(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push() # Push an application context

        # Mock user for JWT
        self.mock_user = User(id=1, username='testuser', email='test@example.com', balance=10000)
        self.mock_user.is_admin = False

        # Patch get_jwt_identity and current_user
        self.patcher_get_jwt_identity = patch('casino_be.app.get_jwt_identity', return_value=self.mock_user.id)
        self.patcher_current_user = patch('casino_be.app.current_user', self.mock_user)

        self.mock_get_jwt_identity = self.patcher_get_jwt_identity.start()
        self.mock_current_user_obj = self.patcher_current_user.start()


    def tearDown(self):
        self.patcher_get_jwt_identity.stop()
        self.patcher_current_user.stop()
        self.app_context.pop()


    @patch('casino_be.models.BaccaratTable.query')
    def test_get_baccarat_tables(self, mock_query):
        # Mock DB response
        table1 = BaccaratTable(id=1, name="Baccarat Table 1", min_bet=100, max_bet=1000, max_tie_bet=200, commission_rate=Decimal("0.05"), is_active=True)
        table2 = BaccaratTable(id=2, name="Baccarat Table 2", min_bet=500, max_bet=5000, max_tie_bet=1000, commission_rate=Decimal("0.05"), is_active=True)
        mock_query.filter_by.return_value.order_by.return_value.all.return_value = [table1, table2]

        response = self.app.get('/api/baccarat/tables', headers={'Authorization': 'Bearer testtoken'})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['status'])
        self.assertEqual(len(data['tables']), 2)
        self.assertEqual(data['tables'][0]['name'], "Baccarat Table 1")

    @patch('casino_be.models.BaccaratTable.query')
    def test_join_baccarat_table_success(self, mock_query_table):
        mock_table = BaccaratTable(id=1, name="Baccarat Table 1", is_active=True)
        mock_query_table.get.return_value = mock_table

        response = self.app.post('/api/baccarat/tables/1/join', headers={'Authorization': 'Bearer testtoken'})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['status'])
        self.assertEqual(data['table']['id'], 1)
        self.assertEqual(data['table']['name'], "Baccarat Table 1")

    @patch('casino_be.models.BaccaratTable.query')
    def test_join_baccarat_table_not_found(self, mock_query_table):
        mock_query_table.get.return_value = None
        response = self.app.post('/api/baccarat/tables/99/join', headers={'Authorization': 'Bearer testtoken'})
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertFalse(data['status'])
        self.assertIn("not found", data['status_message'])

    @patch('casino_be.models.BaccaratTable.query')
    def test_join_baccarat_table_not_active(self, mock_query_table):
        mock_table = BaccaratTable(id=1, name="Baccarat Table 1", is_active=False)
        mock_query_table.get.return_value = mock_table
        response = self.app.post('/api/baccarat/tables/1/join', headers={'Authorization': 'Bearer testtoken'})
        self.assertEqual(response.status_code, 400) # As per current app.py logic
        data = response.get_json()
        self.assertFalse(data['status'])
        self.assertIn("not active", data['status_message'])

    @patch('casino_be.app.db.session.add')
    @patch('casino_be.app.db.session.commit')
    @patch('casino_be.app.db.session.flush')
    @patch('casino_be.models.BaccaratTable.query')
    @patch('casino_be.models.GameSession.query')
    @patch('casino_be.utils.baccarat_helper.play_baccarat_hand')
    def test_play_baccarat_hand_success_player_win(
        self, mock_play_baccarat, mock_gs_query, mock_bt_query,
        mock_db_flush, mock_db_commit, mock_db_add
    ):
        # Setup mocks
        self.mock_user.balance = 1000 # Sufficient balance
        mock_table = BaccaratTable(
            id=1, name="Test Bacc Table", is_active=True,
            min_bet=10, max_bet=500, max_tie_bet=100,
            commission_rate=Decimal("0.05")
        )
        mock_bt_query.get.return_value = mock_table

        # Mock GameSession query to simulate no existing session or one for a different table
        mock_gs_query.filter_by.return_value.all.return_value = [] # No old sessions to end
        mock_gs_query.filter_by.return_value.first.return_value = None # No existing baccarat session for this table

        mock_helper_result = {
            "player_cards": ["HA", "H8"], "banker_cards": ["C2", "C5"],
            "player_score": 8, "banker_score": 7, "outcome": "player_win",
            "total_winnings": Decimal(200), # Gross: bet 100, win 100 -> total 200
            "net_profit": Decimal(100),
            "commission_paid": Decimal(0),
            "details": {}
        }
        mock_play_baccarat.return_value = mock_helper_result

        bet_payload = {
            "table_id": 1,
            "bet_on_player": 100,
            "bet_on_banker": 0,
            "bet_on_tie": 0
        }
        response = self.app.post('/api/baccarat/hands', json=bet_payload, headers={'Authorization': 'Bearer testtoken'})

        self.assertEqual(response.status_code, 200, msg=response.get_data(as_text=True))
        data = response.get_json()
        self.assertTrue(data['status'])
        self.assertEqual(data['hand']['outcome'], "player_win")
        self.assertEqual(data['hand']['win_amount'], 100) # Net profit
        self.assertEqual(data['hand']['initial_bet_player'], 100)
        self.assertEqual(self.mock_user.balance, 1000 - 100 + 200) # Initial - bet + gross_winnings

        # Check that db.session.add was called for BaccaratHand, GameSession (if new), Transaction (wager + win)
        # Number of calls to add can be tricky if GameSession is reused.
        # For this test, GameSession is new (2), BaccaratHand (1), Transaction (2: wager, win) = 5
        self.assertGreaterEqual(mock_db_add.call_count, 3) # At least Hand, Wager Tx, Win Tx. Session might be reused/created.
        mock_db_commit.assert_called_once()

    @patch('casino_be.app.db.session.add')
    @patch('casino_be.app.db.session.commit')
    @patch('casino_be.app.db.session.flush')
    @patch('casino_be.models.BaccaratTable.query')
    @patch('casino_be.models.GameSession.query')
    @patch('casino_be.utils.baccarat_helper.play_baccarat_hand')
    def test_play_baccarat_hand_insufficient_balance(
        self, mock_play_baccarat, mock_gs_query, mock_bt_query,
        mock_db_flush, mock_db_commit, mock_db_add
    ):
        self.mock_user.balance = 50 # Insufficient for 100 bet
        mock_table = BaccaratTable(
            id=1, name="Test Bacc Table", is_active=True,
            min_bet=10, max_bet=500, max_tie_bet=100,
            commission_rate=Decimal("0.05")
        )
        mock_bt_query.get.return_value = mock_table

        bet_payload = {"table_id": 1, "bet_on_player": 100, "bet_on_banker": 0, "bet_on_tie": 0}
        response = self.app.post('/api/baccarat/hands', json=bet_payload, headers={'Authorization': 'Bearer testtoken'})

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data['status'])
        self.assertIn("Insufficient balance", data['status_message'])
        mock_db_add.assert_not_called()
        mock_db_commit.assert_not_called()

    @patch('casino_be.models.BaccaratHand.query')
    def test_get_baccarat_hand_success(self, mock_hand_query):
        mock_hand = BaccaratHand(id=1, user_id=self.mock_user.id, table_id=1, total_bet_amount=100, outcome="player_win")
        # Simulate filter_by().first()
        mock_hand_query.get.return_value = mock_hand

        response = self.app.get('/api/baccarat/hands/1', headers={'Authorization': 'Bearer testtoken'})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['status'])
        self.assertEqual(data['hand']['id'], 1)
        self.assertEqual(data['hand']['outcome'], "player_win")

    @patch('casino_be.models.BaccaratHand.query')
    def test_get_baccarat_hand_not_found(self, mock_hand_query):
        mock_hand_query.get.return_value = None
        response = self.app.get('/api/baccarat/hands/999', headers={'Authorization': 'Bearer testtoken'})
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertFalse(data['status'])
        self.assertIn("not found", data['status_message'])

    @patch('casino_be.models.BaccaratHand.query')
    def test_get_baccarat_hand_unauthorized(self, mock_hand_query):
        # Hand belongs to another user
        mock_hand = BaccaratHand(id=1, user_id=2, table_id=1, total_bet_amount=100, outcome="player_win")
        mock_hand_query.get.return_value = mock_hand

        # current_user.is_admin is False by default in self.mock_user
        response = self.app.get('/api/baccarat/hands/1', headers={'Authorization': 'Bearer testtoken'})
        self.assertEqual(response.status_code, 403)
        data = response.get_json()
        self.assertFalse(data['status'])
        self.assertIn("not authorized", data['status_message'])

    @patch('casino_be.models.BaccaratHand.query')
    def test_get_baccarat_hand_admin_access(self, mock_hand_query):
        self.mock_user.is_admin = True # Make current_user an admin
        # Hand belongs to another user, but admin should access
        mock_hand = BaccaratHand(id=1, user_id=2, table_id=1, total_bet_amount=100, outcome="player_win")
        mock_hand_query.get.return_value = mock_hand

        response = self.app.get('/api/baccarat/hands/1', headers={'Authorization': 'Bearer testtoken'})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['status'])
        self.assertEqual(data['hand']['id'], 1)


if __name__ == '__main__':
    unittest.main()
