"""
Blackjack Network Game - Network & Protocol Layer
==================================================
Handles all socket operations, connection management, and message encoding/decoding.
"""

import socket
import struct
import threading
import time
from collections import namedtuple
from variables import *


# =============================================================================
# DATA STRUCTURES
# =============================================================================

# Server offer message (UDP broadcast)
OfferMessage = namedtuple('OfferMessage', ['tcp_port', 'server_name'])

# Client request message (TCP)
RequestMessage = namedtuple('RequestMessage', ['num_rounds', 'client_name'])

# Server payload message (TCP)
# result: 0=not over, 1=tie, 2=loss, 3=win
# card_rank: 1-13 (0 if no card)
# card_suit: 0-3 (Hearts, Diamonds, Clubs, Spades)
ServerPayload = namedtuple('ServerPayload', ['result', 'card_rank', 'card_suit'])

# Client payload message (TCP)
ClientPayload = namedtuple('ClientPayload', ['decision'])


# =============================================================================
# PROTOCOL: ENCODING FUNCTIONS
# =============================================================================

def _prepare_name(name: str) -> bytes:
    """Prepare a team name: truncate or pad to 32 bytes."""
    name_bytes = name.encode('utf-8')
    if len(name_bytes) > TEAM_NAME_LENGTH:
        return name_bytes[:TEAM_NAME_LENGTH]
    return name_bytes.ljust(TEAM_NAME_LENGTH, b'\x00')


def encode_offer(tcp_port: int, server_name: str) -> bytes:
    """
    Encode server offer message for UDP broadcast.
    Format: Magic(4) + Type(1) + Port(2) + Name(32) = 39 bytes
    """
    name_bytes = _prepare_name(server_name)
    return struct.pack(">IBH32s", MAGIC_COOKIE, MSG_TYPE_OFFER, tcp_port, name_bytes)


def encode_request(num_rounds: int, client_name: str) -> bytes:
    """
    Encode client request message for TCP.
    Format: Magic(4) + Type(1) + Rounds(1) + Name(32) = 38 bytes
    """
    if not 1 <= num_rounds <= 255:
        raise ValueError(f"Number of rounds must be 1-255, got {num_rounds}")
    name_bytes = _prepare_name(client_name)
    return struct.pack(">IBB32s", MAGIC_COOKIE, MSG_TYPE_REQUEST, num_rounds, name_bytes)


def encode_server_payload(result: int, card_rank: int = 0, card_suit: int = 0) -> bytes:
    """
    Encode server payload message for TCP.
    Format: Magic(4) + Type(1) + Result(1) + Rank(2) + Suit(1) = 9 bytes
    """
    return struct.pack(">IBBHB", MAGIC_COOKIE, MSG_TYPE_PAYLOAD, result, card_rank, card_suit)


def encode_client_payload(decision: str) -> bytes:
    """
    Encode client payload (decision) message for TCP.
    Format: Magic(4) + Type(1) + Decision(5) = 10 bytes
    Decision must be exactly 5 bytes: "Hittt" or "Stand"
    """
    decision_lower = decision.lower().strip()
    if decision_lower == "hit":
        decision_bytes = b"Hittt"  # MUST be "Hittt" (5 bytes) per protocol
    elif decision_lower == "stand":
        decision_bytes = b"Stand"  # Already 5 bytes
    else:
        raise ValueError(f"Invalid decision: {decision}. Must be 'hit' or 'stand'")
    return struct.pack(">IB5s", MAGIC_COOKIE, MSG_TYPE_PAYLOAD, decision_bytes)


# =============================================================================
# PROTOCOL: DECODING FUNCTIONS
# =============================================================================

def decode_offer(data: bytes):
    """Decode server offer message from UDP. Returns None if invalid."""
    if len(data) < 39:
        return None
    try:
        magic, msg_type, tcp_port, name_bytes = struct.unpack(">IBH32s", data[:39])
        if magic != MAGIC_COOKIE or msg_type != MSG_TYPE_OFFER:
            return None
        server_name = name_bytes.rstrip(b'\x00').decode('utf-8', errors='replace')
        return OfferMessage(tcp_port=tcp_port, server_name=server_name)
    except struct.error:
        return None


def decode_request(data: bytes):
    """Decode client request message from TCP. Returns None if invalid."""
    if len(data) < 38:
        return None
    try:
        magic, msg_type, num_rounds, name_bytes = struct.unpack(">IBB32s", data[:38])
        if magic != MAGIC_COOKIE or msg_type != MSG_TYPE_REQUEST:
            return None
        if num_rounds < 1:
            return None
        client_name = name_bytes.rstrip(b'\x00').decode('utf-8', errors='replace')
        return RequestMessage(num_rounds=num_rounds, client_name=client_name)
    except struct.error:
        return None


def decode_server_payload(data: bytes):
    """Decode server payload message from TCP. Returns None if invalid."""
    if len(data) < 9:
        return None
    try:
        magic, msg_type, result, card_rank, card_suit = struct.unpack(">IBBHB", data[:9])
        if magic != MAGIC_COOKIE or msg_type != MSG_TYPE_PAYLOAD:
            return None
        return ServerPayload(result=result, card_rank=card_rank, card_suit=card_suit)
    except struct.error:
        return None


def decode_client_payload(data: bytes):
    """Decode client payload (decision) message from TCP. Returns None if invalid."""
    if len(data) < 10:
        return None
    try:
        magic, msg_type, decision_bytes = struct.unpack(">IB5s", data[:10])
        if magic != MAGIC_COOKIE or msg_type != MSG_TYPE_PAYLOAD:
            return None
        # Parse decision - handle "Hittt" and "Stand"
        if decision_bytes == DECISION_HIT or decision_bytes == b"Hittt":
            return ClientPayload(decision="Hit")
        elif decision_bytes == DECISION_STAND or decision_bytes == b"Stand":
            return ClientPayload(decision="Stand")
        else:
            return None
    except struct.error:
        return None


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_local_ip() -> str:
    """Get the local IP address of this machine."""
    try:
        # Create a dummy connection to find our IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        try:
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        except Exception:
            return "127.0.0.1"


# =============================================================================
# UDP BROADCASTER (Server-side)
# =============================================================================

class UDPBroadcaster:
    """Handles UDP broadcast of server offer messages."""

    def __init__(self, tcp_port: int, server_name: str):
        self.tcp_port = tcp_port
        self.server_name = server_name
        self.running = False
        self.socket = None
        self.thread = None
        self.offer_message = encode_offer(tcp_port, server_name)
        self.broadcast_addresses = self._get_broadcast_addresses()

    def _get_broadcast_addresses(self):
        """Get all broadcast addresses to try (255.255.255.255 + subnet-specific)."""
        addresses = [BROADCAST_ADDRESS]  # Always include 255.255.255.255

        # Try to get subnet-specific broadcast address
        try:
            # Find our local IP by connecting to external
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]

            # Assume /24 subnet and create subnet broadcast (e.g., 10.0.0.255)
            parts = local_ip.split(".")
            if len(parts) == 4:
                subnet_broadcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
                if subnet_broadcast not in addresses:
                    addresses.append(subnet_broadcast)
                    print(f"📡 Will also broadcast to subnet: {subnet_broadcast}")
        except Exception:
            pass

        return addresses

    def start(self):
        """Start broadcasting offers."""
        self.running = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.thread = threading.Thread(target=self._broadcast_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop broadcasting."""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

    def _broadcast_loop(self):
        """Broadcast offers every second to ALL broadcast addresses."""
        while self.running:
            try:
                # Send to ALL broadcast addresses for maximum compatibility
                for broadcast_addr in self.broadcast_addresses:
                    try:
                        self.socket.sendto(
                            self.offer_message,
                            (broadcast_addr, UDP_BROADCAST_PORT)
                        )
                    except Exception:
                        pass  # Some addresses may fail, that's okay

                time.sleep(OFFER_BROADCAST_INTERVAL)
            except Exception as e:
                if self.running:
                    print(f"⚠️ Broadcast error: {e}")
                    time.sleep(OFFER_BROADCAST_INTERVAL)


# =============================================================================
# UDP LISTENER (Client-side)
# =============================================================================

class UDPListener:
    """Handles listening for UDP server offer broadcasts."""

    def __init__(self, port: int = UDP_BROADCAST_PORT):
        self.port = port
        self.socket = None

    def _create_socket(self):
        """Create and bind the UDP socket."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Allow multiple clients on same machine (for testing)
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass  # Not available on all platforms

        # Bind to all interfaces
        self.socket.bind(("", self.port))

    def wait_for_offer(self, timeout: float = OFFER_TIMEOUT):
        """
        Wait for a server offer broadcast.
        Returns (server_ip, offer_message) or None on timeout.
        """
        try:
            # Create fresh socket each time
            self._create_socket()
            self.socket.settimeout(timeout)

            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    data, addr = self.socket.recvfrom(UDP_BUFFER_SIZE)
                    offer = decode_offer(data)
                    if offer:
                        return (addr[0], offer)
                except socket.timeout:
                    return None
                except (ValueError, struct.error):
                    # Bad packet, keep listening
                    continue
            return None

        except Exception as e:
            print(f"⚠️ UDP listener error: {e}")
            return None
        finally:
            self.close()

    def close(self):
        """Close the socket."""
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None


# =============================================================================
# TCP SERVER
# =============================================================================

class TCPServer:
    """Handles TCP server operations."""

    def __init__(self, port: int = 0):
        self.requested_port = port
        self.actual_port = 0
        self.socket = None
        self.running = False

    def bind(self) -> int:
        """Bind to the port and return the actual port number."""
        if self.socket is None:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Bind to all interfaces (important for cross-machine!)
            self.socket.bind(('0.0.0.0', self.requested_port))
            self.actual_port = self.socket.getsockname()[1]
        return self.actual_port

    def start(self, connection_handler):
        """Start accepting connections."""
        self.running = True
        if self.socket is None:
            self.bind()

        self.socket.listen(5)
        self.socket.settimeout(1.0)

        while self.running:
            try:
                client_socket, client_addr = self.socket.accept()
                connection = TCPConnection(client_socket)

                # Handle each client in a separate thread
                client_thread = threading.Thread(
                    target=self._handle_connection,
                    args=(connection_handler, connection, client_addr),
                    daemon=True
                )
                client_thread.start()

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"⚠️ Accept error: {e}")

    def _handle_connection(self, handler, connection, addr):
        """Handle a client connection with proper cleanup."""
        try:
            handler(connection, addr)
        finally:
            connection.close()

    def stop(self):
        """Stop the server."""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None


# =============================================================================
# TCP CONNECTION
# =============================================================================

class TCPConnection:
    """Wraps a TCP socket with game-specific send/receive methods."""

    REQUEST_SIZE = 38        # Request message size
    SERVER_PAYLOAD_SIZE = 9  # Server payload size
    CLIENT_PAYLOAD_SIZE = 10 # Client payload size

    def __init__(self, sock: socket.socket, timeout: float = TCP_TIMEOUT):
        self.socket = sock
        self.socket.settimeout(timeout)
        self._closed = False
        self._buffer = b""

    @classmethod
    def connect(cls, host: str, port: int, timeout: float = TCP_TIMEOUT):
        """Create a new connection to a server."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect((host, port))
            return cls(sock, timeout)
        except Exception as e:
            sock.close()
            raise ConnectionError(f"Failed to connect to {host}:{port}: {e}")

    def set_timeout(self, timeout: float):
        """Set the socket timeout."""
        self.socket.settimeout(timeout)

    def close(self):
        """Close the connection."""
        if not self._closed:
            self._closed = True
            try:
                self.socket.close()
            except Exception:
                pass

    def is_closed(self) -> bool:
        """Check if connection is closed."""
        return self._closed

    def _send_raw(self, data: bytes) -> bool:
        """Send raw bytes."""
        try:
            self.socket.sendall(data)
            return True
        except Exception as e:
            print(f"⚠️ Send error: {e}")
            return False

    def _receive_exact(self, num_bytes: int):
        """Receive exactly num_bytes using buffered I/O."""
        while len(self._buffer) < num_bytes:
            try:
                chunk = self.socket.recv(TCP_BUFFER_SIZE)
                if not chunk:
                    return None
                self._buffer += chunk
            except socket.timeout:
                return None
            except ConnectionResetError:
                return None
            except Exception as e:
                print(f"⚠️ Receive error: {e}")
                return None

        result = self._buffer[:num_bytes]
        self._buffer = self._buffer[num_bytes:]
        return result

    # =========== HIGH-LEVEL MESSAGE METHODS ===========

    def send_request(self, num_rounds: int, client_name: str) -> bool:
        """Send a game request to the server."""
        data = encode_request(num_rounds, client_name)
        return self._send_raw(data)

    def receive_request(self):
        """Receive a game request from a client."""
        data = self._receive_exact(self.REQUEST_SIZE)
        if data is None:
            return None
        return decode_request(data)

    def send_card(self, result: int, card_rank: int, card_suit: int) -> bool:
        """Send a card to the client."""
        data = encode_server_payload(result, card_rank, card_suit)
        return self._send_raw(data)

    def send_result(self, result: int) -> bool:
        """Send just a result (no card)."""
        return self.send_card(result, 0, 0)

    def receive_server_payload(self):
        """Receive a payload from the server."""
        data = self._receive_exact(self.SERVER_PAYLOAD_SIZE)
        if data is None:
            return None
        return decode_server_payload(data)

    def send_decision(self, decision: str) -> bool:
        """Send a hit/stand decision to the server."""
        try:
            data = encode_client_payload(decision)
            return self._send_raw(data)
        except ValueError as e:
            print(f"⚠️ Invalid decision: {e}")
            return False

    def receive_decision(self):
        """Receive a decision from a client."""
        data = self._receive_exact(self.CLIENT_PAYLOAD_SIZE)
        if data is None:
            return None
        return decode_client_payload(data)