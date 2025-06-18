import unittest
from unittest.mock import patch, MagicMock, call, ANY
import os
import time

import sys

from casino_be.services import bitcoin_poller
from casino_be.app import create_app, db
from casino_be.models import User

import uuid
from .test_api import BaseTestCase

ORIGINAL_ENV = os.environ.copy()

class TestBitcoinPoller(BaseTestCase):

    def setUp(self):
        super().setUp()

        self.app.config['SERVICE_API_TOKEN'] = 'test_poller_service_api_token_for_poller_tests'
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

        bitcoin_poller.PROCESSED_TX_IDS.clear()

        self.user1 = self._create_user(
            username='polleruser1',
            email='poll1@example.com',
            deposit_wallet_address=self.known_test_address
        )
        self.user2 = self._create_user(
            username='polleruser2',
            email='poll2@example.com',
            deposit_wallet_address=f"another_addr_poller_{uuid.uuid4().hex[:6]}"
        )

        self.user1_id = self.user1.id
        self.user1_deposit_address = self.user1.deposit_wallet_address
        self.user2_id = self.user2.id
        self.user2_deposit_address = self.user2.deposit_wallet_address

    def tearDown(self):
        super().tearDown()

    @patch('casino_be.services.bitcoin_poller.requests.get')
    @patch('casino_be.services.bitcoin_poller.send_to_hot_wallet')
    @patch('casino_be.services.bitcoin_poller.update_player_balance_api')
    @patch('casino_be.services.bitcoin_poller.get_private_key_for_address')
    def test_check_address_new_confirmed_transaction(
        self, mock_get_priv_key, mock_update_balance_api, mock_send_hot_wallet, mock_requests_get
    ):
        user_id = self.user1_id
        deposit_address = self.user1_deposit_address
        txid = "testtxid123"
        amount_sats = 100000
        dummy_cycle_id = "test_cycle_new_tx"

        mock_explorer_response = MagicMock()
        mock_explorer_response.json.return_value = [{
            "txid": txid, "version": 1, "locktime": 0, "vin": [],
            "vout": [{"scriptpubkey_address": deposit_address, "value": amount_sats}],
            "status": {"confirmed": True, "block_height": 123456, "block_hash": "somehash", "block_time": time.time()}
        }]
        mock_explorer_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_explorer_response

        mock_get_priv_key.return_value = self.known_test_wif
        mock_send_hot_wallet.return_value = "dummy_sweep_txid_789"
        mock_update_balance_api.return_value = True

        bitcoin_poller.check_address_for_transactions(deposit_address, user_id, dummy_cycle_id)

        mock_requests_get.assert_called_once_with(f"{bitcoin_poller.BLOCKCHAIN_EXPLORER_API_BASE_URL}/address/{deposit_address}/txs", timeout=20)
        mock_get_priv_key.assert_called_once_with(deposit_address)
        mock_send_hot_wallet.assert_called_once_with(
            private_key_wif=self.known_test_wif,
            amount_sats=amount_sats,
            hot_wallet_address=bitcoin_poller.HOT_WALLET_ADDRESS,
            fee_sats=1000
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
        bitcoin_poller.PROCESSED_TX_IDS.add(txid)

        mock_explorer_response = MagicMock()
        mock_explorer_response.json.return_value = [{"txid": txid, "status": {"confirmed": True, "block_height": 123}}]
        mock_explorer_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_explorer_response

        bitcoin_poller.check_address_for_transactions(deposit_address, user_id, "test_cycle_already_proc")

        mock_requests_get.assert_called_once()
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
        mock_explorer_response.json.return_value = [{"txid": txid, "status": {"confirmed": False}}]
        mock_explorer_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_explorer_response

        bitcoin_poller.check_address_for_transactions(deposit_address, user_id, "test_cycle_unconfirmed")

        mock_requests_get.assert_called_once()
        mock_send_hot_wallet.assert_not_called()
        mock_update_balance_api.assert_not_called()
        self.assertNotIn(txid, bitcoin_poller.PROCESSED_TX_IDS)

    @patch('casino_be.services.bitcoin_poller.requests.get')
    def test_check_address_no_transactions_returned(self, mock_requests_get):
        mock_explorer_response = MagicMock()
        mock_explorer_response.json.return_value = []
        mock_explorer_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_explorer_response

        bitcoin_poller.check_address_for_transactions(self.user1_deposit_address, self.user1_id, "test_cycle_no_tx")
        mock_requests_get.assert_called_once()

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
        mock_get_priv_key.return_value = None

        bitcoin_poller.check_address_for_transactions(deposit_address, user_id, "test_cycle_no_priv_key")

        mock_get_priv_key.assert_called_once_with(deposit_address)
        mock_send_hot_wallet.assert_not_called() # Should not attempt send if no private key
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
        mock_send_hot_wallet.return_value = None

        bitcoin_poller.check_address_for_transactions(deposit_address, user_id, "test_cycle_sweep_fail")

        mock_send_hot_wallet.assert_called_once()
        mock_update_balance_api.assert_not_called()
        self.assertNotIn(txid, bitcoin_poller.PROCESSED_TX_IDS)

    @patch('casino_be.services.bitcoin_poller.create_app')
    @patch('casino_be.services.bitcoin_poller.check_address_for_transactions')
    def test_poll_deposits_main_loop_iteration(self, mock_check_address_txs, mock_poller_create_app):
        mock_poller_create_app.return_value = self.app

        bitcoin_poller.poll_deposits()

        expected_calls = [
            call(self.user1_deposit_address, self.user1_id, ANY),
            call(self.user2_deposit_address, self.user2_id, ANY)
        ]
        mock_check_address_txs.assert_has_calls(expected_calls, any_order=True)
        self.assertEqual(mock_check_address_txs.call_count, 2)

if __name__ == '__main__':
    unittest.main()
