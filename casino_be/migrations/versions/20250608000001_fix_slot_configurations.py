"""Fix slot configurations to use modern value_multipliers format

Revision ID: fix_slot_configs
Revises: populate_slots
Create Date: 2025-06-08 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import Integer, String, Float, Boolean, BigInteger, JSON, Text, DateTime
from datetime import datetime, timezone

# revision identifiers, used by Alembic.
revision = 'fix_slot_configs'
down_revision = 'populate_slots'
branch_labels = None
depends_on = None

def upgrade():
    # Define table structure for updates
    slot_table = table('slot',
        column('id', Integer),
        column('reel_configurations', JSON)
    )
    
    slot_symbol_table = table('slot_symbol',
        column('id', Integer),
        column('slot_id', Integer),
        column('symbol_internal_id', Integer),
        column('data', JSON)
    )

    # Update Slot 1 (Hack) - Remove old payouts array and add value_multipliers to symbols
    hack_reel_config = {
        'paylines': [
            {'id': 'payline_1', 'coords': [[0,0],[0,1],[0,2],[0,3],[0,4]]},
            {'id': 'payline_2', 'coords': [[1,0],[1,1],[1,2],[1,3],[1,4]]},
            {'id': 'payline_3', 'coords': [[2,0],[2,1],[2,2],[2,3],[2,4]]},
            {'id': 'payline_4', 'coords': [[0,0],[1,1],[2,2],[1,3],[0,4]]},
            {'id': 'payline_5', 'coords': [[2,0],[1,1],[0,2],[1,3],[2,4]]},
            {'id': 'payline_6', 'coords': [[0,0],[0,1],[1,2],[2,3],[2,4]]},
            {'id': 'payline_7', 'coords': [[2,0],[2,1],[1,2],[0,3],[0,4]]},
            {'id': 'payline_8', 'coords': [[1,0],[0,1],[0,2],[0,3],[1,4]]},
            {'id': 'payline_9', 'coords': [[1,0],[2,1],[2,2],[2,3],[1,4]]},
            {'id': 'payline_10', 'coords': [[0,0],[1,1],[0,2],[1,3],[0,4]]}
        ],
        'reel_strips': [
            [1,2,3,4,5,6,7,8,9, 1,2,3,1,4,5,1,2,3,4,5,6,7,8,9], # Reel 1
            [1,2,3,4,5,6,7,8,9, 1,3,6,7,8,1,2,3,4,5,6,7,8,9], # Reel 2
            [1,2,3,4,5,6,7,8,9, 1,2,4,5,9,8,1,2,3,4,5,6,7,8], # Reel 3
            [1,2,3,4,5,6,7,8,9, 1,3,6,7,8,1,2,3,4,5,6,7,8,9], # Reel 4
            [1,2,3,4,5,6,7,8,9, 2,4,5,8,9,1,2,3,4,5,6,7,8,9]  # Reel 5
        ]
    }

    # Update Slot 1 symbols with value_multipliers
    op.execute(
        slot_symbol_table.update()
        .where(slot_symbol_table.c.slot_id == 1)
        .where(slot_symbol_table.c.symbol_internal_id == 1)
        .values(data={'value_multipliers': {'3': 0.5, '4': 1, '5': 2}})
    )
    
    op.execute(
        slot_symbol_table.update()
        .where(slot_symbol_table.c.slot_id == 1)
        .where(slot_symbol_table.c.symbol_internal_id == 2)
        .values(data={'value_multipliers': {'3': 0.5, '4': 1, '5': 2}})
    )
    
    op.execute(
        slot_symbol_table.update()
        .where(slot_symbol_table.c.slot_id == 1)
        .where(slot_symbol_table.c.symbol_internal_id == 3)
        .values(data={'value_multipliers': {'3': 0.7, '4': 1.5, '5': 3}})
    )
    
    op.execute(
        slot_symbol_table.update()
        .where(slot_symbol_table.c.slot_id == 1)
        .where(slot_symbol_table.c.symbol_internal_id == 4)
        .values(data={'value_multipliers': {'3': 0.7, '4': 1.5, '5': 3}})
    )
    
    op.execute(
        slot_symbol_table.update()
        .where(slot_symbol_table.c.slot_id == 1)
        .where(slot_symbol_table.c.symbol_internal_id == 5)
        .values(data={'value_multipliers': {'3': 1, '4': 2.5, '5': 5}})
    )
    
    op.execute(
        slot_symbol_table.update()
        .where(slot_symbol_table.c.slot_id == 1)
        .where(slot_symbol_table.c.symbol_internal_id == 6)
        .values(data={'value_multipliers': {'3': 1, '4': 2.5, '5': 5}})
    )
    
    op.execute(
        slot_symbol_table.update()
        .where(slot_symbol_table.c.slot_id == 1)
        .where(slot_symbol_table.c.symbol_internal_id == 7)
        .values(data={'value_multipliers': {'3': 1.5, '4': 5, '5': 10}})
    )
    
    op.execute(
        slot_symbol_table.update()
        .where(slot_symbol_table.c.slot_id == 1)
        .where(slot_symbol_table.c.symbol_internal_id == 8)
        .values(data={'scatter_payouts': {'3': 2, '4': 10, '5': 50}})
    )
    
    op.execute(
        slot_symbol_table.update()
        .where(slot_symbol_table.c.slot_id == 1)
        .where(slot_symbol_table.c.symbol_internal_id == 9)
        .values(data={'is_wild': True})
    )

    # Update Slot 1 reel configuration (remove old payouts array)
    op.execute(
        slot_table.update()
        .where(slot_table.c.id == 1)
        .values(reel_configurations=hack_reel_config)
    )

    # Update other slots with similar fixes...
    # (Similar updates for slots 2, 3, 4 would go here)


def downgrade():
    # Restore old payouts format if needed
    pass