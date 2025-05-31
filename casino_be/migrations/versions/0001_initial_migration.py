"""Initial migration reflecting original table structure (potentially with adjustments)"""
# Note: This baseline might need adjustment if the very first 'real' state was different.
# It should create tables compatible with the refactored models.py

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql # Import postgresql for JSONB if used

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None # This is the first migration
branch_labels = None
depends_on = None

def upgrade():
    print("Applying initial migration: Creating core tables...")

    # --- user table ---
    op.create_table('user',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('password', sa.String(length=128), nullable=False),
        sa.Column('balance', sa.BigInteger(), nullable=False, server_default='0'), # Use BigInteger, server_default
        sa.Column('deposit_wallet_address', sa.String(length=256), nullable=False),
        sa.Column('deposit_wallet_private_key', sa.String(length=256), nullable=False), # Insecure
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'), # Added is_active
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), # Use timezone
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True), # Added last_login_at
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('deposit_wallet_address') # Added unique constraint
    )
    op.create_index(op.f('ix_user_balance'), 'user', ['balance'], unique=False)
    op.create_index(op.f('ix_user_email'), 'user', ['email'], unique=True)
    op.create_index(op.f('ix_user_username'), 'user', ['username'], unique=True)
    print("Created 'user' table.")

    # --- slot table ---
    op.create_table('slot',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True), # Allow null
        sa.Column('num_rows', sa.Integer(), nullable=False),
        sa.Column('num_columns', sa.Integer(), nullable=False),
        sa.Column('num_symbols', sa.Integer(), nullable=False),
        sa.Column('wild_symbol_id', sa.Integer(), nullable=True), # Changed name
        sa.Column('scatter_symbol_id', sa.Integer(), nullable=True), # Changed name
        sa.Column('bonus_type', sa.String(length=50), nullable=True), # Allow null
        sa.Column('bonus_subtype', sa.String(length=50), nullable=True), # Allow null
        sa.Column('bonus_multiplier', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('bonus_spins_trigger_count', sa.Integer(), nullable=False, server_default='3'), # Added
        sa.Column('bonus_spins_awarded', sa.Integer(), nullable=False, server_default='10'), # Renamed
        sa.Column('short_name', sa.String(length=50), nullable=False),
        sa.Column('asset_directory', sa.String(length=100), nullable=False, server_default=''),
        sa.Column('rtp', sa.Float(), nullable=True), # Added
        sa.Column('volatility', sa.String(length=20), nullable=True), # Added
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'), # Added
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), # Use timezone
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('short_name')
    )
    op.create_index(op.f('ix_slot_is_active'), 'slot', ['is_active'], unique=False)
    print("Created 'slot' table.")


    # --- slot_symbol table ---
    op.create_table('slot_symbol',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slot_id', sa.Integer(), nullable=False),
        sa.Column('symbol_internal_id', sa.Integer(), nullable=False), # Added
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('img_link', sa.String(length=256), nullable=False),
        sa.Column('value_multiplier', sa.Float(), nullable=True), # Renamed, allow null
        # Removed is_wild, is_scatter
        sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True), # Added, use JSONB
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), # Use timezone
        sa.ForeignKeyConstraint(['slot_id'], ['slot.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_slot_symbol_slot_id'), 'slot_symbol', ['slot_id'], unique=False)
    op.create_index('ix_slot_symbol_slot_id_internal_id', 'slot_symbol', ['slot_id', 'symbol_internal_id'], unique=True) # Added unique index
    print("Created 'slot_symbol' table.")

    # --- Add FK constraints for wild/scatter in slot table (after slot_symbol is created) ---
    # Note: FKs to slot_symbol.id might be complex if symbol IDs aren't stable.
    # Consider FK to slot_symbol.symbol_internal_id composite with slot_id if needed, but nullable simple FK is easier.
    # op.create_foreign_key('fk_slot_wild_symbol', 'slot', 'slot_symbol', ['wild_symbol_id'], ['id'])
    # op.create_foreign_key('fk_slot_scatter_symbol', 'slot', 'slot_symbol', ['scatter_symbol_id'], ['id'])


    # --- game_session table ---
    op.create_table('game_session',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('slot_id', sa.Integer(), nullable=False),
        sa.Column('bonus_active', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('bonus_spins_remaining', sa.Integer(), nullable=False, server_default='0'), # Renamed
        sa.Column('bonus_multiplier', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('amount_wagered', sa.BigInteger(), nullable=False, server_default='0'), # BigInt
        sa.Column('amount_won', sa.BigInteger(), nullable=False, server_default='0'), # BigInt
        # Removed spin_amount column
        sa.Column('num_spins', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('session_start', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), # Use timezone
        sa.Column('session_end', sa.DateTime(timezone=True), nullable=True), # Use timezone
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), # Use timezone
        sa.ForeignKeyConstraint(['slot_id'], ['slot.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_game_session_session_end'), 'game_session', ['session_end'], unique=False)
    op.create_index(op.f('ix_game_session_slot_id'), 'game_session', ['slot_id'], unique=False)
    op.create_index(op.f('ix_game_session_user_id'), 'game_session', ['user_id'], unique=False)
    print("Created 'game_session' table.")

    # --- slot_spin table ---
    op.create_table('slot_spin',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('game_session_id', sa.Integer(), nullable=False),
        sa.Column('spin_result', postgresql.JSONB(astext_type=sa.Text()), nullable=False), # Use JSONB
        sa.Column('win_amount', sa.BigInteger(), nullable=False), # BigInt
        sa.Column('bet_amount', sa.BigInteger(), nullable=False), # BigInt
        sa.Column('is_bonus_spin', sa.Boolean(), nullable=False, server_default='false'), # Added
        sa.Column('spin_time', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), # Use timezone
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), # Use timezone
        sa.ForeignKeyConstraint(['game_session_id'], ['game_session.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_slot_spin_game_session_id'), 'slot_spin', ['game_session_id'], unique=False)
    op.create_index(op.f('ix_slot_spin_spin_time'), 'slot_spin', ['spin_time'], unique=False) # Added index
    print("Created 'slot_spin' table.")


    # --- transaction table ---
    op.create_table('transaction',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.BigInteger(), nullable=False), # BigInt
        sa.Column('transaction_type', sa.String(length=20), nullable=False), # Increased length
        sa.Column('status', sa.String(length=15), nullable=False, server_default='completed'), # Increased length
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True), # Added, use JSONB
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), # Use timezone
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transaction_created_at'), 'transaction', ['created_at'], unique=False)
    op.create_index(op.f('ix_transaction_status'), 'transaction', ['status'], unique=False)
    op.create_index(op.f('ix_transaction_transaction_type'), 'transaction', ['transaction_type'], unique=False)
    op.create_index(op.f('ix_transaction_user_id'), 'transaction', ['user_id'], unique=False)
    print("Created 'transaction' table.")


    # --- bonus_code table ---
    op.create_table('bonus_code',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code_id', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True), # Added
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('subtype', sa.String(length=50), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False), # Keep float for percentage/fixed handling
        sa.Column('max_uses', sa.Integer(), nullable=True), # Added
        sa.Column('uses_remaining', sa.Integer(), nullable=True), # Added
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True), # Added, use timezone
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'), # Added
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), # Use timezone
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code_id')
    )
    op.create_index(op.f('ix_bonus_code_code_id'), 'bonus_code', ['code_id'], unique=True)
    op.create_index(op.f('ix_bonus_code_is_active'), 'bonus_code', ['is_active'], unique=False)
    print("Created 'bonus_code' table.")


    # --- slot_bet table ---
    op.create_table('slot_bet',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slot_id', sa.Integer(), nullable=False),
        sa.Column('bet_amount', sa.BigInteger(), nullable=False), # BigInt
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), # Use timezone
        sa.ForeignKeyConstraint(['slot_id'], ['slot.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_slot_bet_slot_id'), 'slot_bet', ['slot_id'], unique=False)
    op.create_index('ix_slot_bet_slot_id_bet_amount', 'slot_bet', ['slot_id', 'bet_amount'], unique=True) # Added unique index
    print("Created 'slot_bet' table.")


    # --- token_blacklist table ---
    op.create_table('token_blacklist',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('jti', sa.String(length=36), nullable=False), # UUID length
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), # Use timezone
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False), # Added expiry
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_token_blacklist_expires_at'), 'token_blacklist', ['expires_at'], unique=False) # Index expiry
    op.create_index(op.f('ix_token_blacklist_jti'), 'token_blacklist', ['jti'], unique=True) # JTI must be unique
    print("Created 'token_blacklist' table.")

    # --- Remove old tables/indexes from original 0001 if they are no longer used ---
    # Example: If 'match', 'slot_payline', 'user_bonus', etc. existed before and are removed now.
    # op.drop_table('match')
    # op.drop_table('slot_payout')
    # op.drop_table('user_bonus')
    # op.drop_table('slot_reel_strip')
    # op.drop_table('slot_payline')
    print("Initial migration finished.")


def downgrade():
    print("Reverting initial migration: Dropping all tables...")
    # Drop tables in reverse order of creation, handling dependencies
    op.drop_index(op.f('ix_token_blacklist_jti'), table_name='token_blacklist')
    op.drop_index(op.f('ix_token_blacklist_expires_at'), table_name='token_blacklist')
    op.drop_table('token_blacklist')
    print("Dropped 'token_blacklist' table.")

    op.drop_index('ix_slot_bet_slot_id_bet_amount', table_name='slot_bet')
    op.drop_index(op.f('ix_slot_bet_slot_id'), table_name='slot_bet')
    op.drop_table('slot_bet')
    print("Dropped 'slot_bet' table.")

    op.drop_index(op.f('ix_bonus_code_is_active'), table_name='bonus_code')
    op.drop_index(op.f('ix_bonus_code_code_id'), table_name='bonus_code')
    op.drop_table('bonus_code')
    print("Dropped 'bonus_code' table.")

    op.drop_index(op.f('ix_transaction_user_id'), table_name='transaction')
    op.drop_index(op.f('ix_transaction_transaction_type'), table_name='transaction')
    op.drop_index(op.f('ix_transaction_status'), table_name='transaction')
    op.drop_index(op.f('ix_transaction_created_at'), table_name='transaction')
    op.drop_table('transaction')
    print("Dropped 'transaction' table.")

    op.drop_index(op.f('ix_slot_spin_spin_time'), table_name='slot_spin')
    op.drop_index(op.f('ix_slot_spin_game_session_id'), table_name='slot_spin')
    op.drop_table('slot_spin')
    print("Dropped 'slot_spin' table.")

    op.drop_index(op.f('ix_game_session_user_id'), table_name='game_session')
    op.drop_index(op.f('ix_game_session_slot_id'), table_name='game_session')
    op.drop_index(op.f('ix_game_session_session_end'), table_name='game_session')
    op.drop_table('game_session')
    print("Dropped 'game_session' table.")

    # Drop FK constraints before dropping referenced table
    # op.drop_constraint('fk_slot_wild_symbol', 'slot', type_='foreignkey')
    # op.drop_constraint('fk_slot_scatter_symbol', 'slot', type_='foreignkey')

    op.drop_index('ix_slot_symbol_slot_id_internal_id', table_name='slot_symbol')
    op.drop_index(op.f('ix_slot_symbol_slot_id'), table_name='slot_symbol')
    op.drop_table('slot_symbol')
    print("Dropped 'slot_symbol' table.")

    op.drop_index(op.f('ix_slot_is_active'), table_name='slot')
    op.drop_table('slot')
    print("Dropped 'slot' table.")

    op.drop_index(op.f('ix_user_username'), table_name='user')
    op.drop_index(op.f('ix_user_email'), table_name='user')
    op.drop_index(op.f('ix_user_balance'), table_name='user')
    op.drop_table('user')
    print("Dropped 'user' table.")

    print("Finished reverting initial migration.")

