from datetime import datetime, timezone
import random
import json
from models import db, User, GameSession, BlackjackHand, BlackjackAction, BlackjackTable, Transaction

def generate_deck(deck_count=1):
    """Generate a deck of cards (multiple decks if deck_count > 1)"""
    suits = ['hearts', 'diamonds', 'clubs', 'spades']
    values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    
    deck = []
    for _ in range(deck_count):
        for suit in suits:
            for value in values:
                card = {
                    'suit': suit,
                    'value': value,
                    'numeric_value': get_card_value(value)
                }
                deck.append(card)
    
    # Shuffle the deck
    random.shuffle(deck)
    return deck

def get_card_value(value):
    """Get the numeric value of a card"""
    if value in ['J', 'Q', 'K']:
        return 10
    elif value == 'A':
        return 11  # Ace is 11 initially, can be 1 if needed
    else:
        return int(value)

def calculate_hand_value(cards):
    """Calculate the value of a hand, accounting for aces"""
    total = 0
    aces = 0
    
    for card in cards:
        if card['value'] == 'A':
            aces += 1
            total += 11
        else:
            total += get_card_value(card['value'])
    
    # Adjust for aces if total is over 21
    while total > 21 and aces > 0:
        total -= 10  # Convert an ace from 11 to 1
        aces -= 1
    
    return total

def is_blackjack(cards):
    """Check if a hand is a blackjack (21 with exactly 2 cards)"""
    return len(cards) == 2 and calculate_hand_value(cards) == 21

def is_busted(cards):
    """Check if a hand is busted (over 21)"""
    return calculate_hand_value(cards) > 21

def deal_card(deck):
    """Deal a card from the deck"""
    if not deck:
        # If deck is empty, generate a new shuffled deck
        deck = generate_deck()
    
    return deck.pop()

def create_hand_data(cards):
    """Create a hand data object for a set of cards"""
    return {
        'cards': cards,
        'total': calculate_hand_value(cards),
        'is_busted': is_busted(cards),
        'is_blackjack': is_blackjack(cards),
        'is_doubled': False,
        'is_split': False
    }

def handle_join_blackjack(user, table, bet_amount):
    """Handle a user joining a blackjack game"""
    # Validate bet amount
    if bet_amount < table.min_bet:
        raise ValueError(f"Bet amount {bet_amount} is below the minimum bet of {table.min_bet}")
    
    if bet_amount > table.max_bet:
        raise ValueError(f"Bet amount {bet_amount} is above the maximum bet of {table.max_bet}")
    
    if bet_amount > user.balance:
        raise ValueError(f"Insufficient balance. You have {user.balance} satoshis, but bet is {bet_amount} satoshis")
    
    # Close any existing active sessions for this user
    now = datetime.now(timezone.utc)
    active_sessions = GameSession.query.filter_by(user_id=user.id, session_end=None).all()
    for session in active_sessions:
        session.session_end = now
    
    # Create a new game session
    new_session = GameSession(
        user_id=user.id,
        slot_id=1,  # Use a default slot_id (1) to avoid not-null constraint
        table_id=table.id,
        game_type='blackjack',
        session_start=now,
        amount_wagered=0,
        amount_won=0
    )
    db.session.add(new_session)
    db.session.flush()  # Get the session ID without committing
    
    # Generate a deck based on table rules
    deck = generate_deck(table.deck_count)
    
    # Deal initial cards
    player_cards = [deal_card(deck), deal_card(deck)]
    dealer_cards = [deal_card(deck), deal_card(deck)]
    
    # Set dealer's second card as face down
    dealer_cards[1]['is_face_down'] = True
    
    # Create hand data objects
    player_hand = create_hand_data(player_cards)
    dealer_hand = create_hand_data([dealer_cards[0]])  # Only count the face-up card for now
    
    # Create a new blackjack hand record
    new_hand = BlackjackHand(
        user_id=user.id,
        table_id=table.id,
        session_id=new_session.id,
        initial_bet=bet_amount,
        total_bet=bet_amount,
        player_cards=player_cards,
        dealer_cards=dealer_cards,
        player_hands=[player_hand],
        dealer_hand=dealer_hand,
        status='active'
    )
    db.session.add(new_hand)
    
    # Deduct the bet from the user's balance
    user.balance -= bet_amount
    
    # Record the wager as a transaction
    transaction = Transaction(
        user_id=user.id,
        amount=-bet_amount,
        transaction_type='wager',
        status='completed',
        details={
            'game_type': 'blackjack',
            'table_id': table.id,
            'hand_id': new_hand.id
        }
    )
    db.session.add(transaction)
    
    # Update session stats
    new_session.amount_wagered += bet_amount
    
    # Commit the changes
    db.session.commit()
    
    # Return the hand data
    return {
        'hand_id': new_hand.id,
        'player_cards': player_cards,
        'dealer_cards': [dealer_cards[0], {'is_face_down': True}],  # Only show the face-up card
        'player_hands': [player_hand],
        'dealer_hand': dealer_hand,
        'initial_bet': bet_amount,
        'total_bet': bet_amount,
        'deck_remaining': len(deck)
    }

def handle_blackjack_action(user, hand_id, action_type, hand_index=0):
    """Handle a blackjack action (hit, stand, double, split)"""
    # Get the hand
    hand = BlackjackHand.query.filter_by(id=hand_id, user_id=user.id, status='active').first()
    if not hand:
        raise ValueError(f"No active hand found with ID {hand_id}")
    
    # Get the table
    table = BlackjackTable.query.get(hand.table_id)
    if not table:
        raise ValueError(f"Table with ID {hand.table_id} not found")
    
    # Get the session
    session = GameSession.query.get(hand.session_id)
    if not session or session.session_end:
        raise ValueError(f"No active session found for hand {hand_id}")
    
    # Load the player hands and dealer hand from JSON
    player_hands = hand.player_hands
    dealer_hand = hand.dealer_hand
    
    # Validate hand_index
    if hand_index < 0 or hand_index >= len(player_hands):
        raise ValueError(f"Invalid hand index {hand_index}")
    
    # Get the current player hand
    current_hand = player_hands[hand_index]
    
    # Check if the hand is already completed
    if current_hand.get('is_busted') or current_hand.get('is_blackjack'):
        raise ValueError(f"Hand {hand_index} is already completed")
    
    # Generate a deck from the remaining cards
    deck = generate_deck(table.deck_count)
    
    # Process the action
    result = None
    card_dealt = None
    
    if action_type == 'hit':
        # Deal a card to the player
        card_dealt = deal_card(deck)
        current_hand['cards'].append(card_dealt)
        current_hand['total'] = calculate_hand_value(current_hand['cards'])
        current_hand['is_busted'] = is_busted(current_hand['cards'])
        
        # Record the action
        action = BlackjackAction(
            hand_id=hand.id,
            action_type='hit',
            hand_index=hand_index,
            card_dealt=card_dealt,
            hand_total=current_hand['total']
        )
        db.session.add(action)
        
        # Check if the player busted
        if current_hand['is_busted']:
            # Move to the next hand or end the game
            result = handle_next_hand(hand, player_hands, dealer_hand, hand_index, table, session, user)
    
    elif action_type == 'stand':
        # Record the action
        action = BlackjackAction(
            hand_id=hand.id,
            action_type='stand',
            hand_index=hand_index,
            hand_total=current_hand['total']
        )
        db.session.add(action)
        
        # Move to the next hand or dealer's turn
        result = handle_next_hand(hand, player_hands, dealer_hand, hand_index, table, session, user)
    
    elif action_type == 'double':
        # Check if doubling is allowed (only on first two cards)
        if len(current_hand['cards']) != 2:
            raise ValueError("Doubling is only allowed on the first two cards")
        
        # Check if the player has enough balance
        if user.balance < hand.initial_bet:
            raise ValueError(f"Insufficient balance to double. You have {user.balance} satoshis, but need {hand.initial_bet} satoshis")
        
        # Double the bet
        additional_bet = hand.initial_bet
        user.balance -= additional_bet
        hand.total_bet += additional_bet
        current_hand['is_doubled'] = True
        
        # Record the wager as a transaction
        transaction = Transaction(
            user_id=user.id,
            amount=-additional_bet,
            transaction_type='wager',
            status='completed',
            details={
                'game_type': 'blackjack',
                'table_id': table.id,
                'hand_id': hand.id,
                'action': 'double'
            }
        )
        db.session.add(transaction)
        
        # Update session stats
        session.amount_wagered += additional_bet
        
        # Deal one card to the player
        card_dealt = deal_card(deck)
        current_hand['cards'].append(card_dealt)
        current_hand['total'] = calculate_hand_value(current_hand['cards'])
        current_hand['is_busted'] = is_busted(current_hand['cards'])
        
        # Record the action
        action = BlackjackAction(
            hand_id=hand.id,
            action_type='double',
            hand_index=hand_index,
            card_dealt=card_dealt,
            hand_total=current_hand['total']
        )
        db.session.add(action)
        
        # Move to the next hand or dealer's turn
        result = handle_next_hand(hand, player_hands, dealer_hand, hand_index, table, session, user)
    
    elif action_type == 'split':
        # Check if splitting is allowed
        if len(current_hand['cards']) != 2:
            raise ValueError("Splitting is only allowed with two cards")
        
        if current_hand['cards'][0]['value'] != current_hand['cards'][1]['value']:
            raise ValueError("Splitting is only allowed with two cards of the same value")
        
        # Check if the player has enough balance
        if user.balance < hand.initial_bet:
            raise ValueError(f"Insufficient balance to split. You have {user.balance} satoshis, but need {hand.initial_bet} satoshis")
        
        # Add the additional bet
        additional_bet = hand.initial_bet
        user.balance -= additional_bet
        hand.total_bet += additional_bet
        
        # Record the wager as a transaction
        transaction = Transaction(
            user_id=user.id,
            amount=-additional_bet,
            transaction_type='wager',
            status='completed',
            details={
                'game_type': 'blackjack',
                'table_id': table.id,
                'hand_id': hand.id,
                'action': 'split'
            }
        )
        db.session.add(transaction)
        
        # Update session stats
        session.amount_wagered += additional_bet
        
        # Create a new hand with the second card
        second_card = current_hand['cards'].pop()
        new_hand_data = create_hand_data([second_card])
        new_hand_data['is_split'] = True
        player_hands.append(new_hand_data)
        
        # Update the current hand
        current_hand['is_split'] = True
        current_hand['total'] = calculate_hand_value(current_hand['cards'])
        
        # Deal a card to each hand
        card_dealt = deal_card(deck)
        current_hand['cards'].append(card_dealt)
        current_hand['total'] = calculate_hand_value(current_hand['cards'])
        
        second_card_dealt = deal_card(deck)
        player_hands[-1]['cards'].append(second_card_dealt)
        player_hands[-1]['total'] = calculate_hand_value(player_hands[-1]['cards'])
        
        # Record the action
        action = BlackjackAction(
            hand_id=hand.id,
            action_type='split',
            hand_index=hand_index,
            card_dealt=card_dealt,
            hand_total=current_hand['total']
        )
        db.session.add(action)
    
    else:
        raise ValueError(f"Invalid action type: {action_type}")
    
    # Update the hand record
    hand.player_hands = player_hands
    hand.dealer_hand = dealer_hand
    
    # If we have a result, update the hand status and result
    if result:
        hand.status = 'completed'
        hand.result = result['result']
        hand.win_amount = result['win_amount']
        hand.completed_at = datetime.now(timezone.utc)
    
    # Commit the changes
    db.session.commit()
    
    # Return the updated hand data
    response = {
        'hand_id': hand.id,
        'player_cards': hand.player_cards,
        'dealer_cards': hand.dealer_cards,
        'player_hands': player_hands,
        'dealer_hand': dealer_hand,
        'initial_bet': hand.initial_bet,
        'total_bet': hand.total_bet,
        'status': hand.status
    }
    
    if result:
        response.update({
            'result': result['result'],
            'win_amount': result['win_amount'],
            'message': result['message']
        })
    
    if card_dealt:
        response['card_dealt'] = card_dealt
    
    return response

def handle_next_hand(hand, player_hands, dealer_hand, current_index, table, session, user):
    """Handle moving to the next hand or dealer's turn"""
    # Check if there are more hands to play
    if current_index + 1 < len(player_hands):
        # Move to the next hand
        return None
    
    # All player hands are done, now it's dealer's turn
    return handle_dealer_turn(hand, player_hands, dealer_hand, table, session, user)

def handle_dealer_turn(hand, player_hands, dealer_hand, table, session, user):
    """Handle the dealer's turn"""
    # Check if all player hands are busted
    all_busted = all(h.get('is_busted', False) for h in player_hands)
    
    # Reveal the dealer's face-down card
    dealer_cards = hand.dealer_cards
    if len(dealer_cards) > 1 and dealer_cards[1].get('is_face_down', False):
        dealer_cards[1]['is_face_down'] = False
    
    # Update dealer hand data with all cards
    dealer_hand['cards'] = dealer_cards
    dealer_hand['total'] = calculate_hand_value(dealer_cards)
    dealer_hand['is_blackjack'] = is_blackjack(dealer_cards)
    
    # If all player hands are busted, dealer doesn't need to draw
    if all_busted:
        return determine_outcome(hand, player_hands, dealer_hand, table, session, user)
    
    # Generate a deck
    deck = generate_deck(table.deck_count)
    
    # Dealer draws cards until reaching 17 or higher
    # Ensure rules is a dictionary
    rules = table.rules if isinstance(table.rules, dict) else {}
    dealer_stands_on_soft17 = rules.get('dealer_stands_on', 'soft17') == 'soft17'
    
    while dealer_hand['total'] < 17 or (dealer_hand['total'] == 17 and not dealer_stands_on_soft17 and has_soft_ace(dealer_cards)):
        card = deal_card(deck)
        dealer_cards.append(card)
        dealer_hand['total'] = calculate_hand_value(dealer_cards)
    
    dealer_hand['is_busted'] = is_busted(dealer_cards)
    
    # Update the hand record
    hand.dealer_cards = dealer_cards
    hand.dealer_hand = dealer_hand
    
    # Determine the outcome
    return determine_outcome(hand, player_hands, dealer_hand, table, session, user)

def has_soft_ace(cards):
    """Check if a hand has a soft ace (an ace counted as 11)"""
    total = 0
    aces = 0
    
    for card in cards:
        if card['value'] == 'A':
            aces += 1
        total += get_card_value(card['value'])
    
    # If total is over 21 and we have aces, they're being counted as 1
    return aces > 0 and total <= 21 and total - 10 < 17

def determine_outcome(hand, player_hands, dealer_hand, table, session, user):
    """Determine the outcome of the hand"""
    dealer_total = dealer_hand['total']
    dealer_blackjack = dealer_hand['is_blackjack']
    dealer_busted = dealer_hand['is_busted']
    
    total_win_amount = 0
    overall_result = None
    
    # Check each player hand
    for i, player_hand in enumerate(player_hands):
        player_total = player_hand['total']
        player_blackjack = player_hand['is_blackjack']
        player_busted = player_hand['is_busted']
        is_doubled = player_hand.get('is_doubled', False)
        
        # Calculate the bet for this hand
        hand_bet = hand.initial_bet
        if is_doubled:
            hand_bet *= 2
        
        # Determine the result for this hand
        if player_busted:
            result = 'lose'
            win_amount = 0
        elif player_blackjack and not dealer_blackjack:
            result = 'blackjack'
            # Ensure rules is a dictionary
            rules = table.rules if isinstance(table.rules, dict) else {}
            blackjack_payout = rules.get('blackjack_payout', 1.5)
            # Debug log the payout calculation
            print(f"Blackjack payout: {blackjack_payout}, Bet: {hand_bet}, Win amount: {int(hand_bet * (1 + blackjack_payout))}")
            win_amount = int(hand_bet * (1 + blackjack_payout))
        elif dealer_blackjack and not player_blackjack:
            result = 'lose'
            win_amount = 0
        elif player_blackjack and dealer_blackjack:
            result = 'push'
            win_amount = hand_bet
        elif dealer_busted:
            result = 'win'
            win_amount = hand_bet * 2
        elif player_total > dealer_total:
            result = 'win'
            win_amount = hand_bet * 2
        elif player_total < dealer_total:
            result = 'lose'
            win_amount = 0
        else:
            result = 'push'
            win_amount = hand_bet
        
        # Store the result in the player hand
        player_hand['result'] = result
        player_hand['win_amount'] = win_amount
        
        # Add to the total win amount
        total_win_amount += win_amount
        
        # Set the overall result based on the first hand
        if i == 0:
            overall_result = result
    
    # Update the user's balance with the winnings
    user.balance += total_win_amount
    
    # Record the win as a transaction if there was a win
    if total_win_amount > 0:
        transaction = Transaction(
            user_id=user.id,
            amount=total_win_amount,
            transaction_type='win',
            status='completed',
            details={
                'game_type': 'blackjack',
                'table_id': table.id,
                'hand_id': hand.id,
                'result': overall_result
            }
        )
        db.session.add(transaction)
        
        # Update session stats
        session.amount_won += total_win_amount
    
    # Generate a message based on the result
    message = ''
    if overall_result == 'blackjack':
        message = 'Blackjack! You win!'
    elif overall_result == 'win':
        message = 'You win!'
    elif overall_result == 'lose':
        message = 'Dealer wins.'
    elif overall_result == 'push':
        message = 'Push. Your bet is returned.'
    
    return {
        'result': overall_result,
        'win_amount': total_win_amount,
        'message': message
    }