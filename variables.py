"""
Blackjack Network Game - Configuration Variables
=================================================
All hardcoded values are stored here for easy modification.
"""

# =============================================================================
# NETWORK CONFIGURATION
# =============================================================================

# UDP port for broadcast offers (MUST be 13122 per assignment spec)
UDP_BROADCAST_PORT = 13122

# TCP port - set to 0 to let OS assign an available port automatically
# The actual port will be sent in the UDP offer message
DEFAULT_TCP_PORT = 0

# Broadcast address for UDP offers
BROADCAST_ADDRESS = "255.255.255.255"

# Offer broadcast interval in seconds
OFFER_BROADCAST_INTERVAL = 1.0

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
RESULT_LOSS = 0x02
RESULT_WIN = 0x03

# Client-side special result (not sent over network)
RESULT_DISCONNECTED = -1  # Used when connection is lost

# Player decisions (5 bytes each, as per spec)
DECISION_HIT = b"Hittt"
DECISION_STAND = b"Stand"

# Team name max length
TEAM_NAME_LENGTH = 32

# =============================================================================
# GAME CONSTANTS
# =============================================================================

# Card suits (encoded 0-3: Hearts, Diamonds, Clubs, Spades)
SUITS = {
    0: "Hearts",
    1: "Diamonds",
    2: "Clubs",
    3: "Spades"
}

# Suit symbols for fancy display
SUIT_SYMBOLS = {
    0: "♥",
    1: "♦",
    2: "♣",
    3: "♠"
}

# Card ranks (1-13) - face cards show their blackjack value for clarity
RANKS = {
    1: "A",
    2: "2",
    3: "3",
    4: "4",
    5: "5",
    6: "6",
    7: "7",
    8: "8",
    9: "9",
    10: "10",
    11: "J(10)",
    12: "Q(10)",
    13: "K(10)"
}

# Card values for blackjack scoring
CARD_VALUES = {
    1: 11,   # Ace = 11
    2: 2,
    3: 3,
    4: 4,
    5: 5,
    6: 6,
    7: 7,
    8: 8,
    9: 9,
    10: 10,
    11: 10,  # Jack = 10
    12: 10,  # Queen = 10
    13: 10   # King = 10
}

# Dealer must stand at this value or higher
DEALER_STAND_THRESHOLD = 17

# Bust threshold
BUST_THRESHOLD = 21

# =============================================================================
# TIMEOUTS (in seconds)
# =============================================================================

# Timeout for waiting for UDP offer
OFFER_TIMEOUT = 5.0

# Timeout for TCP operations (connection, initial card receive)
TCP_TIMEOUT = 30.0

# Timeout for player decision (give players time to think!)
PLAYER_DECISION_TIMEOUT = 60.0

# =============================================================================
# DISPLAY SETTINGS
# =============================================================================

# Server/Client name (change this to your team name!)
DEFAULT_TEAM_NAME = "The Socket Wizards"

# Fun messages for different game events
MESSAGES = {
    "welcome": [
        "🎰 Welcome to the table, high roller!",
        "🃏 Ready to test your luck?",
        "🎲 The cards are waiting for you!"
    ],
    "hit": [
        "🔥 Feeling lucky! Drawing another card...",
        "📥 One more card coming up!",
        "🎯 Let's see what fate has in store..."
    ],
    "stand": [
        "✋ Playing it safe!",
        "🛑 Holding steady...",
        "💎 Standing firm on your hand!"
    ],
    "bust": [
        "💥 BUST! The house always wins... or does it?",
        "😱 Over 21! Better luck next time!",
        "🎭 Sometimes the cards just aren't with you..."
    ],
    "win": [
        "🎉 WINNER WINNER! You beat the dealer!",
        "🏆 Victory! The chips are yours!",
        "💰 Cha-ching! You're on fire!"
    ],
    "lose": [
        "😢 The dealer takes this one...",
        "🏠 House wins this round!",
        "📉 Not your round, but don't give up!"
    ],
    "tie": [
        "🤝 It's a push! Nobody wins, nobody loses.",
        "⚖️ Perfectly balanced, as all things should be.",
        "🔄 Draw! The universe couldn't decide."
    ],
    "dealer_bust": [
        "💥 Dealer BUSTS! You win by default!",
        "🎊 Dealer went over 21! Easy win!",
        "🌟 The dealer got greedy!"
    ],
    "timeout": [
        "⏰ Time's up! Did you fall asleep at the table?",
        "🐌 Too slow! The dealer got tired of waiting...",
        "😴 Hello? Anyone there? Connection lost!",
        "🔌 Looks like your carrier pigeon got lost. Disconnected!",
        "⚡ Pro tip: Faster internet = more blackjack! Disconnected."
    ],
    "disconnected": [
        "🔌 Oops! Lost connection to the server.",
        "📡 Server went poof! Maybe it busted too?",
        "🌐 Connection lost! The internet gremlins strike again!"
    ]
}

# =============================================================================
# BUFFER SIZES
# =============================================================================

# Maximum UDP receive buffer
UDP_BUFFER_SIZE = 1024

# Maximum TCP receive buffer
TCP_BUFFER_SIZE = 1024
