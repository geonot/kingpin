from marshmallow import Schema, fields, validate, ValidationError, pre_load, validates, validates_schema
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field
from marshmallow.validate import OneOf, Range, Length, Email, Regexp
from datetime import datetime, timezone
import re
import html

# Import all models - combining Spacecrash, Poker, and Plinko models
from .models import ( # Relative import
    db, User, GameSession, SlotSpin, Transaction, BonusCode, Slot, SlotSymbol, SlotBet,
    BlackjackTable, BlackjackHand, BlackjackAction, UserBonus,
    SpacecrashGame, SpacecrashBet,  # Spacecrash models
    PokerTable, PokerHand, PokerPlayerState,  # Poker models
    PlinkoDropLog,  # Plinko models
    BaccaratTable, BaccaratHand, BaccaratAction # Baccarat models
)
from .utils.plinko_helper import STAKE_CONFIG, PAYOUT_MULTIPLIERS # Relative import
from .utils.security import validate_password_strength, sanitize_input # Relative import

# --- Enhanced Security Validators ---
def validate_username(username):
    """Enhanced username validation"""
    if not username:
        raise ValidationError('Username is required.')
    
    # Length check
    if len(username) < 3 or len(username) > 30:
        raise ValidationError('Username must be between 3 and 30 characters.')
    
    # Character validation - only alphanumeric and underscore
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        raise ValidationError('Username can only contain letters, numbers, and underscores.')
    
    # Prevent reserved usernames
    reserved = ['admin', 'root', 'administrator', 'moderator', 'support', 'system', 'null', 'undefined']
    if username.lower() in reserved:
        raise ValidationError('This username is reserved.')
    
    return username

def validate_email_enhanced(email):
    """Enhanced email validation"""
    if not email:
        raise ValidationError('Email is required.')
    
    # Basic email format validation
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        raise ValidationError('Invalid email format.')
    
    # Length check
    if len(email) > 254:
        raise ValidationError('Email address is too long.')
    
    # Domain validation
    domain = email.split('@')[1]
    if domain.startswith('.') or domain.endswith('.') or '..' in domain:
        raise ValidationError('Invalid email domain.')
    
    return email.lower()

def validate_password(password):
    """Enhanced password validation using security utils"""
    errors = validate_password_strength(password)
    if errors:
        raise ValidationError(errors)

def validate_amount(amount):
    """Validate monetary amounts (in satoshis)"""
    if amount < 0:
        raise ValidationError('Amount cannot be negative.')
    
    if amount > 21000000 * 100000000:  # Max 21M BTC in satoshis
        raise ValidationError('Amount exceeds maximum allowed value.')
    
    return amount

def sanitize_string_field(value):
    """Sanitize string inputs to prevent XSS"""
    if isinstance(value, str):
        # HTML escape
        value = html.escape(value)
        # Remove potential script tags
        value = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', value, flags=re.IGNORECASE)
    return value

# --- Custom Fields ---
class SanitizedString(fields.String):
    """String field with automatic sanitization"""
    def _deserialize(self, value, attr, data, **kwargs):
        value = super()._deserialize(value, attr, data, **kwargs)
        return sanitize_string_field(value) if value else value

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
        exclude = ("password",) # Exclude sensitive fields. deposit_wallet_private_key is not a model field.

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
        exclude = ("password",) # Still exclude sensitive fields. deposit_wallet_private_key is not a model field.

    # Include relationships explicitly if needed
    transactions = fields.Nested('TransactionSchema', many=True, dump_only=True)
    game_sessions = fields.Nested('GameSessionSchema', many=True, dump_only=True)


class RegisterSchema(Schema):
    username = SanitizedString(required=True, validate=validate_username)
    email = fields.Email(required=True, validate=validate_email_enhanced)
    password = fields.Str(required=True, validate=validate_password)
    
    @validates_schema
    def validate_registration_data(self, data, **kwargs):
        # Additional cross-field validation
        if 'username' in data and 'email' in data:
            if data['username'].lower() in data['email'].lower():
                raise ValidationError('Username cannot be part of email address.')

class LoginSchema(Schema):
    username = SanitizedString(required=True, validate=Length(min=1, max=50))
    password = fields.Str(required=True, validate=Length(min=1, max=200))
    
    @pre_load
    def sanitize_input(self, data, **kwargs):
        """Sanitize login input data"""
        return sanitize_input(data)

class UpdateSettingsSchema(Schema):
    email = fields.Email(validate=validate_email_enhanced)
    password = fields.Str(validate=validate_password)
    
    @validates_schema
    def validate_at_least_one_field(self, data, **kwargs):
        if not any(data.values()):
            raise ValidationError('At least one field must be provided.')

class WithdrawSchema(Schema):
    amount = fields.Int(required=True, validate=[validate_amount, Range(min=10000)])  # Min 0.0001 BTC
    address = SanitizedString(required=True, validate=Length(min=26, max=62))
    
    @validates('address')
    def validate_btc_address(self, address):
        # Basic Bitcoin address validation
        if not re.match(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[a-z0-9]{39,59}$', address):
            raise ValidationError('Invalid Bitcoin address format.')

class DepositSchema(Schema):
    amount = fields.Int(required=True, validate=[validate_amount, Range(min=1000)])  # Min 0.00001 BTC
    
class TransferSchema(Schema):
    recipient_username = SanitizedString(required=True, validate=validate_username)
    amount = fields.Int(required=True, validate=[validate_amount, Range(min=100)])  # Min 0.000001 BTC
    note = SanitizedString(validate=Length(max=200))

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
    bet_amount = fields.Int(
        required=True,
        validate=[
            validate_amount,
            Range(min=100, max=1000000, error="Bet amount must be between 100 and 1,000,000 satoshis")
        ]
    )
    
    @validates('bet_amount')
    def validate_bet_reasonable(self, value, **kwargs): # Added **kwargs to accept unexpected arguments
        # Additional validation for reasonable bet amounts
        if value % 100 != 0:  # Must be multiple of 100 satoshis
            raise ValidationError('Bet amount must be a multiple of 100 satoshis.')

class BlackjackActionSchema(Schema):
    action = fields.Str(required=True, validate=OneOf(['hit', 'stand', 'double', 'split']))
    
class BlackjackBetSchema(Schema):
    bet_amount = fields.Int(
        required=True,
        validate=[
            validate_amount,
            Range(min=1000, max=5000000, error="Bet amount must be between 1,000 and 5,000,000 satoshis")
        ]
    )

# --- Enhanced Game Validation Schemas ---
class PlinkoDropSchema(Schema):
    bet_amount = fields.Int(
        required=True,
        validate=[
            validate_amount,
            Range(min=100, max=1000000, error="Bet amount must be between 100 and 1,000,000 satoshis")
        ]
    )
    risk_level = fields.Str(required=True, validate=OneOf(['low', 'medium', 'high']))
    
    @validates_schema
    def validate_plinko_bet(self, data, **kwargs):
        bet_amount = data.get('bet_amount')
        risk_level = data.get('risk_level')
        
        if bet_amount and risk_level:
            # Validate bet amount is valid for risk level
            if risk_level in STAKE_CONFIG:
                valid_amounts = STAKE_CONFIG[risk_level]
                if bet_amount not in valid_amounts:
                    raise ValidationError(f'Invalid bet amount for {risk_level} risk level.')

class SpacecrashBetSchema(Schema):
    bet_amount = fields.Int(
        required=True,
        validate=[
            validate_amount,
            Range(min=100, max=10000000, error="Bet amount must be between 100 and 10,000,000 satoshis")
        ]
    )
    auto_cashout = fields.Float(validate=Range(min=1.01, max=1000.0))

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

    # New fields for Symphony of Spheres
    game_type_name = fields.String(description="Type of the slot game", allow_none=True)
    sphere_colors = fields.Raw(nullable=True, description="JSON object or list of available sphere colors/definitions")
    sphere_textures = fields.Raw(nullable=True, description="JSON object or list of available sphere textures/definitions")
    winning_patterns = fields.Raw(nullable=True, description="JSON object defining winning patterns and payouts")
    prism_sphere_config = fields.Raw(nullable=True, description="JSON object for Prism Sphere behavior")
    base_field_dimensions = fields.Raw(nullable=True, description="JSON object for base field dimensions (e.g., width, height)")

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

# --- Baccarat Schemas ---

class BaccaratTableSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = BaccaratTable
        load_instance = True
        sqla_session = db.session
        # Fields to expose for a table listing or detail view
        fields = ("id", "name", "description", "min_bet", "max_bet", "max_tie_bet", "commission_rate", "is_active", "created_at", "updated_at")

    id = auto_field(dump_only=True)
    name = auto_field()
    description = auto_field(allow_none=True)
    min_bet = auto_field()
    max_bet = auto_field()
    max_tie_bet = auto_field()
    commission_rate = fields.Float() # Explicitly serialize Decimal as Float
    is_active = auto_field(dump_only=True)
    created_at = auto_field(dump_only=True)
    updated_at = auto_field(dump_only=True)

class BaccaratActionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = BaccaratAction
        load_instance = True
        sqla_session = db.session
        fields = ("id", "user_id", "action_type", "bet_on_player", "bet_on_banker", "bet_on_tie", "action_details", "created_at")

    id = auto_field(dump_only=True)
    user_id = auto_field(dump_only=True)
    action_type = auto_field()
    bet_on_player = auto_field(allow_none=True)
    bet_on_banker = auto_field(allow_none=True)
    bet_on_tie = auto_field(allow_none=True)
    action_details = auto_field(allow_none=True) # JSON field
    created_at = auto_field(dump_only=True)


class BaccaratHandSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = BaccaratHand
        load_instance = True
        sqla_session = db.session
        # Define fields to include to control what's exposed
        fields = (
            "id", "user_id", "table_id", "game_session_id",
            "initial_bet_player", "initial_bet_banker", "initial_bet_tie", "total_bet_amount",
            "win_amount", "player_cards", "banker_cards", "player_score", "banker_score",
            "outcome", "commission_paid", "status", "details",
            "created_at", "updated_at", "completed_at",
            "user", "table", "actions" # Nested fields
        )

    id = auto_field(dump_only=True)
    user_id = auto_field(dump_only=True)
    table_id = auto_field(dump_only=True)
    game_session_id = auto_field(dump_only=True)
    initial_bet_player = auto_field()
    initial_bet_banker = auto_field()
    initial_bet_tie = auto_field()
    total_bet_amount = auto_field()
    win_amount = auto_field() # Net profit
    player_cards = auto_field() # JSON
    banker_cards = auto_field() # JSON
    player_score = auto_field(allow_none=True)
    banker_score = auto_field(allow_none=True)
    outcome = auto_field(allow_none=True)
    commission_paid = auto_field()
    status = auto_field()
    details = auto_field(allow_none=True) # JSON field from baccarat_helper
    created_at = auto_field(dump_only=True)
    updated_at = auto_field(dump_only=True)
    completed_at = auto_field(allow_none=True, dump_only=True)

    user = fields.Nested(UserSchema, only=("id", "username", "balance"))
    table = fields.Nested(BaccaratTableSchema, only=("id", "name"))
    actions = fields.List(fields.Nested(BaccaratActionSchema, exclude=("baccarat_hand_id",)), dump_only=True)


class PlaceBaccaratBetSchema(Schema):
    table_id = fields.Int(required=True, validate=Range(min=1))
    bet_on_player = fields.Int(required=False, load_default=0, validate=Range(min=0))
    bet_on_banker = fields.Int(required=False, load_default=0, validate=Range(min=0))
    bet_on_tie = fields.Int(required=False, load_default=0, validate=Range(min=0))

    @validates_schema
    def validate_bets(self, data, **kwargs):
        player_bet = data.get("bet_on_player", 0)
        banker_bet = data.get("bet_on_banker", 0)
        tie_bet = data.get("bet_on_tie", 0)

        if player_bet < 0 or banker_bet < 0 or tie_bet < 0:
            raise ValidationError("Bet amounts cannot be negative.")

        total_bet = player_bet + banker_bet + tie_bet
        if total_bet <= 0:
            raise ValidationError("At least one bet amount must be positive, and the total bet must be greater than zero.")
        return data
