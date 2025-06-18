import logging
import time
import requests
from typing import Dict, List, Optional
from datetime import datetime, timezone

from models import db, User, Transaction
from utils.encryption import decrypt_private_key

logger = logging.getLogger(__name__)

class BitcoinMonitor:
    """
    Bitcoin blockchain monitoring service for detecting deposits.
    This service would run as a background process to monitor addresses.
    """
    
    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval  # seconds between checks
        self.running = False
        
    def start_monitoring(self):
        """Start the monitoring loop"""
        self.running = True
        logger.info("Bitcoin monitoring service started")
        
        while self.running:
            try:
                self.check_all_addresses()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.check_interval)
    
    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.running = False
        logger.info("Bitcoin monitoring service stopped")
    
    def check_all_addresses(self):
        """Check all user deposit addresses for new transactions"""
        users_with_addresses = User.query.filter(
            User.deposit_wallet_address.isnot(None)
        ).all()
        
        logger.debug(f"Checking {len(users_with_addresses)} addresses for deposits")
        
        for user in users_with_addresses:
            try:
                self.check_address_for_deposits(user)
            except Exception as e:
                logger.error(f"Error checking address for user {user.id}: {e}")
    
    def check_address_for_deposits(self, user: User):
        """Check a specific address for new deposits"""
        address = user.deposit_wallet_address
        
        # Get transaction history for the address
        transactions = self.get_address_transactions(address)
        
        for tx in transactions:
            # Check if we've already processed this transaction
            existing_tx = Transaction.query.filter_by(
                user_id=user.id,
                transaction_type='deposit',
                details={'btc_txid': tx['txid']}
            ).first()
            
            if not existing_tx:
                self.process_deposit_transaction(user, tx)
    
    def get_address_transactions(self, address: str) -> List[Dict]:
        """
        Get transaction history for a Bitcoin address.
        In production, this would use blockchain APIs or Bitcoin Core RPC.
        """
        try:
            # Example using blockchain.info API (free tier)
            # In production, use your own Bitcoin node or paid API
            url = f"https://blockchain.info/rawaddr/{address}?format=json"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                transactions = []
                
                for tx in data.get('txs', []):
                    # Check if this transaction sends money TO our address
                    for output in tx.get('out', []):
                        if output.get('addr') == address:
                            transactions.append({
                                'txid': tx['hash'],
                                'amount_sats': output['value'],
                                'confirmations': tx.get('confirmations', 0),
                                'timestamp': tx.get('time', 0)
                            })
                
                return transactions
            else:
                logger.warning(f"Failed to fetch transactions for {address}: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching transactions for {address}: {e}")
            return []
    
    def process_deposit_transaction(self, user: User, tx_data: Dict):
        """Process a detected deposit transaction"""
        amount_sats = tx_data['amount_sats']
        txid = tx_data['txid']
        confirmations = tx_data['confirmations']
        
        # Only process transactions with sufficient confirmations
        min_confirmations = 3  # Configurable
        
        if confirmations >= min_confirmations:
            try:
                # Credit the user's balance
                user.balance += amount_sats
                
                # Create a deposit transaction record
                transaction = Transaction(
                    user_id=user.id,
                    amount=amount_sats,
                    transaction_type='deposit',
                    status='completed',
                    details={
                        'btc_txid': txid,
                        'confirmations': confirmations,
                        'deposit_address': user.deposit_wallet_address,
                        'timestamp': tx_data.get('timestamp'),
                        'auto_detected': True
                    }
                )
                
                db.session.add(transaction)
                db.session.commit()
                
                logger.info(
                    f"Processed Bitcoin deposit for user {user.id}: "
                    f"{amount_sats} sats from txid {txid}"
                )
                
                # Could send notification to user here
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Failed to process deposit for user {user.id}: {e}")
        else:
            logger.info(
                f"Deposit detected for user {user.id} but insufficient confirmations: "
                f"{confirmations}/{min_confirmations}"
            )
    
    def get_address_balance(self, address: str) -> int:
        """Get current balance for an address in satoshis"""
        try:
            url = f"https://blockchain.info/rawaddr/{address}?format=json"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('final_balance', 0)
            else:
                logger.warning(f"Failed to fetch balance for {address}: {response.status_code}")
                return 0
                
        except Exception as e:
            logger.error(f"Error fetching balance for {address}: {e}")
            return 0


# Standalone monitoring function for background process
def run_bitcoin_monitor():
    """Function to run the Bitcoin monitor as a background process"""
    monitor = BitcoinMonitor()
    monitor.start_monitoring()


if __name__ == "__main__":
    # For testing the monitor standalone
    import sys
    import os
    
    # Add the parent directory to the Python path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from app import create_app
    
    app = create_app()
    with app.app_context():
        run_bitcoin_monitor()
