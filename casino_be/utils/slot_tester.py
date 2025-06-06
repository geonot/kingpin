import argparse
import json
import os
import random
import secrets # May need for mocking parts of spin_handler later
from datetime import datetime, timezone
from casino_be.utils.spin_handler import (
    load_game_config,
    generate_spin_grid,
    calculate_win,
    check_bonus_trigger,
    handle_cascade_fill
)
# We need SlotSymbol for spin_handler functions that expect slot.symbols
from casino_be.models import Slot, SlotSymbol

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("Warning: Numpy not found. Some advanced statistics (e.g., Volatility Index) and some graphs might not be calculated/generated.")

try:
    import matplotlib
    matplotlib.use('Agg') # Use a non-interactive backend suitable for saving files
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: Matplotlib not found. Graphs will not be generated.")


class MockUser:
    def __init__(self, initial_balance_sats):
        self.balance = initial_balance_sats
        self.id = 1 # Dummy ID

    def __repr__(self):
        return f"<MockUser id={self.id} balance={self.balance}>"

class MockGameSession:
    def __init__(self, user_id, slot_id, game_type="slot"):
        self.user_id = user_id
        self.slot_id = slot_id
        self.game_type = game_type
        self.bonus_active = False
        self.bonus_spins_remaining = 0
        self.bonus_multiplier = 1.0
        self.amount_wagered = 0
        self.amount_won = 0
        self.num_spins = 0
        self.session_start = datetime.now(timezone.utc)
        self.id = random.randint(1000, 9999) # Dummy ID

    def __repr__(self):
        return f"<MockGameSession id={self.id} user_id={self.user_id} slot_id={self.slot_id} spins={self.num_spins}>"


class SlotTester:
    def __init__(self, slot_short_name, num_spins, bet_amount_sats):
        self.slot_short_name = slot_short_name
        self.num_spins = num_spins
        self.bet_amount_sats = bet_amount_sats
        self.game_config = None
        self.slot_properties = None # To store properties from the Slot model if needed

        self.mock_user = None
        self.mock_session = None

        # Statistics to be collected
        self.total_bet = 0
        self.total_win = 0
        self.spin_results_data = [] # List to store detailed outcome of each spin if needed
        self.bonus_triggers = 0
        self.total_bonus_win = 0
        # self.wins_in_bonus = 0 # Covered by current_bonus_session_win logic
        # self.wins_in_base = 0 # Can be derived: total_win - total_bonus_win
        self.hit_count = 0

        # New attributes for detailed statistics
        self.bonus_data = [] # To store info about each bonus round (e.g., total win, number of spins)
        self.wins_by_multiplier = {} # To categorize wins by their multiplier of bet amount
        self.rtp_over_time = [] # To track RTP progression
        self.current_bonus_session_win = 0
        self.current_bonus_session_spins = 0 # Spins *within* the current bonus mode
        self.is_in_bonus_previously = False # Tracks if the previous spin was in bonus mode

        # Attributes to store calculated derived statistics
        self.overall_rtp = 0
        self.hit_frequency = 0
        self.bonus_frequency = 0
        self.avg_bonus_win = 0
        self.base_game_rtp_contribution = 0
        self.bonus_rtp_contribution = 0
        self.volatility_index = "N/A"


    def load_configuration(self, test_config_base_path=None): # Add optional arg
        print(f"INFO: Loading configuration for slot: {self.slot_short_name}...")

        # Determine path for game_config
        if test_config_base_path:
            # Construct path relative to the provided base path
            # Ensure test_config_base_path is relative to the repo root if needed, or absolute
            # For this subtask, assume test_config_base_path will be like "casino_be/tests/test_data/slot_tester_configs"
            # and self.slot_short_name is "test_slot1"
            current_script_dir = os.path.dirname(os.path.abspath(__file__))
            repo_root = os.path.abspath(os.path.join(current_script_dir, '..', '..')) # casino_be/utils/ -> casino_be/ -> /
            config_path = os.path.join(repo_root, test_config_base_path, self.slot_short_name, "gameConfig.json")
        else:
            # Original path construction logic: assumes execution from repo root
            # or that casino_fe/public is directly accessible.
            # This needs to be robust. Let's assume casino_fe is at the same level as casino_be.
            current_script_dir = os.path.dirname(os.path.abspath(__file__)) # .../casino_be/utils
            repo_root_guess = os.path.abspath(os.path.join(current_script_dir, '..', '..')) # .../
            config_path = os.path.join(repo_root_guess, "casino_fe", "public", self.slot_short_name, "gameConfig.json")

        if not os.path.exists(config_path):
            print(f"ERROR: Game configuration file not found at {config_path}. Exiting.")
            self.game_config = None
            return False
        try:
            with open(config_path, 'r') as f:
                self.game_config = json.load(f)
        except Exception as e:
            print(f"ERROR: Failed to load or parse gameConfig.json from {config_path}: {e}")
            self.game_config = None
            return False

        if not self.game_config:
            print(f"ERROR: gameConfig.json for {self.slot_short_name} could not be loaded or is empty (path: {config_path}). Exiting.")
            return False

        game_data = self.game_config.get('game', {})
        if not game_data:
            print(f"ERROR: 'game' object not found in gameConfig for {self.slot_short_name}. Exiting.")
            return False

        mock_slot_obj = Slot(
            id=game_data.get('slot_id'),
            name=game_data.get('name'),
            short_name=self.slot_short_name,
            num_rows=game_data.get('layout', {}).get('rows', 3),
            num_columns=game_data.get('layout', {}).get('columns', 5),
            wild_symbol_id=game_data.get('symbol_wild'),
            scatter_symbol_id=game_data.get('symbol_scatter'),
            is_cascading=game_data.get('is_cascading', False),
            cascade_type=game_data.get('cascade_type'),
            min_symbols_to_match=game_data.get('min_symbols_to_match'),
            win_multipliers=game_data.get('win_multipliers', [])
        )

        mock_slot_obj.symbols = []
        cfg_symbols_list = game_data.get('symbols', [])
        if not cfg_symbols_list:
             print(f"Warning: No symbols found in game_config for {self.slot_short_name}. Spin generation might fail.")

        for sym_data in cfg_symbols_list:
            mock_sym = SlotSymbol(
                slot_id=mock_slot_obj.id,
                symbol_internal_id=sym_data['id'],
                name=sym_data['name'],
                value_multiplier=float(sym_data.get('value', 0.0)) if sym_data.get('value') is not None else 0.0,
                img_link=""
            )
            mock_slot_obj.symbols.append(mock_sym)

        self.slot_properties = mock_slot_obj

        print(f"INFO: Successfully loaded configuration for {self.slot_properties.name}.")
        print(f"INFO: Slot is_cascading: {self.slot_properties.is_cascading}")
        return True

    def initialize_simulation_state(self):
        # Initialize mock user and session
        # For now, start with a large enough balance to cover all spins.
        # This might be adjusted later if we want to test insufficient balance scenarios.
        initial_balance = self.num_spins * self.bet_amount_sats * 10 # Ample balance
        self.mock_user = MockUser(initial_balance_sats=initial_balance)

        # Assuming game_config is loaded and has slot_id
        slot_db_id = self.game_config.get("game", {}).get("slot_id", 0) # Default to 0 if not found
        self.mock_session = MockGameSession(user_id=self.mock_user.id, slot_id=slot_db_id)

        print(f"INFO: Initialized simulation state: User Balance={self.mock_user.balance}, Session Spins={self.mock_session.num_spins}")


    def run_simulation(self):
        if not self.game_config or not self.slot_properties:
            print("ERROR: Game configuration or slot properties not loaded. Cannot run simulation.")
            return

        print(f"INFO: Starting simulation for {self.slot_short_name} with {self.num_spins} spins at {self.bet_amount_sats} sats per spin.")

        # --- This is where the main simulation loop will go (Step 4) ---
        # For now, just a placeholder print
        print("INFO: [Placeholder] Simulation loop will be implemented in a later step.")
        for i in range(self.num_spins):
            spin_data = self._simulate_one_spin()
            if spin_data is None: # Indicates an error during spin simulation
                print(f"ERROR: Halting simulation due to error in _simulate_one_spin for spin {i+1}.")
                break
            self._collect_spin_statistics(spin_data) # Will be implemented in Step 5
            if (i + 1) % (self.num_spins // 20 or 1) == 0: # Print progress roughly 20 times
                print(f"INFO: Completed {i+1}/{self.num_spins} spins...")

        print(f"INFO: Simulation finished for {self.slot_short_name}.")

    def _simulate_one_spin(self):
        user = self.mock_user
        slot = self.slot_properties # This is our mock Slot object
        game_session = self.mock_session
        bet_amount_sats = self.bet_amount_sats
        game_config = self.game_config

        # Extract necessary configurations from game_config
        game_data = game_config.get('game', {})
        cfg_layout = game_data.get('layout', {})
        cfg_symbols_list = game_data.get('symbols', []) # List of symbol dicts from config
        cfg_symbols_map = {s_cfg['id']: s_cfg for s_cfg in cfg_symbols_list}

        cfg_paylines = game_data.get('paylines', []) # Ensure this key exists or provide default
        if not cfg_paylines: # Older configs might have paylines under layout
            cfg_paylines = cfg_layout.get('paylines', [])


        cfg_rows = slot.num_rows
        cfg_columns = slot.num_columns
        cfg_wild_symbol_id = slot.wild_symbol_id
        cfg_scatter_symbol_id = slot.scatter_symbol_id
        cfg_bonus_features = game_data.get('bonus_features', {}) # Ensure this exists or provide default

        cfg_is_cascading = slot.is_cascading
        cfg_cascade_type = slot.cascade_type
        cfg_min_symbols_to_match = slot.min_symbols_to_match
        cfg_win_multipliers = slot.win_multipliers
        cfg_reel_strips = game_data.get('reel_strips')

        # Betting Logic (Simplified)
        is_bonus_spin = False
        current_spin_multiplier = 1.0
        actual_bet_this_spin = 0

        if game_session.bonus_active and game_session.bonus_spins_remaining > 0:
            is_bonus_spin = True
            actual_bet_this_spin = 0 # Free spin
            current_spin_multiplier = game_session.bonus_multiplier
            game_session.bonus_spins_remaining -= 1
        else:
            is_bonus_spin = False
            actual_bet_this_spin = bet_amount_sats
            current_spin_multiplier = 1.0
            if user.balance < actual_bet_this_spin:
                print("Warning: Mock user has insufficient balance. Stopping simulation.")
                # This case should ideally be handled or decided if it's a test scenario
                return None # Stop simulation if balance runs out
            user.balance -= actual_bet_this_spin

        # Generate Spin Grid
        if not slot.symbols:
            print("ERROR: No symbols loaded into slot_properties.symbols. Cannot generate grid.")
            return None

        spin_result_grid = generate_spin_grid(
            cfg_rows,
            cfg_columns,
            slot.symbols,
            cfg_wild_symbol_id,
            cfg_scatter_symbol_id,
            cfg_symbols_map,
            cfg_reel_strips
        )
        initial_spin_grid_for_record = [row[:] for row in spin_result_grid] # Deep copy

        # Calculate Wins (Initial + Cascades)
        bet_for_calc_win = actual_bet_this_spin if not is_bonus_spin else bet_amount_sats

        win_info = calculate_win(
            spin_result_grid,
            cfg_paylines,
            cfg_symbols_map,
            bet_for_calc_win, # Base win calculation on original bet for bonus spins too
            cfg_wild_symbol_id,
            cfg_scatter_symbol_id,
            game_data.get('payouts', []),
            cfg_min_symbols_to_match
        )
        initial_raw_win_sats = win_info['total_win_sats']
        winning_lines = win_info['winning_lines']
        current_winning_coords = win_info['winning_symbol_coords']

        total_win_for_entire_spin_sequence = initial_raw_win_sats

        if cfg_is_cascading and initial_raw_win_sats > 0 and current_winning_coords:
            cascade_level_counter = 0
            current_raw_win_for_cascade_loop = initial_raw_win_sats

            while current_raw_win_for_cascade_loop > 0 and current_winning_coords:
                current_grid_state = handle_cascade_fill(
                    spin_result_grid, # Pass the current grid state
                    current_winning_coords,
                    cfg_cascade_type,
                    slot.symbols,
                    cfg_symbols_map,
                    cfg_wild_symbol_id,
                    cfg_scatter_symbol_id
                )
                spin_result_grid = current_grid_state # Update grid for next cascade or final result

                cascade_win_info = calculate_win(
                    current_grid_state,
                    cfg_paylines,
                    cfg_symbols_map,
                    actual_bet_this_spin if not is_bonus_spin else bet_amount_sats,
                    cfg_wild_symbol_id,
                    cfg_scatter_symbol_id,
                    game_data.get('payouts', []),
                    cfg_min_symbols_to_match
                )
                new_raw_win_this_cascade = cascade_win_info['total_win_sats']
                current_winning_coords = cascade_win_info['winning_symbol_coords']

                if new_raw_win_this_cascade > 0:
                    cascade_level_counter += 1
                    current_cascade_multiplier_val = 1.0
                    if cfg_win_multipliers:
                        if cascade_level_counter -1 < len(cfg_win_multipliers):
                            current_cascade_multiplier_val = cfg_win_multipliers[cascade_level_counter - 1]
                        elif cfg_win_multipliers:
                            current_cascade_multiplier_val = cfg_win_multipliers[-1]

                    total_win_for_entire_spin_sequence += int(new_raw_win_this_cascade * current_cascade_multiplier_val)
                    current_raw_win_for_cascade_loop = new_raw_win_this_cascade
                    # winning_lines.extend(cascade_win_info['winning_lines']) # Optional: accumulate all lines
                else:
                    current_raw_win_for_cascade_loop = 0
                    current_winning_coords = []

        final_win_amount_for_session = total_win_for_entire_spin_sequence
        if is_bonus_spin and current_spin_multiplier > 1.0:
            final_win_amount_for_session = int(total_win_for_entire_spin_sequence * current_spin_multiplier)

        # Bonus Trigger
        bonus_triggered_this_spin = False
        if not is_bonus_spin: # Bonus can only be triggered on a normal spin
            # Default bonus features if not in config (spin_handler might do this, replicate here for safety)
            # cfg_bonus_features = game_data.get('bonus_features', {}) # already fetched

            bonus_trigger_info = check_bonus_trigger(
                initial_spin_grid_for_record,
                cfg_scatter_symbol_id, # Ensure this is the correct scatter ID from game_config
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
                    # Optionally update multiplier on re-trigger based on game rules
                    # game_session.bonus_multiplier = new_bonus_multiplier

        if game_session.bonus_active and game_session.bonus_spins_remaining <= 0:
            game_session.bonus_active = False
            game_session.bonus_multiplier = 1.0 # Reset

        # Update Mock Balances/Session
        user.balance += final_win_amount_for_session
        game_session.num_spins += 1
        if not is_bonus_spin:
            game_session.amount_wagered += actual_bet_this_spin
        game_session.amount_won += final_win_amount_for_session


        return {
            "spin_result": initial_spin_grid_for_record,
            "win_amount_sats": int(final_win_amount_for_session),
            "winning_lines": winning_lines,
            "bonus_triggered": bonus_triggered_this_spin,
            "bonus_active": game_session.bonus_active,
            "bonus_spins_remaining": game_session.bonus_spins_remaining if game_session.bonus_active else 0,
            "bonus_multiplier": game_session.bonus_multiplier if game_session.bonus_active else 1.0,
            "user_balance_sats": int(user.balance),
            "session_stats": {
                "num_spins": game_session.num_spins,
                "amount_wagered_sats": int(game_session.amount_wagered),
                "amount_won_sats": int(game_session.amount_won),
            },
            "is_bonus_spin": is_bonus_spin,
            "actual_bet_this_spin": actual_bet_this_spin
        }

    def _collect_spin_statistics(self, spin_data):
        self.total_bet += spin_data['actual_bet_this_spin']
        self.total_win += spin_data['win_amount_sats']

        if spin_data['win_amount_sats'] > 0:
            self.hit_count += 1

        # Bonus Tracking
        if spin_data['bonus_active']:
            self.current_bonus_session_win += spin_data['win_amount_sats']
            if spin_data['is_bonus_spin']: # Only count spins that occurred *during* the bonus mode
                self.current_bonus_session_spins += 1

            # Check for main bonus trigger (not re-triggers within an active bonus)
            if spin_data['bonus_triggered'] and not self.is_in_bonus_previously:
                self.bonus_triggers += 1

        elif not spin_data['bonus_active'] and self.is_in_bonus_previously:
            # Bonus session just ended
            if self.current_bonus_session_spins > 0 or self.current_bonus_session_win > 0: # Ensure it was a valid bonus session
                self.bonus_data.append({
                    'total_win': self.current_bonus_session_win,
                    'num_spins': self.current_bonus_session_spins,
                    # Approximate trigger spin number relative to the start of this bonus.
                    # More accurate tracking might require passing total spins count into bonus_data.
                    'trigger_spin_number': self.mock_session.num_spins - self.current_bonus_session_spins
                })
                self.total_bonus_win += self.current_bonus_session_win

            # Reset for the next potential bonus session
            self.current_bonus_session_win = 0
            self.current_bonus_session_spins = 0

        self.is_in_bonus_previously = spin_data['bonus_active']

        # Win Multiplier Categorization
        if spin_data['win_amount_sats'] > 0 and spin_data['actual_bet_this_spin'] > 0:
            # Calculate multiplier based on the actual bet for that spin (could be 0 for bonus spins)
            # For categorization, we usually care about multipliers on *paid* spins.
            multiplier_category = round(spin_data['win_amount_sats'] / spin_data['actual_bet_this_spin'])
            self.wins_by_multiplier[multiplier_category] = self.wins_by_multiplier.get(multiplier_category, 0) + 1
        elif spin_data['win_amount_sats'] == 0:
            # This counts spins with zero win (including paid spins that lost, and potentially free spins with no win)
            self.wins_by_multiplier[0] = self.wins_by_multiplier.get(0, 0) + 1
        # Note: Free spins that win will be categorized based on their win amount relative to the original bet that triggered them,
        # if actual_bet_this_spin is passed as the original bet amount during free spins.
        # The current _simulate_one_spin passes actual_bet_this_spin as 0 for bonus spins when calculating win_info,
        # but then uses bet_amount_sats (original bet) for win calculation.
        # For multiplier categorization, it's more consistent to use the original bet that triggered the bonus,
        # or the standard bet_amount_sats if we consider bonus wins relative to the standard play cost.
        # Let's adjust to use self.bet_amount_sats for categorization if actual_bet_this_spin is 0 but there's a win (bonus spin win)
        elif spin_data['win_amount_sats'] > 0 and spin_data['actual_bet_this_spin'] == 0 and self.bet_amount_sats > 0 : # Bonus spin win
             multiplier_category = round(spin_data['win_amount_sats'] / self.bet_amount_sats)
             self.wins_by_multiplier[multiplier_category] = self.wins_by_multiplier.get(multiplier_category, 0) + 1


        self.spin_results_data.append(spin_data)

    def calculate_derived_statistics(self):
        if self.num_spins == 0:
            print("Warning: No spins were simulated. Cannot calculate derived statistics.")
            return

        self.overall_rtp = (self.total_win / self.total_bet) * 100 if self.total_bet > 0 else 0
        self.hit_frequency = (self.hit_count / self.num_spins) * 100 if self.num_spins > 0 else 0
        self.bonus_frequency = (self.bonus_triggers / self.num_spins) * 100 if self.num_spins > 0 else 0

        # Ensure all bonus sessions are accounted for, even if the last one was active at sim end
        if self.is_in_bonus_previously and (self.current_bonus_session_spins > 0 or self.current_bonus_session_win > 0):
            self.bonus_data.append({
                'total_win': self.current_bonus_session_win,
                'num_spins': self.current_bonus_session_spins,
                'trigger_spin_number': self.mock_session.num_spins - self.current_bonus_session_spins
            })
            self.total_bonus_win += self.current_bonus_session_win
            # Reset them after adding to bonus_data, though not strictly necessary here as it's end of sim
            self.current_bonus_session_win = 0
            self.current_bonus_session_spins = 0
            self.is_in_bonus_previously = False # Explicitly mark as ended for clarity

        self.avg_bonus_win = (self.total_bonus_win / self.bonus_triggers) if self.bonus_triggers > 0 else 0

        base_game_win = self.total_win - self.total_bonus_win
        self.base_game_rtp_contribution = (base_game_win / self.total_bet) * 100 if self.total_bet > 0 else 0
        self.bonus_rtp_contribution = (self.total_bonus_win / self.total_bet) * 100 if self.total_bet > 0 else 0

        # Volatility Index
        wins_per_spin = [s['win_amount_sats'] for s in self.spin_results_data]
        if NUMPY_AVAILABLE and wins_per_spin:
            std_dev_wins = np.std(wins_per_spin)
            # mean_win = np.mean(wins_per_spin) # Not directly used in this version of VI
            self.volatility_index = std_dev_wins / self.bet_amount_sats if self.bet_amount_sats > 0 else 0
        else:
            self.volatility_index = "N/A (Numpy not installed or no wins)" if not NUMPY_AVAILABLE else "N/A (No wins)"


        # RTP Over Time
        cumulative_win = 0
        cumulative_bet = 0
        self.rtp_over_time = [] # Clear previous calculations if any
        for i, spin_res in enumerate(self.spin_results_data):
            cumulative_win += spin_res['win_amount_sats']
            # actual_bet_this_spin should be used as it accounts for free spins (bet=0)
            cumulative_bet += spin_res['actual_bet_this_spin']

            # Calculate RTP at intervals (e.g., every 10% of spins or specific number of spins)
            # For smoother graph, can calculate more frequently, e.g. every 100 or 1000 spins
            interval = self.num_spins // 20 or 1 # Aim for ~20 data points for the graph
            if (i + 1) % interval == 0 or (i + 1) == self.num_spins : # Ensure last point is captured
                current_rtp = (cumulative_win / cumulative_bet) * 100 if cumulative_bet > 0 else 0
                self.rtp_over_time.append({'spin_count': i + 1, 'rtp': current_rtp})


    def print_summary_statistics(self):
        # Ensure derived statistics are calculated before printing
        # self.calculate_derived_statistics() # This is called at the end of run_simulation

        print("\n--- Simulation Summary ---")
        slot_name_display = self.slot_properties.name if self.slot_properties and self.slot_properties.name else self.slot_short_name
        print(f"Slot Game: {slot_name_display}")
        print(f"Total Spins Simulated: {self.num_spins}")
        print(f"Bet Amount Per Spin: {self.bet_amount_sats} sats")
        print(f"Total Wagered: {self.total_bet} sats")
        print(f"Total Won: {self.total_win} sats")

        print("\n--- Detailed Metrics ---")
        target_rtp_display = f"{self.slot_properties.rtp:.2f}%" if self.slot_properties and hasattr(self.slot_properties, 'rtp') and self.slot_properties.rtp is not None else "N/A"
        print(f"Overall RTP: {self.overall_rtp:.2f}% (Target: {target_rtp_display})")
        print(f"Hit Frequency: {self.hit_frequency:.2f}% ({self.hit_count} wins out of {self.num_spins} spins)")
        print(f"Bonus Trigger Frequency: {self.bonus_frequency:.2f}% ({self.bonus_triggers} triggers in {self.num_spins} spins)")

        avg_bonus_spins = 0
        if self.bonus_triggers > 0:
            total_spins_in_bonus_mode = sum(b['num_spins'] for b in self.bonus_data)
            avg_bonus_spins = total_spins_in_bonus_mode / self.bonus_triggers

        print(f"Average Bonus Win: {self.avg_bonus_win:.2f} sats (Total from bonuses: {self.total_bonus_win} sats from {self.bonus_triggers} triggers)")
        print(f"Average Spins in Bonus: {avg_bonus_spins:.2f} spins")

        print(f"Base Game RTP Contribution: {self.base_game_rtp_contribution:.2f}%")
        print(f"Bonus Game RTP Contribution: {self.bonus_rtp_contribution:.2f}%")

        volatility_display = self.volatility_index if isinstance(self.volatility_index, str) else f'{self.volatility_index:.2f}'
        print(f"Volatility Index (Win StdDev / Bet): {volatility_display}")

        print("\nWin Distribution (by Bet Multiplier):")
        if self.wins_by_multiplier:
            # Sort by multiplier for readability
            for mult, count in sorted(self.wins_by_multiplier.items()):
                percentage_of_total_spins = (count / self.num_spins) * 100 if self.num_spins > 0 else 0
                print(f"  {mult}x Bet: {count} times ({percentage_of_total_spins:.2f}%)")
        else:
            print("  No win data to display for multiplier distribution.")

        # Optionally print RTP over time data points for debugging or detailed reports
        # print("\nRTP Over Time (last 10 points):")
        # for rtp_point in self.rtp_over_time[-10:]: # Print last 10 points as an example
        #     print(f"  Spins: {rtp_point['spin_count']}, RTP: {rtp_point['rtp']:.2f}%")


    def generate_graphs(self):
        if not MATPLOTLIB_AVAILABLE:
            print("INFO: Matplotlib not available, skipping graph generation.")
            return

        graph_dir = "slot_tester_graphs"
        os.makedirs(graph_dir, exist_ok=True)

        slot_name_for_file = self.slot_short_name.replace("/", "_") # Sanitize for filename
        slot_display_name = self.slot_properties.name if self.slot_properties and self.slot_properties.name else self.slot_short_name


        # Graph 1: Histogram of Win Multipliers
        if self.wins_by_multiplier:
            multipliers = sorted(self.wins_by_multiplier.keys())
            counts = [self.wins_by_multiplier[m] for m in multipliers]

            plt.figure(figsize=(12, 7))
            plt.bar([str(m) + 'x' for m in multipliers], counts, color='skyblue', width=0.8)
            plt.title(f"Win Multiplier Distribution for {slot_display_name}", fontsize=16)
            plt.xlabel("Bet Multiplier", fontsize=12)
            plt.ylabel("Frequency", fontsize=12)
            plt.xticks(rotation=45, ha="right", fontsize=10)
            plt.yticks(fontsize=10)
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            plt.tight_layout()
            graph_file_path = os.path.join(graph_dir, f"{slot_name_for_file}_win_multipliers.png")
            try:
                plt.savefig(graph_file_path)
                print(f"INFO: Saved win multiplier distribution graph to {graph_file_path}")
            except Exception as e:
                print(f"ERROR: Failed to save win multiplier graph: {e}")
            plt.clf()
        else:
            print("INFO: No win multiplier data to generate graph.")

        # Graph 2: RTP Convergence Over Time
        if self.rtp_over_time:
            spin_counts = [d['spin_count'] for d in self.rtp_over_time]
            rtps = [d['rtp'] for d in self.rtp_over_time]

            plt.figure(figsize=(10, 6))
            plt.plot(spin_counts, rtps, label="Simulated RTP", marker='.', linestyle='-')

            target_rtp_value = None
            if self.slot_properties and hasattr(self.slot_properties, 'rtp') and self.slot_properties.rtp is not None:
                target_rtp_value = self.slot_properties.rtp

            if target_rtp_value is not None:
                plt.axhline(y=target_rtp_value, color='r', linestyle='--', label=f"Target RTP ({target_rtp_value:.2f}%)")

            plt.title(f"RTP Convergence for {slot_display_name}", fontsize=16)
            plt.xlabel("Number of Spins", fontsize=12)
            plt.ylabel("RTP (%)", fontsize=12)
            plt.legend(fontsize=10)
            plt.grid(True, linestyle='--', alpha=0.7)
            plt.tight_layout()
            graph_file_path = os.path.join(graph_dir, f"{slot_name_for_file}_rtp_convergence.png")
            try:
                plt.savefig(graph_file_path)
                print(f"INFO: Saved RTP convergence graph to {graph_file_path}")
            except Exception as e:
                print(f"ERROR: Failed to save RTP convergence graph: {e}")
            plt.clf()
        else:
            print("INFO: No RTP over time data to generate graph.")

        # Graph 3: Pie Chart of Win Contributions (Base Game vs. Bonus Game)
        if self.total_win > 0 : # Only make sense if there are any wins
            base_wins = self.total_win - self.total_bonus_win
            bonus_wins = self.total_bonus_win

            labels = 'Base Game Wins', 'Bonus Game Wins'
            sizes = [base_wins, bonus_wins]
            colors = ['lightcoral', 'lightskyblue']
            explode = (0, 0.1) if bonus_wins > 0 else (0,0) # Explode bonus slice if it exists

            if base_wins > 0 or bonus_wins > 0: # Ensure there's something to plot
                plt.figure(figsize=(8, 8))
                plt.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%', shadow=True, startangle=90)
                plt.title(f"Win Contribution (Base vs Bonus)\nfor {slot_display_name}", fontsize=16)
                plt.axis('equal') # Equal aspect ratio ensures that pie is drawn as a circle.
                plt.tight_layout()
                graph_file_path = os.path.join(graph_dir, f"{slot_name_for_file}_win_contributions.png")
                try:
                    plt.savefig(graph_file_path)
                    print(f"INFO: Saved win contribution pie chart to {graph_file_path}")
                except Exception as e:
                    print(f"ERROR: Failed to save win contribution pie chart: {e}")
                plt.clf()
            else:
                print("INFO: No wins recorded, skipping win contribution pie chart.")
        else:
            print("INFO: Total win is zero, skipping win contribution pie chart.")

        # Graph 4: Histogram of Bonus Round Wins
        if self.bonus_data:
            bonus_round_wins = [b['total_win'] for b in self.bonus_data if b['total_win'] > 0]
            if bonus_round_wins:
                plt.figure(figsize=(10, 6))
                plt.hist(bonus_round_wins, bins=max(10, len(set(bonus_round_wins)) // 2 or 1), color='gold', edgecolor='black') # Adjust bins
                plt.title(f"Bonus Round Win Distribution for {slot_display_name}", fontsize=16)
                plt.xlabel("Win Amount in Bonus Round (sats)", fontsize=12)
                plt.ylabel("Frequency of Bonus Rounds", fontsize=12)
                plt.grid(axis='y', linestyle='--', alpha=0.7)
                plt.tight_layout()
                graph_file_path = os.path.join(graph_dir, f"{slot_name_for_file}_bonus_win_distribution.png")
                try:
                    plt.savefig(graph_file_path)
                    print(f"INFO: Saved bonus win distribution graph to {graph_file_path}")
                except Exception as e:
                    print(f"ERROR: Failed to save bonus win distribution graph: {e}")
                plt.clf()
            else:
                print("INFO: No bonus rounds with wins > 0 to generate distribution graph.")
        else:
            print("INFO: No bonus data to generate bonus win distribution graph.")

        plt.close('all') # Close all figures to free memory


def main():
    parser = argparse.ArgumentParser(description="Slot Machine Tester - Simulates slot play to analyze RTP and other metrics.")
    parser.add_argument("slot_short_name", type=str, help="The short_name of the slot to test (must match a directory in casino_fe/public/).")
    parser.add_argument("--num_spins", type=int, default=10000, help="Number of spins to simulate.")
    parser.add_argument("--bet_amount", type=int, default=100, help="Bet amount in satoshis for each spin.")
    # parser.add_argument("--config_path", type=str, default="casino_fe/public", help="Path to the directory containing slot configurations.") # If needed

    args = parser.parse_args()

    print(f"--- Initializing Slot Tester for: {args.slot_short_name} ---")

    tester = SlotTester(
        slot_short_name=args.slot_short_name,
        num_spins=args.num_spins,
        bet_amount_sats=args.bet_amount
    )

    if tester.load_configuration():
        tester.initialize_simulation_state()
        tester.run_simulation() # Will call placeholder methods for now
        tester.print_summary_statistics() # Will print placeholder stats
        tester.generate_graphs() # Will call placeholder method

    print(f"--- Slot Tester run finished for: {args.slot_short_name} ---")

if __name__ == "__main__":
    main()
