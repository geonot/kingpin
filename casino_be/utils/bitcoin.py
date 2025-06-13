# --- Bitcoin Utility Functions ---
# WARNING: All Bitcoin functionality in this module is MOCKED for development and testing purposes.
# It does NOT interact with the real Bitcoin network.
# Private key management, transaction broadcasting, and status checking are simulated.
# DO NOT USE THIS IN A PRODUCTION ENVIRONMENT WITH REAL BITCOIN.

import logging
import uuid
import os
from decimal import Decimal
import time
import random
import string
from flask import current_app

# Module-level storage for mocked transaction data
mock_sent_transactions = {} # Stores {txid: {'timestamp': float, 'amount_btc': Decimal, 'recipient': str}}

def generate_bitcoin_wallet():
    """
    Generates a new Bitcoin P2PKH address.
    FOR TESTING: Returns a dummy, random address.
    Private keys are NOT generated or returned by this function.
    """
    random_id = str(uuid.uuid4()).replace('-', '')[:12]
    dummy_address = f"dummyBtcAddr_{random_id}" # Added Addr_ for clarity
    if current_app:
        current_app.logger.info(f"Generated DUMMY Bitcoin address for testing: {dummy_address}")
    else: # Fallback logger if no app context
        logging.info(f"Generated DUMMY Bitcoin address for testing: {dummy_address}")
    return dummy_address

def send_bitcoin(recipient_address: str, amount_btc: Decimal) -> str:
    """
    MOCK FUNCTION: Simulates sending Bitcoin.
    Logs the action and returns a dummy transaction ID.
    Does NOT actually send any Bitcoin.
    Assumes DAILY_WITHDRAWAL_WALLET_WIF is available as an environment variable.
    """
    logger = current_app.logger if current_app else logging.getLogger(__name__)

    logger.info(f"Attempting to send {amount_btc:.8f} BTC to {recipient_address} (MOCKED)")

    # Simulate private key retrieval (not actually used in mock)
    wallet_wif = os.environ.get('DAILY_WITHDRAWAL_WALLET_WIF')
    if not wallet_wif:
        logger.warning("DAILY_WITHDRAWAL_WALLET_WIF environment variable not set. This is a mock, so proceeding.")
        # In a real scenario, this might raise an error or prevent sending.

    # Simulate transaction construction and broadcasting
    # In a real implementation, this would involve using a Bitcoin library (e.g., python-bitcoinlib)
    # to create, sign, and broadcast the transaction.

    time.sleep(random.uniform(0.5, 1.5)) # Simulate network delay

    # Generate a unique dummy transaction ID
    timestamp_str = str(int(time.time()))
    random_chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    dummy_txid = f"dummy_txid_{timestamp_str}_{random_chars}"

    # Store mock transaction info
    mock_sent_transactions[dummy_txid] = {
        'timestamp': time.time(),
        'amount_btc': amount_btc,
        'recipient': recipient_address,
        'status_history': [{'status': 'pending', 'timestamp': time.time()}]
    }

    logger.info(f"Successfully 'sent' {amount_btc:.8f} BTC to {recipient_address}. (MOCK) TXID: {dummy_txid}")
    return dummy_txid

def get_transaction_status(txid: str) -> dict:
    """
    MOCK FUNCTION: Simulates checking Bitcoin transaction status.
    Returns a mocked status based on previously "sent" dummy transactions.
    """
    logger = current_app.logger if current_app else logging.getLogger(__name__)
    logger.info(f"Checking status for TXID: {txid} (MOCKED)")

    if txid in mock_sent_transactions:
        tx_data = mock_sent_transactions[txid]
        time_since_sent = time.time() - tx_data['timestamp']

        # Simulate confirmations based on time passed
        if time_since_sent > 180: # More than 3 minutes
            confirmations = random.randint(6, 10)
            status = 'confirmed'
        elif time_since_sent > 120: # More than 2 minutes
            confirmations = random.randint(3, 5)
            status = 'pending'
        elif time_since_sent > 60: # More than 1 minute
            confirmations = random.randint(1, 2)
            status = 'pending'
        else: # Less than 1 minute
            confirmations = 0
            status = 'pending'

        # Update status history (optional, but good for more complex mocks)
        if tx_data['status_history'][-1]['status'] != status:
             tx_data['status_history'].append({'status': status, 'timestamp': time.time()})

        logger.info(f"Status for TXID {txid}: {status}, Confirmations: {confirmations} (MOCKED)")
        return {
            'txid': txid,
            'confirmations': confirmations,
            'status': status, # 'pending', 'confirmed', 'failed' (add later if needed)
            'amount_btc': str(tx_data['amount_btc']), # Return as string for consistency
            'recipient': tx_data['recipient'],
            'timestamp_sent': tx_data['timestamp']
        }
    elif txid.startswith("dummy_txid_"): # A dummy txid that was not 'sent' by this instance
        logger.warning(f"TXID {txid} looks like a dummy TXID but was not found in current mock session.")
        return {'txid': txid, 'confirmations': 0, 'status': 'not_found_in_session'}
    else: # A non-dummy txid (or an unknown dummy one)
        logger.info(f"TXID {txid} not found in mock data.")
        # In a real scenario, query a blockchain explorer API here
        # For mock, if it's not a known dummy txid, assume it's not found
        return {'txid': txid, 'confirmations': 0, 'status': 'not_found'}

# Example usage (for testing purposes within this file):
if __name__ == "__main__":
    # Basic logging setup for __main__ execution
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Note: current_app.logger won't be available here, so functions will use fallback logger.

    # Test generate_bitcoin_wallet
    print("\n--- Testing generate_bitcoin_wallet ---")
    addr1 = generate_bitcoin_wallet()
    addr2 = generate_bitcoin_wallet()
    print(f"Generated Address 1: {addr1}")
    print(f"Generated Address 2: {addr2}")

    # Test send_bitcoin
    print("\n--- Testing send_bitcoin ---")
    recipient = "mock_recipient_address_123"
    amount = Decimal("0.00123")
    # Set a dummy WIF for testing the os.environ.get part
    os.environ['DAILY_WITHDRAWAL_WALLET_WIF'] = 'cVerySecretWalletImportFormatKey'

    txid1 = send_bitcoin(recipient, amount)
    print(f"Sent! Mock TXID 1: {txid1}")

    txid2 = send_bitcoin("another_mock_address_456", Decimal("0.05"))
    print(f"Sent! Mock TXID 2: {txid2}")

    # Test get_transaction_status
    print("\n--- Testing get_transaction_status ---")
    print(f"Status for {txid1}: {get_transaction_status(txid1)}")
    print(f"Status for txid_unknown: {get_transaction_status('txid_unknown_real_or_fake')}")

    print("\nSimulating time passing for confirmations...")
    # For txid1, let's manually adjust its timestamp to simulate it being older for testing confirmations
    if txid1 in mock_sent_transactions:
        mock_sent_transactions[txid1]['timestamp'] = time.time() - 185 # Simulate it was sent ~3 minutes ago

    print(f"Status for {txid1} (after simulated time): {get_transaction_status(txid1)}")
    print(f"Status for {txid2} (should have fewer confirmations): {get_transaction_status(txid2)}")

    # Test a dummy txid not in current session
    unknown_dummy_txid = "dummy_txid_12345_abcdef"
    print(f"Status for {unknown_dummy_txid}: {get_transaction_status(unknown_dummy_txid)}")

    # Clean up env variable if set for test
    if 'DAILY_WITHDRAWAL_WALLET_WIF' in os.environ:
        del os.environ['DAILY_WITHDRAWAL_WALLET_WIF']

    print("\n--- Mock Bitcoin Utils Test Complete ---")
