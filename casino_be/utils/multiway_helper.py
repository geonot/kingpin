import os
import json
import random
from flask import current_app
import secrets
from casino_be.utils.spin_handler import SLOT_CONFIG_BASE_PATH

def load_multiway_game_config(slot_short_name):
    """
    Loads the game configuration JSON file for a given multiway slot.
    This is similar to load_game_config in spin_handler.py but intended
    for multiway-specific configurations if they differ, or can be a direct reuse
    if the structure is identical.
    """
    # Construct path like "public/slots/slot_short_name/gameConfig.json"
    config_path = os.path.join(SLOT_CONFIG_BASE_PATH, slot_short_name, "gameConfig.json")

    if not os.path.exists(config_path):
        # Log or raise a more specific error for multiway config
        raise FileNotFoundError(f"Multiway game configuration not found for slot '{slot_short_name}' at {config_path}")

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config
    except json.JSONDecodeError as e:
        # Log error details
        raise ValueError(f"Error decoding JSON from {config_path}: {e}")
    except Exception as e:
        # Log error details
        raise RuntimeError(f"An unexpected error occurred while loading multiway game config from {config_path}: {e}")

def generate_multiway_spin_grid(
    slot_reel_configurations,
    num_reels,
    config_symbols_map,
    wild_symbol_config_id,
    scatter_symbol_config_id,
    db_symbols
):
    """
    Generates a multiway spin grid where the number of symbols per reel can vary.

    Args:
        slot_reel_configurations (dict): Configuration for reel pane counts.
            Example: {"possible_counts_per_reel": [[2,3,4], [3,4,5], ...]}
        num_reels (int): The number of reels for the slot.
        config_symbols_map (dict): Symbols map from gameConfig.json.
        wild_symbol_config_id (int, optional): ID of the wild symbol.
        scatter_symbol_config_id (int, optional): ID of the scatter symbol.
        db_symbols (list): List of SlotSymbol ORM objects for the slot.

    Returns:
        dict: {
            "panes_per_reel": list[int],  # e.g., [3, 4, 2, 5, 3]
            "symbols_grid": list[list[int]] # e.g., [[10,2,5], [4,2,1,5], ...]
        }
    """
    panes_per_reel = []
    secure_random = secrets.SystemRandom()

    possible_counts_per_reel = slot_reel_configurations.get("possible_counts_per_reel")

    if not possible_counts_per_reel or not isinstance(possible_counts_per_reel, list) or len(possible_counts_per_reel) != num_reels:
        # Fallback or error: If config is missing or malformed, default to 3 panes for all reels or raise error.
        # For now, let's default to 3 for robustness, but this should ideally be an error.
        # Consider raising ValueError for critical config issues.
        # Defaulting to a fixed size (e.g. 3xnum_reels) makes it not truly "multiway" based on this dynamic config.
        # However, the question implies `possible_counts_per_reel` is the primary source.
        # If `slot_reel_configurations` itself is None, or "possible_counts_per_reel" is absent:
        if possible_counts_per_reel is None:
             # This is a more critical error if the slot is marked is_multiway but has no reel_configurations.
             # Fallback to a default (e.g. 3 panes) or raise an error.
             # For now, let's assume a default of 3 if not specified.
             # This path should be reviewed based on how strictly multiway slots *must* have this config.
             # If `reel_configurations` can be None for a multiway slot, a default needs to be defined.
             # If `reel_configurations` *must* exist for `is_multiway=True` slots, then this is an error condition.
            # Defaulting to 3 panes per reel if config is missing.
            current_app.logger.warning(f"'possible_counts_per_reel' missing or malformed in slot_reel_configurations. Defaulting to 3 panes for {num_reels} reels.")
            panes_per_reel = [3] * num_reels
        else: # Config exists but is malformed for the number of reels
            raise ValueError(
                f"Configuration error: 'possible_counts_per_reel' must be a list of {num_reels} lists. "
                f"Received: {possible_counts_per_reel}"
            )


    for reel_idx in range(num_reels):
        if possible_counts_per_reel and reel_idx < len(possible_counts_per_reel):
            possible_counts_for_this_reel = possible_counts_per_reel[reel_idx]
            if not possible_counts_for_this_reel or not isinstance(possible_counts_for_this_reel, list):
                # Default for this specific reel if its config is bad
                current_app.logger.warning(f"Malformed 'possible_counts' for reel {reel_idx}. Defaulting to 3 panes.")
                panes_per_reel.append(3)
            else:
                panes_per_reel.append(secure_random.choice(possible_counts_for_this_reel))
        else:
            # This case should ideally be caught by the length check above if possible_counts_per_reel is present
            # If possible_counts_per_reel was None initially and we defaulted, this won't be hit.
            # If it was present but shorter than num_reels (and not caught by initial length check for some reason),
            # we default this specific reel.
            current_app.logger.warning(f"Configuration missing for reel {reel_idx} beyond 'possible_counts_per_reel' length. Defaulting to 3 panes.")
            panes_per_reel.append(3)


    # --- Symbol Selection Logic (adapted from spin_handler.generate_spin_grid) ---
    if not db_symbols:
        # Fallback or error if no symbols are defined for the slot in DB.
        # This indicates a critical setup issue.
        # For multiway, each reel column would be empty or filled with a placeholder.
        # This part needs careful consideration on how to handle.
        # Returning empty lists or raising an error are options.
        raise ValueError("Cannot generate multiway grid: No symbols defined in db_symbols for this slot.")

    valid_symbol_ids_for_slot = [s.symbol_internal_id for s in db_symbols]
    spinable_symbol_ids = [sid for sid in valid_symbol_ids_for_slot if sid in config_symbols_map]

    if not spinable_symbol_ids:
        raise ValueError("No spinable symbols found. Check slot DB symbol configuration against gameConfig.json.")

    weights = []
    symbols_for_choice = []
    for s_id in spinable_symbol_ids:
        symbol_config = config_symbols_map.get(s_id)
        if symbol_config:
            # Using 'weight' from symbol config, default to 1.0
            # Special handling for wild/scatter weights can be added if needed,
            # but current spin_handler logic applies a generic 'weight' property.
            weights.append(float(symbol_config.get('weight', 1.0))) # Ensure weight is float
            symbols_for_choice.append(s_id)

    total_weight = sum(weights)
    if total_weight == 0 or not symbols_for_choice:
        if not symbols_for_choice: # Should be caught by `if not spinable_symbol_ids:`
            raise ValueError("Cannot generate spin grid: No symbols available for choice.")
        # If all weights are zero, distribute uniformly
        num_symbols = len(symbols_for_choice)
        weights = [1.0 / num_symbols] * num_symbols
    else:
        weights = [w / total_weight for w in weights]

    # Generate the jagged grid
    spin_grid_symbols = []
    for reel_idx in range(num_reels):
        num_panes_for_this_reel = panes_per_reel[reel_idx]
        if num_panes_for_this_reel <= 0 : # Should not happen if config is sane (e.g. counts are positive)
            # Add an empty list for this reel if it somehow gets 0 or negative panes.
            # This indicates bad configuration.
            reel_symbols = []
            current_app.logger.warning(f"Reel {reel_idx} has {num_panes_for_this_reel} panes. Check reel_configurations.")
        elif not symbols_for_choice : # Should be caught earlier
            reel_symbols = [] # No symbols to choose from
        else:
            reel_symbols = secure_random.choices(
                symbols_for_choice,
                weights=weights,
                k=num_panes_for_this_reel
            )
        spin_grid_symbols.append(reel_symbols)

    return {
        "panes_per_reel": panes_per_reel,
        "symbols_grid": spin_grid_symbols
    }

# Example usage (optional, for testing or demonstration):
# if __name__ == '__main__':
#     try:
#         # Create dummy files for testing if SLOT_CONFIG_BASE_PATH is relative to current execution
#         # This assumes you run this script from a directory where 'public/slots/testslot/gameConfig.json' can be created.
#         # For actual use, these files would exist as part of your application structure.
#         if not os.path.exists(os.path.join(SLOT_CONFIG_BASE_PATH, "testslot")):
#             os.makedirs(os.path.join(SLOT_CONFIG_BASE_PATH, "testslot"))
#         with open(os.path.join(SLOT_CONFIG_BASE_PATH, "testslot", "gameConfig.json"), 'w') as f:
#             json.dump({"name": "Test Multiway Slot", "version": "1.0"}, f)
#
#         config = load_multiway_game_config("testslot")
#         print("Loaded config:", config)
#
#         # Test FileNotFoundError
#         # config_not_found = load_multiway_game_config("nonexistentslot")
#         # print("Config (not found):", config_not_found)
#
#     except Exception as e:
#         print(f"Error in example usage: {e}")

def calculate_multiway_win(
    spin_result,
    config_symbols_map,
    total_bet_sats,
    wild_symbol_config_id,
    scatter_symbol_config_id,
    game_config
):
    """
    Calculates wins for a multiway slot machine.

    Args:
        spin_result (dict): Output from generate_multiway_spin_grid
                            {"panes_per_reel": list, "symbols_grid": list[list]}.
        config_symbols_map (dict): Symbols map from gameConfig.json.
        total_bet_sats (int): Total amount bet for the spin.
        wild_symbol_config_id (int, optional): ID of the wild symbol.
        scatter_symbol_config_id (int, optional): ID of the scatter symbol.
        game_config (dict): Full game configuration.

    Returns:
        dict: {
            "total_win_sats": int,
            "winning_lines_data": list[dict] # List of winning ways/scatter details
        }
    """
    total_win_sats = 0
    winning_ways_data = []
    symbols_grid = spin_result["symbols_grid"]
    num_reels = len(symbols_grid)

    if num_reels == 0:
        return {"total_win_sats": 0, "winning_lines_data": []}

    min_match_for_ways_win = game_config.get('game', {}).get('min_match_for_ways_win', 3)
    bet_divisor_for_ways = float(game_config.get('game', {}).get('bet_ways_divisor', 1.0))
    effective_bet_for_ways = total_bet_sats / bet_divisor_for_ways

    # --- Calculate "Ways" Wins ---
    first_reel_symbols_processed_for_ways = set()

    if not symbols_grid[0]: # First reel has no symbols
        pass # No ways wins possible if first reel is empty

    else:
        for first_reel_pane_idx, base_symbol_id_from_pane in enumerate(symbols_grid[0]):
            
            # Determine the actual base symbol for the way (if wild on first reel, what it represents)
            # For this simplified version, if wild is on 1st reel, it can only form a "wild way"
            # if wilds themselves have a payout. It doesn't "become" every other symbol for starting ways.
            # The core idea is a way is defined by a specific symbol type from left to right.
            base_symbol_id = base_symbol_id_from_pane

            if base_symbol_id == scatter_symbol_config_id:
                continue # Scatters are handled separately

            # If we treat wilds on the first reel as only "wilds" for payout purposes:
            # if base_symbol_id == wild_symbol_config_id and wild_symbol_config_id is not None:
            # This logic branch would be if wilds themselves can start a way and have payouts.
            # For now, we assume a way is started by a non-wild symbol, or wild symbol if it explicitly pays as "wild way".

            if base_symbol_id in first_reel_symbols_processed_for_ways:
                continue
            first_reel_symbols_processed_for_ways.add(base_symbol_id)

            current_ways_for_symbol = 0
            num_reels_matched = 0
            # Stores lists of [reel_idx, pane_idx] for each reel in the matched sequence
            winning_positions_for_this_way_sequence = [[] for _ in range(num_reels)]


            for reel_idx in range(num_reels):
                count_on_this_reel = 0
                positions_on_this_reel_for_current_symbol = []
                if reel_idx >= len(symbols_grid) or not symbols_grid[reel_idx]: # Reel missing or empty
                    break # End of this potential way

                for pane_idx, symbol_on_pane in enumerate(symbols_grid[reel_idx]):
                    is_match = (symbol_on_pane == base_symbol_id)
                    is_wild_substitute = (wild_symbol_config_id is not None and \
                                          symbol_on_pane == wild_symbol_config_id and \
                                          base_symbol_id != wild_symbol_config_id) # Wild cannot substitute itself unless it's the base_symbol

                    if is_match or is_wild_substitute:
                        count_on_this_reel += 1
                        positions_on_this_reel_for_current_symbol.append([reel_idx, pane_idx])
                
                if count_on_this_reel > 0:
                    if num_reels_matched == 0: # First reel in the sequence for this symbol
                        current_ways_for_symbol = count_on_this_reel
                    else:
                        current_ways_for_symbol *= count_on_this_reel
                    num_reels_matched += 1
                    # Store positions for this reel, even if it's just wilds substituting
                    winning_positions_for_this_way_sequence[reel_idx].extend(positions_on_this_reel_for_current_symbol)
                else:
                    break # Symbol (or its wild substitute) not found, way broken

            if num_reels_matched >= min_match_for_ways_win:
                payout_config_for_symbol = config_symbols_map.get(base_symbol_id, {}).get('payouts', {}).get('ways', {})
                if not payout_config_for_symbol and base_symbol_id == wild_symbol_config_id: # Check if wild has its own ways payout
                     payout_config_for_symbol = config_symbols_map.get(wild_symbol_config_id, {}).get('payouts', {}).get('ways', {})


                payout_multiplier = float(payout_config_for_symbol.get(str(num_reels_matched), 0.0))

                if payout_multiplier > 0:
                    way_win_sats = int(current_ways_for_symbol * payout_multiplier * effective_bet_for_ways)
                    if way_win_sats > 0:
                        total_win_sats += way_win_sats
                        
                        # Collect only positions that contributed to the win up to num_reels_matched
                        actual_winning_positions = []
                        temp_positions_collector = [[] for _ in range(num_reels_matched)]

                        # Re-evaluate positions based on the actual base_symbol_id for this win
                        # This is to ensure wilds are included correctly in the positions if they formed part of the way.
                        for r_idx_check in range(num_reels_matched):
                            for p_idx_check, sym_check in enumerate(symbols_grid[r_idx_check]):
                                if sym_check == base_symbol_id or \
                                   (wild_symbol_config_id is not None and sym_check == wild_symbol_config_id):
                                    temp_positions_collector[r_idx_check].append([r_idx_check, p_idx_check])
                        
                        # Filter out empty lists from the end if reels didn't contribute
                        final_positions = [pos_list for pos_list in temp_positions_collector if pos_list]


                        winning_ways_data.append({
                            "type": "way",
                            "symbol_id": base_symbol_id,
                            "reels_matched": num_reels_matched,
                            "ways_count": current_ways_for_symbol, # Renamed from "ways"
                            "win_amount_sats": way_win_sats,
                            "is_scatter": False,
                            # "positions": [pos_list for pos_list in winning_positions_for_this_way_sequence if pos_list][:num_reels_matched]
                            "positions": final_positions
                        })

    # --- Calculate Scatter Wins ---
    scatter_positions_on_grid = []
    scatter_count_on_grid = 0
    if scatter_symbol_config_id is not None:
        for r_idx, reel_symbols in enumerate(symbols_grid):
            for p_idx, symbol_in_cell in enumerate(reel_symbols):
                if symbol_in_cell == scatter_symbol_config_id:
                    scatter_count_on_grid += 1
                    scatter_positions_on_grid.append([r_idx, p_idx])

    if scatter_count_on_grid > 0:
        # Scatter payouts are typically defined in gameConfig under the symbol's properties
        # e.g. config_symbols_map[scatter_id]['payouts']['scatter'] = {"3": 5, "4": 10, "5": 25}
        # These multipliers are usually for the *total bet*.
        scatter_payout_rules = config_symbols_map.get(scatter_symbol_config_id, {}).get('payouts', {}).get('scatter', {})
        scatter_payout_multiplier = float(scatter_payout_rules.get(str(scatter_count_on_grid), 0.0))

        if scatter_payout_multiplier > 0:
            scatter_win_sats = int(scatter_payout_multiplier * total_bet_sats)
            if scatter_win_sats > 0:
                total_win_sats += scatter_win_sats
                winning_ways_data.append({
                    "type": "scatter",
                    "symbol_id": scatter_symbol_config_id,
                    "count": scatter_count_on_grid,
                    "win_amount_sats": scatter_win_sats,
                    "is_scatter": True,
                    "positions": scatter_positions_on_grid
                })

    return {
        "total_win_sats": total_win_sats,
        "winning_lines_data": winning_ways_data # Key consistent with payline slots
    }

# --- Main Handler ---
from datetime import datetime, timezone
# Assuming models.py is in the parent directory of utils/
# Adjust if your project structure is different (e.g. casino_be.models)
from casino_be.models import db, SlotSpin, GameSession, User, Transaction, UserBonus
from casino_be.utils.spin_handler import check_bonus_trigger # Reusing bonus trigger logic

def handle_multiway_spin(user: User, slot: db.Model, game_session: GameSession, bet_amount_sats: int):
    """
    Handles the logic for a single multiway slot machine spin.
    Adapted from spin_handler.handle_spin.
    """
    if not slot.is_multiway or not slot.reel_configurations:
        raise ValueError(f"Slot {slot.short_name} is not configured for multiway spins or lacks reel_configurations.")

    try:
        # --- Load Game Configuration ---
        game_config = load_multiway_game_config(slot.short_name)
        cfg_symbols_map = {s['id']: s for s in game_config.get('game', {}).get('symbols', [])}
        cfg_wild_symbol_id = game_config.get('game', {}).get('wild_symbol_id')
        cfg_scatter_symbol_id = game_config.get('game', {}).get('scatter_symbol_id')
        cfg_bonus_features = game_config.get('game', {}).get('bonus_features', {})

        # --- Pre-Spin Validation ---
        if not isinstance(bet_amount_sats, int) or bet_amount_sats <= 0:
            raise ValueError("Invalid bet amount. Must be a positive integer (satoshis).")

        if not (game_session.bonus_active and game_session.bonus_spins_remaining > 0) and \
           user.balance < bet_amount_sats:
            raise ValueError("Insufficient balance for this bet.")

        # --- Update Wagering Progress if Active Bonus (for PAID spins) ---
        actual_bet_this_spin_for_wagering = 0
        if not (game_session.bonus_active and game_session.bonus_spins_remaining > 0):
            actual_bet_this_spin_for_wagering = bet_amount_sats

        wager_tx = None # Initialize wager_tx
        win_tx = None   # Initialize win_tx

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

        # --- Determine Spin Type and Deduct Bet ---
        is_bonus_spin = False
        current_spin_multiplier = 1.0

        if game_session.bonus_active and game_session.bonus_spins_remaining > 0:
            is_bonus_spin = True
            current_spin_multiplier = game_session.bonus_multiplier
            game_session.bonus_spins_remaining -= 1
            actual_bet_this_spin = 0 # No cost for bonus spins
        else:
            user.balance -= bet_amount_sats
            actual_bet_this_spin = bet_amount_sats
            wager_tx = Transaction(
                user_id=user.id,
                amount=-bet_amount_sats,
                transaction_type='wager',
                details={'slot_name': slot.name, 'session_id': game_session.id, 'spin_type': 'multiway'},
                game_session_id=game_session.id
            )
            db.session.add(wager_tx)

        # --- Generate Spin Result (Multiway Specific) ---
        if not slot.reel_configurations:
             raise ValueError(f"Slot {slot.short_name} is multiway but missing reel_configurations.")
        if not slot.symbols:
            raise ValueError(f"Slot {slot.short_name} has no symbols defined in db_symbols.")

        generated_grid_data = generate_multiway_spin_grid(
            slot.reel_configurations, # From Slot model
            slot.num_columns,          # Assuming num_columns from Slot model is num_reels
            cfg_symbols_map,
            cfg_wild_symbol_id,
            cfg_scatter_symbol_id,
            slot.symbols               # List of SlotSymbol ORM objects
        )

        # --- Calculate Wins (Multiway Specific) ---
        # Note: actual_bet_this_spin is used for scatter win calculations if they are based on total bet.
        # For ways wins, calculate_multiway_win uses total_bet_sats (original bet before bonus considerations)
        # and its own bet_divisor_for_ways logic.
        win_calculation_result = calculate_multiway_win(
            generated_grid_data,
            cfg_symbols_map,
            bet_amount_sats, # Original bet amount for payout scaling
            cfg_wild_symbol_id,
            cfg_scatter_symbol_id,
            game_config
        )
        win_amount_sats = win_calculation_result['total_win_sats']
        winning_lines = win_calculation_result['winning_lines_data'] # This is winning_ways_data

        if is_bonus_spin and current_spin_multiplier > 1.0:
            win_amount_sats = int(win_amount_sats * current_spin_multiplier)
            for line_win_detail in winning_lines:
                line_win_detail['win_amount_sats'] = int(line_win_detail['win_amount_sats'] * current_spin_multiplier)

        # --- Check for Bonus Trigger (using multiway grid) ---
        bonus_triggered_this_spin = False
        if not is_bonus_spin:
            # check_bonus_trigger expects a grid of symbol IDs.
            # generated_grid_data["symbols_grid"] is the correct structure.
            bonus_trigger_info = check_bonus_trigger(
                generated_grid_data["symbols_grid"], # Pass the actual grid of symbols
                cfg_scatter_symbol_id,
                cfg_bonus_features
            )
            if bonus_trigger_info['triggered']:
                bonus_triggered_this_spin = True
                newly_awarded_spins = bonus_trigger_info.get('spins_awarded', 0)
                new_bonus_multiplier = bonus_trigger_info.get('multiplier', 1.0)

                if not game_session.bonus_active:
                    game_session.bonus_active = True
                    game_session.bonus_spins_remaining = newly_awarded_spins
                    game_session.bonus_multiplier = new_bonus_multiplier
                else: # Re-trigger
                    game_session.bonus_spins_remaining += newly_awarded_spins
                    if new_bonus_multiplier != game_session.bonus_multiplier and newly_awarded_spins > 0:
                        game_session.bonus_multiplier = new_bonus_multiplier # Or some other logic like max()

        elif game_session.bonus_active and game_session.bonus_spins_remaining <= 0:
            game_session.bonus_active = False
            game_session.bonus_multiplier = 1.0 # Reset

        # --- Update Session Aggregates ---
        game_session.num_spins += 1
        if not is_bonus_spin:
            game_session.amount_wagered = (game_session.amount_wagered or 0) + actual_bet_this_spin
        game_session.amount_won = (game_session.amount_won or 0) + win_amount_sats

        # --- Update User Balance & Win Transaction ---
        if win_amount_sats > 0:
            user.balance += win_amount_sats
            win_tx = Transaction(
                user_id=user.id,
                amount=win_amount_sats,
                transaction_type='win',
                details={'slot_name': slot.name, 'session_id': game_session.id, 'spin_type': 'multiway'},
                game_session_id=game_session.id
            )
            db.session.add(win_tx)

        # --- Create Spin Record ---
        # `generated_grid_data` includes `panes_per_reel` and `symbols_grid`
        new_spin = SlotSpin(
            game_session_id=game_session.id,
            spin_result=generated_grid_data, # Store the full multiway grid data
            win_amount=win_amount_sats,
            bet_amount=actual_bet_this_spin, # This is 0 for bonus spins
            is_bonus_spin=is_bonus_spin,
            spin_time=datetime.now(timezone.utc)
        )
        db.session.add(new_spin)
        db.session.flush() # To get new_spin.id

        if wager_tx:
            wager_tx.slot_spin_id = new_spin.id
            wager_tx.details['slot_spin_id'] = new_spin.id
        if win_tx:
            win_tx.slot_spin_id = new_spin.id
            win_tx.details['slot_spin_id'] = new_spin.id

        # --- Return Results ---
        return {
            "spin_result": generated_grid_data, # Includes panes_per_reel and symbols_grid
            "win_amount_sats": int(win_amount_sats),
            "winning_lines": winning_lines, # This is winning_ways_data
            "bonus_triggered": bonus_triggered_this_spin,
            "bonus_active": game_session.bonus_active,
            "bonus_spins_remaining": game_session.bonus_spins_remaining if game_session.bonus_active else 0,
            "bonus_multiplier": game_session.bonus_multiplier if game_session.bonus_active else 1.0,
            "user_balance_sats": int(user.balance),
            "session_stats": {
                "num_spins": game_session.num_spins,
                "amount_wagered_sats": int(game_session.amount_wagered or 0),
                "amount_won_sats": int(game_session.amount_won or 0),
            }
        }
    except ValueError as e: # Specific, potentially user-facing errors
        db.session.rollback()
        raise e
    except FileNotFoundError as e: # Config file issues
        db.session.rollback()
        # Log e here
        raise RuntimeError(f"Game configuration error for slot {slot.short_name}: {e}")
    except Exception as e:
        db.session.rollback()
        # Log e here for debugging
        raise RuntimeError(f"An unexpected error occurred during the multiway spin: {str(e)}")

