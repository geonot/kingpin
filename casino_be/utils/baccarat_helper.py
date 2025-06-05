import secrets
from decimal import Decimal

# Card Constants
SUITS = ['H', 'D', 'C', 'S']  # Hearts, Diamonds, Clubs, Spades
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A'] # Ten, Jack, Queen, King, Ace

# --- Deck Functions ---
def _create_deck(num_decks=6):
    """Creates a list of cards for the specified number of decks."""
    deck = []
    for _ in range(num_decks):
        for suit in SUITS:
            for rank in RANKS:
                deck.append(f"{suit}{rank}")
    return deck

def _shuffle_deck(deck):
    """Shuffles the deck in place using secrets.SystemRandom()."""
    rng = secrets.SystemRandom()
    rng.shuffle(deck)

def _deal_card(deck_list):
    """Removes and returns the top card from the deck."""
    if not deck_list:
        raise ValueError("Deck is empty. Cannot deal card.")
    return deck_list.pop(0)

# --- Card Value Calculation ---
def _get_card_baccarat_value(card_str):
    """
    Calculates the Baccarat value of a single card.
    'A': 1
    'K', 'Q', 'J', 'T': 0
    '2'-'9': Their integer value.
    """
    rank = card_str[1:]
    if rank == 'A':
        return 1
    elif rank in ['K', 'Q', 'J', 'T']:
        return 0
    elif rank.isdigit():
        value = int(rank)
        if 2 <= value <= 9:
            return value
    raise ValueError(f"Invalid card rank: {rank} in card {card_str}")

def _calculate_baccarat_hand_value(cards_list):
    """
    Calculates the Baccarat value of a hand (sum of card values modulo 10).
    Returns an integer between 0 and 9.
    """
    total_value = 0
    for card in cards_list:
        total_value += _get_card_baccarat_value(card)
    return total_value % 10

# --- Payout Calculation Helper ---
def _calculate_payouts(outcome, player_bet, banker_bet, tie_bet, commission_rate=Decimal("0.05"), tie_payout_rate=8):
    """
    Calculates the winnings for each bet type and any commission.
    Returns: win_amount_player, win_amount_banker, win_amount_tie, commission_amount
    """
    win_player = Decimal(0)
    win_banker = Decimal(0)
    win_tie = Decimal(0)
    commission = Decimal(0)

    if outcome == "player_win":
        win_player = player_bet * Decimal(1) # Player bet pays 1:1
    elif outcome == "banker_win":
        win_banker = banker_bet * (Decimal(1) - commission_rate) # Banker bet pays 1:1 minus commission
        commission = banker_bet * commission_rate
    elif outcome == "tie":
        win_tie = tie_bet * Decimal(tie_payout_rate) # Tie bet pays 8:1 (or as specified)
        # In case of a Tie, Player and Banker bets are typically pushed (returned)
        # So, we effectively give them back their bet by setting their win to their bet amount if they bet on P/B
        # However, the prompt implies calculating net profit later based on total_winnings - total_bets.
        # For simplicity in `play_baccarat_hand` return structure, we'll consider push as 0 net win for P/B bets on a Tie.
        # If bets are returned, `total_winnings` should include these returned bets.
        # Let's assume for now that `win_player` and `win_banker` are 0 if outcome is "tie" unless they also bet on Tie.
        # The problem asks for `total_winnings = payout_player + payout_banker + payout_tie`.
        # If Player/Banker bets are returned on a Tie, they are part of total_winnings.
        # For now, let's only pay the Tie bet on a Tie outcome.
        # Clarification might be needed on how P/B bets are handled in total_winnings on a Tie.
        # Standard casino rules: Player/Banker bets push on a Tie.
        # So if Tie wins, Player gets player_bet back, Banker gets banker_bet back.
        # This means their "winnings" for that specific bet type are 0, but the bet amount is not lost.
        # The current structure returns `win_amount_player`, `win_amount_banker`, `win_amount_tie`.
        # If P/B bets are pushed on a tie, then `win_amount_player` should be `player_bet` and `win_amount_banker` should be `banker_bet`.
        # However, the prompt's `net_profit` calculation seems to imply these are just the *profit* parts.
        # Let's stick to the prompt "Player bet pays 1:1", "Banker bet pays 1:1 minus commission", "Tie bet pays typically 8:1".
        # This implies these are the *profits* on the winning condition.
        # If Tie occurs, only Tie bet wins. Player/Banker bets are lost unless specified as push.
        # Most common rule: Player/Banker bets are a PUSH on a Tie.
        # Let's adjust to reflect PUSH for Player/Banker bets on a Tie.
        # So, if outcome is "tie", player_bet and banker_bet are returned.
        # The `win_amount` for player/banker in this case is just their original bet (net zero gain/loss from that part of the wager).
        # The `payout_player`, `payout_banker` in the main function should then be player_bet and banker_bet respectively if a tie.
        # Let's refine: `_calculate_payouts` will return the *profit* for each part, and the original bet if it's a push.
        # player_profit, banker_profit, tie_profit, commission_paid
        pass # Re-evaluating this part after main function structure

    # Revised approach for _calculate_payouts: return what is *paid out* for each bet type, including original bet if it wins or pushes.
    payout_player = Decimal(0)
    payout_banker = Decimal(0)
    payout_tie = Decimal(0)
    commission_amount = Decimal(0)

    total_bet_amount = player_bet + banker_bet + tie_bet

    if outcome == "player_win":
        payout_player = player_bet * Decimal(2) # Original bet + 1:1 win
    elif outcome == "banker_win":
        payout_banker = banker_bet + (banker_bet * (Decimal(1) - commission_rate)) # Original bet + win (after commission)
        commission_amount = banker_bet * commission_rate
    elif outcome == "tie":
        payout_tie = tie_bet * (Decimal(tie_payout_rate) + Decimal(1)) # Original bet + 8:1 win
        payout_player = player_bet # Player bet pushes
        payout_banker = banker_bet # Banker bet pushes

    return payout_player, payout_banker, payout_tie, commission_amount


# --- Main Game Flow Function ---
def play_baccarat_hand(player_bet_amount, banker_bet_amount, tie_bet_amount, num_decks=6, commission_rate=Decimal("0.05"), tie_payout_rate=8):
    """
    Simulates a single hand of Baccarat.
    """
    deck = _create_deck(num_decks)
    _shuffle_deck(deck)

    player_cards = []
    banker_cards = []
    player_third_card = None # Store the value of player's third card if drawn

    # Initial Deal (Player, Banker, Player, Banker)
    try:
        player_cards.append(_deal_card(deck))
        banker_cards.append(_deal_card(deck))
        player_cards.append(_deal_card(deck))
        banker_cards.append(_deal_card(deck))
    except ValueError:
        # Handle empty deck during initial deal - should not happen with standard num_decks
        return {"error": "Deck empty during initial deal. Critical error."}

    player_score = _calculate_baccarat_hand_value(player_cards)
    banker_score = _calculate_baccarat_hand_value(banker_cards)

    outcome = None

    # Natural Win Check
    if player_score >= 8 or banker_score >= 8:
        if player_score == banker_score:
            outcome = "tie"
        elif player_score > banker_score:
            outcome = "player_win"
        else:
            outcome = "banker_win"
    else:
        # Player's Third Card Rule
        player_drew_third = False
        if player_score <= 5:
            try:
                card = _deal_card(deck)
                player_cards.append(card)
                player_third_card_value = _get_card_baccarat_value(card) # Value needed for Banker's rule
                player_score = _calculate_baccarat_hand_value(player_cards)
                player_drew_third = True
            except ValueError:
                # If deck runs out here, hand might end prematurely or be invalid.
                # For simulation, assume it's unlikely with 6 decks for one hand.
                # If it does, the current scores would stand.
                pass


        # Banker's Third Card Rule
        banker_drew_third = False
        if not player_drew_third: # Player stood pat (2 cards)
            if banker_score <= 5:
                try:
                    banker_cards.append(_deal_card(deck))
                    banker_score = _calculate_baccarat_hand_value(banker_cards)
                    banker_drew_third = True
                except ValueError:
                    pass # Deck ran out
        else: # Player drew a third card
            if banker_score <= 2:
                try:
                    banker_cards.append(_deal_card(deck))
                    banker_score = _calculate_baccarat_hand_value(banker_cards)
                    banker_drew_third = True
                except ValueError:
                    pass
            elif banker_score == 3:
                if player_third_card_value != 8:
                    try:
                        banker_cards.append(_deal_card(deck))
                        banker_score = _calculate_baccarat_hand_value(banker_cards)
                        banker_drew_third = True
                    except ValueError:
                        pass
            elif banker_score == 4:
                if player_third_card_value in [2, 3, 4, 5, 6, 7]:
                    try:
                        banker_cards.append(_deal_card(deck))
                        banker_score = _calculate_baccarat_hand_value(banker_cards)
                        banker_drew_third = True
                    except ValueError:
                        pass
            elif banker_score == 5:
                if player_third_card_value in [4, 5, 6, 7]:
                    try:
                        banker_cards.append(_deal_card(deck))
                        banker_score = _calculate_baccarat_hand_value(banker_cards)
                        banker_drew_third = True
                    except ValueError:
                        pass
            elif banker_score == 6:
                if player_third_card_value in [6, 7]:
                    try:
                        banker_cards.append(_deal_card(deck))
                        banker_score = _calculate_baccarat_hand_value(banker_cards)
                        banker_drew_third = True
                    except ValueError:
                        pass
            # Banker score 7: Banker stands (already handled as no draw if condition not met)

        # Determine Final Winner (if not determined by natural)
        if player_score == banker_score:
            outcome = "tie"
        elif player_score > banker_score:
            outcome = "player_win"
        else:
            outcome = "banker_win"

    # Calculate Payouts
    # Bets are Decimal, convert if they are not
    dec_player_bet = Decimal(str(player_bet_amount))
    dec_banker_bet = Decimal(str(banker_bet_amount))
    dec_tie_bet = Decimal(str(tie_bet_amount))

    payout_player, payout_banker, payout_tie, commission_paid_val = _calculate_payouts(
        outcome, dec_player_bet, dec_banker_bet, dec_tie_bet,
        commission_rate=Decimal(str(commission_rate)),
        tie_payout_rate=int(tie_payout_rate)
    )

    total_winnings = payout_player + payout_banker + payout_tie
    total_bet = dec_player_bet + dec_banker_bet + dec_tie_bet
    net_profit = total_winnings - total_bet

    return {
        "player_cards": player_cards,
        "banker_cards": banker_cards,
        "player_score": player_score,
        "banker_score": banker_score,
        "player_third_card_value_if_drawn": player_third_card_value if player_drew_third else None, # For debugging/logging
        "outcome": outcome,
        "total_winnings": total_winnings, # This is the total amount returned to the player (includes original winning bets)
        "net_profit": net_profit, # This is (total_winnings - total_amount_bet)
        "commission_paid": commission_paid_val,
        "details": {
            "player_bet": dec_player_bet,
            "banker_bet": dec_banker_bet,
            "tie_bet": dec_tie_bet,
            "commission_rate": commission_rate,
            "tie_payout_rate": tie_payout_rate,
            "player_drew_third": player_drew_third,
            "banker_drew_third": banker_drew_third # Added for more detailed logging
        }
    }

# if __name__ == '__main__':
#     # Example Usage:
#     print("--- Example Hand 1: Player Bet ---")
#     result1 = play_baccarat_hand(player_bet_amount=100, banker_bet_amount=0, tie_bet_amount=0)
#     print(f"Player Cards: {result1['player_cards']} (Score: {result1['player_score']})")
#     print(f"Banker Cards: {result1['banker_cards']} (Score: {result1['banker_score']})")
#     if result1['details']['player_drew_third']:
#         print(f"Player drew 3rd card (value): {result1['player_third_card_value_if_drawn']}")
#     if result1['details']['banker_drew_third']:
#         print(f"Banker drew 3rd card")
#     print(f"Outcome: {result1['outcome']}")
#     print(f"Total Winnings: {result1['total_winnings']}")
#     print(f"Net Profit: {result1['net_profit']}")
#     print(f"Commission Paid: {result1['commission_paid']}\n")
#
#     print("--- Example Hand 2: Banker Bet ---")
#     result2 = play_baccarat_hand(player_bet_amount=0, banker_bet_amount=100, tie_bet_amount=0)
#     print(f"Player Cards: {result2['player_cards']} (Score: {result2['player_score']})")
#     print(f"Banker Cards: {result2['banker_cards']} (Score: {result2['banker_score']})")
#     if result2['details']['player_drew_third']:
#         print(f"Player drew 3rd card (value): {result2['player_third_card_value_if_drawn']}")
#     if result2['details']['banker_drew_third']:
#         print(f"Banker drew 3rd card")
#     print(f"Outcome: {result2['outcome']}")
#     print(f"Total Winnings: {result2['total_winnings']}")
#     print(f"Net Profit: {result2['net_profit']}")
#     print(f"Commission Paid: {result2['commission_paid']}\n")
#
#     print("--- Example Hand 3: Tie Bet ---")
#     result3 = play_baccarat_hand(player_bet_amount=0, banker_bet_amount=0, tie_bet_amount=100)
#     print(f"Player Cards: {result3['player_cards']} (Score: {result3['player_score']})")
#     print(f"Banker Cards: {result3['banker_cards']} (Score: {result3['banker_score']})")
#     if result3['details']['player_drew_third']:
#         print(f"Player drew 3rd card (value): {result3['player_third_card_value_if_drawn']}")
#     if result3['details']['banker_drew_third']:
#         print(f"Banker drew 3rd card")
#     print(f"Outcome: {result3['outcome']}")
#     print(f"Total Winnings: {result3['total_winnings']}")
#     print(f"Net Profit: {result3['net_profit']}")
#     print(f"Commission Paid: {result3['commission_paid']}\n")
#
#     print("--- Example Hand 4: All Bets, potential Tie ---")
#     # Try to find a tie by running multiple times if needed, or just observe
#     for i in range(5): # Run a few times to see different outcomes
#         print(f"Attempt {i+1}")
#         result4 = play_baccarat_hand(player_bet_amount=10, banker_bet_amount=10, tie_bet_amount=10)
#         print(f"  Player Cards: {result4['player_cards']} (Score: {result4['player_score']})")
#         print(f"  Banker Cards: {result4['banker_cards']} (Score: {result4['banker_score']})")
#         if result4['details']['player_drew_third']:
#             print(f"  Player drew 3rd card (value): {result4['player_third_card_value_if_drawn']}")
#         if result4['details']['banker_drew_third']:
#             print(f"  Banker drew 3rd card")
#         print(f"  Outcome: {result4['outcome']}")
#         print(f"  Total Winnings: {result4['total_winnings']}") # Player bet 10, Banker 10, Tie 10. Total 30.
#                                                             # If Tie: Payout_P=10, Payout_B=10, Payout_T=10*(8+1)=90. Total Winnings=110. Net=80.
#         print(f"  Net Profit: {result4['net_profit']}")
#         print(f"  Commission Paid: {result4['commission_paid']}\n")
#         if result4['outcome'] == 'tie':
#             break
#
#     print("--- Example Hand 5: Player Natural ---")
#     # This requires specific deck setup or many runs. For now, just run normally.
#     result5 = play_baccarat_hand(player_bet_amount=100, banker_bet_amount=0, tie_bet_amount=0)
#     print(f"Player Cards: {result5['player_cards']} (Score: {result5['player_score']})")
#     print(f"Banker Cards: {result5['banker_cards']} (Score: {result5['banker_score']})")
#     print(f"Outcome: {result5['outcome']}")
#     print(f"Net Profit: {result5['net_profit']}\n")
#
#     print("--- Example Hand 6: Banker Natural ---")
#     result6 = play_baccarat_hand(player_bet_amount=0, banker_bet_amount=100, tie_bet_amount=0)
#     print(f"Player Cards: {result6['player_cards']} (Score: {result6['player_score']})")
#     print(f"Banker Cards: {result6['banker_cards']} (Score: {result6['banker_score']})")
#     print(f"Outcome: {result6['outcome']}")
#     print(f"Net Profit: {result6['net_profit']}\n")
#
#     print("--- Example Hand 7: Banker wins, commission check ---")
#     # Try to force a banker win for commission check.
#     # This is hard without deck manipulation. We assume logic is correct.
#     # For a Banker win with 100 bet, commission should be 5. Net profit 95. Total winnings 195.
#     result7 = play_baccarat_hand(player_bet_amount=0, banker_bet_amount=100, tie_bet_amount=0)
#     print(f"Player Cards: {result7['player_cards']} (Score: {result7['player_score']})")
#     print(f"Banker Cards: {result7['banker_cards']} (Score: {result7['banker_score']})")
#     print(f"Outcome: {result7['outcome']}")
#     print(f"Total Winnings: {result7['total_winnings']}")
#     print(f"Net Profit: {result7['net_profit']}")
#     print(f"Commission Paid: {result7['commission_paid']}\n")
#
#     # Test specific third card rules if possible by manipulating deck (not done here)
#     # e.g. Player score 0-5, draws.
#     # Banker score 3, Player's third card 8 -> Banker stands.
#     # Banker score 6, Player's third card 6 or 7 -> Banker draws.
#
#     # Test empty deck error (difficult to force with many decks, but _deal_card has the check)
#     # small_deck = ["H2", "C3", "D4"] # Not enough for initial deal
#     # try:
#     #     play_baccarat_hand(10,0,0, custom_deck=small_deck) # Needs modification to accept custom_deck
#     # except ValueError as e:
#     #     print(f"Caught expected error for small deck: {e}")
#
#     # Test _get_card_baccarat_value
#     print(f"Value of H2: {_get_card_baccarat_value('H2')}") # Expected 2
#     print(f"Value of HK: {_get_card_baccarat_value('HK')}") # Expected 0
#     print(f"Value of DA: {_get_card_baccarat_value('DA')}") # Expected 1
#     # try:
#     #     _get_card_baccarat_value('X5') # Invalid
#     # except ValueError as e:
#     #     print(f"Caught expected error for invalid card: {e}")
#
#     print(f"Hand value ['H5', 'C2']: {_calculate_baccarat_hand_value(['H5', 'C2'])}") # 7
#     print(f"Hand value ['DT', 'S9']: {_calculate_baccarat_hand_value(['DT', 'S9'])}") # 9
#     print(f"Hand value ['HA', 'C9']: {_calculate_baccarat_hand_value(['HA', 'C9'])}") # 0
#     print(f"Hand value ['HK', 'CQ', 'SJ']: {_calculate_baccarat_hand_value(['HK', 'CQ', 'SJ'])}") # 0
#     print(f"Hand value ['H7', 'D8']: {_calculate_baccarat_hand_value(['H7', 'D8'])}") # 5 (15 % 10)
#
#``` Removed trailing characters
