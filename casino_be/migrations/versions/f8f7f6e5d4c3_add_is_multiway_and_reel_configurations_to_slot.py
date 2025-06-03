"""Add is_multiway and reel_configurations to Slot model

Revision ID: f8f7f6e5d4c3
Revises: e19c416cd61b
Create Date: 2024-07-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8f7f6e5d4c3'
down_revision = 'e19c416cd61b'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('slot', sa.Column('is_multiway', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('slot', sa.Column('reel_configurations', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('slot', 'reel_configurations')
    op.drop_column('slot', 'is_multiway')
