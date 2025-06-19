import unittest
from datetime import datetime, timezone

from casino_be.app import db
from casino_be.models import User, AstroMinerXExpedition, AstroMinerXAsteroid, AstroMinerXResource
from casino_be.tests.test_api import BaseTestCase # Import BaseTestCase

class TestAstroMinerXModels(BaseTestCase):

    def test_create_astro_miner_x_expedition(self):
        """Test creation of an AstroMinerXExpedition."""
        user = self._create_user(username="expedition_owner") # Helper from BaseTestCase

        expedition = AstroMinerXExpedition(
            user_id=user.id,
            bet_amount=100.0,
            start_time=datetime.now(timezone.utc),
            status="active"
        )
        db.session.add(expedition)
        db.session.commit()

        self.assertIsNotNone(expedition.id)
        self.assertEqual(expedition.user_id, user.id)
        self.assertEqual(expedition.bet_amount, 100.0)
        self.assertEqual(expedition.status, "active")
        self.assertEqual(expedition.total_value_collected, 0) # Default value
        self.assertIsNotNone(expedition.start_time)
        self.assertIsNone(expedition.end_time)
        self.assertEqual(expedition.user, user)

    def test_create_astro_miner_x_asteroid(self):
        """Test creation of an AstroMinerXAsteroid."""
        user = self._create_user(username="asteroid_finder")
        expedition = AstroMinerXExpedition(user_id=user.id, bet_amount=50.0)
        db.session.add(expedition)
        db.session.commit()

        asteroid = AstroMinerXAsteroid(
            expedition_id=expedition.id,
            asteroid_type="iron_ore",
            value=25.5,
            is_empty=False,
            is_hazard=False,
            scan_time=datetime.now(timezone.utc)
        )
        db.session.add(asteroid)
        db.session.commit()

        self.assertIsNotNone(asteroid.id)
        self.assertEqual(asteroid.expedition_id, expedition.id)
        self.assertEqual(asteroid.asteroid_type, "iron_ore")
        self.assertEqual(asteroid.value, 25.5)
        self.assertFalse(asteroid.is_empty)
        self.assertFalse(asteroid.is_hazard)
        self.assertIsNotNone(asteroid.scan_time)
        self.assertEqual(asteroid.expedition, expedition)

    def test_create_astro_miner_x_resource(self):
        """Test creation of an AstroMinerXResource."""
        user = self._create_user(username="resource_collector")
        expedition = AstroMinerXExpedition(user_id=user.id, bet_amount=75.0)
        db.session.add(expedition)
        db.session.commit()

        resource = AstroMinerXResource(
            expedition_id=expedition.id,
            resource_name="diamond_cluster",
            value=500.0,
            collected_time=datetime.now(timezone.utc)
        )
        db.session.add(resource)
        db.session.commit()

        self.assertIsNotNone(resource.id)
        self.assertEqual(resource.expedition_id, expedition.id)
        self.assertEqual(resource.resource_name, "diamond_cluster")
        self.assertEqual(resource.value, 500.0)
        self.assertIsNotNone(resource.collected_time)
        self.assertEqual(resource.expedition, expedition)

    def test_expedition_relationships(self):
        """Test relationships between expedition, asteroids, and resources."""
        user = self._create_user(username="relationship_tester")
        expedition = AstroMinerXExpedition(user_id=user.id, bet_amount=200.0)
        db.session.add(expedition)
        db.session.commit()

        asteroid1 = AstroMinerXAsteroid(expedition_id=expedition.id, asteroid_type="gold_nugget", value=100)
        asteroid2 = AstroMinerXAsteroid(expedition_id=expedition.id, asteroid_type="empty_rock", is_empty=True)
        db.session.add_all([asteroid1, asteroid2])

        resource1 = AstroMinerXResource(expedition_id=expedition.id, resource_name="gold_nugget", value=100)
        db.session.add(resource1)
        db.session.commit()

        # Refresh expedition to load relationships
        db.session.refresh(expedition)

        self.assertEqual(len(expedition.asteroids.all()), 2)
        self.assertIn(asteroid1, expedition.asteroids)
        self.assertIn(asteroid2, expedition.asteroids)

        self.assertEqual(len(expedition.resources_collected.all()), 1)
        self.assertIn(resource1, expedition.resources_collected)

    def test_expedition_default_values(self):
        """Test default values for AstroMinerXExpedition."""
        user = self._create_user(username="default_exp_user")
        expedition = AstroMinerXExpedition(user_id=user.id, bet_amount=10.0)
        db.session.add(expedition)
        db.session.commit()

        self.assertEqual(expedition.total_value_collected, 0)
        self.assertEqual(expedition.status, "active") # Default from model definition
        self.assertIsNotNone(expedition.start_time)

    def test_asteroid_default_values(self):
        """Test default values for AstroMinerXAsteroid."""
        user = self._create_user(username="default_ast_user")
        expedition = AstroMinerXExpedition(user_id=user.id, bet_amount=10.0)
        db.session.add(expedition)
        db.session.commit()

        asteroid = AstroMinerXAsteroid(expedition_id=expedition.id, asteroid_type="unknown")
        db.session.add(asteroid)
        db.session.commit()

        self.assertFalse(asteroid.is_empty)
        self.assertFalse(asteroid.is_hazard)
        self.assertIsNone(asteroid.value)
        self.assertIsNone(asteroid.scan_time)

    def test_cascade_delete_expedition(self):
        """Test that deleting an expedition cascades to its asteroids and resources."""
        user = self._create_user(username="cascade_user")
        expedition = AstroMinerXExpedition(user_id=user.id, bet_amount=100.0)
        db.session.add(expedition)
        db.session.commit()
        exp_id = expedition.id

        asteroid = AstroMinerXAsteroid(expedition_id=exp_id, asteroid_type="test_rock")
        resource = AstroMinerXResource(expedition_id=exp_id, resource_name="test_gem", value=10)
        db.session.add_all([asteroid, resource])
        db.session.commit()
        ast_id = asteroid.id
        res_id = resource.id

        # Ensure they exist
        self.assertIsNotNone(AstroMinerXAsteroid.query.get(ast_id))
        self.assertIsNotNone(AstroMinerXResource.query.get(res_id))

        # Delete expedition
        db.session.delete(expedition)
        db.session.commit()

        self.assertIsNone(AstroMinerXExpedition.query.get(exp_id))
        self.assertIsNone(AstroMinerXAsteroid.query.get(ast_id)) # Should be deleted by cascade
        self.assertIsNone(AstroMinerXResource.query.get(res_id)) # Should be deleted by cascade

if __name__ == '__main__':
    unittest.main()
