"""Fix Classic 3x3 Seven symbol multiplier

Revision ID: fix_classic3x3_seven
Revises: classic_3x3_slot
Create Date: 2025-06-10 04:00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'fix_classic3x3_seven'
down_revision = 'classic_3x3_slot'
branch_labels = None
depends_on = None

def upgrade():
    connection = op.get_bind()
    
    # Update the Seven symbol multiplier to match gameConfig.json
    connection.execute(sa.text("""
        UPDATE slot_symbol 
        SET data = '{"value_multipliers": {"3": 200}}'::jsonb
        WHERE slot_id IN (SELECT id FROM slot WHERE short_name = 'classic3x3')
        AND symbol_internal_id = 7
    """))
    
    print("Fixed Classic 3x3 Seven symbol multiplier from 250 to 200")

def downgrade():
    connection = op.get_bind()
    
    # Revert the Seven symbol multiplier back to original
    connection.execute(sa.text("""
        UPDATE slot_symbol 
        SET data = '{"value_multipliers": {"3": 250}}'::jsonb
        WHERE slot_id IN (SELECT id FROM slot WHERE short_name = 'classic3x3')
        AND symbol_internal_id = 7
    """))