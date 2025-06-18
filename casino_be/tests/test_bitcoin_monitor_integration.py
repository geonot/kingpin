import unittest
from unittest.mock import patch, MagicMock
import time
from datetime import datetime, timezone
from sqlalchemy import select # Import select

from casino_be.app import create_app, db
from casino_be.models import User, Transaction
from casino_be.services.bitcoin_monitor import BitcoinMonitor
from casino_be.config import TestingConfig

# Use BaseTestCase from test_api for app context and db management
from .test_api import BaseTestCase

class TestBitcoinMonitorIntegration(BaseTestCase):

    def setUp(self):
        super().setUp()
        # Test user and deposit address
        self.deposit_address = "mock_deposit_address_monitor_test"
        self.user = self._create_user(
            username="monitor_user",
            email="monitor@example.com",
            password="StrongPassword123!",
            deposit_wallet_address=self.deposit_address
        )
        self.initial_balance = self.user.balance
        # self.user is directly from _create_user, which should have the correct address.
        # No need to re-fetch with db.session.get(User, self.user.id) here if _create_user is trusted.
        self.assertIsNotNone(self.user, "User object from _create_user should not be None.")
        self.assertEqual(self.user.deposit_wallet_address, self.deposit_address, "User's deposit address should match the one set.")


    @patch('casino_be.services.bitcoin_monitor.requests.get')
    def test_check_address_for_deposits_mocked_new_transaction(self, mock_requests_get):
        """Test BitcoinMonitor processing a new confirmed transaction from mocked API."""
        monitor = BitcoinMonitor(check_interval=1) # Short interval for test

        # Mocked API response for blockchain.info/rawaddr/{address}
        tx_hash = "mock_tx_hash_monitor_test_123"
        amount_sats = 100000 # 0.001 BTC

        mock_api_response_data = {
            "address": self.deposit_address,
            "n_tx": 1,
            "total_received": amount_sats,
            "total_sent": 0,
            "final_balance": amount_sats,
            "txs": [
                {
                    "hash": tx_hash,
                    "ver": 1,
                    "vin_sz": 1,
                    "vout_sz": 1,
                    "time": int(time.time()), # Current time as epoch
                    "block_height": 700000, # Example block height
                    "confirmations": 3, # Sufficient confirmations
                    "inputs": [{"prev_out": {"addr": "some_other_address", "value": amount_sats}}],
                    "out": [
                        {"value": amount_sats, "addr": self.deposit_address, "script": "mock_script_pk"},
                        # Potentially other outputs not to our address
                    ]
                }
            ]
        }
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_api_response_data
        mock_requests_get.return_value = mock_response_obj

        # --- ACT ---
        # Directly call the method that processes deposits for a user
        monitor.check_address_for_deposits(self.user)

        # --- ASSERT ---
        # Check if requests.get was called correctly
        expected_url = f"https://blockchain.info/rawaddr/{self.deposit_address}?format=json"
        mock_requests_get.assert_called_once_with(expected_url, timeout=10)

        # Check user balance update
        updated_user = db.session.get(User, self.user.id) # Changed to db.session.get
        self.assertEqual(updated_user.balance, self.initial_balance + amount_sats)

        # Check Transaction record creation
        stmt = select(Transaction).filter_by(user_id=self.user.id, transaction_type='deposit')
        transaction = db.session.execute(stmt).scalar_one_or_none()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.amount, amount_sats)
        self.assertEqual(transaction.status, 'completed')
        self.assertIn('btc_txid', transaction.details)
        self.assertEqual(transaction.details['btc_txid'], tx_hash)
        self.assertEqual(transaction.details['confirmations'], 3)
        self.assertTrue(transaction.details['auto_detected'])

    @patch('casino_be.services.bitcoin_monitor.requests.get')
    def test_check_address_for_deposits_insufficient_confirmations(self, mock_requests_get):
        """Test BitcoinMonitor ignoring a transaction with insufficient confirmations."""
        monitor = BitcoinMonitor(check_interval=1)

        tx_hash = "mock_tx_hash_insufficient_conf"
        amount_sats = 50000

        mock_api_response_data = {
            "txs": [{
                "hash": tx_hash, "time": int(time.time()), "confirmations": 1, # Insufficient
                "out": [{"value": amount_sats, "addr": self.deposit_address}]
            }]
        }
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_api_response_data
        mock_requests_get.return_value = mock_response_obj

        monitor.check_address_for_deposits(self.user)

        updated_user = db.session.get(User, self.user.id) # Changed to db.session.get
        self.assertEqual(updated_user.balance, self.initial_balance) # Balance should not change
        # Correct way to query JSON field:
        stmt = select(Transaction).filter(Transaction.details.op('->>')('btc_txid') == tx_hash)
        transaction = db.session.execute(stmt).scalar_one_or_none()
        self.assertIsNone(transaction) # No transaction should be recorded

    @patch('casino_be.services.bitcoin_monitor.requests.get')
    def test_check_address_for_deposits_transaction_already_processed(self, mock_requests_get):
        """Test BitcoinMonitor skipping an already processed transaction."""
        monitor = BitcoinMonitor(check_interval=1)

        tx_hash = "mock_tx_hash_already_processed"
        amount_sats = 75000

        # Pre-create a transaction record to simulate it being already processed
        existing_transaction = Transaction(
            user_id=self.user.id,
            amount=amount_sats,
            transaction_type='deposit',
            status='completed',
            details={'btc_txid': tx_hash, 'confirmations': 6, 'auto_detected': True}
        )
        db.session.add(existing_transaction)
        db.session.commit()
        self.user.balance += amount_sats # Reflect this in user's balance for accurate test
        db.session.commit()
        initial_balance_after_manual_tx = self.user.balance

        mock_api_response_data = {
            "txs": [{
                "hash": tx_hash, "time": int(time.time()), "confirmations": 6,
                "out": [{"value": amount_sats, "addr": self.deposit_address}]
            }]
        }
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_api_response_data
        mock_requests_get.return_value = mock_response_obj

        monitor.check_address_for_deposits(self.user)

        updated_user = db.session.get(User, self.user.id) # Changed to db.session.get
        self.assertEqual(updated_user.balance, initial_balance_after_manual_tx) # Balance should not change further
        # Ensure no new transaction record was created for this tx_hash
        stmt = select(Transaction).filter(Transaction.details.op('->>')('btc_txid') == tx_hash)
        transactions = db.session.execute(stmt).scalars().all()
        self.assertEqual(len(transactions), 1) # Only the one we manually created


if __name__ == '__main__':
    unittest.main()
