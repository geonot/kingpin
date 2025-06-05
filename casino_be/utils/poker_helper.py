import random
import secrets
from datetime import datetime, timezone
from decimal import Decimal # For precise monetary calculations

# treys library for hand evaluation
from treys import Card, Evaluator

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


def _deal_card_from_deck_list(deck_list: list[str]) -> str | None:
    """
    Removes and returns the top card from a given mutable deck list.
    Returns None if deck_list is empty.
    This function MODIFIES the passed deck_list.
    """
    if deck_list:
        return deck_list.pop(0) # Assuming top card is at the start of the list
    return None

def deal_hole_cards(poker_hand: PokerHand, player_states: list[PokerPlayerState]) -> bool:
    """
    Deals two cards to each player in player_states who is is_active_in_hand,
    using the deck from poker_hand.deck_state.
    Updates player_states with hole cards and poker_hand.deck_state.
    Returns True if successful, False if not enough cards.
    """
    if not poker_hand.deck_state:
        print(f"Error: Hand {poker_hand.id} has no deck_state.")
        return False

    # Work with a mutable copy of the deck_state for this operation
    current_deck_list = list(poker_hand.deck_state)

    num_active_players = sum(1 for ps in player_states if ps.is_active_in_hand)
    if len(current_deck_list) < num_active_players * 2:
        print(f"Error: Not enough cards in hand's deck ({len(current_deck_list)}) to deal hole cards to {num_active_players} players.")
        return False

    for _ in range(2): # Deal one card at a time to each player
        for player_state in player_states:
            if player_state.is_active_in_hand:
                card = _deal_card_from_deck_list(current_deck_list) # Modifies current_deck_list
                if card:
                    if player_state.hole_cards is None:
                        player_state.hole_cards = []
                    player_state.hole_cards.append(card)
                else:
                    # This should not happen if initial check passed
                    print("Error: Deck ran out unexpectedly during hole card dealing.")
                    # poker_hand.deck_state is not updated yet, so no rollback of that needed here
                    return False

    # Persist the modified deck back to the hand
    poker_hand.deck_state = current_deck_list
    db.session.add(poker_hand) # Mark poker_hand as dirty to ensure deck_state update is saved
    return True


def deal_community_cards(poker_hand: PokerHand, street: str) -> list[str] | None:
    """
    Deals community cards for the given street using poker_hand.deck_state.
    Updates poker_hand.board_cards and poker_hand.deck_state.
    Returns the list of newly dealt community cards for this street, or None on error.
    """
    if not poker_hand.deck_state:
        print(f"Error: Hand {poker_hand.id} has no deck_state for dealing {street}.")
        return None

    # Work with a mutable copy of the deck_state
    current_deck_list = list(poker_hand.deck_state)

    # Ensure board_cards is a list
    if poker_hand.board_cards is None:
        poker_hand.board_cards = []


    cards_to_deal_count = 0
    if street == 'flop':
        cards_to_deal_count = 3
    elif street == 'turn' or street == 'river':
        cards_to_deal_count = 1
    else:
        print(f"Error: Invalid street name '{street}'.")
        return None

    if len(current_deck_list) < cards_to_deal_count: # Check against the mutable copy
        print(f"Error: Not enough cards in hand's deck to deal {street}.")
        return None

    # Optional: Burn a card. If burning, ensure deck has enough for burn + deal.
    # if len(current_deck_list) < cards_to_deal_count + 1: # If burning
    #     print(f"Error: Not enough cards to burn and deal {street}.")
    #     return None
    # burned_card = _deal_card_from_deck_list(current_deck_list)
    # if burned_card:
    #     poker_hand.hand_history.append({"action": "burn_card", "card": burned_card, "street_before": street})
    # else: # Should not happen if check above is done
    #     print(f"Error: Failed to burn card before {street} deal.")
    #     return None


    newly_dealt_street_cards = []
    for _ in range(cards_to_deal_count):
        card = _deal_card_from_deck_list(current_deck_list) # Modifies current_deck_list
        if card:
            newly_dealt_street_cards.append(card)
        else:
            # Should not happen if initial checks passed
            print(f"Error: Deck ran out unexpectedly during {street} dealing for hand {poker_hand.id}.")
            return None # Indicates critical error
            
    # Update the hand's board_cards and deck_state
    # Ensure poker_hand.board_cards is a list that can be extended
    if not isinstance(poker_hand.board_cards, list): # If it was None or other type
        poker_hand.board_cards = []
    poker_hand.board_cards.extend(newly_dealt_street_cards)
    poker_hand.deck_state = current_deck_list # Persist the deck with cards removed

    db.session.add(poker_hand) # Mark dirty
    return newly_dealt_street_cards


# --- Basic Hand State & Player Management ---

def start_new_hand(table_id: int):
    """
    Starts a new hand at the specified poker table.
    - Fetches table and active players.
    - Resets relevant player states for the new hand.
    - Determines new dealer button position.
    - Assigns and collects Small and Big Blinds.
    - Creates and initializes a new PokerHand record.
    - Creates and shuffles a deck.
    - Deals hole cards to active players.
    - Determines the first player to act pre-flop.
    - Commits all changes to the database.
    """
    session = db.session
    poker_table = session.query(PokerTable).options(
        joinedload(PokerTable.player_states).joinedload(PokerPlayerState.user)
    ).get(table_id)

    if not poker_table or not poker_table.is_active:
        return {"error": "Table not found or inactive."}

    # Filter for players who are present, have a stack, and are not sitting out
    eligible_players_for_hand = [
        ps for ps in poker_table.player_states if ps.user and ps.stack_sats > 0 and not ps.is_sitting_out
    ]

    if len(eligible_players_for_hand) < 2:
        return {"error": "Not enough active players (min 2) to start a hand."}

    # 1. Reset player states for the new hand (for those eligible)
    for ps in eligible_players_for_hand:
        ps.hole_cards = []
        ps.last_action = "prehand_reset" # Or None
        ps.is_active_in_hand = True # Mark them as active for this new hand
        ps.total_invested_this_hand = 0 # Reset for the new hand

    # 2. Determine Dealer Button
    sorted_active_players_by_seat = sorted(eligible_players_for_hand, key=lambda p: p.seat_id)
    num_active_players = len(sorted_active_players_by_seat)

    new_dealer_player = None
    if poker_table.current_dealer_seat_id is None:
        new_dealer_player = sorted_active_players_by_seat[0]
    else:
        current_dealer_idx = -1
        for i, ps in enumerate(sorted_active_players_by_seat):
            if ps.seat_id == poker_table.current_dealer_seat_id:
                current_dealer_idx = i
                break

        if current_dealer_idx == -1: # Previous dealer is no longer active or present
            new_dealer_player = sorted_active_players_by_seat[0]
        else:
            # Move to the next active player circularly
            new_dealer_player = sorted_active_players_by_seat[(current_dealer_idx + 1) % num_active_players]

    poker_table.current_dealer_seat_id = new_dealer_player.seat_id
    # The dealer_player_index is relative to sorted_active_players_by_seat list
    dealer_player_index = sorted_active_players_by_seat.index(new_dealer_player)


    # 3. Determine SB and BB Players & Collect Blinds
    sb_player_state = None
    bb_player_state = None
    actual_sb_amount = 0
    actual_bb_amount = 0
    initial_pot_size_sats = 0
    player_street_investments = {} # For the new hand

    if num_active_players == 2: # Heads-up
        # Dealer is SB, other player is BB
        sb_player_state = new_dealer_player
        sb_player_index = dealer_player_index # Relative to sorted_active_players_by_seat
        bb_player_index = (dealer_player_index + 1) % num_active_players
        bb_player_state = sorted_active_players_by_seat[bb_player_index]
    else: # More than 2 players
        sb_player_index = (dealer_player_index + 1) % num_active_players
        sb_player_state = sorted_active_players_by_seat[sb_player_index]
        bb_player_index = (dealer_player_index + 2) % num_active_players
        bb_player_state = sorted_active_players_by_seat[bb_player_index]

    hand_history_events = [{"action": "start_hand", "timestamp": datetime.now(timezone.utc).isoformat()}]

    # Collect Small Blind
    actual_sb_amount = min(poker_table.small_blind, sb_player_state.stack_sats)
    sb_player_state.stack_sats -= actual_sb_amount
    sb_player_state.total_invested_this_hand += actual_sb_amount # Increment total hand investment
    initial_pot_size_sats += actual_sb_amount
    player_street_investments[str(sb_player_state.user_id)] = actual_sb_amount
    sb_player_state.last_action = f"posts_sb_{actual_sb_amount}"
    session.add(sb_player_state)
    sb_tx = Transaction(user_id=sb_player_state.user_id, amount=-actual_sb_amount, transaction_type='poker_blind', details={"table_id": table_id, "blind_type": "small"})
    session.add(sb_tx)
    hand_history_events.append({
        "user_id": sb_player_state.user_id, "seat_id": sb_player_state.seat_id,
        "action": "post_small_blind", "amount": actual_sb_amount,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    # Collect Big Blind
    actual_bb_amount = min(poker_table.big_blind, bb_player_state.stack_sats)
    bb_player_state.stack_sats -= actual_bb_amount
    bb_player_state.total_invested_this_hand += actual_bb_amount # Increment total hand investment
    initial_pot_size_sats += actual_bb_amount
    player_street_investments[str(bb_player_state.user_id)] = player_street_investments.get(str(bb_player_state.user_id), 0) + actual_bb_amount # Could be same player in HU
    bb_player_state.last_action = f"posts_bb_{actual_bb_amount}"
    session.add(bb_player_state)
    bb_tx = Transaction(user_id=bb_player_state.user_id, amount=-actual_bb_amount, transaction_type='poker_blind', details={"table_id": table_id, "blind_type": "big"})
    session.add(bb_tx)
    hand_history_events.append({
        "user_id": bb_player_state.user_id, "seat_id": bb_player_state.seat_id,
        "action": "post_big_blind", "amount": actual_bb_amount,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    # 4. Create PokerHand record
    current_time = datetime.now(timezone.utc)
    new_hand = PokerHand(
        table_id=table_id,
        pot_size_sats=initial_pot_size_sats,
        start_time=current_time,
        hand_history=hand_history_events, # Initial history with blinds
        board_cards=[],
        player_street_investments=player_street_investments,
        current_bet_to_match=actual_bb_amount, # BB is the initial bet to match
        min_next_raise_amount=poker_table.big_blind, # Standard min raise increment is usually BB size
        last_raiser_user_id=None # No raiser yet, BB is just a forced bet
    )
    session.add(new_hand)
    session.flush() # To get new_hand.id for linking transactions

    sb_tx.poker_hand_id = new_hand.id # Link transaction to hand
    bb_tx.poker_hand_id = new_hand.id # Link transaction to hand

    # 5. Create and Shuffle Deck for the Hand
    initial_deck = _create_deck()
    _shuffle_deck(initial_deck)
    new_hand.deck_state = initial_deck # Store the shuffled deck with the hand

    # 6. Deal Hole Cards (to all players marked active_in_hand, which are eligible_players_for_hand)
    # deal_hole_cards will now use and update new_hand.deck_state
    if not deal_hole_cards(new_hand, eligible_players_for_hand):
        session.rollback() # Rollback all DB changes if dealing fails
        # deal_hole_cards logs specific errors
        return {"error": "Failed to deal hole cards."}
    
    # Player states (hole cards) and new_hand (deck_state) have been modified by deal_hole_cards
    # and added to session if necessary by that function.

    # 7. Determine First Player to Act (Pre-flop)
    first_to_act_player = None
    if num_active_players == 2: # Heads-up, dealer (SB) is first to act pre-flop
        first_to_act_player = sb_player_state
    else: # More than 2 players, player after BB (UTG) is first
        utg_player_index = (bb_player_index + 1) % num_active_players
        first_to_act_player = sorted_active_players_by_seat[utg_player_index]

    new_hand.current_turn_user_id = first_to_act_player.user_id

    # Update hand history with dealing and next to act
    new_hand.hand_history.append({ # Using mutable_json_type, direct append should work and mark dirty
        "action": "deal_hole_cards", 
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "next_to_act": {"user_id": first_to_act_player.user_id, "seat_id": first_to_act_player.seat_id}
    })

    # Set turn_starts_at for the first player to act
    # Conceptual: Assumes PokerPlayerState has a 'turn_starts_at' field (db.Column(db.DateTime, nullable=True))
    if first_to_act_player and hasattr(first_to_act_player, 'turn_starts_at'):
        first_to_act_player.turn_starts_at = datetime.now(timezone.utc)
        session.add(first_to_act_player)
    elif first_to_act_player: # Defensive check if attribute exists
        print(f"Warning: PlayerState for user {first_to_act_player.user_id} does not have 'turn_starts_at' attribute.")
    
    # Final commit for PokerTable, PokerPlayerStates (stacks, actions), new PokerHand, Transactions
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error during start_new_hand commit: {e}")
        return {"error": f"Database error starting new hand: {str(e)}"}

    # TODO: Return a more comprehensive game state for the API, tailored per player.
    # This simplified return is for basic confirmation.
    return {
        "message": "New hand started successfully.",
        "hand_id": new_hand.id,
        "table_id": table_id,
        "dealer_seat": new_dealer_player.seat_id,
        "sb_player_seat": sb_player_state.seat_id, "sb_amount": actual_sb_amount,
        "bb_player_seat": bb_player_state.seat_id, "bb_amount": actual_bb_amount,
        "pot_size": new_hand.pot_size_sats,
        "first_to_act_seat": first_to_act_player.seat_id,
        "board_cards": new_hand.board_cards,
        "active_player_count_in_hand": len(eligible_players_for_hand)
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
        is_sitting_out=False,
        is_active_in_hand=False,
        total_invested_this_hand=0, # Initialize
        hole_cards=[],              # Initialize
        last_action=None,           # Initialize
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
        player_state.last_action = "auto_fold_stand_up"
        # Find the current active hand for this table to log the fold
        current_poker_hand = session.query(PokerHand).filter(
            PokerHand.table_id == table_id,
            PokerHand.status.notin_(['completed', 'showdown']) # Active hand statuses
        ).order_by(PokerHand.start_time.desc()).first()

        if current_poker_hand:
            if current_poker_hand.hand_history is None: # Should be initialized
                current_poker_hand.hand_history = []
            current_poker_hand.hand_history.append({
                "action": "auto_fold_stand_up",
                "user_id": user_id,
                "seat_id": player_state.seat_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            session.add(current_poker_hand)
            # Note: _check_betting_round_completion will be called by the *next* player's action normally.
            # Or, if this player was current_turn_user_id, a more complex game manager would advance turn.
            # For now, this logs the event. The player is marked inactive below.

        player_state.is_active_in_hand = False # Mark as folded essentially
        # Chips in pot are lost for this hand.
        print(f"Player {user_id} stood up and auto-folded from active hand {current_poker_hand.id if current_poker_hand else 'unknown'}.")

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
    poker_hand = session.query(PokerHand).get(hand_id)

    if not player_state:
        return {"error": f"Player {user_id} not found at table {table_id}."}
    if not poker_hand:
        return {"error": f"Hand {hand_id} not found."}
    
    # TODO: Add check if it's actually the player's turn before allowing fold.
    # This might be handled in a higher-level game logic controller.
    # For now, we assume the action is valid if the player is active.

    if not player_state.is_active_in_hand:
        return {"error": f"Player {user_id} is not active in hand {hand_id}."}

    player_state.is_active_in_hand = False
    player_state.last_action = "fold"

    if poker_hand.hand_history is None: # Should have been initialized in start_new_hand
        poker_hand.hand_history = []

    poker_hand.hand_history.append({
        "user_id": user_id,
        "seat_id": player_state.seat_id, # Assuming PokerPlayerState has seat_id
        "action": "fold",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    session.add(player_state)
    session.add(poker_hand)

    try:
        game_flow_result = _check_betting_round_completion(hand_id, user_id, session)
        session.commit()
        return {
            "message": f"User {user_id} folded successfully in hand {hand_id}.",
            "game_flow": game_flow_result
        }
    except Exception as e:
        session.rollback()
        print(f"Error during fold action for user {user_id} in hand {hand_id}: {e}")
        return {"error": "Could not process fold due to a server error.", "details": str(e)}

def handle_check(user_id: int, table_id: int, hand_id: int):
    """Placeholder for handling a player's check action."""
    # TODO: Implement check logic
    # - Validate if check is a legal action (no outstanding bet)
    # - Update PokerHand.hand_history
    # - Determine next player to act or end of betting round
    session = db.session
    player_state = session.query(PokerPlayerState).filter_by(user_id=user_id, table_id=table_id).first()
    poker_hand = session.query(PokerHand).get(hand_id)

    if not player_state:
        return {"error": f"Player {user_id} not found at table {table_id}."}
    if not poker_hand:
        return {"error": f"Hand {hand_id} not found."}

    # TODO: Add check if it's actually the player's turn. (Handled by caller or game flow manager)

    if not player_state.is_active_in_hand:
        return {"error": f"Player {user_id} is not active in hand {hand_id}."}

    # --- Check Legality ---
    # A check is legal if the player's current bet for the street matches the current_bet_to_match.
    # These fields need to be reliably tracked on the PokerHand or related live game state.
    # poker_hand.current_bet_to_match: The highest bet amount any player has made in this betting round.
    # player_invested_this_street: How much this specific player has already bet in this round.

    # Placeholder for where this value would come from.
    # This might be stored in PokerHand.player_street_investments (JSON field) or a separate table.
    # For now, assuming 0 if not explicitly set for the player for this street.
    player_invested_this_street = poker_hand.player_street_investments.get(str(user_id), 0) if poker_hand.player_street_investments else 0
    
    # current_bet_to_match should be a field on PokerHand, updated after each bet/raise.
    # If not present, we'll assume it's 0 for this placeholder.
    current_bet_to_match_on_table = poker_hand.current_bet_to_match if hasattr(poker_hand, 'current_bet_to_match') else 0
    # A more robust system would ensure current_bet_to_match is always present on PokerHand.
    # For newly started hand/street, it would be 0 until a bet is made.

    if player_invested_this_street < current_bet_to_match_on_table:
        return {"error": f"Cannot check. Player {user_id} needs to call {current_bet_to_match_on_table - player_invested_this_street} more."}

    # If check is legal:
    player_state.last_action = "check"

    if poker_hand.hand_history is None: # Should be initialized
        poker_hand.hand_history = []

    poker_hand.hand_history.append({
        "user_id": user_id,
        "seat_id": player_state.seat_id,
        "action": "check",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    session.add(player_state)
    session.add(poker_hand)

    try:
        game_flow_result = _check_betting_round_completion(hand_id, user_id, session)
        session.commit()
        return {
            "message": f"User {user_id} checked successfully in hand {hand_id}.",
            "game_flow": game_flow_result
        }
    except Exception as e:
        session.rollback()
        print(f"Error during check action for user {user_id} in hand {hand_id}: {e}")
        return {"error": "Could not process check due to a server error.", "details": str(e)}

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
    poker_hand = session.query(PokerHand).get(hand_id)
    user = session.query(User).get(user_id) # Needed for Transaction, though balance not debited

    if not player_state:
        return {"error": f"Player {user_id} not found at table {table_id}."}
    if not poker_hand:
        return {"error": f"Hand {hand_id} not found."}
    if not user: # Should not happen if player_state exists
        return {"error": f"User {user_id} not found."}

    # TODO: Add check if it's actually the player's turn. (Handled by caller or game flow manager)

    if not player_state.is_active_in_hand:
        return {"error": f"Player {user_id} is not active in hand {hand_id}."}

    # --- Determine Call Amount & Legality ---
    current_bet_to_match = poker_hand.current_bet_to_match if hasattr(poker_hand, 'current_bet_to_match') else 0

    if poker_hand.player_street_investments is None: # Ensure the dict exists
        poker_hand.player_street_investments = {}
    player_invested_this_street = poker_hand.player_street_investments.get(str(user_id), 0)

    amount_to_call_due = current_bet_to_match - player_invested_this_street

    if amount_to_call_due <= 0:
        # This means player has already matched the bet or even overbet (e.g. if they were BB and it's folded to them, or an error)
        # Or if current_bet_to_match is 0 and player also has 0 invested (can only check or bet)
        return {"error": f"Player {user_id} has no pending bet to call. Amount due is {amount_to_call_due}. Can only check or bet/raise."}

    # --- Handle Stack and All-In ---
    actual_call_amount = min(amount_to_call_due, player_state.stack_sats)
    is_all_in = (actual_call_amount == player_state.stack_sats) and (actual_call_amount < amount_to_call_due)

    # --- Update States ---
    player_state.stack_sats -= actual_call_amount
    player_state.total_invested_this_hand += actual_call_amount # Increment total hand investment

    # Update player's investment for the current street
    poker_hand.player_street_investments[str(user_id)] = player_invested_this_street + actual_call_amount

    poker_hand.pot_size_sats += actual_call_amount

    action_string = "call_all_in" if is_all_in else "call"
    player_state.last_action = f"{action_string}_{actual_call_amount}"


    # --- Create Transaction ---
    # This transaction records the movement of chips from player's table stack to the pot.
    # It does not affect User.balance directly.
    transaction = Transaction(
        user_id=user_id,
        amount=-actual_call_amount, # Negative as it's an outflow from player's perspective at the table
        transaction_type='poker_action_call', # Specific type for table actions
        status='completed',
        details={
            "hand_id": hand_id,
            "table_id": table_id,
            "action": action_string,
            "amount": actual_call_amount,
            "current_bet_to_match": current_bet_to_match,
            "player_invested_this_street_before_call": player_invested_this_street
        }
        # poker_hand_id=hand_id # If Transaction model has this foreign key
    )

    # --- Hand History ---
    if poker_hand.hand_history is None: # Should be initialized
        poker_hand.hand_history = []

    poker_hand.hand_history.append({
        "user_id": user_id,
        "seat_id": player_state.seat_id,
        "action": action_string,
        "amount": actual_call_amount,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    session.add(player_state)
    session.add(poker_hand)
    session.add(transaction)

    try:
        game_flow_result = _check_betting_round_completion(hand_id, user_id, session)
        session.commit()
        return {
            "message": f"User {user_id} {action_string}s {actual_call_amount} successfully in hand {hand_id}.",
            "game_flow": game_flow_result
            }
    except Exception as e:
        session.rollback()
        print(f"Error during call action for user {user_id} in hand {hand_id}: {e}")
        return {"error": "Could not process call due to a server error.", "details": str(e)}


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
    poker_hand = session.query(PokerHand).get(hand_id)
    user = session.query(User).get(user_id) # For transaction record
    poker_table = session.query(PokerTable).get(table_id) # For min_bet (big blind)

    if not player_state:
        return {"error": f"Player {user_id} not found at table {table_id}."}
    if not poker_hand:
        return {"error": f"Hand {hand_id} not found."}
    if not user:
        return {"error": f"User {user_id} not found."}
    if not poker_table:
        return {"error": f"Table {table_id} not found."}

    # TODO: Add check if it's actually the player's turn.

    if not player_state.is_active_in_hand:
        return {"error": f"Player {user_id} is not active in hand {hand_id}."}

    # --- Bet Legality Validation ---
    current_bet_on_table = poker_hand.current_bet_to_match if hasattr(poker_hand, 'current_bet_to_match') else 0
    player_invested_this_street = poker_hand.player_street_investments.get(str(user_id), 0) if poker_hand.player_street_investments else 0

    # Condition for a "bet": current_bet_on_table should be 0, or player must have already matched it if it's from blinds.
    # For simplicity, we'll allow a "bet" if current_bet_on_table is 0.
    # If current_bet_on_table > 0, it should ideally be a "raise".
    # This logic might need refinement based on how blinds are posted and if they count as first bet.
    # Assuming a "bet" action implies opening the betting for this round or if previous bets are all matched.
    if current_bet_on_table > 0 and player_invested_this_street < current_bet_on_table:
        return {"error": f"Cannot bet. There is an outstanding bet of {current_bet_on_table} to call or raise."}


    # Validate bet amount
    if amount <= 0:
        return {"error": "Bet amount must be positive."}

    min_bet_amount = poker_table.big_blind # Simplified minimum bet
    # TODO: More complex min bet logic for specific game states (e.g. post-flop must be BB, or fixed limit rules)

    if amount < min_bet_amount and amount < player_state.stack_sats : # Allow all-in for less than min bet
         return {"error": f"Bet amount {amount} is less than minimum bet of {min_bet_amount}."}


    # --- Determine Actual Bet Amount (Handle All-In) ---
    actual_bet_amount_put_in_pot = min(amount, player_state.stack_sats) # This is the amount taken from stack

    # The "bet amount" for game rules is the total new money player is making it to.
    # If player already has money in (e.g. straddle, or re-opening betting), this needs care.
    # For a simple opening bet, actual_bet_amount_put_in_pot is the bet size.

    is_all_in = (actual_bet_amount_put_in_pot == player_state.stack_sats) and (actual_bet_amount_put_in_pot < amount if amount else True)


    # --- Update States ---
    player_state.stack_sats -= actual_bet_amount_put_in_pot
    player_state.total_invested_this_hand += actual_bet_amount_put_in_pot # Increment total hand investment

    if poker_hand.player_street_investments is None:
        poker_hand.player_street_investments = {}

    # Total investment by player in this street becomes this bet amount
    poker_hand.player_street_investments[str(user_id)] = player_invested_this_street + actual_bet_amount_put_in_pot

    poker_hand.pot_size_sats += actual_bet_amount_put_in_pot

    # This bet now becomes the amount to match for subsequent players
    poker_hand.current_bet_to_match = poker_hand.player_street_investments[str(user_id)]

    # Mark this player as the last aggressor (raiser or better)
    if hasattr(poker_hand, 'last_raiser_user_id'): # Add this field to PokerHand model
        poker_hand.last_raiser_user_id = user_id
    else:
        # Log or handle missing attribute - for now, we'll skip if not present
        print(f"Warning: PokerHand model missing 'last_raiser_user_id'. Skipping update.")

    # The minimum next raise would be at least this bet amount on top of current_bet_to_match
    if hasattr(poker_hand, 'min_next_raise_amount'): # Add this field to PokerHand model
        poker_hand.min_next_raise_amount = actual_bet_amount_put_in_pot # Simplified: The size of this bet itself.
                                                                # More precisely: current_bet_to_match (after this bet) + this_bet_size
    else:
        print(f"Warning: PokerHand model missing 'min_next_raise_amount'. Skipping update.")

    action_string = "bet_all_in" if is_all_in else "bet"
    player_state.last_action = f"{action_string}_{actual_bet_amount_put_in_pot}"

    # --- Create Transaction ---
    transaction = Transaction(
        user_id=user_id,
        amount=-actual_bet_amount_put_in_pot,
        transaction_type='poker_action_bet',
        status='completed',
        details={
            "hand_id": hand_id,
            "table_id": table_id,
            "action": action_string,
            "amount": actual_bet_amount_put_in_pot
        }
        # poker_hand_id=hand_id # If Transaction model has this foreign key
    )

    # --- Hand History ---
    if poker_hand.hand_history is None:
        poker_hand.hand_history = []

    poker_hand.hand_history.append({
        "user_id": user_id,
        "seat_id": player_state.seat_id,
        "action": action_string,
        "amount": actual_bet_amount_put_in_pot,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    session.add(player_state)
    session.add(poker_hand)
    session.add(transaction)

    try:
        game_flow_result = _check_betting_round_completion(hand_id, user_id, session)
        session.commit()
        return {
            "message": f"User {user_id} {action_string}s {actual_bet_amount_put_in_pot} successfully in hand {hand_id}.",
            "game_flow": game_flow_result
        }
    except Exception as e:
        session.rollback()
        print(f"Error during bet action for user {user_id} in hand {hand_id}: {e}")
        return {"error": "Could not process bet due to a server error.", "details": str(e)}

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
    poker_hand = session.query(PokerHand).get(hand_id)
    user = session.query(User).get(user_id) # For transaction record
    poker_table = session.query(PokerTable).get(table_id) # For table rules like min_bet, big_blind

    if not player_state:
        return {"error": f"Player {user_id} not found at table {table_id}."}
    if not poker_hand:
        return {"error": f"Hand {hand_id} not found."}
    if not user:
        return {"error": f"User {user_id} not found."}
    if not poker_table:
        return {"error": f"Table {table_id} not found."}

    # TODO: Add check if it's actually the player's turn.

    if not player_state.is_active_in_hand:
        return {"error": f"Player {user_id} is not active in hand {hand_id}."}

    # --- Raise Legality Validation ---
    # Ensure poker_hand.player_street_investments is initialized
    if poker_hand.player_street_investments is None:
        poker_hand.player_street_investments = {}

    player_invested_this_street = poker_hand.player_street_investments.get(str(user_id), 0)

    # current_bet_to_match is the current highest total bet a player has made in this street.
    # It should be > 0 for a raise to be possible.
    previous_bet_to_match = poker_hand.current_bet_to_match if hasattr(poker_hand, 'current_bet_to_match') else 0
    if previous_bet_to_match == 0:
        return {"error": "Cannot raise. No prior bet in this round. Use 'bet' action instead."}

    # The total amount the player is raising TO must be greater than their current investment.
    if amount <= player_invested_this_street:
        return {"error": f"Raise amount ({amount}) must be greater than current investment this street ({player_invested_this_street})."}

    # The total amount must be greater than the current bet to match.
    if amount <= previous_bet_to_match:
         return {"error": f"Raise amount ({amount}) must be greater than the current bet to match ({previous_bet_to_match})."}


    # Minimum Raise Increment Validation (Simplified)
    # min_next_raise_amount on PokerHand should store the size of the last significant bet/raise.
    # A new raise must be at least that increment on top of the previous_bet_to_match.
    min_raise_increment_required = poker_hand.min_next_raise_amount if hasattr(poker_hand, 'min_next_raise_amount') and poker_hand.min_next_raise_amount is not None else poker_table.big_blind

    required_total_raise_amount = previous_bet_to_match + min_raise_increment_required

    is_going_all_in_for_less_than_min_raise = (amount < required_total_raise_amount) and (amount == (player_invested_this_street + player_state.stack_sats))

    if amount < required_total_raise_amount and not is_going_all_in_for_less_than_min_raise:
        return {"error": f"Raise to {amount} is too small. Must raise to at least {required_total_raise_amount} (current bet {previous_bet_to_match} + min increment {min_raise_increment_required})."}

    # --- Determine Actual Amounts to Add (Handle All-In) ---
    # `amount` is the total sum the player wants their current street investment to be.
    amount_player_needs_to_add = amount - player_invested_this_street

    if amount_player_needs_to_add <= 0: # Should be caught by earlier checks, but good safeguard
        return {"error": "Internal error: calculated amount to add is not positive."}

    actual_amount_added_to_pot = min(amount_player_needs_to_add, player_state.stack_sats)

    final_player_investment_this_street = player_invested_this_street + actual_amount_added_to_pot
    is_all_in = (actual_amount_added_to_pot == player_state.stack_sats) and (actual_amount_added_to_pot < amount_player_needs_to_add)

    # --- Update States ---
    player_state.stack_sats -= actual_amount_added_to_pot
    player_state.total_invested_this_hand += actual_amount_added_to_pot # Increment total hand investment
    poker_hand.player_street_investments[str(user_id)] = final_player_investment_this_street
    poker_hand.pot_size_sats += actual_amount_added_to_pot

    # The new current_bet_to_match is the total amount this player has now invested in the street.
    poker_hand.current_bet_to_match = final_player_investment_this_street

    # Update who made the last raise and the size of that raise (for next min-raise calculation)
    if hasattr(poker_hand, 'last_raiser_user_id'):
        poker_hand.last_raiser_user_id = user_id
    else:
        print("Warning: PokerHand model missing 'last_raiser_user_id'.")
        
    new_raise_increment_size = final_player_investment_this_street - previous_bet_to_match
    if hasattr(poker_hand, 'min_next_raise_amount'):
        poker_hand.min_next_raise_amount = new_raise_increment_size
    else:
        print("Warning: PokerHand model missing 'min_next_raise_amount'.")

    action_string = "raise_all_in" if is_all_in else "raise"
    player_state.last_action = f"{action_string}_to_{final_player_investment_this_street}"

    # --- Create Transaction ---
    transaction = Transaction(
        user_id=user_id,
        amount=-actual_amount_added_to_pot, # Debit from player's table stack
        transaction_type='poker_action_raise',
        status='completed',
        details={
            "hand_id": hand_id,
            "table_id": table_id,
            "action": action_string,
            "raised_to_amount": final_player_investment_this_street, # Total investment this street
            "amount_added_to_pot": actual_amount_added_to_pot
        }
    )

    # --- Hand History ---
    if poker_hand.hand_history is None:
        poker_hand.hand_history = []

    poker_hand.hand_history.append({
        "user_id": user_id,
        "seat_id": player_state.seat_id,
        "action": action_string,
        "amount": final_player_investment_this_street, # Record the total amount raised to
        "added_to_pot": actual_amount_added_to_pot,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    session.add(player_state)
    session.add(poker_hand)
    session.add(transaction)

    try:
        game_flow_result = _check_betting_round_completion(hand_id, user_id, session)
        session.commit()
        return {
            "message": f"User {user_id} {action_string}s to {final_player_investment_this_street} successfully in hand {hand_id}.",
            "game_flow": game_flow_result
        }
    except Exception as e:
        session.rollback()
        print(f"Error during raise action for user {user_id} in hand {hand_id}: {e}")
        return {"error": "Could not process raise due to a server error.", "details": str(e)}


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
    """
    Validates a bet or raise amount based on game rules.
    `action_amount` is the total amount the player's investment for the current street will be if the action is valid.

    Args:
        player_state (PokerPlayerState): The state of the player making the action.
        action_amount (int): The total cumulative amount the player intends to have invested in the current street after this action.
        current_bet_to_match (int): The current highest total bet any player has made in this street.
        min_raise_amount_total (int): For a raise, this is the minimum total amount the player's bet must reach for the street.
                                     (i.e., current_bet_to_match + last valid raise increment).
        limit_type (str): "no_limit", "pot_limit", "fixed_limit".
        table_pot_size_if_pot_limit (int): Current total pot size in the middle, needed for Pot-Limit max raise calculation.
        player_amount_invested_this_street (int): How much the player has already invested in this street before this action.
        min_bet_this_game (int): The minimum size of an opening bet (e.g., the Big Blind).

    Returns:
        tuple[bool, str]: (is_valid, message). Message explains why invalid or confirms validity type (e.g. "all-in").
    """

    chips_for_this_action = action_amount - player_amount_invested_this_street

    if chips_for_this_action < 0:
        return False, "Invalid action: total bet amount is less than already invested."

    if chips_for_this_action > player_state.stack_sats:
        return False, f"Insufficient stack. Trying to bet {chips_for_this_action}, but only have {player_state.stack_sats}."

    is_all_in = (chips_for_this_action == player_state.stack_sats)

    # --- Call / Check Path ---
    if action_amount < current_bet_to_match:
        if is_all_in: # All-in call for less than full amount
            return True, "All-in call for less." # Valid, but specific type
        return False, f"Amount {action_amount} is less than current bet to match {current_bet_to_match}."

    if action_amount == current_bet_to_match:
        if chips_for_this_action == 0: # It's a check
            return True, "Check."
        else: # It's a call of the exact amount
            return True, "Call."

    # --- Bet / Raise Path (action_amount > current_bet_to_match) ---
    is_opening_bet = (current_bet_to_match == 0) or \
                     (current_bet_to_match == min_bet_this_game and player_amount_invested_this_street == current_bet_to_match and chips_for_this_action > 0) # e.g. BB raising themselves if allowed

    if limit_type == "no_limit":
        if is_opening_bet:
            # Bet size is chips_for_this_action
            if chips_for_this_action < min_bet_this_game and not is_all_in:
                return False, f"Opening bet ({chips_for_this_action}) is less than minimum bet ({min_bet_this_game})."
            return True, "Valid No-Limit opening bet."
        else: # Raise
            if action_amount < min_raise_amount_total and not is_all_in:
                 return False, f"Raise to {action_amount} is less than minimum required raise total of {min_raise_amount_total}."
            # Ensure raise is by at least the last bet/raise amount (min_raise_amount_total - current_bet_to_match)
            # This is implicitly covered if min_raise_amount_total was set correctly.
            return True, "Valid No-Limit raise."

    elif limit_type == "pot_limit":
        # min_bet_this_game often serves as the min_valid_raise_increment for the first raise,
        # or it could be derived from poker_hand.min_next_raise_amount if available.
        # For _calculate_pot_limit_raise_sizes, min_valid_raise_increment is key.
        # Assuming min_bet_this_game can stand in for a basic min raise increment here.
        # A more robust system would pass the true min_next_raise_amount (last bet/raise size) from PokerHand.

        min_raise_target, max_raise_target = _calculate_pot_limit_raise_sizes(
            player_current_stack=player_state.stack_sats,
            player_invested_this_street=player_amount_invested_this_street,
            current_pot_total=table_pot_size_if_pot_limit,
            bet_to_match_this_street=current_bet_to_match,
            min_valid_raise_increment=min_bet_this_game # Simplified: Using BB as min raise increment for now
        )

        if is_opening_bet: # Pot limit opening bet
            if chips_for_this_action < min_bet_this_game and not is_all_in:
                 return False, f"Opening Pot-Limit bet ({chips_for_this_action}) is less than minimum bet ({min_bet_this_game})."
            if action_amount > max_raise_target and not is_all_in : # Max pot opening bet
                 return False, f"Opening Pot-Limit bet ({action_amount}) exceeds max pot limit ({max_raise_target})."
            return True, "Valid Pot-Limit opening bet."
        else: # Pot limit raise
            if action_amount < min_raise_target and not is_all_in:
                return False, f"Raise to {action_amount} is less than Pot-Limit min raise target of {min_raise_target}."
            if action_amount > max_raise_target and not is_all_in:
                return False, f"Raise to {action_amount} exceeds Pot-Limit max raise target of {max_raise_target}."

            # If all-in, it must still be a valid raise (i.e. action_amount > current_bet_to_match)
            if is_all_in and action_amount <= current_bet_to_match:
                 return False, f"All-in raise to {action_amount} does not exceed current bet {current_bet_to_match}."
            return True, "Valid Pot-Limit raise."

    elif limit_type == "fixed_limit":
        # TODO: Implement detailed Fixed-Limit validation
        # - Bet/raise amounts must be specific fixed values based on street and number of raises.
        # - Typically, pre-flop & flop use lower tier, turn & river use upper tier.
        # - Limit on number of raises per round (e.g., 1 bet and 3 or 4 raises).
        if is_opening_bet:
            if chips_for_this_action != min_bet_this_game and not is_all_in: # min_bet_this_game is the fixed bet amount
                return False, f"Fixed-Limit bet must be exactly {min_bet_this_game} (unless all-in)."
        else: # Raise
            # Fixed-Limit raise increment is usually same as fixed bet amount for that street
            expected_raise_total = current_bet_to_match + min_bet_this_game
            if action_amount != expected_raise_total and not is_all_in:
                 return False, f"Fixed-Limit raise must make total {expected_raise_total} (current {current_bet_to_match} + increment {min_bet_this_game})."
            # TODO: Check cap on number of raises.
        return True, "Fixed-Limit validation (basic stub - check amounts)." # Placeholder

    return False, f"Unknown limit type: {limit_type}"


def _calculate_pot_limit_raise_sizes(
    player_current_stack: int,
    player_invested_this_street: int,
    current_pot_total: int,
    bet_to_match_this_street: int,
    min_valid_raise_increment: int
) -> tuple[int, int]:
    """
    Calculates the minimum and maximum total bet amounts for a player making a Pot-Limit raise.

    Args:
        player_current_stack: The current amount of chips the player has available.
        player_invested_this_street: The amount the player has already invested in the pot during the current betting round.
        current_pot_total: The total amount of chips in the pot from all previous streets and actions in the current street
                           BEFORE this player makes their call or raise.
        bet_to_match_this_street: The current highest total investment any player has made in this betting street.
                                  The acting player must at least match this amount to stay in.
        min_valid_raise_increment: The minimum additional amount required for a valid raise beyond the 'bet_to_match_this_street'.
                                   (e.g., Big Blind, or the size of the last valid bet/raise).

    Returns:
        A tuple (min_raise_target_total_investment, max_raise_target_total_investment).
        - min_raise_target_total_investment: The minimum total amount the player's investment for this street
                                             must be if they make a valid minimum raise.
        - max_raise_target_total_investment: The maximum total amount the player's investment for this street
                                             can be if they make a valid pot-sized raise.
        Both values are capped by the player's effective all-in amount for the street.
        If no valid raise is possible (e.g., player stack too small to meet min increment),
        the returned min_raise_target might be less than or equal to bet_to_match_this_street,
        indicating only a call (or all-in call) is possible.
    """

    # Amount player needs to add to just call the current bet_to_match_this_street
    amount_to_call_action = bet_to_match_this_street - player_invested_this_street
    if amount_to_call_action < 0: # Should not happen if logic is correct before calling this
        amount_to_call_action = 0


    # 1. Calculate Minimum Raise Target
    # The minimum total investment a player must make for a valid raise.
    min_raise_target_total_investment = bet_to_match_this_street + min_valid_raise_increment

    # Calculate the actual additional chips needed for this minimum raise action
    additional_chips_for_min_raise = min_raise_target_total_investment - player_invested_this_street

    # Cap this by player's current stack. Player cannot add more than they have.
    actual_additional_for_min_raise = min(player_current_stack, additional_chips_for_min_raise)

    # The effective minimum total investment player can make if they choose to min-raise (could be all-in)
    effective_min_raise_total_street_investment = player_invested_this_street + actual_additional_for_min_raise


    # 2. Calculate Maximum Raise Target (Pot-Sized Raise)
    # "The 'pot' in this case is defined as the total of the active pot, plus all bets on the table,
    #  plus the amount the active player must first call before raising."
    # pot_total_before_this_player_acts = current_pot_total (this should include all previous bets)
    # amount_player_calls = amount_to_call_action

    # Pot size for calculation = current_pot_total (all chips in pot now) + amount_to_call_action (the call this player makes)
    # This is the size of the pot if the current player just calls.
    pot_size_if_player_calls = current_pot_total + amount_to_call_action

    # The player can raise BY this amount (pot_size_if_player_calls), on top of their call.
    value_of_pot_raise_increment = pot_size_if_player_calls

    # Total additional chips for this pot-sized raise action
    additional_chips_for_pot_raise = amount_to_call_action + value_of_pot_raise_increment

    # Cap this by player's current stack
    actual_additional_for_pot_raise = min(player_current_stack, additional_chips_for_pot_raise)

    # The effective maximum total investment player can make if they choose to pot-raise (could be all-in)
    effective_max_raise_total_street_investment = player_invested_this_street + actual_additional_for_pot_raise

    # Ensure min raise is not more than max raise (can happen if stack is very small)
    # Also, ensure the "min raise" is actually a raise (i.e. results in total investment > bet_to_match_this_street)
    # If effective_min_raise_total_street_investment <= bet_to_match_this_street, it means player cannot even make the min_raise_increment.
    # In this case, their only "raise" option is all-in, if that all-in is > bet_to_match_this_street.
    # If their all-in is <= bet_to_match_this_street, they can only call all-in.

    # If the calculated minimum raise is not even possible or not a real raise,
    # then the only "raise" is an all-in, provided that all-in is greater than the call amount.
    if effective_min_raise_total_street_investment <= bet_to_match_this_street:
        # If going all-in is more than just calling, that's the only "raise".
        all_in_total_investment = player_invested_this_street + player_current_stack
        if all_in_total_investment > bet_to_match_this_street:
            # The only raise possible is all-in. Min and Max raise are the same: all-in.
            return (all_in_total_investment, all_in_total_investment)
        else:
            # No raise is possible, only a call (or all-in call).
            # Return values that make it impossible to raise.
            # Or, the calling function should check if min_raise_target > bet_to_match_this_street.
            # For now, return the (possibly invalid as a "raise") min and the capped max.
            # The handler_raise function will do further validation.
             return (effective_min_raise_total_street_investment, max(effective_min_raise_total_street_investment, effective_max_raise_total_street_investment))


    return (effective_min_raise_total_street_investment, effective_max_raise_total_street_investment)


# --- Hand Evaluation ---

def _determine_winning_hand(player_hole_cards_map: dict[int, list[str]], board_cards_str: list[str]):
    """
    Determines the winning hand(s) from players who went to showdown using the 'treys' library.
    player_hole_cards_map: {user_id_1: ["AH", "KH"], user_id_2: ["7D", "8D"]}
    board_cards_str: ["5S", "6S", "7S", "QD", "JC"] (String representation)

    Returns: A list of winning player dicts, e.g.,
             [{"user_id": X, "winning_hand": "Full House", "best_five_cards": ["AH", "KH", "5S", "6S", "7S"]}]
             Handles split pots by returning multiple players if they tie.
             "best_five_cards" will contain the player's hole cards and the board cards as a proxy,
             as treys library doesn't directly return the exact 5 cards forming the best hand.
    """
    if not player_hole_cards_map:
        return []

    evaluator = Evaluator()
    
    # Convert board cards from string to treys.Card objects
    # treys expects card strings like 'Ah', 'Ks', 'Td', '2c' (rank first, then suit, lowercase)
    # Our format is 'HA', 'SK', 'DT', 'C2' (suit first, then rank, uppercase)
    # We need to convert: e.g., "HA" -> "Ah", "S2" -> "2s"

    # Helper to convert our card format to treys format
    def to_treys_card_str(card_str: str) -> str:
        suit_map = {'H': 'h', 'D': 'd', 'C': 'c', 'S': 's'}
        # Our format: SUIT RANK e.g. HA, S2
        # Treys format: RANK SUIT e.g. Ah, 2s
        original_suit = card_str[0]
        original_rank = card_str[1:]
        return original_rank + suit_map[original_suit]

    try:
        board = [Card.from_string(to_treys_card_str(c)) for c in board_cards_str]
    except Exception as e:
        # Log error: Invalid card string in board_cards
        print(f"Error converting board cards for treys: {board_cards_str} - {e}")
        # Consider how to handle this - perhaps invalidate the hand or return error
        return []

    best_score = float('inf')  # Lower score is better in treys
    winners = []

    for user_id, hole_cards_str_list in player_hole_cards_map.items():
        if not hole_cards_str_list or len(hole_cards_str_list) != 2:
            # Log warning or skip player
            print(f"Warning: User {user_id} has invalid hole cards: {hole_cards_str_list}")
            continue

        try:
            # Ensure hole_cards_str is a list of strings, then convert
            hand = [Card.from_string(to_treys_card_str(c)) for c in hole_cards_str_list]
        except Exception as e:
            # Log error: Invalid card string in hole_cards
            print(f"Error converting hole cards for user {user_id}: {hole_cards_str_list} - {e}")
            continue # Skip this player

        # Evaluate the hand (board + player's hole cards)
        # treys evaluate function takes board and hand (player's cards)
        score = evaluator.evaluate(board, hand)
        hand_class_str = evaluator.class_to_string(evaluator.get_rank_class(score))

        # For "best_five_cards", we'll just return the combination of hole + board as a proxy.
        # A more advanced implementation might try to find the exact 5 cards.
        combined_cards_str = hole_cards_str_list + board_cards_str

        # DEBUG LOG: Original line logged hole cards: print(f"User {user_id}, Hole: {hole_cards_str_list}, Board: {board_cards_str}, Score: {score}, Hand Class: {hand_class_str}")
        # Hole cards redacted for security in general logging:
        print(f"User {user_id} evaluation - Board: {board_cards_str}, Score: {score}, Hand Class: {hand_class_str}")

        if score < best_score:
            best_score = score
            winners = [{
                "user_id": user_id,
                "winning_hand": hand_class_str,
                "best_five_cards": combined_cards_str, # Proxy
                "score": score # For debugging or advanced tie-breaking if needed
            }]
        elif score == best_score:
            winners.append({
                "user_id": user_id,
                "winning_hand": hand_class_str,
                "best_five_cards": combined_cards_str, # Proxy
                "score": score
            })

    # Remove score from the final output as it's not part of the required return structure
    for winner in winners:
        del winner["score"]
        
    return winners


# --- Showdown & Payout Stubs ---

def _distribute_pot(poker_hand: PokerHand, showdown_player_states: list[PokerPlayerState]):
    """
    Distributes the pot(s) to the winner(s), handling side pots.
    Updates PokerHand with rake and winner details.
    Creates Transaction records for winnings.

    Args:
        poker_hand (PokerHand): The PokerHand object for which to distribute pots.
        showdown_player_states (list[PokerPlayerState]): A list of PokerPlayerState objects for all players
                                                        who reached showdown (i.e., did not fold and have cards).
                                                        It's assumed these states have `hole_cards` and an accurate
                                                        `total_invested_this_hand` attribute or a reliable way to compute it.
    """
    session = db.session
    poker_table = session.query(PokerTable).get(poker_hand.table_id)

    # --- 1. Prepare Player Data for Showdown ---
    # Each element: {'user_id': int, 'total_invested': int, 'hole_cards_str': list[str], 'player_state_obj': PokerPlayerState}
    players_at_showdown = []
    for ps in showdown_player_states:
        if not ps.hole_cards: # Should not happen for showdown players
            print(f"Warning: Player {ps.user_id} at showdown has no hole cards. Skipping for pot distribution.")
            continue

        # TODO: CRITICAL - Ensure `ps.total_invested_this_hand` is accurately populated before calling _distribute_pot.
        # This value represents the total amount a player has put into the pot for this entire hand.
        # For this implementation, we'll assume it exists and is correct.
        # If not, it needs to be calculated by summing contributions from hand_history or another tracking mechanism.
        total_invested = getattr(ps, 'total_invested_this_hand', 0)
        if total_invested == 0 and poker_hand.pot_size_sats > 0 : # Player must have invested something if pot > 0 (e.g. blinds)
            # This is a fallback/warning. Real calculation is needed.
            print(f"Warning: Player {ps.user_id} has 0 total_invested_this_hand. This might lead to incorrect side pot calculation.")
            # As a rough placeholder if total_invested_this_hand is missing, try to use current street investments (highly inaccurate for multi-street)
            # if poker_hand.player_street_investments and str(ps.user_id) in poker_hand.player_street_investments:
            #    total_invested = poker_hand.player_street_investments[str(ps.user_id)]


        players_at_showdown.append({
            'user_id': ps.user_id,
            'total_invested': total_invested,
            'hole_cards_str': ps.hole_cards,
            'player_state_obj': ps # Keep direct access to the player state object
        })

    if not players_at_showdown:
        print(f"Error: No players at showdown for hand {poker_hand.id}. Pot distribution cannot occur.")
        # This typically means one player won by default, which should be handled before calling _distribute_pot.
        # However, if called, ensure pot is returned or handled.
        # For now, if pot exists, it implies an error state or unhandled scenario.
        if poker_hand.pot_size_sats > 0:
            print(f"Error: Pot for hand {poker_hand.id} is {poker_hand.pot_size_sats} but no showdown players identified in _distribute_pot.")
        return

    # Sort players by their total investment in ascending order
    players_at_showdown.sort(key=lambda x: x['total_invested'])

    # --- 2. Rake Calculation ---
    total_pot_value = poker_hand.pot_size_sats
    actual_rake = 0
    if total_pot_value > 0 and poker_table:
        # Ensure rake_percentage and max_rake_sats are Decimal and int respectively, or provide defaults.
        rake_percentage_from_table = getattr(poker_table, 'rake_percentage', Decimal("0.00"))
        if not isinstance(rake_percentage_from_table, Decimal):
            try:
                rake_percentage_from_table = Decimal(str(rake_percentage_from_table)) # Attempt conversion
            except:
                rake_percentage_from_table = Decimal("0.00") # Fallback

        max_rake_cap_from_table = getattr(poker_table, 'max_rake_sats', 0)
        if not isinstance(max_rake_cap_from_table, int):
            try:
                max_rake_cap_from_table = int(max_rake_cap_from_table) # Attempt conversion
            except:
                max_rake_cap_from_table = 0 # Fallback (effectively no cap if rake is percentage based and this is 0)


        if rake_percentage_from_table > Decimal("0.00"):
            calculated_rake = int(Decimal(total_pot_value) * rake_percentage_from_table)

            if max_rake_cap_from_table > 0: # Apply cap only if it's a positive value
                actual_rake = min(calculated_rake, max_rake_cap_from_table)
            else: # No cap defined (or cap is 0), so take the full calculated percentage rake
                actual_rake = calculated_rake

        # Ensure rake is not negative and does not exceed the total pot value itself.
        actual_rake = max(0, actual_rake)
        actual_rake = min(actual_rake, total_pot_value)

    poker_hand.rake_sats = actual_rake
    distributable_pot_overall = total_pot_value - actual_rake
    if distributable_pot_overall < 0:
        distributable_pot_overall = 0 # Pot cannot be negative

    # --- 3. Create and Calculate Pots (Main and Side Pots) ---
    # pots is a list of dictionaries: {'amount': int, 'eligible_user_ids': set[int], 'description': str}
    created_pots = []
    processed_investment_level = 0 # Tracks the investment level already accounted for in previous pots

    # Iterate through unique investment levels to define pot layers
    unique_investment_caps = sorted(list(set(p['total_invested'] for p in players_at_showdown)))

    for cap_level in unique_investment_caps:
        if cap_level <= processed_investment_level:
            continue

        # Amount each contributing player puts into this specific layer of the pot
        contribution_per_player_this_layer = cap_level - processed_investment_level

        # Identify players who contribute to this layer
        players_contributing_to_this_layer = []
        for p_data in players_at_showdown:
            if p_data['total_invested'] >= processed_investment_level: # Must have met previous levels
                # How much this player actually adds to *this specific layer*
                actual_added_by_player_to_layer = min(contribution_per_player_this_layer, p_data['total_invested'] - processed_investment_level)
                if actual_added_by_player_to_layer > 0:
                    players_contributing_to_this_layer.append(p_data['user_id'])

        if not players_contributing_to_this_layer: # Should not happen if cap_level > processed_investment_level
            continue

        # The value of this pot layer is sum of contributions to it
        value_of_this_pot_layer = contribution_per_player_this_layer * len(players_contributing_to_this_layer)

        # Deduct from overall distributable pot (ensure no overallocation)
        value_to_assign_to_this_pot = min(value_of_this_pot_layer, distributable_pot_overall - sum(p['amount'] for p in created_pots))

        if value_to_assign_to_this_pot > 0:
            pot_description = f"Main Pot (up to {cap_level})" if not created_pots else f"Side Pot for investments up to {cap_level}"
            created_pots.append({
                'amount': value_to_assign_to_this_pot,
                'eligible_user_ids': set(players_contributing_to_this_layer), # Players who put money into this layer are eligible
                'description': pot_description
            })

        processed_investment_level = cap_level

    # If sum of created pots is less than total distributable (e.g. rounding, or complex all-ins not perfectly layered by unique caps)
    # Add remainder to the first pot (main pot) - this is a simplification.
    current_sum_of_created_pots = sum(p['amount'] for p in created_pots)
    if distributable_pot_overall > current_sum_of_created_pots and created_pots:
        remainder = distributable_pot_overall - current_sum_of_created_pots
        created_pots[0]['amount'] += remainder
        print(f"Hand {poker_hand.id}: Added remainder of {remainder} to the main pot.")
    elif not created_pots and distributable_pot_overall > 0 and players_at_showdown:
         # Fallback if unique_investment_caps logic was empty but pot exists (e.g. all invested same)
        created_pots.append({
            'amount': distributable_pot_overall,
            'eligible_user_ids': {p['user_id'] for p in players_at_showdown},
            'description': "Main Pot (all players)"
        })


    # --- 4. Determine Winners and Distribute Each Pot ---
    final_hand_winners_summary = [] # To be stored in PokerHand.winners

    for pot_info in created_pots:
        pot_amount_to_distribute = pot_info['amount']
        eligible_ids_this_pot = pot_info['eligible_user_ids']
        pot_description = pot_info['description']

        if pot_amount_to_distribute <= 0:
            continue

        # Get hole cards for players eligible for *this* pot
        player_hole_cards_map_for_this_pot = {
            p['user_id']: p['hole_cards_str']
            for p in players_at_showdown if p['user_id'] in eligible_ids_this_pot and p['hole_cards_str']
        }

        if not player_hole_cards_map_for_this_pot:
            print(f"Warning: No eligible players with cards for pot '{pot_description}'. Amount {pot_amount_to_distribute} unawarded from this pot.")
            continue

        # Determine winner(s) for this specific pot
        winners_of_this_pot = _determine_winning_hand(player_hole_cards_map_for_this_pot, poker_hand.board_cards)

        if not winners_of_this_pot:
            print(f"Warning: _determine_winning_hand returned no winners for pot '{pot_description}'. Amount {pot_amount_to_distribute} unawarded.")
            continue

        num_winners_this_pot = len(winners_of_this_pot)
        amount_per_winner_this_pot = pot_amount_to_distribute // num_winners_this_pot
        # TODO: Handle odd chips if pot doesn't split evenly (e.g., award to player closest to button)

        for winner_detail in winners_of_this_pot:
            winner_user_id = winner_detail['user_id']

            # Find the original PokerPlayerState object for the winner to update stack
            winner_player_state_obj = next((p['player_state_obj'] for p in players_at_showdown if p['user_id'] == winner_user_id), None)
            winner_user_obj = session.query(User).get(winner_user_id)

            if winner_player_state_obj and winner_user_obj:
                winner_player_state_obj.stack_sats += amount_per_winner_this_pot
                session.add(winner_player_state_obj)

                transaction = Transaction(
                    user_id=winner_user_id,
                    amount=amount_per_winner_this_pot,
                    transaction_type='poker_win',
                    status='completed',
                    details={
                        "hand_id": poker_hand.id, "table_id": poker_hand.table_id,
                        "pot_description": pot_description,
                        "pot_total_amount_awarded_to_player": amount_per_winner_this_pot,
                        "this_pot_total_value": pot_amount_to_distribute,
                        "num_winners_for_this_pot": num_winners_this_pot,
                        "winning_hand": winner_detail.get("winning_hand", "Unknown"),
                        "board_cards": poker_hand.board_cards
                    }
                )
                session.add(transaction)

                final_hand_winners_summary.append({
                    "user_id": winner_user_id, "username": winner_user_obj.username,
                    "amount_won": amount_per_winner_this_pot,
                    "pot_description": pot_description,
                    "winning_hand": winner_detail.get("winning_hand", "Unknown"),
                    "best_five_cards": winner_detail.get("best_five_cards", []) # From _determine_winning_hand
                })
            else:
                print(f"Error: Could not find full PlayerState or User object for winner ID {winner_user_id} of pot '{pot_description}'.")

    poker_hand.winners = final_hand_winners_summary
    poker_hand.end_time = datetime.now(timezone.utc)
    session.add(poker_hand)

    try:
        session.commit()
        # print(f"Hand {poker_hand.id}: Pot distribution complete. Rake: {actual_rake}. Winners: {final_hand_winners_summary}")
    except Exception as e:
        session.rollback()
        print(f"Error during final pot distribution commit for hand {poker_hand.id}: {e}")
        # Consider how to signal this error to the game flow

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
# - `_determine_winning_hand` now uses treys. `best_five_cards` is a proxy (hole + board).
# - Transactions for blinds in `start_new_hand` are commented out. They should be implemented.
# - `Transaction` model might need `poker_hand_id` nullable ForeignKey.
# - `PokerTable` might need fields like `current_dealer_seat_id`, `current_turn_user_id`, `current_bet_to_match`, `last_raise_amount`, `current_pot_this_street`
#   or these could be part of a live game state cache (e.g., Redis) associated with the hand/table rather than SQL columns updated frequently.
#   For now, some of this state is implicitly managed or intended to be added to PokerHand.
# - The `deal_hole_cards` function modifies `player_state.hole_cards` directly. These are SQLAlchemy model instances.
#   The changes are added to the session and committed in `start_new_hand`.
# - _get_card_value is removed as treys handles card representation.
# - `_distribute_pot` currently doesn't handle side pots at all. This is a major component for multi-way all-in situations.
# - The `winners` list in `PokerHand` stores `amount_won`. This is good.
# - `poker_table.player_states` is accessed. Ensure this relationship is loaded efficiently, e.g. with `joinedload` or `selectinload` where appropriate
#   (added to `start_new_hand` and `handle_sit_down`).
# - `Decimal` was imported but not used. It's good for financial calcs but satoshis are integers, so direct integer math is fine.
# - `handle_sit_down` checks for user already seated at *any* seat at the table. This is correct.

# --- Game Progression Logic ---

# Conceptual placeholder for timeout logic
# Assumes PokerPlayerState has a 'turn_starts_at' field (db.Column(db.DateTime, nullable=True)).
# And a POKER_ACTION_TIMEOUT_SECONDS constant is defined in config or globally.
# def check_and_handle_player_timeouts(poker_hand_id: int, session: Session, POKER_ACTION_TIMEOUT_SECONDS: int = 60):
#     """
#     Checks the current player for timeout and auto-folds them.
#     This would ideally be triggered by a separate scheduler or before processing any player action request.
#     Returns True if a timeout action was taken, False otherwise.
#     The actual auto-fold action should call the handle_fold function to ensure game state consistency.
#     """
#     poker_hand = session.query(PokerHand).get(poker_hand_id)
#     if not poker_hand or poker_hand.current_turn_user_id is None or poker_hand.status in ['completed', 'showdown']:
#         return False # No active turn or hand is over
#
#     player_to_act_state = session.query(PokerPlayerState).filter_by(
#         user_id=poker_hand.current_turn_user_id,
#         table_id=poker_hand.table_id # Ensure we get player at the correct table
#     ).first()
#
#     if player_to_act_state and hasattr(player_to_act_state, 'turn_starts_at') and player_to_act_state.turn_starts_at:
#         time_elapsed = (datetime.now(timezone.utc) - player_to_act_state.turn_starts_at).total_seconds()
#         if time_elapsed > POKER_ACTION_TIMEOUT_SECONDS:
#             print(f"Player {player_to_act_state.user_id} at seat {player_to_act_state.seat_id} timed out after {time_elapsed:.2f}s. Auto-folding.")
#
#             original_turn_user_id = player_to_act_state.user_id
#             # It's crucial that handle_fold is called, which then calls _check_betting_round_completion
#             # to correctly update game state including turn timers and player status.
#             # The handle_fold function should also ensure player_to_act_state.turn_starts_at is cleared after folding.
#             fold_result = handle_fold(original_turn_user_id, poker_hand.table_id, poker_hand.id) # handle_fold will manage session commit
#             print(f"Auto-fold result for user {original_turn_user_id}: {fold_result}")
#             return True # Timeout action was taken
#     return False


def _advance_to_next_street(hand_id: int, session: Session) -> dict:
    """
    Advances the hand to the next street (Flop, Turn, River) or to Showdown.
    - Deals community cards for the new street.
    - Resets street-specific betting state on PokerHand.
    - Determines the first player to act on the new street.
    - Updates PokerHand status.

    Args:
        hand_id (int): The ID of the PokerHand to advance.
        session (Session): The SQLAlchemy session to use for database operations.

    Returns:
        dict: A status message, e.g., {"status": "advanced_to_flop", "hand_id": hand_id}
              or {"status": "showdown_reached", "hand_id": hand_id}
              or an error dictionary.
    """
    poker_hand = session.query(PokerHand).options(
        joinedload(PokerHand.table).joinedload(PokerTable.player_states).joinedload(PokerPlayerState.user), # Load table and all player states
        joinedload(PokerHand.player_states_in_hand) # Assuming a relationship 'player_states_in_hand' for active players
                                                   # If not, query PokerPlayerState separately based on hand_id (more complex)
                                                   # For now, we'll use poker_hand.table.player_states and filter.
    ).get(hand_id)

    if not poker_hand:
        return {"error": f"PokerHand {hand_id} not found."}
    if not poker_hand.table:
        return {"error": f"PokerTable not found for PokerHand {hand_id}."}

    poker_table = poker_hand.table
    current_board_cards = list(poker_hand.board_cards) if poker_hand.board_cards else [] # Ensure it's a mutable list
    num_board_cards = len(current_board_cards)
    next_street_name = None
    cards_to_deal_count = 0

    if num_board_cards == 0: # Pre-flop -> Flop
        next_street_name = "flop"
        cards_to_deal_count = 3
        poker_hand.status = "flop"
    elif num_board_cards == 3: # Flop -> Turn
        next_street_name = "turn"
        cards_to_deal_count = 1
        poker_hand.status = "turn"
    elif num_board_cards == 4: # Turn -> River
        next_street_name = "river"
        cards_to_deal_count = 1
        poker_hand.status = "river"
    elif num_board_cards == 5: # River -> Showdown
        poker_hand.status = "showdown"
        poker_hand.current_turn_user_id = None # No more betting turns
        poker_hand.hand_history.append({
            "action": "proceed_to_showdown",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        # session.add(poker_hand) # Will be committed at the end of the calling function or here
        # session.commit() # Or commit immediately
        return {"status": "showdown_reached", "hand_id": hand_id, "board_cards": poker_hand.board_cards}
    else:
        return {"error": f"Invalid number of board cards ({num_board_cards}) for hand {hand_id}."}

    # --- Deck Management: Use poker_hand.deck_state ---
    # The insecure deck reconstruction is removed.
    # deal_community_cards will now use and update poker_hand.deck_state directly.

    if cards_to_deal_count > 0:
        newly_dealt_street_cards = deal_community_cards(poker_hand, next_street_name)

        if newly_dealt_street_cards is None:
            # Error already logged by deal_community_cards
            # Potentially rollback or handle error state if critical (e.g. could not deal flop)
            # For now, assume deal_community_cards handles session correctly or we handle it after call
            return {"error": f"Failed to deal {next_street_name} for hand {hand_id}."}

        # Hand history for dealing the street
        poker_hand.hand_history.append({
            "action": f"deal_{next_street_name}",
            "cards": newly_dealt_street_cards, # Only the cards dealt this street
            "board": list(poker_hand.board_cards), # Full board after this street
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    # Reset street-specific betting state
    poker_hand.current_bet_to_match = 0
    # min_next_raise_amount is typically BB, but could be SB in fixed limit pre-flop, or based on game rules.
    poker_hand.min_next_raise_amount = poker_table.big_blind
    poker_hand.last_raiser_user_id = None
    poker_hand.player_street_investments = {} # Reset for the new street

    # Determine First Player to Act (Post-flop: SB or first active player left of dealer)
    active_players_in_hand = [
        ps for ps in poker_table.player_states
        if ps.is_active_in_hand and ps.stack_sats > 0 # Must have chips to act
    ]
    if not active_players_in_hand:
        # This implies everyone else is all-in or folded. The hand might go to showdown directly.
        # This should be caught by logic that calls _advance_to_next_street.
        # If it reaches here, it's likely an early showdown or hand completion.
        poker_hand.status = "showdown" # Or "completed" if only one player remains effectively
        poker_hand.current_turn_user_id = None
        poker_hand.hand_history.append({
            "action": "all_remaining_players_all_in_or_one_left_post_street_deal",
            "next_street": next_street_name,
            "board": list(poker_hand.board_cards),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        # session.add(poker_hand)
        # session.commit()
        return {"status": poker_hand.status, "hand_id": hand_id, "board_cards": poker_hand.board_cards}

    sorted_active_players = sorted(active_players_in_hand, key=lambda ps: ps.seat_id)

    first_to_act_postflop = None
    dealer_seat_id = poker_table.current_dealer_seat_id

    if dealer_seat_id is not None:
        dealer_player_idx_in_sorted_active = -1
        for i, ps in enumerate(sorted_active_players):
            if ps.seat_id == dealer_seat_id:
                dealer_player_idx_in_sorted_active = i
                break

        if dealer_player_idx_in_sorted_active != -1:
            # Start search from player left of dealer
            for i in range(len(sorted_active_players)):
                player_to_check_idx = (dealer_player_idx_in_sorted_active + 1 + i) % len(sorted_active_players)
                player_candidate = sorted_active_players[player_to_check_idx]
                if player_candidate.is_active_in_hand and player_candidate.stack_sats > 0:
                    first_to_act_postflop = player_candidate
                    break
        else: # Dealer is not in active players (e.g. dealer folded) - start from lowest seat
            first_to_act_postflop = sorted_active_players[0] if sorted_active_players else None
    else: # No dealer button somehow (should not happen in a running hand)
        first_to_act_postflop = sorted_active_players[0] if sorted_active_players else None

    if first_to_act_postflop:
        poker_hand.current_turn_user_id = first_to_act_postflop.user_id
        # Set turn_starts_at for the first player of the new street
        # Conceptual: Assumes PokerPlayerState has 'turn_starts_at'
        if hasattr(first_to_act_postflop, 'turn_starts_at'):
            first_to_act_postflop.turn_starts_at = datetime.now(timezone.utc)
            session.add(first_to_act_postflop)
        else:
            print(f"Warning: PlayerState for user {first_to_act_postflop.user_id} does not have 'turn_starts_at' attribute in _advance_to_next_street.")

        poker_hand.hand_history.append({
            "action": "set_next_to_act",
            "street": next_street_name,
            "user_id": first_to_act_postflop.user_id,
            "seat_id": first_to_act_postflop.seat_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    else:
        # Should be handled by the active_players_in_hand check earlier or implies showdown
        print(f"Warning: Could not determine first player to act for {next_street_name} in hand {hand_id}.")
        poker_hand.status = "showdown" # Default to showdown if no one can act
        poker_hand.current_turn_user_id = None


    session.add(poker_hand)
    # Commit is typically handled by the calling function (e.g., after a player action that triggers street change)
    # For standalone testing or if this is the final step of a process, commit here.
    # For now, assume commit is handled by caller.

    return {
        "status": f"advanced_to_{next_street_name}",
        "hand_id": hand_id,
        "board_cards": list(poker_hand.board_cards),
        "next_to_act_user_id": poker_hand.current_turn_user_id
    }

def _check_betting_round_completion(hand_id: int, last_actor_user_id: int, session: Session) -> dict:
    """
    Checks if a betting round is complete after a player action.
    If complete, advances to the next street or showdown.
    If not complete, determines the next player to act.

    Args:
        hand_id (int): The ID of the current PokerHand.
        last_actor_user_id (int): The user_id of the player who just acted.
        session (Session): SQLAlchemy session.

    Returns:
        dict: Status of the hand, e.g.,
              {"status": "hand_completed_by_folds", "winner_user_id": ...},
              {"status": "round_completed_advancing_street", "next_street_status": ...},
              {"status": "all_in_showdown"},
              {"status": "betting_continues", "next_to_act_user_id": ...},
              or an error dictionary.
    """
    poker_hand = session.query(PokerHand).options(
        joinedload(PokerHand.table).joinedload(PokerTable.player_states).joinedload(PokerPlayerState.user)
    ).get(hand_id)

    if not poker_hand: return {"error": f"PokerHand {hand_id} not found."}
    if not poker_hand.table: return {"error": f"PokerTable for hand {hand_id} not found."}

    all_player_states_in_hand = [ps for ps in poker_hand.table.player_states if ps.is_active_in_hand or (poker_hand.player_street_investments and str(ps.user_id) in poker_hand.player_street_investments)]

    # Players who are still in the hand (haven't folded)
    active_players_still_in_hand = [ps for ps in all_player_states_in_hand if ps.is_active_in_hand]

    # Clear timer for the player who just acted (last_actor_user_id)
    # Conceptual: Assumes PokerPlayerState has 'turn_starts_at'
    last_actor_ps = session.query(PokerPlayerState).filter_by(user_id=last_actor_user_id, table_id=poker_hand.table_id).first()
    if last_actor_ps and hasattr(last_actor_ps, 'turn_starts_at'):
        last_actor_ps.turn_starts_at = None
        session.add(last_actor_ps)

    # 1. Check for Hand End by Folds
    if len(active_players_still_in_hand) <= 1:
        winner_user_id = active_players_still_in_hand[0].user_id if active_players_still_in_hand else None

        # Ensure any other potentially active timer is cleared
        if poker_hand.current_turn_user_id and poker_hand.current_turn_user_id != last_actor_user_id:
            # This case should be rare if current_turn_user_id was last_actor_user_id
            other_ps_to_clear = session.query(PokerPlayerState).filter_by(user_id=poker_hand.current_turn_user_id, table_id=poker_hand.table_id).first()
            if other_ps_to_clear and hasattr(other_ps_to_clear, 'turn_starts_at'):
                other_ps_to_clear.turn_starts_at = None
                session.add(other_ps_to_clear)

        poker_hand.status = 'completed'
        poker_hand.current_turn_user_id = None
        # _distribute_pot needs a list of PokerPlayerState objects for showdown.
        # If one player wins by folds, they are the only one.
        # Ensure total_invested_this_hand is set on these player_state objects for _distribute_pot.
        # This part might need adjustment based on how _distribute_pot expects its input for fold scenarios.
        if winner_user_id:
             _distribute_pot(poker_hand, active_players_still_in_hand) # Assuming _distribute_pot can handle this
             poker_hand.hand_history.append({
                "action": "hand_completed_by_folds",
                "winner_user_id": winner_user_id,
                "pot_size": poker_hand.pot_size_sats,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        else: # No one left - should not happen if game started with players.
            poker_hand.hand_history.append({"action": "hand_completed_no_winner", "timestamp": datetime.now(timezone.utc).isoformat()})

        session.add(poker_hand)
        # session.commit() # Commit handled by calling action function
        return {"status": "hand_completed_by_folds", "winner_user_id": winner_user_id, "hand_id": hand_id}

    # 2. Check for Betting Round Completion
    # Players who can still make betting decisions (not folded, have chips)
    bettable_players = [ps for ps in active_players_still_in_hand if ps.stack_sats > 0]

    current_bet = poker_hand.current_bet_to_match
    player_investments = poker_hand.player_street_investments if poker_hand.player_street_investments else {}

    # Condition 1: All players who can still bet are all-in (or only one non-all-in player left)
    non_all_in_bettable_players = [
        ps for ps in bettable_players
        if player_investments.get(str(ps.user_id), 0) < current_bet or ps.stack_sats > 0 # Has to call/raise OR has chips to do so
                                                                                         # More simply: those not all-in for less than current_bet
    ]

    # More precise: players who are active, have chips, and have not yet matched the current_bet
    players_who_must_act = []
    for ps in active_players_still_in_hand: # Iterate in seat order to be fair
        is_all_in_for_less = (ps.stack_sats == 0 and player_investments.get(str(ps.user_id), 0) < current_bet)
        if ps.stack_sats > 0 and player_investments.get(str(ps.user_id), 0) < current_bet and not is_all_in_for_less:
            players_who_must_act.append(ps)

    round_complete = False
    if not players_who_must_act: # No one left who needs to call/raise the current bet
        # This means all active players have either matched the current_bet_to_match or are all-in for less.
        # Check if the action is closed:
        # - If no bet was made (everyone checked), round is over.
        # - If a bet/raise was made, action must return to the last aggressor without them re-raising.
        # Simplified: If players_who_must_act is empty, assume action is closed for this subtask.
        # A more robust check would involve tracking who made the last aggressive action and if the turn has passed them.
        round_complete = True


    if round_complete:
        # If all bettable players are all-in (or only one is not), proceed to showdown after dealing all cards
        if len(non_all_in_bettable_players) <=1 and len(active_players_still_in_hand) > 1 :
             # Advance all remaining streets automatically
            while poker_hand.status not in ['showdown', 'completed'] and len(poker_hand.board_cards) < 5:
                adv_result = _advance_to_next_street(hand_id, session)
                if "error" in adv_result: return adv_result
                if adv_result["status"] == "showdown_reached": break
            # After all streets, it should be showdown
            if poker_hand.status != 'showdown': poker_hand.status = 'showdown' # Force if not set by advance

            # Clear timer for the current_turn_user_id if it was set (now effectively null as it's all-in)
            if poker_hand.current_turn_user_id:
                 prev_turn_ps_all_in = session.query(PokerPlayerState).filter_by(user_id=poker_hand.current_turn_user_id, table_id=poker_hand.table_id).first()
                 if prev_turn_ps_all_in and hasattr(prev_turn_ps_all_in, 'turn_starts_at'):
                     prev_turn_ps_all_in.turn_starts_at = None
                     session.add(prev_turn_ps_all_in)

            poker_hand.current_turn_user_id = None # No more turns
            poker_hand.hand_history.append({"action": "all_in_proceed_to_showdown", "timestamp": datetime.now(timezone.utc).isoformat()})
            session.add(poker_hand)
            return {"status": "all_in_showdown", "hand_id": hand_id} # Or "all_in_runout_pending_cards" if not river yet
        else: # Normal round completion, advance to next street
            # last_actor_ps timer already cleared at the start of this function.
            # _advance_to_next_street will handle setting the timer for the first player of the new street.
            adv_result = _advance_to_next_street(hand_id, session)
            return {"status": "round_completed_advancing_street",
                    "next_street_status": poker_hand.status,
                    "next_to_act_user_id": poker_hand.current_turn_user_id,
                    "board_cards": list(poker_hand.board_cards),
                    "hand_id": hand_id}

    # 3. Determine Next Player to Act
    # Sort active players who can still make decisions (not folded, have stack)
    sorted_bettable_players = sorted(bettable_players, key=lambda p: p.seat_id)
    if not sorted_bettable_players: # Should be caught by earlier checks (all_in_showdown or hand_completed)
        return {"error": "No bettable players left, but round not deemed complete."}

    last_actor_seat_id = -1
    for ps in sorted_bettable_players: # Could be all_player_states_in_hand if we need to find last actor even if they folded
        if ps.user_id == last_actor_user_id:
            last_actor_seat_id = ps.seat_id
            break

    if last_actor_seat_id == -1 and sorted_bettable_players: # Fallback or if last actor folded and is not in bettable_players
        # This indicates an issue or complex scenario not fully handled by simplified logic.
        # For robustness, pick the first bettable player if last actor cannot be clearly determined.
        # Or, if current_turn_user_id was the one who just acted:
        current_player_idx = -1
        if poker_hand.current_turn_user_id: # This should be the ID of player who just acted
             for idx, p in enumerate(sorted_bettable_players):
                 if p.user_id == poker_hand.current_turn_user_id:
                     current_player_idx = idx
                     break
        if current_player_idx != -1 :
            start_search_idx = (current_player_idx + 1) % len(sorted_bettable_players)
        else: # Fallback: start from the first player in the sorted list.
            start_search_idx = 0
    elif sorted_bettable_players:
        current_player_idx = next((i for i, p in enumerate(sorted_bettable_players) if p.user_id == last_actor_user_id), -1)
        start_search_idx = (current_player_idx + 1) % len(sorted_bettable_players) if current_player_idx !=-1 else 0
    else: # No bettable players, should have been caught
        return {"error":"Logically should not reach here: No bettable players."}


    next_player_to_act = None
    for i in range(len(sorted_bettable_players)):
        player_idx = (start_search_idx + i) % len(sorted_bettable_players)
        candidate_player = sorted_bettable_players[player_idx]

        # Player must be active, have chips, and either owe money or action hasn't closed on them yet.
        # Simplified: if they are in bettable_players, they are considered needing to act if round not over.
        # More precise check: if player_investments.get(str(candidate_player.user_id),0) < current_bet
        # OR if current_bet == 0 and they haven't checked/bet this round.
        # For now, just finding the next in line from bettable_players.
        if candidate_player.is_active_in_hand and candidate_player.stack_sats > 0:
            next_player_to_act = candidate_player
            break

    if next_player_to_act:
        poker_hand.current_turn_user_id = next_player_to_act.user_id
        poker_hand.hand_history.append({
            "action": "set_next_to_act",
            "street": poker_hand.status, # current street
            "user_id": next_player_to_act.user_id,
            "seat_id": next_player_to_act.seat_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # Set turn_starts_at for the next player
        # Conceptual: Assumes PokerPlayerState has 'turn_starts_at'
        if hasattr(next_player_to_act, 'turn_starts_at'):
            next_player_to_act.turn_starts_at = datetime.now(timezone.utc)
            session.add(next_player_to_act)
        else:
            print(f"Warning: PlayerState for user {next_player_to_act.user_id} does not have 'turn_starts_at' attribute.")

        session.add(poker_hand)
        return {"status": "betting_continues", "next_to_act_user_id": poker_hand.current_turn_user_id, "hand_id": hand_id}
    else:
        # This case implies that all bettable players have acted and matched the bet, or are all-in.
        # This should ideally be caught by the 'round_complete' logic.
        # If it reaches here, it's an unexpected state.
        # Timer for last_actor_user_id was already cleared at the start of the function.
        print(f"Warning: Betting round logic fell through for hand {hand_id}. No specific next actor determined, but round not flagged as complete earlier. Current turn on hand: {poker_hand.current_turn_user_id}")
        # This might indicate an issue in round_complete logic or player state.
        # For safety, assume round is over and try to advance.
        adv_result = _advance_to_next_street(hand_id, session)
        return {"status": "round_completed_advancing_street_fallback",
                "next_street_status": poker_hand.status,
                "next_to_act_user_id": poker_hand.current_turn_user_id, # Could be None
                "hand_id": hand_id}


# Conceptual placeholder for timeout logic
# Assumes PokerPlayerState has a 'turn_starts_at' field (db.Column(db.DateTime, nullable=True)).
# And a POKER_ACTION_TIMEOUT_SECONDS constant is defined in config or globally.
# def check_and_handle_player_timeouts(poker_hand_id: int, session: Session, POKER_ACTION_TIMEOUT_SECONDS: int = 60):
#     """
#     Checks the current player for timeout and auto-folds them.
#     This would ideally be triggered by a separate scheduler or before processing any player action request.
#     Returns True if a timeout action was taken, False otherwise.
#     The actual auto-fold action should call the handle_fold function to ensure game state consistency.
#     """
#     poker_hand = session.query(PokerHand).get(poker_hand_id)
#     if not poker_hand or poker_hand.current_turn_user_id is None or poker_hand.status in ['completed', 'showdown']:
#         return False # No active turn or hand is over
#
#     player_to_act_state = session.query(PokerPlayerState).filter_by(
#         user_id=poker_hand.current_turn_user_id,
#         table_id=poker_hand.table_id # Ensure we get player at the correct table
#     ).first()
#
#     if player_to_act_state and hasattr(player_to_act_state, 'turn_starts_at') and player_to_act_state.turn_starts_at:
#         time_elapsed = (datetime.now(timezone.utc) - player_to_act_state.turn_starts_at).total_seconds()
#         if time_elapsed > POKER_ACTION_TIMEOUT_SECONDS:
#             print(f"Player {player_to_act_state.user_id} at seat {player_to_act_state.seat_id} timed out after {time_elapsed:.2f}s. Auto-folding.")
#
#             original_turn_user_id = player_to_act_state.user_id
#             # It's crucial that handle_fold is called, which then calls _check_betting_round_completion
#             # to correctly update game state including turn timers and player status.
#             # The handle_fold function should also ensure player_to_act_state.turn_starts_at is cleared after folding.
#             fold_result = handle_fold(original_turn_user_id, poker_hand.table_id, poker_hand.id) # handle_fold will manage session commit
#             print(f"Auto-fold result for user {original_turn_user_id}: {fold_result}")
#             return True # Timeout action was taken
#     return False


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
            "hole_cards": None # Default to None
        }
        if ps.user_id == user_id: # Requesting user
            player_data["hole_cards"] = ps.hole_cards 
        elif ps.hole_cards: # Other players with cards
            player_data["hole_cards"] = ["X", "X"] # Masked cards
        # If ps.hole_cards is None (e.g. player not in hand or cards not revealed yet), it remains None

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
