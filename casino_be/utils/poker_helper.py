import random
import secrets
from datetime import datetime, timezone, timedelta
from decimal import Decimal # For precise monetary calculations
from flask import current_app

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

POKER_ACTION_TIMEOUT_SECONDS = 60

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
        current_app.logger.error(f"Hand {poker_hand.id} has no deck_state.")
        return False

    # Work with a mutable copy of the deck_state for this operation
    current_deck_list = list(poker_hand.deck_state)

    num_active_players = sum(1 for ps in player_states if ps.is_active_in_hand)
    if len(current_deck_list) < num_active_players * 2:
        current_app.logger.error(f"Not enough cards in hand's deck ({len(current_deck_list)}) to deal hole cards to {num_active_players} players.")
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
                    current_app.logger.error("Deck ran out unexpectedly during hole card dealing.")
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
        current_app.logger.error(f"Hand {poker_hand.id} has no deck_state for dealing {street}.")
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
        current_app.logger.error(f"Invalid street name '{street}'.")
        return None

    if len(current_deck_list) < cards_to_deal_count: # Check against the mutable copy
        current_app.logger.error(f"Not enough cards in hand's deck to deal {street}.")
        return None

    # Optional: Burn a card. If burning, ensure deck has enough for burn + deal.
    # if len(current_deck_list) < cards_to_deal_count + 1: # If burning
    #     current_app.logger.error(f"Error: Not enough cards to burn and deal {street}.")
    #     return None
    # burned_card = _deal_card_from_deck_list(current_deck_list)
    # if burned_card:
    #     poker_hand.hand_history.append({"action": "burn_card", "card": burned_card, "street_before": street})
    # else: # Should not happen if check above is done
    #     current_app.logger.error(f"Error: Failed to burn card before {street} deal.")
    #     return None


    newly_dealt_street_cards = []
    for _ in range(cards_to_deal_count):
        card = _deal_card_from_deck_list(current_deck_list) # Modifies current_deck_list
        if card:
            newly_dealt_street_cards.append(card)
        else:
            # Should not happen if initial checks passed
            current_app.logger.error(f"Error: Deck ran out unexpectedly during {street} dealing for hand {poker_hand.id}.")
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
    new_hand.status = 'preflop' # <<< SETTING HAND STATUS
    session.add(new_hand) # Ensure status is staged

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
    if first_to_act_player:
        first_to_act_player.time_to_act_ends = datetime.now(timezone.utc) + timedelta(seconds=POKER_ACTION_TIMEOUT_SECONDS)
        session.add(first_to_act_player)
    
    # Final commit for PokerTable, PokerPlayerStates (stacks, actions), new PokerHand, Transactions
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        current_app.logger.error(f"Error during start_new_hand commit: {e}")
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
        current_app.logger.error(f"Error during sit down: {e}")
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
        current_app.logger.info(f"Player {user_id} stood up and auto-folded from active hand {current_poker_hand.id if current_poker_hand else 'unknown'}.")

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
        current_app.logger.error(f"Error during stand up: {e}")
        return {"error": "Could not process stand up due to a server error."}


# --- Betting Logic Stubs ---

def handle_fold(user_id: int, table_id: int, hand_id: int):
    """
    Handles a player's fold action.
    - Fetches PokerPlayerState and PokerHand.
    - If player state or hand not found, returns an error.
    - Clears player_state.time_to_act_ends.
    - If player not active in hand, returns an error.
    - Sets player_state.is_active_in_hand = False.
    - Sets player_state.last_action = "fold".
    - Initializes poker_hand.hand_history to [] if None.
    - Appends fold action (with user_id, seat_id, action, timestamp) to poker_hand.hand_history.
    - Adds player_state and poker_hand to session.
    - Calls game_flow_result = _check_betting_round_completion(hand_id, user_id, db.session).
    - Commits session.
    - Returns a success message with game_flow_result or an error from _check_betting_round_completion.
    """
    session = db.session
    player_state = session.query(PokerPlayerState).filter_by(user_id=user_id, table_id=table_id).first()
    poker_hand = session.query(PokerHand).get(hand_id)

    if not player_state:
        return {"error": f"Player state for user {user_id} not found at table {table_id}."}
    if not poker_hand:
        return {"error": f"Poker hand {hand_id} not found."}

    # Clear player's action timer
    player_state.time_to_act_ends = None

    if not player_state.is_active_in_hand:
        session.add(player_state) # Add to session to save time_to_act_ends clearing even if erroring
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            current_app.logger.error(f"Error committing player_state on inactive fold for user {user_id}: {e}")
        return {"error": f"Player {user_id} is not active in hand {hand_id}."}

    player_state.is_active_in_hand = False
    player_state.last_action = "fold"

    if poker_hand.hand_history is None:
        poker_hand.hand_history = []

    poker_hand.hand_history.append({
        "user_id": user_id,
        "seat_id": player_state.seat_id,
        "action": "fold",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    session.add(player_state)
    session.add(poker_hand)

    try:
        # _check_betting_round_completion is expected to handle session commit internally if it's the final step,
        # or stage changes if further actions are needed within its scope.
        # For actions like fold/check/call/bet/raise, the primary responsibility for commit lies with the action handler.
        game_flow_result = _check_betting_round_completion(hand_id, user_id, session)
        session.commit() # Commit changes from this function and potentially from _check_betting_round_completion
        return {
            "message": f"User {user_id} folded successfully in hand {hand_id}.",
            "game_flow": game_flow_result
        }
    except Exception as e:
        session.rollback()
        current_app.logger.error(f"Error during fold action for user {user_id} in hand {hand_id}: {e}")
        # It's good to return a consistent error structure
        return {"error": "Could not process fold due to a server error.", "details": str(e)}


def handle_check(user_id: int, table_id: int, hand_id: int):
    """Placeholder for handling a player's check action."""
    """
    Handles a player's check action.
    - Fetches PokerPlayerState and PokerHand.
    - If player state or hand not found, returns an error.
    - Clears player_state.time_to_act_ends.
    - If player not active in hand, returns an error.
    - Initializes poker_hand.player_street_investments to {} if None.
    - Calculates player_invested_this_street and current_bet_to_match.
    - If player_invested_this_street < current_bet_to_match, returns an error "Cannot check, must call...".
    - Sets player_state.last_action = "check".
    - Initializes poker_hand.hand_history to [] if None.
    - Appends check action to poker_hand.hand_history.
    - Adds player_state and poker_hand to session.
    - Calls game_flow_result = _check_betting_round_completion(hand_id, user_id, db.session).
    - Commits session.
    - Returns a success message with game_flow_result or an error.
    """
    session = db.session
    player_state = session.query(PokerPlayerState).filter_by(user_id=user_id, table_id=table_id).first()
    poker_hand = session.query(PokerHand).get(hand_id)

    if not player_state:
        return {"error": f"Player state for user {user_id} not found at table {table_id}."}
    if not poker_hand:
        return {"error": f"Poker hand {hand_id} not found."}

    player_state.time_to_act_ends = None

    if not player_state.is_active_in_hand:
        session.add(player_state) # Save cleared timer
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            current_app.logger.error(f"Error committing player_state on inactive check for user {user_id}: {e}")
        return {"error": f"Player {user_id} is not active in hand {hand_id}."}

    if poker_hand.player_street_investments is None:
        poker_hand.player_street_investments = {}
    
    player_invested_this_street = poker_hand.player_street_investments.get(str(user_id), 0)
    current_bet_to_match = poker_hand.current_bet_to_match or 0

    if player_invested_this_street < current_bet_to_match:
        session.add(player_state) # Save cleared timer
        session.add(poker_hand) # Save initialized player_street_investments
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            current_app.logger.error(f"Error committing on check legality fail for user {user_id}: {e}")
        return {"error": f"Cannot check. Player {user_id} needs to call {current_bet_to_match - player_invested_this_street} more to match current bet of {current_bet_to_match}."}

    player_state.last_action = "check"

    if poker_hand.hand_history is None:
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
        current_app.logger.error(f"Error during check action for user {user_id} in hand {hand_id}: {e}")
        return {"error": "Could not process check due to a server error.", "details": str(e)}


def handle_call(user_id: int, table_id: int, hand_id: int):
    """Placeholder for handling a player's call action."""
    """
    Handles a player's call action.
    - Fetches PokerPlayerState, PokerHand. User can be accessed via player_state.user.
    - If player state or hand not found, returns an error.
    - Clears player_state.time_to_act_ends.
    - If player not active in hand, returns an error.
    - Initializes poker_hand.player_street_investments to {} if None.
    - Calculates player_invested_this_street, current_bet_to_match, and amount_to_call_due.
    - If amount_to_call_due <= 0, returns an error "No pending bet to call...".
    - Calculates actual_call_amount and is_all_in.
    - Updates player_state.stack_sats, player_state.total_invested_this_hand.
    - Updates poker_hand.player_street_investments, poker_hand.pot_size_sats.
    - Sets action_string and player_state.last_action.
    - Creates a Transaction.
    - Initializes poker_hand.hand_history to [] if None and appends call action.
    - Adds player_state, poker_hand, transaction to session.
    - Calls _check_betting_round_completion and commits session.
    - Returns success message or error.
    """
    session = db.session
    # Eagerly load user for transaction details if needed, though not strictly for balance.
    player_state = session.query(PokerPlayerState).options(joinedload(PokerPlayerState.user)).filter_by(user_id=user_id, table_id=table_id).first()
    poker_hand = session.query(PokerHand).get(hand_id)

    if not player_state:
        return {"error": f"Player state for user {user_id} not found at table {table_id}."}
    if not poker_hand:
        return {"error": f"Poker hand {hand_id} not found."}
    # player_state.user is available due to joinedload

    player_state.time_to_act_ends = None

    if not player_state.is_active_in_hand:
        session.add(player_state) # Save cleared timer
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            current_app.logger.error(f"Error committing player_state on inactive call for user {user_id}: {e}")
        return {"error": f"Player {user_id} is not active in hand {hand_id}."}

    if poker_hand.player_street_investments is None:
        poker_hand.player_street_investments = {}

    player_invested_this_street = poker_hand.player_street_investments.get(str(user_id), 0)
    current_bet_to_match = poker_hand.current_bet_to_match or 0
    amount_to_call_due = current_bet_to_match - player_invested_this_street

    if amount_to_call_due <= 0:
        session.add(player_state) # Save cleared timer
        session.add(poker_hand) # Save initialized investments
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            current_app.logger.error(f"Error committing on call legality fail for user {user_id}: {e}")
        return {"error": f"No pending bet to call for user {user_id}. Amount due is {amount_to_call_due}. Current bet: {current_bet_to_match}, Player invested: {player_invested_this_street}."}

    actual_call_amount = min(amount_to_call_due, player_state.stack_sats)
    is_all_in = (actual_call_amount == player_state.stack_sats) and (actual_call_amount < amount_to_call_due)

    player_state.stack_sats -= actual_call_amount
    player_state.total_invested_this_hand = (player_state.total_invested_this_hand or 0) + actual_call_amount

    poker_hand.player_street_investments[str(user_id)] = player_invested_this_street + actual_call_amount
    poker_hand.pot_size_sats = (poker_hand.pot_size_sats or 0) + actual_call_amount

    action_string = "call_all_in" if is_all_in else "call"
    player_state.last_action = f"{action_string}_{actual_call_amount}"

    transaction = Transaction(
        user_id=user_id,
        amount=-actual_call_amount,
        transaction_type='poker_action_call',
        status='completed',
        details={
            "table_id": table_id,
            "hand_id": hand_id,
            "action": action_string,
            "amount": actual_call_amount
        },
        poker_hand_id=hand_id
    )

    if poker_hand.hand_history is None:
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
        current_app.logger.error(f"Error during call action for user {user_id} in hand {hand_id}: {e}")
        return {"error": "Could not process call due to a server error.", "details": str(e)}


def handle_bet(user_id: int, table_id: int, hand_id: int, amount: int):
    """Placeholder for handling a player's bet action."""
    """
    Handles a player's bet action.
    - Fetches PokerPlayerState, PokerHand, PokerTable.
    - If any not found, or amount <= 0, returns an error.
    - Clears player_state.time_to_act_ends.
    - If player not active, returns an error.
    - Initializes poker_hand.player_street_investments to {} if None.
    - Calculates player_invested_this_street and current_bet_to_match_val.
    - If current_bet_to_match_val > player_invested_this_street, returns error "Cannot bet, must call or raise...".
    - Validates min_bet_val.
    - Calculates actual_bet_amount_put_in_pot and is_all_in.
    - Updates player_state (stack_sats, total_invested_this_hand).
    - Updates poker_hand (player_street_investments, pot_size_sats, current_bet_to_match, last_raiser_user_id, min_next_raise_amount).
    - Sets action_string and player_state.last_action.
    - Creates Transaction.
    - Initializes and appends to poker_hand.hand_history.
    - Adds all modified objects to session.
    - Calls _check_betting_round_completion and commits.
    - Returns success message or error.
    """
    session = db.session
    player_state = session.query(PokerPlayerState).filter_by(user_id=user_id, table_id=table_id).first()
    poker_hand = session.query(PokerHand).get(hand_id)
    poker_table = session.query(PokerTable).get(table_id)

    if not player_state:
        return {"error": f"Player state for user {user_id} not found at table {table_id}."}
    if not poker_hand:
        return {"error": f"Poker hand {hand_id} not found."}
    if not poker_table:
        return {"error": f"Poker table {table_id} not found."}
    if amount <= 0:
        return {"error": "Bet amount must be positive."}

    player_state.time_to_act_ends = None

    if not player_state.is_active_in_hand:
        session.add(player_state) # Save cleared timer
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            current_app.logger.error(f"Error committing player_state on inactive bet for user {user_id}: {e}")
        return {"error": f"Player {user_id} is not active in hand {hand_id}."}

    if poker_hand.player_street_investments is None:
        poker_hand.player_street_investments = {}

    player_invested_this_street = poker_hand.player_street_investments.get(str(user_id), 0)
    current_bet_to_match_on_table = poker_hand.current_bet_to_match or 0

    # For a "bet" action, it's generally expected that either:
    # 1. The current_bet_to_match_on_table is 0 (no prior bets this street).
    # 2. The player has already matched the current_bet_to_match_on_table (e.g. BB checking option, then deciding to bet).
    #    This means player_invested_this_street == current_bet_to_match_on_table.
    # If current_bet_to_match_on_table > player_invested_this_street, it implies an outstanding bet the player must call or raise.
    if current_bet_to_match_on_table > player_invested_this_street:
        # session.add(player_state) # Save cleared timer - commit will be handled before return
        # session.add(poker_hand)
        # try: session.commit()
        # except Exception as e: session.rollback(); print(f"Error committing on bet legality (must call/raise) for user {user_id}: {e}")
        return {"error": f"Cannot bet. Must call or raise existing bet of {current_bet_to_match_on_table}. Player has invested {player_invested_this_street}."}

    # `amount` is the additional amount the player wants to bet.
    # `action_amount_total_for_street` is what their total investment for the street will become.
    action_amount_total_for_street = player_invested_this_street + amount

    is_valid_bet, validation_message = _validate_bet(
        player_state=player_state,
        action_amount=action_amount_total_for_street, # Total investment this player is making it to for the street
        current_bet_to_match=current_bet_to_match_on_table, # Current highest bet on table player needs to exceed
        min_next_raise_increment=poker_hand.min_next_raise_amount or poker_table.big_blind, # For opening bet, this effectively sets min open size via logic in _validate_bet
        limit_type=poker_table.limit_type,
        poker_table=poker_table,
        player_amount_invested_this_street=player_invested_this_street,
        current_hand_pot_size=poker_hand.pot_size_sats or 0 # Pot size before this player's current action
    )

    if not is_valid_bet:
        # session.add(player_state) # Save cleared timer before returning error
        # session.add(poker_hand)
        # try: session.commit()
        # except Exception as e: session.rollback(); print(f"Error committing on invalid bet validation for user {user_id}: {e}")
        return {"error": f"Invalid bet: {validation_message}"}

    # `amount` is the additional amount the player declared to bet.
    # `actual_bet_amount_put_in_pot` is what they actually can put in (capped by stack).
    actual_bet_amount_put_in_pot = min(amount, player_state.stack_sats)

    # is_all_in means the player is putting their entire remaining stack into this bet.
    # This happens if the amount they intend to bet (actual_bet_amount_put_in_pot) is equal to their stack.
    # And, critically for the "bet_all_in" string, usually implies they *intended* to bet `amount` but were capped by stack,
    # OR they intended to bet their exact stack.
    # If `amount` (their declared bet) was greater than their stack, and they put in their stack, it's an all-in.
    # If `amount` was equal to their stack, it's also an all-in.
    is_all_in = (actual_bet_amount_put_in_pot == player_state.stack_sats)

    player_state.stack_sats -= actual_bet_amount_put_in_pot
    player_state.total_invested_this_hand = (player_state.total_invested_this_hand or 0) + actual_bet_amount_put_in_pot

    new_player_street_investment = player_invested_this_street + actual_bet_amount_put_in_pot
    poker_hand.player_street_investments[str(user_id)] = new_player_street_investment
    poker_hand.pot_size_sats = (poker_hand.pot_size_sats or 0) + actual_bet_amount_put_in_pot

    # This bet action sets a new current_bet_to_match for others.
    poker_hand.current_bet_to_match = new_player_street_investment
    poker_hand.last_raiser_user_id = user_id # This player made the latest aggressive action.
    # The minimum next raise increment is the size of this bet itself (the additional amount put in).
    poker_hand.min_next_raise_amount = actual_bet_amount_put_in_pot

    action_string = "bet_all_in" if is_all_in else "bet"
    player_state.last_action = f"{action_string}_{actual_bet_amount_put_in_pot}"

    transaction = Transaction(
        user_id=user_id,
        amount=-actual_bet_amount_put_in_pot,
        transaction_type='poker_action_bet',
        status='completed',
        details={
            "table_id": table_id,
            "hand_id": hand_id,
            "action": action_string,
            "amount": actual_bet_amount_put_in_pot
        },
        poker_hand_id=hand_id
    )

    if poker_hand.hand_history is None:
        poker_hand.hand_history = []

    poker_hand.hand_history.append({
        "user_id": user_id,
        "seat_id": player_state.seat_id,
        "action": action_string,
        "amount": actual_bet_amount_put_in_pot, # The amount put into the pot for this bet action
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    session.add(player_state)
    session.add(poker_hand)
    session.add(poker_table) # Though not modified, good practice if accessed
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
        current_app.logger.error(f"Error during bet action for user {user_id} in hand {hand_id}: {e}")
        return {"error": "Could not process bet due to a server error.", "details": str(e)}


def handle_raise(user_id: int, table_id: int, hand_id: int, amount: int):
    """Placeholder for handling a player's raise action."""
    """
    Handles a player's raise action.
    - Fetches PokerPlayerState, PokerHand, PokerTable.
    - If any not found, or amount <= 0, returns error.
    - Clears player_state.time_to_act_ends.
    - If player not active, returns error.
    - Initializes poker_hand.player_street_investments.
    - Validates raise conditions (prior bet, amount > current bet, min raise increment).
    - Calculates amounts, is_all_in.
    - Updates player_state (stack_sats, total_invested_this_hand).
    - Updates poker_hand (player_street_investments, pot_size_sats, min_next_raise_amount, current_bet_to_match, last_raiser_user_id).
    - Sets action_string and player_state.last_action.
    - Creates Transaction.
    - Initializes and appends to poker_hand.hand_history.
    - Adds all modified objects to session.
    - Calls _check_betting_round_completion and commits.
    - Returns success message or error.
    """
    session = db.session
    player_state = session.query(PokerPlayerState).filter_by(user_id=user_id, table_id=table_id).first()
    poker_hand = session.query(PokerHand).get(hand_id)
    poker_table = session.query(PokerTable).get(table_id)

    if not player_state:
        return {"error": f"Player state for user {user_id} not found at table {table_id}."}
    if not poker_hand:
        return {"error": f"Poker hand {hand_id} not found."}
    if not poker_table:
        return {"error": f"Poker table {table_id} not found."}
    if amount <= 0: # Amount is the total sum the player is raising TO for the street
        return {"error": "Raise amount must be positive."}

    player_state.time_to_act_ends = None

    if not player_state.is_active_in_hand:
        session.add(player_state) # Save cleared timer
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            current_app.logger.error(f"Error committing player_state on inactive raise for user {user_id}: {e}")
        return {"error": f"Player {user_id} is not active in hand {hand_id}."}

    if poker_hand.player_street_investments is None:
        poker_hand.player_street_investments = {}

    player_invested_this_street = poker_hand.player_street_investments.get(str(user_id), 0)
    previous_bet_to_match_on_table = poker_hand.current_bet_to_match or 0 # This is current_bet_to_match for _validate_bet

    # `amount` for handle_raise IS the total action_amount for the street.
    action_amount_total_for_street = amount

    # Preliminary check: must be a bet to raise.
    if previous_bet_to_match_on_table == 0:
        # try: session.commit() # Commit cleared timer if necessary
        # except Exception as e: session.rollback(); print(f"Error committing on raise legality (no prior bet) for user {user_id}: {e}")
        return {"error": "Cannot raise, no prior bet. Use 'bet' action instead."}

    # Preliminary check: raise amount must be greater than the current bet.
    if action_amount_total_for_street <= previous_bet_to_match_on_table:
        # try: session.commit()
        # except Exception as e: session.rollback(); print(f"Error committing on raise legality (amount <= prev bet) for user {user_id}: {e}")
        return {"error": f"Raise amount ({action_amount_total_for_street}) must be greater than current bet to match ({previous_bet_to_match_on_table})."}

    is_valid_raise, validation_message = _validate_bet(
        player_state=player_state,
        action_amount=action_amount_total_for_street, # This is the 'amount' parameter of handle_raise
        current_bet_to_match=previous_bet_to_match_on_table,
        min_next_raise_increment=poker_hand.min_next_raise_amount or poker_table.big_blind,
        limit_type=poker_table.limit_type,
        poker_table=poker_table,
        player_amount_invested_this_street=player_invested_this_street,
        current_hand_pot_size=poker_hand.pot_size_sats or 0 # Pot size before this player's call portion
    )

    if not is_valid_raise:
        # try: session.commit()
        # except Exception as e: session.rollback(); print(f"Error committing on invalid raise validation for user {user_id}: {e}")
        return {"error": f"Invalid raise: {validation_message}"}

    # Calculate the actual additional chips based on the validated action_amount_total_for_street (raise amount 'amount')
    amount_player_needs_to_add_for_this_raise = action_amount_total_for_street - player_invested_this_street

    # This check should be covered by _validate_bet (chips_for_this_action < 0) or subsequent logic,
    # but as a safeguard here if action_amount_total_for_street was somehow miscalculated.
    if amount_player_needs_to_add_for_this_raise <= 0:
         return {"error": "Raise results in no additional chips being added to the pot. This should have been caught by validation."}

    actual_amount_added_to_pot = min(amount_player_needs_to_add_for_this_raise, player_state.stack_sats)

    # final_player_investment_this_street is same as action_amount_total_for_street if player not stack constrained,
    # otherwise it's player_invested_this_street + actual_amount_added_to_pot (their all-in amount).
    final_player_investment_this_street = player_invested_this_street + actual_amount_added_to_pot

    # is_all_in is true if the player commits their entire stack AND this amount is less than what they *intended* to add for the raise
    # OR if they intended to raise their exact stack size.
    # More simply: if actual_amount_added_to_pot is their entire stack.
    is_all_in = (actual_amount_added_to_pot == player_state.stack_sats)
    # Refined is_all_in for "raise_all_in" string: implies they might have wanted to raise more but couldn't.
    # This happens if the actual amount they could add is less than the amount they needed for their declared raise total,
    # and they indeed added all their chips.
    is_all_in_short = is_all_in and (actual_amount_added_to_pot < amount_player_needs_to_add_for_this_raise)


    player_state.stack_sats -= actual_amount_added_to_pot
    player_state.total_invested_this_hand = (player_state.total_invested_this_hand or 0) + actual_amount_added_to_pot

    poker_hand.player_street_investments[str(user_id)] = final_player_investment_this_street
    poker_hand.pot_size_sats = (poker_hand.pot_size_sats or 0) + actual_amount_added_to_pot

    # The new minimum increment for the *next* raise is the size of this raise.
    poker_hand.min_next_raise_amount = final_player_investment_this_street - previous_bet_to_match_on_table
    poker_hand.current_bet_to_match = final_player_investment_this_street
    poker_hand.last_raiser_user_id = user_id

    action_string = "raise_all_in" if is_all_in else "raise"
    player_state.last_action = f"{action_string}_to_{final_player_investment_this_street}"

    transaction = Transaction(
        user_id=user_id,
        amount=-actual_amount_added_to_pot,
        transaction_type='poker_action_raise',
        status='completed',
        details={
            "table_id": table_id,
            "hand_id": hand_id,
            "action": action_string,
            "raised_to_amount": final_player_investment_this_street,
            "actual_amount_added_to_pot": actual_amount_added_to_pot
        },
        poker_hand_id=hand_id
    )

    if poker_hand.hand_history is None:
        poker_hand.hand_history = []

    poker_hand.hand_history.append({
        "user_id": user_id,
        "seat_id": player_state.seat_id,
        "action": action_string,
        "amount": final_player_investment_this_street, # Total amount player has raised to this street
        "added_to_pot": actual_amount_added_to_pot, # The portion added in this specific action
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    session.add(player_state)
    session.add(poker_hand)
    session.add(poker_table) # Though not modified
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
        current_app.logger.error(f"Error during raise action for user {user_id} in hand {hand_id}: {e}")
        return {"error": "Could not process raise due to a server error.", "details": str(e)}


def _validate_bet(player_state: PokerPlayerState,
                  action_amount: int, # The total amount the player's street investment will be post-action.
                  current_bet_to_match: int, # The current highest total bet any player has made in this street.
                  min_next_raise_increment: int, # The minimum additional amount for a valid raise (e.g., BB or last raise size).
                                                # For an opening bet, this isn't strictly "raise increment" but helps define min opening bet.
                  limit_type: str, # "no_limit", "pot_limit", "fixed_limit"
                  poker_table: PokerTable, # Provides BB, SB, and for PLO, the current hand's pot_size_sats
                  player_amount_invested_this_street: int,
                  current_hand_pot_size: int # Crucial for PLO max bet calculation. This is pot *before* player's call.
                  ) -> tuple[bool, str]:
    """
    Validates a bet or raise amount based on game rules.
    `action_amount` is the total cumulative amount the player intends to have invested in the current street after this action.

    Args:
        player_state (PokerPlayerState): The state of the player making the action.
        action_amount (int): The total cumulative amount for the street post-action.
        current_bet_to_match (int): Current highest total investment by any player this street.
        min_next_raise_increment (int): The minimum delta for a raise (e.g., BB or last raise size).
                                        Used to calculate min_raise_amount_total.
        limit_type (str): "no_limit", "pot_limit", "fixed_limit".
        poker_table (PokerTable): Provides big_blind, small_blind.
        player_amount_invested_this_street (int): How much player already put in this street.
        current_hand_pot_size (int): Current total pot size of the hand (for PLO calculations primarily).
                                      This is the pot *before* the current player's implied call portion of a raise.

    Returns:
        tuple[bool, str]: (is_valid, message). Message explains why invalid or confirms validity type.
    """

    chips_for_this_action = action_amount - player_amount_invested_this_street

    if chips_for_this_action < 0:
        # This case should ideally be prevented by UI or earlier logic,
        # as action_amount should always be >= player_amount_invested_this_street.
        return False, "Invalid action: Total action amount is less than already invested this street."

    if chips_for_this_action > player_state.stack_sats:
        # Player doesn't have enough chips for the desired additional amount.
        return False, f"Insufficient stack. Trying to commit {chips_for_this_action} additional chips, but only have {player_state.stack_sats}."

    # An action is "all-in" if the player commits all their remaining stack with this action.
    is_all_in = (chips_for_this_action == player_state.stack_sats)

    min_opening_bet_size = poker_table.big_blind # Standard for NL/PL. FL is street-dependent.

    # --- Path 1: Action is a Call or Check ---
    # If action_amount makes player's total investment for street equal to current_bet_to_match
    if action_amount == current_bet_to_match:
        if chips_for_this_action == 0: # No additional chips, so it's a check.
            # Legality of check (e.g. if there was a bet before them) is handled before calling _validate_bet typically.
            # This path assumes it's a valid situation for a check amount-wise.
            return True, "Valid check."
        else: # Additional chips are being committed to match current_bet_to_match. This is a call.
            # If is_all_in, it's an all-in call for the exact amount.
            return True, "Valid call." if not is_all_in else "Valid all-in call (exact amount)."

    # --- Path 2: Action is a Call for Less (Player is All-In) ---
    # If action_amount is less than current_bet_to_match
    if action_amount < current_bet_to_match:
        if is_all_in: # Player must be all-in if their total street investment is less than current_bet_to_match
            return True, "Valid all-in call for less."
        else: # Not all-in, so it's an invalid under-call. This should be caught by chips_for_this_action > player_state.stack_sats.
              # However, if action_amount was manually set lower without being all-in.
            return False, f"Action amount {action_amount} is an invalid undercall of current bet {current_bet_to_match} (player not all-in)."

    # --- Path 3: Action is a Bet or Raise (action_amount > current_bet_to_match) ---
    # This means player is increasing the current bet to match.

    is_opening_action = (current_bet_to_match == 0)
    # Note: BB re-opening preflop is a special case: current_bet_to_match is BB, player_invested is BB.
    # If they raise, action_amount > current_bet_to_match. This is not an "opening action" by current_bet_to_match == 0.

    if limit_type == "no_limit":
        if is_opening_action: # This is an opening bet
            # chips_for_this_action is the size of the opening bet.
            if chips_for_this_action < min_opening_bet_size and not is_all_in:
                return False, f"No-Limit opening bet ({chips_for_this_action}) is less than minimum opening bet size ({min_opening_bet_size})."
            return True, "Valid No-Limit opening bet." if not is_all_in else "Valid No-Limit all-in opening bet."
        else: # This is a raise
            # min_next_raise_increment is the minimum *additional* amount of the raise.
            # So, the total amount for the raise must be at least current_bet_to_match + min_next_raise_increment.
            min_raise_target_total = current_bet_to_match + min_next_raise_increment
            if action_amount < min_raise_target_total and not is_all_in:
                return False, f"No-Limit raise to {action_amount} is less than minimum required raise total of {min_raise_target_total} (current bet {current_bet_to_match} + min increment {min_next_raise_increment})."
            return True, "Valid No-Limit raise." if not is_all_in else "Valid No-Limit all-in raise."

    elif limit_type == "pot_limit":
        # For PLO, min_next_raise_increment from hand state (last raise size) or BB if first raise on street.
        effective_min_valid_raise_increment_for_plo = min_next_raise_increment if min_next_raise_increment > 0 else poker_table.big_blind

        min_pl_raise_target, max_pl_raise_target = _calculate_pot_limit_raise_sizes(
            player_current_stack=player_state.stack_sats,
            player_invested_this_street=player_amount_invested_this_street,
            current_pot_total=current_hand_pot_size, # This is pot *before* this player's call portion
            bet_to_match_this_street=current_bet_to_match,
            min_valid_raise_increment=effective_min_valid_raise_increment_for_plo
        )

        if is_opening_action: # Pot-Limit opening bet
            if chips_for_this_action < min_opening_bet_size and not is_all_in:
                return False, f"Pot-Limit opening bet ({chips_for_this_action}) is less than minimum opening bet size ({min_opening_bet_size})."
            # action_amount is total investment for street. For opening bet, this is chips_for_this_action.
            # It must be <= max_pl_raise_target (which for opening bet, is calculated based on current_bet_to_match=0).
            if action_amount > max_pl_raise_target and not is_all_in:
                 return False, f"Pot-Limit opening bet to {action_amount} (chips: {chips_for_this_action}) exceeds max pot limit target of {max_pl_raise_target}."
            return True, "Valid Pot-Limit opening bet." if not is_all_in else "Valid Pot-Limit all-in opening bet."
        else: # Pot-Limit raise
            # action_amount is the total player is making their investment for the street.
            if action_amount < min_pl_raise_target and not is_all_in:
                return False, f"Pot-Limit raise to {action_amount} is less than Pot-Limit min raise target of {min_pl_raise_target}."
            if action_amount > max_pl_raise_target and not is_all_in:
                return False, f"Pot-Limit raise to {action_amount} exceeds Pot-Limit max raise target of {max_pl_raise_target}."
            # If all-in, validity is determined by action_amount > current_bet_to_match and _calculate_pot_limit_raise_sizes handling stack limits.
            return True, "Valid Pot-Limit raise." if not is_all_in else "Valid Pot-Limit all-in raise."

    elif limit_type == "fixed_limit":
        # Simplified: Assume poker_table.big_blind is the fixed bet/raise amount for the current street.
        # A full FL implementation needs current_street to determine if it's small or big bet tier,
        # and also needs to track number of raises made on the current street if there's a cap.
        # For this function, we'll assume the correct fixed_bet_amount for the street is passed via min_next_raise_increment
        # or derived if a street parameter were available. Using poker_table.big_blind is a placeholder.
        fixed_bet_increment = poker_table.big_blind # Placeholder: This should be street-dependent (e.g. BB or 2xBB)
                                                    # And could be passed in via a refined min_next_raise_increment for FL.

        if is_opening_action: # Fixed-Limit opening bet
            # In FL, an opening bet must be exactly the fixed_bet_increment, unless all-in for less.
            if chips_for_this_action != fixed_bet_increment and not is_all_in:
                return False, f"Fixed-Limit bet ({chips_for_this_action}) must be exactly {fixed_bet_increment} (unless all-in for less)."
            return True, "Valid Fixed-Limit bet." if not is_all_in else "Valid Fixed-Limit all-in bet."
        else: # Fixed-Limit raise
            # A raise must make the total investment for the street exactly current_bet_to_match + fixed_bet_increment.
            expected_total_after_raise = current_bet_to_match + fixed_bet_increment
            if action_amount != expected_total_after_raise and not is_all_in:
                 return False, f"Fixed-Limit raise to {action_amount} is invalid. Must make total investment {expected_total_after_raise} (current bet {current_bet_to_match} + fixed increment {fixed_bet_increment})."
            # Note: Cap on number of raises per street in FL games is not handled here. Needs more state if required.
            return True, "Valid Fixed-Limit raise." if not is_all_in else "Valid Fixed-Limit all-in raise."

    return False, f"Unknown limit type '{limit_type}' or unhandled validation scenario for action_amount {action_amount}."


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
    # Amount player needs to add to just call the current bet_to_match_this_street
    amount_to_call_action = bet_to_match_this_street - player_invested_this_street
    if amount_to_call_action < 0:
        amount_to_call_action = 0 # Player has already invested enough, effectively a call costs 0 more.

    # 1. Calculate Minimum Raise Target
    # The minimum total investment a player must make for a valid raise.
    # This is the current bet to match plus the minimum valid raise increment.
    min_raise_target_total_investment = bet_to_match_this_street + min_valid_raise_increment

    # However, player cannot bet more than their stack.
    # The actual number of chips they would add for a minimum raise:
    chips_for_min_raise_action = min_raise_target_total_investment - player_invested_this_street
    # Player can only add what they have in their stack
    chips_for_min_raise_action_capped_by_stack = min(chips_for_min_raise_action, player_current_stack)

    # Effective total investment if player makes the minimum possible raise (could be all-in)
    effective_min_raise_total_street_investment = player_invested_this_street + chips_for_min_raise_action_capped_by_stack

    # 2. Calculate Maximum Raise Target (Pot-Sized Raise)
    # "The 'pot' in PLO is defined as the total of the active pot, plus all bets on the table,
    #  plus the amount the active player must first call before raising."
    # current_pot_total = all chips in the pot from previous streets and current street actions BEFORE this player acts.
    # Pot size for calculation = current_pot_total + (all bets on table currently) + (the call this player makes)
    # A simpler way to think: pot_size_if_player_calls = current_pot_total (which includes previous bets this street) + amount_to_call_action

    pot_size_if_player_calls = current_pot_total + amount_to_call_action

    # The player can raise BY this amount (pot_size_if_player_calls), ON TOP of their call.
    # So, chips for pot raise action = amount_to_call_action (to call) + pot_size_if_player_calls (the raise amount).
    chips_for_pot_raise_action = amount_to_call_action + pot_size_if_player_calls

    # Player can only add what they have in their stack
    chips_for_pot_raise_action_capped_by_stack = min(chips_for_pot_raise_action, player_current_stack)

    # Effective total investment if player makes the maximum pot-sized raise (could be all-in)
    effective_max_raise_total_street_investment = player_invested_this_street + chips_for_pot_raise_action_capped_by_stack

    # Ensure that the calculated "max raise" isn't less than a "min raise" if stack is very constrained.
    # If player is all-in, their max raise is their all-in amount.
    # The min raise must still be a valid raise (i.e., more than just calling bet_to_match_this_street).
    if effective_min_raise_total_street_investment <= bet_to_match_this_street:
        # This means the player cannot even make the minimum defined increment.
        # Their only "raise" option is to go all-in, if that all-in amount is greater than bet_to_match_this_street.
        all_in_total_investment_for_street = player_invested_this_street + player_current_stack
        if all_in_total_investment_for_street > bet_to_match_this_street:
            # The only possible "raise" is all-in. So min and max raise targets are the same (their all-in amount).
            return (all_in_total_investment_for_street, all_in_total_investment_for_street)
        else:
            # No raise is possible (even all-in is just a call or less).
            # Return the bet_to_match_this_street as min_raise_target (effectively meaning only call is possible for this amount)
            # and the all_in amount as max (which is <= bet_to_match_this_street).
            # The calling function (_validate_bet) will interpret this.
            return (bet_to_match_this_street, all_in_total_investment_for_street)

    # Max raise cannot be less than min raise. If stack constrains pot raise to be less than a standard min raise,
    # then the max is effectively the min (or all-in if that's even smaller but still a raise).
    final_max_raise = max(effective_min_raise_total_street_investment, effective_max_raise_total_street_investment)

    return (effective_min_raise_total_street_investment, final_max_raise)


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
        current_app.logger.error(f"Error converting board cards for treys: {board_cards_str} - {e}")
        # Consider how to handle this - perhaps invalidate the hand or return error
        return []

    best_score = float('inf')  # Lower score is better in treys
    winners = []

    for user_id, hole_cards_str_list in player_hole_cards_map.items():
        if not hole_cards_str_list or len(hole_cards_str_list) != 2:
            # Log warning or skip player
            current_app.logger.warning(f"User {user_id} has invalid hole cards: {hole_cards_str_list}")
            continue

        try:
            # Ensure hole_cards_str is a list of strings, then convert
            hand = [Card.from_string(to_treys_card_str(c)) for c in hole_cards_str_list]
        except Exception as e:
            # Log error: Invalid card string in hole_cards
            current_app.logger.error(f"Error converting hole cards for user {user_id}: {hole_cards_str_list} - {e}")
            continue # Skip this player

        # Evaluate the hand (board + player's hole cards)
        # treys evaluate function takes board and hand (player's cards)
        score = evaluator.evaluate(board, hand)
        hand_class_str = evaluator.class_to_string(evaluator.get_rank_class(score))

        # For "best_five_cards", we'll just return the combination of hole + board as a proxy.
        # A more advanced implementation might try to find the exact 5 cards.
        combined_cards_str = hole_cards_str_list + board_cards_str

        # DEBUG LOG: Original line logged hole cards: current_app.logger.debug(f"User {user_id}, Hole: {hole_cards_str_list}, Board: {board_cards_str}, Score: {score}, Hand Class: {hand_class_str}")
        # Hole cards redacted for security in general logging:
        current_app.logger.info(f"User {user_id} evaluation - Board: {board_cards_str}, Score: {score}, Hand Class: {hand_class_str}")

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
    """
    session = db.session
    poker_table = session.query(PokerTable).get(poker_hand.table_id)

    if not poker_table:
        current_app.logger.error(f"PokerTable {poker_hand.table_id} not found for pot distribution of hand {poker_hand.id}.")
        # This is a critical error, likely indicates data integrity issue or programming error.
        # Depending on desired robustness, could try to proceed without rake or raise exception.
        # For now, let's assume this is fatal for pot distribution.
        return {"error": f"Table not found for pot distribution, hand {poker_hand.id}"}

    # --- 1. Prepare Player Data for Showdown ---
    players_data_for_pots = []
    for ps in showdown_player_states:
        if not ps.hole_cards or len(ps.hole_cards) != 2:
            # Log this, but might not be critical to stop if other players are valid.
            # However, a player at showdown should always have hole cards.
            current_app.logger.warning(f"Player {ps.user_id} at showdown for hand {poker_hand.id} has invalid hole cards: {ps.hole_cards}. Skipping for pot eligibility.")
            continue

        # total_invested_this_hand should be accurately tracked by action handlers.
        # Fallback or error if not present could be added, but spec assumes it's populated.
        total_invested = ps.total_invested_this_hand if ps.total_invested_this_hand is not None else 0

        players_data_for_pots.append({
            'user_id': ps.user_id,
            'total_invested': total_invested,
            'hole_cards_str': ps.hole_cards, # String representation like ["HA", "SK"]
            'player_state_obj': ps # Direct reference to the SQLAlchemy object for stack updates
        })

    if not players_data_for_pots:
        if poker_hand.pot_size_sats > 0:
            # This case means the pot has money, but no valid showdown players were passed.
            # This might happen if only one player remained due to folds (handled before calling _distribute_pot)
            # or an error in game flow logic.
            current_app.logger.warning(f"_distribute_pot called for hand {poker_hand.id} with pot {poker_hand.pot_size_sats} but no valid showdown players. Pot remains unawarded by this function.")
            # Consider refunding pot or specific error handling based on game rules.
        # If pot is 0 and no players, it's fine.
        poker_hand.status = 'completed' # Ensure hand is marked completed
        poker_hand.end_time = datetime.now(timezone.utc)
        session.add(poker_hand)
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            current_app.logger.error(f"Error committing hand completion with no showdown players for hand {poker_hand.id}: {e}")
        return # Or return a status indicating no distribution needed/possible.

    # --- 2. Rake Calculation ---
    total_pot_value_before_rake = poker_hand.pot_size_sats or 0
    actual_rake = 0

    # Apply rake only if conditions are met (e.g., flop seen, or always if pot > 0 as per simplified rule)
    # For now, applying if pot > 0 based on table settings.
    # A more advanced rule: if poker_hand.status not in ['preflop', 'completed'] or len(poker_hand.board_cards) > 0
    if total_pot_value_before_rake > 0:
        rake_percentage = poker_table.rake_percentage if poker_table.rake_percentage is not None else Decimal("0.00")
        max_rake = poker_table.max_rake_sats if poker_table.max_rake_sats is not None else 0

        if rake_percentage > Decimal("0.00"):
            calculated_rake = int(Decimal(total_pot_value_before_rake) * rake_percentage)
            if max_rake > 0: # Apply cap only if max_rake is positive
                actual_rake = min(calculated_rake, max_rake)
            else: # No cap or cap is 0
                actual_rake = calculated_rake

        actual_rake = max(0, actual_rake) # Ensure rake is not negative
        actual_rake = min(actual_rake, total_pot_value_before_rake) # Rake cannot exceed total pot

    poker_hand.rake_sats = actual_rake
    distributable_pot_overall = total_pot_value_before_rake - actual_rake
    if distributable_pot_overall < 0: # Should not happen with current logic
        distributable_pot_overall = 0


    # --- 3. Create Pots (Main and Side Pots) ---
    # Sort players by their total investment for this hand in ascending order
    # This order is crucial for correctly layering investments into pots.
    sorted_players_by_investment = sorted(players_data_for_pots, key=lambda x: x['total_invested'])

    created_pots = [] # List of dicts: {'amount': int, 'eligible_user_ids': set[int], 'description': str}
    last_cap_level = 0 # Tracks the investment level covered by previous pots

    # Iterate through each player's unique investment level to define pot boundaries
    unique_investment_levels = sorted(list(set(p['total_invested'] for p in sorted_players_by_investment)))

    for cap_level in unique_investment_levels:
        if cap_level <= last_cap_level: # Already processed up to or beyond this level
            continue

        contribution_this_layer = cap_level - last_cap_level
        current_pot_value_from_investments = 0
        eligible_players_for_this_pot = set()

        for p_data in sorted_players_by_investment: # Iterate all players to see who contributes to this layer
            # Amount this player contributes *to this specific layer*
            player_contribution_to_layer = min(contribution_this_layer, max(0, p_data['total_invested'] - last_cap_level))

            if player_contribution_to_layer > 0:
                current_pot_value_from_investments += player_contribution_to_layer
                eligible_players_for_this_pot.add(p_data['user_id'])

        if current_pot_value_from_investments > 0:
            pot_description = f"Main Pot" if not created_pots else f"Side Pot {len(created_pots)}"
            # The actual amount for this pot is capped by what's left in distributable_pot_overall
            amount_for_this_pot = min(current_pot_value_from_investments, distributable_pot_overall - sum(p['amount'] for p in created_pots))

            if amount_for_this_pot > 0 :
                 created_pots.append({
                    'amount': amount_for_this_pot,
                    'eligible_user_ids': eligible_players_for_this_pot,
                    'description': pot_description
                })
            elif distributable_pot_overall <= sum(p['amount'] for p in created_pots) and current_pot_value_from_investments > 0:
                # This means no more distributable money left for further side pots from player actual investments.
                # This can happen if rake consumed the remaining amounts.
                current_app.logger.info(f"Hand {poker_hand.id}: Pot layer for cap {cap_level} calculated {current_pot_value_from_investments}, but no distributable funds left due to rake. Sum of created pots: {sum(p['amount'] for p in created_pots)}, Distributable: {distributable_pot_overall}")
                break # No more money to distribute

        last_cap_level = cap_level

    # Sanity check: If sum of created pots (from distributable amount) is less than total distributable_pot_overall
    # (e.g., due to all players being all-in for same small amount and rake making it complex),
    # distribute any remaining small amount. This is rare with integer math if rake is handled first.
    # The current logic should allocate distributable_pot_overall correctly across layers.
    # If any distributable_pot_overall remains unallocated to a pot layer (shouldn't happen if players invested), it's an issue.

    # --- 4. Determine Winners and Distribute Each Pot ---
    final_hand_winners_summary = [] # To be stored in PokerHand.winners

    for pot_info in created_pots:
        pot_amount = pot_info['amount']
        eligible_user_ids = pot_info['eligible_user_ids']
        pot_description = pot_info['description']

        if pot_amount <= 0: # No value in this pot to distribute
            continue

        # Prepare data for _determine_winning_hand for this specific pot
        hole_cards_for_this_pot_eval = {
            p_data['user_id']: p_data['hole_cards_str']
            for p_data in players_data_for_pots # Use original full list to find user_ids
            if p_data['user_id'] in eligible_user_ids and p_data['hole_cards_str']
        }

        if not hole_cards_for_this_pot_eval:
            current_app.logger.warning(f"Hand {poker_hand.id}, Pot '{pot_description}': No eligible players with cards found for evaluation. Amount {pot_amount} unawarded.")
            continue

        # Determine winner(s) for this pot
        # _determine_winning_hand returns list of dicts: [{"user_id": X, "winning_hand": "...", "best_five_cards": [...]}, ...]
        winners_of_this_pot = _determine_winning_hand(hole_cards_for_this_pot_eval, poker_hand.board_cards or [])

        if not winners_of_this_pot:
            current_app.logger.warning(f"Hand {poker_hand.id}, Pot '{pot_description}': _determine_winning_hand returned no winners. Amount {pot_amount} unawarded.")
            continue

        num_winners_this_pot = len(winners_of_this_pot)
        # Handle odd chips: integer division means leftover chips are currently discarded per pot.
        # For more precise handling, odd chips could be awarded to player in earliest position, or accumulated.
        amount_per_winner = pot_amount // num_winners_this_pot

        if amount_per_winner <= 0 and pot_amount > 0 : # If pot has value but per-winner is 0 (many winners of tiny pot)
            current_app.logger.warning(f"Hand {poker_hand.id}, Pot '{pot_description}': pot amount {pot_amount} results in {amount_per_winner} per winner for {num_winners_this_pot} winners. Chips may be lost.")
            # Potentially award to first winner if amount_per_winner is 0 but pot_amount > 0
            # For now, proceeding with amount_per_winner as calculated.

        for winner_data in winners_of_this_pot:
            winner_user_id = winner_data['user_id']

            # Find the PokerPlayerState object for the winner to update their stack
            winner_player_state = next((p['player_state_obj'] for p in players_data_for_pots if p['user_id'] == winner_user_id), None)
            winner_user_account = session.query(User).get(winner_user_id) # For username in summary

            if winner_player_state and winner_user_account:
                if amount_per_winner > 0: # Only process if there's an actual amount to award
                    winner_player_state.stack_sats += amount_per_winner
                    session.add(winner_player_state)

                    # Create Transaction for winnings
                    win_transaction = Transaction(
                        user_id=winner_user_id,
                        amount=amount_per_winner,
                        transaction_type='poker_win',
                        status='completed',
                        details={
                            "hand_id": poker_hand.id,
                            "table_id": poker_hand.table_id,
                            "pot_description": pot_description,
                            "amount_won_from_this_pot": amount_per_winner,
                            "this_pot_total_value_distributed": pot_amount, # Pot value before this winner's share
                            "num_winners_for_this_pot": num_winners_this_pot,
                            "winning_hand_description": winner_data.get("winning_hand", "Unknown"),
                            "board_cards_at_showdown": poker_hand.board_cards or []
                        },
                        poker_hand_id=poker_hand.id
                    )
                    session.add(win_transaction)

                # Add to summary regardless of amount (e.g. won a $0 split pot if that's possible)
                final_hand_winners_summary.append({
                    "user_id": winner_user_id,
                    "username": winner_user_account.username,
                    "amount_won": amount_per_winner, # This is share from this specific pot
                    "pot_description": pot_description,
                    "winning_hand": winner_data.get("winning_hand", "Unknown"),
                    "best_five_cards": winner_data.get("best_five_cards", []) # From _determine_winning_hand
                })
            else:
                current_app.logger.error(f"Hand {poker_hand.id}, Pot '{pot_description}': Could not find PlayerState or User account for winner ID {winner_user_id}.")

    # --- 5. Finalize Hand ---
    poker_hand.winners = final_hand_winners_summary # Store detailed winner breakdown
    poker_hand.end_time = datetime.now(timezone.utc)
    poker_hand.status = 'completed' # Mark hand as fully completed
    session.add(poker_hand)

    try:
        session.commit()
        # current_app.logger.info(f"Hand {poker_hand.id} pot distribution complete. Rake: {poker_hand.rake_sats}. Winners summary: {final_hand_winners_summary}")
    except Exception as e:
        session.rollback()
        current_app.logger.error(f"Error during final commit of pot distribution for hand {poker_hand.id}: {e}")
        # This is a server-side error; the calling context might need to be aware.
        # For now, error is logged. Potentially return an error status.
        return {"error": f"Failed to commit pot distribution for hand {poker_hand.id}: {str(e)}"}

    return {"status": "pot_distributed", "hand_id": poker_hand.id, "winners": final_hand_winners_summary, "rake_taken": poker_hand.rake_sats}


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
#             current_app.logger.info(f"Player {player_to_act_state.user_id} at seat {player_to_act_state.seat_id} timed out after {time_elapsed:.2f}s. Auto-folding.")
#
#             original_turn_user_id = player_to_act_state.user_id
#             # It's crucial that handle_fold is called, which then calls _check_betting_round_completion
#             # to correctly update game state including turn timers and player status.
#             # The handle_fold function should also ensure player_to_act_state.turn_starts_at is cleared after folding.
#             fold_result = handle_fold(original_turn_user_id, poker_hand.table_id, poker_hand.id) # handle_fold will manage session commit
#             current_app.logger.info(f"Auto-fold result for user {original_turn_user_id}: {fold_result}")
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
            joinedload(PokerHand.table).joinedload(PokerTable.player_states).joinedload(PokerPlayerState.user) # Load table and all player states
            # removed: joinedload(PokerHand.player_states_in_hand)
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
        poker_hand.status = "flop" # <<< SETTING HAND STATUS
    elif num_board_cards == 3: # Flop -> Turn
        next_street_name = "turn"
        cards_to_deal_count = 1
        poker_hand.status = "turn" # <<< SETTING HAND STATUS
    elif num_board_cards == 4: # Turn -> River
        next_street_name = "river"
        cards_to_deal_count = 1
        poker_hand.status = "river" # <<< SETTING HAND STATUS
    elif num_board_cards == 5: # River -> Showdown
        poker_hand.status = "showdown" # <<< SETTING HAND STATUS
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
        poker_hand.status = "showdown" # <<< SETTING HAND STATUS (all-in or one left)
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
        first_to_act_postflop.time_to_act_ends = datetime.now(timezone.utc) + timedelta(seconds=POKER_ACTION_TIMEOUT_SECONDS)
        session.add(first_to_act_postflop)

        poker_hand.hand_history.append({
            "action": "set_next_to_act",
            "street": next_street_name,
            "user_id": first_to_act_postflop.user_id,
            "seat_id": first_to_act_postflop.seat_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    else:
        # Should be handled by the active_players_in_hand check earlier or implies showdown
        current_app.logger.warning(f"Could not determine first player to act for {next_street_name} in hand {hand_id}.")
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
    last_actor_ps = session.query(PokerPlayerState).filter_by(user_id=last_actor_user_id, table_id=poker_hand.table_id).first()
    if last_actor_ps:
        last_actor_ps.time_to_act_ends = None
        session.add(last_actor_ps)

    # 1. Check for Hand End by Folds
    if len(active_players_still_in_hand) <= 1:
        winner_user_id = active_players_still_in_hand[0].user_id if active_players_still_in_hand else None

        # Ensure any other potentially active timer is cleared
        if poker_hand.current_turn_user_id and poker_hand.current_turn_user_id != last_actor_user_id: # If current turn was not the one who folded to end hand
            other_ps_to_clear = session.query(PokerPlayerState).filter_by(user_id=poker_hand.current_turn_user_id, table_id=poker_hand.table_id).first()
            if other_ps_to_clear:
                other_ps_to_clear.time_to_act_ends = None
                session.add(other_ps_to_clear)

        poker_hand.current_turn_user_id = None # Hand is over, no one's turn
        # poker_hand.status = 'completed' is set below within the if winner_user_id block or if no winner (already done)
        # _distribute_pot needs a list of PokerPlayerState objects for showdown.
        # If one player wins by folds, they are the only one.
        # Ensure total_invested_this_hand is set on these player_state objects for _distribute_pot.
        # This part might need adjustment based on how _distribute_pot expects its input for fold scenarios.
        if winner_user_id:
             # Pot is awarded to the winner without showdown
             winner_player_state = active_players_still_in_hand[0]
             winner_user = session.query(User).get(winner_user_id)

             # Create transaction for the pot won
             win_transaction = Transaction(
                 user_id=winner_user_id,
                 amount=poker_hand.pot_size_sats, # Winner gets the whole pot
                 transaction_type='poker_win',
                 status='completed',
                 poker_hand_id=poker_hand.id,
                 details={
                     "hand_id": poker_hand.id,
                     "table_id": poker_hand.table_id,
                     "reason": "Opponents folded",
                     "pot_won": poker_hand.pot_size_sats
                 }
             )
             session.add(win_transaction)

             # Update winner's stack in PokerPlayerState
             winner_player_state.stack_sats += poker_hand.pot_size_sats
             session.add(winner_player_state)

             poker_hand.winners = [{ # Record winner info
                 "user_id": winner_user_id,
                 "username": winner_user.username if winner_user else "Unknown",
                 "amount_won": poker_hand.pot_size_sats,
                 "reason": "Opponents folded"
             }]
             poker_hand.status = 'completed' # <<< SETTING HAND STATUS
             poker_hand.end_time = datetime.now(timezone.utc)
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
    if current_bet > 0: # There is an outstanding bet
        for ps in active_players_still_in_hand:
            is_all_in_for_less = (ps.stack_sats == 0 and player_investments.get(str(ps.user_id), 0) < current_bet)
            if ps.stack_sats > 0 and player_investments.get(str(ps.user_id), 0) < current_bet and not is_all_in_for_less:
                players_who_must_act.append(ps)
    else: # current_bet == 0 (checking round, or option to check for BB)
        if poker_hand.last_raiser_user_id is None: # No bet made yet this street
            # Players who haven't acted yet (or whose action isn't "final" for a checking round)
            # This logic aims to keep the round going if players are yet to check.
            action_closed = True # Assume action is closed until a player is found who must act

            # Determine who would be "first to act" in this round normally to check if action has completed a full circle.
            # This is a simplified proxy for complex "action closed" logic.
            # For now, if current_bet is 0 and no raiser, any active player with chips
            # who isn't the one that just acted is considered to be "pending action".
            if len(active_players_still_in_hand) > 1 : # Only relevant if multiple players
                for ps in active_players_still_in_hand:
                    if ps.user_id == last_actor_user_id:
                        continue # Skip the player who just acted
                    if ps.stack_sats > 0 : # Active and has chips
                        # This player is pending action in a checking round.
                        players_who_must_act.append(ps)
                        # No need to break, add all who are pending.
                        # The "next player to act" logic will pick the correct one.

            # Special case for BB option: If only one player active (must be BB), and they check, round is over.
            if len(active_players_still_in_hand) == 1 and active_players_still_in_hand[0].user_id == last_actor_user_id:
                players_who_must_act = [] # BB checked, round is over.
        # If there was a raise previously, and current_bet is now 0 (should not happen unless side pots settled weirdly),
        # it implies all bets were matched. players_who_must_act would be empty by default.

    round_complete = False
    if not players_who_must_act: # No one left who needs to call/raise the current bet or act in a checking round
        # This means all active players have either matched the current_bet_to_match or are all-in for less,
        # or all players have checked in a checking round.
        round_complete = True


    if round_complete:
        # If all bettable players are all-in (or only one is not), proceed to showdown after dealing all cards
        if len(non_all_in_bettable_players) <= 1 and len(active_players_still_in_hand) > 1:
            # Advance all remaining streets automatically
            if poker_hand.board_cards is None: # Ensure board_cards is not None before len()
                poker_hand.board_cards = []
            while poker_hand.status not in ['showdown', 'completed'] and len(poker_hand.board_cards) < 5:
                adv_result = _advance_to_next_street(hand_id, session)
                if "error" in adv_result: return adv_result
                if adv_result["status"] == "showdown_reached": break

            # After all streets, it should be showdown
            if poker_hand.status != 'showdown': poker_hand.status = 'showdown' # Force if not set by advance

            # Clear timer for the current_turn_user_id if it was set
            if poker_hand.current_turn_user_id:
                current_turn_player_state = session.query(PokerPlayerState).filter_by(user_id=poker_hand.current_turn_user_id, table_id=poker_hand.table_id).first()
                if current_turn_player_state:
                    current_turn_player_state.time_to_act_ends = None
                    session.add(current_turn_player_state)

            poker_hand.current_turn_user_id = None # No more turns
            poker_hand.hand_history.append({"action": "all_in_proceed_to_showdown", "timestamp": datetime.now(timezone.utc).isoformat()})
            session.add(poker_hand)
            return {"status": "all_in_showdown", "hand_id": hand_id}
        else: # Normal round completion, advance to next street
            # last_actor_ps timer already cleared at the start of this function.
            # _advance_to_next_street will handle setting the timer for the first player of the new street.
            adv_result = _advance_to_next_street(hand_id, session)
            if "error" in adv_result: # Check for errors from _advance_to_next_street
                return adv_result
            return {"status": "round_completed_advancing_street",
                    "next_street_status": poker_hand.status, # status on poker_hand would have been updated by _advance_to_next_street
                    "next_to_act_user_id": poker_hand.current_turn_user_id, # also updated by _advance_to_next_street
                    "board_cards": list(adv_result.get('board_cards', [])), # Use board_cards from adv_result
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
        next_player_to_act.time_to_act_ends = datetime.now(timezone.utc) + timedelta(seconds=POKER_ACTION_TIMEOUT_SECONDS)
        session.add(next_player_to_act)

        session.add(poker_hand)
        return {"status": "betting_continues", "next_to_act_user_id": poker_hand.current_turn_user_id, "hand_id": hand_id}
    else:
        # This case implies that all bettable players have acted and matched the bet, or are all-in.
        # This should ideally be caught by the 'round_complete' logic.
        # If it reaches here, it's an unexpected state.
        # Timer for last_actor_user_id was already cleared at the start of the function.
        current_app.logger.warning(f"Betting round logic fell through for hand {hand_id}. No specific next actor determined, but round not flagged as complete earlier. Current turn on hand: {poker_hand.current_turn_user_id}")
        # This might indicate an issue in round_complete logic or player state.
        # For safety, assume round is over and try to advance.
        # If advancing to showdown, status will be set there.
        # If advancing to another street, status will be set there.
        adv_result = _advance_to_next_street(hand_id, session) # This will set status like 'flop', 'turn', 'river', or 'showdown'
        session.add(poker_hand) # Ensure poker_hand status change from _advance_to_next_street is staged
        return {"status": "round_completed_advancing_street_fallback",
                "next_street_status": poker_hand.status, # Reflects status set by _advance_to_next_street
                "next_to_act_user_id": poker_hand.current_turn_user_id, # Could be None
                "hand_id": hand_id}


def check_and_handle_player_timeouts(table_id: int, session: Session) -> bool:
    """
    Checks the current player for timeout and auto-folds them.
    This would ideally be triggered by a separate scheduler or before processing any player action request.
    Returns True if a timeout action was taken, False otherwise.
    The actual auto-fold action should call the handle_fold function to ensure game state consistency.
    """
    # Find the current active hand for this table
    poker_hand = session.query(PokerHand).filter(
        PokerHand.table_id == table_id,
        PokerHand.status.notin_(['completed', 'showdown'])
    ).order_by(PokerHand.start_time.desc()).first()

    if not poker_hand or poker_hand.current_turn_user_id is None:
        return False # No active hand or no one's turn

    player_to_act_state = session.query(PokerPlayerState).filter_by(
        user_id=poker_hand.current_turn_user_id,
        table_id=poker_hand.table_id
    ).first()

    if not player_to_act_state:
        current_app.logger.error(f"Player state not found for current turn user {poker_hand.current_turn_user_id} in hand {poker_hand.id}")
        return False # Should not happen

    if player_to_act_state.time_to_act_ends and datetime.now(timezone.utc) > player_to_act_state.time_to_act_ends:
        original_turn_user_id = player_to_act_state.user_id
        seat_id = player_to_act_state.seat_id # For logging

        current_app.logger.info(f"Player {original_turn_user_id} at seat {seat_id} on table {table_id} timed out for hand {poker_hand.id}. Auto-folding.")

        # Clear the timer immediately to prevent re-entry if handle_fold has delays or issues
        player_to_act_state.time_to_act_ends = None
        session.add(player_to_act_state)
        try:
            session.commit() # Commit the timer clear before calling handle_fold
        except Exception as e:
            session.rollback()
            current_app.logger.error(f"Error committing timeout clear for user {original_turn_user_id}: {e}")
            # Proceed with fold attempt anyway, but this is problematic

        # Call handle_fold. This function is expected to manage its own session commits/rollbacks.
        fold_result = handle_fold(original_turn_user_id, poker_hand.table_id, poker_hand.id)

        if "error" in fold_result:
            current_app.logger.error(f"Error during auto-fold for user {original_turn_user_id} due to timeout: {fold_result['error']}")
            # Potentially mark player as sitting out or other error handling
        else:
            current_app.logger.info(f"Auto-fold successful for user {original_turn_user_id} due to timeout.")
            # The game_flow result from handle_fold will indicate next player and their timer will be set
            # by _check_betting_round_completion.

        return True # Timeout action was taken (attempted)

    return False


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
            # current_app.logger.warning(f"Hand {hand_id} not found for table {table_id}, but returning table state.")

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

# current_app.logger.info("poker_helper.py structure created with placeholders.") # This print is at module level
