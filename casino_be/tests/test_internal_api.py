import unittest
import json
from casino_be.app import create_app, db
from casino_be.models import User, Transaction
from casino_be.tests.test_api import BaseTestCase # Re-use BaseTestCase for setup
from casino_be.error_codes import ErrorCodes # Import ErrorCodes

class TestInternalAPI(BaseTestCase):

    def setUp(self):
        super().setUp() # Setup app, client, db
        self.valid_service_token = "test_internal_api_service_token"
        self.app.config['SERVICE_API_TOKEN'] = self.valid_service_token
        self.headers = {
            'X-Service-Token': self.valid_service_token,
            'Content-Type': 'application/json'
        }
        # Create a test user. _create_user uses default "testuser", "test@example.com", "password123"
        # or specify them directly if needed for clarity or variation.
        # To ensure uniqueness if this class had multiple tests creating the same default user,
        # we could use a unique name here, e.g., based on the test method or a counter.
        # For now, relying on BaseTestCase's setUp/tearDown to isolate this single test method.
        # Create a test user. _create_user helper from BaseTestCase handles its own commit (user starts with balance 0).
        # Create a test user. _create_user helper from BaseTestCase handles its own commit (user starts with balance 0).
        created_user = self._create_user(username="internaltestuser_balcheck", email="internal_balcheck@example.com", password="password123")

        # Update balance. This operates in the app context pushed by BaseTestCase.setUp().
        # The 'created_user' object is already persistent and associated with the current session
        # due to db.session.refresh(user) in _create_user.
        created_user.balance = 1000  # Initial balance
        db.session.add(created_user) # Re-adding a persistent object is usually okay, it re-merges.
        db.session.commit() # Commit the balance update

        # self.user will be used for payload (user.id) and checking initial_balance in the test method.
        # Re-fetch to ensure the instance in the test method has the updated balance and is the same session instance.
        self.user = User.query.get(created_user.id)
        self.assertIsNotNone(self.user, "User is None after fetching post-balance update in setUp.")
        self.assertEqual(self.user.balance, 1000, "User balance not set correctly in setUp after update.")


    def tearDown(self):
        if 'SERVICE_API_TOKEN' in self.app.config:
            del self.app.config['SERVICE_API_TOKEN']
        super().tearDown()

    def test_update_player_balance_success(self):
        initial_balance = self.user.balance
        sats_to_add = 500
        payload = {
            "user_id": self.user.id,
            "sats_amount": sats_to_add,
            "original_tx_id": "test_btc_tx_123"
        }

        response = self.client.post('/api/internal/update_player_balance', data=json.dumps(payload), headers=self.headers)

        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertTrue(json_data['status'])
        self.assertEqual(json_data['status_message'], 'Balance updated successfully.')

        # Verify user balance in DB
        # Verify user balance in DB
        # The `db.session.remove()` in BaseTestCase.tearDown() will handle session cleanup for the next test.
        # For verifying the result of *this* test, we query within the current context.
        # The issue is that this query might see stale data.

        updated_user = User.query.get(self.user.id)
        if updated_user:
            self.app.logger.info(f"Balance from User.query.get(self.user.id) in test after client call: {updated_user.balance}")
            final_balance_in_test = updated_user.balance
        else:
            self.app.logger.error(f"User with ID {self.user.id} not found after API call in test method!")
            final_balance_in_test = -1

        # KNOWN ISSUE: The following assertion is expected to fail due to stale read.
        # Log analysis confirms:
        # 1. API route receives initial balance correctly (e.g., 1000).
        # 2. API route calculates and commits new balance correctly (e.g., 1500).
        # 3. This test method's query for `updated_user` reads stale data (e.g., 1000).
        # This indicates a persistent issue with transaction visibility/caching in the test environment
        # where commits by the app route (via test client) are not immediately visible to subsequent
        # queries from the test method's session, even with file-based DB and per-test app instances.
        self.assertEqual(final_balance_in_test, initial_balance + sats_to_add, "Balance in DB after API call is not as expected.")
        self.assertEqual(json_data['user']['balance'], initial_balance + sats_to_add, "Balance in API response is not as expected.")

        # Verify transaction record
        # This query might also see stale data if the transaction commit by the API route isn't visible.
        transaction = Transaction.query.filter_by(user_id=self.user.id, amount=sats_to_add).first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.transaction_type, 'deposit_btc')
        self.assertEqual(transaction.status, 'completed')
        self.assertIn('test_btc_tx_123', transaction.details.get('original_tx_id'))
        self.assertEqual(transaction.details.get('previous_balance_sats'), initial_balance)
        self.assertEqual(transaction.details.get('new_balance_sats'), initial_balance + sats_to_add)

    def test_update_player_balance_unauthorized_no_token(self):
        payload = {"user_id": self.user.id, "sats_amount": 100}
        headers_no_token = {'Content-Type': 'application/json'}
        response = self.client.post('/api/internal/update_player_balance', data=json.dumps(payload), headers=headers_no_token)
        json_data = response.get_json()
        self.assertEqual(response.status_code, 401)
        self.assertFalse(json_data['status'])
        self.assertEqual(json_data['error_code'], ErrorCodes.UNAUTHENTICATED) # Assuming service_token_required raises AuthenticationException
        self.assertEqual(json_data['status_message'], 'Service token is missing or invalid.')


    def test_update_player_balance_unauthorized_invalid_token(self):
        payload = {"user_id": self.user.id, "sats_amount": 100}
        headers_invalid_token = {
            'X-Service-Token': 'invalid_token_value',
            'Content-Type': 'application/json'
        }
        response = self.client.post('/api/internal/update_player_balance', data=json.dumps(payload), headers=headers_invalid_token)
        json_data = response.get_json()
        self.assertEqual(response.status_code, 403)
        self.assertFalse(json_data['status'])
        self.assertEqual(json_data['error_code'], ErrorCodes.FORBIDDEN) # Assuming service_token_required raises AuthorizationException
        self.assertEqual(json_data['status_message'], 'Service token is invalid.')


    def test_update_player_balance_user_not_found(self):
        payload = {
            "user_id": 99999, # Non-existent user
            "sats_amount": 100,
            "original_tx_id": "test_user_not_found_tx"
        }
        response = self.client.post('/api/internal/update_player_balance', data=json.dumps(payload), headers=self.headers)
        json_data = response.get_json()
        self.assertEqual(response.status_code, 404) # NotFoundException
        self.assertFalse(json_data['status'])
        self.assertEqual(json_data['error_code'], ErrorCodes.USER_NOT_FOUND)
        self.assertEqual(json_data['status_message'], "User with ID 99999 not found.")


    def test_update_player_balance_invalid_payload_missing_field(self):
        payload = {"user_id": self.user.id} # Missing sats_amount and original_tx_id
        response = self.client.post('/api/internal/update_player_balance', data=json.dumps(payload), headers=self.headers)
        json_data = response.get_json()
        self.assertEqual(response.status_code, 422) # ValidationException
        self.assertFalse(json_data['status'])
        self.assertEqual(json_data['error_code'], ErrorCodes.VALIDATION_ERROR)
        self.assertIn("sats_amount", json_data['details']['errors'])
        self.assertIn("original_tx_id", json_data['details']['errors'])

    def test_update_player_balance_invalid_payload_wrong_type(self):
        payload = {
            "user_id": self.user.id,
            "sats_amount": "not_an_integer", # Incorrect type
            "original_tx_id": "test_wrong_type_tx"
        }
        response = self.client.post('/api/internal/update_player_balance', data=json.dumps(payload), headers=self.headers)
        json_data = response.get_json()
        self.assertEqual(response.status_code, 422) # ValidationException
        self.assertFalse(json_data['status'])
        self.assertEqual(json_data['error_code'], ErrorCodes.VALIDATION_ERROR)
        self.assertIn("sats_amount", json_data['details']['errors']) # Marshmallow reports error on field
        self.assertIn("Not a valid integer.", "".join(json_data['details']['errors']['sats_amount']))


    def test_update_player_balance_invalid_payload_non_positive_sats(self):
        payload = {
            "user_id": self.user.id,
            "sats_amount": -100, # Non-positive
            "original_tx_id": "test_non_positive_tx"
        }
        response = self.client.post('/api/internal/update_player_balance', data=json.dumps(payload), headers=self.headers)
        json_data = response.get_json()
        self.assertEqual(response.status_code, 422) # ValidationException
        self.assertFalse(json_data['status'])
        self.assertEqual(json_data['error_code'], ErrorCodes.VALIDATION_ERROR)
        self.assertIn("sats_amount", json_data['details']['errors'])
        self.assertIn("must be greater than 0", "".join(json_data['details']['errors']['sats_amount'])) # Adjusted to match typical validator message


    def test_update_player_balance_no_json_payload(self):
        headers_no_json = self.headers.copy()
        headers_no_json['Content-Type'] = 'text/plain' # Incorrect content type
        response = self.client.post('/api/internal/update_player_balance', data="not json", headers=headers_no_json)
        json_data = response.get_json()
        # Werkzeug/Flask catches this early if content-type is not application/json and get_json(force=False/silent=False) is used.
        # Or if it's application/json but malformed.
        # This should be a 400 error, likely ErrorCodes.GENERIC_ERROR from handle_werkzeug_http_exception
        self.assertEqual(response.status_code, 400)
        self.assertFalse(json_data['status'])
        self.assertEqual(json_data['error_code'], ErrorCodes.GENERIC_ERROR) # Or specific parsing error if defined
        self.assertIn("Failed to decode JSON object", json_data['details']['description'])


if __name__ == '__main__':
    unittest.main()
