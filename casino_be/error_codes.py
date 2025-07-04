# casino_be/error_codes.py
class ErrorCodes:
    # General Errors (001-099)
    GENERIC_ERROR = "BE_GEN_001"
    VALIDATION_ERROR = "BE_GEN_002"
    UNAUTHENTICATED = "BE_GEN_003"
    FORBIDDEN = "BE_GEN_004"
    NOT_FOUND = "BE_GEN_005"
    METHOD_NOT_ALLOWED = "BE_GEN_006"
    RATE_LIMIT_EXCEEDED = "BE_GEN_007"
    INTERNAL_SERVER_ERROR = "BE_GEN_008"
    SERVICE_UNAVAILABLE = "BE_GEN_009"
    CSRF_TOKEN_INVALID = "BE_GEN_010"

    # Account/User Errors (100-199)
    USER_NOT_FOUND = "BE_USR_100"
    EMAIL_ALREADY_EXISTS = "BE_USR_101"
    USERNAME_ALREADY_EXISTS = "BE_USR_102"
    INVALID_CREDENTIALS = "BE_USR_103"
    ACCOUNT_LOCKED = "BE_USR_104"
    ACCOUNT_DISABLED = "BE_USR_105"
    PASSWORD_TOO_WEAK = "BE_USR_106"
    INVALID_EMAIL_FORMAT = "BE_USR_107"

    # Financial/Transaction Errors (200-299)
    INSUFFICIENT_FUNDS = "BE_FIN_200"
    TRANSACTION_FAILED = "BE_FIN_201"
    INVALID_AMOUNT = "BE_FIN_202"
    DEPOSIT_FAILED = "BE_FIN_203"
    WITHDRAWAL_FAILED = "BE_FIN_204"
    WALLET_CREATION_FAILED = "BE_FIN_205"
    MAX_WITHDRAWAL_LIMIT_EXCEEDED = "BE_FIN_206"

    # Game Specific Errors (300-399)
    GAME_NOT_FOUND = "BE_GAME_300"
    INVALID_GAME_ACTION = "BE_GAME_301"
    SESSION_EXPIRED = "BE_GAME_302"
    TABLE_FULL = "BE_GAME_303"
    INVALID_BET = "BE_GAME_304"
    GAME_LOGIC_ERROR = "BE_GAME_305"
    SLOT_CONFIG_ERROR = "BE_GAME_306"
    SESSION_NOT_FOUND = "BE_GAME_307" # For when a required active session is missing

    # Admin Errors (400-499)
    ADMIN_ACTION_FAILED = "BE_ADM_400"
    USER_UPDATE_FAILED = "BE_ADM_401"

    # Bitcoin Service Errors (500-599)
    BITCOIN_SERVICE_UNAVAILABLE = "BE_BTC_500"
    BITCOIN_WALLET_ERROR = "BE_BTC_501"
    BITCOIN_TRANSACTION_ERROR = "BE_BTC_502"
