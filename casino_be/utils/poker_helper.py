import random
import secrets
from datetime import datetime, timezone
from decimal import Decimal # For precise monetary calculations

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc

# Assuming models are in casino_be.models
# Adjust the import path if your project structure is different.
# from ..models import db, User, PokerTable, PokerHand, PokerPlayerState, Transaction # if utils is a module inside casino_be
from casino_be.models import db, User, PokerTable, PokerHand, PokerPlayerState, Transaction

# Card Constants
SUITS = ['H', 'D', 'C', 'S']  # Hearts, Diamonds, Clubs, Spades
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']

# --- Game Setup Functions ---

def _create_deck() -> list[str]:
    """Creates a standard 52-card deck."""
    return [s + r for s in SUITS for r in RANKS]

def _shuffle_deck(deck: list[str]) -> None:
    """Shuffles the deck in place using secrets.SystemRandom for better randomness."""
    # secrets.SystemRandom().shuffle(deck) # This is the preferred way if secrets.SystemRandom has shuffle
    # random.shuffle uses Mersenne Twister which is fine for most simulations but not cryptographically secure
    # For card games, especially involving real money, stronger shuffling is good practice.
    # Python's default random.shuffle is usually sufficient for non-critical applications.
    # Let's use random.shuffle for now for simplicity as secrets.SystemRandom().shuffle isn't a direct method.
    # A more robust shuffle could involve multiple shuffles or a CSPRNG.
    random.shuffle(deck)


def _deal_card(deck_list: list[str]) -> str | None:
    """Removes and returns the top card from the deck list. Returns None if deck is empty."""
    if deck_list:
        return deck_list.pop(0) # Assuming top card is at the start of the list
    return None

def deal_hole_cards(player_states: list[PokerPlayerState], deck: list[str]) -> bool:
    """
    Deals two cards to each player in player_states who is is_active_in_hand.
    Updates player_states with hole cards.
    Assumes deck is already shuffled.
    Returns True if successful, False if not enough cards.
    """
    num_active_players = sum(1 for ps in player_states if ps.is_active_in_hand)
    if len(deck) < num_active_players * 2:
        # Log error: Not enough cards to deal hole cards
        print(f"Error: Not enough cards ({len(deck)}) to deal hole cards to {num_active_players} players.")
        return False

    for _ in range(2): # Deal one card at a time to each player
        for player_state in player_states:
            if player_state.is_active_in_hand:
                card = _deal_card(deck)
                if card:
                    if player_state.hole_cards is None:
                        player_state.hole_cards = []
                    player_state.hole_cards.append(card)
                else:
                    # This should not happen if initial check passed
                    print("Error: Deck ran out unexpectedly during hole card dealing.")
                    return False
    return True


def deal_community_cards(street: str, deck: list[str], current_board_cards: list[str]) -> list[str]:
    """
    Deals community cards for the given street.
    Street can be 'flop' (3 cards), 'turn' (1 card), 'river' (1 card).
    Appends cards to current_board_cards and returns the updated list.
    """
    cards_to_deal = 0
    if street == 'flop':
        cards_to_deal = 3
    elif street == 'turn' or street == 'river':
        cards_to_deal = 1

    if len(deck) < cards_to_deal:
        print(f"Error: Not enough cards in deck to deal {street}.")
        return current_board_cards # Or raise an error

    # Burn a card (optional, common practice)
    # _deal_card(deck) 

    for _ in range(cards_to_deal):
        card = _deal_card(deck)
        if card:
            current_board_cards.append(card)
        else:
            # Should not happen if initial check passed
            print(f"Error: Deck ran out unexpectedly during {street} dealing.")
            break 
            
    return current_board_cards

# --- Basic Hand State & Player Management ---

def start_new_hand(table_id: int):
    """
    Starts a new hand at the specified poker table.
    - Fetches table and active players.
    - Resets relevant states.
    - Determines dealer button.
    - Collects blinds.
    - Creates PokerHand record.
    - Deals hole cards.
    - Sets initial player to act.
    """
    session = db.session
    poker_table = session.query(PokerTable).options(joinedload(PokerTable.player_states).joinedload(PokerPlayerState.user)).get(table_id)

    if not poker_table or not poker_table.is_active:
        return {"error": "Table not found or inactive."}

    active_players = [ps for ps in poker_table.player_states if ps.stack_sats > 0 and not ps.is_sitting_out]
    
    if len(active_players) < 2:
        return {"error": "Not enough active players to start a hand (minimum 2 required)."}

    # 1. Reset player states for the new hand
    for ps in active_players:
        ps.hole_cards = [] # Reset hole cards
        ps.last_action = None
        ps.is_active_in_hand = True # Mark them as active for this hand

    # 2. Determine dealer button (simple rotation for now)
    # This needs a more robust way to track the button, e.g., store last_button_seat_id on PokerTable
    # For now, pick the first player or rotate based on seat_id if available
    # TODO: Implement robust dealer button assignment (e.g., store button position on table)
    
    # Find the player who was dealer last, or start with the lowest seat_id
    # This is a placeholder. A real implementation needs to track the button position persistently.
    sorted_players_by_seat = sorted(active_players, key=lambda p: p.seat_id)
    
    # Example: find current button or initialize if first hand
    # current_button_seat_id = poker_table.current_dealer_seat_id (needs to be added to PokerTable model)
    # if current_button_seat_id is None:
    #    dealer_player = sorted_players_by_seat[0]
    # else:
    #    current_dealer_idx = next((i for i, p in enumerate(sorted_players_by_seat) if p.seat_id == current_button_seat_id), -1)
    #    dealer_player = sorted_players_by_seat[(current_dealer_idx + 1) % len(sorted_players_by_seat)]
    # poker_table.current_dealer_seat_id = dealer_player.seat_id

    if not sorted_players_by_seat: # Should be caught by len(active_players) < 2
        return {"error": "No players available to be dealer."}

    # Simplified: first player in sorted list is dealer for now.
    dealer_player_index = 0 # Placeholder for actual button logic
    
    # 3. Collect Blinds
    pot_size_sats = 0
    
    # Small Blind
    sb_player_index = (dealer_player_index + 1) % len(sorted_players_by_seat)
    sb_player_state = sorted_players_by_seat[sb_player_index]
    sb_amount = min(poker_table.small_blind, sb_player_state.stack_sats)
    sb_player_state.stack_sats -= sb_amount
    pot_size_sats += sb_amount
    # TODO: Create Transaction for SB
    # transaction_sb = Transaction(user_id=sb_player_state.user_id, amount=-sb_amount, transaction_type='poker_blind', details={"table_id": table_id, "blind_type": "small"})
    # session.add(transaction_sb)
    sb_player_state.last_action = f"posts_sb_{sb_amount}"


    # Big Blind
    bb_player_index = (dealer_player_index + 2) % len(sorted_players_by_seat)
    bb_player_state = sorted_players_by_seat[bb_player_index]
    bb_amount = min(poker_table.big_blind, bb_player_state.stack_sats)
    bb_player_state.stack_sats -= bb_amount
    pot_size_sats += bb_amount
    # TODO: Create Transaction for BB
    # transaction_bb = Transaction(user_id=bb_player_state.user_id, amount=-bb_amount, transaction_type='poker_blind', details={"table_id": table_id, "blind_type": "big"})
    # session.add(transaction_bb)
    bb_player_state.last_action = f"posts_bb_{bb_amount}"

    # 4. Create PokerHand record
    current_time = datetime.now(timezone.utc)
    new_hand = PokerHand(
        table_id=table_id,
        pot_size_sats=pot_size_sats,
        start_time=current_time,
        hand_history=[ # Initial history
            {"action": "start_hand", "timestamp": current_time.isoformat()},
            {"user_id": sb_player_state.user_id, "seat_id": sb_player_state.seat_id, "action": "post_small_blind", "amount": sb_amount, "timestamp": current_time.isoformat()},
            {"user_id": bb_player_state.user_id, "seat_id": bb_player_state.seat_id, "action": "post_big_blind", "amount": bb_amount, "timestamp": current_time.isoformat()}
        ],
        board_cards=[] # Initialize empty board
    )
    session.add(new_hand)
    session.flush() # To get new_hand.id for transactions if needed immediately

    # Link transactions to hand_id if that's desired (needs Transaction model adjustment or other linking table)
    # transaction_sb.poker_hand_id = new_hand.id 
    # transaction_bb.poker_hand_id = new_hand.id

    # 5. Create and Shuffle Deck
    deck = _create_deck()
    _shuffle_deck(deck)

    # 6. Deal Hole Cards
    if not deal_hole_cards(active_players, deck): # Pass only active players who are in the hand
        # This should rollback the transaction or handle error appropriately
        session.rollback()
        return {"error": "Failed to deal hole cards due to insufficient cards."}
    
    for ps in active_players: # Persist hole cards if they were dealt
        session.add(ps)

    # 7. Set initial player to act (player after Big Blind)
    # TODO: Determine actual first player to act (e.g., UTG)
    first_to_act_index = (bb_player_index + 1) % len(sorted_players_by_seat)
    first_to_act_player = sorted_players_by_seat[first_to_act_index]
    # Store this information, perhaps in PokerHand.current_turn_user_id or similar
    # poker_table.current_turn_user_id = first_to_act_player.user_id (needs field on table or hand)
    # poker_table.current_bet_to_match = poker_table.big_blind
    # poker_table.last_raise_amount = poker_table.big_blind


    new_hand.hand_history.append({
        "action": "deal_hole_cards", 
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "next_to_act": {"user_id": first_to_act_player.user_id, "seat_id": first_to_act_player.seat_id}
    })
    
    session.commit()

    # TODO: Return a more comprehensive game state for the API
    return {
        "message": "New hand started.",
        "hand_id": new_hand.id,
        "table_id": table_id,
        "dealer_seat": sorted_players_by_seat[dealer_player_index].seat_id, # Example
        "sb_player_seat": sb_player_state.seat_id,
        "bb_player_seat": bb_player_state.seat_id,
        "pot_size": new_hand.pot_size_sats,
        "board_cards": new_hand.board_cards,
        "active_players_states": [
            {
                "user_id": ps.user_id, 
                "seat_id": ps.seat_id, 
                "stack": ps.stack_sats, 
                "hole_cards": ps.hole_cards, # This should only be sent to the specific player
                "is_active_in_hand": ps.is_active_in_hand
            } for ps in active_players
        ],
        "next_to_act_seat": first_to_act_player.seat_id, # Example
        # "deck_remaining": len(deck) # For debugging/testing
    }


def handle_sit_down(user_id: int, table_id: int, seat_id: int, buy_in_amount: int):
    """
    Allows a user to sit down at a poker table.
    - Validates seat availability and buy-in amount.
    - Deducts buy_in_amount from User.balance.
    - Creates a Transaction.
    - Creates/Updates PokerPlayerState.
    """
    session = db.session
    user = session.query(User).get(user_id)
    poker_table = session.query(PokerTable).options(joinedload(PokerTable.player_states)).get(table_id)

    if not user:
        return {"error": "User not found."}
    if not poker_table:
        return {"error": "Poker table not found."}

    # Validate buy-in amount
    if not (poker_table.min_buy_in <= buy_in_amount <= poker_table.max_buy_in):
        return {"error": f"Buy-in amount must be between {poker_table.min_buy_in} and {poker_table.max_buy_in} satoshis."}

    if user.balance < buy_in_amount:
        return {"error": "Insufficient balance."}

    # Check if seat is valid and available
    if not (1 <= seat_id <= poker_table.max_seats):
        return {"error": f"Invalid seat ID. Must be between 1 and {poker_table.max_seats}."}
    
    existing_player_at_seat = next((ps for ps in poker_table.player_states if ps.seat_id == seat_id), None)
    if existing_player_at_seat:
        return {"error": f"Seat {seat_id} is already occupied."}
    
    # Check if user is already seated at this table
    user_already_seated = next((ps for ps in poker_table.player_states if ps.user_id == user_id), None)
    if user_already_seated:
        return {"error": f"User {user.username} is already seated at this table at seat {user_already_seated.seat_id}."}

    # Process buy-in
    user.balance -= buy_in_amount
    transaction = Transaction(
        user_id=user_id,
        amount=-buy_in_amount, # Negative for debit from user balance
        transaction_type='poker_buy_in',
        status='completed',
        details={"table_id": table_id, "seat_id": seat_id, "buy_in_amount": buy_in_amount}
    )
    session.add(transaction)

    # Create PokerPlayerState
    player_state = PokerPlayerState(
        user_id=user_id,
        table_id=table_id,
        seat_id=seat_id,
        stack_sats=buy_in_amount,
        is_sitting_out=False, # Player is active when they sit down
        is_active_in_hand=False, # Not in a hand until one starts and they are dealt in
        joined_at=datetime.now(timezone.utc)
    )
    session.add(player_state)
    
    # poker_table.current_players might be a JSON field or managed by relation, handled by player_states relationship
    
    try:
        session.commit()
        return {
            "message": f"User {user.username} successfully sat down at table {poker_table.name}, seat {seat_id} with {buy_in_amount} satoshis.",
            "player_state": {
                "user_id": player_state.user_id,
                "table_id": player_state.table_id,
                "seat_id": player_state.seat_id,
                "stack_sats": player_state.stack_sats,
                "is_sitting_out": player_state.is_sitting_out
            },
            "user_balance": user.balance
        }
    except Exception as e:
        session.rollback()
        # Log error e
        print(f"Error during sit down: {e}")
        return {"error": "Could not process sit down due to a server error."}


def handle_stand_up(user_id: int, table_id: int):
    """
    Allows a user to stand up from a poker table.
    - Adds player's stack from PokerPlayerState back to User.balance.
    - Creates a Transaction.
    - Removes/deactivates the PokerPlayerState.
    - Folds the player from any active hand (TODO).
    """
    session = db.session
    player_state = session.query(PokerPlayerState).filter_by(user_id=user_id, table_id=table_id).first()
    
    if not player_state:
        return {"error": "Player not found at this table."}

    user = session.query(User).get(user_id)
    if not user: # Should not happen if player_state exists with user_id
        return {"error": "User associated with player state not found."}

    # TODO: Handle folding from active hand if player is_active_in_hand
    # This might involve calling handle_fold logic or directly updating hand state.
    if player_state.is_active_in_hand:
        # For now, just mark as inactive. Real logic would fold them.
        player_state.is_active_in_hand = False 
        # Consider implications for current hand pot, side pots etc.
        print(f"Warning: Player {user_id} stood up while active in a hand. Auto-folding (not fully implemented).")


    amount_to_return = player_state.stack_sats
    user.balance += amount_to_return
    
    transaction = Transaction(
        user_id=user_id,
        amount=amount_to_return, # Positive for credit to user balance
        transaction_type='poker_cash_out', # Or 'poker_stand_up'
        status='completed',
        details={"table_id": table_id, "seat_id": player_state.seat_id, "returned_amount": amount_to_return}
    )
    session.add(transaction)

    # Remove PokerPlayerState
    session.delete(player_state)
    
    try:
        session.commit()
        return {
            "message": f"User {user.username} successfully stood up from table {table_id}. Returned {amount_to_return} satoshis to balance.",
            "user_balance": user.balance
        }
    except Exception as e:
        session.rollback()
        # Log error e
        print(f"Error during stand up: {e}")
        return {"error": "Could not process stand up due to a server error."}


# --- Betting Logic Stubs ---

def handle_fold(user_id: int, table_id: int, hand_id: int):
    """Placeholder for handling a player's fold action."""
    # TODO: Implement fold logic
    # - Mark player as folded for the hand (PokerPlayerState.is_active_in_hand = False, or a status field)
    # - Update PokerHand.hand_history
    # - Check if hand ends (if only one player remains)
    # - Determine next player to act
    # - Update table/hand state (current_bet_to_match, etc.)
    session = db.session
    player_state = session.query(PokerPlayerState).filter_by(user_id=user_id, table_id=table_id).first()
    # hand = session.query(PokerHand).get(hand_id)
    if not player_state: # or not hand:
        return {"error": "Player or hand not found."}
    
    player_state.is_active_in_hand = False
    player_state.last_action = "fold"
    # hand.hand_history.append(...)
    # session.commit()
    print(f"Action (Placeholder): User {user_id} folds at table {table_id}.")
    return {"message": f"User {user_id} folded."}

def handle_check(user_id: int, table_id: int, hand_id: int):
    """Placeholder for handling a player's check action."""
    # TODO: Implement check logic
    # - Validate if check is a legal action (no outstanding bet)
    # - Update PokerHand.hand_history
    # - Determine next player to act or end of betting round
    session = db.session
    player_state = session.query(PokerPlayerState).filter_by(user_id=user_id, table_id=table_id).first()
    if not player_state:
        return {"error": "Player not found."}

    # poker_hand = session.query(PokerHand).get(hand_id)
    # current_bet = poker_hand.current_bet_to_match # Need to store this on PokerHand or PokerTable state
    # amount_player_invested_in_street = ... # Need to track this
    # if current_bet > amount_player_invested_in_street:
    #    return {"error": "Cannot check, there is a bet to call."}
    
    player_state.last_action = "check"
    # hand.hand_history.append(...)
    # session.commit()
    print(f"Action (Placeholder): User {user_id} checks at table {table_id}.")
    return {"message": f"User {user_id} checked."}

def handle_call(user_id: int, table_id: int, hand_id: int):
    """Placeholder for handling a player's call action."""
    # TODO: Implement call logic
    # - Determine amount to call
    # - Validate if player has enough stack
    # - Update player stack, pot size
    # - Create Transaction
    # - Update PokerHand.hand_history
    # - Determine next player to act or end of betting round
    session = db.session
    player_state = session.query(PokerPlayerState).filter_by(user_id=user_id, table_id=table_id).first()
    if not player_state:
        return {"error": "Player not found."}
    
    # poker_hand = session.query(PokerHand).get(hand_id)
    # amount_to_call = poker_hand.current_bet_to_match - player_state.amount_invested_this_street
    # if player_state.stack_sats < amount_to_call:
    #    # Handle all-in call
    #    pass
    # player_state.stack_sats -= amount_to_call
    # poker_hand.pot_size_sats += amount_to_call
    player_state.last_action = "call"
    # hand.hand_history.append(...)
    # session.commit()
    print(f"Action (Placeholder): User {user_id} calls at table {table_id}.")
    return {"message": f"User {user_id} called."}


def handle_bet(user_id: int, table_id: int, hand_id: int, amount: int):
    """Placeholder for handling a player's bet action."""
    # TODO: Implement bet logic
    # - Validate if bet is a legal action (no prior bet in the round, or it's a new street)
    # - Validate bet amount (min bet, table limits, player stack) using _validate_bet
    # - Update player stack, pot size
    # - Create Transaction
    # - Update PokerHand.hand_history, PokerHand.current_bet_to_match, PokerHand.last_raiser
    # - Determine next player to act
    session = db.session
    player_state = session.query(PokerPlayerState).filter_by(user_id=user_id, table_id=table_id).first()
    if not player_state:
        return {"error": "Player not found."}

    # poker_hand = session.query(PokerHand).get(hand_id)
    # poker_table = session.query(PokerTable).get(table_id)
    # is_valid, error_msg = _validate_bet(player_state, amount, poker_hand.current_bet_to_match, poker_hand.min_raise_this_round, poker_table.limit_type, poker_hand.pot_size_sats)
    # if not is_valid:
    #    return {"error": error_msg}

    # player_state.stack_sats -= amount
    # poker_hand.pot_size_sats += amount
    player_state.last_action = f"bet_{amount}"
    # hand.hand_history.append(...)
    # session.commit()
    print(f"Action (Placeholder): User {user_id} bets {amount} at table {table_id}.")
    return {"message": f"User {user_id} bet {amount}."}

def handle_raise(user_id: int, table_id: int, hand_id: int, amount: int):
    """Placeholder for handling a player's raise action."""
    # TODO: Implement raise logic
    # - Validate if raise is a legal action
    # - Validate raise amount (min raise, table limits, player stack) using _validate_bet
    # - Update player stack, pot size
    # - Create Transaction
    # - Update PokerHand.hand_history, PokerHand.current_bet_to_match, PokerHand.last_raiser
    # - Determine next player to act
    session = db.session
    player_state = session.query(PokerPlayerState).filter_by(user_id=user_id, table_id=table_id).first()
    if not player_state:
        return {"error": "Player not found."}
        
    # poker_hand = session.query(PokerHand).get(hand_id)
    # poker_table = session.query(PokerTable).get(table_id)
    # is_valid, error_msg = _validate_bet(player_state, amount, poker_hand.current_bet_to_match, poker_hand.min_raise_this_round, poker_table.limit_type, poker_hand.pot_size_sats)
    # if not is_valid: # This validation needs to check if it's a valid *raise* specifically
    #    return {"error": error_msg}

    # player_state.stack_sats -= amount # Amount here is the total bet for the current action
    # poker_hand.pot_size_sats += amount
    player_state.last_action = f"raise_to_{amount}"
    # hand.hand_history.append(...)
    # session.commit()
    print(f"Action (Placeholder): User {user_id} raises to {amount} at table {table_id}.")
    return {"message": f"User {user_id} raised to {amount}."}


def _validate_bet(player_state: PokerPlayerState, 
                  action_amount: int, # The total amount the player is making their bet/raise to for this action
                  current_bet_to_match: int, # The current highest bet on the table for this street
                  min_raise_amount_total: int, # The minimum total amount a raise must be (current_bet_to_match + last_raise_delta)
                  limit_type: str, # "no_limit", "pot_limit", "fixed_limit"
                  table_pot_size_if_pot_limit: int = 0, # Needed for pot_limit calculations
                  player_amount_invested_this_street: int = 0 # How much player already put in this street
                  ) -> tuple[bool, str]:
    """
    Validates a bet or raise amount based on game rules.
    action_amount is the total amount the player is committing with this action (not just the raise portion).
    min_raise_amount_total is the total sum a player must make it if they are raising.
    player_amount_invested_this_street is the amount player already has in the pot for the current betting round.
    Returns (is_valid, message).
    """
    # TODO: Implement comprehensive bet validation logic
    # This is a complex function that needs to handle:
    # - No-Limit: Min bet (usually Big Blind), min raise (usually previous bet/raise delta)
    # - Pot-Limit: Max bet/raise is pot size. Pot calculation: current_pot + all bets on table + amount caller would call.
    # - Fixed-Limit: Bet/raise amounts are fixed.
    # - Player stack coverage (cannot bet more than stack, handle all-in)
    
    actual_bet_value = action_amount - player_amount_invested_this_street # The new money being added

    if actual_bet_value <= 0 and action_amount < current_bet_to_match : # Not a call or raise, and not covering current bet
        return False, "Invalid bet amount. Must be at least the call amount or a valid raise."

    if player_state.stack_sats < actual_bet_value: # Checks if new money part of bet is covered
        # This implies an all-in. The action_amount should be capped at player_state.stack_sats + player_amount_invested_this_street
        # The actual_bet_value would then be player_state.stack_sats
        # For now, let's assume action_amount is already capped by client or earlier logic for all-in.
        # If action_amount is effectively an all-in:
        if action_amount == (player_state.stack_sats + player_amount_invested_this_street):
             pass # This is a valid all-in bet/call/raise (assuming it meets other criteria if it's a raise)
        else: # Player trying to bet more than they have, but not exactly all-in
            return False, f"Cannot bet {action_amount}. Insufficient stack ({player_state.stack_sats} remaining)."


    # Is it a bet (opening action) or a raise?
    is_opening_bet = current_bet_to_match == 0

    if is_opening_bet:
        if limit_type == "no_limit" or limit_type == "pot_limit":
            # Minimum opening bet is usually the Big Blind size
            # This needs access to table.big_blind
            # if action_amount < table.big_blind: return False, f"Minimum opening bet is {table.big_blind}"
            pass 
        # TODO: Pot limit check for opening bet max
        # TODO: Fixed limit check for opening bet amount
    else: # It's a call or a raise
        if action_amount < current_bet_to_match: # Not enough to call
             # This case should ideally be handled by all-in logic if stack is short
            return False, f"Amount too small. Must call {current_bet_to_match} or raise."
        
        if action_amount > current_bet_to_match: # It's a raise
            if action_amount < min_raise_amount_total and action_amount < (player_state.stack_sats + player_amount_invested_this_street) : # Not an all-in raise that's less than min_raise
                return False, f"Raise amount too small. Minimum raise must make total bet at least {min_raise_amount_total}."
            # TODO: Pot limit check for raise max
            # TODO: Fixed limit check for raise amount

    return True, "Bet is valid." # Placeholder


def _calculate_pot_limit_raise_sizes(player_total_stack: int, 
                                     current_pot_total: int, 
                                     amount_to_call_for_player: int) -> tuple[int, int]:
    """
    Calculates minimum and maximum raise amounts for Pot Limit games.
    The amount a player can raise is relative to what the pot size *would be* after they call.
    Returns (min_raise_total_bet, max_raise_total_bet).
    min_raise_total_bet is the total bet amount for a minimum raise.
    max_raise_total_bet is the total bet amount for a maximum (pot-sized) raise.
    """
    # TODO: Implement pot limit raise calculation
    # Min raise: Typically, the previous bet/raise amount. If BB is 10, first bet is 10. Min raise makes it 20.
    # If current bet is 20, last raise was 10. Min raise makes it 30.
    # This needs knowledge of the previous bet/raise increment (delta).
    # min_raise_delta = last_raise_or_bet_amount (e.g. big_blind if no prior raise)
    # min_raise_total_bet = current_bet_to_match + min_raise_delta 
    
    # Max (pot) raise:
    # Pot size after call = current_pot_total + (all active bets now on table, including current_bet_to_match from others) + amount_to_call_for_player
    # This is tricky. Simpler: pot_size_after_call = current_pot_total + (current_bet_to_match - player_amount_already_in_for_street) + current_bet_to_match (if others have also matched)
    # Standard calculation: Pot = existing_pot + all_bets_on_table_including_callers_call.
    # So, if pot is 100, player A bets 50. Player B wants to pot. Player B must first call 50. Pot is now 100 + 50 (A's bet) + 50 (B's call) = 200.
    # Player B can raise BY 200, making their total bet 50 (call) + 200 (raise) = 250.
    
    pot_size_after_call = current_pot_total + (amount_to_call_for_player * 2) # Simplified: assumes one other better who made current_bet_to_match
    # A more accurate `pot_size_after_call` would sum current_pot_total + all player's commitments in the current round if they all called.
    # Let's use a common definition: current_pot + (2 * last_bet_or_raise) + sum_of_other_calls_between_last_raiser_and_current_player
    # For simplicity: pot_if_called = current_pot_total + (amount_to_call_for_player) + sum of what other active players would call
    # The raise is on top of the call.
    # max_raise_amount = pot_if_called
    # max_raise_total_bet = amount_to_call_for_player + max_raise_amount
    
    # Placeholder, this needs careful implementation based on precise PLO rules.
    # Example: Pot is 100. Bet is 50. To make a pot raise:
    # 1. Call 50. Pot is now 100 (original) + 50 (bet) + 50 (your call) = 200.
    # 2. You can raise by 200.
    # Your total bet = 50 (call) + 200 (raise) = 250.
    
    # Let prev_bet_size be the amount of the last bet or raise.
    # min_raise_total = current_bet_to_match + prev_bet_size (assuming prev_bet_size is the increment)
    
    # max_raise_value_on_top_of_call = current_pot_total + amount_to_call_for_player + current_bet_to_match (if current_bet_to_match was from one player)
    # This is a common simplification: Pot = Current Pot + 3 * Previous Bet/Raise (if heads up, or 2* if first to act and betting pot)
    
    # For now, returning unbounded for No-Limit effectively.
    # True PLO min raise is typically double the previous bet, or the previous raise amount.
    # min_raise_total = current_bet_to_match + (current_bet_to_match - previous_bet_before_current_one)
    # max_raise_total = amount_to_call_for_player + (current_pot_total + amount_to_call_for_player + current_bet_to_match) # One common interpretation
    
    # These are effectively No-Limit values for now.
    min_raise_total_placeholder = amount_to_call_for_player + (current_pot_total if current_pot_total > 0 else 1) # Needs actual big blind / prev raise
    max_raise_total_placeholder = player_total_stack # Effectively no limit up to stack
    
    # Ensure min raise is at least doubling the previous bet or fulfilling the minimum increment.
    # Ensure max raise is capped by player's stack.
    # min_raise_total_placeholder = max(min_raise_total_placeholder, amount_to_call_for_player * 2) # simple double
    # max_raise_total_placeholder = min(max_raise_total_placeholder, player_total_stack)


    # THIS IS A STUB and needs to be accurate for PLO.
    # For now, let's assume min raise is double current bet to match (if it's an actual raise, not opening bet)
    # And max is player's stack.
    # This does not correctly implement PLO min/max raise sizes.
    min_raise = current_bet_to_match * 2 if current_bet_to_match > 0 else 1 # Simplified, needs last raise delta
    max_raise = player_total_stack 
    
    return (min_raise, max_raise)


# --- Hand Evaluation Stub ---

def _get_card_value(card_str: str) -> int:
    """
    Helper to get numeric value of a card. 'T' is 10, ..., 'A' is 14.
    Suit is ignored. For Ace in A-5 straight, special handling is needed elsewhere.
    """
    rank = card_str[1:] #Suit is card_str[0]
    if rank.isdigit():
        return int(rank)
    elif rank == 'T':
        return 10
    elif rank == 'J':
        return 11
    elif rank == 'Q':
        return 12
    elif rank == 'K':
        return 13
    elif rank == 'A':
        return 14 # Ace high
    return 0 # Should not happen

def _determine_winning_hand(player_hole_cards_map: dict[int, list[str]], board_cards: list[str]):
    """
    Determines the winning hand(s) from players who went to showdown.
    player_hole_cards_map: {user_id_1: ["AH", "KH"], user_id_2: ["7D", "8D"]}
    board_cards: ["5S", "6S", "7S", "QD", "JC"]

    Returns: A list of winning player dicts, e.g., [{"user_id": X, "amount_won": Y, "winning_hand": "Full House", "best_five_cards": []}]
             Handles split pots by returning multiple players if they tie.
    
    TODO: This is a complex function. Needs a robust hand evaluation algorithm.
          For now, placeholder: picks a random winner or highest card.
          Libraries like 'treys' or 'deuces' can be used for this.
    """
    if not player_hole_cards_map:
        return []

    # Placeholder: Naive highest card logic (very basic)
    best_hand_value = -1
    winners = []
    
    print(f"Determining winner (placeholder) for board: {board_cards}")
    print(f"Player hands: {player_hole_cards_map}")

    for user_id, hole_cards in player_hole_cards_map.items():
        if not hole_cards or len(hole_cards) != 2:
            continue # Skip players with no/invalid hole cards for this simple eval

        # Simple high card eval from hole cards only (ignores board for this placeholder)
        hc_values = sorted([_get_card_value(c) for c in hole_cards], reverse=True)
        player_high_card_val = hc_values[0] if hc_values else 0
        
        # A slightly better placeholder: best card out of hole + board
        all_cards = hole_cards + board_cards
        all_card_values = sorted([_get_card_value(c) for c in all_cards], reverse=True)
        current_player_best_value = all_card_values[0] if all_card_values else 0
        # This is still not a poker hand evaluation, just "highest single card"

        print(f"User {user_id}, Hole: {hole_cards}, Best card value (placeholder): {current_player_best_value}")

        if current_player_best_value > best_hand_value:
            best_hand_value = current_player_best_value
            winners = [{"user_id": user_id, "winning_hand": "High Card (Placeholder)", "best_five_cards": hole_cards}] # Placeholder
        elif current_player_best_value == best_hand_value:
            winners.append({"user_id": user_id, "winning_hand": "High Card (Placeholder)", "best_five_cards": hole_cards}) # Tie

    if not winners and player_hole_cards_map: # Fallback if above logic fails somehow
        # Pick a random winner if no logic applied or all cards had 0 value
        random_winner_id = random.choice(list(player_hole_cards_map.keys()))
        winners = [{"user_id": random_winner_id, "winning_hand": "Randomly Selected (Placeholder)", "best_five_cards": []}]

    # The "amount_won" will be determined by _distribute_pot based on these winners
    return winners


# --- Showdown & Payout Stubs ---

def _distribute_pot(poker_hand: PokerHand, winners_info: list[dict]):
    """
    Distributes the pot(s) to the winner(s).
    Updates PokerHand with rake and winner details.
    Creates Transaction records for winnings.
    
    winners_info: from _determine_winning_hand, but amount_won needs to be calculated here.
                  e.g., [{"user_id": X, "winning_hand": "Full House", "best_five_cards": []}, ...]
                  
    TODO: Implement pot distribution logic, including side pots.
    """
    session = db.session
    
    if not winners_info:
        print(f"Error: No winners provided for hand {poker_hand.id}. Pot distribution cannot occur.")
        # This might happen if all remaining players folded except one, handled before showdown.
        # Or if _determine_winning_hand had an issue.
        return

    total_pot = poker_hand.pot_size_sats
    
    # TODO: Calculate rake (e.g., 5% of pot up to a max cap)
    # poker_table = session.query(PokerTable).get(poker_hand.table_id)
    # rake_percentage = Decimal("0.05") # Example: 5%
    # max_rake_sats = 3 * poker_table.big_blind # Example: Max rake of 3 BBs
    # calculated_rake = int(Decimal(total_pot) * rake_percentage)
    # actual_rake = min(calculated_rake, max_rake_sats)
    actual_rake = 0 # Placeholder: No rake for now
    
    poker_hand.rake_sats = actual_rake
    pot_to_distribute = total_pot - actual_rake
    
    num_winners = len(winners_info)
    if num_winners == 0: # Should be caught earlier
        # This could mean the pot is carried over or returned if rules allow (unlikely in poker)
        print(f"Hand {poker_hand.id}: No winners determined. Pot of {pot_to_distribute} not distributed.")
        return

    amount_per_winner = pot_to_distribute // num_winners # Integer division for satoshis
    
    # Store detailed winner info in PokerHand.winners JSON
    final_winners_json = []

    for winner_data in winners_info:
        user_id = winner_data['user_id']
        user = session.query(User).get(user_id)
        player_state = session.query(PokerPlayerState).filter_by(user_id=user_id, table_id=poker_hand.table_id).first()

        if user and player_state:
            player_state.stack_sats += amount_per_winner # Add winnings to stack at table
            
            transaction = Transaction(
                user_id=user_id,
                amount=amount_per_winner,
                transaction_type='poker_win',
                status='completed',
                details={
                    "hand_id": poker_hand.id,
                    "table_id": poker_hand.table_id,
                    "winning_hand": winner_data.get("winning_hand", "Unknown"),
                    "board_cards": poker_hand.board_cards,
                    "hole_cards": player_state.hole_cards, # Be mindful of showing this in a general transaction log
                    "num_winners_for_pot": num_winners
                }
            )
            session.add(transaction)
            session.add(player_state)
            
            final_winners_json.append({
                "user_id": user_id,
                "username": user.username,
                "amount_won": amount_per_winner,
                "winning_hand": winner_data.get("winning_hand", "Unknown"),
                "best_five_cards": winner_data.get("best_five_cards", [])
            })
        else:
            print(f"Error: Could not find user or player_state for winner ID {user_id} in hand {poker_hand.id}")

    poker_hand.winners = final_winners_json
    poker_hand.end_time = datetime.now(timezone.utc)
    session.add(poker_hand)

    try:
        session.commit()
        print(f"Hand {poker_hand.id}: Pot of {total_pot} (rake: {actual_rake}) distributed to {num_winners} winner(s). Amount per winner: {amount_per_winner}")
    except Exception as e:
        session.rollback()
        print(f"Error distributing pot for hand {poker_hand.id}: {e}")
        # Log error e

# Example of how a full hand might proceed (very simplified flow):
# 1. new_hand_data = start_new_hand(table_id=1)
# 2. If error in new_hand_data, handle it.
# 3. Loop for betting rounds (preflop, flop, turn, river):
#    - Get actions from players (fold, check, bet, call, raise) using handle_* functions.
#    - Update hand state (pot, current_bet, player_stacks, hand_history).
#    - If betting round ends and more than one player remains:
#        - If street is 'preflop', deal flop: deal_community_cards('flop', deck, board)
#        - If street is 'flop', deal turn: deal_community_cards('turn', deck, board)
#        - If street is 'turn', deal river: deal_community_cards('river', deck, board)
# 4. If showdown:
#    - active_players_at_showdown = {ps.user_id: ps.hole_cards for ps in active_players if ps.is_active_in_hand}
#    - winners = _determine_winning_hand(active_players_at_showdown, board_cards)
#    - _distribute_pot(poker_hand_object, winners)
# 5. Mark hand as complete.
# (This is a conceptual flow, actual implementation would be in API endpoints calling these helpers)

# TODO:
# - Robust dealer button logic (store on PokerTable, rotate correctly)
# - Tracking current player to act, current bet to match, min raise amount (likely on PokerHand or PokerTable state cache)
# - Detailed hand history logging within PokerHand.hand_history JSON
# - Full implementation of betting actions (fold, check, call, bet, raise) with validation
# - Full implementation of _validate_bet for different limit types
# - Accurate Pot-Limit Omaha raise calculation in _calculate_pot_limit_raise_sizes
# - Robust hand evaluation in _determine_winning_hand (e.g., integrate 'treys' library)
# - Side pot calculation logic in _distribute_pot
# - Handling for all-in scenarios throughout betting and showdown
# - Player timers and auto-actions (e.g., auto-fold if time runs out)
# - Secure management of hole cards (e.g., only send to the specific player, don't log plaintext if possible long-term)
# - Error handling and transaction rollbacks for database operations.
# - Add logging (import logging) instead of print statements for errors/warnings.
# - Consider atomicity of operations, especially those involving multiple DB updates and financial transactions.
# - Add type hinting more extensively.
# - Unit tests for all functions.
# - Refactor `start_new_hand` to be less monolithic and call sub-functions for clarity.
# - Add foreign key from Transaction to PokerHand (poker_hand_id) for better tracking of financial events related to specific hands.
#   This would require modifying the Transaction model.
# - Clarify if `PokerPlayerState.hole_cards` should be cleared immediately after a hand or kept for history/review features.
#   If kept, ensure strict access controls. For now, it's cleared in `start_new_hand`.
# - `deal_hole_cards` updates `player_state.hole_cards` in memory. Ensure these are persisted to DB in `start_new_hand` after calling it.
#   (Added session.add(ps) for this in start_new_hand)
# - `_deal_card` pops from index 0. If deck is a list, pop() or pop(0) have different performance. For typical deck sizes (52), this is fine.
#   `collections.deque` could be used if performance for dealing from left becomes an issue with very large/many decks.
# - `secrets.SystemRandom().shuffle(deck)` is not a direct method. `random.shuffle(deck, random=secrets.SystemRandom())` could be an option
#   but `random.shuffle(deck)` is generally fine. For more security, one might implement Fisher-Yates with `secrets.randbelow`.
#   Kept `random.shuffle()` for now.
# - The `start_new_hand` function has grown quite large. It would benefit from being broken down.
# - The blind collection in `start_new_hand` should correctly handle cases where players have stacks smaller than the blind amounts (all-in for blinds).
#   (Added min() for this).
# - `handle_stand_up`: If a player stands up mid-hand, their chips in the current pot are forfeited or handled by game rules.
#   The current implementation just removes them. This needs more thought for live games.
# - `_determine_winning_hand` placeholder returns hole cards as `best_five_cards`, which is incorrect. It should be the actual best 5-card hand.
# - Transactions for blinds in `start_new_hand` are commented out. They should be implemented.
# - `Transaction` model might need `poker_hand_id` nullable ForeignKey.
# - `PokerTable` might need fields like `current_dealer_seat_id`, `current_turn_user_id`, `current_bet_to_match`, `last_raise_amount`, `current_pot_this_street`
#   or these could be part of a live game state cache (e.g., Redis) associated with the hand/table rather than SQL columns updated frequently.
#   For now, some of this state is implicitly managed or intended to be added to PokerHand.
# - The `deal_hole_cards` function modifies `player_state.hole_cards` directly. These are SQLAlchemy model instances.
#   The changes are added to the session and committed in `start_new_hand`.
# - `_get_card_value` returns 0 for unknown rank, which could be problematic if bad card data appears.
# - `_distribute_pot` currently doesn't handle side pots at all. This is a major component for multi-way all-in situations.
# - The `winners` list in `PokerHand` stores `amount_won`. This is good.
# - `poker_table.player_states` is accessed. Ensure this relationship is loaded efficiently, e.g. with `joinedload` or `selectinload` where appropriate
#   (added to `start_new_hand` and `handle_sit_down`).
# - `Decimal` was imported but not used. It's good for financial calcs but satoshis are integers, so direct integer math is fine.
# - `handle_sit_down` checks for user already seated at *any* seat at the table. This is correct.

def get_table_state(table_id: int, hand_id: int | None, user_id: int):
    """
    Fetches and returns the comprehensive state of a poker table for a specific user.
    Ensures that sensitive information like other players' hole cards are not revealed.

    Args:
        table_id: The ID of the poker table.
        hand_id: The ID of the current or relevant hand. May be None if no hand active.
        user_id: The ID of the user requesting the state (to tailor information).

    Returns:
        A dictionary containing the table state, or an error dictionary.
    """
    # TODO: Implement actual logic to fetch and format table state.
    # This should include:
    # - PokerTable details (name, blinds, limits, etc.)
    # - Current PokerHand details (pot size, board cards, current turn, last action, etc.)
    # - List of PokerPlayerState for all players at the table:
    #   - For each player: user_id, username, seat_id, stack_sats, status (active, sitting out), last_action.
    #   - CRUCIALLY: Only include hole_cards for the requesting user (user_id). Others should be masked or omitted.
    # - Game-specific state like current bet to match, dealer position, etc.

    session = db.session
    table = session.query(PokerTable).options(
        joinedload(PokerTable.player_states).joinedload(PokerPlayerState.user) # Eager load player states and their users
    ).get(table_id)

    if not table:
        return {"error": f"Table {table_id} not found."}

    current_hand = None
    if hand_id:
        current_hand = session.query(PokerHand).filter_by(id=hand_id, table_id=table_id).first()
        # if not current_hand: # It's okay if a hand_id is passed that doesn't exist or isn't current
            # print(f"Warning: Hand {hand_id} not found for table {table_id}, but returning table state.")

    player_states_serializable = []
    for ps in table.player_states: # Use eager-loaded player_states
        player_data = {
            "user_id": ps.user_id,
            "username": ps.user.username if ps.user else "Unknown", 
            "seat_id": ps.seat_id,
            "stack_sats": ps.stack_sats,
            "is_sitting_out": ps.is_sitting_out,
            "is_active_in_hand": ps.is_active_in_hand,
            "last_action": ps.last_action,
            "hole_cards": None 
        }
        if ps.user_id == user_id and ps.hole_cards:
            player_data["hole_cards"] = ps.hole_cards 
        player_states_serializable.append(player_data)
    
    # Placeholder response
    response_data = {
        "table_id": table.id,
        "table_name": table.name,
        "game_type": table.game_type,
        "limit_type": table.limit_type,
        "small_blind": table.small_blind,
        "big_blind": table.big_blind,
        "max_seats": table.max_seats,
        "is_active": table.is_active,
        "player_states": player_states_serializable,
        "last_updated": datetime.now(timezone.utc).isoformat()
    }

    if current_hand:
        response_data.update({
            "current_hand_id": current_hand.id,
            "pot_size_sats": current_hand.pot_size_sats,
            "board_cards": current_hand.board_cards,
            "hand_history_preview": current_hand.hand_history[-5:] if current_hand.hand_history else [],
            # TODO: Add current_turn_user_id, current_bet_to_match, dealer_seat_id from hand/table state cache
        })
    else:
         response_data.update({
            "current_hand_id": None,
            "pot_size_sats": 0,
            "board_cards": [],
        })

    return response_data

# - `handle_stand_up` returns stack to balance. This is typical. If game has specific rules about leaving mid-game with winnings not yet "banked", that's more complex.
# - Added `session.flush()` in `start_new_hand` to get `new_hand.id` if it were immediately needed for linking transactions,
#   though the current commented-out transaction lines don't strictly require it if committed at the end.
# - `deal_community_cards` does not currently burn a card before dealing flop/turn/river. This is a common rule and can be added by uncommenting `_deal_card(deck)`.
# - The player list for dealing blinds in `start_new_hand` (`sorted_players_by_seat`) uses all active players. This is generally correct.
#   It also correctly handles wrap-around for SB/BB assignment using modulo.
# - Initial hand history in `start_new_hand` is a good start. More detailed actions will be appended by betting functions.
# - `start_new_hand` returns player hole cards to all callers of the function. THIS IS A SECURITY ISSUE for a real API.
#   Hole cards should only be sent to the specific player they belong to, over a secure channel.
#   The return structure needs to be different for actual game clients vs internal state.
#   For now, acknowledging this as a placeholder structure.

print("poker_helper.py structure created with placeholders.")
