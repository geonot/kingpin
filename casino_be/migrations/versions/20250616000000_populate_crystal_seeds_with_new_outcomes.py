"""populate_crystal_seeds_with_new_outcomes

Revision ID: populate_crystal_seeds_with_new_outcomes
Revises: add_crystal_garden_models
Create Date: 2025-06-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import json # For dumping potential_outcomes

# revision identifiers, used by Alembic.
revision = 'populate_crystal_seeds_with_new_outcomes'
down_revision = 'add_crystal_garden_models' # The previous migration that created the tables
branch_labels = None
depends_on = None

# Define the table structure for CrystalSeed here for use in the migration
# This helps if the model definition changes later, the migration still works.
crystal_seed_table = sa.table(
    'crystal_seed',
    sa.column('id', sa.Integer),
    sa.column('name', sa.String),
    sa.column('cost', sa.Integer),
    sa.column('potential_outcomes', sa.JSON)
)

# Seed Definitions with refined potential_outcomes

# 1. Common Rock Seed (Refined)
common_rock_seed_outcomes = {
    "colors": {"grey": 60, "brown": 30, "dull_green": 10},
    "sizes": {
        "distribution": "weighted_ranges",
        "ranges": {
            "pebble": {"weight": 60, "min": 0.2, "max": 0.7},
            "small_rock": {"weight": 30, "min": 0.7, "max": 1.2},
            "rock": {"weight": 10, "min": 1.2, "max": 1.8}
        }
    },
    "clarities": { # Tends to be cloudy
        "distribution": "normal", "mean": 0.25, "stddev": 0.1,
        "min_clip": 0.05, "max_clip": 0.5
    },
    "special_types": {"none": 95, "faint_glow": 5} # new 'faint_glow' instead of common_glow
}

# 2. Geode Seed (Refined)
geode_seed_outcomes = {
    "colors": {"crystal_clear": 30, "amethyst_purple": 25, "citrine_yellow": 20, "rose_quartz_pink": 15, "smoky_quartz_grey": 10},
    "sizes": { # Small to medium, typical for geodes
        "distribution": "normal", "mean": 2.5, "stddev": 0.5,
        "min_clip": 1.0, "max_clip": 4.0
    },
    "clarities": { # Can vary widely
        "distribution": "uniform", "min": 0.3, "max": 0.9
    },
    "special_types": {"none": 60, "common_glow": 30, "rare_sparkle": 10} # Better chance for sparkle
}

# 3. Star Shard Seed (Refined)
star_shard_seed_outcomes = {
    "colors": {"starlight_gold": 30, "cosmic_blue": 30, "nebula_purple": 25, "comet_white": 15},
    "sizes": { # Tends to be larger
        "distribution": "weighted_ranges",
        "ranges": {
            "fragment": {"weight": 20, "min": 2.0, "max": 3.5},
            "cluster": {"weight": 50, "min": 3.5, "max": 5.5},
            "large_cluster": {"weight": 30, "min": 5.5, "max": 7.0}
        }
    },
    "clarities": { # Generally high clarity
        "distribution": "normal", "mean": 0.85, "stddev": 0.1,
        "min_clip": 0.6, "max_clip": 1.0
    },
    "special_types": {"none": 20, "common_glow": 40, "rare_sparkle": 30, "celestial_radiance": 10} # new 'celestial_radiance'
}

# 4. Shadowvein Seed (New)
shadowvein_seed_outcomes = {
    "colors": {"obsidian_black": 40, "void_purple": 30, "crimson_red": 20, "shadow_clear": 10},
    "sizes": {
        "distribution": "weighted_ranges",
        "ranges": {
            "shard": {"weight": 20, "min": 1.5, "max": 2.8},
            "core": {"weight": 60, "min": 2.8, "max": 4.2},
            "heart": {"weight": 20, "min": 4.2, "max": 5.5}
        }
    },
    "clarities": { # Often included, but can be surprisingly clear
        "distribution": "normal", "mean": 0.45, "stddev": 0.2,
        "min_clip": 0.1, "max_clip": 0.85
    },
    "special_types": {"none": 25, "common_glow": 25, "rare_sparkle": 25, "umbral_echo": 25}
}

# 5. Sunstone Seed (New)
sunstone_seed_outcomes = {
    "colors": {"sunbeam_yellow": 40, "dawn_orange": 30, "horizon_red": 20, "brilliant_white": 10},
    "sizes": {
        "distribution": "normal", "mean": 3.2, "stddev": 0.6,
        "min_clip": 1.8, "max_clip": 4.8
    },
    "clarities": { # High clarity
        "distribution": "normal", "mean": 0.8, "stddev": 0.1,
        "min_clip": 0.55, "max_clip": 1.0
    },
    "special_types": {"none": 40, "common_glow": 40, "rare_sparkle": 10,"solar_flare": 10}
}

# 6. Rivergem Seed (New)
rivergem_seed_outcomes = {
    "colors": {"aqua_blue": 30, "moss_green": 30, "pebble_grey": 25, "clear_water": 15},
    "sizes": { # Smaller, smoother
        "distribution": "weighted_ranges",
        "ranges": {
            "pebble": {"weight": 50, "min": 0.5, "max": 1.5},
            "stone": {"weight": 40, "min": 1.5, "max": 2.5},
            "gem": {"weight": 10, "min": 2.5, "max": 3.2}
        }
    },
    "clarities": { # Consistently good
        "distribution": "uniform", "min": 0.65, "max": 0.95
    },
    "special_types": {"none": 65, "common_glow": 25, "water_ripple": 10}
}

# 7. Heartwood Seed (New)
heartwood_seed_outcomes = {
    "colors": {"forest_green": 30, "rich_brown": 30, "amber_yellow": 25, "leaf_gold": 15},
    "sizes": { # Larger, resilient
        "distribution": "normal", "mean": 4.2, "stddev": 0.8,
        "min_clip": 2.5, "max_clip": 6.5
    },
    "clarities": { # Can be varied, often with character
        "distribution": "weighted_ranges",
        "ranges": {
            "included": {"weight": 40, "min": 0.4, "max": 0.65},
            "clear": {"weight": 50, "min": 0.65, "max": 0.85},
            "flawless": {"weight": 10, "min": 0.85, "max": 0.95}
        }
    },
    "special_types": {"none": 50, "common_glow": 30, "rare_sparkle": 10, "ancient_resin": 10}
}

# Fallback/Basic seed for testing if needed (can be removed if not essential for prod seeding)
basic_seed_outcomes = {
    "colors": {"test_red": 50, "test_blue": 50},
    "sizes": {"distribution": "uniform", "min": 1, "max": 3},
    "clarities": {"distribution": "uniform", "min": 0.1, "max": 0.9},
    "special_types": {"none": 90, "test_glow": 10}
}


def upgrade():
    seed_data = [
        {'id': 1, 'name': 'Common Rock Seed', 'cost': 5, 'potential_outcomes': json.dumps(common_rock_seed_outcomes)},
        {'id': 2, 'name': 'Geode Seed', 'cost': 20, 'potential_outcomes': json.dumps(geode_seed_outcomes)},
        {'id': 3, 'name': 'Star Shard Seed', 'cost': 50, 'potential_outcomes': json.dumps(star_shard_seed_outcomes)},
        {'id': 4, 'name': 'Shadowvein Seed', 'cost': 75, 'potential_outcomes': json.dumps(shadowvein_seed_outcomes)},
        {'id': 5, 'name': 'Sunstone Seed', 'cost': 60, 'potential_outcomes': json.dumps(sunstone_seed_outcomes)},
        {'id': 6, 'name': 'Rivergem Seed', 'cost': 30, 'potential_outcomes': json.dumps(rivergem_seed_outcomes)},
        {'id': 7, 'name': 'Heartwood Seed', 'cost': 40, 'potential_outcomes': json.dumps(heartwood_seed_outcomes)},
        # Keeping Basic Test Seed for now, can be removed if not needed. Ensure ID is unique if kept.
        {'id': 99, 'name': 'Basic Test Seed', 'cost': 1, 'potential_outcomes': json.dumps(basic_seed_outcomes)}
    ]

    # To handle re-runs of migration or existing data, we can delete existing seeds by name first
    # Or use a more sophisticated upsert if the DB and SQLAlchemy version support it easily in Alembic.
    # For simplicity, let's delete by known names first, then insert.
    # This makes the migration re-runnable for these specific seeds.

    seed_names_to_delete = [s['name'] for s in seed_data]
    op.execute(
        crystal_seed_table.delete().where(crystal_seed_table.c.name.in_(seed_names_to_delete))
    )

    op.bulk_insert(crystal_seed_table, seed_data)


def downgrade():
    # Delete only the seeds added/modified in this migration.
    seed_names = [
        'Common Rock Seed', 'Geode Seed', 'Star Shard Seed',
        'Shadowvein Seed', 'Sunstone Seed', 'Rivergem Seed', 'Heartwood Seed',
        'Basic Test Seed' # If it was added/managed by this migration
    ]
    # Create a string like "'Name1', 'Name2', ..." for the SQL IN clause
    seed_names_sql_list = ", ".join([f"'{name}'" for name in seed_names])
    op.execute(f"DELETE FROM crystal_seed WHERE name IN ({seed_names_sql_list})")
