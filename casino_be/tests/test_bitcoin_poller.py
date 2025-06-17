import unittest
from unittest.mock import patch, MagicMock, call
import os
import time # For potential time.sleep mocks if needed, though not primary here

# Temporarily adjust PYTHONPATH for poller imports if run directly before full packaging
import sys
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from casino_be.services import bitcoin_poller # Direct import for patching
from casino_be.app import create_app, db # For app context
from casino_be.models import User # For creating test users

import uuid # Added for unique addresses
from .test_api import BaseTestCase # Import BaseTestCase

# Store original environment variables that poller might modify or depend on
ORIGINAL_ENV = os.environ.copy()

class TestBitcoinPoller(BaseTestCase): # Inherit from BaseTestCase

    def setUp(self):
        super().setUp() # Call BaseTestCase.setUp() for app context and db init

        # It's crucial to ensure poller's module-level config is what we expect for tests
        # Access app config via self.app set by BaseTestCase
        self.app.config['SERVICE_API_TOKEN'] = 'test_poller_service_api_token_for_poller_tests' # Make it unique for this test class
        bitcoin_poller.SERVICE_API_TOKEN = self.app.config['SERVICE_API_TOKEN']

        bitcoin_poller.INTERNAL_API_ENDPOINT_UPDATE_BALANCE = "http://localhost:5000/api/internal/update_player_balance"
        bitcoin_poller.BLOCKCHAIN_EXPLORER_API_BASE_URL = "https://blockstream.info/testnet/api"
        bitcoin_poller.MIN_CONFIRMATIONS = 1
        bitcoin_poller.HOT_WALLET_ADDRESS = "test_hot_wallet_address_poller"
        bitcoin_poller.NETWORK = "testnet"

        self.known_test_address = f"tb1q_poller_known_{uuid.uuid4().hex[:10]}"
        self.known_test_wif = f"cTestPollerWIF_{uuid.uuid4().hex[:10]}"
        bitcoin_poller.KNOWN_TESTNET_ADDRESS_FOR_POLLER_SIMULATION = self.known_test_address
        bitcoin_poller.KNOWN_TESTNET_WIF_FOR_POLLER_SIMULATION = self.known_test_wif

        # Reset processed TXIDs for each test
        bitcoin_poller.PROCESSED_TX_IDS.clear()

        # Create test users using the helper from BaseTestCase
        # For user1, pass the known_test_address directly to _create_user.
        self.user1 = self._create_user(
            username='polleruser1',
            email='poll1@example.com',
            deposit_wallet_address=self.known_test_address
        )

        # For user2, let _create_user generate its default unique address or specify another unique one.
        self.user2 = self._create_user(
            username='polleruser2',
            email='poll2@example.com',
            deposit_wallet_address=f"another_addr_poller_{uuid.uuid4().hex[:6]}" # Explicitly unique
        )

        # db.session.commit() might not be needed here if _create_user already commits and refreshes.
        # BaseTestCase._create_user does commit and refresh.

        # Store IDs and addresses for assertions
        self.user1_id = self.user1.id
        self.user1_deposit_address = self.user1.deposit_wallet_address
        self.user2_id = self.user2.id
        self.user2_deposit_address = self.user2.deposit_wallet_address

    def tearDown(self):
        # Restore original environment variables if they were modified directly at module level
        # os.environ = ORIGINAL_ENV # This might be too broad if BaseTestCase also modifies os.environ
        # Specific cleanup of poller module vars if needed, or rely on setUp to reset them.
        # Reset poller config to avoid interference if absolutely necessary, though setUp should handle it.
        super().tearDown() # Call BaseTestCase.tearDown() for db cleanup

    @patch('casino_be.services.bitcoin_poller.requests.get')
    @patch('casino_be.services.bitcoin_poller.send_to_hot_wallet')
    @patch('casino_be.services.bitcoin_poller.update_player_balance_api')
    @patch('casino_be.services.bitcoin_poller.get_private_key_for_address')
    def test_check_address_new_confirmed_transaction(
        self, mock_get_priv_key, mock_update_balance_api, mock_send_hot_wallet, mock_requests_get
    ):
        # --- ARRANGE ---
        # Use the stored IDs and addresses from setUp
        user_id = self.user1_id
        deposit_address = self.user1_deposit_address
        txid = "testtxid123"
        amount_sats = 100000

        # Mock blockchain explorer response
        mock_explorer_response = MagicMock()
        mock_explorer_response.json.return_value = [{
            "txid": txid,
            "version": 1,
            "locktime": 0,
            "vin": [], # Simplified
            "vout": [{
                "scriptpubkey_address": deposit_address,
                "value": amount_sats
            }],
            "status": {"confirmed": True, "block_height": 123456, "block_hash": "somehash", "block_time": time.time()}
        }]
        mock_explorer_response.raise_for_status = MagicMock() # Ensure no HTTP error
        mock_requests_get.return_value = mock_explorer_response

        # Mock dependent functions
        mock_get_priv_key.return_value = self.known_test_wif # Corrected attribute name
        mock_send_hot_wallet.return_value = "dummy_sweep_txid_789" # Simulate successful sweep
        mock_update_balance_api.return_value = True # Simulate successful API update

        # --- ACT ---
        bitcoin_poller.check_address_for_transactions(deposit_address, user_id, "test_cycle_id")

        # --- ASSERT ---
        mock_requests_get.assert_called_once_with(f"{bitcoin_poller.BLOCKCHAIN_EXPLORER_API_BASE_URL}/address/{deposit_address}/txs", timeout=20)
        mock_get_priv_key.assert_called_once_with(deposit_address)
        mock_send_hot_wallet.assert_called_once_with(
            private_key_wif=self.known_test_wif, # Corrected attribute
            amount_sats=amount_sats,
            hot_wallet_address=bitcoin_poller.HOT_WALLET_ADDRESS,
            fee_sats=1000 # Default simulated fee in poller's check_address_for_transactions
        )
        mock_update_balance_api.assert_called_once_with(user_id, amount_sats, txid)
        self.assertIn(txid, bitcoin_poller.PROCESSED_TX_IDS)

    @patch('casino_be.services.bitcoin_poller.requests.get')
    @patch('casino_be.services.bitcoin_poller.send_to_hot_wallet')
    @patch('casino_be.services.bitcoin_poller.update_player_balance_api')
    def test_check_address_already_processed_transaction(
        self, mock_update_balance_api, mock_send_hot_wallet, mock_requests_get
    ):
        user_id = self.user1_id
        deposit_address = self.user1_deposit_address
        txid = "testtxid_processed"
        bitcoin_poller.PROCESSED_TX_IDS.add(txid) # Pre-mark as processed

        mock_explorer_response = MagicMock()
        mock_explorer_response.json.return_value = [{
            "txid": txid, "status": {"confirmed": True, "block_height": 123} # other fields omitted
        }]
        mock_explorer_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_explorer_response

        bitcoin_poller.check_address_for_transactions(deposit_address, user_id, "test_cycle_id")

        mock_requests_get.assert_called_once() # Still fetches from explorer
        mock_send_hot_wallet.assert_not_called()
        mock_update_balance_api.assert_not_called()

    @patch('casino_be.services.bitcoin_poller.requests.get')
    @patch('casino_be.services.bitcoin_poller.send_to_hot_wallet')
    @patch('casino_be.services.bitcoin_poller.update_player_balance_api')
    def test_check_address_unconfirmed_transaction(
        self, mock_update_balance_api, mock_send_hot_wallet, mock_requests_get
    ):
        user_id = self.user1_id
        deposit_address = self.user1_deposit_address
        txid = "testtxid_unconfirmed"
        mock_explorer_response = MagicMock()
        mock_explorer_response.json.return_value = [{
            "txid": txid, "status": {"confirmed": False} # Unconfirmed
        }]
        mock_explorer_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_explorer_response

        bitcoin_poller.check_address_for_transactions(deposit_address, user_id, "test_cycle_id")

        mock_requests_get.assert_called_once()
        mock_send_hot_wallet.assert_not_called()
        mock_update_balance_api.assert_not_called()
        self.assertNotIn(txid, bitcoin_poller.PROCESSED_TX_IDS)

    @patch('casino_be.services.bitcoin_poller.requests.get')
    def test_check_address_no_transactions_returned(self, mock_requests_get):
        mock_explorer_response = MagicMock()
        mock_explorer_response.json.return_value = [] # Empty list
        mock_explorer_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_explorer_response

        bitcoin_poller.check_address_for_transactions(self.user1_deposit_address, self.user1_id, "test_cycle_id")
        mock_requests_get.assert_called_once()
        # No other calls should be made

    @patch('casino_be.services.bitcoin_poller.requests.get')
    @patch('casino_be.services.bitcoin_poller.send_to_hot_wallet')
    @patch('casino_be.services.bitcoin_poller.update_player_balance_api')
    @patch('casino_be.services.bitcoin_poller.get_private_key_for_address')
    def test_check_address_error_fetching_private_key(
        self, mock_get_priv_key, mock_update_balance_api, mock_send_hot_wallet, mock_requests_get
    ):
        user_id = self.user1_id
        deposit_address = self.user1_deposit_address
        txid = "testtxid_no_priv_key"
        amount_sats = 50000

        mock_explorer_response = MagicMock()
        mock_explorer_response.json.return_value = [{
            "txid": txid, "vout": [{"scriptpubkey_address": deposit_address, "value": amount_sats}],
            "status": {"confirmed": True, "block_height": 123}
        }]
        mock_explorer_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_explorer_response

        mock_get_priv_key.return_value = None # Simulate private key retrieval failure

        bitcoin_poller.check_address_for_transactions(deposit_address, user_id, "test_cycle_id")

        mock_get_priv_key.assert_called_once_with(deposit_address)
        mock_send_hot_wallet.assert_not_called()
        mock_update_balance_api.assert_not_called()
        self.assertNotIn(txid, bitcoin_poller.PROCESSED_TX_IDS)

    @patch('casino_be.services.bitcoin_poller.requests.get')
    @patch('casino_be.services.bitcoin_poller.send_to_hot_wallet')
    @patch('casino_be.services.bitcoin_poller.update_player_balance_api')
    @patch('casino_be.services.bitcoin_poller.get_private_key_for_address')
    def test_check_address_send_to_hot_wallet_fails(
        self, mock_get_priv_key, mock_update_balance_api, mock_send_hot_wallet, mock_requests_get
    ):
        user_id = self.user1_id
        deposit_address = self.user1_deposit_address
        txid = "testtxid_sweep_fail"
        amount_sats = 70000

        mock_explorer_response = MagicMock()
        mock_explorer_response.json.return_value = [{
            "txid": txid, "vout": [{"scriptpubkey_address": deposit_address, "value": amount_sats}],
            "status": {"confirmed": True, "block_height": 123}
        }]
        mock_explorer_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_explorer_response

        mock_get_priv_key.return_value = self.known_test_wif
        mock_send_hot_wallet.return_value = None # Simulate sweep failure

        bitcoin_poller.check_address_for_transactions(deposit_address, user_id, "test_cycle_id")

        mock_send_hot_wallet.assert_called_once()
        mock_update_balance_api.assert_not_called()
        self.assertNotIn(txid, bitcoin_poller.PROCESSED_TX_IDS)


    @patch('casino_be.services.bitcoin_poller.check_address_for_transactions')
    def test_poll_deposits_main_loop_iteration(self, mock_check_address_txs):
        # Test one iteration of the main poll_deposits loop
        # This primarily tests that it fetches users and calls check_address_for_transactions for each

        # ARRANGE: Users are already created in setUp.

        # ACT
        bitcoin_poller.poll_deposits() # Runs within the app context set up by setUp/tearDown

        # ASSERT
        # Ensure check_address_for_transactions was called for each user with a deposit address
        # The cycle_id is generated within poll_deposits, so we use unittest.mock.ANY for it.
        expected_calls = [
            call(self.user1_deposit_address, self.user1_id, unittest.mock.ANY),
            call(self.user2_deposit_address, self.user2_id, unittest.mock.ANY)
        ]
        mock_check_address_txs.assert_has_calls(expected_calls, any_order=True)
        self.assertEqual(mock_check_address_txs.call_count, 2)


if __name__ == '__main__':
    # This allows running this test file directly, useful for debugging.
    # Ensure that the environment is set up correctly if running this way,
    # especially PYTHONPATH to find casino_be modules.
    # Example: PYTHONPATH=. python casino_be/tests/test_bitcoin_poller.py
    unittest.main()
