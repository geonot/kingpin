from marshmallow import Schema, fields, validate, ValidationError, pre_load, validates, validates_schema
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field # For easier model mapping
from marshmallow.validate import OneOf, Range, Length, Email, Regexp
from datetime import datetime, timezone
import re

# Updated import to include Poker models
from .models import (
    db, User, GameSession, SlotSpin, Transaction, BonusCode, Slot, SlotSymbol, SlotBet,
    BlackjackTable, BlackjackHand, BlackjackAction, UserBonus, # UserBonus was missing, added back
    PokerTable, PokerHand, PokerPlayerState # Poker models
)


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
        # Explicitly list fields to include, excluding sensitive ones
        # This also helps avoid issues with fields that might have been removed from model but linger in some cache/introspection
        only = (
            "id", "username", "email", "balance", "deposit_wallet_address",
            "is_admin", "is_active", "created_at", "last_login_at", "balance_btc"
        )
        # exclude = ("password", "deposit_wallet_private_key", "transactions", "game_sessions") # Keep for reference

    id = auto_field(dump_only=True)
    username = auto_field()
    email = auto_field()
    balance = auto_field(metadata={"description": "Balance in Satoshis"}) # Keep as integer
    deposit_wallet_address = auto_field(dump_only=True)
    is_admin = auto_field(dump_only=True)
    is_active = auto_field(dump_only=True)
    created_at = auto_field(dump_only=True)
    last_login_at = auto_field(dump_only=True)

    # Example custom field: balance in BTC (string for display)
    balance_btc = fields.Method("get_balance_btc", dump_only=True, metadata={"description": "Balance in BTC (display only)"})

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
    slot_id = auto_field(allow_none=True, dump_only=True)
    table_id = auto_field(allow_none=True, dump_only=True) # For Blackjack
    poker_table_id = fields.Int(allow_none=True, dump_only=True) # ADDED for Poker
    game_type = auto_field(dump_only=True)
    bonus_active = auto_field(dump_only=True)
    bonus_spins_remaining = auto_field(dump_only=True)
    bonus_multiplier = auto_field(dump_only=True)
    amount_wagered = auto_field(dump_only=True, metadata={"description": "Total wagered in Satoshis"})
    amount_won = auto_field(dump_only=True, metadata={"description": "Total won in Satoshis"})
    num_spins = auto_field(dump_only=True)
    session_start = auto_field(dump_only=True)
    session_end = auto_field(dump_only=True)
    # Include related slot info if useful
    slot = fields.Nested('SlotBasicSchema', dump_only=True, allow_none=True) 
    blackjack_table = fields.Nested('BlackjackTableBasicSchema', dump_only=True, allow_none=True)
    # ADDED PokerTable relation to GameSessionSchema
    poker_table = fields.Nested(
        lambda: PokerTableSchema(
            only=("id", "name", "game_type", "limit_type", "small_blind", "big_blind", "max_seats"),
            allow_none=True
        ), 
        dump_only=True, 
        allow_none=True
    )

class SpinRequestSchema(Schema):
    bet_amount = fields.Int(required=True, validate=Range(min=1), metadata={"description": "Bet amount in Satoshis"})
    # game_session_id is no longer needed, derived from user's active session

class SpinSchema(Schema):
    # Represents the data stored for a spin (part of SlotSpin)
    bet_amount = fields.Int(required=True, metadata={"description": "Bet amount in Satoshis"})
    win_amount = fields.Int(required=True, metadata={"description": "Win amount in Satoshis"})
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
     win_amount = auto_field(metadata={"description": "Win amount in Satoshis"})
     bet_amount = auto_field(metadata={"description": "Bet amount in Satoshis"})
     is_bonus_spin = auto_field(dump_only=True)
     spin_time = auto_field(dump_only=True)

# --- Transaction Schemas ---
class WithdrawSchema(Schema):
    amount_sats = fields.Int(required=True, validate=Range(min=1), data_key="amount", metadata={"description": "Amount to withdraw in Satoshis"}) # Use data_key if frontend sends 'amount'
    withdraw_wallet_address = fields.Str(required=True, validate=Length(min=26, max=62)) # Basic Bitcoin address length validation

class DepositSchema(Schema):
    # Primarily for bonus code application during deposit flow
    bonus_code = fields.Str(required=False, validate=Length(min=1, max=50))
    deposit_amount_sats = fields.Integer(required=True, validate=Range(min=1), metadata={"description": "The amount of the deposit in Satoshis."})

class BalanceTransferSchema(Schema):
    from_user_id = fields.Int(required=False, allow_none=True, metadata={"description": "Source User ID (null for system)"})
    to_user_id = fields.Int(required=True, metadata={"description": "Destination User ID"})
    amount_sats = fields.Int(required=True, validate=lambda x: x != 0, metadata={"description": "Amount in Satoshis (positive for credit, negative for debit from system)"})
    description = fields.Str(required=False, validate=Length(max=255), load_default="Admin balance transfer")
    transaction_type = fields.Str(load_default='transfer', validate=OneOf(['transfer', 'credit', 'debit', 'adjustment', 'bonus']))


class TransactionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Transaction
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)
    user_id = auto_field(dump_only=True)
    amount = auto_field(metadata={"description": "Transaction amount in Satoshis (can be negative)"})
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
    symbol_internal_id = auto_field(metadata={"description": "ID used within the slot (1, 2, ...)"})
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
     bet_amount = auto_field(metadata={"description": "Allowed bet amount in Satoshis"})

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
    num_symbols = auto_field(metadata={"description": "Total distinct symbols defined"})
    wild_symbol_id = fields.Int(dump_only=True, allow_none=True, metadata={"description": "Internal ID of the Wild symbol, from gameConfig.json"})
    scatter_symbol_id = fields.Int(dump_only=True, allow_none=True, metadata={"description": "Internal ID of the Scatter symbol, from gameConfig.json"})
    bonus_type = auto_field()
    bonus_subtype = auto_field()
    bonus_multiplier = auto_field(metadata={"description": "Multiplier during bonus rounds"})
    bonus_spins_trigger_count = auto_field(metadata={"description": "Number of scatters to trigger bonus"})
    bonus_spins_awarded = auto_field(metadata={"description": "Number of free spins awarded"})
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
    description = auto_field(validate=Length(max=500)) # Marshmallow-SQLAlchemy auto_field might not directly take 'description'.
                                                     # If 'description' is a model field, its description comes from the model.
                                                     # For Schema-level description, use metadata on the field if not auto-generated.
    type = auto_field(required=True, validate=validate.OneOf(['deposit', 'registration', 'free_spins', 'other']))
    subtype = auto_field(required=True, validate=validate.OneOf(['percentage', 'fixed', 'spins']))
    amount = fields.Float(required=False, allow_none=True, metadata={"description": "Percentage value (e.g., 10.5 for 10.5%) for 'percentage' subtype. Not for 'fixed' or 'spins'."})
    amount_sats = fields.Integer(required=False, allow_none=True, validate=Range(min=1), metadata={"description": "Fixed Satoshi amount for 'fixed' subtype bonus codes."})
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

    @validates_schema
    def validate_amount_based_on_subtype(self, data, **kwargs):
        subtype = data.get('subtype')
        amount = data.get('amount')
        amount_sats = data.get('amount_sats')

        if subtype == 'fixed':
            if amount_sats is None:
                raise ValidationError("amount_sats is required and must be a positive integer for 'fixed' subtype.", "amount_sats")
            if amount is not None:
                raise ValidationError("amount should not be provided for 'fixed' subtype.", "amount")
            if amount_sats is not None and amount_sats <= 0: # validate=Range(min=1) should cover this
                 raise ValidationError("amount_sats must be a positive integer for 'fixed' subtype.", "amount_sats")

        elif subtype == 'percentage':
            if amount is None:
                raise ValidationError("amount is required and must be a positive value for 'percentage' subtype.", "amount")
            if amount_sats is not None:
                raise ValidationError("amount_sats should not be provided for 'percentage' subtype.", "amount_sats")
            if amount is not None and amount <= 0:
                 raise ValidationError("amount must be a positive value for 'percentage' subtype.", "amount")

        elif subtype == 'spins':
            # For 'spins', amount & amount_sats are optional.
            # If provided, they should be positive.
            if amount is not None and amount <= 0:
                raise ValidationError("If 'amount' is provided for 'spins' subtype, it must be positive.", "amount")
            if amount_sats is not None and amount_sats <= 0: # validate=Range(min=1) should cover this
                raise ValidationError("If 'amount_sats' is provided for 'spins' subtype, it must be a positive integer.", "amount_sats")
        return data


class BonusCodeListSchema(PaginationSchema):
    items = fields.Nested(BonusCodeSchema, many=True, dump_only=True)

# --- Admin Schemas ---
class AdminCreditDepositSchema(Schema):
    user_id = fields.Int(required=True)
    amount_sats = fields.Int(required=True, validate=Range(min=1))
    external_tx_id = fields.Str(required=False, allow_none=True, validate=Length(max=256)) # e.g., Bitcoin transaction hash
    admin_notes = fields.Str(required=False, allow_none=True, validate=Length(max=500))

class UserBonusSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = UserBonus # Ensure UserBonus model is imported
        load_instance = True
        sqla_session = db.session
        include_relationships = True

    id = auto_field(dump_only=True)
    user_id = auto_field()
    bonus_code_id = auto_field()

    bonus_amount_awarded_sats = auto_field()
    wagering_requirement_multiplier = auto_field()
    wagering_requirement_sats = auto_field()
    wagering_progress_sats = auto_field()

    is_active = auto_field()
    is_completed = auto_field()
    is_cancelled = auto_field()

    activated_at = auto_field(dump_only=True)
    updated_at = auto_field(dump_only=True)
    completed_at = auto_field(dump_only=True)
    cancelled_at = auto_field(dump_only=True)

    user = fields.Nested(lambda: UserSchema(only=("id", "username")), dump_only=True)
    bonus_code = fields.Nested(lambda: BonusCodeSchema(exclude=("applications", "description")), dump_only=True)

# --- WinLine Schema (For Spin Response) ---
class WinLineSchema(Schema):
    line_index = fields.Field(required=True, metadata={"description": "Payline index (integer) or 'scatter'"})
    symbol_id = fields.Int(required=True, metadata={"description": "Internal ID of the winning symbol"})
    count = fields.Int(required=True, metadata={"description": "Number of matching symbols"})
    positions = fields.List(fields.List(fields.Int()), required=True, metadata={"description": "List of [row, col] positions"})
    win_amount = fields.Int(required=True, metadata={"description": "Win amount for this line in Satoshis"})

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
    description = auto_field() # Assuming description is a model field
    min_bet = auto_field(metadata={"description": "Minimum bet in Satoshis"})
    max_bet = auto_field(metadata={"description": "Maximum bet in Satoshis"})

class BlackjackTableSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = BlackjackTable
        load_instance = True
        sqla_session = db.session

    id = auto_field(dump_only=True)
    name = auto_field()
    description = auto_field() # Assuming description is a model field
    min_bet = auto_field(metadata={"description": "Minimum bet in Satoshis"})
    max_bet = auto_field(metadata={"description": "Maximum bet in Satoshis"})
    deck_count = auto_field()
    rules = auto_field()
    is_active = auto_field()
    created_at = auto_field(dump_only=True)
    updated_at = auto_field(dump_only=True)

class BlackjackCardSchema(Schema):
    suit = fields.Str(required=True, validate=OneOf(['hearts', 'diamonds', 'clubs', 'spades']))
    value = fields.Str(required=True, validate=OneOf(['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']))
    is_face_down = fields.Bool(required=False, load_default=False) # Changed missing to load_default

class BlackjackHandDataSchema(Schema):
    cards = fields.Nested(BlackjackCardSchema, many=True, required=True)
    total = fields.Int(required=True)
    is_busted = fields.Bool(required=True)
    is_blackjack = fields.Bool(required=True)
    is_doubled = fields.Bool(required=False, load_default=False) # Changed default to load_default
    is_split = fields.Bool(required=False, load_default=False)   # Changed default to load_default
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
    initial_bet = auto_field(metadata={"description": "Initial bet in Satoshis"})
    total_bet = auto_field(metadata={"description": "Total bet in Satoshis (includes doubles, splits)"})
    win_amount = auto_field(metadata={"description": "Win amount in Satoshis"})
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
    bet_amount = fields.Int(required=True, validate=Range(min=1), metadata={"description": "Bet amount in Satoshis"})

class BlackjackActionRequestSchema(Schema):
    hand_id = fields.Int(required=True, validate=Range(min=1))
    action_type = fields.Str(required=True, validate=OneOf(['hit', 'stand', 'double', 'split']))
    hand_index = fields.Int(required=True, validate=Range(min=0)) # Removed load_default for required field

# --- Poker Schemas (New) ---

class PokerPlayerStateSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PokerPlayerState
        load_instance = True
        sqla_session = db.session
        include_relationships = True
        # Exclude hole_cards by default in general listings. API must handle conditional exposure.
        exclude = ("table",) # Avoid circular dep with PokerTableSchema if it includes player_states

    id = auto_field(dump_only=True)
    seat_id = auto_field()
    stack_sats = auto_field()
    is_sitting_out = auto_field()
    is_active_in_hand = auto_field()
    last_action = auto_field()
    hole_cards = fields.List(fields.String(), allow_none=True) # Defined, but API controls exposure
    user = fields.Nested('UserSchema', only=("id", "username"), dump_only=True)
    # table_id and user_id are implicitly handled by relationships or can be added if needed directly

class PokerHandSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PokerHand
        load_instance = True
        sqla_session = db.session
        include_relationships = False # Usually part of a table context

    id = auto_field(dump_only=True)
    table_id = auto_field(dump_only=True)
    hand_history = fields.Raw(allow_none=True) # JSON
    board_cards = fields.List(fields.String(), allow_none=True) # JSON array of strings
    pot_size_sats = auto_field()
    rake_sats = auto_field()
    start_time = auto_field(dump_only=True)
    end_time = auto_field(dump_only=True)
    winners = fields.Raw(allow_none=True) # JSON

class PokerTableSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PokerTable
        load_instance = True
        sqla_session = db.session
        include_relationships = True
        # Exclude game_sessions to avoid circular dependency with GameSessionSchema.
        # Hands might be too much for a list view, consider a separate endpoint or flag.
        exclude = ("game_sessions",)

    id = auto_field(dump_only=True)
    name = auto_field()
    description = auto_field()
    game_type = auto_field()
    limit_type = auto_field()
    small_blind = auto_field()
    big_blind = auto_field()
    min_buy_in = auto_field()
    max_buy_in = auto_field()
    max_seats = auto_field()
    is_active = auto_field()
    created_at = auto_field(dump_only=True)
    updated_at = auto_field(dump_only=True)
    
    player_states = fields.Nested(PokerPlayerStateSchema, many=True, dump_only=True, exclude=('hole_cards',)) # Exclude sensitive cards in general table view
    hands = fields.Nested(PokerHandSchema, many=True, dump_only=True) # Optional: might be too much for list view

class PokerTableBasicInfoSchema(SQLAlchemyAutoSchema):
    # Used for nesting inside PokerTableStateResponseSchema to avoid meta conflicts
    class Meta:
        model = PokerTable
        load_instance = True
        sqla_session = db.session
        fields = (
            "id", "name", "description", "game_type", "limit_type", 
            "small_blind", "big_blind", "min_buy_in", "max_buy_in", 
            "max_seats", "is_active", "created_at", "updated_at"
        ) # Explicitly list fields, relationships are not included unless specified here

    id = auto_field(dump_only=True)
    name = auto_field()
    description = auto_field()
    game_type = auto_field()
    limit_type = auto_field()
    small_blind = auto_field()
    big_blind = auto_field()
    min_buy_in = auto_field()
    max_buy_in = auto_field()
    max_seats = auto_field()
    is_active = auto_field()
    created_at = auto_field(dump_only=True)
    updated_at = auto_field(dump_only=True)

# --- Poker API Request/Response Schemas (New) ---

class JoinPokerTableSchema(Schema):
    table_id = fields.Int(required=True, validate=Range(min=1))
    seat_id = fields.Int(required=True, validate=Range(min=1, max=10, error="Seat ID must be between 1 and 10."))
    buy_in_amount = fields.Int(required=True, validate=Range(min=1, error="Buy-in amount must be positive."))

class LeavePokerTableSchema(Schema): # Usually table_id is in URL, user from JWT
    table_id = fields.Int(required=True)

class PokerActionSchema(Schema):
    # table_id might be in URL path for some API designs
    table_id = fields.Int(required=True) 
    hand_id = fields.Int(required=True) # ID of the current hand being played
    action_type = fields.Str(required=True, validate=OneOf(["fold", "check", "call", "bet", "raise"]))
    amount = fields.Int(allow_none=True, validate=Range(min=0)) # Allow 0 for pot-limit pre-flop calls/checks that are technically amount 0

    @validates_schema
    def validate_action_amount(self, data, **kwargs):
        action = data.get("action_type")
        amount = data.get("amount")

        if action in ("bet", "raise"):
            if amount is None or amount <= 0: # Min bet/raise is usually > 0, but handled by game logic mostly
                raise ValidationError("A positive amount is required for 'bet' or 'raise' actions.", "amount")
        elif action in ("fold", "check", "call"): # Call can have an implicit amount (the current bet to match)
            if amount is not None and amount < 0 : # Amount could be 0 for a call if it's a BB option pre-flop
                 raise ValidationError(f"Amount should not be negative for '{action}' action.", "amount")
        return data

class PokerTableStateResponseSchema(Schema):
    """
    Complex schema to represent the full table state sent to clients.
    Careful consideration for PokerPlayerStateSchema to hide other players' hole_cards.
    """
    table = fields.Nested(PokerTableBasicInfoSchema) # Use the new basic schema
    current_hand = fields.Nested(PokerHandSchema, allow_none=True)
    # player_states needs custom handling in the API to show/hide hole_cards
    player_states = fields.List(fields.Nested(PokerPlayerStateSchema)) 
    
    current_player_to_act_user_id = fields.Int(allow_none=True, dump_only=True)
    dealer_seat_id = fields.Int(allow_none=True, dump_only=True)
    # Pot details often derived or part of PokerHandSchema
    pot_total_sats = fields.Int(dump_only=True, allow_none=True) 
    current_bet_to_match_sats = fields.Int(dump_only=True, allow_none=True)
    min_raise_sats = fields.Int(allow_none=True, dump_only=True)
    last_action_description = fields.Str(allow_none=True, dump_only=True)
    active_betting_round = fields.Str(allow_none=True, dump_only=True) # e.g., 'preflop', 'flop', 'turn', 'river'
