"""
Blackjack Network Game - Configuration Variables
=================================================
All constants and configuration values.
"""

# =============================================================================
# NETWORK CONFIGURATION
# =============================================================================

# UDP port for broadcast offers (MUST be 13122 per assignment spec)
UDP_BROADCAST_PORT = 13122

# TCP port - 0 means OS assigns an available port
DEFAULT_TCP_PORT = 0

# Broadcast address - use this for cross-machine communication
BROADCAST_ADDRESS = "255.255.255.255"

# =============================================================================
# PROTOCOL CONSTANTS
# =============================================================================

# Magic cookie for message validation
MAGIC_COOKIE = 0xABCDDCBA

# Message types
MSG_TYPE_OFFER = 0x02
MSG_TYPE_REQUEST = 0x03
MSG_TYPE_PAYLOAD = 0x04

# Server payload - Round results
RESULT_NOT_OVER = 0x00
RESULT_TIE = 0x01
RESULT_LOSS = 0x02  # Client loses
RESULT_WIN = 0x03   # Client wins

# Player decisions (5 bytes each, padded)
DECISION_HIT = b"Hit\x00\x00"      # "Hit" + 2 null bytes = 5 bytes
DECISION_STAND = b"Stand"          # "Stand" = 5 bytes

# Team name max length
TEAM_NAME_LENGTH = 32

# =============================================================================
# GAME CONSTANTS
# =============================================================================

# Card suits (0-3: Hearts, Diamonds, Clubs, Spades)
SUITS = {0: "Hearts", 1: "Diamonds", 2: "Clubs", 3: "Spades"}
SUIT_SYMBOLS = {0: "♥", 1: "♦", 2: "♣", 3: "♠"}

# Card ranks (1-13)
RANKS = {
    1: "A", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7",
    8: "8", 9: "9", 10: "10", 11: "J", 12: "Q", 13: "K"
}

# Card values for blackjack scoring
CARD_VALUES = {
    1: 11,  # Ace = 11
    2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9, 10: 10,
    11: 10, 12: 10, 13: 10  # Face cards = 10
}

# Dealer stands at 17+
DEALER_STAND_THRESHOLD = 17
BUST_THRESHOLD = 21

# =============================================================================
# TIMEOUTS (seconds)
# =============================================================================

OFFER_TIMEOUT = 10.0           # How long to wait for a server offer
OFFER_BROADCAST_INTERVAL = 1.0 # How often server broadcasts
TCP_TIMEOUT = 30.0             # General TCP timeout
PLAYER_DECISION_TIMEOUT = 60.0 # Time for player to decide

# =============================================================================
# BUFFER SIZES
# =============================================================================

UDP_BUFFER_SIZE = 1024
TCP_BUFFER_SIZE = 1024

# =============================================================================
# DISPLAY
# =============================================================================

DEFAULT_TEAM_NAME = "The Socket Wizards"

# Terminal colors (ANSI)
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"

# Fun messages
WIN_MESSAGES = [
    "🎉 WINNER WINNER! You beat the dealer!",
    "🏆 Victory! The chips are yours!",
    "💰 Cha-ching! You're on fire!"
]

LOSE_MESSAGES = [
    "😢 The dealer takes this one...",
    "🏠 House wins this round!",
    "📉 Not your round, but don't give up!"
]

TIE_MESSAGES = [
    "🤝 It's a push! Nobody wins, nobody loses.",
    "⚖️ Perfectly balanced, as all things should be.",
    "🔄 Draw! The universe couldn't decide."
]

BUST_MESSAGES = [
    "💥 BUST! The house always wins... or does it?",
    "😱 Over 21! Better luck next time!",
    "🎭 Sometimes the cards just aren't with you..."
]

DEALER_BUST_MESSAGES = [
    "💥 Dealer BUSTS! You win by default!",
    "🎊 Dealer went over 21! Easy win!",
    "🌟 The dealer got greedy!"
]