import hmac
import hashlib
import math
import os
from datetime import datetime, timezone

from casino_be.models import db, SpacecrashGame, SpacecrashBet, User # Assuming models are in casino_be.models
# If your app instance 'app' is needed for config, you might need to import it or pass config values.
# from casino_be.app import app # Or from casino_be.config import Config

MAX_MULTIPLIER_CAP = 9999.00  # Default cap, can be overridden by param

def get_multiplier_from_hash(game_hash_hex_string: str, house_edge: float = 0.01, max_multiplier_cap_param: float = MAX_MULTIPLIER_CAP) -> float:
    """
    Calculates a crash multiplier based on a hexadecimal game hash string,
    simulating a Bustabit-like probability distribution.
    A portion of outcomes result in an instant crash (1.00x).
    """
    if not (0 <= house_edge < 1):
        raise ValueError("House edge must be between 0 (inclusive) and 1 (exclusive).")

    # 1. Calculate E (target average for non-instant bust outcomes)
    # The formula aims for an average payout if there were no instant busts.
    # To achieve a target house edge, the distribution is skewed.
    # For 1% house edge, if game played 100 times, house expects to keep 1 unit.
    # This means total payout should be 99 units for 100 units wagered.
    # The probability of an instant bust (1.00x) is house_edge. (e.g., 1%)
    # Let P_instant_bust = house_edge
    # The remaining (1 - P_instant_bust) probability mass is distributed for multipliers > 1.00x

    # The Bustabit formula for crash point calculation from a hash:
    # E = 100 / (1-house_edge) is not directly used in the simplified probability distribution.
    # Instead, we'll use a direct probability for instant bust.

    # Probability of instant bust (1.00x)
    # Example: if house_edge is 0.01 (1%), then 1 out of 100 numbers (e.g., 0) will result in 1.00x
    # We can use a modulus operation for this. Let's use 10000 possible outcomes for more granularity.
    # Number of outcomes for instant bust = house_edge * 10000
    
    # Using the provided formula structure:
    # E_target = 100 / (1 - house_edge) # This represents the point where payout is 100% if not instant bust
                                     # Example: house_edge = 0.01 => E_target = 100 / 0.99 = 101.0101...
                                     # This implies that on average, for non-instant busts, the multiplier will be around this.
    
    # The actual Bustabit formula seems to be:
    # If divisible by (1 / house_edge_percent), then bust at 1.00x.
    # Example: house_edge = 0.01 (1%). Divisible by 100 -> instant bust.
    # Otherwise, multiplier = floor( (100 * E - H % E) / (E - H % E) ) / 100
    # where E = 1/(1-house_edge_percent) and H is part of the hash.
    # This is complex. Let's use the one from the prompt:
    # "1% instant bust, remaining distribution adjusted"
    # If H % (1/house_edge) == 0, then 1.00x.
    # Otherwise, multiplier = floor( (100 * (1/house_edge) - (H % (1/house_edge))) / ( (1/house_edge) - (H % (1/house_edge)) ) ) / 100
    # This seems to be a misunderstanding of the formula from my side.

    # Re-evaluating the formula:
    # If H % (1/P_INSTANT_BUST) == 0 -> 1.00x
    # P_INSTANT_BUST = house_edge (e.g. 0.01)
    # So, if H % (1/0.01) == H % 100 == 0, then 1.00x.

    # For the other outcomes:
    # Multiplier M = floor(100 * E_prime / (E_prime - X)) / 100
    # where E_prime is related to the edge without instant bust, and X is derived from hash.
    # Let's use the formula that seems most standard for provably fair games:
    # 1. Convert hex hash to integer. Use first 13 chars (52 bits) for precision.
    game_hash_int = int(game_hash_hex_string[:13], 16)
    
    # 2. Determine if it's an instant crash (e.g., 1% of the time)
    # Using a common method: if hash divisible by X results in instant crash.
    # Let's use 1 / house_edge as the divisor.
    # For house_edge = 0.01, divisor = 100.
    # If game_hash_int % 100 == 0, it's an instant 1.00x crash.
    if house_edge > 0 and game_hash_int % int(1 / house_edge) == 0:
        return 1.00

    # 3. Calculate the multiplier for non-instant crash outcomes.
    # The formula: E = 2^52 (max value for 52 bits)
    # Multiplier = floor( (E * (1 - house_edge_for_non_instant) - game_hash_int) / (E - game_hash_int) ) / 100
    # This needs careful derivation to ensure fairness and correct distribution.
    
    # A widely cited formula for provably fair crash point generation is:
    # r = game_hash_int / (2**52)  (random number between 0 and 1)
    # crash_point = floor( (1 - r) / (1 - (1 - house_edge) * r) * 100) / 100
    # This formula needs to be analyzed for its distribution properties.
    # It seems simpler:
    # crash = (MAX_HASH_VALUE * 100) / (MAX_HASH_VALUE - game_hash_int) / (1 - house_edge)
    
    # Let's use the one from a known implementation if possible or stick to the prompt's spirit.
    # The prompt mentioned: "1% instant bust, remaining distribution adjusted."
    # And "E = 100 / (1 - house_edge)" then "If H % E == 0, then crash point is 1.00"
    # This implies E should be an integer for H % E.
    # If E = 100 / (1-0.01) = 101.01, this is not an integer.

    # Let's use a clearer, common approach for provably fair crash:
    # 1. Instant bust probability: `house_edge`.
    #    If a random number `r` (0-1) is less than `house_edge`, then 1.00x.
    #    (This part is covered by the `game_hash_int % int(1/house_edge) == 0` for discrete cases)

    # 2. For other cases, distribute multipliers.
    #    A common formula: `multiplier = (1 - house_edge) / (1 - r)` where r is a uniform random number [0,1).
    #    `r` can be `game_hash_int / (2**52)`.
    #    Ensure `r` is not too close to 1 to prevent extreme multipliers if not capped.
    
    # Max value for 52 bits (13 hex chars)
    MAX_52_BIT_HASH = 2**52 -1 
    # Ensure hash_int is within this range effectively if it came from a longer hash
    # game_hash_int = game_hash_int % (2**52) # Not needed if we only take 13 chars

    # Generate a float between 0 (inclusive) and 1 (exclusive)
    # To avoid multiplier being infinite if game_hash_int is exactly MAX_52_BIT_HASH
    if game_hash_int == MAX_52_BIT_HASH:
        game_hash_int -=1 # or handle this edge case to ensure r < 1

    r = game_hash_int / (2**52) # float [0, 1)

    # Calculate multiplier using the formula that distributes the remaining probability
    # Multiplier M = (1-P_house_keeps_overall) / (1-r)
    # P_house_keeps_overall is house_edge.
    # So, M = (1 - house_edge) / (1 - r)
    # This formula generates multipliers starting from (1-house_edge) up to infinity.
    # We want multipliers starting from 1.00x.
    
    # Let's use the standard Bustabit formula more directly:
    # Source: https://github.com/BLAKE2/BLAKE2/issues/20 (discussion on Bustabit's algorithm)
    # And various provably fair explanations.
    # Simplified:
    # 1. Take first 52 bits of hash as `h`.
    # 2. If `h % (1 / house_edge)` is 0 (e.g. `h % 100 == 0` for 1% HE), crash = 1.00x.
    # 3. Else, crash = floor( ( (100 * (1/house_edge) - h) / ((1/house_edge) - h) ) * 100) / 100 -- this seems overly complex.
    # Alternative: `crash = floor( ((100 * E_val - H_val) / (E_val - H_val)) ) / 100` where E_val is 2^52 and H_val is hash_int
    # This leads to `floor( (100 * 2^52 - hash_int) / (2^52 - hash_int) ) / 100` which simplifies to `floor(100 * (1 + hash_int / (2^52 - hash_int))) / 100` (approx)
    # This formula is `( (2^52 * 100 - hash_int) / (2^52 - hash_int) ) / 100`
    # = `( (2^52 * 99 + (2^52 - hash_int) ) / (2^52 - hash_int) ) / 100`
    # = `( 99 * 2^52 / (2^52 - hash_int) + 1 ) / 100` -- still not quite right.

    # The formula is often cited as:
    # crash_point = ( (100 - house_edge_percent) * MAX_HASH_VALUE ) / (MAX_HASH_VALUE - game_hash_int)
    # And then take floor(crash_point) / 100.
    # house_edge_percent = house_edge * 100 (e.g. 1 for 1% HE)
    
    # Let's use the formula from the prompt's structure:
    # If H % E_divisor == 0, then 1.00x. (E_divisor = 1/house_edge)
    # Otherwise, multiplier = floor(E_target * 100 / (E_target - (H % E_target_for_calc))) / 100
    # This is still confusing.

    # Let's use a clear, verifiable method for provably fair crash point generation:
    # h = int value from 52 bits of hash
    # If h % (1/house_edge) == 0 (e.g. 1 out of 100 for 1% HE), crash = 1.00x.
    # This provides the house edge via instant busts.
    # For all other cases, we want the game to be "fair" (0% house edge for this part).
    # So, for the 99% of cases (if HE=1%), multiplier = (MAX_HASH_VALUE * 100) / (MAX_HASH_VALUE - h_adjusted)
    # h_adjusted would be the hash value within the non-instant-bust range.
    
    # Simpler:
    # Use the first 4 bytes (32 bits) of the hash for the "instant bust" check to keep it separate.
    # And the next 52 bits for the actual multiplier calculation if not an instant bust.
    # Or, use the same hash_int for both.
    
    # Sticking to the most common interpretation of Bustabit's formula:
    # 1. Instant bust check (1% of cases for 1% HE)
    #    This is often represented by `h % 100 == 0` (if using integer 0-9999 from hash).
    #    Or, if using 52 bits, `game_hash_int % 100 == 0` (if house_edge is 0.01).
    #    This means 1 in 100 outcomes is an instant bust.
    
    if house_edge > 0:
        # Example: if house_edge = 0.01, then divisor = 100.
        # If game_hash_int is, say, 1234567800, then 1234567800 % 100 == 0.
        divisor = int(1.0 / house_edge)
        if game_hash_int % divisor == 0:
            return 1.00

    # 2. For other cases (99% if HE=0.01), calculate growth.
    #    The formula is: multiplier = (MAX_HASH_VALUE_RANGE * payout_percentage_for_these_cases) / (MAX_HASH_VALUE_RANGE - value_from_hash_in_range)
    #    Payout percentage for these cases should be 100% to make the math simple.
    #    So, multiplier = MAX_HASH_VALUE_RANGE / (MAX_HASH_VALUE_RANGE - value_from_hash_in_range)
    #    This means we scale `game_hash_int` to be within the range of non-instant bust outcomes.
    
    # A widely accepted formula for provably fair crash point:
    # `max_possible_result = 2**52` (number of possible outcomes from 52 bits)
    # `result = game_hash_int`
    # `multiplier = math.floor( (max_possible_result * (1 - house_edge) * 100) / (max_possible_result - result) ) / 100`
    # This formula includes house edge directly. Let's test its properties.
    # If result is 0, multiplier = (1-HE)*100. This is not 1.00x.
    # If result is close to max_possible_result, multiplier becomes very large.

    # Let's use the direct formula that is often cited:
    # `r = game_hash_int / (2**52)` (a float from 0 to nearly 1)
    # `crash_point = (1 - house_edge) / (1 - r)`
    # This value is then typically floored to two decimal places.
    
    # Ensure r is not 1 (if game_hash_int could be 2**52)
    # Our game_hash_int is from 13 hex chars, so max is 2**52 - 1. So r is always < 1.
    r_float = game_hash_int / (2**52)

    # Multiplier calculation for the non-instant bust cases.
    # The house edge is already taken out by the 1% instant bust cases.
    # So, these remaining 99% of cases should average out fairly around some target.
    # The formula is often: `1 / (1-r_float)` for a fair game (0% HE).
    # Then apply house edge on top or via the instant bust.
    
    # If we use the instant bust for the entire house edge:
    multiplier = 1 / (1 - r_float) # This gives a "fair" distribution from 1.0 upwards
    
    # We need to floor to 2 decimal places
    multiplier_scaled = math.floor(multiplier * 100) / 100
    
    return min(multiplier_scaled, max_multiplier_cap_param)


def generate_server_seed() -> str:
    return os.urandom(32).hex()

def generate_crash_point(server_seed_hex: str, client_seed_hex: str, nonce: int, house_edge: float = 0.01) -> float:
    """
    Generates a crash point using HMAC-SHA256.
    server_seed_hex: Server seed in hexadecimal.
    client_seed_hex: Client seed in hexadecimal.
    nonce: Game round number (integer).
    house_edge: The house edge for this game.
    """
    message_str = f"{client_seed_hex}:{nonce}"
    
    # Create HMAC-SHA256 hash
    game_hash = hmac.new(
        bytes.fromhex(server_seed_hex),
        msg=message_str.encode('utf-8'),
        digestmod=hashlib.sha256
    )
    game_hash_hex = game_hash.hexdigest()
    
    return get_multiplier_from_hash(game_hash_hex, house_edge)

# --- Game State Management Functions ---

def create_new_game() -> SpacecrashGame:
    """Creates a new Spacecrash game instance."""
    server_seed = generate_server_seed()
    public_seed = hashlib.sha256(server_seed.encode('utf-8')).hexdigest() # Hash of server_seed is public

    new_game = SpacecrashGame(
        server_seed=server_seed,
        public_seed=public_seed,
        nonce=0, # Placeholder, will be set when game round starts if we use per-round nonces
                 # Or this could be a global nonce for this seed pair if client_seed is fixed early
        status='pending', # Initial status
        # crash_point will be set when game starts
    )
    db.session.add(new_game)
    # db.session.commit() # Commit should be handled by the caller route
    return new_game

def start_betting_phase(game: SpacecrashGame) -> bool:
    """Transitions the game to the 'betting' phase."""
    if game.status == 'pending':
        game.status = 'betting'
        # game.game_start_time = None # Ensure it's not set yet
        game.game_end_time = None
        # db.session.commit() # Caller handles commit
        return True
    return False

def start_game_round(game: SpacecrashGame, client_seed_param: str, nonce_param: int) -> bool:
    """
    Starts a new game round: sets client_seed, nonce, calculates crash_point,
    sets game_start_time, and updates status to 'in_progress'.
    """
    if game.status == 'betting': # Or 'pending' if bets can be placed before formal betting phase
        game.client_seed = client_seed_param
        game.nonce = nonce_param # Use the provided nonce for this specific round
        
        # Calculate crash point (assuming house edge is fixed for now, or get from config)
        # TODO: Get house_edge from app config if it's configurable
        house_edge_config = 0.01 # Example
        game.crash_point = generate_crash_point(game.server_seed, game.client_seed, game.nonce, house_edge_config)
        
        game.status = 'in_progress'
        game.game_start_time = datetime.now(timezone.utc)
        game.game_end_time = None # Ensure end time is cleared
        # db.session.commit() # Caller handles commit
        return True
    return False

def end_game_round(game: SpacecrashGame) -> bool:
    """Ends the current game round, sets status to 'completed' and records end time."""
    if game.status == 'in_progress':
        game.status = 'completed'
        game.game_end_time = datetime.now(timezone.utc)
        
        # Process bets that were not ejected and determine if they busted or won implicitly at crash
        # This logic is complex: if a player did not eject, their bet outcome is determined by crash_point.
        # If auto_eject_at was set and <= crash_point, it's a win. Otherwise, bust.
        # If no auto_eject_at, they bust unless crash_point is somehow a win (not typical for crash games).
        
        bets_to_process = SpacecrashBet.query.filter_by(game_id=game.id, status='placed').all()
        for bet in bets_to_process:
            user = User.query.get(bet.user_id)
            if not user: # Should not happen
                continue

            won = False
            if bet.auto_eject_at and bet.auto_eject_at <= game.crash_point:
                # Auto-eject was successful
                bet.ejected_at = bet.auto_eject_at
                bet.win_amount = int(bet.bet_amount * bet.ejected_at)
                user.balance += bet.win_amount
                bet.status = 'ejected' # Or 'won_auto'
                won = True
            else:
                # Busted or no auto-eject, so they rode it to the crash
                bet.status = 'busted'
                bet.ejected_at = game.crash_point # Informational: they "ejected" at crash
                bet.win_amount = 0 # No winnings if busted

            # Could add a transaction record here for the bet resolution (win/loss)
        
        # db.session.commit() # Caller handles commit
        return True
    return False

def get_current_multiplier(game: SpacecrashGame, default_if_not_started: float = 1.0) -> float:
    """
    Calculates the current multiplier for an 'in_progress' game.
    Returns default_if_not_started if game hasn't started or not in progress.
    """
    if game and game.status == 'in_progress' and game.game_start_time:
        elapsed_seconds = (datetime.now(timezone.utc) - game.game_start_time).total_seconds()
        if elapsed_seconds < 0: elapsed_seconds = 0 # Should not happen with proper time sync

        # Growth formula: e.g., 1.00 * (1.07^elapsed_seconds)
        # Adjust base and exponent factor for desired curve
        # For example, a common curve: multiplier = 1.00 * math.pow(1.07, elapsed_seconds)
        # Or using `e`: multiplier = math.exp(elapsed_seconds * k) where k controls speed
        
        # Using a simple exponential growth for now:
        # multiplier = 1.00 * math.pow(1.015, elapsed_seconds * 5) # Example: faster growth
        # multiplier = 1.00 * math.pow(1.0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000_00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000:00:00** Intro
**00:02:26** What the guys are drinking
**00:06:14** The guys talk to Richard Paterson
**00:07:07** The importance of wood and oak
**00:09:44** The Dalmore King Alexander III
**00:11:38** Richard's early career
**00:16:51** The Whyte & Mackay years
**00:23:21** Richard's signature style
**00:26:43** The Dalmore Constellation Collection
**00:28:29** The Dalmore Paterson Collection
**00:31:16** Richard's love of sherry
**00:34:38** The challenges of sourcing sherry casks
**00:37:39** Jura distillery
**00:40:42** Richard's involvement with other distilleries
**00:43:39** The Fettercairn warehouses
**00:45:07** Richard's new venture - Wolfcraig Distillery
**00:48:11** Richard's view on NAS whisky
**00:50:01** Richard's view on the secondary market
**00:51:17** Richard's view on the future of Scotch whisky
**00:52:15** Outro
