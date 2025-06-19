import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import random

from casino_be.app import db
from casino_be.models import User, AstroMinerXExpedition, AstroMinerXAsteroid, AstroMinerXResource, Transaction
from casino_be.services import astrominerx_service
from casino_be.exceptions import InsufficientFundsException, ValidationException, NotFoundException, GameLogicException
from casino_be.error_codes import ErrorCodes
from casino_be.tests.test_api import BaseTestCase

class TestAstroMinerXService(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.user = self._create_user(username="service_tester", balance=1000.0)
        db.session.add(self.user) # Ensure user is added via self's session
        db.session.commit()


    def test_launch_expedition_service_success(self):
        bet_amount = 100.0
        initial_balance = self.user.balance

        expedition, initial_asteroids, new_balance = astrominerx_service.launch_expedition_service(self.user, bet_amount)

        self.assertIsNotNone(expedition.id)
        self.assertEqual(expedition.user_id, self.user.id)
        self.assertEqual(expedition.bet_amount, bet_amount)
        self.assertEqual(expedition.status, "active")
        self.assertTrue(astrominerx_service.ASTEROID_COUNT_MIN <= len(initial_asteroids) <= astrominerx_service.ASTEROID_COUNT_MAX)

        for asteroid in initial_asteroids:
            self.assertEqual(asteroid.expedition_id, expedition.id)
            self.assertEqual(asteroid.asteroid_type, "unknown_asteroid") # As per service logic

        self.assertEqual(new_balance, initial_balance - bet_amount)
        self.assertEqual(self.user.balance, initial_balance - bet_amount)

        # Check for transaction
        transaction = Transaction.query.filter_by(user_id=self.user.id, transaction_type='astrominerx_bet').first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.amount, -bet_amount)

    def test_launch_expedition_service_insufficient_funds(self):
        self.user.balance = 50.0
        db.session.commit()
        bet_amount = 100.0

        with self.assertRaises(InsufficientFundsException) as context:
            astrominerx_service.launch_expedition_service(self.user, bet_amount)
        self.assertEqual(context.exception.status_message, "Insufficient balance to start expedition.")

    def test_launch_expedition_service_invalid_bet(self):
        with self.assertRaises(ValidationException) as context:
            astrominerx_service.launch_expedition_service(self.user, 0)
        self.assertEqual(context.exception.error_code, ErrorCodes.INVALID_BET)

        with self.assertRaises(ValidationException) as context:
            astrominerx_service.launch_expedition_service(self.user, -10)
        self.assertEqual(context.exception.error_code, ErrorCodes.INVALID_BET)

        with self.assertRaises(ValidationException) as context:
            astrominerx_service.launch_expedition_service(self.user, "not_a_number")
        self.assertEqual(context.exception.error_code, ErrorCodes.INVALID_BET)


    @patch('casino_be.services.astrominerx_service._generate_random_asteroid_properties')
    def test_scan_asteroid_service_success(self, mock_generate_properties):
        # Setup expedition and an unknown asteroid
        expedition, _, _ = astrominerx_service.launch_expedition_service(self.user, 50.0)
        asteroid_to_scan = expedition.asteroids.first() # Get one of the generated asteroids
        self.assertIsNotNone(asteroid_to_scan)
        self.assertEqual(asteroid_to_scan.asteroid_type, "unknown_asteroid")

        # Mock the RNG part
        mock_scan_result = {
            "asteroid_type": "iron_ore",
            "is_hazard": False,
            "is_empty": False,
            "value": 25.0
        }
        mock_generate_properties.return_value = mock_scan_result

        scanned_asteroid, event_details, _ = astrominerx_service.scan_asteroid_service(expedition, asteroid_to_scan.id)

        mock_generate_properties.assert_called_once()
        self.assertIsNotNone(scanned_asteroid.scan_time)
        self.assertEqual(scanned_asteroid.asteroid_type, mock_scan_result["asteroid_type"])
        self.assertEqual(scanned_asteroid.is_hazard, mock_scan_result["is_hazard"])
        self.assertEqual(scanned_asteroid.is_empty, mock_scan_result["is_empty"])
        self.assertEqual(scanned_asteroid.value, mock_scan_result["value"])
        self.assertIsNone(event_details) # Default no event

    def test_scan_asteroid_service_not_active(self):
        expedition, _, _ = astrominerx_service.launch_expedition_service(self.user, 50.0)
        expedition.status = "completed"
        db.session.commit()
        asteroid_to_scan = expedition.asteroids.first()

        with self.assertRaises(GameLogicException) as context:
            astrominerx_service.scan_asteroid_service(expedition, asteroid_to_scan.id)
        self.assertEqual(context.exception.error_code, ErrorCodes.EXPEDITION_NOT_ACTIVE)

    def test_scan_asteroid_service_not_found(self):
        expedition, _, _ = astrominerx_service.launch_expedition_service(self.user, 50.0)
        with self.assertRaises(NotFoundException) as context:
            astrominerx_service.scan_asteroid_service(expedition, 99999) # Non-existent ID
        self.assertEqual(context.exception.error_code, ErrorCodes.ASTEROID_NOT_FOUND)

    def test_scan_asteroid_service_already_scanned(self):
        expedition, _, _ = astrominerx_service.launch_expedition_service(self.user, 50.0)
        asteroid_to_scan = expedition.asteroids.first()
        # Simulate a scan
        with patch('casino_be.services.astrominerx_service._generate_random_asteroid_properties') as mock_gen:
            mock_gen.return_value = {"asteroid_type": "test", "is_hazard": False, "is_empty": False, "value": 1}
            astrominerx_service.scan_asteroid_service(expedition, asteroid_to_scan.id)

        # Try to scan again
        with self.assertRaises(GameLogicException) as context:
            astrominerx_service.scan_asteroid_service(expedition, asteroid_to_scan.id)
        self.assertEqual(context.exception.error_code, ErrorCodes.ASTEROID_ALREADY_SCANNED)

    @patch('casino_be.services.astrominerx_service.random.random')
    @patch('casino_be.services.astrominerx_service._generate_random_asteroid_properties')
    def test_scan_asteroid_service_with_pirate_event(self, mock_generate_properties, mock_random_roll):
        expedition, _, _ = astrominerx_service.launch_expedition_service(self.user, 50.0)
        asteroid_to_scan = expedition.asteroids.first()

        mock_generate_properties.return_value = {"asteroid_type": "iron_ore", "is_hazard": False, "is_empty": False, "value": 10.0}

        # Setup random rolls: first for MINI_EVENT_CHANCE, second for PIRATE_AMBUSH_CHANCE
        # MINI_EVENT_CHANCE = 0.05, PIRATE_AMBUSH_CHANCE = 0.3
        mock_random_roll.side_effect = [0.04, 0.2] # Trigger event, then trigger pirate ambush

        scanned_asteroid, event_details, _ = astrominerx_service.scan_asteroid_service(expedition, asteroid_to_scan.id)

        self.assertIsNotNone(event_details)
        self.assertEqual(event_details["type"], "pirate_ambush")
        # self.assertEqual(expedition.status, "active") # Default behavior, event doesn't abort yet

    def test_collect_resources_service_success(self):
        expedition, initial_asteroids, _ = astrominerx_service.launch_expedition_service(self.user, 100.0)
        initial_balance = self.user.balance # Balance after bet

        # Simulate scanning some asteroids to have value
        total_expected_value = 0
        with patch('casino_be.services.astrominerx_service._generate_random_asteroid_properties') as mock_gen:
            mock_gen.return_value = {"asteroid_type": "gold_nugget", "is_hazard": False, "is_empty": False, "value": 50.0}
            astrominerx_service.scan_asteroid_service(expedition, initial_asteroids[0].id)
            total_expected_value += 50.0

            mock_gen.return_value = {"asteroid_type": "silver_crystal", "is_hazard": False, "is_empty": False, "value": 20.0}
            astrominerx_service.scan_asteroid_service(expedition, initial_asteroids[1].id)
            total_expected_value += 20.0

            # A hazard asteroid, should not be collected
            mock_gen.return_value = {"asteroid_type": "gas_pocket", "is_hazard": True, "is_empty": True, "value": 0.0}
            astrominerx_service.scan_asteroid_service(expedition, initial_asteroids[2].id)

            # An empty rock, should not be collected
            mock_gen.return_value = {"asteroid_type": "empty_rock", "is_hazard": False, "is_empty": True, "value": 0.0}
            astrominerx_service.scan_asteroid_service(expedition, initial_asteroids[3].id)

        final_expedition, collected_resources, new_balance = astrominerx_service.collect_resources_service(expedition)

        self.assertEqual(final_expedition.status, "completed")
        self.assertIsNotNone(final_expedition.end_time)
        self.assertEqual(final_expedition.total_value_collected, total_expected_value)
        self.assertEqual(len(collected_resources), 2) # Only 2 valuable resources

        # Verify resource names and values
        resource_names = [r.resource_name for r in collected_resources]
        self.assertIn("gold_nugget", resource_names)
        self.assertIn("silver_crystal", resource_names)

        self.assertEqual(new_balance, initial_balance + total_expected_value)
        self.assertEqual(self.user.balance, initial_balance + total_expected_value)

        # Check for win transaction
        win_tx = Transaction.query.filter_by(user_id=self.user.id, transaction_type='astrominerx_win').first()
        self.assertIsNotNone(win_tx)
        self.assertEqual(win_tx.amount, total_expected_value)

    def test_collect_resources_service_already_completed(self):
        expedition, _, _ = astrominerx_service.launch_expedition_service(self.user, 100.0)
        expedition.status = "completed"
        db.session.commit()

        with self.assertRaises(GameLogicException) as context:
            astrominerx_service.collect_resources_service(expedition)
        self.assertEqual(context.exception.status_message, "Expedition already completed.")

    def test_get_expedition_state_service_success(self):
        expedition_launched, _, _ = astrominerx_service.launch_expedition_service(self.user, 100.0)

        retrieved_expedition = astrominerx_service.get_expedition_state_service(expedition_launched.id, self.user)

        self.assertIsNotNone(retrieved_expedition)
        self.assertEqual(retrieved_expedition.id, expedition_launched.id)
        self.assertEqual(retrieved_expedition.user_id, self.user.id)
        # Check if relationships are loaded (asteroids, resources_collected)
        self.assertTrue(hasattr(retrieved_expedition, 'asteroids'))
        self.assertTrue(hasattr(retrieved_expedition, 'resources_collected'))

    def test_get_expedition_state_service_not_found(self):
        with self.assertRaises(NotFoundException) as context:
            astrominerx_service.get_expedition_state_service(99999, self.user)
        self.assertEqual(context.exception.error_code, ErrorCodes.GAME_NOT_FOUND)

    def test_get_expedition_state_service_wrong_user(self):
        expedition_launched, _, _ = astrominerx_service.launch_expedition_service(self.user, 100.0)

        other_user = self._create_user(username="otherplayer", email="other@example.com", balance=500)
        db.session.add(other_user)
        db.session.commit()

        with self.assertRaises(NotFoundException) as context: # Or AuthorizationException depending on desired behavior
            astrominerx_service.get_expedition_state_service(expedition_launched.id, other_user)
        self.assertEqual(context.exception.error_code, ErrorCodes.GAME_NOT_FOUND)


if __name__ == '__main__':
    unittest.main()
