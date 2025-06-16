"""add_signature_to_codex_entry

Revision ID: add_signature_to_codex_entry
Revises: populate_crystal_seeds_with_new_outcomes
Create Date: 2025-06-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_signature_to_codex_entry'
down_revision = 'populate_crystal_seeds_with_new_outcomes'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('crystal_codex_entry', schema=None) as batch_op:
        batch_op.add_column(sa.Column('signature', sa.String(length=255), nullable=True)) # Will be made non-nullable after populating existing rows if necessary
        batch_op.create_index('ix_crystal_codex_entry_signature', ['signature'], unique=False) # Index for querying
        # Initially, signature can be nullable to handle existing rows.
        # For new entries, the application logic should ensure it's populated.
        # A unique constraint will be added separately if all existing data can conform.
        # For now, let's assume we want it unique for new entries and enforce via app logic or make it non-nullable + unique later.
        # If starting fresh or can ensure signatures are generated for existing entries:
        batch_op.create_unique_constraint('uq_user_signature', ['user_id', 'signature'])

    # If there's existing data, a data migration step would be needed here to populate the 'signature'
    # for all existing CrystalCodexEntry rows before making the column non-nullable
    # and strictly enforcing the unique constraint at DB level for all rows.
    # For this exercise, we assume new entries will have signatures and the constraint is desired.
    # Making it nullable=False now would fail if there are existing rows without it.
    # op.alter_column('crystal_codex_entry', 'signature', existing_type=sa.String(length=255), nullable=False)


def downgrade():
    with op.batch_alter_table('crystal_codex_entry', schema=None) as batch_op:
        batch_op.drop_constraint('uq_user_signature', type_='unique')
        batch_op.drop_index('ix_crystal_codex_entry_signature')
        batch_op.drop_column('signature')
