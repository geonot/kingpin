import unittest
import re
from unittest.mock import MagicMock # For MagicMock
import os
import sys # Not strictly needed now but good for consistency if other tests use it
import importlib # Not strictly needed now

from flask import current_app, jsonify

from app import create_app, db
from models import User, Transaction
from utils.bitcoin import generate_bitcoin_wallet
from utils.encryption import encrypt_private_key, decrypt_private_key
from config import TestingConfig
# No import of bitcoin_routes_module needed for current_app strategy

TEST_ENCRYPTION_SECRET = 'test_secret_key_for_bitcoin_wallet_tests_12345'

class TestBitcoinWalletManagement(unittest.TestCase):

    def setUp(self):
        """Set up for each test."""
        self.app = create_app(config_class=TestingConfig)
        self.app.config['ENCRYPTION_SECRET'] = TEST_ENCRYPTION_SECRET
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        """Tear down after each test."""
        db.session.remove()
        db.drop_all()
        db_uri = TestingConfig.SQLALCHEMY_DATABASE_URI
        if db_uri.startswith('sqlite:///'):
            db_file = db_uri.replace('sqlite:///', '')
            if os.path.exists(db_file) and db_file != ':memory:':
                os.remove(db_file)
        self.app_context.pop()

    def test_generate_bitcoin_wallet(self):
        """Test the generate_bitcoin_wallet utility function."""
        address, private_key_wif = generate_bitcoin_wallet()
        self.assertIsNotNone(address)
        self.assertIsInstance(address, str)
        self.assertTrue(len(address) > 0)
        self.assertIsNotNone(private_key_wif)
        self.assertIsInstance(private_key_wif, str)
        self.assertTrue(len(private_key_wif) > 0)
        is_valid_address = re.match(r'^[13mn2bct][a-zA-HJ-NP-Z0-9]{25,59}$', address)
        self.assertTrue(is_valid_address, f"Generated address {address} does not match basic format.")

    def test_private_key_encryption_decryption(self):
        """Test encryption and decryption of a private key."""
        _address, original_wif = generate_bitcoin_wallet()
        self.assertTrue(original_wif)
        encrypted_key_hex = encrypt_private_key(original_wif)
        self.assertIsNotNone(encrypted_key_hex)
        self.assertNotEqual(original_wif, encrypted_key_hex)
        decrypted_wif = decrypt_private_key(encrypted_key_hex)
        self.assertIsNotNone(decrypted_wif)
        self.assertEqual(original_wif, decrypted_wif)

    def test_get_deposit_address_api(self):
        """Test the GET /api/bitcoin/deposit-address endpoint."""
        register_payload = {
            'username': 'testuser_api',
            'email': 'test_api_user@example.com',
            'password': 'StrongPassword123!'
        }
        resp_register = self.client.post('/api/register', json=register_payload)
        self.assertEqual(resp_register.status_code, 201, f"Registration failed: {resp_register.get_data(as_text=True)}")

        user = User.query.filter_by(username='testuser_api').first()
        self.assertIsNotNone(user)
        initial_address = user.deposit_wallet_address

        login_payload = {'username': 'testuser_api', 'password': 'StrongPassword123!'}
        resp_login = self.client.post('/api/login', json=login_payload)
        self.assertEqual(resp_login.status_code, 200, f"Login failed: {resp_login.get_data(as_text=True)}")

        resp_deposit_address = self.client.get('/api/bitcoin/deposit-address')
        self.assertEqual(resp_deposit_address.status_code, 200, f"API call failed: {resp_deposit_address.get_data(as_text=True)}")

        data = resp_deposit_address.get_json()
        self.assertTrue(data['status'])
        api_address = data['deposit_address']

        user_updated = User.query.filter_by(username='testuser_api').first()
        self.assertEqual(user_updated.deposit_wallet_address, api_address)
        self.assertEqual(api_address, initial_address)

        self.assertIsNotNone(user_updated.deposit_wallet_private_key)
        decrypted_wif = decrypt_private_key(user_updated.deposit_wallet_private_key)
        self.assertTrue(re.match(r'^[59KLc][a-zA-HJ-NP-Z0-9]{50,51}$', decrypted_wif), f"Decrypted WIF {decrypted_wif} does not match basic WIF format.")

    def test_process_withdrawal_api(self):
        """Test the POST /api/bitcoin/process-withdrawal endpoint using current_app seam."""

        mock_send_tx = MagicMock(return_value='dummy_txid_for_withdrawal_app_attr')

        original_env_value = os.environ.get('TEST_MODE_ACTIVE_FOR_BTC_SENDER')
        os.environ['TEST_MODE_ACTIVE_FOR_BTC_SENDER'] = '1'

        # Store original attribute if it exists on self.app (which is current_app during test request)
        original_app_attr = getattr(self.app, 'test_btc_sender_override', None)
        self.app.test_btc_sender_override = mock_send_tx

        # Cleanup logic using addCleanup
        self.addCleanup(os.environ.pop, 'TEST_MODE_ACTIVE_FOR_BTC_SENDER', None)
        if original_env_value is not None:
            self.addCleanup(os.environ.__setitem__, 'TEST_MODE_ACTIVE_FOR_BTC_SENDER', original_env_value)

        if original_app_attr is not None:
            self.addCleanup(setattr, self.app, 'test_btc_sender_override', original_app_attr)
        else:
            self.addCleanup(lambda: hasattr(self.app, 'test_btc_sender_override') and delattr(self.app, 'test_btc_sender_override'))

        # 1. Create User and Transaction
        user = User(username='withdraw_user_seam', email='withdraw_seam@example.com', password=User.hash_password('StrongPassword123!'))
        # Use a valid Testnet WIF: cUZES61ThB2r2isT7JzgyCPxH1HDPfX2A2p8s2YUDbQ27Jg3uE8M
        valid_testnet_wif = "cUZES61ThB2r2isT7JzgyCPxH1HDPfX2A2p8s2YUDbQ27Jg3uE8M"
        encrypted_pk = encrypt_private_key(valid_testnet_wif)
        user.deposit_wallet_address = "mtestAddressForWithdrawSeam"
        user.deposit_wallet_private_key = encrypted_pk
        db.session.add(user)
        db.session.commit()

        withdraw_amount = 50000
        mock_recipient_address = 'mock_withdraw_address_seam_123'
        transaction = Transaction(
            user_id=user.id, amount=withdraw_amount, transaction_type='withdraw',
            status='pending', details={'withdraw_address': mock_recipient_address}
        )
        db.session.add(transaction)
        db.session.commit()
        created_transaction_id = transaction.id

        # 2. Login user
        login_payload = {'username': 'withdraw_user_seam', 'password': 'StrongPassword123!'}
        resp_login = self.client.post('/api/login', json=login_payload)
        self.assertEqual(resp_login.status_code, 200, f"Login failed: {resp_login.get_data(as_text=True)}")

        # 3. Make the API call to process withdrawal
        withdrawal_payload = {'transaction_id': created_transaction_id}
        resp_withdraw = self.client.post('/api/bitcoin/process-withdrawal', json=withdrawal_payload)

        # 4. Assert outcomes
        self.assertEqual(resp_withdraw.status_code, 200, f"Withdrawal API call failed: {resp_withdraw.get_data(as_text=True)}")
        data = resp_withdraw.get_json()
        self.assertTrue(data['status'])
        self.assertEqual(data['status_message'], 'Withdrawal processed')
        self.assertEqual(data['txid'], 'dummy_txid_for_withdrawal_app_attr')

        # Verify mock was called correctly
        mock_send_tx.assert_called_once()

        expected_decrypted_pk = decrypt_private_key(user.deposit_wallet_private_key)
        self.assertEqual(mock_send_tx.call_args[0][0], expected_decrypted_pk)
        self.assertEqual(mock_send_tx.call_args[0][1], withdraw_amount)
        self.assertEqual(mock_send_tx.call_args[0][2], mock_recipient_address)
        self.assertEqual(mock_send_tx.call_args[0][3], 5000) # Expected fee

        db_transaction = db.session.get(Transaction, created_transaction_id)
        self.assertIsNotNone(db_transaction)
        self.assertEqual(db_transaction.status, 'completed')
        self.assertIn('txid', db_transaction.details)
        self.assertEqual(db_transaction.details['txid'], 'dummy_txid_for_withdrawal_app_attr')

    def test_check_deposits_api_placeholder(self):
        """Test the POST /api/bitcoin/check-deposits placeholder endpoint."""
        # Scenario 1: User has a deposit address
        register_payload_s1 = {
            'username': 'checkdeposits_user1',
            'email': 'checkdeposits1@example.com',
            'password': 'StrongPassword123!'
        }
        resp_register_s1 = self.client.post('/api/register', json=register_payload_s1)
        self.assertEqual(resp_register_s1.status_code, 201)

        login_payload_s1 = {'username': 'checkdeposits_user1', 'password': 'StrongPassword123!'}
        resp_login_s1 = self.client.post('/api/login', json=login_payload_s1)
        self.assertEqual(resp_login_s1.status_code, 200)

        # Ensure deposit address exists (registration should create it)
        user_s1 = User.query.filter_by(username='checkdeposits_user1').first()
        self.assertIsNotNone(user_s1.deposit_wallet_address)

        resp_check_s1 = self.client.post('/api/bitcoin/check-deposits', json={}) # Empty JSON payload as per typical POST
        self.assertEqual(resp_check_s1.status_code, 200)
        data_s1 = resp_check_s1.get_json()
        self.assertTrue(data_s1['status'])
        self.assertEqual(data_s1['status_message'], 'No new deposits found')
        self.assertTrue(data_s1['deposits_checked'])

        # Scenario 2: User does NOT have a deposit address
        register_payload_s2 = {
            'username': 'checkdeposits_user2',
            'email': 'checkdeposits2@example.com',
            'password': 'StrongPassword123!'
        }
        resp_register_s2 = self.client.post('/api/register', json=register_payload_s2)
        self.assertEqual(resp_register_s2.status_code, 201)

        user_s2 = User.query.filter_by(username='checkdeposits_user2').first()
        self.assertIsNotNone(user_s2)
        # Manually remove deposit address for this test case
        user_s2.deposit_wallet_address = None
        user_s2.deposit_wallet_private_key = None # Also clear private key if it was set
        db.session.commit()

        login_payload_s2 = {'username': 'checkdeposits_user2', 'password': 'StrongPassword123!'}
        resp_login_s2 = self.client.post('/api/login', json=login_payload_s2)
        self.assertEqual(resp_login_s2.status_code, 200)

        resp_check_s2 = self.client.post('/api/bitcoin/check-deposits', json={})
        self.assertEqual(resp_check_s2.status_code, 400)
        data_s2 = resp_check_s2.get_json()
        self.assertFalse(data_s2['status'])
        self.assertEqual(data_s2['status_message'], 'No deposit address found')

    def test_get_wallet_balance_api_placeholder(self):
        """Test the GET /api/bitcoin/balance placeholder endpoint."""
        # Scenario 1: User has a deposit address
        register_payload_s1 = {
            'username': 'balanceuser1',
            'email': 'bal_user1@example.com', # Changed email
            'password': 'StrongPassword123!'
        }
        resp_register_s1 = self.client.post('/api/register', json=register_payload_s1)
        self.assertEqual(resp_register_s1.status_code, 201)

        user_s1 = User.query.filter_by(username='balanceuser1').first()
        self.assertIsNotNone(user_s1)
        self.assertIsNotNone(user_s1.deposit_wallet_address) # Should be created by register
        expected_address_s1 = user_s1.deposit_wallet_address

        login_payload_s1 = {'username': 'balanceuser1', 'password': 'StrongPassword123!'}
        resp_login_s1 = self.client.post('/api/login', json=login_payload_s1)
        self.assertEqual(resp_login_s1.status_code, 200)

        resp_balance_s1 = self.client.get('/api/bitcoin/balance')
        self.assertEqual(resp_balance_s1.status_code, 200)
        data_s1 = resp_balance_s1.get_json()
        self.assertTrue(data_s1['status'])
        self.assertEqual(data_s1['address'], expected_address_s1)
        self.assertEqual(data_s1['balance_sats'], 0) # Placeholder balance
        self.assertEqual(data_s1['status_message'], 'Balance retrieved (demo mode)')

        # Scenario 2: User does NOT have a deposit address
        register_payload_s2 = {
            'username': 'balanceuser2',
            'email': 'bal_user2@example.com', # Changed email
            'password': 'StrongPassword123!'
        }
        resp_register_s2 = self.client.post('/api/register', json=register_payload_s2)
        self.assertEqual(resp_register_s2.status_code, 201)

        user_s2 = User.query.filter_by(username='balanceuser2').first()
        self.assertIsNotNone(user_s2)
        # Manually remove deposit address for this test case
        user_s2.deposit_wallet_address = None
        user_s2.deposit_wallet_private_key = None
        db.session.commit()

        login_payload_s2 = {'username': 'balanceuser2', 'password': 'StrongPassword123!'}
        resp_login_s2 = self.client.post('/api/login', json=login_payload_s2)
        self.assertEqual(resp_login_s2.status_code, 200)

        resp_balance_s2 = self.client.get('/api/bitcoin/balance')
        self.assertEqual(resp_balance_s2.status_code, 200)
        data_s2 = resp_balance_s2.get_json()
        self.assertTrue(data_s2['status'])
        self.assertIsNone(data_s2['address'])
        self.assertEqual(data_s2['balance_sats'], 0)
        self.assertEqual(data_s2['status_message'], 'No wallet address configured')


if __name__ == '__main__':
    unittest.main()
