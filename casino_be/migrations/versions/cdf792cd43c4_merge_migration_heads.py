"""merge migration heads

Revision ID: cdf792cd43c4
Revises: fix_classic3x3_seven, add_active_power_ups_flower, 48c490c7769c, 4c0fb7878a54
Create Date: 2025-06-18 23:03:46.581818

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cdf792cd43c4'
down_revision = ('fix_classic3x3_seven', 'add_active_power_ups_flower', '48c490c7769c', '4c0fb7878a54')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
