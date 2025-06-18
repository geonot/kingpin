# Bitcoin Deposit Processing

This directory contains services related to Bitcoin operations.

- `bitcoin_monitor.py` (BitcoinMonitor): This is the primary service responsible for actively monitoring user deposit addresses, detecting new Bitcoin transactions on the blockchain, and updating user balances accordingly. It directly interacts with the database to record deposits.

- `bitcoin_poller.py` (BitcoinPoller): This service was previously used for deposit detection. It is currently **DEACTIVATED** for this purpose to avoid conflicts and potential double-processing of deposits now handled by `BitcoinMonitor`. It may be used for other auxiliary tasks in the future or serve as a reference.

For Bitcoin deposit detection and processing, `BitcoinMonitor` is the active component.
