from marshmallow import Schema, fields, validate, ValidationError, pre_load, validates
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field # For easier model mapping
from marshmallow.validate import OneOf, Range, Length, Email, Regexp
from datetime import datetime, timezone
import re

from models import db, User, GameSession, SlotSpin, Transaction, BonusCode, Slot, SlotSymbol, SlotBet, BlackjackTable, BlackjackHand, BlackjackAction # Import models

# --- Helper ---
def validate_password(password):
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", password):
        raise ValidationError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise ValidationError("Password must contain at least one lowercase letter.")
    if not re.search(r"[0-9]", password):
        raise ValidationError("Password must contain at least one number.")
    if not re.search(r"[!@#$%^&*()_+=\-[\]{};':\"\\|,.<>/?~`]", password):
        raise ValidationError("Password must contain at least one special character.")

# --- Base Schemas (for pagination etc.) ---
class PaginationSchema(Schema):
    page = fields.Int(dump_only=True)
    pages = fields.Int(dump_only=True)
    per_page = fields.Int(dump_only=True)
    total = fields.Int(dump_only=True)

# --- User Schemas ---
class UserSchema(SQLAlchemyAutoSchema):
    # Schema for general user data exposure (sensitive fields excluded)
    class Meta:
        model = User
        load_instance = True
        sqla_session = db.session
        # Exclude sensitive fields
        exclude = ("password", "deposit_wallet_private_key", "transactions", "game_sessions")

    id = auto_field(dump_only=True)
    username = auto_field()
    email = auto_field()
    balance = auto_field(description="Balance in Satoshis") # Keep as integer
    deposit_wallet_address = auto_field(dump_only=True)
    is_admin = auto_field(dump_only=True)
    is_active = auto_field(dump_only=True)
    created_at = auto_field(dump_only=True)
    last_login_at = auto_field(dump_only=True)

    # Example custom field: balance in BTC (string for display)
    balance_btc = fields.Method("get_balance_btc", dump_only=True, description="Balance in BTC (display only)")

    def get_balance_btc(self, obj):
        # Avoid division by zero
        factor = 100_000_000
        if factor == 0: return "0.00000000"
        # Format to 8 decimal places
        return f"{obj.balance / factor:.8f}"

class AdminUserSchema(UserSchema):
     # Schema for admin viewing user details (includes potentially more info)
    class Meta(UserSchema.Meta):
        exclude = ("password", "deposit_wallet_private_key") # Still exclude private key
        # Include relationships if needed for admin view
        # include_relationships = True

    # Include relationships explicitly if needed
    transactions = fields.Nested('TransactionSchema', many=True, dump_only=True)
    game_sessions = fields.Nested('GameSessionSchema', many=True, dump_only=True)


class RegisterSchema(Schema):
    username = fields.Str(required=True, validate=[
        Length(min=3, max=50),
        Regexp(r'^[a-zA-Z0-9_]+$', error="Username must contain only letters, numbers, and underscores.")
    ])
    email = fields.Email(required=True, validate=Length(max=120))
    password = fields.Str(required=True, validate=validate_password) # Use custom validator

class LoginSchema(Schema):
    username = fields.Str(required=True)
    password = fields.Str(required=True)

class UpdateSettingsSchema(Schema):
    # Allow partial updates
    email = fields.Email(validate=Length(max=120))
    password = fields.Str(validate=validate_password, load_default=None) # Optional password update

    @pre_load
    def remove_empty(self, data, **kwargs):
        # Remove password field if it's empty string, so validation isn't triggered unnecessarily
        if 'password' in data and not data['password']:
            del data['password']
        return data

class UserListSchema(PaginationSchema):
    items = fields.Nested(UserSchema, many=True, dump_only=True)

# --- Game Schemas ---
class JoinGameSchema(Schema):
    slot_id = fields.Int(required=False, validate=Range(min=1))
    table_id = fields.Int(required=False, validate=Range(min=1))
    game_type = fields.Str(required=True, validate=OneOf(['slot', 'blackjack']))

class GameSessionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = GameSession
        load_instance = True
        sqla_session = db.session
        # Exclude relationships by default unless needed
        exclude = ("slot_spins", "blackjack_hands")

    id = auto_field(dump_only=True)
    user_id = auto_field(dump_only=True)
    slot_id = auto_field(dump_only=True)
    table_id = auto_field(dump_only=True)
    game_type = auto_field(dump_only=True)
    bonus_active = auto_field(dump_only=True)
    bonus_spins_remaining = auto_field(dump_only=True)
    bonus_multiplier = auto_field(dump_only=True)
    amount_wagered = auto_field(dump_only=True, description="Total wagered in Satoshis")
    amount_won = auto_field(dump_only=True, description="Total won in Satoshis")
    num_spins = auto_field(dump_only=True)
    session_start = auto_field(dump_only=True)
    session_end = auto_field(dump_only=True)
    # Include related slot info if useful
    slot = fields.Nested('SlotBasicSchema', dump_only=True) # Basic info
    blackjack_table = fields.Nested('BlackjackTableBasicSchema', dump_only=True) # Basic info

class SpinRequestSchema(Schema):
    bet_amount = fields.Int(required=True, validate=Range(min=1), description="Bet amount in Satoshis")
    # game_session_id is no longer needed, derived from user's active session

class SpinSchema(Schema):
    # Represents the data stored for a spin (part of SlotSpin)
    bet_amount = fields.Int(required=True, description="Bet amount in Satoshis")
    win_amount = fields.Int(required=True, description="Win amount in Satoshis")
    spin_result = fields.List(fields.List(fields.Int()), required=True)
    winning_lines = fields.List(fields.Dict(), required=False, allow_none=True) # Detailed win lines info
    is_bonus_spin = fields.Bool(required=True)

class SlotSpinSchema(SQLAlchemyAutoSchema):
     class Meta:
        model = SlotSpin
        load_instance = True
        sqla_session = db.session

     id = auto_field(dump_only=True)
     game_session_id = auto_field(dump_only=True)
     spin_result = auto_field()
     win_amount = auto_field(description="Win amount in Satoshis")
     bet_amount = auto_field(description="Bet amount in Satoshis")
     is_bonus_spin = auto_field(dump_only=True)
     spin_time = auto_field(dump_only=True)

# --- Transaction Schemas ---
class WithdrawSchema(Schema):
    amount_sats = fields.Int(required=True, validate=Range(min=1), data_key="amount", description="Amount to withdraw in Satoshis") # Use data_key if frontend sends 'amount'
    withdraw_wallet_address = fields.Str(required=True, validate=Length(min=26, max=62)) # Basic Bitcoin address length validation

class DepositSchema(Schema):
    # Primarily for bonus code application during deposit flow
    bonus_code = fields.Str(required=False, validate=Length(min=1, max=50))

class BalanceTransferSchema(Schema):
    from_user_id = fields.Int(required=False, allow_none=True, description="Source User ID (null for system)")
    to_user_id = fields.Int(required=True, description="Destination User ID")
    amount_sats = fields.Int(required=True, validate=lambda x: x != 0, description="Amount in Satoshis (positive for credit, negative for debit from system)")
    description = fields.Str(required=False, validate=Length(max=255), load_default="Admin balance transfer")
    transaction_type = fields.Str(load_default='transfer', validate=OneOf(['transfer', 'credit', 'debit', 'adjustment', 'bonus']))


class TransactionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Transaction
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)
    user_id = auto_field(dump_only=True)
    amount = auto_field(description="Transaction amount in Satoshis (can be negative)")
    transaction_type = auto_field()
    status = auto_field()
    details = auto_field()
    created_at = auto_field(dump_only=True)
    # Include basic user info
    user = fields.Nested(lambda: UserSchema(only=("id", "username")), dump_only=True)


class TransactionListSchema(PaginationSchema):
    items = fields.Nested(TransactionSchema, many=True, dump_only=True)


# --- Slot Schemas ---
class SlotSymbolSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = SlotSymbol
        load_instance = True
        sqla_session = db.session
        exclude = ("slot",) # Avoid circular ref

    id = auto_field(dump_only=True)
    symbol_internal_id = auto_field(description="ID used within the slot (1, 2, ...)")
    name = auto_field()
    img_link = auto_field()
    value_multiplier = auto_field()
    data = auto_field()

class SlotBetSchema(SQLAlchemyAutoSchema):
     class Meta:
        model = SlotBet
        load_instance = True
        sqla_session = db.session
        exclude = ("slot",) # Avoid circular ref

     id = auto_field(dump_only=True)
     bet_amount = auto_field(description="Allowed bet amount in Satoshis")

class SlotBasicSchema(SQLAlchemyAutoSchema):
     # Minimal schema for nesting inside GameSession etc.
     class Meta:
        model = Slot
        load_instance = True
        sqla_session = db.session
        only = ("id", "name", "short_name", "description")

     id = auto_field(dump_only=True)
     name = auto_field()
     short_name = auto_field()
     description = auto_field()


class SlotSchema(SQLAlchemyAutoSchema):
    # Full schema for slot details view or /api/slots endpoint
    class Meta:
        model = Slot
        load_instance = True
        sqla_session = db.session
        # Eager loaded relationships are included by default if lazy='joined'
        # exclude = () # Exclude specific fields if needed

    id = auto_field(dump_only=True)
    name = auto_field()
    description = auto_field()
    num_rows = auto_field()
    num_columns = auto_field()
    num_symbols = auto_field(description="Total distinct symbols defined")
    wild_symbol_id = auto_field(description="Internal ID of the Wild symbol")
    scatter_symbol_id = auto_field(description="Internal ID of the Scatter symbol")
    bonus_type = auto_field()
    bonus_subtype = auto_field()
    bonus_multiplier = auto_field(description="Multiplier during bonus rounds")
    bonus_spins_trigger_count = auto_field(description="Number of scatters to trigger bonus")
    bonus_spins_awarded = auto_field(description="Number of free spins awarded")
    short_name = auto_field()
    asset_directory = auto_field()
    rtp = auto_field()
    volatility = auto_field()
    is_active = auto_field()
    created_at = auto_field(dump_only=True)

    # Include nested symbols and bets
    symbols = fields.Nested(SlotSymbolSchema, many=True, dump_only=True)
    bets = fields.Nested(SlotBetSchema, many=True, dump_only=True)

# --- Bonus Code Schemas ---
class BonusCodeSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = BonusCode
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)
    code_id = auto_field(required=True, validate=[
        Length(min=3, max=50),
        Regexp(r'^[A-Z0-9]+$', error="Code must be uppercase letters and numbers only.")
    ])
    description = auto_field(validate=Length(max=500))
    type = auto_field(required=True, validate=validate.OneOf(['deposit', 'registration', 'free_spins', 'other']))
    subtype = auto_field(required=True, validate=validate.OneOf(['percentage', 'fixed', 'spins']))
    # Amount validation happens in the route based on subtype
    amount = fields.Float(required=True, description="Percentage value (e.g., 10.5 for 10.5%) or fixed Satoshi amount")
    max_uses = fields.Int(allow_none=True, validate=Range(min=1))
    uses_remaining = fields.Int(dump_only=True, allow_none=True)
    expires_at = fields.DateTime(allow_none=True)
    is_active = fields.Bool(load_default=True)
    created_at = auto_field(dump_only=True)

    # Add validation for code_id uniqueness on create
    @validates('code_id')
    def validate_code_id_unique(self, value):
        # Check uniqueness only if context indicates creation
        if self.context.get('check_unique'):
            existing = BonusCode.query.filter(BonusCode.code_id == value.strip().upper()).first()
            if existing:
                raise ValidationError(f"Bonus code '{value}' already exists.")

    @pre_load
    def normalize_code_id(self, data, **kwargs):
        if 'code_id' in data and isinstance(data['code_id'], str):
            data['code_id'] = data['code_id'].strip().upper()
        return data


class BonusCodeListSchema(PaginationSchema):
    items = fields.Nested(BonusCodeSchema, many=True, dump_only=True)

# --- WinLine Schema (For Spin Response) ---
class WinLineSchema(Schema):
    line_index = fields.Field(required=True, description="Payline index (integer) or 'scatter'")
    symbol_id = fields.Int(required=True, description="Internal ID of the winning symbol")
    count = fields.Int(required=True, description="Number of matching symbols")
    positions = fields.List(fields.List(fields.Int()), required=True, description="List of [row, col] positions")
    win_amount = fields.Int(required=True, description="Win amount for this line in Satoshis")

# --- Blackjack Schemas ---
class BlackjackTableBasicSchema(SQLAlchemyAutoSchema):
    # Minimal schema for nesting inside GameSession etc.
    class Meta:
        model = BlackjackTable
        load_instance = True
        sqla_session = db.session
        only = ("id", "name", "description", "min_bet", "max_bet")

    id = auto_field(dump_only=True)
    name = auto_field()
    description = auto_field()
    min_bet = auto_field(description="Minimum bet in Satoshis")
    max_bet = auto_field(description="Maximum bet in Satoshis")

class BlackjackTableSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = BlackjackTable
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)
    name = auto_field()
    description = auto_field()
    min_bet = auto_field(description="Minimum bet in Satoshis")
    max_bet = auto_field(description="Maximum bet in Satoshis")
    deck_count = auto_field()
    rules = auto_field()
    is_active = auto_field()
    created_at = auto_field(dump_only=True)
    updated_at = auto_field(dump_only=True)

class BlackjackCardSchema(Schema):
    suit = fields.Str(required=True, validate=OneOf(['hearts', 'diamonds', 'clubs', 'spades']))
    value = fields.Str(required=True, validate=OneOf(['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']))
    is_face_down = fields.Bool(required=False, default=False)

class BlackjackHandDataSchema(Schema):
    cards = fields.Nested(BlackjackCardSchema, many=True, required=True)
    total = fields.Int(required=True)
    is_busted = fields.Bool(required=True)
    is_blackjack = fields.Bool(required=True)
    is_doubled = fields.Bool(required=False, default=False)
    is_split = fields.Bool(required=False, default=False)
    result = fields.Str(required=False, validate=OneOf(['win', 'lose', 'push', 'blackjack']))

class BlackjackHandSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = BlackjackHand
        load_instance = True
        sqla_session = db.session
        exclude = ("actions",)

    id = auto_field(dump_only=True)
    user_id = auto_field(dump_only=True)
    table_id = auto_field(dump_only=True)
    session_id = auto_field(dump_only=True)
    initial_bet = auto_field(description="Initial bet in Satoshis")
    total_bet = auto_field(description="Total bet in Satoshis (includes doubles, splits)")
    win_amount = auto_field(description="Win amount in Satoshis")
    player_cards = auto_field()
    dealer_cards = auto_field()
    player_hands = auto_field()
    dealer_hand = auto_field()
    status = auto_field()
    result = auto_field()
    created_at = auto_field(dump_only=True)
    updated_at = auto_field(dump_only=True)
    completed_at = auto_field(dump_only=True)

    # Include related data
    table = fields.Nested(BlackjackTableBasicSchema, dump_only=True)
    user = fields.Nested(lambda: UserSchema(only=("id", "username")), dump_only=True)

class BlackjackActionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = BlackjackAction
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)
    hand_id = auto_field(dump_only=True)
    action_type = auto_field(validate=OneOf(['hit', 'stand', 'double', 'split']))
    hand_index = auto_field()
    card_dealt = auto_field()
    hand_total = auto_field()
    created_at = auto_field(dump_only=True)

class JoinBlackjackSchema(Schema):
    table_id = fields.Int(required=True, validate=Range(min=1))
    bet_amount = fields.Int(required=True, validate=Range(min=1), description="Bet amount in Satoshis")

class BlackjackActionRequestSchema(Schema):
    hand_id = fields.Int(required=True, validate=Range(min=1))
    action_type = fields.Str(required=True, validate=OneOf(['hit', 'stand', 'double', 'split']))
    hand_index = fields.Int(required=True, validate=Range(min=0), default=0)
