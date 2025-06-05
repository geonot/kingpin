# --- Bitcoin Wallet Generation Utility ---
# WARNING: This uses the 'bitcoin' library which might be outdated or unmaintained.
# Consider using more modern libraries like 'python-bitcoinlib' or 'bit'.
# Also, generating and storing private keys directly in the database is EXTREMELY INSECURE for production.
# Use Hardware Security Modules (HSMs), dedicated key management services, or hierarchical deterministic (HD) wallets.
# This implementation is for demonstration purposes ONLY.

import logging
from flask import current_app

DUMMY_WALLET_COUNT = 0

def generate_bitcoin_wallet():
    """
    Generates a new Bitcoin P2PKH address.
    FOR TESTING: Returns a dummy, predictable address.
    Private keys are NOT generated or returned by this function.
    """
    global DUMMY_WALLET_COUNT
    DUMMY_WALLET_COUNT += 1
    # Return a simple, non-random, but unique enough for testing, dummy address
    dummy_address = f"dummyBitcoinAddress{DUMMY_WALLET_COUNT}"
    current_app.logger.info(f"Generated DUMMY Bitcoin address for testing: {dummy_address}")
    return dummy_address

# Example usage (for testing purposes):
if __name__ == "__main__":
    # logging.basicConfig(level=logging.INFO) # This would require app context if using current_app.logger
    address1 = generate_bitcoin_wallet()
    address2 = generate_bitcoin_wallet()
    if address1 and address2:
        print(f"Generated Address 1: {address1}")
        print(f"Generated Address 2: {address2}")
    else:
        print("Failed to generate address.")
