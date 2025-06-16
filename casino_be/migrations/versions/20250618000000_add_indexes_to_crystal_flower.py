"""add_indexes_to_crystal_flower

Revision ID: add_indexes_to_crystal_flower
Revises: add_signature_to_codex_entry
Create Date: 2025-06-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_indexes_to_crystal_flower'
down_revision = 'add_signature_to_codex_entry'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('crystal_flower', schema=None) as batch_op:
        # Index for the plant_seed query
        batch_op.create_index('ix_crystal_flower_garden_plot_position', ['player_garden_id', 'position_x', 'position_y'], unique=False)

        # Explicit indexes for foreign keys, if not already created by unique constraints or primary key status
        # Some DBs create these automatically for FKs, but explicit is safer for cross-DB compatibility / clarity.
        # Check your DB to see if these are redundant. If player_garden_id is part of another specific index (like the one above),
        # a separate index on just player_garden_id might be less critical but can still help other queries.
        batch_op.create_index('ix_crystal_flower_player_garden_id', ['player_garden_id'], unique=False)
        batch_op.create_index('ix_crystal_flower_crystal_seed_id', ['crystal_seed_id'], unique=False)
        batch_op.create_index('ix_crystal_flower_user_id', ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('crystal_flower', schema=None) as batch_op:
        batch_op.drop_index('ix_crystal_flower_garden_plot_position')
        batch_op.drop_index('ix_crystal_flower_player_garden_id')
        batch_op.drop_index('ix_crystal_flower_crystal_seed_id')
        batch_op.drop_index('ix_crystal_flower_user_id')
