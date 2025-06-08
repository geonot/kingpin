"""Consolidated migration for all casino models

Revision ID: consolidated_models
Revises: 
Create Date: 2025-06-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'consolidated_models'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create user table
    op.create_table('user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=50), nullable=False),
    sa.Column('email', sa.String(length=120), nullable=False),
    sa.Column('password', sa.String(length=255), nullable=False),
    sa.Column('balance', sa.BigInteger(), nullable=False),
    sa.Column('deposit_wallet_address', sa.String(length=255), nullable=True),
    sa.Column('is_admin', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('deposit_wallet_address'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('username')
    )
    op.create_index(op.f('ix_user_balance'), 'user', ['balance'], unique=False)
    op.create_index(op.f('ix_user_deposit_wallet_address'), 'user', ['deposit_wallet_address'], unique=False)
    op.create_index(op.f('ix_user_email'), 'user', ['email'], unique=False)
    op.create_index(op.f('ix_user_is_active'), 'user', ['is_active'], unique=False)
    op.create_index(op.f('ix_user_is_admin'), 'user', ['is_admin'], unique=False)
    op.create_index(op.f('ix_user_username'), 'user', ['username'], unique=False)
    
    # Create bonus_code table
    op.create_table('bonus_code',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code_id', sa.String(length=50), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('type', sa.String(length=50), nullable=False),
    sa.Column('subtype', sa.String(length=50), nullable=False),
    sa.Column('amount', sa.Float(), nullable=True),
    sa.Column('amount_sats', sa.BigInteger(), nullable=True),
    sa.Column('max_uses', sa.Integer(), nullable=True),
    sa.Column('uses_remaining', sa.Integer(), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('wagering_requirement_multiplier', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code_id')
    )
    op.create_index(op.f('ix_bonus_code_code_id'), 'bonus_code', ['code_id'], unique=False)
    op.create_index(op.f('ix_bonus_code_is_active'), 'bonus_code', ['is_active'], unique=False)
    op.create_index(op.f('ix_bonus_code_subtype'), 'bonus_code', ['subtype'], unique=False)
    op.create_index(op.f('ix_bonus_code_type'), 'bonus_code', ['type'], unique=False)
    
    # Create slot table
    op.create_table('slot',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('num_rows', sa.Integer(), nullable=False),
    sa.Column('num_columns', sa.Integer(), nullable=False),
    sa.Column('num_symbols', sa.Integer(), nullable=False),
    sa.Column('wild_symbol_id', sa.Integer(), nullable=True),
    sa.Column('scatter_symbol_id', sa.Integer(), nullable=True),
    sa.Column('bonus_type', sa.String(length=50), nullable=True),
    sa.Column('bonus_subtype', sa.String(length=50), nullable=True),
    sa.Column('bonus_multiplier', sa.Float(), nullable=False),
    sa.Column('bonus_spins_trigger_count', sa.Integer(), nullable=False),
    sa.Column('bonus_spins_awarded', sa.Integer(), nullable=False),
    sa.Column('short_name', sa.String(length=50), nullable=False),
    sa.Column('asset_directory', sa.String(length=255), nullable=False),
    sa.Column('rtp', sa.Float(), nullable=False),
    sa.Column('volatility', sa.String(length=20), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_multiway', sa.Boolean(), nullable=False),
    sa.Column('reel_configurations', sa.JSON(), nullable=True),
    sa.Column('is_cascading', sa.Boolean(), nullable=False),
    sa.Column('cascade_type', sa.String(length=50), nullable=True),
    sa.Column('min_symbols_to_match', sa.Integer(), nullable=True),
    sa.Column('win_multipliers', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_slot_is_active'), 'slot', ['is_active'], unique=False)
    
    # Create blackjack_table table
    op.create_table('blackjack_table',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=True),
    sa.Column('min_bet', sa.BigInteger(), nullable=False),
    sa.Column('max_bet', sa.BigInteger(), nullable=False),
    sa.Column('deck_count', sa.Integer(), nullable=False),
    sa.Column('rules', sa.JSON(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    
    # Create poker_table table
    op.create_table('poker_table',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('game_type', sa.String(length=50), nullable=False),
    sa.Column('limit_type', sa.String(length=50), nullable=False),
    sa.Column('small_blind', sa.BigInteger(), nullable=False),
    sa.Column('big_blind', sa.BigInteger(), nullable=False),
    sa.Column('min_buy_in', sa.BigInteger(), nullable=False),
    sa.Column('max_buy_in', sa.BigInteger(), nullable=False),
    sa.Column('max_seats', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('rake_percentage', sa.Numeric(precision=5, scale=4), nullable=False),
    sa.Column('max_rake_sats', sa.BigInteger(), nullable=False),
    sa.Column('current_dealer_seat_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_poker_table_is_active'), 'poker_table', ['is_active'], unique=False)
    
    # Create baccarat_table table
    op.create_table('baccarat_table',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('min_bet', sa.BigInteger(), nullable=False),
    sa.Column('max_bet', sa.BigInteger(), nullable=False),
    sa.Column('max_tie_bet', sa.BigInteger(), nullable=False),
    sa.Column('commission_rate', sa.Numeric(precision=5, scale=4), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_baccarat_table_is_active'), 'baccarat_table', ['is_active'], unique=False)
    
    # Create spacecrash_game table
    op.create_table('spacecrash_game',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('server_seed', sa.String(length=255), nullable=False),
    sa.Column('client_seed', sa.String(length=255), nullable=True),
    sa.Column('nonce', sa.Integer(), nullable=False),
    sa.Column('crash_point', sa.Float(), nullable=True),
    sa.Column('public_seed', sa.String(length=255), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('game_start_time', sa.DateTime(timezone=True), nullable=True),
    sa.Column('game_end_time', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_spacecrash_game_status'), 'spacecrash_game', ['status'], unique=False)
    
    # Create token_blacklist table
    op.create_table('token_blacklist',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('jti', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('jti')
    )
    op.create_index(op.f('ix_token_blacklist_jti'), 'token_blacklist', ['jti'], unique=False)
    
    # Create game_session table
    op.create_table('game_session',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('slot_id', sa.Integer(), nullable=True),
    sa.Column('table_id', sa.Integer(), nullable=True),
    sa.Column('poker_table_id', sa.Integer(), nullable=True),
    sa.Column('baccarat_table_id', sa.Integer(), nullable=True),
    sa.Column('game_type', sa.String(length=50), nullable=False),
    sa.Column('bonus_active', sa.Boolean(), nullable=False),
    sa.Column('bonus_spins_remaining', sa.Integer(), nullable=False),
    sa.Column('bonus_multiplier', sa.Float(), nullable=False),
    sa.Column('amount_wagered', sa.BigInteger(), nullable=False),
    sa.Column('amount_won', sa.BigInteger(), nullable=False),
    sa.Column('num_spins', sa.Integer(), nullable=False),
    sa.Column('session_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('session_end', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['baccarat_table_id'], ['baccarat_table.id'], ),
    sa.ForeignKeyConstraint(['poker_table_id'], ['poker_table.id'], ),
    sa.ForeignKeyConstraint(['slot_id'], ['slot.id'], ),
    sa.ForeignKeyConstraint(['table_id'], ['blackjack_table.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_game_session_baccarat_table_id'), 'game_session', ['baccarat_table_id'], unique=False)
    op.create_index(op.f('ix_game_session_game_type'), 'game_session', ['game_type'], unique=False)
    op.create_index(op.f('ix_game_session_poker_table_id'), 'game_session', ['poker_table_id'], unique=False)
    op.create_index(op.f('ix_game_session_slot_id'), 'game_session', ['slot_id'], unique=False)
    op.create_index(op.f('ix_game_session_table_id'), 'game_session', ['table_id'], unique=False)
    op.create_index(op.f('ix_game_session_user_id'), 'game_session', ['user_id'], unique=False)
    
    # Create slot_symbol table
    op.create_table('slot_symbol',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('slot_id', sa.Integer(), nullable=False),
    sa.Column('symbol_internal_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('img_link', sa.String(length=255), nullable=False),
    sa.Column('value_multiplier', sa.Float(), nullable=False),
    sa.Column('data', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['slot_id'], ['slot.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_slot_symbol_slot_id_internal_id', 'slot_symbol', ['slot_id', 'symbol_internal_id'], unique=True)
    
    # Create slot_bet table
    op.create_table('slot_bet',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('slot_id', sa.Integer(), nullable=False),
    sa.Column('bet_amount', sa.BigInteger(), nullable=False),
    sa.ForeignKeyConstraint(['slot_id'], ['slot.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_slot_bet_slot_id_amount', 'slot_bet', ['slot_id', 'bet_amount'], unique=True)
    
    # Create user_bonus table
    op.create_table('user_bonus',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('bonus_code_id', sa.Integer(), nullable=False),
    sa.Column('bonus_amount_awarded_sats', sa.BigInteger(), nullable=False),
    sa.Column('wagering_requirement_sats', sa.BigInteger(), nullable=False),
    sa.Column('wagering_progress_sats', sa.BigInteger(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_completed', sa.Boolean(), nullable=False),
    sa.Column('is_cancelled', sa.Boolean(), nullable=False),
    sa.Column('awarded_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['bonus_code_id'], ['bonus_code.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_bonus_bonus_code_id'), 'user_bonus', ['bonus_code_id'], unique=False)
    op.create_index(op.f('ix_user_bonus_is_active'), 'user_bonus', ['is_active'], unique=False)
    op.create_index('ix_user_bonus_user_id_active', 'user_bonus', ['user_id', 'is_active'], unique=False)
    op.create_index(op.f('ix_user_bonus_user_id'), 'user_bonus', ['user_id'], unique=False)
    
    # Create spacecrash_bet table
    op.create_table('spacecrash_bet',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('game_id', sa.Integer(), nullable=False),
    sa.Column('bet_amount', sa.BigInteger(), nullable=False),
    sa.Column('auto_eject_at', sa.Float(), nullable=True),
    sa.Column('ejected_at', sa.Float(), nullable=True),
    sa.Column('win_amount', sa.BigInteger(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('placed_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['game_id'], ['spacecrash_game.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_spacecrash_bet_game_id'), 'spacecrash_bet', ['game_id'], unique=False)
    op.create_index(op.f('ix_spacecrash_bet_status'), 'spacecrash_bet', ['status'], unique=False)
    op.create_index(op.f('ix_spacecrash_bet_user_id'), 'spacecrash_bet', ['user_id'], unique=False)
    
    # Create poker_hand table
    op.create_table('poker_hand',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('table_id', sa.Integer(), nullable=False),
    sa.Column('hand_history', sa.JSON(), nullable=False),
    sa.Column('board_cards', sa.JSON(), nullable=True),
    sa.Column('pot_size_sats', sa.BigInteger(), nullable=False),
    sa.Column('rake_sats', sa.BigInteger(), nullable=False),
    sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
    sa.Column('winners', sa.JSON(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('deck_state', sa.JSON(), nullable=True),
    sa.Column('current_turn_user_id', sa.Integer(), nullable=True),
    sa.Column('current_bet_to_match', sa.BigInteger(), nullable=False),
    sa.Column('player_street_investments', sa.JSON(), nullable=True),
    sa.Column('min_next_raise_amount', sa.BigInteger(), nullable=True),
    sa.Column('last_raiser_user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['current_turn_user_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['last_raiser_user_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['table_id'], ['poker_table.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_poker_hand_start_time'), 'poker_hand', ['start_time'], unique=False)
    op.create_index(op.f('ix_poker_hand_status'), 'poker_hand', ['status'], unique=False)
    op.create_index(op.f('ix_poker_hand_table_id'), 'poker_hand', ['table_id'], unique=False)
    
    # Create poker_player_state table
    op.create_table('poker_player_state',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('table_id', sa.Integer(), nullable=False),
    sa.Column('seat_id', sa.Integer(), nullable=False),
    sa.Column('stack_sats', sa.BigInteger(), nullable=False),
    sa.Column('is_sitting_out', sa.Boolean(), nullable=False),
    sa.Column('is_active_in_hand', sa.Boolean(), nullable=False),
    sa.Column('hole_cards', sa.JSON(), nullable=True),
    sa.Column('last_action', sa.String(length=50), nullable=True),
    sa.Column('time_to_act_ends', sa.DateTime(timezone=True), nullable=True),
    sa.Column('total_invested_this_hand', sa.BigInteger(), nullable=False),
    sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['table_id'], ['poker_table.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('table_id', 'seat_id', name='uq_table_seat'),
    sa.UniqueConstraint('user_id', 'table_id', name='uq_user_table')
    )
    op.create_index('ix_poker_player_state_user_table_seat', 'poker_player_state', ['user_id', 'table_id', 'seat_id'], unique=False)
    
    # Create plinko_drop_log table
    op.create_table('plinko_drop_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('stake_amount', sa.BigInteger(), nullable=False),
    sa.Column('chosen_stake_label', sa.String(length=50), nullable=False),
    sa.Column('slot_landed_label', sa.String(length=50), nullable=False),
    sa.Column('multiplier_applied', sa.Float(), nullable=False),
    sa.Column('winnings_amount', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    
    # Create roulette_game table
    op.create_table('roulette_game',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('bet_amount', sa.Float(), nullable=False),
    sa.Column('bet_type', sa.String(length=50), nullable=False),
    sa.Column('winning_number', sa.Integer(), nullable=True),
    sa.Column('payout', sa.Float(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    
    # Create slot_spin table
    op.create_table('slot_spin',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('game_session_id', sa.Integer(), nullable=False),
    sa.Column('spin_result', sa.JSON(), nullable=False),
    sa.Column('win_amount', sa.BigInteger(), nullable=False),
    sa.Column('bet_amount', sa.BigInteger(), nullable=False),
    sa.Column('is_bonus_spin', sa.Boolean(), nullable=False),
    sa.Column('current_multiplier_level', sa.Integer(), nullable=False),
    sa.Column('spin_time', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['game_session_id'], ['game_session.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_slot_spin_game_session_id'), 'slot_spin', ['game_session_id'], unique=False)
    
    # Create blackjack_hand table
    op.create_table('blackjack_hand',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('table_id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.Integer(), nullable=False),
    sa.Column('initial_bet', sa.BigInteger(), nullable=False),
    sa.Column('total_bet', sa.BigInteger(), nullable=False),
    sa.Column('win_amount', sa.BigInteger(), nullable=False),
    sa.Column('player_cards', sa.JSON(), nullable=False),
    sa.Column('dealer_cards', sa.JSON(), nullable=False),
    sa.Column('player_hands', sa.JSON(), nullable=False),
    sa.Column('dealer_hand', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('result', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['session_id'], ['game_session.id'], ),
    sa.ForeignKeyConstraint(['table_id'], ['blackjack_table.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_blackjack_hand_session_id'), 'blackjack_hand', ['session_id'], unique=False)
    op.create_index(op.f('ix_blackjack_hand_status'), 'blackjack_hand', ['status'], unique=False)
    op.create_index(op.f('ix_blackjack_hand_table_id'), 'blackjack_hand', ['table_id'], unique=False)
    op.create_index(op.f('ix_blackjack_hand_user_id'), 'blackjack_hand', ['user_id'], unique=False)
    
    # Create baccarat_hand table
    op.create_table('baccarat_hand',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('table_id', sa.Integer(), nullable=False),
    sa.Column('game_session_id', sa.Integer(), nullable=False),
    sa.Column('initial_bet_player', sa.BigInteger(), nullable=False),
    sa.Column('initial_bet_banker', sa.BigInteger(), nullable=False),
    sa.Column('initial_bet_tie', sa.BigInteger(), nullable=False),
    sa.Column('total_bet_amount', sa.BigInteger(), nullable=False),
    sa.Column('win_amount', sa.BigInteger(), nullable=False),
    sa.Column('player_cards', sa.JSON(), nullable=True),
    sa.Column('banker_cards', sa.JSON(), nullable=True),
    sa.Column('player_score', sa.Integer(), nullable=True),
    sa.Column('banker_score', sa.Integer(), nullable=True),
    sa.Column('outcome', sa.String(length=50), nullable=True),
    sa.Column('commission_paid', sa.BigInteger(), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('details', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['game_session_id'], ['game_session.id'], ),
    sa.ForeignKeyConstraint(['table_id'], ['baccarat_table.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_baccarat_hand_game_session_id'), 'baccarat_hand', ['game_session_id'], unique=False)
    op.create_index(op.f('ix_baccarat_hand_outcome'), 'baccarat_hand', ['outcome'], unique=False)
    op.create_index(op.f('ix_baccarat_hand_status'), 'baccarat_hand', ['status'], unique=False)
    op.create_index(op.f('ix_baccarat_hand_table_id'), 'baccarat_hand', ['table_id'], unique=False)
    op.create_index(op.f('ix_baccarat_hand_user_id'), 'baccarat_hand', ['user_id'], unique=False)
    
    # Create transaction table
    op.create_table('transaction',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('amount', sa.BigInteger(), nullable=False),
    sa.Column('transaction_type', sa.String(length=50), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('details', sa.JSON(), nullable=True),
    sa.Column('slot_spin_id', sa.Integer(), nullable=True),
    sa.Column('blackjack_hand_id', sa.Integer(), nullable=True),
    sa.Column('plinko_drop_id', sa.Integer(), nullable=True),
    sa.Column('poker_hand_id', sa.Integer(), nullable=True),
    sa.Column('baccarat_hand_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['baccarat_hand_id'], ['baccarat_hand.id'], ),
    sa.ForeignKeyConstraint(['blackjack_hand_id'], ['blackjack_hand.id'], ),
    sa.ForeignKeyConstraint(['plinko_drop_id'], ['plinko_drop_log.id'], ),
    sa.ForeignKeyConstraint(['poker_hand_id'], ['poker_hand.id'], ),
    sa.ForeignKeyConstraint(['slot_spin_id'], ['slot_spin.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transaction_blackjack_hand_id'), 'transaction', ['blackjack_hand_id'], unique=False)
    op.create_index(op.f('ix_transaction_plinko_drop_id'), 'transaction', ['plinko_drop_id'], unique=False)
    op.create_index(op.f('ix_transaction_poker_hand_id'), 'transaction', ['poker_hand_id'], unique=False)
    op.create_index(op.f('ix_transaction_slot_spin_id'), 'transaction', ['slot_spin_id'], unique=False)
    op.create_index(op.f('ix_transaction_status'), 'transaction', ['status'], unique=False)
    op.create_index(op.f('ix_transaction_transaction_type'), 'transaction', ['transaction_type'], unique=False)
    op.create_index(op.f('ix_transaction_user_id'), 'transaction', ['user_id'], unique=False)
    
    # Create blackjack_action table
    op.create_table('blackjack_action',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('hand_id', sa.Integer(), nullable=False),
    sa.Column('action_type', sa.String(length=20), nullable=False),
    sa.Column('hand_index', sa.Integer(), nullable=False),
    sa.Column('card_dealt', sa.String(length=10), nullable=True),
    sa.Column('hand_total', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['hand_id'], ['blackjack_hand.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_blackjack_action_hand_id'), 'blackjack_action', ['hand_id'], unique=False)
    
    # Create baccarat_action table
    op.create_table('baccarat_action',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('baccarat_hand_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('action_type', sa.String(length=50), nullable=False),
    sa.Column('bet_on_player', sa.BigInteger(), nullable=True),
    sa.Column('bet_on_banker', sa.BigInteger(), nullable=True),
    sa.Column('bet_on_tie', sa.BigInteger(), nullable=True),
    sa.Column('action_details', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['baccarat_hand_id'], ['baccarat_hand.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_baccarat_action_baccarat_hand_id'), 'baccarat_action', ['baccarat_hand_id'], unique=False)
    op.create_index(op.f('ix_baccarat_action_user_id'), 'baccarat_action', ['user_id'], unique=False)


def downgrade():
    # Drop tables in reverse order to handle foreign key constraints
    op.drop_table('baccarat_action')
    op.drop_table('blackjack_action')
    op.drop_table('transaction')
    op.drop_table('baccarat_hand')
    op.drop_table('blackjack_hand')
    op.drop_table('slot_spin')
    op.drop_table('roulette_game')
    op.drop_table('plinko_drop_log')
    op.drop_table('poker_player_state')
    op.drop_table('poker_hand')
    op.drop_table('spacecrash_bet')
    op.drop_table('user_bonus')
    op.drop_table('slot_bet')
    op.drop_table('slot_symbol')
    op.drop_table('game_session')
    op.drop_table('token_blacklist')
    op.drop_table('spacecrash_game')
    op.drop_table('baccarat_table')
    op.drop_table('poker_table')
    op.drop_table('blackjack_table')
    op.drop_table('slot')
    op.drop_table('bonus_code')
    op.drop_table('user')