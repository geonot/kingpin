"""Merge 0008 and 93adbc7a66aa into a new head

Revision ID: 4a5d8e2197b3
Revises: 0008, 93adbc7a66aa
Create Date: 2025-06-02 20:31:48.726914

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4a5d8e2197b3'
down_revision = 'b57bf8ca2042' # Was ('0008', '93adbc7a66aa'), simplifying due to missing 0008
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
