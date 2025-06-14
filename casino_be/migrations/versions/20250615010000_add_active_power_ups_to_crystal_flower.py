"""add_active_power_ups_to_crystal_flower

Revision ID: add_active_power_ups_flower
Revises: add_crystal_garden_models
Create Date: 2025-06-15 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.types import JSON # Using generic JSON for broader compatibility


# revision identifiers, used by Alembic.
revision = 'add_active_power_ups_flower'
down_revision = 'add_crystal_garden_models' # From the manually created Crystal Garden schema migration
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('crystal_flower',
                  sa.Column('active_power_ups',
                            JSON,
                            nullable=True,
                            server_default=sa.text("'[]'"))) # Default to an empty JSON array string for SQL side

def downgrade():
    op.drop_column('crystal_flower', 'active_power_ups')
