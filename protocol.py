"""
Blackjack Network Game - Protocol Handler
==========================================
Handles encoding and decoding of all message types:
- Offer (UDP): Server broadcasts to find clients
- Request (TCP): Client requests game rounds
- Payload (TCP): Game messages between client and server
"""

import struct
from typing import Tuple, Optional, NamedTuple
from variables import (
    MAGIC_COOKIE, 
    MSG_TYPE_OFFER, MSG_TYPE_REQUEST, MSG_TYPE_PAYLOAD,
    TEAM_NAME_LENGTH,
    DECISION_HIT, DECISION_STAND
)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class OfferMessage(NamedTuple):
    """Represents a server offer message."""
    tcp_port: int
    server_name: str


class RequestMessage(NamedTuple):
    """Represents a client request message."""
    num_rounds: int
    client_name: str


class ServerPayload(NamedTuple):
    """Represents a server payload message."""
    result: int       # 0=not over, 1=tie, 2=loss, 3=win
    card_rank: int    # 1-13 (0 if no card)
    card_suit: int    # 0-3 (Hearts, Diamonds, Clubs, Spades)


class ClientPayload(NamedTuple):
    """Represents a client payload message."""
    decision: str     # "Hit" or "Stand"


# =============================================================================
# ENCODING FUNCTIONS
# =============================================================================

def encode_offer(tcp_port: int, server_name: str) -> bytes:
    """
    Encode a server offer message for UDP broadcast.
    
    Format:
    - Magic cookie (4 bytes): 0xabcddcba
    - Message type (1 byte): 0x02
    - TCP port (2 bytes): Big-endian unsigned short
    - Server name (32 bytes): Null-padded string
    
    Args:
        tcp_port: The TCP port clients should connect to
        server_name: The server's team name
        
    Returns:
        Encoded message bytes
    """
    # Prepare the server name (pad or truncate to 32 bytes)
    name_bytes = _prepare_name(server_name)
    
    # Pack the message: magic cookie, type, port, name
    # >I = big-endian unsigned int (4 bytes)
    # B = unsigned char (1 byte)
    # H = unsigned short (2 bytes)
    # 32s = 32 bytes string
    return struct.pack(">IBH32s", MAGIC_COOKIE, MSG_TYPE_OFFER, tcp_port, name_bytes)


def encode_request(num_rounds: int, client_name: str) -> bytes:
    """
    Encode a client request message for TCP.
    
    Format:
    - Magic cookie (4 bytes): 0xabcddcba
    - Message type (1 byte): 0x03
    - Number of rounds (1 byte): 1-255
    - Client name (32 bytes): Null-padded string
    
    Args:
        num_rounds: Number of rounds to play (1-255)
        client_name: The client's team name
        
    Returns:
        Encoded message bytes
    """
    # Validate rounds
    if not 1 <= num_rounds <= 255:
        raise ValueError(f"Number of rounds must be 1-255, got {num_rounds}")
    
    # Prepare the client name
    name_bytes = _prepare_name(client_name)
    
    # Pack the message
    return struct.pack(">IBB32s", MAGIC_COOKIE, MSG_TYPE_REQUEST, num_rounds, name_bytes)


def encode_server_payload(result: int, card_rank: int = 0, card_suit: int = 0) -> bytes:
    """
    Encode a server payload message for TCP.
    
    Format:
    - Magic cookie (4 bytes): 0xabcddcba
    - Message type (1 byte): 0x04
    - Round result (1 byte): 0=not over, 1=tie, 2=loss, 3=win
    - Card rank (2 bytes): 01-13 (or 00 if no card)
    - Card suit (1 byte): 0-3 (HDCS)
    
    Args:
        result: Game result code
        card_rank: Card rank 1-13 (0 for no card)
        card_suit: Card suit 0-3
        
    Returns:
        Encoded message bytes
    """
    # Pack: magic, type, result, rank (2 bytes), suit (1 byte)
    return struct.pack(">IBBHB", MAGIC_COOKIE, MSG_TYPE_PAYLOAD, result, card_rank, card_suit)


def encode_client_payload(decision: str) -> bytes:
    """
    Encode a client payload (decision) message for TCP.
    
    Format:
    - Magic cookie (4 bytes): 0xabcddcba
    - Message type (1 byte): 0x04
    - Decision (5 bytes): "Hit" or "Stand"
    
    Args:
        decision: Either "hit" or "stand" (case-insensitive)
        
    Returns:
        Encoded message bytes
    """
    # Normalize decision
    decision_lower = decision.lower().strip()
    if decision_lower == "hit":
        decision_bytes = DECISION_HIT
    elif decision_lower == "stand":
        decision_bytes = DECISION_STAND
    else:
        raise ValueError(f"Invalid decision: {decision}. Must be 'hit' or 'stand'")
    
    return struct.pack(">IB5s", MAGIC_COOKIE, MSG_TYPE_PAYLOAD, decision_bytes)


# =============================================================================
# DECODING FUNCTIONS
# =============================================================================

def decode_offer(data: bytes) -> Optional[OfferMessage]:
    """
    Decode a server offer message from UDP.
    
    Args:
        data: Raw bytes received
        
    Returns:
        OfferMessage if valid, None otherwise
    """
    # Check minimum length: 4 + 1 + 2 + 32 = 39 bytes
    if len(data) < 39:
        return None
    
    try:
        magic, msg_type, tcp_port, name_bytes = struct.unpack(">IBH32s", data[:39])
        
        # Validate magic cookie and message type
        if magic != MAGIC_COOKIE:
            return None
        if msg_type != MSG_TYPE_OFFER:
            return None
        
        # Decode server name (strip null padding)
        server_name = name_bytes.rstrip(b'\x00').decode('utf-8', errors='replace')
        
        return OfferMessage(tcp_port=tcp_port, server_name=server_name)
        
    except struct.error:
        return None


def decode_request(data: bytes) -> Optional[RequestMessage]:
    """
    Decode a client request message from TCP.
    
    Args:
        data: Raw bytes received
        
    Returns:
        RequestMessage if valid, None otherwise
    """
    # Check minimum length: 4 + 1 + 1 + 32 = 38 bytes
    if len(data) < 38:
        return None
    
    try:
        magic, msg_type, num_rounds, name_bytes = struct.unpack(">IBB32s", data[:38])
        
        # Validate magic cookie and message type
        if magic != MAGIC_COOKIE:
            return None
        if msg_type != MSG_TYPE_REQUEST:
            return None
        
        # Validate num_rounds is at least 1
        if num_rounds < 1:
            return None
        
        # Decode client name
        client_name = name_bytes.rstrip(b'\x00').decode('utf-8', errors='replace')
        
        return RequestMessage(num_rounds=num_rounds, client_name=client_name)
        
    except struct.error:
        return None


def decode_server_payload(data: bytes) -> Optional[ServerPayload]:
    """
    Decode a server payload message from TCP.
    
    Args:
        data: Raw bytes received
        
    Returns:
        ServerPayload if valid, None otherwise
    """
    # Check minimum length: 4 + 1 + 1 + 2 + 1 = 9 bytes
    if len(data) < 9:
        return None
    
    try:
        magic, msg_type, result, card_rank, card_suit = struct.unpack(">IBBHB", data[:9])
        
        # Validate magic cookie and message type
        if magic != MAGIC_COOKIE:
            return None
        if msg_type != MSG_TYPE_PAYLOAD:
            return None
        
        return ServerPayload(result=result, card_rank=card_rank, card_suit=card_suit)
        
    except struct.error:
        return None


def decode_client_payload(data: bytes) -> Optional[ClientPayload]:
    """
    Decode a client payload (decision) message from TCP.
    
    Args:
        data: Raw bytes received
        
    Returns:
        ClientPayload if valid, None otherwise
    """
    # Check minimum length: 4 + 1 + 5 = 10 bytes
    if len(data) < 10:
        return None
    
    try:
        magic, msg_type, decision_bytes = struct.unpack(">IB5s", data[:10])
        
        # Validate magic cookie and message type
        if magic != MAGIC_COOKIE:
            return None
        if msg_type != MSG_TYPE_PAYLOAD:
            return None
        
        # Parse decision
        if decision_bytes == DECISION_HIT:
            decision = "Hit"
        elif decision_bytes == DECISION_STAND:
            decision = "Stand"
        else:
            return None
        
        return ClientPayload(decision=decision)
        
    except struct.error:
        return None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _prepare_name(name: str) -> bytes:
    """
    Prepare a team name for encoding.
    Truncates to 32 bytes or pads with null bytes.
    
    Args:
        name: The team name string
        
    Returns:
        32-byte padded/truncated name
    """
    name_bytes = name.encode('utf-8')
    if len(name_bytes) > TEAM_NAME_LENGTH:
        name_bytes = name_bytes[:TEAM_NAME_LENGTH]
    else:
        name_bytes = name_bytes.ljust(TEAM_NAME_LENGTH, b'\x00')
    return name_bytes


def validate_magic_cookie(data: bytes) -> bool:
    """
    Quick check if data starts with the magic cookie.
    
    Args:
        data: Raw bytes to check
        
    Returns:
        True if valid magic cookie, False otherwise
    """
    if len(data) < 4:
        return False
    magic = struct.unpack(">I", data[:4])[0]
    return magic == MAGIC_COOKIE
