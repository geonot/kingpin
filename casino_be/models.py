from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from passlib.hash import pbkdf2_sha256 as sha256
from sqlalchemy import BigInteger, Index, JSON, UniqueConstraint

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    balance = db.Column(BigInteger, default=0, nullable=False, index=True)
    deposit_wallet_address = db.Column(db.String(255), unique=True, nullable=True, index=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def check_password(self, password):
        return sha256.verify(password, self.password)

    @staticmethod
    def hash_password(password):
        return sha256.hash(password)

    def __repr__(self):
        return f"<User {self.username}>"

class GameSession(db.Model):
    __tablename__ = 'game_session'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    slot_id = db.Column(db.Integer, db.ForeignKey('slot.id'), nullable=True, index=True)
    table_id = db.Column(db.Integer, db.ForeignKey('blackjack_table.id'), nullable=True, index=True)
    poker_table_id = db.Column(db.Integer, db.ForeignKey('poker_table.id'), nullable=True, index=True)
    game_type = db.Column(db.String(50), nullable=False, index=True)
    bonus_active = db.Column(db.Boolean, default=False, nullable=False)
    bonus_spins_remaining = db.Column(db.Integer, default=0, nullable=False)
    bonus_multiplier = db.Column(db.Float, default=1.0, nullable=False)
    amount_wagered = db.Column(BigInteger, default=0, nullable=False)
    amount_won = db.Column(BigInteger, default=0, nullable=False)
    num_spins = db.Column(db.Integer, default=0, nullable=False)
    session_start = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    session_end = db.Column(db.DateTime(timezone=True), nullable=True)

    user = db.relationship('User', backref='game_sessions')
    slot = db.relationship('Slot', backref='game_sessions')
    blackjack_table = db.relationship('BlackjackTable', backref='game_sessions')
    poker_table = db.relationship('PokerTable', backref='game_sessions')

    def __repr__(self):
        return f"<GameSession {self.id} (User: {self.user_id}, Type: {self.game_type})>"

class SlotSpin(db.Model):
    __tablename__ = 'slot_spin'
    id = db.Column(db.Integer, primary_key=True)
    game_session_id = db.Column(db.Integer, db.ForeignKey('game_session.id'), nullable=False, index=True)
    spin_result = db.Column(JSON, nullable=False)
    win_amount = db.Column(BigInteger, nullable=False)
    bet_amount = db.Column(BigInteger, nullable=False)
    is_bonus_spin = db.Column(db.Boolean, default=False, nullable=False)
    spin_time = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    game_session = db.relationship('GameSession', backref='slot_spins')

    def __repr__(self):
        return f"<SlotSpin {self.id} (Session: {self.game_session_id}, Bet: {self.bet_amount}, Win: {self.win_amount})>"

class Transaction(db.Model):
    __tablename__ = 'transaction'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    amount = db.Column(BigInteger, nullable=False)
    transaction_type = db.Column(db.String(50), nullable=False, index=True)
    status = db.Column(db.String(50), default='pending', nullable=False, index=True)
    details = db.Column(JSON, nullable=True)
    slot_spin_id = db.Column(db.Integer, db.ForeignKey('slot_spin.id'), nullable=True, index=True)
    blackjack_hand_id = db.Column(db.Integer, db.ForeignKey('blackjack_hand.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship('User', backref='transactions')
    slot_spin = db.relationship('SlotSpin', backref='transactions')
    blackjack_hand = db.relationship('BlackjackHand', backref='transactions')

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
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    symbols = db.relationship('SlotSymbol', backref='slot', lazy='select')
    bets = db.relationship('SlotBet', backref='slot', lazy='select')

    def __repr__(self):
        return f"<Slot {self.id} ({self.short_name})>"

class SlotSymbol(db.Model):
    __tablename__ = 'slot_symbol'
    id = db.Column(db.Integer, primary_key=True)
    slot_id = db.Column(db.Integer, db.ForeignKey('slot.id'), nullable=False, index=True)
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
    slot_id = db.Column(db.Integer, db.ForeignKey('slot.id'), nullable=False, index=True)
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
    max_bet = db.Column(BigInteger, nullable=False)
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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    table_id = db.Column(db.Integer, db.ForeignKey('blackjack_table.id'), nullable=False, index=True)
    session_id = db.Column(db.Integer, db.ForeignKey('game_session.id'), nullable=False, index=True)
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

    user = db.relationship('User', backref='blackjack_hands')
    session = db.relationship('GameSession', backref='blackjack_hands')
    actions = db.relationship('BlackjackAction', backref='hand', lazy='dynamic')

    def __repr__(self):
        return f"<BlackjackHand {self.id} (User: {self.user_id}, Bet: {self.initial_bet}, Status: {self.status})>"

class BlackjackAction(db.Model):
    __tablename__ = 'blackjack_action'
    id = db.Column(db.Integer, primary_key=True)
    hand_id = db.Column(db.Integer, db.ForeignKey('blackjack_hand.id'), nullable=False, index=True)
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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    bonus_code_id = db.Column(db.Integer, db.ForeignKey('bonus_code.id'), nullable=False, index=True)
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
    user = db.relationship('User', backref='user_bonuses')

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
    game_start_time = db.Column(db.DateTime(timezone=True), nullable=True)
    game_end_time = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    bets = db.relationship('SpacecrashBet', backref='game', lazy='dynamic')

    def __repr__(self):
        return f"<SpacecrashGame {self.id} (Status: {self.status}, Crash: {self.crash_point})>"

class SpacecrashBet(db.Model):
    __tablename__ = 'spacecrash_bet'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    game_id = db.Column(db.Integer, db.ForeignKey('spacecrash_game.id'), nullable=False, index=True)
    bet_amount = db.Column(BigInteger, nullable=False)
    auto_eject_at = db.Column(db.Float, nullable=True)
    ejected_at = db.Column(db.Float, nullable=True)
    win_amount = db.Column(BigInteger, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='placed', index=True)
    placed_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship('User', backref=db.backref('spacecrash_bets', lazy='dynamic'))

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
    max_buy_in = db.Column(BigInteger, nullable=False)
    max_seats = db.Column(db.Integer, nullable=False, default=9)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    hands = db.relationship('PokerHand', backref='table', lazy='dynamic')
    player_states = db.relationship('PokerPlayerState', backref='table', lazy='dynamic')

    def __repr__(self):
        return f"<PokerTable {self.id} ({self.name} - {self.game_type} {self.small_blind}/{self.big_blind})>"

class PokerHand(db.Model):
    __tablename__ = 'poker_hand'
    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey('poker_table.id'), nullable=False, index=True)
    hand_history = db.Column(JSON, nullable=False)
    board_cards = db.Column(JSON, nullable=True)
    pot_size_sats = db.Column(BigInteger, nullable=False, default=0)
    rake_sats = db.Column(BigInteger, nullable=False, default=0)
    start_time = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    end_time = db.Column(db.DateTime(timezone=True), nullable=True)
    winners = db.Column(JSON, nullable=True)

    def __repr__(self):
        return f"<PokerHand {self.id} (Table: {self.table_id}, Pot: {self.pot_size_sats}, Start: {self.start_time})>"

class PokerPlayerState(db.Model):
    __tablename__ = 'poker_player_state'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    table_id = db.Column(db.Integer, db.ForeignKey('poker_table.id'), nullable=False, index=True)
    seat_id = db.Column(db.Integer, nullable=False)
    stack_sats = db.Column(BigInteger, nullable=False)
    is_sitting_out = db.Column(db.Boolean, default=False, nullable=False)
    is_active_in_hand = db.Column(db.Boolean, default=False, nullable=False)
    hole_cards = db.Column(JSON, nullable=True)
    last_action = db.Column(db.String(50), nullable=True)
    time_to_act_ends = db.Column(db.DateTime(timezone=True), nullable=True)
    joined_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship('User', backref='poker_states')

    __table_args__ = (
        UniqueConstraint('user_id', 'table_id', name='uq_user_table'),
        UniqueConstraint('table_id', 'seat_id', name='uq_table_seat'),
        Index('ix_poker_player_state_user_table_seat', 'user_id', 'table_id', 'seat_id'),
    )

    def __repr__(self):
        return f"<PokerPlayerState {self.id} (User: {self.user_id}, Table: {self.table_id}, Seat: {self.seat_id}, Stack: {self.stack_sats})>"
