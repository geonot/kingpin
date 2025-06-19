import unittest
from unittest.mock import patch, MagicMock
import json
from datetime import datetime, timezone

from casino_be.app import db
from casino_be.models import User, AstroMinerXExpedition, AstroMinerXAsteroid, AstroMinerXResource
from casino_be.tests.test_api import BaseTestCase # Import BaseTestCase
from casino_be.schemas import AstroMinerXExpeditionSchema, AstroMinerXAsteroidSchema, AstroMinerXResourceSchema
from casino_be.error_codes import ErrorCodes

# To avoid recreating schemas in tests, import them if they are centrally defined
# from casino_be.schemas import AstroMinerXExpeditionSchema, AstroMinerXAsteroidSchema, AstroMinerXResourceSchema

class TestAstroMinerXRoutes(BaseTestCase):

    def setUp(self):
        super().setUp()
        # self.user is created in BaseTestCase's _login_and_get_token if called
        # For route tests, we often need a token.
        self.token, self.user_id = self._login_and_get_token(username_prefix="route_tester")
        self.auth_headers = {'Authorization': f'Bearer {self.token}'}

        # Fetch the user object if needed for setting up test conditions
        with self.app.app_context():
            self.user = User.query.get(self.user_id)
            self.user.balance = 10000 # Give some initial balance for tests
            db.session.commit()

    @patch('casino_be.routes.astrominerx.astrominerx_service.launch_expedition_service')
    def test_launch_expedition_route_success(self, mock_launch_service):
        bet_amount = 100.0
        # Mock service response
        mock_expedition = MagicMock(spec=AstroMinerXExpedition)
        mock_expedition.id = 1
        mock_expedition.user_id = self.user_id
        mock_expedition.bet_amount = bet_amount
        mock_expedition.status = "active"
        mock_expedition.start_time = datetime.now(timezone.utc)
        mock_expedition.end_time = None
        mock_expedition.total_value_collected = 0
        mock_expedition.user = self.user
        # Mock relationships if schema tries to access them directly (SQLAlchemyAutoSchema might)
        mock_expedition.asteroids = []
        mock_expedition.resources_collected = []


        mock_asteroids = [] # Assuming service returns a list of asteroid objects
        mock_new_balance = self.user.balance - bet_amount

        mock_launch_service.return_value = (mock_expedition, mock_asteroids, mock_new_balance)

        response = self.client.post('/api/astrominerx/launch',
                                     headers=self.auth_headers,
                                     json={'bet_amount': bet_amount})
        data = response.get_json()

        self.assertEqual(response.status_code, 201)
        self.assertTrue(data['status'])
        self.assertEqual(data['expedition']['id'], mock_expedition.id)
        self.assertEqual(data['expedition']['bet_amount'], bet_amount)
        self.assertEqual(data['user_balance'], mock_new_balance)
        mock_launch_service.assert_called_once_with(user=unittest.mock.ANY, bet_amount=bet_amount)


    def test_launch_expedition_route_missing_bet(self):
        response = self.client.post('/api/astrominerx/launch', headers=self.auth_headers, json={})
        data = response.get_json()
        self.assertEqual(response.status_code, 422) # ValidationException
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.VALIDATION_ERROR)
        self.assertIn("Missing bet_amount", data['status_message'])

    @patch('casino_be.routes.astrominerx.astrominerx_service.get_expedition_state_service')
    @patch('casino_be.routes.astrominerx.astrominerx_service.scan_asteroid_service')
    def test_scan_asteroid_route_success(self, mock_scan_service, mock_get_expedition_service):
        expedition_id = 1
        asteroid_id = 101

        # Mock for get_expedition_state_service (called first in the route)
        mock_expedition_obj = MagicMock(spec=AstroMinerXExpedition)
        mock_expedition_obj.id = expedition_id
        mock_expedition_obj.user_id = self.user_id
        mock_expedition_obj.status = "active"
        mock_get_expedition_service.return_value = mock_expedition_obj

        # Mock for scan_asteroid_service
        mock_scanned_asteroid = MagicMock(spec=AstroMinerXAsteroid)
        mock_scanned_asteroid.id = asteroid_id
        mock_scanned_asteroid.expedition_id = expedition_id
        mock_scanned_asteroid.asteroid_type = "iron_ore"
        mock_scanned_asteroid.value = 15.0
        mock_scanned_asteroid.is_empty = False
        mock_scanned_asteroid.is_hazard = False
        mock_scanned_asteroid.scan_time = datetime.now(timezone.utc)

        mock_event_details = None
        mock_new_balance = self.user.balance # Assuming scan is free for this test

        mock_scan_service.return_value = (mock_scanned_asteroid, mock_event_details, mock_new_balance)

        response = self.client.post('/api/astrominerx/scan',
                                     headers=self.auth_headers,
                                     json={'expedition_id': expedition_id, 'asteroid_id': asteroid_id})
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['status'])
        self.assertEqual(data['scan_result']['id'], asteroid_id)
        self.assertEqual(data['scan_result']['asteroid_type'], "iron_ore")
        self.assertEqual(data['user_balance'], mock_new_balance)

        mock_get_expedition_service.assert_called_once_with(expedition_id, unittest.mock.ANY) # ANY for current_user
        mock_scan_service.assert_called_once_with(expedition=mock_expedition_obj, asteroid_id=asteroid_id)

    def test_scan_asteroid_route_missing_params(self):
        response = self.client.post('/api/astrominerx/scan', headers=self.auth_headers, json={'expedition_id': 1})
        data = response.get_json()
        self.assertEqual(response.status_code, 422)
        self.assertIn("Missing expedition_id or asteroid_id", data['status_message'])

        response = self.client.post('/api/astrominerx/scan', headers=self.auth_headers, json={'asteroid_id': 1})
        data = response.get_json()
        self.assertEqual(response.status_code, 422)
        self.assertIn("Missing expedition_id or asteroid_id", data['status_message'])

    @patch('casino_be.routes.astrominerx.astrominerx_service.get_expedition_state_service')
    @patch('casino_be.routes.astrominerx.astrominerx_service.collect_resources_service')
    def test_collect_resources_route_success(self, mock_collect_service, mock_get_expedition_service):
        expedition_id = 1

        mock_expedition_obj = MagicMock(spec=AstroMinerXExpedition) # For get_expedition_state_service
        mock_expedition_obj.id = expedition_id
        mock_expedition_obj.user_id = self.user_id
        mock_expedition_obj.status = "active"
        mock_get_expedition_service.return_value = mock_expedition_obj

        # Mock for collect_resources_service
        mock_final_expedition = MagicMock(spec=AstroMinerXExpedition)
        mock_final_expedition.id = expedition_id
        mock_final_expedition.status = "completed"
        mock_final_expedition.total_value_collected = 150.0
        mock_final_expedition.user = self.user # For schema serialization
        mock_final_expedition.asteroids = []
        mock_final_expedition.resources_collected = []


        mock_collected_resources = [] # List of AstroMinerXResource mocks if needed by schema
        mock_new_balance = self.user.balance + 150.0

        mock_collect_service.return_value = (mock_final_expedition, mock_collected_resources, mock_new_balance)

        response = self.client.post('/api/astrominerx/collect',
                                      headers=self.auth_headers,
                                      json={'expedition_id': expedition_id})
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['status'])
        self.assertEqual(data['expedition_summary']['id'], expedition_id)
        self.assertEqual(data['expedition_summary']['status'], "completed")
        self.assertEqual(data['expedition_summary']['total_value_collected'], 150.0)
        self.assertEqual(data['user_balance'], mock_new_balance)

        mock_get_expedition_service.assert_called_once_with(expedition_id, unittest.mock.ANY)
        mock_collect_service.assert_called_once_with(expedition=mock_expedition_obj)

    @patch('casino_be.routes.astrominerx.astrominerx_service.get_expedition_state_service')
    def test_get_expedition_status_route_success(self, mock_get_expedition_service):
        expedition_id = 1

        mock_expedition = MagicMock(spec=AstroMinerXExpedition)
        mock_expedition.id = expedition_id
        mock_expedition.user_id = self.user_id
        mock_expedition.status = "active"
        mock_expedition.bet_amount = 100.0
        mock_expedition.user = self.user # Required by schema
        mock_expedition.asteroids = [] # Required by schema
        mock_expedition.resources_collected = [] # Required by schema


        mock_get_expedition_service.return_value = mock_expedition

        response = self.client.get(f'/api/astrominerx/expedition/{expedition_id}', headers=self.auth_headers)
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['status'])
        self.assertEqual(data['expedition']['id'], expedition_id)
        self.assertEqual(data['expedition']['status'], "active")
        mock_get_expedition_service.assert_called_once_with(expedition_id, unittest.mock.ANY)

    @patch('casino_be.routes.astrominerx.astrominerx_service.get_expedition_state_service')
    def test_get_expedition_status_route_not_found(self, mock_get_expedition_service):
        expedition_id = 999 # Non-existent
        mock_get_expedition_service.side_effect = NotFoundException(ErrorCodes.GAME_NOT_FOUND, "Expedition not found.")

        response = self.client.get(f'/api/astrominerx/expedition/{expedition_id}', headers=self.auth_headers)
        data = response.get_json()

        self.assertEqual(response.status_code, 404) # NotFoundException
        self.assertFalse(data['status'])
        self.assertEqual(data['error_code'], ErrorCodes.GAME_NOT_FOUND)
        mock_get_expedition_service.assert_called_once_with(expedition_id, unittest.mock.ANY)

    def test_launch_expedition_route_insufficient_funds_service_exception(self):
        # Test how the route handles an InsufficientFundsException from the service
        with patch('casino_be.routes.astrominerx.astrominerx_service.launch_expedition_service') as mock_launch:
            mock_launch.side_effect = InsufficientFundsException("Not enough credits.")

            response = self.client.post('/api/astrominerx/launch',
                                         headers=self.auth_headers,
                                         json={'bet_amount': 100000.0}) # High bet
            data = response.get_json()

            self.assertEqual(response.status_code, 400) # InsufficientFundsException default code
            self.assertFalse(data['status'])
            self.assertEqual(data['error_code'], ErrorCodes.INSUFFICIENT_FUNDS)
            self.assertEqual(data['status_message'], "Not enough credits.")


if __name__ == '__main__':
    unittest.main()
