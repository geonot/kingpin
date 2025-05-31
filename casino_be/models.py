from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone, timedelta
from passlib.hash import pbkdf2_sha256 as sha256
from sqlalchemy.dialects.postgresql import JSONB # Use JSONB for better performance in Postgres
from sqlalchemy import BigInteger, Index # Import BigInteger and Index

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True) # Added index
    email = db.Column(db.String(120), unique=True, nullable=False, index=True) # Added index
    password = db.Column(db.String(128), nullable=False)
    balance = db.Column(BigInteger, default=0, nullable=False, index=True)  # Balance in satoshis, Indexed
    deposit_wallet_address = db.Column(db.String(256), nullable=False, unique=True) # Wallet address should be unique
    deposit_wallet_private_key = db.Column(db.String(256), nullable=False) # Highly insecure for prod!
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False) # Added active status
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False) # Use timezone-aware
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True) # Track last login

    # Relationships
    game_sessions = db.relationship('GameSession', backref='user', lazy=True)
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    blackjack_hands = db.relationship('BlackjackHand', backref='user', lazy=True)
    # user_bonuses = db.relationship('UserBonus', backref='user', lazy=True) # If UserBonus model exists

    @staticmethod
    def hash_password(password):
        # Increase rounds for better security (default is 29000, adjust based on server capability)
        return sha256.using(rounds=600000).hash(password)

    @staticmethod
    def verify_password(hash_str, password):
        # Use constant time comparison if possible, though passlib might handle this.
        return sha256.verify(password, hash_str)

    def __repr__(self):
        return f"<User {self.username} (ID: {self.id})>"

class GameSession(db.Model):
    __tablename__ = 'game_session'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True) # Added index
    slot_id = db.Column(db.Integer, db.ForeignKey('slot.id'), nullable=True, index=True) # Made nullable for blackjack
    table_id = db.Column(db.Integer, db.ForeignKey('blackjack_table.id'), nullable=True, index=True) # Added for blackjack
    game_type = db.Column(db.String(20), nullable=False, default='slot') # 'slot', 'blackjack', etc.
    bonus_active = db.Column(db.Boolean, default=False, nullable=False)
    bonus_spins_remaining = db.Column(db.Integer, default=0, nullable=False) # Renamed from bonus_spins
    bonus_multiplier = db.Column(db.Float, default=1.0, nullable=False)
    amount_wagered = db.Column(BigInteger, default=0, nullable=False) # In satoshis
    amount_won = db.Column(BigInteger, default=0, nullable=False) # In satoshis
    # spin_amount is ambiguous, bet_amount is in SlotSpin. Remove spin_amount? Or rename?
    # Let's remove spin_amount as it's redundant with SlotSpin.bet_amount
    # spin_amount = db.Column(BigInteger, default=0, nullable=False) # In satoshis
    num_spins = db.Column(db.Integer, default=0, nullable=False)
    session_start = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    session_end = db.Column(db.DateTime(timezone=True), nullable=True, index=True) # Added index
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationship
    slot_spins = db.relationship('SlotSpin', backref='game_session', lazy=True, order_by="desc(SlotSpin.spin_time)")
    blackjack_hands = db.relationship('BlackjackHand', backref='game_session', lazy=True)

    def __repr__(self):
        status = "Active" if self.session_end is None else "Ended"
        return f"<GameSession {self.id} (User: {self.user_id}, Type: {self.game_type}, Status: {status})>"

class SlotSpin(db.Model):
    __tablename__ = 'slot_spin'
    id = db.Column(db.Integer, primary_key=True)
    game_session_id = db.Column(db.Integer, db.ForeignKey('game_session.id'), nullable=False, index=True) # Added index
    spin_result = db.Column(JSONB, nullable=False) # Use JSONB
    win_amount = db.Column(BigInteger, nullable=False) # In satoshis
    bet_amount = db.Column(BigInteger, nullable=False) # In satoshis - Already existed, ensure type is BigInteger
    is_bonus_spin = db.Column(db.Boolean, default=False, nullable=False) # Added is_bonus_spin flag
    spin_time = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True) # Added index
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<SlotSpin {self.id} (Session: {self.game_session_id}, Bet: {self.bet_amount}, Win: {self.win_amount})>"

class Transaction(db.Model):
    __tablename__ = 'transaction'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True) # Added index
    amount = db.Column(BigInteger, nullable=False) # In satoshis (can be negative for debits)
    transaction_type = db.Column(db.String(20), nullable=False, index=True) # e.g., 'deposit', 'withdraw', 'wager', 'win', 'bonus', 'transfer', 'adjustment'
    status = db.Column(db.String(15), default='completed', nullable=False, index=True) # e.g., 'pending', 'completed', 'failed', 'cancelled'
    details = db.Column(JSONB, nullable=True) # Store related info like addresses, bonus codes, related tx_id etc.
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True) # Added index

    def __repr__(self):
        return f"<Transaction {self.id} (User: {self.user_id}, Type: {self.transaction_type}, Amount: {self.amount}, Status: {self.status})>"

class BonusCode(db.Model):
    __tablename__ = 'bonus_code'
    id = db.Column(db.Integer, primary_key=True)
    code_id = db.Column(db.String(50), unique=True, nullable=False, index=True) # Added index
    description = db.Column(db.Text, nullable=True) # Added description
    type = db.Column(db.String(50), nullable=False) # e.g., 'deposit', 'registration', 'free_spins'
    subtype = db.Column(db.String(50), nullable=False) # e.g., 'percentage', 'fixed', 'spins'
    amount = db.Column(db.Float, nullable=False) # For 'percentage', this is the percentage value. For 'fixed', this is Satoshis (use Float here to accommodate percentage, but handle conversion in logic)
    # Consider adding a separate column for 'spins_awarded' if type is 'free_spins'
    max_uses = db.Column(db.Integer, nullable=True) # Max total uses
    uses_remaining = db.Column(db.Integer, nullable=True) # Track remaining uses
    # max_uses_per_user = db.Column(db.Integer, default=1) # Limit per user
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True) # Expiry date
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True) # Added active status and index
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<BonusCode {self.id} ({self.code_id})>"

class Slot(db.Model):
    __tablename__ = 'slot'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True) # Allow null description
    num_rows = db.Column(db.Integer, nullable=False)
    num_columns = db.Column(db.Integer, nullable=False)
    num_symbols = db.Column(db.Integer, nullable=False) # Total distinct symbols defined for this slot
    wild_symbol_id = db.Column(db.Integer, nullable=True) # FK to SlotSymbol ID (allow null if no wild)
    scatter_symbol_id = db.Column(db.Integer, nullable=True) # FK to SlotSymbol ID (allow null if no scatter)
    bonus_type = db.Column(db.String(50), nullable=True) # e.g., 'free_spins', 'pick_em', etc.
    bonus_subtype = db.Column(db.String(50), nullable=True) # Further details
    bonus_multiplier = db.Column(db.Float, nullable=False, default=1.0) # Default multiplier for bonus rounds
    bonus_spins_trigger_count = db.Column(db.Integer, nullable=False, default=3) # Scatters needed
    bonus_spins_awarded = db.Column(db.Integer, nullable=False, default=10) # Free spins awarded
    # Removed bonus_multiplier and bonus_spins from here as they were ambiguous - moved specifics above
    short_name = db.Column(db.String(50), nullable=False, unique=True) # Used for asset paths, e.g., 'hack', 'dragon'
    asset_directory = db.Column(db.String(100), nullable=False, default='') # Path relative to static/public folder
    rtp = db.Column(db.Float, nullable=True) # Return to Player percentage
    volatility = db.Column(db.String(20), nullable=True) # e.g., 'low', 'medium', 'high'
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True) # Can disable slots
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    symbols = db.relationship('SlotSymbol', backref='slot', lazy='joined', order_by='SlotSymbol.id') # Eager load symbols
    bets = db.relationship('SlotBet', backref='slot', lazy='joined', order_by='SlotBet.bet_amount') # Eager load bets
    # paylines = db.relationship('SlotPayline', backref='slot', lazy='joined') # Eager load paylines if model exists
    # payouts = db.relationship('SlotPayout', backref='slot', lazy=True) # If payout table exists

    # Add constraints if needed, e.g., ensuring wild/scatter IDs exist in symbols
    # __table_args__ = (
    #     db.ForeignKeyConstraint(['wild_symbol_id'], ['slot_symbol.id']),
    #     db.ForeignKeyConstraint(['scatter_symbol_id'], ['slot_symbol.id']),
    # )

    def __repr__(self):
        return f"<Slot {self.id} ({self.name})>"

class SlotSymbol(db.Model):
    __tablename__ = 'slot_symbol'
    id = db.Column(db.Integer, primary_key=True) # Use auto-incrementing ID
    slot_id = db.Column(db.Integer, db.ForeignKey('slot.id'), nullable=False, index=True) # Added index
    symbol_internal_id = db.Column(db.Integer, nullable=False) # The ID used within the game logic/config (e.g., 1, 2, 3...)
    name = db.Column(db.String(50), nullable=False) # e.g., 'Cherry', 'Wild', 'Scatter'
    img_link = db.Column(db.String(256), nullable=False) # Path to image asset
    value_multiplier = db.Column(db.Float, nullable=True) # Base multiplier for win calc (can be null for non-paying like scatter)
    # Replaced is_wild/is_scatter with FKs in Slot table
    # is_wild = db.Column(db.Boolean, default=False, nullable=False)
    # is_scatter = db.Column(db.Boolean, default=False, nullable=False)
    data = db.Column(JSONB, nullable=True) # Store extra data like animation details, sound effects
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index('ix_slot_symbol_slot_id_internal_id', 'slot_id', 'symbol_internal_id', unique=True), # Ensure unique internal ID per slot
    )

    def __repr__(self):
        return f"<SlotSymbol {self.id} (Slot: {self.slot_id}, InternalID: {self.symbol_internal_id}, Name: {self.name})>"


class SlotBet(db.Model):
    # Represents predefined bet amounts available for a slot
    __tablename__ = 'slot_bet'
    id = db.Column(db.Integer, primary_key=True)
    slot_id = db.Column(db.Integer, db.ForeignKey('slot.id'), nullable=False, index=True) # Added index
    bet_amount = db.Column(BigInteger, nullable=False) # Bet amount in satoshis
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index('ix_slot_bet_slot_id_bet_amount', 'slot_id', 'bet_amount', unique=True), # Ensure unique bet amount per slot
    )

    def __repr__(self):
        return f"<SlotBet {self.id} (Slot: {self.slot_id}, Amount: {self.bet_amount})>"


# Add SlotPayline and SlotPayout models if needed for more complex win calculations
# class SlotPayline(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     slot_id = db.Column(db.Integer, db.ForeignKey('slot.id'), nullable=False, index=True)
#     line_index = db.Column(db.Integer, nullable=False) # 0, 1, 2...
#     positions = db.Column(JSONB, nullable=False) # e.g., [[0,0], [1,1], [2,2]] (list of [row, col])
#     __table_args__ = (Index('ix_slot_payline_slot_id_line_index', 'slot_id', 'line_index', unique=True),)

# class SlotPayout(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     slot_id = db.Column(db.Integer, db.ForeignKey('slot.id'), nullable=False, index=True)
#     symbol_id = db.Column(db.Integer, db.ForeignKey('slot_symbol.id'), nullable=False) # FK to SlotSymbol PK
#     num_matches = db.Column(db.Integer, nullable=False) # e.g., 3, 4, 5
#     multiplier = db.Column(db.Float, nullable=False) # Payout multiplier for this combination
#     __table_args__ = (Index('ix_slot_payout_slot_symbol_matches', 'slot_id', 'symbol_id', 'num_matches', unique=True),)


# Blackjack Models
class BlackjackTable(db.Model):
    __tablename__ = 'blackjack_table'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    min_bet = db.Column(BigInteger, nullable=False)  # in satoshis
    max_bet = db.Column(BigInteger, nullable=False)  # in satoshis
    deck_count = db.Column(db.Integer, nullable=False)
    rules = db.Column(JSONB, nullable=True)  # JSON field for specific rules
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    game_sessions = db.relationship('GameSession', backref='blackjack_table', lazy=True)
    hands = db.relationship('BlackjackHand', backref='table', lazy=True)

    def __repr__(self):
        return f"<BlackjackTable {self.id} ({self.name})>"


class BlackjackHand(db.Model):
    __tablename__ = 'blackjack_hand'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    table_id = db.Column(db.Integer, db.ForeignKey('blackjack_table.id'), nullable=False, index=True)
    session_id = db.Column(db.Integer, db.ForeignKey('game_session.id'), nullable=False, index=True)
    initial_bet = db.Column(BigInteger, nullable=False)  # in satoshis
    total_bet = db.Column(BigInteger, nullable=False)  # in satoshis (includes doubles, splits)
    win_amount = db.Column(BigInteger, nullable=True)  # in satoshis
    player_cards = db.Column(JSONB, nullable=False)  # JSON array of card objects
    dealer_cards = db.Column(JSONB, nullable=False)  # JSON array of card objects
    player_hands = db.Column(JSONB, nullable=False)  # JSON array of hand objects (for splits)
    dealer_hand = db.Column(JSONB, nullable=False)  # JSON object for dealer hand
    status = db.Column(db.String(20), nullable=False, index=True)  # 'active', 'completed', 'cancelled'
    result = db.Column(db.String(20), nullable=True)  # 'win', 'lose', 'push', 'blackjack'
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    actions = db.relationship('BlackjackAction', backref='hand', lazy=True, order_by='BlackjackAction.created_at')

    def __repr__(self):
        return f"<BlackjackHand {self.id} (User: {self.user_id}, Table: {self.table_id}, Status: {self.status})>"


class BlackjackAction(db.Model):
    __tablename__ = 'blackjack_action'
    id = db.Column(db.Integer, primary_key=True)
    hand_id = db.Column(db.Integer, db.ForeignKey('blackjack_hand.id'), nullable=False, index=True)
    action_type = db.Column(db.String(20), nullable=False)  # 'hit', 'stand', 'double', 'split'
    hand_index = db.Column(db.Integer, nullable=False)  # Which hand the action applies to (for splits)
    card_dealt = db.Column(JSONB, nullable=True)  # Card dealt as a result of the action
    hand_total = db.Column(db.Integer, nullable=True)  # Hand total after the action
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<BlackjackAction {self.id} (Hand: {self.hand_id}, Type: {self.action_type})>"


class TokenBlacklist(db.Model):
    __tablename__ = 'token_blacklist'
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False, index=True, unique=True) # JTI is usually a UUID
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True) # Add expiry for cleanup

    def __repr__(self):
        return f"<TokenBlacklist {self.id} (JTI: {self.jti})>"

# TODO: Add a periodic task (e.g., using Celery Beat or APScheduler) to clean up expired tokens from TokenBlacklist.
