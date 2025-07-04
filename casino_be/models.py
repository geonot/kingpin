from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from passlib.hash import pbkdf2_sha256 as sha256
from decimal import Decimal
from sqlalchemy import BigInteger, Index, JSON, UniqueConstraint, Numeric, DateTime, Float, ForeignKey

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    balance = db.Column(BigInteger, default=0, nullable=False, index=True)
    deposit_wallet_address = db.Column(db.String(255), unique=True, nullable=True, index=True)
    deposit_wallet_private_key = db.Column(db.Text, nullable=True)  # Encrypted WIF private key
    is_admin = db.Column(db.Boolean, default=False, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    game_sessions = db.relationship('GameSession', back_populates='user', lazy=True)
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    blackjack_hands = db.relationship('BlackjackHand', back_populates='user', lazy=True)
    user_bonuses = db.relationship('UserBonus', back_populates='user', lazy=True)
    spacecrash_bets = db.relationship('SpacecrashBet', back_populates='user', lazy='dynamic')
    poker_states = db.relationship('PokerPlayerState', back_populates='user', lazy='dynamic')
    plinko_drops = db.relationship('PlinkoDropLog', back_populates='user', lazy=True)
    # roulette_games backref will be added by RouletteGame model
    baccarat_hands = db.relationship('BaccaratHand', back_populates='user', lazy='dynamic')

    # Crystal Garden related relationships
    garden = db.relationship("PlayerGarden", back_populates="user", uselist=False)
    crystal_flowers = db.relationship("CrystalFlower", back_populates="user")
    codex_entries = db.relationship("CrystalCodexEntry", back_populates="user")

    def check_password(self, password):
        return sha256.verify(password, self.password)

    @staticmethod
    def hash_password(password):
        return sha256.hash(password)

    @staticmethod
    def verify_password(hashed_password, password):
        return sha256.verify(password, hashed_password)

    def __repr__(self):
        return f"<User {self.username}>"

class GameSession(db.Model):
    __tablename__ = 'game_session'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    slot_id = db.Column(db.Integer, db.ForeignKey('slot.id', ondelete='SET NULL'), nullable=True, index=True)
    table_id = db.Column(db.Integer, db.ForeignKey('blackjack_table.id', ondelete='SET NULL'), nullable=True, index=True)
    poker_table_id = db.Column(db.Integer, db.ForeignKey('poker_table.id', ondelete='SET NULL'), nullable=True, index=True)
    baccarat_table_id = db.Column(db.Integer, db.ForeignKey('baccarat_table.id', ondelete='SET NULL'), nullable=True, index=True)
    game_type = db.Column(db.String(50), nullable=False, index=True)
    bonus_active = db.Column(db.Boolean, default=False, nullable=False)
    bonus_spins_remaining = db.Column(db.Integer, default=0, nullable=False)
    bonus_multiplier = db.Column(db.Float, default=1.0, nullable=False)
    amount_wagered = db.Column(BigInteger, default=0, nullable=False)
    amount_won = db.Column(BigInteger, default=0, nullable=False)
    num_spins = db.Column(db.Integer, default=0, nullable=False)
    session_start = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    session_end = db.Column(db.DateTime(timezone=True), nullable=True)

    user = db.relationship('User', back_populates='game_sessions')
    slot = db.relationship('Slot', backref='game_sessions')
    blackjack_table = db.relationship('BlackjackTable', backref='game_sessions')
    poker_table = db.relationship('PokerTable', backref='game_sessions')
    baccarat_table = db.relationship('BaccaratTable', backref='game_sessions')
    baccarat_hands = db.relationship('BaccaratHand', back_populates='session', lazy='dynamic')


    def __repr__(self):
        return f"<GameSession {self.id} (User: {self.user_id}, Type: {self.game_type})>"

class SlotSpin(db.Model):
    __tablename__ = 'slot_spin'
    id = db.Column(db.Integer, primary_key=True)
    game_session_id = db.Column(db.Integer, db.ForeignKey('game_session.id', ondelete='CASCADE'), nullable=False, index=True) # If a game session is deleted, its spins go too.
    spin_result = db.Column(JSON, nullable=False)
    win_amount = db.Column(BigInteger, nullable=False)
    bet_amount = db.Column(BigInteger, nullable=False)
    is_bonus_spin = db.Column(db.Boolean, default=False, nullable=False)
    current_multiplier_level = db.Column(db.Integer, default=0, nullable=False) # Tracks current multiplier for cascading wins
    spin_time = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    game_session = db.relationship('GameSession', backref='slot_spins')

    def __repr__(self):
        return f"<SlotSpin {self.id} (Session: {self.game_session_id}, Bet: {self.bet_amount}, Win: {self.win_amount})>"

class Transaction(db.Model):
    __tablename__ = 'transaction'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True, index=True) # Changed nullable to True
    amount = db.Column(BigInteger, nullable=False)
    transaction_type = db.Column(db.String(50), nullable=False, index=True)
    status = db.Column(db.String(50), default='pending', nullable=False, index=True)
    details = db.Column(JSON, nullable=True)
    slot_spin_id = db.Column(db.Integer, db.ForeignKey('slot_spin.id', ondelete='SET NULL'), nullable=True, index=True)
    blackjack_hand_id = db.Column(db.Integer, db.ForeignKey('blackjack_hand.id', ondelete='SET NULL'), nullable=True, index=True)
    plinko_drop_id = db.Column(db.Integer, db.ForeignKey('plinko_drop_log.id', ondelete='SET NULL'), nullable=True, index=True)

    # Relationships to game events
    slot_spin = db.relationship('SlotSpin', backref=db.backref('transactions', lazy='dynamic'))
    blackjack_hand = db.relationship('BlackjackHand', backref=db.backref('transactions', lazy='dynamic'))
    plinko_drop_log = db.relationship('PlinkoDropLog', backref=db.backref('transactions', lazy='dynamic'))
    poker_hand_id = db.Column(db.Integer, db.ForeignKey('poker_hand.id', ondelete='SET NULL'), nullable=True, index=True)
    poker_hand = db.relationship('PokerHand', backref=db.backref('transactions', lazy='dynamic'))
    baccarat_hand_id = db.Column(db.Integer, db.ForeignKey('baccarat_hand.id', ondelete='SET NULL'), nullable=True, index=True)
    baccarat_hand = db.relationship('BaccaratHand', backref=db.backref('transactions', lazy='dynamic'))

    def __repr__(self):
        return f"<Transaction {self.id} (User: {self.user_id}, Type: {self.transaction_type}, Amount: {self.amount})>"

class BonusCode(db.Model):
    __tablename__ = 'bonus_code'
    id = db.Column(db.Integer, primary_key=True)
    code_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    type = db.Column(db.String(50), nullable=False, index=True)
    subtype = db.Column(db.String(50), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=True)
    amount_sats = db.Column(BigInteger, nullable=True)
    max_uses = db.Column(db.Integer, nullable=True)
    uses_remaining = db.Column(db.Integer, nullable=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    wagering_requirement_multiplier = db.Column(db.Float, default=1.0, nullable=False) # Added field
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<BonusCode {self.code_id} ({self.type}/{self.subtype})>"

class Slot(db.Model):
    __tablename__ = 'slot'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    num_rows = db.Column(db.Integer, nullable=False)
    num_columns = db.Column(db.Integer, nullable=False)
    num_symbols = db.Column(db.Integer, nullable=False)
    wild_symbol_id = db.Column(db.Integer, nullable=True)
    scatter_symbol_id = db.Column(db.Integer, nullable=True)
    bonus_type = db.Column(db.String(50), nullable=True)
    bonus_subtype = db.Column(db.String(50), nullable=True)
    bonus_multiplier = db.Column(db.Float, default=1.0, nullable=False)
    bonus_spins_trigger_count = db.Column(db.Integer, default=3, nullable=False)
    bonus_spins_awarded = db.Column(db.Integer, default=10, nullable=False)
    short_name = db.Column(db.String(50), nullable=False)
    asset_directory = db.Column(db.String(255), nullable=False)
    rtp = db.Column(db.Float, nullable=False)
    volatility = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    is_multiway = db.Column(db.Boolean, default=False, nullable=False)
    reel_configurations = db.Column(JSON, nullable=True)
    is_cascading = db.Column(db.Boolean, default=False, nullable=False)
    cascade_type = db.Column(db.String(50), nullable=True)  # e.g., "replace_in_place", "fall_from_top"
    min_symbols_to_match = db.Column(db.Integer, nullable=True) # For non-payline wins, e.g. scatter-pays or cluster-pays if is_multiway is False
    win_multipliers = db.Column(JSON, nullable=True)  # e.g., [1, 2, 4, 8, 10] for cascading wins
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    symbols = db.relationship('SlotSymbol', backref='slot', lazy='select')
    bets = db.relationship('SlotBet', backref='slot', lazy='select')

    def __repr__(self):
        return f"<Slot {self.id} ({self.short_name})>"

class SlotSymbol(db.Model):
    __tablename__ = 'slot_symbol'
    id = db.Column(db.Integer, primary_key=True)
    slot_id = db.Column(db.Integer, db.ForeignKey('slot.id', ondelete='CASCADE'), nullable=False, index=True)
    symbol_internal_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(50), nullable=False)
    img_link = db.Column(db.String(255), nullable=False)
    value_multiplier = db.Column(db.Float, nullable=False)
    data = db.Column(JSON, nullable=True)

    __table_args__ = (Index('ix_slot_symbol_slot_id_internal_id', 'slot_id', 'symbol_internal_id', unique=True),)

    def __repr__(self):
        return f"<SlotSymbol {self.name} (Slot: {self.slot_id}, ID: {self.symbol_internal_id})>"

class SlotBet(db.Model):
    __tablename__ = 'slot_bet'
    id = db.Column(db.Integer, primary_key=True)
    slot_id = db.Column(db.Integer, db.ForeignKey('slot.id', ondelete='CASCADE'), nullable=False, index=True)
    bet_amount = db.Column(BigInteger, nullable=False)

    __table_args__ = (Index('ix_slot_bet_slot_id_amount', 'slot_id', 'bet_amount', unique=True),)

    def __repr__(self):
        return f"<SlotBet {self.bet_amount} sats (Slot: {self.slot_id})>"

class BlackjackTable(db.Model):
    __tablename__ = 'blackjack_table'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    min_bet = db.Column(BigInteger, nullable=False)
    max_bet = db.Column(db.BigInteger, nullable=False)
    deck_count = db.Column(db.Integer, nullable=False)
    rules = db.Column(JSON, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text('CURRENT_TIMESTAMP'), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text('CURRENT_TIMESTAMP'), nullable=False)

    hands = db.relationship('BlackjackHand', backref='table', lazy='dynamic')

    def __repr__(self):
        return f"<BlackjackTable {self.id} ({self.name})>"

class BlackjackHand(db.Model):
    __tablename__ = 'blackjack_hand'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    table_id = db.Column(db.Integer, db.ForeignKey('blackjack_table.id', ondelete='RESTRICT'), nullable=False, index=True) # Prevent table deletion if hands exist
    session_id = db.Column(db.Integer, db.ForeignKey('game_session.id', ondelete='CASCADE'), nullable=False, index=True) # Hands are part of a session
    initial_bet = db.Column(BigInteger, nullable=False)
    total_bet = db.Column(BigInteger, nullable=False)
    win_amount = db.Column(BigInteger, default=0, nullable=False)
    player_cards = db.Column(JSON, nullable=False)
    dealer_cards = db.Column(JSON, nullable=False)
    player_hands = db.Column(JSON, nullable=False)
    dealer_hand = db.Column(JSON, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='active', index=True)
    result = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    user = db.relationship('User', back_populates='blackjack_hands')
    session = db.relationship('GameSession', backref='blackjack_hands')
    actions = db.relationship('BlackjackAction', backref='hand', lazy='dynamic')

    def __repr__(self):
        return f"<BlackjackHand {self.id} (User: {self.user_id}, Bet: {self.initial_bet}, Status: {self.status})>"

class BlackjackAction(db.Model):
    __tablename__ = 'blackjack_action'
    id = db.Column(db.Integer, primary_key=True)
    hand_id = db.Column(db.Integer, db.ForeignKey('blackjack_hand.id', ondelete='CASCADE'), nullable=False, index=True)
    action_type = db.Column(db.String(20), nullable=False)
    hand_index = db.Column(db.Integer, nullable=False)
    card_dealt = db.Column(db.String(10), nullable=True)
    hand_total = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<BlackjackAction {self.id} (Hand: {self.hand_id}, Action: {self.action_type})>"

class UserBonus(db.Model):
    __tablename__ = 'user_bonus'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    bonus_code_id = db.Column(db.Integer, db.ForeignKey('bonus_code.id', ondelete='RESTRICT'), nullable=False, index=True)
    bonus_amount_awarded_sats = db.Column(BigInteger, nullable=False)
    wagering_requirement_sats = db.Column(BigInteger, nullable=False)
    wagering_progress_sats = db.Column(BigInteger, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    is_completed = db.Column(db.Boolean, default=False, nullable=False)
    is_cancelled = db.Column(db.Boolean, default=False, nullable=False)
    awarded_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    cancelled_at = db.Column(db.DateTime(timezone=True), nullable=True)

    bonus_code = db.relationship('BonusCode', backref='user_bonuses')
    user = db.relationship('User', back_populates='user_bonuses') # Assuming User.user_bonuses will be defined or this is the primary def

    __table_args__ = (Index('ix_user_bonus_user_id_active', 'user_id', 'is_active'),)

    def __repr__(self):
        return f"<UserBonus {self.id} (User: {self.user_id}, BonusCodeID: {self.bonus_code_id}, Active: {self.is_active})>"

# Spacecrash Game Models
class SpacecrashGame(db.Model):
    __tablename__ = 'spacecrash_game'
    id = db.Column(db.Integer, primary_key=True)
    server_seed = db.Column(db.String(255), nullable=False)
    client_seed = db.Column(db.String(255), nullable=True)
    nonce = db.Column(db.Integer, nullable=False)
    crash_point = db.Column(db.Float, nullable=True)
    public_seed = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(50), nullable=False, default='pending', index=True)
    betting_start_time = db.Column(db.DateTime(timezone=True), nullable=True)
    game_start_time = db.Column(db.DateTime(timezone=True), nullable=True)
    game_end_time = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    bets = db.relationship('SpacecrashBet', backref='game', lazy='dynamic')

    def __repr__(self):
        return f"<SpacecrashGame {self.id} (Status: {self.status}, Crash: {self.crash_point})>"

class SpacecrashBet(db.Model):
    __tablename__ = 'spacecrash_bet'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    game_id = db.Column(db.Integer, db.ForeignKey('spacecrash_game.id', ondelete='CASCADE'), nullable=False, index=True) # If game is deleted, bets are too
    bet_amount = db.Column(BigInteger, nullable=False)
    auto_eject_at = db.Column(db.Float, nullable=True)
    ejected_at = db.Column(db.Float, nullable=True)
    win_amount = db.Column(BigInteger, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='placed', index=True)
    placed_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship('User', back_populates='spacecrash_bets') # Assuming User.spacecrash_bets will be defined

    def __repr__(self):
        return f"<SpacecrashBet {self.id} (User: {self.user_id}, Game: {self.game_id}, Bet: {self.bet_amount}, Status: {self.status})>"

# Poker Models
class PokerTable(db.Model):
    __tablename__ = 'poker_table'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    game_type = db.Column(db.String(50), nullable=False, default='texas_holdem')
    limit_type = db.Column(db.String(50), nullable=False, default='no_limit')
    small_blind = db.Column(BigInteger, nullable=False)
    big_blind = db.Column(BigInteger, nullable=False)
    min_buy_in = db.Column(BigInteger, nullable=False)
    max_buy_in = db.Column(db.BigInteger, nullable=False)
    max_seats = db.Column(db.Integer, nullable=False, default=9)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    # Rake configuration
    rake_percentage = db.Column(db.Numeric(5, 4), default=Decimal("0.00"), nullable=False) # e.g., 0.05 for 5%
    max_rake_sats = db.Column(db.BigInteger, default=0, nullable=False) # Max rake in satoshis, 0 for no cap beyond percentage
    current_dealer_seat_id = db.Column(db.Integer, nullable=True) # Seat ID of the current dealer

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    hands = db.relationship('PokerHand', backref='table', lazy='dynamic')
    player_states = db.relationship('PokerPlayerState', backref='table', lazy='dynamic')

    def __repr__(self):
        return f"<PokerTable {self.id} ({self.name} - {self.game_type} {self.small_blind}/{self.big_blind})>"

class PokerHand(db.Model):
    __tablename__ = 'poker_hand'
    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey('poker_table.id', ondelete='CASCADE'), nullable=False, index=True) # If table is deleted, hands are too
    hand_history = db.Column(JSON, nullable=False)
    board_cards = db.Column(JSON, nullable=True)
    pot_size_sats = db.Column(BigInteger, nullable=False, default=0)
    rake_sats = db.Column(BigInteger, nullable=False, default=0)
    start_time = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    end_time = db.Column(db.DateTime(timezone=True), nullable=True)
    winners = db.Column(JSON, nullable=True) # JSON field to store winner(s) info
    status = db.Column(db.String(50), nullable=False, default='pending_start', index=True)
    deck_state = db.Column(db.JSON, nullable=True)

    # Fields for tracking betting state within a hand
    current_turn_user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    current_bet_to_match = db.Column(db.BigInteger, default=0, nullable=False)
    player_street_investments = db.Column(JSON, nullable=True, default=lambda: {}) # Tracks {user_id: amount} for current street
    min_next_raise_amount = db.Column(db.BigInteger, nullable=True) # Minimum valid increment for the next raise
    last_raiser_user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True) # Tracks the last player who bet/raised

    # Relationships for ForeignKey fields
    current_turn_player = db.relationship('User', foreign_keys=[current_turn_user_id], backref=db.backref('poker_hands_current_turn', lazy='dynamic'))
    last_raiser = db.relationship('User', foreign_keys=[last_raiser_user_id], backref=db.backref('poker_hands_last_raised', lazy='dynamic'))


    def __repr__(self):
        return f"<PokerHand {self.id} (Table: {self.table_id}, Pot: {self.pot_size_sats}, Start: {self.start_time})>"

class PokerPlayerState(db.Model):
    __tablename__ = 'poker_player_state'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    table_id = db.Column(db.Integer, db.ForeignKey('poker_table.id', ondelete='CASCADE'), nullable=False, index=True) # If table is deleted, player states are too
    seat_id = db.Column(db.Integer, nullable=False)
    stack_sats = db.Column(BigInteger, nullable=False)
    is_sitting_out = db.Column(db.Boolean, default=False, nullable=False)
    is_active_in_hand = db.Column(db.Boolean, default=False, nullable=False)
    hole_cards = db.Column(JSON, nullable=True)
    last_action = db.Column(db.String(50), nullable=True)
    time_to_act_ends = db.Column(db.DateTime(timezone=True), nullable=True)
    total_invested_this_hand = db.Column(db.BigInteger, default=0, nullable=False) # Total amount invested by player in current hand
    joined_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship('User', back_populates='poker_states') # Assuming User.poker_states will be defined

    __table_args__ = (
        UniqueConstraint('user_id', 'table_id', name='uq_user_table'),
        UniqueConstraint('table_id', 'seat_id', name='uq_table_seat'),
        Index('ix_poker_player_state_user_table_seat', 'user_id', 'table_id', 'seat_id'),
    )

    def __repr__(self):
        return f"<PokerPlayerState {self.id} (User: {self.user_id}, Table: {self.table_id}, Seat: {self.seat_id}, Stack: {self.stack_sats})>"

class PlinkoDropLog(db.Model):
    __tablename__ = 'plinko_drop_log'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    stake_amount = db.Column(db.BigInteger, nullable=False)  # In satoshis
    chosen_stake_label = db.Column(db.String(50), nullable=False)
    slot_landed_label = db.Column(db.String(50), nullable=False)
    multiplier_applied = db.Column(db.Float, nullable=False)
    winnings_amount = db.Column(db.BigInteger, nullable=False, default=0)  # In satoshis
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    user = db.relationship('User', back_populates='plinko_drops') # Assuming User.plinko_drops will be defined

class TokenBlacklist(db.Model):
    __tablename__ = 'token_blacklist'
    
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(255), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    
    def __repr__(self):
        return f'<TokenBlacklist {self.jti}>'

class RouletteGame(db.Model):
    __tablename__ = 'roulette_game'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    bet_amount = db.Column(db.BigInteger, nullable=False)
    bet_type = db.Column(db.String(50), nullable=False)  # e.g., 'straight_up_0', 'red', 'even', 'column_1', 'dozen_1'
    winning_number = db.Column(db.Integer, nullable=True) # Nullable until wheel spins
    payout = db.Column(db.BigInteger, nullable=True) # Nullable until result
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Add this line
    user = db.relationship('User', backref=db.backref('roulette_games', lazy='dynamic'))

    def __repr__(self):
        return f'<RouletteGame {self.id} by User {self.user_id} - Bet: {self.bet_amount} on {self.bet_type}>'

# Baccarat Models
class BaccaratTable(db.Model):
    __tablename__ = 'baccarat_table'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    min_bet = db.Column(BigInteger, nullable=False)
    max_bet = db.Column(BigInteger, nullable=False)
    max_tie_bet = db.Column(BigInteger, nullable=False)
    commission_rate = db.Column(Numeric(5, 4), default=Decimal("0.05"), nullable=False) # e.g., 0.05 for 5%
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    hands = db.relationship('BaccaratHand', back_populates='table', lazy='dynamic')

    def __repr__(self):
        return f"<BaccaratTable {self.id} ({self.name})>"

class BaccaratHand(db.Model):
    __tablename__ = 'baccarat_hand'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    table_id = db.Column(db.Integer, db.ForeignKey('baccarat_table.id', ondelete='RESTRICT'), nullable=False, index=True) # Prevent table deletion if hands exist
    game_session_id = db.Column(db.Integer, db.ForeignKey('game_session.id', ondelete='CASCADE'), nullable=False, index=True) # Hands are part of a session
    initial_bet_player = db.Column(BigInteger, default=0, nullable=False)
    initial_bet_banker = db.Column(BigInteger, default=0, nullable=False)
    initial_bet_tie = db.Column(BigInteger, default=0, nullable=False)
    total_bet_amount = db.Column(BigInteger, nullable=False)
    win_amount = db.Column(BigInteger, default=0, nullable=False)
    player_cards = db.Column(JSON, nullable=True) # Store as list of strings e.g. ["H5", "C2"]
    banker_cards = db.Column(JSON, nullable=True) # Store as list of strings
    player_score = db.Column(db.Integer, nullable=True)
    banker_score = db.Column(db.Integer, nullable=True)
    outcome = db.Column(db.String(50), nullable=True, index=True) # e.g., "player_win", "banker_win", "tie"
    commission_paid = db.Column(BigInteger, default=0, nullable=False)
    status = db.Column(db.String(50), default='pending_bet', nullable=False, index=True) # e.g., "pending_bet", "dealing", "completed"
    details = db.Column(JSON, nullable=True) # For extra info like deck state, third-card reasons
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    user = db.relationship('User', back_populates='baccarat_hands')
    table = db.relationship('BaccaratTable', back_populates='hands')
    session = db.relationship('GameSession', back_populates='baccarat_hands')
    actions = db.relationship('BaccaratAction', back_populates='hand', lazy='dynamic')

    def __repr__(self):
        return f"<BaccaratHand {self.id} (User: {self.user_id}, Table: {self.table_id}, Status: {self.status})>"

class BaccaratAction(db.Model):
    __tablename__ = 'baccarat_action'
    id = db.Column(db.Integer, primary_key=True)
    baccarat_hand_id = db.Column(db.Integer, db.ForeignKey('baccarat_hand.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True) # User performing the action
    action_type = db.Column(db.String(50), nullable=False) # e.g., "place_bet", "player_draw", "banker_draw"
    bet_on_player = db.Column(BigInteger, nullable=True)
    bet_on_banker = db.Column(BigInteger, nullable=True)
    bet_on_tie = db.Column(BigInteger, nullable=True)
    action_details = db.Column(JSON, nullable=True) # e.g., card dealt, updated scores
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    hand = db.relationship('BaccaratHand', back_populates='actions')
    user = db.relationship('User', backref='baccarat_actions') # Simple backref as User might have many actions across games

    def __repr__(self):
        return f"<BaccaratAction {self.id} (Hand: {self.baccarat_hand_id}, User: {self.user_id}, Type: {self.action_type})>"


# Crystal Garden Models
class CrystalSeed(db.Model):
    __tablename__ = 'crystal_seed'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)
    cost = db.Column(db.Integer, nullable=False)
    potential_outcomes = db.Column(JSON, nullable=True)  # Describes potential crystal attributes

    # Relationships
    flowers_grown = db.relationship("CrystalFlower", back_populates="seed")

    def __repr__(self):
        return f"<CrystalSeed {self.name}>"

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'cost': self.cost,
            'potential_outcomes': self.potential_outcomes
        }

class PlayerGarden(db.Model):
    __tablename__ = 'player_garden'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), unique=True, nullable=False)  # One garden per user
    grid_size_x = db.Column(db.Integer, default=5, nullable=False)
    grid_size_y = db.Column(db.Integer, default=5, nullable=False)
    last_cycle_time = db.Column(DateTime, nullable=True)  # To track sun/moon cycle progression

    # Relationships
    user = db.relationship("User", back_populates="garden")
    flowers = db.relationship("CrystalFlower", back_populates="garden")

    def __repr__(self):
        return f"<PlayerGarden for User {self.user_id}>"

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'grid_size_x': self.grid_size_x,
            'grid_size_y': self.grid_size_y,
            'last_cycle_time': self.last_cycle_time.isoformat() if self.last_cycle_time else None
        }

class CrystalFlower(db.Model):
    __tablename__ = 'crystal_flower'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    crystal_seed_id = db.Column(db.Integer, db.ForeignKey('crystal_seed.id', ondelete='RESTRICT'), nullable=False) # Prevent seed deletion if flowers exist
    player_garden_id = db.Column(db.Integer, db.ForeignKey('player_garden.id', ondelete='CASCADE'), nullable=False)
    planted_at = db.Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    growth_stage = db.Column(db.String, nullable=False)  # e.g., 'seeded', 'sprouting', 'blooming', 'withered'
    color = db.Column(db.String, nullable=True)
    size = db.Column(Float, nullable=True)
    clarity = db.Column(Float, nullable=True)
    special_type = db.Column(db.String, nullable=True)
    appraised_value = db.Column(db.Integer, nullable=True)
    position_x = db.Column(db.Integer, nullable=False)  # Position in the garden grid
    position_y = db.Column(db.Integer, nullable=False)  # Position in the garden grid
    active_power_ups = db.Column(db.JSON, nullable=True, default=lambda: [])

    # Relationships
    user = db.relationship("User", back_populates="crystal_flowers")
    seed = db.relationship("CrystalSeed", back_populates="flowers_grown")
    garden = db.relationship("PlayerGarden", back_populates="flowers")

    def __repr__(self):
        return f"<CrystalFlower {self.id} (Seed: {self.crystal_seed_id})>"

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'crystal_seed_id': self.crystal_seed_id,
            'player_garden_id': self.player_garden_id,
            'planted_at': self.planted_at.isoformat() if self.planted_at else None,
            'growth_stage': self.growth_stage,
            'color': self.color,
            'size': self.size,
            'clarity': self.clarity,
            'special_type': self.special_type,
            'appraised_value': self.appraised_value,
            'position_x': self.position_x,
            'position_y': self.position_y,
            'active_power_ups': self.active_power_ups if self.active_power_ups is not None else []
        }

class CrystalCodexEntry(db.Model):
    __tablename__ = 'crystal_codex_entry'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    crystal_name = db.Column(db.String, nullable=False)  # e.g., "Large Blue Sapphire"
    color = db.Column(db.String, nullable=False)
    size = db.Column(Float, nullable=False)
    clarity = db.Column(Float, nullable=False)
    special_type = db.Column(db.String, nullable=True)
    first_discovered_at = db.Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    notes = db.Column(db.String, nullable=True)  # Player's personal notes or game-generated lore

    # Relationships
    user = db.relationship("User", back_populates="codex_entries")

    def __repr__(self):
        return f"<CrystalCodexEntry {self.crystal_name} for User {self.user_id}>"

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'crystal_name': self.crystal_name,
            'color': self.color,
            'size': self.size,
            'clarity': self.clarity,
            'special_type': self.special_type,
            'first_discovered_at': self.first_discovered_at.isoformat() if self.first_discovered_at else None,
            'notes': self.notes
        }
