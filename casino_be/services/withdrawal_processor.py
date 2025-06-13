# casino_be/services/withdrawal_processor.py

from ..models import db, Transaction, TransactionStatus
from ..utils.bitcoin import send_bitcoin, get_transaction_status
from flask import current_app
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.orm.attributes import flag_modified # For explicit change tracking of JSON fields

def process_pending_approvals():
    """
    Processes withdrawal transactions that are in PENDING_APPROVAL status.
    Attempts to initiate a Bitcoin transfer for each.
    """
    logger = current_app.logger
    logger.info("Starting processing of pending withdrawal approvals...")

    transactions_to_process = Transaction.query.filter_by(
        transaction_type='withdraw',
        status=TransactionStatus.PENDING_APPROVAL
    ).all()

    if not transactions_to_process:
        logger.info("No withdrawal approvals pending processing.")
        return

    for tx in transactions_to_process:
        logger.info(f"Processing withdrawal TX ID: {tx.id} for user {tx.user_id}")

        if tx.details is None:
            tx.details = {}
            flag_modified(tx, "details")


        recipient_address = tx.details.get('withdraw_address')
        amount_sats = tx.amount # This is an Integer/BigInteger in satoshis

        if not recipient_address:
            logger.error(f"Missing recipient_address for TX ID: {tx.id}. Marking as FAILED.")
            tx.status = TransactionStatus.FAILED
            tx.details['error'] = "Missing withdrawal address for processing."
            tx.details['failed_at'] = datetime.now(timezone.utc).isoformat()
            flag_modified(tx, "details")
            db.session.add(tx)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"Failed to commit FAILED status for TX ID: {tx.id} due to missing address. Error: {str(e)}")
            continue

        try:
            amount_btc = Decimal(amount_sats) / Decimal('100000000')
            logger.info(f"Attempting to send {amount_btc:.8f} BTC to {recipient_address} for TX ID: {tx.id}")

            # This will call the MOCKED send_bitcoin function from utils.bitcoin
            bitcoin_txid = send_bitcoin(recipient_address, amount_btc)

            tx.status = TransactionStatus.IN_PROGRESS
            tx.details['bitcoin_txid'] = bitcoin_txid
            tx.details['processing_initiated_at'] = datetime.now(timezone.utc).isoformat()
            tx.details.pop('error', None) # Remove previous error if any
            flag_modified(tx, "details")

            logger.info(f"Successfully initiated BTC transfer for TX ID: {tx.id}. Bitcoin TXID (mocked): {bitcoin_txid}")

        except Exception as e:
            logger.error(f"BTC transfer initiation failed for TX ID: {tx.id}. Error: {str(e)}")
            tx.status = TransactionStatus.FAILED
            tx.details['error'] = f"BTC transfer initiation failed: {str(e)}"
            tx.details['failed_at'] = datetime.now(timezone.utc).isoformat()
            flag_modified(tx, "details")

        db.session.add(tx)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to commit changes for TX ID: {tx.id} during processing. Error: {str(e)}")

    logger.info("Finished processing pending withdrawal approvals.")


def check_in_progress_withdrawals():
    """
    Checks the status of withdrawal transactions that are IN_PROGRESS.
    Queries the (mocked) Bitcoin utility to update their status.
    """
    logger = current_app.logger
    logger.info("Starting check of in-progress withdrawals...")

    transactions_to_check = Transaction.query.filter_by(
        transaction_type='withdraw',
        status=TransactionStatus.IN_PROGRESS
    ).all()

    if not transactions_to_check:
        logger.info("No in-progress withdrawals to check.")
        return

    for tx in transactions_to_check:
        logger.info(f"Checking status for withdrawal TX ID: {tx.id} for user {tx.user_id}")

        if tx.details is None: # Should not happen if processed by process_pending_approvals
            tx.details = {}
            flag_modified(tx, "details")

        bitcoin_txid = tx.details.get('bitcoin_txid')

        if not bitcoin_txid:
            logger.error(f"Internal Error: Missing bitcoin_txid for IN_PROGRESS TX ID: {tx.id}. Marking as FAILED.")
            tx.status = TransactionStatus.FAILED
            tx.details['error'] = "Internal error: Missing bitcoin_txid for an IN_PROGRESS withdrawal."
            tx.details['failed_at'] = datetime.now(timezone.utc).isoformat()
            flag_modified(tx, "details")
            db.session.add(tx)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"Failed to commit FAILED status for TX ID: {tx.id} due to missing bitcoin_txid. Error: {str(e)}")
            continue

        try:
            # This will call the MOCKED get_transaction_status from utils.bitcoin
            status_response = get_transaction_status(bitcoin_txid)

            confirmations = status_response.get('confirmations', 0)
            btc_status = status_response.get('status') # e.g., 'pending', 'confirmed', 'not_found', 'not_found_in_session'

            tx.details['last_btc_check_confirmations'] = confirmations
            tx.details['last_btc_check_status'] = btc_status
            tx.details['last_btc_check_at'] = datetime.now(timezone.utc).isoformat()
            flag_modified(tx, "details")


            if btc_status == 'confirmed': # Mocked bitcoin.py returns 'confirmed' when confirmations >= 6 (simulated)
                tx.status = TransactionStatus.COMPLETED
                tx.details['completed_at'] = datetime.now(timezone.utc).isoformat()
                tx.details.pop('error', None) # Remove previous error if any
                flag_modified(tx, "details")
                logger.info(f"Withdrawal TX ID: {tx.id} (Bitcoin TXID: {bitcoin_txid}) confirmed with {confirmations} confirmations and marked as COMPLETED.")

            elif btc_status == 'not_found' or btc_status == 'not_found_in_session':
                # This could mean the txid is genuinely wrong, or our mock bitcoin util was restarted and lost the dummy_txid.
                # For a real system, 'not_found' after a certain period might indicate failure or an issue.
                # For this mock, if it was "sent" more than, say, 1 hour ago and still not_found, mark as FAILED.
                time_initiated_str = tx.details.get('processing_initiated_at')
                grace_period_expired = False
                if time_initiated_str:
                    time_initiated = datetime.fromisoformat(time_initiated_str)
                    if (datetime.now(timezone.utc) - time_initiated).total_seconds() > 3600: # 1 hour
                        grace_period_expired = True

                if grace_period_expired:
                    logger.error(f"Withdrawal TX ID: {tx.id} (Bitcoin TXID: {bitcoin_txid}) FAILED. Bitcoin transaction status: {btc_status} after grace period.")
                    tx.status = TransactionStatus.FAILED
                    tx.details['error'] = f"Bitcoin transaction {bitcoin_txid} status: {btc_status} after 1hr grace period."
                    tx.details['failed_at'] = datetime.now(timezone.utc).isoformat()
                    flag_modified(tx, "details")
                else:
                    logger.warning(f"Withdrawal TX ID: {tx.id} (Bitcoin TXID: {bitcoin_txid}) returned status {btc_status}. Will re-check. Confirmations: {confirmations}.")

            elif btc_status == 'pending':
                 logger.info(f"Withdrawal TX ID: {tx.id} (Bitcoin TXID: {bitcoin_txid}) still pending with {confirmations} confirmations.")

            else: # Any other status from get_transaction_status that isn't 'confirmed' or 'pending'
                logger.warning(f"Withdrawal TX ID: {tx.id} (Bitcoin TXID: {bitcoin_txid}) has an unexpected status: {btc_status} with {confirmations} confirmations. Will re-check.")


        except Exception as e:
            logger.error(f"Error checking Bitcoin transaction status for {bitcoin_txid} (Withdrawal TX ID: {tx.id}). Error: {str(e)}")
            # Not changing status here, to allow retry on next scheduled run.
            # If this error persists, manual intervention might be needed.
            tx.details['error_checking_status'] = str(e) # Log the error to details
            flag_modified(tx, "details")

        db.session.add(tx)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to commit changes for TX ID: {tx.id} during status check. Error: {str(e)}")

    logger.info("Finished checking in-progress withdrawals.")
