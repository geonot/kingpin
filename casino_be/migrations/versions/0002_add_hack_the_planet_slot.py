"""Add hack the planet slot data"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone # Use timezone
from sqlalchemy.dialects.postgresql import JSONB # For JSONB data type

# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001' # Depends on initial migration
branch_labels = None
depends_on = None

# Define table representation for data insertion
slot_table = sa.table('slot',
    sa.column('id', sa.Integer),
    sa.column('name', sa.String),
    sa.column('description', sa.Text),
    sa.column('num_rows', sa.Integer),
    sa.column('num_columns', sa.Integer),
    sa.column('num_symbols', sa.Integer),
    sa.column('wild_symbol_id', sa.Integer),     # Use new column name convention
    sa.column('scatter_symbol_id', sa.Integer), # Use new column name convention
    sa.column('bonus_type', sa.String),
    sa.column('bonus_subtype', sa.String),
    sa.column('bonus_multiplier', sa.Float),    # Use Float for multiplier
    sa.column('bonus_spins_awarded', sa.Integer),# Use new column name
    sa.column('bonus_spins_trigger_count', sa.Integer), # Use new column name
    sa.column('short_name', sa.String),
    sa.column('asset_directory', sa.String),
    sa.column('is_active', sa.Boolean),
    sa.column('created_at', sa.DateTime(timezone=True)) # Use timezone-aware DateTime
)

# Define table representation for slot symbols
slot_symbol_table = sa.table('slot_symbol',
    sa.column('id', sa.Integer),
    sa.column('slot_id', sa.Integer),
    sa.column('symbol_internal_id', sa.Integer),
    sa.column('name', sa.String),
    sa.column('img_link', sa.String),
    sa.column('value_multiplier', sa.Float),
    sa.column('data', JSONB),
    sa.column('created_at', sa.DateTime(timezone=True))
)

# Define table representation for slot bets
slot_bet_table = sa.table('slot_bet',
    sa.column('id', sa.Integer),
    sa.column('slot_id', sa.Integer),
    sa.column('bet_amount', sa.BigInteger),
    sa.column('created_at', sa.DateTime(timezone=True))
)

def upgrade():
    # Get current time in UTC
    now_utc = datetime.now(timezone.utc)

    # Insert the Hack the Planet slot entry
    op.bulk_insert(slot_table,
        [
            {
                'id': 1, # Ensure ID is unique
                'name': 'Hack the Planet',
                'description': 'Hack the Planet - A cyber-themed slot adventure.', # Improved description
                'num_rows': 3,
                'num_columns': 5,
                'num_symbols': 9, # Matches gameConfig
                'wild_symbol_id': 9, # Matches gameConfig (symbol_wild)
                'scatter_symbol_id': 8, # Matches gameConfig (symbol_scatter)
                'bonus_type': 'free_spins', # Changed from standard
                'bonus_subtype': 'standard', # Keep standard or specify?
                'bonus_multiplier': 3.0, # Bonus round multiplier
                'bonus_spins_trigger_count': 3, # Default triggers
                'bonus_spins_awarded': 10, # Number of spins awarded
                'short_name': 'hack', # For path /slot1/
                'asset_directory': 'slot1', # Matches path
                'is_active': True,
                'created_at': now_utc
            }
        ]
    )
    
    # Insert the Hack the Planet slot symbols
    op.bulk_insert(slot_symbol_table,
        [
            {
                'slot_id': 1,
                'symbol_internal_id': 1,
                'name': 'Symbol 1',
                'img_link': '/slot1/sprite_0.png',
                'value_multiplier': 1.5,
                'data': None,
                'created_at': now_utc
            },
            {
                'slot_id': 1,
                'symbol_internal_id': 2,
                'name': 'Symbol 2',
                'img_link': '/slot1/sprite_1.png',
                'value_multiplier': 2.0,
                'data': None,
                'created_at': now_utc
            },
            {
                'slot_id': 1,
                'symbol_internal_id': 3,
                'name': 'Symbol 3',
                'img_link': '/slot1/sprite_2.png',
                'value_multiplier': 2.5,
                'data': None,
                'created_at': now_utc
            },
            {
                'slot_id': 1,
                'symbol_internal_id': 4,
                'name': 'Symbol 4',
                'img_link': '/slot1/sprite_3.png',
                'value_multiplier': 3.0,
                'data': None,
                'created_at': now_utc
            },
            {
                'slot_id': 1,
                'symbol_internal_id': 5,
                'name': 'Symbol 5',
                'img_link': '/slot1/sprite_4.png',
                'value_multiplier': 5.0,
                'data': None,
                'created_at': now_utc
            },
            {
                'slot_id': 1,
                'symbol_internal_id': 6,
                'name': 'Symbol 6',
                'img_link': '/slot1/sprite_5.png',
                'value_multiplier': 10.0,
                'data': None,
                'created_at': now_utc
            },
            {
                'slot_id': 1,
                'symbol_internal_id': 7,
                'name': 'Symbol 7',
                'img_link': '/slot1/sprite_6.png',
                'value_multiplier': 20.0,
                'data': None,
                'created_at': now_utc
            },
            {
                'slot_id': 1,
                'symbol_internal_id': 8,
                'name': 'Scatter',
                'img_link': '/slot1/sprite_7.png',
                'value_multiplier': None,
                'data': None,
                'created_at': now_utc
            },
            {
                'slot_id': 1,
                'symbol_internal_id': 9,
                'name': 'Wild',
                'img_link': '/slot1/sprite_8.png',
                'value_multiplier': None,
                'data': None,
                'created_at': now_utc
            }
        ]
    )
    
    # Insert the Hack the Planet slot bet options
    op.bulk_insert(slot_bet_table,
        [
            {'slot_id': 1, 'bet_amount': 10 * 100000000, 'created_at': now_utc},  # 10 BTC in satoshis
            {'slot_id': 1, 'bet_amount': 20 * 100000000, 'created_at': now_utc},  # 20 BTC in satoshis
            {'slot_id': 1, 'bet_amount': 50 * 100000000, 'created_at': now_utc},  # 50 BTC in satoshis
            {'slot_id': 1, 'bet_amount': 100 * 100000000, 'created_at': now_utc}, # 100 BTC in satoshis
            {'slot_id': 1, 'bet_amount': 200 * 100000000, 'created_at': now_utc}, # 200 BTC in satoshis
            {'slot_id': 1, 'bet_amount': 500 * 100000000, 'created_at': now_utc}  # 500 BTC in satoshis
        ]
    )

def downgrade():
    # Delete the inserted Hack the Planet slot entry and related data
    op.execute(
        slot_bet_table.delete().where(slot_bet_table.c.slot_id == 1)
    )
    op.execute(
        slot_symbol_table.delete().where(slot_symbol_table.c.slot_id == 1)
    )
    op.execute(
        slot_table.delete().where(slot_table.c.id == 1)
    )

