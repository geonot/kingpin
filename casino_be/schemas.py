from marshmallow import Schema, fields, validate, ValidationError, pre_load, validates, validates_schema
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field
from marshmallow.validate import OneOf, Range, Length, Email, Regexp
from datetime import datetime, timezone
import re

# Import all models - combining Spacecrash, Poker, and Plinko models
from .models import (
    db, User, GameSession, SlotSpin, Transaction, BonusCode, Slot, SlotSymbol, SlotBet,
    BlackjackTable, BlackjackHand, BlackjackAction, UserBonus,
    SpacecrashGame, SpacecrashBet,  # Spacecrash models
    PokerTable, PokerHand, PokerPlayerState,  # Poker models
    PlinkoDropLog  # Plinko models
)
from casino_be.utils.plinko_helper import STAKE_CONFIG, PAYOUT_MULTIPLIERS # Plinko specific imports

# --- Helper ---
def validate_password(password):
    if len(password) < 8:
        raise ValidationError('Password must be at least 8 characters long.')
    if not re.search(r"[A-Z]", password):
        raise ValidationError('Password must contain at least one uppercase letter.')
    if not re.search(r"[a-z]", password):
        raise ValidationError('Password must contain at least one lowercase letter.')
    if not re.search(r"[0-9]", password):
        raise ValidationError('Password must contain at least one digit.')
    if not re.search(r"[!@#$%^&*()_+=\-[\]{};':\"\\|,.<>/?~`]", password):
        raise ValidationError('Password must contain at least one special character.')

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
        exclude = ("password", "deposit_wallet_private_key") # Exclude sensitive fields

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
        return f"{obj.balance / 100000000:.8f}" # Convert satoshis to BTC

class AdminUserSchema(UserSchema):
     # Schema for admin viewing user details (includes potentially more info)
    class Meta(UserSchema.Meta):
        exclude = ("password", "deposit_wallet_private_key") # Still exclude sensitive fields

    # Include relationships explicitly if needed
    transactions = fields.Nested('TransactionSchema', many=True, dump_only=True)
    game_sessions = fields.Nested('GameSessionSchema', many=True, dump_only=True)


class RegisterSchema(Schema):
    username = fields.Str(required=True, validate=Length(min=3, max=50))
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate_password)

class LoginSchema(Schema):
    username = fields.Str(required=True)
    password = fields.Str(required=True)

class UpdateSettingsSchema(Schema):
    email = fields.Email()
    password = fields.Str(validate=validate_password)

class UserListSchema(PaginationSchema):
    items = fields.Nested(UserSchema, many=True, attribute='items')

# --- Game Schemas ---
class JoinGameSchema(Schema):
    game_type = fields.Str(required=True, validate=OneOf(['slot', 'blackjack']))
    slot_id = fields.Int()

class GameSessionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = GameSession
        load_instance = True
        sqla_session = db.session

class SpinRequestSchema(Schema):
    bet_amount = fields.Int(required=True, validate=Range(min=1))

class SpinSchema(Schema):
    result = fields.Raw(required=True)
    win_amount = fields.Int(required=True)

class SlotSpinSchema(SQLAlchemyAutoSchema):
     class Meta:
        model = SlotSpin
        load_instance = True
        sqla_session = db.session

# --- Transaction Schemas ---
class WithdrawSchema(Schema):
    amount_sats = fields.Int(required=True, validate=Range(min=1000)) # Min 1000 sats
    withdraw_wallet_address = fields.Str(required=True, validate=Length(min=26, max=62))

class DepositSchema(Schema):
    deposit_amount_sats = fields.Int(required=True, validate=Range(min=1))
    bonus_code = fields.Str()

class BalanceTransferSchema(Schema):
    from_user_id = fields.Int()
    to_user_id = fields.Int(required=True)
    amount_sats = fields.Int(required=True, validate=Range(min=1))
    description = fields.Str()
    transaction_type = fields.Str()


class TransactionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Transaction
        load_instance = True
        sqla_session = db.session


class TransactionListSchema(PaginationSchema):
    items = fields.Nested(TransactionSchema, many=True, attribute='items')


# --- Slot Schemas ---
class SlotSymbolSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = SlotSymbol
        load_instance = True
        sqla_session = db.session

class SlotBetSchema(SQLAlchemyAutoSchema):
     class Meta:
        model = SlotBet
        load_instance = True
        sqla_session = db.session

class SlotBasicSchema(SQLAlchemyAutoSchema):
     class Meta:
        model = Slot
        load_instance = True
        sqla_session = db.session
        exclude = ("symbols", "bets")


class SlotSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Slot
        load_instance = True
        sqla_session = db.session
        include_relationships = True

    symbols = fields.Nested(SlotSymbolSchema, many=True)
    bets = fields.Nested(SlotBetSchema, many=True)

# --- Bonus Code Schemas ---
class BonusCodeSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = BonusCode
        load_instance = True
        sqla_session = db.session


class BonusCodeListSchema(PaginationSchema):
    items = fields.Nested(BonusCodeSchema, many=True, attribute='items')

# --- Admin Schemas ---
class AdminCreditDepositSchema(Schema):
    user_id = fields.Int(required=True)
    amount_sats = fields.Int(required=True, validate=Range(min=1))
    external_tx_id = fields.Str()
    admin_notes = fields.Str()

class UserBonusSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = UserBonus
        load_instance = True
        sqla_session = db.session

# --- WinLine Schema (For Spin Response) ---
class WinLineSchema(Schema):
    line_id = fields.Int()
    symbol_id = fields.Int()
    count = fields.Int()
    multiplier = fields.Float()
    win_amount = fields.Int()

# --- Blackjack Schemas ---
class BlackjackTableBasicSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = BlackjackTable
        load_instance = True
        sqla_session = db.session
        exclude = ("hands",)

class BlackjackTableSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = BlackjackTable
        load_instance = True
        sqla_session = db.session
        include_relationships = True

class BlackjackCardSchema(Schema):
    suit = fields.Str()
    rank = fields.Str()
    value = fields.Int()

class BlackjackHandDataSchema(Schema):
    cards = fields.List(fields.Nested(BlackjackCardSchema))
    total = fields.Int()
    is_soft = fields.Bool()
    is_blackjack = fields.Bool()
    is_bust = fields.Bool()

class BlackjackHandSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = BlackjackHand
        load_instance = True
        sqla_session = db.session

class BlackjackActionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = BlackjackAction
        load_instance = True
        sqla_session = db.session

class JoinBlackjackSchema(Schema):
    table_id = fields.Int(required=True)
    bet_amount = fields.Int(required=True, validate=Range(min=1))

class BlackjackActionRequestSchema(Schema):
    hand_id = fields.Int(required=True)
    action_type = fields.Str(required=True, validate=OneOf(['hit', 'stand', 'double', 'split']))
    hand_index = fields.Int(required=True, validate=Range(min=0)) # Removed load_default for required field

# --- Spacecrash Schemas ---
class SpacecrashBetSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = SpacecrashBet
        load_instance = True
        sqla_session = db.session
        # Fields for placing a bet (request)
        # For response, we might want to dump more fields
        only = ("bet_amount", "auto_eject_at")

    bet_amount = fields.Integer(required=True, validate=Range(min=1)) # Min 1 satoshi
    auto_eject_at = fields.Float(required=False, allow_none=True, validate=Range(min=1.01)) # Min eject 1.01x

class SpacecrashPlayerBetSchema(SQLAlchemyAutoSchema):
    """Minimal bet info for public game display"""
    class Meta:
        model = SpacecrashBet
        sqla_session = db.session
        only = ("user_id", "bet_amount", "ejected_at", "win_amount", "status") # Add username later via method field for privacy

    user_id = auto_field(dump_only=True) # Consider replacing with username or masked ID
    # username = fields.Method("get_username", dump_only=True) # Example for privacy
    bet_amount = auto_field(dump_only=True)
    ejected_at = auto_field(dump_only=True)
    win_amount = auto_field(dump_only=True)
    status = auto_field(dump_only=True)

    # def get_username(self, obj):
    #     return obj.user.username # Requires eager/joined loading of user or separate query

class SpacecrashGameSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = SpacecrashGame
        load_instance = True # Not typically needed for dump-only schemas
        sqla_session = db.session
        # include_relationships = True # To include 'bets' relationship
        exclude = ("server_seed", "client_seed", "nonce") # Exclude sensitive/internal fields by default

    id = auto_field(dump_only=True)
    crash_point = auto_field(dump_only=True)
    public_seed = auto_field(dump_only=True)
    status = auto_field(dump_only=True)
    game_start_time = auto_field(dump_only=True)
    game_end_time = auto_field(dump_only=True)
    created_at = auto_field(dump_only=True)

    # For /api/spacecrash/current_game
    current_multiplier = fields.Float(dump_only=True, allow_none=True) # To be calculated based on game status and start time
    player_bets = fields.List(fields.Nested(SpacecrashPlayerBetSchema), dump_only=True)

class SpacecrashGameHistorySchema(SQLAlchemyAutoSchema):
    class Meta:
        model = SpacecrashGame
        sqla_session = db.session
        only = ("id", "crash_point", "game_end_time", "public_seed", "status") # Only show relevant history fields

    id = auto_field(dump_only=True)
    crash_point = auto_field(dump_only=True)
    game_end_time = auto_field(dump_only=True)
    public_seed = auto_field(dump_only=True)
    status = auto_field(dump_only=True)

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

# --- Plinko Schemas ---
class PlinkoPlayRequestSchema(Schema):
    stake_amount = fields.Float(required=True, validate=validate.Range(min=0.01))
    chosen_stake_label = fields.String(required=True, validate=validate.OneOf(list(STAKE_CONFIG.keys())))
    slot_landed_label = fields.String(required=True, validate=validate.OneOf(list(PAYOUT_MULTIPLIERS.keys())))

class PlinkoPlayResponseSchema(Schema):
    success = fields.Boolean(required=True)
    winnings = fields.Float(allow_none=True) # Allow none if error or no win
    new_balance = fields.Float(allow_none=True) # Allow none if error
    message = fields.String(allow_none=True)
    error = fields.String(allow_none=True)

    @validates_schema
    def validate_response_fields(self, data, **kwargs):
        if data.get('success'):
            if data.get('winnings') is None:
                raise ValidationError("winnings is required when success is true.", "winnings")
            if data.get('new_balance') is None:
                raise ValidationError("new_balance is required when success is true.", "new_balance")
        else:
            if data.get('error') is None:
                raise ValidationError("error is required when success is false.", "error")
