import unittest
import json
from datetime import datetime, timezone, timedelta

from casino_be.app import app, db
from casino_be.models import User, Slot, GameSession, SlotSymbol, SlotBet, BonusCode, UserBonus
from casino_be.error_codes import ErrorCodes # Import ErrorCodes
from flask_jwt_extended import create_access_token


class TestAPIIntegration(unittest.TestCase):
    """Comprehensive API integration tests for game flows."""
    
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['JWT_SECRET_KEY'] = 'test-super-secret-key'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['RATELIMIT_ENABLED'] = False
        
        cls.app = app
        cls.client = cls.app.test_client()
        
    def setUp(self):
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Create test user
        self.user = User(
            username='api_test_user',
            email='api@test.com',
            password='password123',
            balance=10000000  # 0.1 BTC in sats
        )
        db.session.add(self.user)
        
        # Create test slot
        self.slot = Slot(
            id=1,
            name="API Test Slot",
            short_name="api_slot",
            num_rows=3,
            num_columns=5,
            num_symbols=5,
            asset_directory="/test_assets/",
            is_active=True,
            rtp=95.0,
            volatility="Medium"
        )
        db.session.add(self.slot)
        
        # Create symbols
        symbols_data = [
            {"name": "Cherry", "value_multiplier": 10, "img_link": "cherry.png", "symbol_internal_id": 1, "slot_id": 1},
            {"name": "Lemon", "value_multiplier": 5, "img_link": "lemon.png", "symbol_internal_id": 2, "slot_id": 1},
            {"name": "BAR", "value_multiplier": 20, "img_link": "bar.png", "symbol_internal_id": 3, "slot_id": 1},
            {"name": "Wild", "value_multiplier": 0, "img_link": "wild.png", "symbol_internal_id": 4, "slot_id": 1},
        ]
        for s_data in symbols_data:
            symbol = SlotSymbol(**s_data)
            db.session.add(symbol)
            
        # Create slot bets
        slot_bet = SlotBet(slot_id=1, bet_amount=10000)  # 0.0001 BTC
        db.session.add(slot_bet)
        
        db.session.commit()
        
        # Generate JWT token
        with self.app.app_context():
            self.access_token = create_access_token(identity=self.user)
            
    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        
    def get_auth_headers(self):
        """Get authorization headers with JWT token."""
        return {'Authorization': f'Bearer {self.access_token}'}
        
    def test_complete_game_session_flow(self):
        """Test complete game session from join to end."""
        headers = self.get_auth_headers()
        
        # 1. Join game
        join_payload = {"slot_id": 1}
        join_response = self.client.post('/api/slots/join', 
                                       headers=headers, 
                                       json=join_payload)
        
        self.assertEqual(join_response.status_code, 200)
        join_data = json.loads(join_response.data.decode())
        self.assertTrue(join_data['status'])
        self.assertIn('session_id', join_data)
        
        session_id = join_data['session_id']
        
        # 2. Make several spins
        spin_payload = {"bet_amount": 10000}
        total_wagered = 0
        total_won = 0
        
        for _ in range(3):
            spin_response = self.client.post('/api/slots/spin',
                                           headers=headers,
                                           json=spin_payload)
            
            self.assertEqual(spin_response.status_code, 200)
            spin_data = json.loads(spin_response.data.decode())
            self.assertTrue(spin_data['status'])
            
            total_wagered += spin_payload['bet_amount']
            total_won += spin_data.get('win_amount', 0)
            
        # 3. End session
        end_response = self.client.post('/api/end_session',
                                      headers=headers,
                                      json={})
        
        self.assertEqual(end_response.status_code, 200)
        end_data = json.loads(end_response.data.decode())
        self.assertTrue(end_data['status'])
        
        # 4. Verify session data
        with self.app.app_context():
            session = GameSession.query.get(session_id)
            self.assertIsNotNone(session)
            self.assertEqual(session.amount_wagered, total_wagered)
            self.assertEqual(session.amount_won, total_won)
            
    def test_authentication_flow(self):
        """Test user authentication and authorization flow."""
        # 1. Register new user
        register_payload = {
            "username": "auth_test_user",
            "email": "auth@test.com",
            "password": "password123"
        }
        
        register_response = self.client.post('/api/register', json=register_payload)
        self.assertEqual(register_response.status_code, 200)
        register_data = json.loads(register_response.data.decode())
        self.assertTrue(register_data['status'])
        
        # 2. Login
        login_payload = {
            "username": "auth_test_user",
            "password": "password123"
        }
        
        login_response = self.client.post('/api/login', json=login_payload)
        self.assertEqual(login_response.status_code, 200)
        login_data = json.loads(login_response.data.decode())
        self.assertTrue(login_data['status'])
        self.assertIn('access_token', login_data)
        
        # 3. Access protected endpoint
        auth_headers = {'Authorization': f'Bearer {login_data["access_token"]}'}
        profile_response = self.client.get('/api/me', headers=auth_headers)
        
        self.assertEqual(profile_response.status_code, 200)
        profile_data = json.loads(profile_response.data.decode())
        self.assertTrue(profile_data['status'])
        self.assertEqual(profile_data['user']['username'], 'auth_test_user')
        
        # 4. Logout
        logout_response = self.client.post('/api/logout', headers=auth_headers)
        self.assertEqual(logout_response.status_code, 200)
        
        # 5. Try to access protected endpoint after logout (should fail)
        profile_response_after_logout = self.client.get('/api/me', headers=auth_headers)
        self.assertEqual(profile_response_after_logout.status_code, 401)
        
    def test_game_data_endpoints(self):
        """Test game data retrieval endpoints."""
        headers = self.get_auth_headers()
        
        # 1. Get slots
        slots_response = self.client.get('/api/slots', headers=headers)
        self.assertEqual(slots_response.status_code, 200)
        slots_data = json.loads(slots_response.data.decode())
        self.assertTrue(slots_data['status'])
        self.assertIsInstance(slots_data['slots'], list)
        self.assertGreater(len(slots_data['slots']), 0)
        
        # 2. Get specific slot config
        slot_config_response = self.client.get('/api/slots/1/config', headers=headers)
        self.assertEqual(slot_config_response.status_code, 200)
        config_data = json.loads(slot_config_response.data.decode())
        self.assertIn('name', config_data)
        
        # 3. Get tables
        tables_response = self.client.get('/api/tables', headers=headers)
        self.assertEqual(tables_response.status_code, 200)
        tables_data = json.loads(tables_response.data.decode())
        self.assertTrue(tables_data['status'])
        
    def test_error_handling_and_validation(self):
        """Test API error handling and input validation."""
        headers = self.get_auth_headers()
        
        # 1. Invalid spin payload (missing bet_amount)
        invalid_spin_response = self.client.post('/api/slots/spin',
                                               headers=headers,
                                               json={})
        invalid_spin_data = json.loads(invalid_spin_response.data.decode())
        self.assertEqual(invalid_spin_response.status_code, 422) # Marshmallow validation error
        self.assertFalse(invalid_spin_data['status'])
        self.assertEqual(invalid_spin_data['error_code'], ErrorCodes.VALIDATION_ERROR)
        self.assertIn('bet_amount', invalid_spin_data['details']['errors']) # Expecting error about missing bet_amount
        
        # 2. Spin with insufficient balance
        large_bet_payload = {"bet_amount": 999999999}  # More than user balance
        insufficient_balance_response = self.client.post('/api/slots/spin',
                                                       headers=headers,
                                                       json=large_bet_payload)
        
        error_data = json.loads(insufficient_balance_response.data.decode())
        self.assertEqual(insufficient_balance_response.status_code, 400) # InsufficientFundsException
        self.assertFalse(error_data['status'])
        self.assertEqual(error_data['error_code'], ErrorCodes.INSUFFICIENT_FUNDS)
        self.assertEqual(error_data['status_message'], 'Insufficient balance to place bet.')
        
        # 3. Access without authentication
        no_auth_response = self.client.get('/api/me')
        no_auth_data = json.loads(no_auth_response.data.decode())
        self.assertEqual(no_auth_response.status_code, 401) # NoAuthorizationError
        self.assertFalse(no_auth_data['status'])
        self.assertEqual(no_auth_data['error_code'], ErrorCodes.UNAUTHENTICATED)
        self.assertEqual(no_auth_data['status_message'], 'Missing or invalid authorization token.')

        # 4. Invalid JSON payload
        invalid_json_response = self.client.post('/api/login',
                                               data="invalid json",
                                               content_type='application/json')
        invalid_json_data = json.loads(invalid_json_response.data.decode())
        self.assertEqual(invalid_json_response.status_code, 400) # Werkzeug BadRequest
        self.assertFalse(invalid_json_data['status'])
        # This will be caught by handle_werkzeug_http_exception, which might assign a generic error code or map 400 to validation
        # Based on current app.py, it would be GENERIC_ERROR unless specifically mapped.
        # For a malformed JSON, it's often a BadRequest (400) from Werkzeug.
        # Our handler for WerkzeugHTTPException should assign ErrorCodes.GENERIC_ERROR or similar for a generic 400.
        # Or, if Flask/Werkzeug identifies it as a parsing error that maps to VALIDATION_ERROR.
        # Let's assume it's caught by the WerkzeugHTTPException handler and results in a generic error or specific parse error.
        # ErrorCodes.VALIDATION_ERROR is also plausible if the framework treats it as such.
        # Given current global handler, a generic 400 from werkzeug not specifically mapped might fall to GENERIC_ERROR.
        # Let's check current app.py: handle_werkzeug_http_exception maps 400 to GENERIC_ERROR.
        self.assertEqual(invalid_json_data['error_code'], ErrorCodes.GENERIC_ERROR)
        self.assertIn('Failed to decode JSON object', invalid_json_data['details']['description']) # Werkzeug's default message for bad JSON
        
    def test_bonus_system_integration(self):
        """Test bonus system integration with API."""
        headers = self.get_auth_headers()
        
        # 1. Create bonus code
        with self.app.app_context():
            bonus_code = BonusCode(
                code_id='API_TEST_BONUS',
                name='API Test Bonus',
                bonus_amount_sats=1000000,
                wagering_requirement_multiplier=5,
                expiry_date=datetime.now(timezone.utc) + timedelta(days=30),
                is_active=True
            )
            db.session.add(bonus_code)
            db.session.commit()
            
        # 2. Apply bonus code
        bonus_payload = {"bonus_code": "API_TEST_BONUS"}
        bonus_response = self.client.post('/api/apply_bonus',
                                        headers=headers,
                                        json=bonus_payload)
        
        self.assertEqual(bonus_response.status_code, 200)
        bonus_data = json.loads(bonus_response.data.decode())
        self.assertTrue(bonus_data['status'])
        
        # 3. Verify bonus is active
        with self.app.app_context():
            user_bonus = UserBonus.query.filter_by(
                user_id=self.user.id,
                bonus_code_id=bonus_code.id
            ).first()
            self.assertIsNotNone(user_bonus)
            self.assertTrue(user_bonus.is_active)
            
        # 4. Play with bonus (should contribute to wagering)
        spin_payload = {"bet_amount": 10000}
        spin_response = self.client.post('/api/slots/spin',
                                       headers=headers,
                                       json=spin_payload)
        
        self.assertEqual(spin_response.status_code, 200)
        
        # 5. Check wagering progress
        with self.app.app_context():
            user_bonus = UserBonus.query.filter_by(
                user_id=self.user.id,
                bonus_code_id=bonus_code.id
            ).first()
            self.assertGreater(user_bonus.wagering_progress_sats, 0)
            
    def test_rate_limiting_behavior(self):
        """Test API rate limiting behavior."""
        headers = self.get_auth_headers()
        
        # Make rapid requests to test rate limiting
        responses = []
        for _ in range(20):  # Make many requests quickly
            response = self.client.get('/api/me', headers=headers)
            responses.append(response)
            
        # All should succeed since rate limiting is disabled in tests
        # In production, some would return 429
        success_count = sum(1 for r in responses if r.status_code == 200)
        self.assertGreater(success_count, 0)
        
    def test_concurrent_session_handling(self):
        """Test handling of concurrent game sessions."""
        headers = self.get_auth_headers()
        
        # 1. Join first session
        join_payload = {"slot_id": 1}
        first_session_response = self.client.post('/api/slots/join',
                                                headers=headers,
                                                json=join_payload)
        
        self.assertEqual(first_session_response.status_code, 200)
        
        # 2. Try to join another session (should handle gracefully)
        second_session_response = self.client.post('/api/slots/join',
                                                 headers=headers,
                                                 json=join_payload)
        
        # Should either succeed (ending previous session) or fail gracefully
        self.assertIn(second_session_response.status_code, [200, 400])
        
    def test_transaction_consistency(self):
        """Test transaction consistency across API calls."""
        headers = self.get_auth_headers()
        
        # Record initial balance
        initial_balance = self.user.balance
        
        # Join game
        join_payload = {"slot_id": 1}
        join_response = self.client.post('/api/slots/join',
                                       headers=headers,
                                       json=join_payload)
        self.assertEqual(join_response.status_code, 200)
        
        # Make multiple spins and track balance changes
        spin_payload = {"bet_amount": 10000}
        total_expected_change = 0
        
        for _ in range(5):
            pre_spin_response = self.client.get('/api/me', headers=headers)
            pre_spin_data = json.loads(pre_spin_response.data.decode())
            pre_balance = pre_spin_data['user']['balance']
            
            spin_response = self.client.post('/api/slots/spin',
                                           headers=headers,
                                           json=spin_payload)
            spin_data = json.loads(spin_response.data.decode())
            
            post_spin_response = self.client.get('/api/me', headers=headers)
            post_spin_data = json.loads(post_spin_response.data.decode())
            post_balance = post_spin_data['user']['balance']
            
            # Verify balance change matches spin result
            expected_change = spin_data.get('win_amount', 0) - spin_payload['bet_amount']
            actual_change = post_balance - pre_balance
            
            self.assertEqual(actual_change, expected_change,
                           f"Balance change mismatch: expected {expected_change}, got {actual_change}")
            
            total_expected_change += expected_change
            
        # Verify total balance change
        final_response = self.client.get('/api/me', headers=headers)
        final_data = json.loads(final_response.data.decode())
        final_balance = final_data['user']['balance']
        
        total_actual_change = final_balance - initial_balance
        self.assertEqual(total_actual_change, total_expected_change)


if __name__ == '__main__':
    unittest.main()
