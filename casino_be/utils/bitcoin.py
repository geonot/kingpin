# --- Bitcoin Wallet Generation Utility ---
# WARNING: This uses the 'bitcoin' library which might be outdated or unmaintained.
# Consider using more modern libraries like 'python-bitcoinlib' or 'bit'.
# Also, generating and storing private keys directly in the database is EXTREMELY INSECURE for production.
# Use Hardware Security Modules (HSMs), dedicated key management services, or hierarchical deterministic (HD) wallets.
# This implementation is for demonstration purposes ONLY.

import os
from bitcoin import SelectParams
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress
import logging

logger = logging.getLogger(__name__)

def generate_bitcoin_wallet():
    """
    Generates a new Bitcoin private key and its corresponding P2PKH address.

    Returns:
        tuple: (address: str, private_key_wif: str) or (None, None) if error occurs.
               Address is the public Bitcoin address.
               Private key is in Wallet Import Format (WIF).
    """
    try:
        # Select the Bitcoin network ('mainnet' or 'testnet')
        # Use 'testnet' for development/testing to avoid using real Bitcoin
        # network = 'testnet' if os.environ.get('FLASK_ENV') == 'development' else 'mainnet'
        network = 'mainnet' # Set explicitly for now, configure properly based on env
        SelectParams(network)
        logger.info(f"Generating Bitcoin wallet on network: {network}")

        # Generate 32 random bytes for the private key secret
        # Using os.urandom for cryptographic randomness
        secret_bytes = os.urandom(32)

        # Create the private key object
        # The True argument compresses the corresponding public key, which is standard practice
        private_key = CBitcoinSecret.from_secret_bytes(secret_bytes, compressed=True)

        # Derive the public key from the private key
        public_key = private_key.pub

        # Generate the P2PKH (Pay-to-Public-Key-Hash) address from the public key
        public_address = P2PKHBitcoinAddress.from_pubkey(public_key)

        # Convert to string representation
        address_str = str(public_address)
        private_key_wif_str = str(private_key) # WIF format

        logger.info(f"Generated new Bitcoin address: {address_str}")
        # Avoid logging private keys even in debug mode in real applications
        # logger.debug(f"Generated private key (WIF): {private_key_wif_str}")

        return address_str, private_key_wif_str

    except ImportError:
        logger.error("The 'bitcoin' library is not installed. Cannot generate wallet.")
        logger.error("Install it using: pip install bitcoin")
        return None, None
    except Exception as e:
        logger.error(f"An error occurred during Bitcoin wallet generation: {e}", exc_info=True)
        return None, None

# Example usage (for testing purposes):
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    address, priv_key = generate_bitcoin_wallet()
    if address and priv_key:
        print(f"Generated Address: {address}")
        # print(f"Private Key (WIF): {priv_key}") # Be careful printing private keys
    else:
        print("Failed to generate wallet.")

