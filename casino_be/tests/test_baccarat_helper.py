import unittest
from unittest.mock import patch, MagicMock
from decimal import Decimal

# Assuming baccarat_helper.py is in casino_be.utils
from casino_be.utils import baccarat_helper

class TestBaccaratHelper(unittest.TestCase):

    def test_create_deck(self):
        deck = baccarat_helper._create_deck(num_decks=1)
        self.assertEqual(len(deck), 52)
        self.assertIn("HA", deck) # Heart Ace
        self.assertIn("SK", deck) # Spade King
        self.assertIn("D2", deck) # Diamond 2
        self.assertIn("C9", deck) # Club 9

        deck_6 = baccarat_helper._create_deck(num_decks=6)
        self.assertEqual(len(deck_6), 52 * 6)
        # Check if a specific card appears 6 times
        self.assertEqual(deck_6.count("HA"), 6)

    def test_shuffle_deck(self):
        deck1 = baccarat_helper._create_deck(num_decks=1)
        deck2 = list(deck1) # Create a copy
        baccarat_helper._shuffle_deck(deck2)
        # Check if the deck is shuffled (not identical to original, high probability)
        # This is a probabilistic test, could fail rarely but good enough for this.
        self.assertNotEqual(deck1, deck2, "Deck should be shuffled and not identical to the original.")
        self.assertEqual(len(deck1), len(deck2), "Shuffled deck should have the same length.")
        for card in deck1: # Ensure all original cards are still present
            self.assertIn(card, deck2)

    def test_deal_card(self):
        deck = ["HA", "SK", "D2"]
        card1 = baccarat_helper._deal_card(deck)
        self.assertEqual(card1, "HA")
        self.assertEqual(len(deck), 2)
        self.assertNotIn("HA", deck)

        card2 = baccarat_helper._deal_card(deck)
        self.assertEqual(card2, "SK")
        self.assertEqual(len(deck), 1)

        card3 = baccarat_helper._deal_card(deck)
        self.assertEqual(card3, "D2")
        self.assertEqual(len(deck), 0)

        with self.assertRaises(ValueError, msg="Dealing from an empty deck should raise ValueError."):
            baccarat_helper._deal_card(deck)

    def test_get_card_baccarat_value(self):
        self.assertEqual(baccarat_helper._get_card_baccarat_value("HA"), 1)
        self.assertEqual(baccarat_helper._get_card_baccarat_value("SA"), 1)
        self.assertEqual(baccarat_helper._get_card_baccarat_value("HK"), 0)
        self.assertEqual(baccarat_helper._get_card_baccarat_value("DQ"), 0)
        self.assertEqual(baccarat_helper._get_card_baccarat_value("CJ"), 0)
        self.assertEqual(baccarat_helper._get_card_baccarat_value("ST"), 0) # Ten
        self.assertEqual(baccarat_helper._get_card_baccarat_value("H9"), 9)
        self.assertEqual(baccarat_helper._get_card_baccarat_value("C5"), 5)
        self.assertEqual(baccarat_helper._get_card_baccarat_value("D2"), 2)
        with self.assertRaises(ValueError):
            baccarat_helper._get_card_baccarat_value("X0") # Invalid card

    def test_calculate_baccarat_hand_value(self):
        self.assertEqual(baccarat_helper._calculate_baccarat_hand_value(["HA", "H9"]), 0) # 1 + 9 = 10 % 10 = 0
        self.assertEqual(baccarat_helper._calculate_baccarat_hand_value(["HK", "H7"]), 7) # 0 + 7 = 7
        self.assertEqual(baccarat_helper._calculate_baccarat_hand_value(["D5", "C2"]), 7) # 5 + 2 = 7
        self.assertEqual(baccarat_helper._calculate_baccarat_hand_value(["S8", "H8"]), 6) # 8 + 8 = 16 % 10 = 6
        self.assertEqual(baccarat_helper._calculate_baccarat_hand_value(["HA", "HK", "H2"]), 3) # 1 + 0 + 2 = 3
        self.assertEqual(baccarat_helper._calculate_baccarat_hand_value(["DT", "SJ", "CQ"]), 0) # 0 + 0 + 0 = 0

    def test_calculate_payouts(self):
        commission_rate = Decimal("0.05")
        tie_payout_rate = 8

        # Player Win
        p_player, p_banker, p_tie, p_comm = baccarat_helper._calculate_payouts(
            "player_win", Decimal(100), Decimal(0), Decimal(0), commission_rate, tie_payout_rate
        )
        self.assertEqual(p_player, Decimal(200)) # Original bet + 1:1 win
        self.assertEqual(p_banker, Decimal(0))
        self.assertEqual(p_tie, Decimal(0))
        self.assertEqual(p_comm, Decimal(0))

        # Banker Win
        p_player, p_banker, p_tie, p_comm = baccarat_helper._calculate_payouts(
            "banker_win", Decimal(0), Decimal(100), Decimal(0), commission_rate, tie_payout_rate
        )
        self.assertEqual(p_player, Decimal(0))
        self.assertEqual(p_banker, Decimal(100) + (Decimal(100) * (Decimal(1) - commission_rate))) # Original bet + win (after commission) = 100 + 95 = 195
        self.assertEqual(p_tie, Decimal(0))
        self.assertEqual(p_comm, Decimal(100) * commission_rate) # 5

        # Tie Win (only tie bet wins, player/banker bets push)
        p_player, p_banker, p_tie, p_comm = baccarat_helper._calculate_payouts(
            "tie", Decimal(50), Decimal(50), Decimal(10), commission_rate, tie_payout_rate
        )
        self.assertEqual(p_player, Decimal(50)) # Push
        self.assertEqual(p_banker, Decimal(50)) # Push
        self.assertEqual(p_tie, Decimal(10) * (Decimal(tie_payout_rate) + Decimal(1))) # Original bet + 8:1 win = 10 * 9 = 90
        self.assertEqual(p_comm, Decimal(0))

        # Zero bets
        p_player, p_banker, p_tie, p_comm = baccarat_helper._calculate_payouts(
            "player_win", Decimal(0), Decimal(0), Decimal(0), commission_rate, tie_payout_rate
        )
        self.assertEqual(p_player, Decimal(0))
        self.assertEqual(p_banker, Decimal(0))
        self.assertEqual(p_tie, Decimal(0))
        self.assertEqual(p_comm, Decimal(0))

    @patch('casino_be.utils.baccarat_helper._deal_card')
    def test_play_baccarat_hand_natural_win(self, mock_deal_card):
        # Player natural 8
        mock_deal_card.side_effect = ["H8", "C2", "SA", "C3"] # P: H8, SA (9); B: C2, C3 (5) -> Error in logic: P: H8, SA (9), B: C2,C3 (5) -> P Nat 8
                                                        # Corrected side effect for Player Natural 8: P: H8, Dk (8); B: C2, C3 (5)
        mock_deal_card.side_effect = ["H8", "C2", "DK", "C3"] # P: H8, DK (8); B: C2, C3 (5)
        result = baccarat_helper.play_baccarat_hand(Decimal(10), Decimal(0), Decimal(0))
        self.assertEqual(result["outcome"], "player_win")
        self.assertEqual(result["player_score"], 8)
        self.assertEqual(result["banker_score"], 5)
        self.assertEqual(len(result["player_cards"]), 2)
        self.assertEqual(len(result["banker_cards"]), 2)
        self.assertEqual(result["net_profit"], Decimal(10))

        # Banker natural 9
        mock_deal_card.side_effect = ["H2", "C9", "H3", "SA"] # P: H2, H3 (5); B: C9, SA (0) -> Error in logic: B Nat 9
                                                        # Corrected: P: H2, H3 (5); B: C9, SK (9)
        mock_deal_card.side_effect = ["H2", "C9", "H3", "SK"] # P: H2, H3 (5); B: C9, SK (9)
        result = baccarat_helper.play_baccarat_hand(Decimal(0), Decimal(10), Decimal(0))
        self.assertEqual(result["outcome"], "banker_win")
        self.assertEqual(result["player_score"], 5)
        self.assertEqual(result["banker_score"], 9)
        self.assertEqual(result["net_profit"], Decimal("9.5")) # 10 * 0.95
        self.assertEqual(result["commission_paid"], Decimal("0.5")) # 10 * 0.05

        # Natural Tie (e.g., 8 vs 8)
        mock_deal_card.side_effect = ["H8", "C8", "SJ", "DJ"] # P: H8, SJ (8); B: C8, DJ (8)
        result = baccarat_helper.play_baccarat_hand(Decimal(0), Decimal(0), Decimal(10))
        self.assertEqual(result["outcome"], "tie")
        self.assertEqual(result["player_score"], 8)
        self.assertEqual(result["banker_score"], 8)
        self.assertEqual(result["net_profit"], Decimal(80)) # 10 * 8 (assuming tie_payout_rate=8)

    @patch('casino_be.utils.baccarat_helper._deal_card')
    def test_player_draws_third_card(self, mock_deal_card):
        # Player score 0-5, draws. Banker stands or draws based on rules.
        # Player initial: H1 (1) + H2 (2) = 3. Player draws.
        # Banker initial: H7 (7) + HK (0) = 7. Banker stands.
        # Player draws H3 (3). Player final = 1+2+3 = 6.
        # Outcome: Banker wins 7 vs 6.
        mock_deal_card.side_effect = ["HA", "H7", "H2", "HK", "H3"] # P: HA,H2 (3) -> draws H3 (6). B: H7,HK (7) -> stands.
        result = baccarat_helper.play_baccarat_hand(Decimal(0), Decimal(10), Decimal(0))
        self.assertEqual(result["outcome"], "banker_win")
        self.assertEqual(result["player_score"], 6)
        self.assertEqual(result["banker_score"], 7)
        self.assertEqual(len(result["player_cards"]), 3)
        self.assertEqual(len(result["banker_cards"]), 2)
        self.assertTrue(result["details"]["player_drew_third"])
        self.assertFalse(result["details"]["banker_drew_third"])

    @patch('casino_be.utils.baccarat_helper._deal_card')
    def test_banker_third_card_rules(self, mock_deal_card):
        # Scenario 1: Player stands (score 6 or 7). Banker draws if score 0-5.
        # Player: H6, HK (6) -> Stands.
        # Banker: H2, H3 (5) -> Banker Draws. Banker draws H1 (1). Banker total 6.
        # Outcome: Tie
        mock_deal_card.side_effect = ["H6", "H2", "HK", "H3", "HA"] # P: H6,HK (6) -> stands. B: H2,H3 (5) -> draws HA (6)
        result = baccarat_helper.play_baccarat_hand(Decimal(0), Decimal(0), Decimal(10)) # Bet on Tie
        self.assertEqual(result["outcome"], "tie")
        self.assertEqual(result["player_score"], 6)
        self.assertEqual(result["banker_score"], 6)
        self.assertEqual(len(result["player_cards"]), 2)
        self.assertEqual(len(result["banker_cards"]), 3)
        self.assertFalse(result["details"]["player_drew_third"])
        self.assertTrue(result["details"]["banker_drew_third"])
        self.assertEqual(result["net_profit"], Decimal(80))

        # Scenario 2: Player draws. Banker score 3, Player's 3rd card NOT 8. Banker draws.
        # Player: HA, H2 (3) -> Draws H4 (value 4). Player total 7.
        # Banker: H1, H2 (3) -> Player's 3rd card is 4 (not 8). Banker draws. Banker draws H1 (1). Banker total 4.
        # Outcome: Player wins.
        mock_deal_card.side_effect = ["HA", "H1", "H2", "H2", "H4", "HA"] # P:HA,H2 (3) dr H4 (7). B:H1,H2 (3) dr HA (4)
        result = baccarat_helper.play_baccarat_hand(Decimal(10), Decimal(0), Decimal(0))
        self.assertEqual(result["outcome"], "player_win")
        self.assertEqual(result["player_score"], 7)
        self.assertEqual(result["banker_score"], 4)
        self.assertTrue(result["details"]["player_drew_third"])
        self.assertTrue(result["details"]["banker_drew_third"])
        self.assertEqual(result["player_third_card_value_if_drawn"], 4)

        # Scenario 3: Player draws. Banker score 6, Player's 3rd card 6 or 7. Banker draws.
        # Player: H2, H3 (5) -> Draws H6 (value 6). Player total 1.
        # Banker: H3, H3 (6) -> Player's 3rd card is 6. Banker draws. Banker draws H2 (2). Banker total 8.
        # Outcome: Banker wins.
        mock_deal_card.side_effect = ["H2", "H3", "H3", "H3", "H6", "H2"] # P:H2,H3 (5) dr H6 (1). B:H3,H3 (6) dr H2 (8)
        result = baccarat_helper.play_baccarat_hand(Decimal(0), Decimal(10), Decimal(0))
        self.assertEqual(result["outcome"], "banker_win")
        self.assertEqual(result["player_score"], 1) # (5+6=11 -> 1)
        self.assertEqual(result["banker_score"], 8) # (6+2=8)
        self.assertTrue(result["details"]["player_drew_third"])
        self.assertTrue(result["details"]["banker_drew_third"])
        self.assertEqual(result["player_third_card_value_if_drawn"], 6)
        self.assertEqual(result["net_profit"], Decimal("9.50"))


    @patch('casino_be.utils.baccarat_helper._deal_card')
    def test_banker_stands_player_draws_third_card_8(self, mock_deal_card):
        # Player: HA, H2 (3) -> Draws H8 (value 8). Player total 1.
        # Banker: H1, H2 (3) -> Player's 3rd card is 8. Banker stands. Banker total 3.
        # Outcome: Banker wins.
        mock_deal_card.side_effect = ["HA", "H1", "H2", "H2", "H8"] # P:HA,H2 (3) dr H8 (1). B:H1,H2 (3) stands.
        result = baccarat_helper.play_baccarat_hand(Decimal(0), Decimal(10), Decimal(0))
        self.assertEqual(result["outcome"], "banker_win")
        self.assertEqual(result["player_score"], 1)
        self.assertEqual(result["banker_score"], 3)
        self.assertTrue(result["details"]["player_drew_third"])
        self.assertFalse(result["details"]["banker_drew_third"], "Banker should stand if player's 3rd card is 8 and banker score is 3")
        self.assertEqual(result["player_third_card_value_if_drawn"], 8)
        self.assertEqual(result["net_profit"], Decimal("9.50"))

if __name__ == '__main__':
    unittest.main()
