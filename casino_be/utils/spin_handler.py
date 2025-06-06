import random
import json
import os
import secrets
from datetime import datetime, timezone
from casino_be.models import db, SlotSpin, GameSession, User, Transaction, UserBonus # Added UserBonus
# SlotSymbol might not be directly used if all config comes from JSON, but keep for now

# --- Configuration ---
# Constants like MIN_MATCH_FOR_PAYLINE_WIN will likely come from gameConfig.json or be implicitly handled by payout tables.
# MIN_MATCH_FOR_SCATTER_WIN also likely from config.
# SCATTER_PAY_MULTIPLIER_BASE will be replaced by config.


# Base path for slot configurations
SLOT_CONFIG_BASE_PATH = "public/slots" # Adjust if your structure is different, e.g., "casino_be/static/slots"

def load_game_config(slot_short_name):
    """Loads the game configuration JSON file for a given slot."""
    # Construct path like "public/slots/slot1/gameConfig.json"
    config_path = os.path.join(SLOT_CONFIG_BASE_PATH, slot_short_name, "gameConfig.json")
    if not os.path.exists(config_path):
        # Fallback: try checking if slot_short_name is a direct path or stored in slot.asset_directory
        # This part depends on how slot.asset_directory is structured.
        # For now, assume slot_short_name is the directory name under SLOT_CONFIG_BASE_PATH
        raise FileNotFoundError(f"Game configuration not found for slot '{slot_short_name}' at {config_path}")

    with open(config_path, 'r') as f:
        config = json.load(f)
    return config

def handle_spin(user, slot, game_session, bet_amount_sats):
    """
    Handles the logic for a single slot machine spin.

    Args:
        user (User): The user performing the spin.
        slot (Slot): The slot machine being played.
        game_session (GameSession): The current active game session.
        bet_amount_sats (int): The amount bet in Satoshis.

    Returns:
        dict: A dictionary containing the results of the spin, structured as follows:
            {
                "spin_result": list[list[int]],  # The grid of symbol IDs resulting from the spin.
                "win_amount_sats": int,          # Total win amount in satoshis from this spin.
                "winning_lines": list[dict],     # List of winning paylines and scatter wins. Each dict contains:
                                                 #   "line_id": str (e.g., "payline_1", "scatter"),
                                                 #   "symbol_id": int (winning symbol ID),
                                                 #   "count": int (number of matching symbols),
                                                 #   "positions": list[list[int]] (coordinates of winning symbols),
                                                 #   "win_amount_sats": int (win for this specific line/scatter)
                "bonus_triggered": bool,         # True if a bonus feature was triggered on this spin.
                "bonus_active": bool,            # True if a bonus (e.g., free spins) is currently active.
                "bonus_spins_remaining": int,    # Number of free spins remaining if bonus_active.
                "bonus_multiplier": float,       # Multiplier for wins during bonus spins if bonus_active.
                "user_balance_sats": int,        # The user's balance after the spin.
                "session_stats": dict            # Statistics for the current game session:
                                                 #   "num_spins": int,
                                                 #   "amount_wagered_sats": int,
                                                 #   "amount_won_sats": int
            }

    Side Effects:
        - Modifies the `user` object's balance.
        - Modifies the `game_session` object (e.g., `num_spins`, `amount_wagered`, `amount_won`, bonus states).
        - Creates `SlotSpin` record in the database for the current spin.
        - Creates `Transaction` records for wagers and wins.
        - Updates `UserBonus` wagering progress if an active bonus exists and the spin is a paid spin.
        - All database changes are added to the current `db.session` but NOT committed by this function.
          The caller is responsible for committing the session.

    Raises:
        FileNotFoundError: If the `gameConfig.json` for the slot is not found.
        ValueError: If the bet amount is invalid, user has insufficient balance for a paid spin,
                    or if there's a critical configuration error (e.g., no spinable symbols).
        RuntimeError: For other unexpected errors during spin processing.
    """
    try:
        # --- Load Game Configuration ---
        game_config = load_game_config(slot.short_name)

        # Extract key configurations
        cfg_layout = game_config.get('game', {}).get('layout', {})
        cfg_symbols_map = {s['id']: s for s in game_config.get('game', {}).get('symbols', [])}
        cfg_paylines = cfg_layout.get('paylines', [])
        cfg_rows = cfg_layout.get('rows', 3)
        cfg_columns = cfg_layout.get('columns', 5)
        cfg_wild_symbol_id = game_config.get('game', {}).get('wild_symbol_id')
        cfg_scatter_symbol_id = game_config.get('game', {}).get('scatter_symbol_id')
        cfg_bonus_features = game_config.get('game', {}).get('bonus_features', {})
        # New cascading configurations
        cfg_is_cascading = game_config.get('game', {}).get('is_cascading', False)
        cfg_cascade_type = game_config.get('game', {}).get('cascade_type', None) # e.g., "fall_from_top"
        cfg_min_symbols_to_match = game_config.get('game', {}).get('min_symbols_to_match', None) # For cluster/match-N
        cfg_win_multipliers = game_config.get('game', {}).get('win_multipliers', []) # For cascading wins e.g., [1,2,3,5]

        # --- Pre-Spin Validation ---
        if not isinstance(bet_amount_sats, int) or bet_amount_sats <= 0:
            raise ValueError("Invalid bet amount. Must be a positive integer (satoshis).")

        if user.balance < bet_amount_sats and not (game_session.bonus_active and game_session.bonus_spins_remaining > 0) :
            raise ValueError("Insufficient balance for this bet.")

        # --- Update Wagering Progress if Active Bonus (for PAID spins) ---
        actual_bet_this_spin_for_wagering = 0
        if not (game_session.bonus_active and game_session.bonus_spins_remaining > 0): # i.e., if this is a paid spin
            actual_bet_this_spin_for_wagering = bet_amount_sats

        if actual_bet_this_spin_for_wagering > 0:
            active_bonus = UserBonus.query.filter_by(
                user_id=user.id,
                is_active=True,
                is_completed=False,
                is_cancelled=False
            ).first()

            if active_bonus:
                active_bonus.wagering_progress_sats += actual_bet_this_spin_for_wagering
                active_bonus.updated_at = datetime.now(timezone.utc)

                if active_bonus.wagering_progress_sats >= active_bonus.wagering_requirement_sats:
                    active_bonus.is_active = False
                    active_bonus.is_completed = True
                    active_bonus.completed_at = datetime.now(timezone.utc)
                    # print(f"User {user.id} completed wagering for UserBonus {active_bonus.id}.") # Logging handled by caller or removed for now

        # --- Determine Spin Type and Deduct Bet ---
        is_bonus_spin = False
        current_spin_multiplier = 1.0 # Multiplier for the current spin's winnings

        if game_session.bonus_active and game_session.bonus_spins_remaining > 0:
            is_bonus_spin = True
            current_spin_multiplier = game_session.bonus_multiplier # Use session's bonus multiplier
            game_session.bonus_spins_remaining -= 1
            # Bet is not deducted during a bonus spin
            actual_bet_this_spin = 0
        else:
            user.balance -= bet_amount_sats
            actual_bet_this_spin = bet_amount_sats
            # Create Wager Transaction
            wager_tx = Transaction(
                user_id=user.id,
                amount=-bet_amount_sats, # Negative for wager
                transaction_type='wager', # Ensure this matches model's transaction_type column name
                details={'slot_name': slot.name, 'session_id': game_session.id}, # Using details field
                # description=f'Slot wager: {slot.name}', # Old description field
                    # game_session_id removed
            )
            db.session.add(wager_tx)
            # game_session.transactions.append(wager_tx) # Add to session if relationship is set up

        # --- Generate Spin Result ---
        # slot.symbols still provides the available symbols from DB.
        # We'll use cfg_symbols_map for properties like multipliers, is_wild, is_scatter
        # The generate_spin_grid function might need to be aware of symbol IDs from config
        cfg_reel_strips = game_config.get('game', {}).get('reel_strips') # Get reel_strips

        spin_result_grid = generate_spin_grid(
            cfg_rows,
            cfg_columns,
            slot.symbols, # List of SlotSymbol ORM objects
            cfg_wild_symbol_id, # Ensure this is cfg_wild_symbol_id from game_config.get('game',{}).get('symbol_wild')
            cfg_scatter_symbol_id, # Ensure this is cfg_scatter_symbol_id from game_config.get('game',{}).get('symbol_scatter')
            cfg_symbols_map, # Pass the config symbols map for weighting or other properties
            cfg_reel_strips # Pass the loaded reel_strips
        )

        # --- Calculate Wins ---
        # calculate_win will now use cfg_paylines and cfg_symbols_map
        win_info = calculate_win(
            spin_result_grid,
            cfg_paylines,
            cfg_symbols_map, # Use the symbol data from config
            bet_amount_sats, # This is the total bet for the spin
            cfg_wild_symbol_id,
            cfg_scatter_symbol_id,
            # game_config.get('game', {}).get('payouts', []), # This general payouts list is no longer passed directly
            cfg_min_symbols_to_match # Pass this to calculate_win for cluster/match-N logic
            # current_spin_multiplier is handled outside calculate_win now
        )

        # Initial win calculation results
        initial_raw_win_sats = win_info['total_win_sats']
        winning_lines = win_info['winning_lines'] # From initial spin
        current_winning_coords = win_info['winning_symbol_coords'] # Coords from initial spin

        # Store initial grid for SlotSpin record
        initial_spin_grid_for_record = [row[:] for row in spin_result_grid] # Deep copy

        # Initialize total win & state for potential cascades
        total_win_for_entire_spin_sequence_raw = initial_raw_win_sats # Accumulates RAW wins (base + cascades without cascade multipliers)
                                                                # This will then be multiplied by bonus_spin_multiplier if applicable.
                                                                # OR, this accumulates wins *with* cascade multipliers, then gets *bonus_spin_multiplier*.
                                                                # Let's use: sum of (raw_win * cascade_level_multiplier)

        # Let total_win_for_entire_spin_sequence represent the sum of:
        # (initial_raw_win) + (cascade1_raw_win * mult1) + (cascade2_raw_win * mult2) ...
        total_win_for_entire_spin_sequence = initial_raw_win_sats # Initial win has effective cascade multiplier of 1 or none.

        current_grid_state = spin_result_grid # This grid will be modified in cascades
        current_raw_win_for_cascade_loop = initial_raw_win_sats # Controls cascade loop continuation based on raw win of previous step

        max_cascade_multiplier_level_achieved = 0 # For SlotSpin.current_multiplier_level (tracks highest cfg_win_multipliers index used +1)
                                             # Or simply the highest multiplier value achieved. Let's use the level for now.

        # --- Cascading Wins Logic ---
        if cfg_is_cascading and initial_raw_win_sats > 0 and current_winning_coords:
            cascade_level_counter = 0 # 0 means initial win, 1st cascade is level 1, etc.

            while current_raw_win_for_cascade_loop > 0 and current_winning_coords:
                # 1. Grid Update: Remove winning symbols, fill new ones
                current_grid_state = handle_cascade_fill(
                    current_grid_state,
                    current_winning_coords, # Coords from the previous win calculation
                    cfg_cascade_type,
                    slot.symbols, # db_symbols
                    cfg_symbols_map,
                    cfg_wild_symbol_id,
                    cfg_scatter_symbol_id
                )

                # 2. Recalculate Wins on the new grid
                cascade_win_info = calculate_win(
                    current_grid_state, # The newly formed grid
                    cfg_paylines,
                    cfg_symbols_map,
                    bet_amount_sats, # Base bet amount for calculating wins
                    cfg_wild_symbol_id,
                    cfg_scatter_symbol_id,
                    # game_config.get('game', {}).get('payouts', []), # This general payouts list is no longer passed directly
                    cfg_min_symbols_to_match
                )

                new_raw_win_this_cascade = cascade_win_info['total_win_sats']
                current_winning_coords = cascade_win_info['winning_symbol_coords'] # For the next iteration's fill

                if new_raw_win_this_cascade > 0:
                    cascade_level_counter += 1 # This is the 1st, 2nd, etc. cascade event

                    current_cascade_multiplier = 1.0
                    if cfg_win_multipliers: # Check if win_multipliers are defined and non-empty
                        if cascade_level_counter -1 < len(cfg_win_multipliers): # cfg_win_multipliers is 0-indexed
                            current_cascade_multiplier = cfg_win_multipliers[cascade_level_counter -1]
                        elif cfg_win_multipliers: # Not empty, so use last available
                            current_cascade_multiplier = cfg_win_multipliers[-1]

                    if cascade_level_counter > max_cascade_multiplier_level_achieved: # Using counter as level proxy
                        max_cascade_multiplier_level_achieved = cascade_level_counter

                    # Add the (raw_win_from_this_cascade * its_cascade_multiplier) to the grand total
                    total_win_for_entire_spin_sequence += int(new_raw_win_this_cascade * current_cascade_multiplier)

                    current_raw_win_for_cascade_loop = new_raw_win_this_cascade # Keep loop going if there was a raw win

                    # Accumulate winning_lines (optional, can make response large)
                    # winning_lines.extend(cascade_win_info['winning_lines']) # Example if needed
                else:
                    current_raw_win_for_cascade_loop = 0 # No new raw win, so stop cascading
                    current_winning_coords = [] # Clear coords
            # End of cascade loop

        # Now, total_win_for_entire_spin_sequence holds sum of (initial_raw + C1_raw*M1 + C2_raw*M2 ...)
        # Apply overall bonus spin multiplier if applicable (e.g., from free spins feature)
        final_win_amount_for_session_and_tx = total_win_for_entire_spin_sequence
        if is_bonus_spin and current_spin_multiplier > 1.0:
            final_win_amount_for_session_and_tx = int(total_win_for_entire_spin_sequence * current_spin_multiplier)
            # Note: if winning_lines are accumulated, their individual win_amount_sats would also need scaling
            # if a detailed breakdown of multiplied lines is required. Currently, `winning_lines` primarily reflects initial spin.

        # --- Check for Bonus Trigger (on non-bonus spins) ---
        # Bonus trigger check should be based on the *initial* spin grid results.
        bonus_triggered_this_spin = False
        newly_awarded_spins = 0
        new_bonus_multiplier = 1.0

        if not is_bonus_spin: # Bonus can only be triggered on a normal spin
            bonus_trigger_info = check_bonus_trigger(
                initial_spin_grid_for_record, # Check on the initial grid
                cfg_scatter_symbol_id,
                cfg_bonus_features
            )
            if bonus_trigger_info['triggered']:
                bonus_triggered_this_spin = True
                newly_awarded_spins = bonus_trigger_info.get('spins_awarded', 0)
                new_bonus_multiplier = bonus_trigger_info.get('multiplier', 1.0)


        # --- Update Session State for Bonus ---
        if bonus_triggered_this_spin:
            if not game_session.bonus_active: # Starting a new bonus
                game_session.bonus_active = True
                game_session.bonus_spins_remaining = newly_awarded_spins
                game_session.bonus_multiplier = new_bonus_multiplier
            else: # Re-trigger or additional spins during an active bonus
                game_session.bonus_spins_remaining += newly_awarded_spins
                # Optionally, decide if multiplier updates or accumulates, based on game rules
                # For now, assume it takes the new multiplier if retriggered, or keeps existing if just adding spins.
                if new_bonus_multiplier != game_session.bonus_multiplier and newly_awarded_spins > 0 :
                     game_session.bonus_multiplier = new_bonus_multiplier # Or max(game_session.bonus_multiplier, new_bonus_multiplier)

        elif game_session.bonus_active and game_session.bonus_spins_remaining <= 0:
            # Bonus ended
            game_session.bonus_active = False
            game_session.bonus_multiplier = 1.0 # Reset multiplier


        # --- Update Session Aggregates ---
        game_session.num_spins += 1
        if not is_bonus_spin:
            game_session.amount_wagered = (game_session.amount_wagered or 0) + actual_bet_this_spin
        # `game_session.amount_won` is updated with the final win amount from this spin.
        # The previous logic added `win_amount_sats` (which was initial win pre-bonus mult).
        # We need to correct this if it was already added, or ensure it's added correctly once.
        # Assuming it was added: subtract old, add new.
        # If it wasn't added yet by this point, just add new.
        # The line `game_session.amount_won = (game_session.amount_won or 0) + win_amount_sats` was there.
        # So, we subtract that `win_amount_sats` (which is `initial_raw_win_sats` potentially multiplied by bonus_multiplier)
        # and add `final_win_amount_for_session_and_tx`.

        # Correction: The `win_amount_sats` that was added to `game_session.amount_won`
        # was the one *after* `if is_bonus_spin and current_spin_multiplier > 1.0:` block.
        # This means it was `initial_raw_win_sats * current_spin_multiplier` if bonus, else `initial_raw_win_sats`.
        # Let's denote this value as `previously_added_win_to_session`.
        previously_added_win_to_session = initial_raw_win_sats
        if is_bonus_spin and current_spin_multiplier > 1.0: # This replicates the original multiplication
             previously_added_win_to_session = int(initial_raw_win_sats * current_spin_multiplier)

        game_session.amount_won = (game_session.amount_won or 0) - previously_added_win_to_session + final_win_amount_for_session_and_tx


        # --- Update User Balance & Win Transaction ---
        if final_win_amount_for_session_and_tx > 0:
            user.balance += final_win_amount_for_session_and_tx # Add final total win to user balance
            win_tx = Transaction(
                user_id=user.id,
                amount=final_win_amount_for_session_and_tx,
                transaction_type='win',
                details={
                    'slot_name': slot.name,
                    'session_id': game_session.id,
                    'is_cascade_win': cfg_is_cascading and max_cascade_multiplier_level_achieved > 0,
                    'initial_win': initial_raw_win_sats,
                    'total_cascade_win_multiplied': total_win_for_entire_spin_sequence - initial_raw_win_sats,
                    'bonus_spin_multiplier_applied': current_spin_multiplier if is_bonus_spin else 1.0
                    }
                    # game_session_id removed
            )
            db.session.add(win_tx)
            # game_session.transactions.append(win_tx) # If using relationship for this

        # --- Create Spin Record ---
        new_spin = SlotSpin(
            game_session_id=game_session.id,
            spin_result=initial_spin_grid_for_record, # Record the initial grid
            win_amount=final_win_amount_for_session_and_tx, # Total win from initial + all cascades (with all multipliers)
            bet_amount=actual_bet_this_spin,
            is_bonus_spin=is_bonus_spin,
            spin_time=datetime.now(timezone.utc),
            current_multiplier_level=max_cascade_multiplier_level_achieved # Store max cascade level reached
        )
        db.session.add(new_spin)
        # Crucially, flush here to get new_spin.id before assigning to transactions
        db.session.flush()

        # Link transactions to this spin
        if not is_bonus_spin and 'wager_tx' in locals() and wager_tx: # Ensure wager_tx exists
            wager_tx.slot_spin_id = new_spin.id
            wager_tx.details['slot_spin_id'] = new_spin.id
        if final_win_amount_for_session_and_tx > 0 and 'win_tx' in locals() and win_tx: # Ensure win_tx exists
            win_tx.slot_spin_id = new_spin.id
            win_tx.details['slot_spin_id'] = new_spin.id

        # --- Return Results ---
        # Ensure all satoshi amounts are integers
        return {
            "spin_result": initial_spin_grid_for_record, # Return the initial grid state
            "win_amount_sats": int(final_win_amount_for_session_and_tx),
            "winning_lines": winning_lines, # This currently holds results from the *initial* spin.
                                            # For a full breakdown, this would need to be an accumulation if cascades add more lines.
            "bonus_triggered": bonus_triggered_this_spin,
            "bonus_active": game_session.bonus_active,
            "bonus_spins_remaining": game_session.bonus_spins_remaining if game_session.bonus_active else 0,
            "bonus_multiplier": game_session.bonus_multiplier if game_session.bonus_active else 1.0,
            "user_balance_sats": int(user.balance),
            "session_stats": { # Consistent with other game types potentially
                "num_spins": game_session.num_spins,
                "amount_wagered_sats": int(game_session.amount_wagered or 0),
                "amount_won_sats": int(game_session.amount_won or 0),
            }
        }
    except FileNotFoundError as e:
        # Log error appropriately
        # raise ValueError(f"Game configuration error: {e}") # Or handle more gracefully
        # For now, re-raise as ValueError for the route to catch
        # In a real app, you might want a more specific exception type.
        db.session.rollback() # Rollback any DB changes if config fails
        raise ValueError(str(e))
    except ValueError as e: # Catch specific errors like insufficient balance
        db.session.rollback()
        raise e # Re-raise it for the route to handle
    except Exception as e:
        db.session.rollback()
        # Log the exception e
        # Consider what to return or raise. A generic error for the user.
        raise RuntimeError(f"An unexpected error occurred during the spin: {str(e)}") # Use str(e) for cleaner message


def generate_spin_grid(rows, columns, db_symbols, wild_symbol_config_id, scatter_symbol_config_id, config_symbols_map, reel_strips=None):
    if not db_symbols:
        # This indicates a setup issue.
        # Fallback to a simple grid if no symbols are defined for the slot in DB.
        s_ids = list(config_symbols_map.keys())
        return [[s_ids[0] if s_ids else 1 for _ in range(columns)] for _ in range(rows)]

    valid_symbol_ids_for_slot = [s.symbol_internal_id for s in db_symbols]
    spinable_symbol_ids = [sid for sid in valid_symbol_ids_for_slot if sid in config_symbols_map]

    if not spinable_symbol_ids:
        raise ValueError("No spinable symbols found. Check slot DB symbol configuration against gameConfig.json.")

    # --- Weighting ---
    # Weights are retrieved from each symbol's 'weight' property in gameConfig.json.
    weights = []
    symbols_for_choice = []

    for s_id in spinable_symbol_ids:
        symbol_config = config_symbols_map.get(s_id)
        if symbol_config:
            raw_weight = symbol_config.get('weight')
            current_weight = 1.0  # Default weight
            if isinstance(raw_weight, (int, float)) and raw_weight > 0:
                current_weight = float(raw_weight)
            else:
                # Log a warning here in a real application if weight is missing or invalid for a symbol
                # print(f"Warning: Symbol ID {s_id} has missing or invalid weight '{raw_weight}'. Defaulting to 1.0.")
                pass # Using default weight 1.0

            weights.append(current_weight)
            symbols_for_choice.append(s_id)
        else:
            # This case should ideally not be reached if spinable_symbol_ids are derived correctly from config_symbols_map keys
            # Log a warning: Symbol ID {s_id} not found in config_symbols_map, skipping for weighted choice.
            pass


    total_weight = sum(weights)
    if total_weight == 0 or not symbols_for_choice: # Prevent division by zero or empty choices
         if not symbols_for_choice: # if symbols_for_choice is empty, fall back to spinable_symbol_ids with uniform weight
             if not spinable_symbol_ids: # Should have been caught earlier
                  raise ValueError("Cannot generate spin grid: No symbols available for choice and no spinable_symbol_ids.")
             symbols_for_choice = spinable_symbol_ids
             weights = [1.0] * len(symbols_for_choice)
             total_weight = float(len(symbols_for_choice))
         else: # weights were all zero, distribute uniformly
             weights = [1.0 / len(symbols_for_choice) for _ in symbols_for_choice]
    else:
        if reel_strips is not None: # It was provided but invalid
             print("Warning: reel_strips configuration is invalid, does not match column count, or contains non-integer symbol IDs. Falling back to basic weighted random symbol generation.")
        else:
             print("Warning: reel_strips not found in gameConfig. Falling back to basic weighted random symbol generation.")

        # Fallback to existing (or improved basic weighted) logic
        weights = []
        symbols_for_choice = []

        for s_id in spinable_symbol_ids:
            symbol_config = config_symbols_map.get(s_id)
            if symbol_config: # Should always be true if s_id is from spinable_symbol_ids
                # Example: use a 'spawn_weight' or 'reel_weight' from config if available
                # For now, assume equal weight for simplicity, but favor non-special symbols slightly more.
                is_wild = symbol_config.get('is_wild', False) or s_id == wild_symbol_config_id
                is_scatter = symbol_config.get('is_scatter', False) or s_id == scatter_symbol_config_id

                # Default weights if not specified in symbol_config (as 'weight' key)
                default_weight = 1.0
                if is_wild: default_weight = 0.5
                elif is_scatter: default_weight = 0.4

                weights.append(symbol_config.get('weight', default_weight))
                symbols_for_choice.append(s_id)

        if not symbols_for_choice: # Should be caught by spinable_symbol_ids check earlier
             raise ValueError("Cannot generate spin grid: No symbols available for choice in fallback.")

        total_weight = sum(weights)
        if total_weight == 0 : # Prevent division by zero if all weights are zero
            # Fallback to uniform distribution if all weights are zero
            weights = [1.0 / len(symbols_for_choice)] * len(symbols_for_choice)
        else:
            weights = [w / total_weight for w in weights]

        for r_idx in range(rows):
            row_symbols = secure_random.choices(symbols_for_choice, weights=weights, k=columns)
            grid[r_idx] = row_symbols # Assign directly to the row
        return grid


# Removed define_paylines - it will come from game_config.layout.paylines

def get_symbol_payout(symbol_id, count, config_symbols_map, is_scatter=False):
    """
    Determines the payout multiplier based on the symbol and count.
    This should ideally query a payout table (SlotPayout model).
    Using a simplified placeholder logic here.
    """
    """
    Gets the payout multiplier for a given symbol ID and count from the config.
    `config_symbols_map` is the map of symbol objects from gameConfig.json.
    If `is_scatter` is true, it looks for 'scatter_payouts' from the symbol's config;
    otherwise, it looks for 'value_multipliers' for payline wins.
    """
    symbol_config = config_symbols_map.get(symbol_id)
    if not symbol_config:
        return 0.0

    if is_scatter:
        # Scatter payouts: uses 'scatter_payouts' from the symbol's configuration.
        # These are typically direct multipliers of the total bet.
        payout_map = symbol_config.get('scatter_payouts', {}) # e.g., {"3": 5, "4": 15, "5": 50}
    else:
        # Payline symbol multipliers: uses 'value_multipliers' from the symbol's configuration.
        # These are typically multipliers for the bet_per_line.
        payout_map = symbol_config.get('value_multipliers', {}) # e.g., {"3": 10, "4": 50, "5": 200}

    # `count` must be a string for dict lookup as per example gameConfig
    # Defensive: ensure keys in payout_map are strings if they were somehow loaded as int
    payout_map_str_keys = {str(k): v for k, v in payout_map.items()}
    multiplier = payout_map_str_keys.get(str(count), 0.0)

    # Ensure multiplier is float or int
    try:
        # Ensure that we handle cases where multiplier might be an empty string or None from config
        if multiplier is None or str(multiplier).strip() == "":
            return 0.0
        return float(multiplier)
    except ValueError:
        return 0.0



def calculate_win(grid, config_paylines, config_symbols_map, total_bet_sats, wild_symbol_id, scatter_symbol_id, min_symbols_to_match): # Removed current_spin_multiplier and general config_payouts
    """Calculates total win amount and identifies winning lines using config.
    `config_paylines` is game_config.game.layout.paylines
    `config_symbols_map` is game_config.game.symbols (mapped by id), used for symbol properties and payouts.
    `total_bet_sats` is the total amount bet for the entire spin.
    `wild_symbol_id` is the internal ID from config.
    `scatter_symbol_id` is the internal ID from config.
    `min_symbols_to_match` (from game_config.game.min_symbols_to_match) is for "Match N" or cluster logic.
    """
    # print(f"DEBUG_TEST_HANDLER: calculate_win called with total_bet_sats={total_bet_sats}") # Debug
    total_win_sats = 0
    winning_lines_data = [] # Store detailed info about each win
    all_winning_symbol_coords = set() # Using a set to store unique [r,c] tuples for removal
    num_rows = len(grid)
    num_cols = len(grid[0]) if num_rows > 0 else 0

    # --- Payline Wins ---
    # Bet per line calculation:
    num_active_paylines = len(config_paylines) # Assuming all defined paylines are played
    if num_active_paylines == 0:
        bet_per_line_sats = 0 # Avoid division by zero; though should not happen with valid config
    else:
        # Ensure integer division, handle potential rounding if necessary (though satoshis should be precise)
        bet_per_line_sats = total_bet_sats // num_active_paylines
        # It's possible that total_bet_sats is not perfectly divisible.
        # Game design should specify how this is handled (e.g. user bets per line, or total bet must be multiple of lines)
        # For now, we assume total_bet_sats is what's wagered, and bet_per_line is derived.
    # print(f"DEBUG_TEST_HANDLER: num_active_paylines={num_active_paylines}, bet_per_line_sats={bet_per_line_sats}") # Debug

    for payline_config in config_paylines:
        payline_id = payline_config.get("id", "unknown_line")
        payline_positions = payline_config.get("coords", []) # List of [row, col] #FIX: Changed "positions" to "coords"

        line_symbols_on_grid = [] # Actual symbol IDs on this payline from the spin grid
        actual_positions_on_line = [] # Coordinates of these symbols

        for r, c in payline_positions:
            if 0 <= r < num_rows and 0 <= c < num_cols:
                symbol_on_grid = grid[r][c]
                line_symbols_on_grid.append(symbol_on_grid)
                actual_positions_on_line.append([r,c])
            else: # Should not happen with valid config
                line_symbols_on_grid.append(None) # Placeholder for out-of-bounds
                actual_positions_on_line.append(None)

        # Determine winning symbol and count for this line (left-to-right)
        first_symbol_on_line = line_symbols_on_grid[0]
        if first_symbol_on_line is None or first_symbol_on_line == scatter_symbol_id:
            continue # Paylines typically don't start with scatter or empty positions

        match_symbol_id = None
        consecutive_count = 0
        winning_symbol_positions = []

        # Handle if the line starts with a wild symbol
        if first_symbol_on_line == wild_symbol_id:
            # Wilds substitute for other symbols. Need to find the first non-wild to determine the matching symbol.
            # Then count initial wilds + subsequent matching symbols or wilds.
            temp_match_symbol_id = None
            wilds_at_start = 0
            for i in range(len(line_symbols_on_grid)):
                s_id = line_symbols_on_grid[i]
                if s_id == wild_symbol_id:
                    wilds_at_start += 1
                    winning_symbol_positions.append(actual_positions_on_line[i])
                elif s_id != scatter_symbol_id : # Found the symbol to match
                    temp_match_symbol_id = s_id
                    consecutive_count = wilds_at_start + 1
                    winning_symbol_positions.append(actual_positions_on_line[i])
                    match_symbol_id = temp_match_symbol_id
                    break
                else: # Scatter or None, breaks payline continuity for this potential match
                    break

            if match_symbol_id is None and wilds_at_start > 0: # Line is all wilds (or wilds then scatter/None)
                # If game rules allow all-wild lines, determine payout for wild symbol itself
                # Wild symbol must have its own entry in 'value_multipliers' in config
                symbol_config = config_symbols_map.get(wild_symbol_id)
                if symbol_config and symbol_config.get('value_multipliers'):
                    match_symbol_id = wild_symbol_id
                    consecutive_count = wilds_at_start
                else: # Wilds don't form their own win, or line too short
                    continue
        else:
            # Line starts with a regular symbol
            match_symbol_id = first_symbol_on_line
            consecutive_count = 1
            winning_symbol_positions.append(actual_positions_on_line[0])

        # Continue counting from the position after initial sequence
        # If first symbol was wild and found a match, `consecutive_count` is already set.
        # `i` should start from `consecutive_count` index in `line_symbols_on_grid`.
        if match_symbol_id: # Proceed if a potential winning line is identified
            for i in range(consecutive_count, len(line_symbols_on_grid)):
                current_symbol_on_grid = line_symbols_on_grid[i]
                if current_symbol_on_grid == match_symbol_id or current_symbol_on_grid == wild_symbol_id:
                    consecutive_count += 1
                    winning_symbol_positions.append(actual_positions_on_line[i])
                else:
                    break # Sequence broken

        # Get payout for the matched sequence
        # The minimum match count is implicitly handled by what's defined in value_multipliers (e.g. no "1" or "2")
        payout_multiplier = get_symbol_payout(match_symbol_id, consecutive_count, config_symbols_map, is_scatter=False)
        # print(f"DEBUG_TEST_HANDLER: Payline {payline_id}, Symbol {match_symbol_id}, Count {consecutive_count}, PayoutMultiplier {payout_multiplier}") # Debug

        if payout_multiplier > 0:
            # Line win = bet_per_line * symbol_multiplier
            # Ensure bet_per_line_sats is used here.
            line_win_sats = int(bet_per_line_sats * payout_multiplier)

            # Apply spin multiplier if any (e.g. from free spins bonus)
            # This is now handled outside, after all raw wins are calculated.
            # line_win_sats = int(line_win_sats * current_spin_multiplier)


            if line_win_sats > 0:
                total_win_sats += line_win_sats
                winning_lines_data.append({
                    "line_id": payline_id, # From payline config
                    "symbol_id": match_symbol_id, # The symbol that formed the win (not wild, unless wild itself pays)
                    "count": consecutive_count,
                    "positions": winning_symbol_positions, # List of [r,c] coordinates
                    "win_amount_sats": line_win_sats
                })
                for pos in winning_symbol_positions:
                    all_winning_symbol_coords.add(tuple(pos))

    # --- Scatter Wins ---
    # (This part remains largely the same but contributes to all_winning_symbol_coords)
    scatter_positions_on_grid = []
    scatter_count_on_grid = 0
    if scatter_symbol_id is not None: # Check if a scatter symbol is configured
        for r_idx, row in enumerate(grid):
            for c_idx, symbol_in_cell in enumerate(row):
                if symbol_in_cell == scatter_symbol_id:
                    scatter_count_on_grid += 1
                    scatter_positions_on_grid.append([r_idx, c_idx])

    # Get scatter payout based on count
    # Scatter payouts are typically multiples of the *total bet*
    scatter_payout_multiplier = get_symbol_payout(scatter_symbol_id, scatter_count_on_grid, config_symbols_map, is_scatter=True)

    if scatter_payout_multiplier > 0:
        scatter_win_sats = int(total_bet_sats * scatter_payout_multiplier)
        # scatter_win_sats = int(scatter_win_sats * current_spin_multiplier) # Apply spin multiplier - also handled outside now

        if scatter_win_sats > 0:
            total_win_sats += scatter_win_sats
            winning_lines_data.append({
                "line_id": "scatter", # Special identifier for scatter wins
                "symbol_id": scatter_symbol_id,
                "count": scatter_count_on_grid,
                "positions": scatter_positions_on_grid,
                "win_amount_sats": scatter_win_sats
            })
            for pos in scatter_positions_on_grid: # Add scatter symbol positions for removal
                all_winning_symbol_coords.add(tuple(pos))

    # --- TODO: Implement "Match N" / Cluster Pays Logic ---
    # If cfg_min_symbols_to_match is not None:
    #   1. Count all symbol occurrences on the grid.
    #   2. For symbols meeting cfg_min_symbols_to_match:
    #      a. Find their positions.
    #      b. Calculate win based on cfg_payouts (needs a specific structure for this type of win).
    #      c. Add to total_win_sats, winning_lines_data, and all_winning_symbol_coords.
    # This section will be complex and require careful handling of payout definitions.
    # For now, this placeholder indicates where it would go.

    # --- "Match N" / Cluster Pays Logic ---
    # This logic assumes "anywhere on grid" for clusters, and wilds contribute to any cluster they can help form.
    if min_symbols_to_match is not None and min_symbols_to_match > 0:
        symbol_counts = {}
        symbol_positions_map = {} # Stores list of positions for each symbol_id (excluding wilds initially)

        # Count literal symbols and their positions (excluding wilds for base count)
        for r, row_data in enumerate(grid):
            for c, s_id_in_cell in enumerate(row_data):
                if s_id_in_cell is None: continue

                # For cluster base counts, we only consider non-wild, non-scatter symbols here.
                # Wilds are counted separately and added to effective counts.
                # Scatters are typically handled by their own independent payout logic.
                if s_id_in_cell != wild_symbol_id and s_id_in_cell != scatter_symbol_id:
                    symbol_counts[s_id_in_cell] = symbol_counts.get(s_id_in_cell, 0) + 1
                    if s_id_in_cell not in symbol_positions_map:
                        symbol_positions_map[s_id_in_cell] = []
                    symbol_positions_map[s_id_in_cell].append([r, c])

        # Count total wilds on the grid and their positions
        num_wilds_on_grid = 0
        wild_positions_on_grid = []
        if wild_symbol_id is not None:
            for r_idx, row_data in enumerate(grid):
                for c_idx, s_id_in_cell in enumerate(row_data):
                    if s_id_in_cell == wild_symbol_id:
                        num_wilds_on_grid += 1
                        wild_positions_on_grid.append([r_idx, c_idx])

        for symbol_id, literal_symbol_count in symbol_counts.items():
            # Wilds do not form their own cluster type; they assist other symbols.
            # Scatter symbols are handled by their dedicated scatter win logic, not cluster logic here.
            if symbol_id == wild_symbol_id or symbol_id == scatter_symbol_id: # Should already be excluded by map population
                continue

            effective_count = literal_symbol_count + num_wilds_on_grid

            if effective_count >= min_symbols_to_match:
                # This symbol forms a "match N" win with the help of wilds.
                # `config_payouts` is a list of dicts. We need to find the relevant one.
                # Example structure for a cluster payout entry in `config_payouts`:
                # { "type": "cluster", "symbol_id": <ID>, "matches": <N>, "multiplier": <X_per_symbol_or_fixed> }
                # Or payouts might be within the symbol definition in `config_symbols_map`
                # e.g. config_symbols_map[symbol_id].get('cluster_payouts', {}).get(str(effective_count))

                payout_value_for_cluster = 0
                symbol_config_data = config_symbols_map.get(symbol_id, {})
                cluster_payout_rules = symbol_config_data.get('cluster_payouts', {}) # e.g. {"8": 100, "9": 150}

                if cluster_payout_rules:
                    # The key in cluster_payouts is the string representation of the effective_count.
                    payout_value_for_cluster = cluster_payout_rules.get(str(effective_count), 0.0)

                # Attempt 2: Fallback or alternative - search generic `config_payouts` list
                # This is less direct. The gameConfig structure needs to be clear.
                # if not payout_value_for_cluster:
                #     for payout_rule in config_payouts:
                #         if payout_rule.get("type") == "cluster" and \
                #            payout_rule.get("symbol_id") == symbol_id and \
                #            payout_rule.get("matches") == count:
                #             payout_value_for_cluster = payout_rule.get("multiplier", 0.0)
                #             break

                if payout_value_for_cluster > 0:
                    # Cluster win amount calculation.
                    # Cluster win calculation: total_bet_sats * payout_value_for_cluster.
                    # This assumes the payout_value_for_cluster is a direct multiplier of the total bet for that cluster.
                    cluster_win_sats_this_group = int(total_bet_sats * payout_value_for_cluster)

                    if cluster_win_sats_this_group > 0:
                        print(f"DEBUG: Cluster win for symbol {symbol_id} count {count} with multiplier {payout_value_for_cluster}. Win: {cluster_win_sats_this_group}")
                        total_win_sats += cluster_win_sats_this_group

                        # Combine positions of the literal symbols and all wild symbols
                        current_symbol_positions = symbol_positions_map.get(symbol_id, [])
                        combined_positions_set = set()
                        for pos in current_symbol_positions:
                            combined_positions_set.add(tuple(pos))
                        for wild_pos in wild_positions_on_grid:
                            combined_positions_set.add(tuple(wild_pos))

                        winning_coords_for_this_cluster = [list(pos) for pos in combined_positions_set]

                        winning_lines_data.append({
                            "line_id": f"cluster_{symbol_id}_{effective_count}", # Unique ID for this win type
                            "symbol_id": symbol_id, # The base symbol that formed the cluster
                            "count": effective_count, # Effective count including wilds
                            "positions": winning_coords_for_this_cluster,
                            "win_amount_sats": cluster_win_sats_this_group,
                            "type": "cluster"
                        })
                        for pos_tuple in combined_positions_set: # Add all contributing positions to all_winning_symbol_coords
                            all_winning_symbol_coords.add(pos_tuple)

    return {
        "total_win_sats": total_win_sats, # Raw total, multiplier applied in main handle_spin
        "winning_lines": winning_lines_data,
        "winning_symbol_coords": [list(coords) for coords in all_winning_symbol_coords] # Convert tuples back to lists
    }

# --- Cascade Logic Helper ---
def handle_cascade_fill(current_grid, winning_coords_to_clear, cascade_type, db_symbols, config_symbols_map, wild_symbol_config_id, scatter_symbol_config_id):
    """
    Handles the filling of the grid after winning symbols are removed in a cascade.

    Args:
        current_grid (list[list[int]]): The current state of the slot grid.
        winning_coords_to_clear (list[list[int]]): List of [row, col] of symbols to remove.
        cascade_type (str): How new symbols are introduced (e.g., "fall_from_top", "replace_in_place").
        db_symbols (list): List of SlotSymbol ORM objects for the slot (used by generate_spin_grid).
        config_symbols_map (dict): Map of symbol configurations from gameConfig.json.
        wild_symbol_config_id (int): ID of the wild symbol.
        scatter_symbol_config_id (int): ID of the scatter symbol.

    Returns:
        list[list[int]]: The new grid after clearing winning symbols and filling empty spaces.
    """
    if not current_grid:
        return []

    rows = len(current_grid)
    cols = len(current_grid[0])
    new_grid = [row[:] for row in current_grid] # Create a mutable copy

    # Mark winning symbols for removal (e.g., replace with a temporary marker like None)
    for r, c in winning_coords_to_clear:
        if 0 <= r < rows and 0 <= c < cols:
            new_grid[r][c] = None # Mark as empty

    if cascade_type == "fall_from_top":
        for c in range(cols):
            empty_slots_in_col = 0
            # Move non-empty symbols down
            for r in range(rows - 1, -1, -1): # Iterate from bottom to top of column
                if new_grid[r][c] is None:
                    empty_slots_in_col += 1
                elif empty_slots_in_col > 0:
                    # Shift symbol down
                    new_grid[r + empty_slots_in_col][c] = new_grid[r][c]
                    new_grid[r][c] = None # Mark original position as empty

            # Fill empty slots at the top with new random symbols
            if empty_slots_in_col > 0:
                # Generate a small grid (column strip) of new symbols
                # For simplicity, generate one by one, though generate_spin_grid could be adapted
                # to generate a partial grid or a column if needed.
                # Here, we generate individual symbols for the top of the column.

                # Get weighted symbols for generation (similar to generate_spin_grid)
                spinable_symbol_ids = [s_id for s_id in config_symbols_map.keys() if s_id in [s.symbol_internal_id for s in db_symbols]]
                if not spinable_symbol_ids: # Should not happen if initial grid generation worked
                    raise ValueError("No spinable symbols for cascade fill.")

                weights = []
                symbols_for_choice = []
                for s_id in spinable_symbol_ids:
                    symbol_config = config_symbols_map.get(s_id)
                    if symbol_config:
                        raw_weight = symbol_config.get('weight')
                        current_weight = 1.0 # Default weight
                        if isinstance(raw_weight, (int, float)) and raw_weight > 0:
                            current_weight = float(raw_weight)
                        else:
                            # Log warning for missing/invalid weight in cascade
                            pass
                        weights.append(current_weight)
                        symbols_for_choice.append(s_id)

                total_weight = sum(weights)
                if total_weight == 0 or not symbols_for_choice:
                    if not symbols_for_choice: symbols_for_choice = spinable_symbol_ids
                    weights = [1.0 / len(symbols_for_choice) if symbols_for_choice else 1.0] * len(symbols_for_choice)
                else:
                    weights = [w / total_weight for w in weights]

                secure_random = secrets.SystemRandom()
                for r_fill in range(empty_slots_in_col):
                    if symbols_for_choice: # Ensure there are symbols to choose from
                        new_grid[r_fill][c] = secure_random.choices(symbols_for_choice, weights=weights, k=1)[0]
                    else: # Fallback if no symbols somehow (should be caught earlier)
                        new_grid[r_fill][c] = spinable_symbol_ids[0] if spinable_symbol_ids else 0 # Default to 0 or first available

    elif cascade_type == "replace_in_place":
        # Similar symbol generation logic as above, but directly into winning_coords_to_clear
        spinable_symbol_ids = [s_id for s_id in config_symbols_map.keys() if s_id in [s.symbol_internal_id for s in db_symbols]]
        if not spinable_symbol_ids:
            raise ValueError("No spinable symbols for cascade fill (replace_in_place).")

        weights = []
        symbols_for_choice = []
        for s_id in spinable_symbol_ids:
            symbol_config = config_symbols_map.get(s_id)
            if symbol_config:
                raw_weight = symbol_config.get('weight')
                current_weight = 1.0 # Default weight
                if isinstance(raw_weight, (int, float)) and raw_weight > 0:
                    current_weight = float(raw_weight)
                else:
                    # Log warning for missing/invalid weight in cascade
                    pass
                weights.append(current_weight)
                symbols_for_choice.append(s_id)

        total_weight = sum(weights)
        if total_weight == 0 or not symbols_for_choice:
            if not symbols_for_choice: symbols_for_choice = spinable_symbol_ids
            weights = [1.0 / len(symbols_for_choice) if symbols_for_choice else 1.0] * len(symbols_for_choice)
        else:
            weights = [w / total_weight for w in weights]

        secure_random = secrets.SystemRandom()
        for r, c in winning_coords_to_clear: # Iterate through the specific empty slots
            if symbols_for_choice:
                new_grid[r][c] = secure_random.choices(symbols_for_choice, weights=weights, k=1)[0]
            else:
                new_grid[r][c] = spinable_symbol_ids[0] if spinable_symbol_ids else 0
    else:
        # If cascade_type is unknown or None, or not implemented, just return grid with empty spaces
        # Or, could raise an error if an unsupported cascade_type is specified.
        # For now, returning grid with None values where symbols were cleared.
        # The game logic would then stop cascading if it encounters these.
        print(f"Warning: Unknown or unimplemented cascade_type: {cascade_type}. Returning grid with removed symbols only.")

    return new_grid


def check_bonus_trigger(grid, scatter_symbol_id, config_bonus_features):
    # print(f"DEBUG_TEST_HANDLER: check_bonus_trigger called.")
    # print(f"DEBUG_TEST_HANDLER: grid received: {grid}")
    # print(f"DEBUG_TEST_HANDLER: scatter_symbol_id param: {scatter_symbol_id}")
    # print(f"DEBUG_TEST_HANDLER: config_bonus_features param: {config_bonus_features}")
    """
    Checks if conditions are met to trigger a bonus round based on gameConfig.json.
    `config_bonus_features` is game_config.game.bonus_features.
    Returns a dict with 'triggered': bool, and other bonus details if triggered.
    """
    # Example for free_spins, extend for other bonus types
    free_spins_config = config_bonus_features.get('free_spins')
    if not free_spins_config or not scatter_symbol_id:
        return {'triggered': False}

    trigger_sym_id = free_spins_config.get('trigger_symbol_id')
    if trigger_sym_id != scatter_symbol_id: # Ensure config matches primary scatter_id for clarity
        # Or handle cases where a different symbol triggers bonus. For now, assume it's the main scatter.
        # Log a warning if they don't match?
        pass

    min_scatter_to_trigger = free_spins_config.get('trigger_count')
    if not min_scatter_to_trigger:
        return {'triggered': False}

    scatter_count = 0
    for r_idx, row in enumerate(grid):
        for c_idx, symbol_id_in_cell in enumerate(row):
            if symbol_id_in_cell == scatter_symbol_id: # Use the passed scatter_symbol_id from game root
                scatter_count += 1
                # print(f"DEBUG_TEST_HANDLER: Found scatter {scatter_symbol_id} at row {r_idx}, cell {c_idx}. Current scatter_count: {scatter_count}")

    # Condition: the symbol counted (scatter_symbol_id arg) must be the trigger_symbol_id from this bonus config,
    # and the count must meet the minimum.
    # print(f"DEBUG_TEST_HANDLER: Final scatter_count: {scatter_count}, min_scatter_to_trigger: {min_scatter_to_trigger if free_spins_config else 'N/A'}") # Added before return
    if trigger_sym_id is not None and scatter_symbol_id == trigger_sym_id and scatter_count >= min_scatter_to_trigger:
        # print(f"DEBUG_TEST_HANDLER: Returning: {{'triggered': True, ...}}") # Added before return
        return {
            'triggered': True,
            'type': 'free_spins', # Or derive from config key
            'spins_awarded': free_spins_config.get('spins_awarded', 0),
            'multiplier': free_spins_config.get('multiplier', 1.0)
            # Add other bonus parameters if needed
        }

    # print(f"DEBUG_TEST_HANDLER: Returning: {{'triggered': False}}") # Added before return
    return {'triggered': False}
