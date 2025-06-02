from datetime import datetime, timezone
import random
import secrets # Added import
# import json # Not strictly needed if BlackjackHand.details is handled by SQLAlchemy's JSON type directly
from casino_be.models import db, User, GameSession, BlackjackHand, BlackjackAction, BlackjackTable, Transaction # Ensure BlackjackAction is used or removed if not.

# --- Card Constants ---
SUITS = ['H', 'D', 'C', 'S']  # Hearts, Diamonds, Clubs, Spades
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A'] # T for Ten

# --- Core Helper Functions ---

def _create_deck(num_decks=1):
    """Creates a list of cards, e.g., ["H2", "SA", ...]."""
    deck = []
    for _ in range(num_decks):
        for suit in SUITS:
            for rank in RANKS:
                deck.append(suit + rank)
    return deck

def _shuffle_deck(deck):
    """Shuffles the deck in place using a cryptographically secure RNG."""
    secure_random = secrets.SystemRandom()
    secure_random.shuffle(deck)

def _deal_card(deck_list):
    """Deals a card from the deck_list. Modifies the deck_list."""
    if not deck_list:
        # This should ideally not happen if deck management is correct per game round
        raise ValueError("Deck is empty. Cannot deal card.")
    return deck_list.pop()

def _get_card_value(card_str):
    """
    Determines the Blackjack value of a card string.
    Returns rank value, and 11 for Ace.
    Example: "HA" -> 11, "HK" -> 10, "H7" -> 7.
    """
    rank = card_str[1]
    if rank == 'A':
        return 11
    elif rank in ['K', 'Q', 'J', 'T']:
        return 10
    else:
        return int(rank)

def _calculate_hand_value(cards_list):
    """
    Calculates the value of a hand (list of card strings).
    Correctly handles Aces (1 or 11).
    Returns a tuple: (total_value, is_soft), where is_soft is True if an Ace is counted as 11.
    """
    total = 0
    num_aces = 0
    for card_str in cards_list:
        value = _get_card_value(card_str)
        if value == 11:  # Ace
            num_aces += 1
        total += value

    # Store the original number of aces, as num_aces will be decremented.
    original_num_aces = num_aces

    # Adjust for Aces if total > 21
    while total > 21 and num_aces > 0:
        total -= 10  # Change an Ace from 11 to 1
        num_aces -= 1 # This ace is now effectively a 1, not an 11.

    # A hand is soft if it contains an Ace that is currently counted as 11,
    # and the total value is not over 21.
    # The variable `num_aces` at this point holds the count of Aces still being treated as 11.
    is_soft = (num_aces > 0) and (total <= 21)

    return total, is_soft

def _create_player_hand_obj(cards_list=None, bet_sats=0, bet_multiplier=1.0):
    """
    Creates a new player hand object dictionary.
    `cards_list` should be a list of card strings.
    """
    if cards_list is None:
        cards_list = []

    total, is_soft = _calculate_hand_value(cards_list)
    is_blackjack_val = len(cards_list) == 2 and total == 21

    return {
        "cards": list(cards_list), # Ensure it's a copy
        "total": total,
        "is_soft": is_soft,
        "is_busted": total > 21,
        "is_blackjack": is_blackjack_val,
        "is_standing": False,
        "is_doubled": False, # Will be set true by 'double' action
        "bet_sats": bet_sats, # Stores the actual bet amount for this hand (can change with split/double)
        "bet_multiplier": bet_multiplier, # For display or if base bet is stored elsewhere; actual_bet_sats is probably better
        "result": "pending"  # 'win', 'lose', 'push', 'blackjack_win'
    }


# --- Main Game Functions ---

def handle_join_blackjack(user, table, bet_amount_sats):
    """
    Handles a user joining a blackjack game (equivalent to placing a bet and starting a new round).
    """
    # --- Validation ---
    if not isinstance(bet_amount_sats, int) or bet_amount_sats <= 0:
        raise ValueError("Bet amount must be a positive integer in Satoshis.")
    if bet_amount_sats < table.min_bet:
        raise ValueError(f"Bet amount {bet_amount_sats} is below the minimum bet of {table.min_bet}")
    if bet_amount_sats > table.max_bet:
        raise ValueError(f"Bet amount {bet_amount_sats} is above the maximum bet of {table.max_bet}")
    if user.balance < bet_amount_sats:
        raise ValueError(f"Insufficient balance. You have {user.balance} satoshis, but bet is {bet_amount_sats} satoshis")

    # TODO: Check for existing active BlackjackHand for this user/table (optional based on rules)
    # For now, assume creating a new one is always allowed, or previous one is completed/voided.

    # --- Initialization ---
    current_time = datetime.now(timezone.utc)
    
    # Create and shuffle deck(s)
    # Use table.deck_count which should be an attribute of the BlackjackTable model
    deck = _create_deck(getattr(table, 'deck_count', 1)) # Default to 1 if not set
    _shuffle_deck(deck)
    
    # Create GameSession
    game_session = GameSession(
        user_id=user.id,
        table_id=table.id,
        game_type='blackjack',
        session_start=current_time,
        amount_wagered=0, # Will be updated by transaction
        amount_won=0
    )
    db.session.add(game_session)
    # It's often better to flush related objects together or after all adds if IDs are interdependent
    # However, session_id is needed for BlackjackHand.

    # Deal initial cards
    player_initial_cards = [_deal_card(deck), _deal_card(deck)]
    dealer_initial_cards = [_deal_card(deck), _deal_card(deck)]

    # Player's first hand
    # bet_sats in player_hand_obj is the bet for THIS specific hand.
    player_hand_obj = _create_player_hand_obj(cards_list=player_initial_cards, bet_sats=bet_amount_sats, bet_multiplier=1.0)
    
    # Dealer's hand
    dealer_hand_obj = _create_player_hand_obj(cards_list=dealer_initial_cards) # No bet for dealer hand
    
    db.session.flush() # Flush game_session to get its ID if not already available.

    # Create BlackjackHand record
    new_blackjack_hand = BlackjackHand(
        user_id=user.id,
        table_id=table.id,
        session_id=game_session.id, # Ensure game_session.id is available
        initial_bet=bet_amount_sats, # The bet for the first hand
        total_bet=bet_amount_sats,   # Overall total bet for the round, can increase with splits/doubles
        player_hands=[player_hand_obj],
        dealer_hand=dealer_hand_obj,
        status='active',
        details={
            'deck': deck,
            'current_hand_index': 0,
            'all_player_hands_played': False,
            'dealer_up_card': dealer_initial_cards[0]
        },
        created_at=current_time,
        updated_at=current_time
    )
    db.session.add(new_blackjack_hand)
    db.session.flush() # Flush new_blackjack_hand to get its ID for the transaction.

    # Deduct bet from user balance
    user.balance -= bet_amount_sats
    
    # Create Wager Transaction
    wager_tx = Transaction(
        user_id=user.id,
        amount=-bet_amount_sats, # Negative for wager
        transaction_type='wager',
        details={'hand_id': new_blackjack_hand.id, 'table_id': table.id, 'session_id': game_session.id},
        game_session_id=game_session.id, # Retaining for now
        blackjack_hand_id=new_blackjack_hand.id
    )
    db.session.add(wager_tx)

    # Update GameSession wagered amount
    game_session.amount_wagered += bet_amount_sats
    
    # db.session.commit() is handled by the route

    # --- Prepare Return Value ---
    # Frontend needs player's hand, dealer's UP-CARD, and possible actions
    
    # Check for initial Blackjack for player or dealer
    player_blackjack = player_hand_obj['is_blackjack']
    
    # Only dealer's up-card is visible for dealer's initial total for player
    visible_dealer_total, _ = _calculate_hand_value([dealer_initial_cards[0]])

    # If player has BJ, they auto-stand. `all_player_hands_played` might become true.
    if player_blackjack:
        player_hand_obj['is_standing'] = True # Player stands on their Blackjack
        new_blackjack_hand.details['all_player_hands_played'] = True # Since only one hand initially
        # The game doesn't end immediately; dealer must check their hand.
        # This state will be picked up by handle_blackjack_action if any action is attempted,
        # or if a separate function to proceed game state is called.
        # For now, the responsibility to proceed to dealer turn is after player 'stands' (implicitly here).

    # Determine initial possible actions for the player for the *first hand*
    can_double = (user.balance >= player_hand_obj['bet_sats']) and \
                 len(player_hand_obj['cards']) == 2 and \
                 not player_blackjack # Cannot double on a natural blackjack

    can_split = False
    if len(player_hand_obj['cards']) == 2 and \
       (user.balance >= player_hand_obj['bet_sats']) and \
       not player_blackjack: # Cannot split a natural blackjack
        # Check if cards have same rank (e.g. '8' == '8')
        # Card representation is "SR" (SuitRank, e.g. "HA", "D8")
        if player_hand_obj['cards'][0][1] == player_hand_obj['cards'][1][1]:
             can_split = True
        # Optional: Add table rule for splitting any two 10-value cards
        # elif _get_card_value(player_hand_obj['cards'][0]) == 10 and \
        #      _get_card_value(player_hand_obj['cards'][1]) == 10 and \
        #      table.rules.get('split_any_ten_value_card', False):
        #    can_split = True


    return {
        "id": new_blackjack_hand.id,
        "player_hands": [player_hand_obj], # List of hand objects
        "dealer_hand": { # Only show dealer's up-card initially
            "cards": [dealer_initial_cards[0], "FACE_DOWN"], # "FACE_DOWN" or similar placeholder
            "total": visible_dealer_total, # Total of up-card only
            "is_soft": _get_card_value(dealer_initial_cards[0]) == 11,
        },
        "status": new_blackjack_hand.status,
        "total_bet": new_blackjack_hand.total_bet,
        "can_hit": not player_blackjack, # Cannot hit if blackjack
        "can_stand": True,
        "can_double": can_double and not player_blackjack,
        "can_split": can_split and not player_blackjack,
        "is_player_turn": not player_blackjack, # If player has BJ, turn might be over for them
        "active_hand_index": 0,
        "deck_remaining_estimate": len(deck), # For UI, not for game logic decisions strictly
        "user_balance_sats": user.balance,
        "initial_bet_sats": bet_amount_sats # For reference
    }


def handle_blackjack_action(user, hand_id, action_type, hand_index_requested=0): # Default to 0 for non-split scenarios
    """Handle a blackjack action (hit, stand, double, split)"""
    """
    Handles a player's action (hit, stand, double, split) for a given hand.
    """
    # --- Load State ---
    bj_hand = BlackjackHand.query.filter_by(id=hand_id, user_id=user.id).first()
    if not bj_hand:
        raise ValueError(f"BlackjackHand with ID {hand_id} not found for this user.")
    if bj_hand.status != 'active':
        raise ValueError(f"Hand is not active. Current status: {bj_hand.status}")

    table = BlackjackTable.query.get(bj_hand.table_id) # For table rules, although not heavily used yet
    if not table:
        raise ValueError(f"Table with ID {bj_hand.table_id} not found.") # Should not happen

    game_session = GameSession.query.get(bj_hand.session_id)
    if not game_session or game_session.session_end is not None:
         raise ValueError(f"Active GameSession not found for hand {hand_id}.")


    # --- Retrieve mutable state from details ---
    # Make sure to work with copies if directly modifying lists/dicts from JSON field
    # and then assign them back to trigger SQLAlchemy's change detection.
    current_deck = list(bj_hand.details.get('deck', [])) # Get a mutable copy
    active_hand_idx = bj_hand.details.get('current_hand_index', 0)
    all_hands_played = bj_hand.details.get('all_player_hands_played', False)

    # player_hands_list is a list of dictionaries (our hand objects)
    player_hands_list = [dict(h) for h in bj_hand.player_hands] # Deep copy for modification
    dealer_hand_obj = dict(bj_hand.dealer_hand) # Copy for modification

    if all_hands_played:
        raise ValueError("Player has already played all hands. Dealer's turn or game ended.")

    if hand_index_requested != active_hand_idx:
        raise ValueError(f"Action requested for hand {hand_index_requested}, but current active hand is {active_hand_idx}.")

    current_player_hand = player_hands_list[active_hand_idx]

    if current_player_hand['is_standing'] or current_player_hand['is_busted'] or current_player_hand['is_blackjack']:
        # This specific hand might be done, but current_hand_index might not have advanced.
        # This check is more about preventing action on an already concluded hand.
        raise ValueError(f"Hand {active_hand_idx} is already concluded (stood, busted, or blackjack).")
        
    # --- Player Actions ---
    action_taken_successfully = False
    current_time = datetime.now(timezone.utc)

    if action_type == 'hit':
        new_card = _deal_card(current_deck)
        current_player_hand['cards'].append(new_card)
        total, is_soft = _calculate_hand_value(current_player_hand['cards'])
        current_player_hand['total'] = total
        current_player_hand['is_soft'] = is_soft
        current_player_hand['is_busted'] = total > 21
        
        if total >= 21: # Auto-stand if 21 or busted
            current_player_hand['is_standing'] = True
        action_taken_successfully = True

    elif action_type == 'stand':
        current_player_hand['is_standing'] = True
        action_taken_successfully = True

    elif action_type == 'double':
        # Validation for double:
        if len(current_player_hand['cards']) != 2:
            raise ValueError("Double down is only allowed on the first two cards of a hand.")
        if user.balance < current_player_hand['bet_sats']: # Bet for this hand, not initial_bet of whole game
            raise ValueError(f"Insufficient balance to double. Need {current_player_hand['bet_sats']} more.")

        # Perform double:
        user.balance -= current_player_hand['bet_sats']
        bj_hand.total_bet += current_player_hand['bet_sats']
        game_session.amount_wagered += current_player_hand['bet_sats']
        
        current_player_hand['bet_multiplier'] = 2.0
        current_player_hand['is_doubled'] = True # Mark as doubled

        # Create additional wager transaction
        double_tx = Transaction(
            user_id=user.id,
            amount=-current_player_hand['bet_sats'],
            transaction_type='wager',
            details={
                'reason': 'double_down',
                'hand_id': bj_hand.id,
                'hand_index': active_hand_idx,
                'table_id': table.id,
                'session_id': game_session.id
            },
            game_session_id=game_session.id, # Retaining for now
            blackjack_hand_id=bj_hand.id
        )
        db.session.add(double_tx)

        # Deal one more card
        new_card = _deal_card(current_deck)
        current_player_hand['cards'].append(new_card)
        total, is_soft = _calculate_hand_value(current_player_hand['cards'])
        current_player_hand['total'] = total
        current_player_hand['is_soft'] = is_soft
        current_player_hand['is_busted'] = total > 21
        current_player_hand['is_standing'] = True # Player stands after doubling
        action_taken_successfully = True

    elif action_type == 'split':
        # Validation for split:
        if len(current_player_hand['cards']) != 2:
            raise ValueError("Split is only allowed on the first two cards of a hand.")
        
        card1_rank = current_player_hand['cards'][0][1]
        card2_rank = current_player_hand['cards'][1][1]
        # Standard rule: cards must be of the same rank (e.g. 88, AA, KK). Some allow any 10-value cards.
        # For simplicity, only same rank for now. _get_card_value could be used for 10-value check.
        if card1_rank != card2_rank:
            raise ValueError("Split is only allowed with two cards of the same rank.")
        if user.balance < current_player_hand['bet_sats']:
            raise ValueError(f"Insufficient balance to split. Need {current_player_hand['bet_sats']} for the new hand.")

        # Perform split:
        user.balance -= current_player_hand['bet_sats'] # Bet for the new hand
        bj_hand.total_bet += current_player_hand['bet_sats']
        game_session.amount_wagered += current_player_hand['bet_sats']

        # Create additional wager transaction for the new hand's bet
        split_tx = Transaction(
            user_id=user.id,
            amount=-current_player_hand['bet_sats'],
            transaction_type='wager',
            details={
                'reason': 'split',
                'hand_id': bj_hand.id,
                'new_hand_index': len(player_hands_list),
                'table_id': table.id,
                'session_id': game_session.id
            },
            game_session_id=game_session.id, # Retaining for now
            blackjack_hand_id=bj_hand.id
        )
        db.session.add(split_tx)

        # Original hand keeps first card, new hand gets second card
        original_hand_first_card = current_player_hand['cards'][0]
        new_hand_first_card = current_player_hand['cards'][1]

        # Re-initialize current hand (it was split)
        current_player_hand['cards'] = [original_hand_first_card]
        # Deal one new card to it
        current_player_hand['cards'].append(_deal_card(current_deck))
        total, is_soft = _calculate_hand_value(current_player_hand['cards'])
        current_player_hand['total'] = total
        current_player_hand['is_soft'] = is_soft
        current_player_hand['is_busted'] = total > 21 # Unlikely with 2 cards unless AA gets 2x Ace + picture
        current_player_hand['is_blackjack'] = (total == 21 and len(current_player_hand['cards']) == 2) # Check for BJ on split
        current_player_hand['is_standing'] = current_player_hand['is_blackjack'] # Auto-stand on BJ after split
        # Bet multiplier remains 1.0 for the split hands initially. is_doubled is False.

        # Create the new hand object for the list
        new_player_split_hand = _create_player_hand_obj(
            cards_list=[new_hand_first_card, _deal_card(current_deck)],
            bet_sats=current_player_hand['bet_sats'] # Same bet amount as the hand it split from
        )
        new_player_split_hand['is_blackjack'] = (new_player_split_hand['total'] == 21 and len(new_player_split_hand['cards']) == 2)
        if new_player_split_hand['is_blackjack']: # Auto-stand on BJ after split
            new_player_split_hand['is_standing'] = True

        player_hands_list.insert(active_hand_idx + 1, new_player_split_hand)
        action_taken_successfully = True
        # current_hand_index does not advance yet, player plays the first of the split hands.
    
    else:
        raise ValueError(f"Invalid action type: {action_type}")

    # --- Update State & Check for Next Step ---
    new_action_record = None
    if action_taken_successfully:
        # Record the BlackjackAction
        action_details_for_log = {
            "hand_cards": current_player_hand['cards'],
            "hand_total": current_player_hand['total'],
            "is_busted": current_player_hand['is_busted'],
            "is_standing": current_player_hand['is_standing']
        }
        if action_type in ['hit', 'double']:
            action_details_for_log['card_dealt'] = current_player_hand['cards'][-1] # Last card added

        new_action_record = BlackjackAction(
            blackjack_hand_id=bj_hand.id,
            action_type=action_type,
            hand_index=active_hand_idx, # The hand index on which action was performed
            # card_dealt field can be tricky if multiple cards (split) or no cards (stand)
            # For simplicity, storing details in JSON might be better if card_dealt is specific
            action_details=action_details_for_log
            # Or, if BlackjackAction has specific fields like 'card_dealt_str' and 'resulting_total_int':
            # card_dealt_str = action_details_for_log.get('card_dealt'),
            # resulting_total_int = current_player_hand['total']
        )
        db.session.add(new_action_record)

    # Advance to next hand if current hand is stood, busted, or blackjack (unless it was a split, then play current hand index first)
    if current_player_hand['is_standing'] or current_player_hand['is_busted'] or current_player_hand['is_blackjack']:
        if active_hand_idx < len(player_hands_list) - 1:
            active_hand_idx += 1
        else:
            all_hands_played = True # All player hands have been played

    # --- Update DB ---
    bj_hand.player_hands = player_hands_list # Assign back the modified list
    # dealer_hand_obj might not have changed yet, but assign if it could in future
    # bj_hand.dealer_hand = dealer_hand_obj

    bj_hand.details['deck'] = current_deck
    bj_hand.details['current_hand_index'] = active_hand_idx
    bj_hand.details['all_player_hands_played'] = all_hands_played
    bj_hand.updated_at = current_time

    # --- Dealer's Turn & Outcome Determination ---
    if all_hands_played:
        # Dealer reveals face down card and plays according to rules
        _play_dealer_turn(dealer_hand_obj, current_deck, table.rules) # Modifies dealer_hand_obj
        bj_hand.dealer_hand = dealer_hand_obj # Update dealer hand in DB object

        # Determine winner for each player hand
        total_amount_returned_to_player = 0
        for p_hand in player_hands_list:
            amount_returned_for_hand, result_str = _determine_winner_for_hand(p_hand, dealer_hand_obj, table.rules)
            p_hand['result'] = result_str
            total_amount_returned_to_player += amount_returned_for_hand
        
        # total_bet was the amount deducted from user's balance throughout the hand (initial + doubles/splits)
        # profit_sats is the net change to user's balance from this game's outcome.
        profit_sats = total_amount_returned_to_player - bj_hand.total_bet
        
        bj_hand.win_amount = profit_sats # Store the net profit/loss for the hand summary
        bj_hand.status = 'completed'
        bj_hand.completed_at = current_time

        if total_amount_returned_to_player > 0: # If player gets any money back (win or push)
            user.balance += total_amount_returned_to_player # Add the full amount they get back

            # The 'win' transaction should reflect the actual amount credited back to balance if positive.
            # Or, it could represent net profit. Conventionally, for wins, it's the amount won excluding stake.
            # However, since stake was already taken, returning the full amount won (including stake part of it)
            # in the transaction record makes sense if it's seen as "money in".
            # Let's make the 'win' transaction the actual profit. If it's a push, profit is 0.
            # If only losses, no positive win transaction.

            # If profit_sats > 0, it's a net win.
            # If profit_sats == 0 (and total_amount_returned_to_player > 0), it's a push, money returned.
            # If profit_sats < 0, it's a net loss (already accounted for by bets).

            # Create a 'win' transaction for the net profit, if any.
            # If total_amount_returned_to_player > bj_hand.total_bet (i.e. profit_sats > 0)
            if profit_sats > 0:
                 win_tx = Transaction(
                    user_id=user.id,
                    amount=profit_sats, # Net profit
                    transaction_type='win',
                    details={
                        'hand_id': bj_hand.id,
                        'table_id': table.id,
                        'session_id': game_session.id,
                        'player_final_hands': player_hands_list, # Store final state for audit
                        'dealer_final_hand': dealer_hand_obj
                    },
                    game_session_id=game_session.id, # Retaining for now
                    blackjack_hand_id=bj_hand.id
                )
                 db.session.add(win_tx)
                 game_session.amount_won += profit_sats # Session tracks net profit from wins

            # If it was a PUSH overall (profit_sats == 0 but money was returned),
            # some systems might log a "push" transaction or similar.
            # For now, only explicit profit is logged as a "win" transaction.
            # The user.balance is correctly updated with the total amount returned.
        
        game_session.session_end = current_time # End session as game is complete
        game_session.updated_at = current_time # Update session timestamp

    # db.session.commit() # Handled by route
    bj_hand.updated_at = current_time # Ensure parent hand timestamp is also updated.

    # --- Prepare Return Value ---
    # Similar to join, but reflects current state
    # Need to determine can_double, can_split for the *new* active_hand_idx if game is ongoing
    
    # Dealer's up-card for UI display if game is ongoing
    dealer_up_card_display = bj_hand.details.get('dealer_up_card', dealer_hand_obj['cards'][0] if dealer_hand_obj['cards'] else "UNKNOWN")
    visible_dealer_total_display, _ = _calculate_hand_value([dealer_up_card_display]) if dealer_up_card_display != "UNKNOWN" else (0, False)

    response_dealer_hand = {
        "cards": [dealer_up_card_display, "FACE_DOWN"] if not all_hands_played else dealer_hand_obj['cards'],
        "total": visible_dealer_total_display if not all_hands_played else dealer_hand_obj['total'],
        "is_soft": (_get_card_value(dealer_up_card_display) == 11) if not all_hands_played else dealer_hand_obj['is_soft'],
    }
    if all_hands_played: # If dealer played, show full dealer hand info from dealer_hand_obj
        response_dealer_hand.update(dealer_hand_obj)


    # UI flags for the current active hand
    current_active_p_hand = player_hands_list[active_hand_idx] if not all_hands_played else player_hands_list[0] # fallback for completed game display
    
    can_hit_flag = not (all_hands_played or current_active_p_hand['is_standing'] or current_active_p_hand['is_busted'] or current_active_p_hand['is_blackjack'])
    can_stand_flag = not (all_hands_played or current_active_p_hand['is_standing'] or current_active_p_hand['is_busted'] or current_active_p_hand['is_blackjack'])
    
    can_double_flag = False
    if not all_hands_played and len(current_active_p_hand['cards']) == 2 and \
       user.balance >= current_active_p_hand['bet_sats'] and \
       not (current_active_p_hand['is_standing'] or current_active_p_hand['is_busted'] or current_active_p_hand['is_blackjack']):
        can_double_flag = True

    can_split_flag = False
    if not all_hands_played and len(current_active_p_hand['cards']) == 2 and \
       user.balance >= current_active_p_hand['bet_sats'] and \
       current_active_p_hand['cards'][0][1] == current_active_p_hand['cards'][1][1] and \
       not (current_active_p_hand['is_standing'] or current_active_p_hand['is_busted'] or current_active_p_hand['is_blackjack']):
        # Check if already 4 hands (common max split rule, not specified but good practice)
        if len(player_hands_list) < table.rules.get("max_split_hands", 4): # Default max 4 hands
             can_split_flag = True


    return {
        "id": bj_hand.id,
        "player_hands": player_hands_list,
        "dealer_hand": response_dealer_hand,
        "status": bj_hand.status,
        "total_bet": bj_hand.total_bet,
        "win_amount": bj_hand.win_amount if bj_hand.status == 'completed' else 0,
        "can_hit": can_hit_flag,
        "can_stand": can_stand_flag,
        "can_double": can_double_flag,
        "can_split": can_split_flag,
        "is_player_turn": not all_hands_played,
        "active_hand_index": active_hand_idx if not all_hands_played else -1, # -1 if game over
        "deck_remaining_estimate": len(current_deck),
        "user_balance_sats": user.balance,
         # Include results if completed
        "results_summary": [h.get('result') for h in player_hands_list] if all_hands_played else []
    }


# Helper for dealer's turn
def _play_dealer_turn(dealer_hand_obj, deck_list, table_rules):
    """
    Dealer plays their hand according to table rules.
    Modifies dealer_hand_obj and deck_list in place.
    # `table_rules` is a dict, e.g., {'dealer_stands_on': 'soft17' or 'hard17', 'blackjack_payout': 1.5}
    """
    # Dealer reveals second card implicitly by calculating full hand value
    # Actual card reveal for UI is just showing all cards.

    # Ensure table_rules is a dictionary
    if not isinstance(table_rules, dict):
        table_rules = {} # Default to empty dict if rules are not properly set

    dealer_stands_on_soft17 = table_rules.get('dealer_stands_on', 'soft17') == 'soft17'

    while True:
        # Recalculate dealer hand properties at the start of each loop iteration
        # as cards might have been added.
        current_total, current_is_soft = _calculate_hand_value(dealer_hand_obj['cards'])
        dealer_hand_obj['total'] = current_total
        dealer_hand_obj['is_soft'] = current_is_soft
        dealer_hand_obj['is_busted'] = current_total > 21
        # Blackjack is only for the initial two cards.
        # dealer_hand_obj['is_blackjack'] should have been set at hand creation if dealer had natural.
        # If not set initially, it won't become blackjack by hitting.
        # is_blackjack = (len(dealer_hand_obj['cards']) == 2 and current_total == 21)
        # dealer_hand_obj['is_blackjack'] = is_blackjack # This should be set once.

        if dealer_hand_obj['is_busted']:
            break # Dealer busted, stop hitting.

        if current_total < 17:
            dealer_hand_obj['cards'].append(_deal_card(deck_list))
        elif current_total == 17:
            if current_is_soft and not dealer_stands_on_soft17: # Dealer hits on soft 17
                dealer_hand_obj['cards'].append(_deal_card(deck_list))
            else: # Stands on hard 17, or soft 17 if rule is to stand on soft 17
                break
        else: # current_total > 17
            break

    # Final update of dealer hand values after loop (if cards were added)
    final_total, final_is_soft = _calculate_hand_value(dealer_hand_obj['cards'])
    dealer_hand_obj['total'] = final_total
    dealer_hand_obj['is_soft'] = final_is_soft
    dealer_hand_obj['is_busted'] = final_total > 21
    # dealer_hand_obj['is_blackjack'] remains as it was (only for initial 2 cards).


# Helper for determining winner of a single player hand vs dealer
def _determine_winner_for_hand(player_hand_obj, dealer_hand_obj, table_rules):
    """
    Determines the amount player wins/loses for a single hand.
    Returns (amount_returned_to_player, result_string).
    `amount_returned_to_player` is the total sum player gets back for this hand (includes their stake if not lost).
    Example: Bet 100. Win -> returns 200. Push -> returns 100. Lose -> returns 0. BJ -> returns 250 (if 3:2).
    `table_rules` is a dict from `BlackjackTable.rules`.
    """
    player_total = player_hand_obj['total']
    player_is_blackjack = player_hand_obj['is_blackjack']
    player_is_busted = player_hand_obj['is_busted']

    # Effective wager for this hand (base bet * multiplier if doubled)
    effective_wager = player_hand_obj['bet_sats'] * player_hand_obj['bet_multiplier']

    dealer_total = dealer_hand_obj['total']
    dealer_is_blackjack = dealer_hand_obj['is_blackjack']
    dealer_is_busted = dealer_hand_obj['is_busted']

    # Ensure table_rules is a dictionary
    if not isinstance(table_rules, dict):
        table_rules = {}
    blackjack_payout_ratio = table_rules.get('blackjack_payout', 1.5) # e.g., 1.5 for a 3:2 payout

    if player_is_busted:
        return 0, 'lose' # Player loses their effective wager

    # Player Blackjack scenarios
    if player_is_blackjack:
        if dealer_is_blackjack:
            return effective_wager, 'push' # Both have BJ, push
        else:
            # Player BJ wins. Payout is wager + (wager * ratio)
            # IMPORTANT: BJ payout is typically on the ORIGINAL bet, not a doubled bet.
            # However, a hand that was doubled cannot be a natural BJ.
            # So, effective_wager here would be just player_hand_obj['bet_sats'] as bet_multiplier would be 1.0.
            win_amount = player_hand_obj['bet_sats'] + int(player_hand_obj['bet_sats'] * blackjack_payout_ratio)
            return win_amount, 'blackjack_win'

    # If dealer has Blackjack and player does not (player_is_blackjack already handled)
    if dealer_is_blackjack:
        return 0, 'lose'

    # Other scenarios (neither has natural BJ and player is not busted)
    if dealer_is_busted:
        return effective_wager * 2, 'win' # Player wins 1:1 (original bet + profit equal to bet)

    if player_total > dealer_total:
        return effective_wager * 2, 'win'

    if player_total < dealer_total:
        return 0, 'lose'

    return effective_wager, 'push' # Totals are equal, push


# --- End of refactored Blackjack logic (old functions removed as of previous step) ---