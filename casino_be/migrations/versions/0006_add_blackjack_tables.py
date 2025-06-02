"""add blackjack tables

Revision ID: 0006_add_blackjack_tables
Revises: 25e593b1e95c
Create Date: 2025-03-30 21:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
# from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '0006_add_blackjack_tables'
down_revision = '25e593b1e95c'
branch_labels = None
depends_on = None


def upgrade():
    # Create BlackjackTable model
    op.create_table(
        'blackjack_table',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('min_bet', sa.BigInteger(), nullable=False),  # in satoshis
        sa.Column('max_bet', sa.BigInteger(), nullable=False),  # in satoshis
        sa.Column('deck_count', sa.Integer(), nullable=False),
        sa.Column('rules', sa.JSON(), nullable=True),  # JSON field for specific rules
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create BlackjackHand model
    op.create_table(
        'blackjack_hand',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('table_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),  # Reference to GameSession
        sa.Column('initial_bet', sa.BigInteger(), nullable=False),  # in satoshis
        sa.Column('total_bet', sa.BigInteger(), nullable=False),  # in satoshis (includes doubles, splits)
        sa.Column('win_amount', sa.BigInteger(), nullable=True),  # in satoshis
        sa.Column('player_cards', sa.JSON(), nullable=False),  # JSON array of card objects
        sa.Column('dealer_cards', sa.JSON(), nullable=False),  # JSON array of card objects
        sa.Column('player_hands', sa.JSON(), nullable=False),  # JSON array of hand objects (for splits)
        sa.Column('dealer_hand', sa.JSON(), nullable=False),  # JSON object for dealer hand
        sa.Column('status', sa.String(length=20), nullable=False),  # 'active', 'completed', 'cancelled'
        sa.Column('result', sa.String(length=20), nullable=True),  # 'win', 'lose', 'push', 'blackjack'
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['table_id'], ['blackjack_table.id'], ),
        sa.ForeignKeyConstraint(['session_id'], ['game_session.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create BlackjackAction model
    op.create_table(
        'blackjack_action',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('hand_id', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(length=20), nullable=False),  # 'hit', 'stand', 'double', 'split'
        sa.Column('hand_index', sa.Integer(), nullable=False),  # Which hand the action applies to (for splits)
        sa.Column('card_dealt', sa.JSON(), nullable=True),  # Card dealt as a result of the action
        sa.Column('hand_total', sa.Integer(), nullable=True),  # Hand total after the action
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['hand_id'], ['blackjack_hand.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Insert default blackjack tables
    op.execute("""
    INSERT INTO blackjack_table (name, description, min_bet, max_bet, deck_count, rules, is_active)
    VALUES 
    ('Low Stakes', 'Beginner-friendly blackjack table with low minimum bets', 10, 1000, 6, 
     '{"dealer_stands_on": "soft17", "blackjack_payout": 1.5, "allow_double_after_split": true, "allow_surrender": false}', true),
    ('High Roller', 'Premium blackjack experience for serious players', 1000, 100000, 8, 
     '{"dealer_stands_on": "soft17", "blackjack_payout": 1.5, "allow_double_after_split": true, "allow_surrender": true}', true)
    """)


def downgrade():
    op.drop_table('blackjack_action')
    op.drop_table('blackjack_hand')
    op.drop_table('blackjack_table')