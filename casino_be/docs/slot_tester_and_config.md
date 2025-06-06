# Slot Tester and Enhanced gameConfig.json Documentation

This document provides information on how to use the Slot Tester utility and details the enhancements made to the `gameConfig.json` file format, specifically for `reel_strips` and `cluster_payouts`.

## Slot Tester (`casino_be/utils/slot_tester.py`)

The Slot Tester is a command-line tool designed to simulate extensive slot machine play to analyze Return to Player (RTP), hit frequency, bonus metrics, and other statistical aspects of a slot game.

### How to Run the Tester

The tester is run from the command line. Ensure you are in the root directory of the repository.

```bash
python -m casino_be.utils.slot_tester <slot_short_name> [options]
```

**Arguments:**

*   `<slot_short_name>` (required): The short name of the slot game to test. This must correspond to a directory name in `casino_fe/public/` that contains the slot's `gameConfig.json`.
*   `--num_spins` (optional): The total number of spins to simulate. Default: 10,000.
    *   Example: `--num_spins 1000000`
*   `--bet_amount` (optional): The bet amount in satoshis for each paid spin. Default: 100.
    *   Example: `--bet_amount 50`

**Example Usage:**

```bash
python -m casino_be.utils.slot_tester ancient_pyramids --num_spins 50000 --bet_amount 100
```

### Output

The Slot Tester produces two main forms of output:

1.  **Console Output:**
    *   Progress messages during the simulation.
    *   A detailed summary of calculated statistics after the simulation completes. This includes:
        *   Overall RTP (compared against the target RTP from config if available).
        *   Hit Frequency.
        *   Bonus Trigger Frequency.
        *   Average Bonus Win and total spins in bonus.
        *   RTP contributions from the base game and bonus features.
        *   Volatility Index (if NumPy is installed).
        *   Distribution of wins by bet multiplier.
        *   RTP convergence data points.

2.  **Graphs:**
    *   Graphical representations of key statistics are saved as PNG files in a directory named `slot_tester_graphs/` (created in the directory where the script is run). Graphs include:
        *   Win Multiplier Distribution.
        *   RTP Convergence Over Time.
        *   Win Contribution (Base vs. Bonus).
        *   Bonus Round Win Distribution.
    *   Graph generation requires Matplotlib to be installed.

### How it Works

The tester simulates spins by using the core slot logic found in `spin_handler.py` but adapted to run without database interactions. It uses mock objects for `User` and `GameSession` to track state like balance and bonus features. All game parameters (paylines, payouts, reel behavior, bonus rules, etc.) are loaded from the specified slot's `gameConfig.json`.

---

## Enhanced `gameConfig.json` Structure

To support more realistic and mathematically rigorous simulations, the following fields have been standardized for use in `gameConfig.json` files:

### 1. `reel_strips`

*   **Purpose:** Defines the actual sequence of symbols on each reel. This is crucial for accurate RTP and odds calculation, as it determines the true probability of each symbol landing on a payline.
*   **Structure:** An array of arrays, where each inner array represents a reel strip for a column.
*   **Location:** Inside the main `game` object in `gameConfig.json`.
*   **Example:**
    ```json
    "game": {
        // ... other game properties ...
        "layout": {"rows": 3, "columns": 5},
        "reel_strips": [
            // Reel 1 (column 0)
            [1, 2, 1, 8, 3, 1, 4, 5, 1, 2, 1, 9, 6, 1, 7, 10, 11, 1, 2, 1, 3, 4, 5, 1, 2],
            // Reel 2 (column 1)
            [1, 3, 2, 1, 8, 4, 1, 5, 6, 2, 1, 9, 7, 1, 10, 11, 1, 3, 2, 1, 4, 5, 6, 1, 3],
            // Reel 3 (column 2) - and so on for all columns
            [...],
            [...],
            [...]
        ],
        // ... other game properties ...
    }
    ```
*   **Details:**
    *   The number of inner arrays must match `game.layout.columns`.
    *   Each symbol ID in the strips must correspond to an ID defined in the `game.symbols` array.
    *   The length of each reel strip can vary. Longer strips allow for more precise control over symbol frequencies.
    *   If `reel_strips` is missing or invalid, `spin_handler.py` (and thus the tester) will fall back to a less accurate method of random symbol generation with basic weighting.

### 2. `min_symbols_to_match` (for Cluster/Match-N Pays)

*   **Purpose:** Enables "Match-N" or "Cluster Pays" win mechanics, where wins are awarded for a minimum number of identical symbols appearing anywhere on the grid (or in connected clusters, though current implementation is for "anywhere on grid").
*   **Structure:** An integer.
*   **Location:** Inside the main `game` object in `gameConfig.json`.
*   **Example:**
    ```json
    "game": {
        // ... other game properties ...
        "min_symbols_to_match": 5, // Minimum 5 identical symbols anywhere for a cluster win
        // ... other game properties ...
    }
    ```
*   **Dependencies:** When `min_symbols_to_match` is used, payout information for these types of wins must be defined within each symbol's configuration in the `symbols` array using the `cluster_payouts` field.

### 3. `cluster_payouts` (within each symbol definition)

*   **Purpose:** Defines the payout multipliers for "Match-N" or "Cluster Pays" wins for a specific symbol when `min_symbols_to_match` is active.
*   **Structure:** An object where keys are strings representing the count of matched symbols, and values are the payout multipliers (applied to total bet).
*   **Location:** Inside each symbol object within the `game.symbols` array.
*   **Example:**
    ```json
    "game": {
        // ... other game properties ...
        "min_symbols_to_match": 5,
        "symbols": [
            {
                "id": 1,
                "name": "LowSymbol",
                "value": null, // Payline value might be null if only cluster pays
                // ... other symbol properties ...
                "cluster_payouts": {
                    "5": 0.5,  // 5 LowSymbols pay 0.5x total bet
                    "6": 1.0,  // 6 LowSymbols pay 1.0x total bet
                    "7": 2.5   // 7 LowSymbols pay 2.5x total bet
                }
            },
            // ... other symbols ...
        ],
        // ...
    }
    ```
*   **Details:**
    *   If `min_symbols_to_match` is set, but a symbol does not have a `cluster_payouts` entry (or an entry for a specific count), it will not award cluster wins for that symbol/count.
    *   The `spin_handler.py` uses these multipliers against the `total_bet_sats` for calculating cluster win amounts.

These enhancements to `gameConfig.json` allow for more diverse and accurately simulated slot machine mechanics.
