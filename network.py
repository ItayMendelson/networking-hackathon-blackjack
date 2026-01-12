"""
Blackjack Network Game - Network Layer
=======================================
Handles all socket operations, connection management, and network I/O.
Provides clean abstractions for both client and server networking.
"""

import socket
import threading
import time
from typing import Optional, Tuple, Callable

from variables import (
    UDP_BROADCAST_PORT, BROADCAST_ADDRESS,
    OFFER_BROADCAST_INTERVAL,
    OFFER_TIMEOUT, TCP_TIMEOUT,
    UDP_BUFFER_SIZE, TCP_BUFFER_SIZE
)
from protocol import (
    encode_offer, decode_offer,
    encode_request, decode_request,
    encode_server_payload, decode_server_payload,
    encode_client_payload, decode_client_payload,
    OfferMessage, RequestMessage, ServerPayload, ClientPayload
)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_local_ip() -> str:
    """
    Get the local IP address of this machine.
    
    Returns:
        Local IP address as string, or "127.0.0.1" if detection fails
    """
    try:
        # Create a dummy socket to determine the local IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Try connecting to a public IP (doesn't actually send data)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        # Fallback: try to get any non-localhost IP
        try:
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        except Exception:
            return "127.0.0.1"


def get_all_ips() -> list:
    """
    Get all IP addresses of this machine (for debugging).

    Returns:
        List of (interface_name, ip_address) tuples
    """
    ips = []
    try:
        hostname = socket.gethostname()
        # Get all IPs associated with hostname
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass

    # Also try the connect trick
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass

    return ips if ips else ["127.0.0.1"]


# =============================================================================
# UDP BROADCASTER (Server-side)
# =============================================================================

class UDPBroadcaster:
    """
    Handles UDP broadcast of server offer messages.
    Runs in a separate thread, broadcasting at regular intervals.
    """

    def __init__(self, tcp_port: int, server_name: str):
        """
        Initialize the broadcaster.

        Args:
            tcp_port: The TCP port clients should connect to
            server_name: The server's team name
        """
        self.tcp_port = tcp_port
        self.server_name = server_name
        self.running = False
        self.socket: Optional[socket.socket] = None
        self.thread: Optional[threading.Thread] = None

        # Pre-encode the offer message (it never changes)
        self.offer_message = encode_offer(tcp_port, server_name)

    def start(self):
        """Start broadcasting offers in a background thread."""
        self.running = True

        # Create UDP socket for broadcasting
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # Always set SO_REUSEADDR for address reuse
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Also try SO_REUSEPORT if available (Linux/Mac)
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass

        # Start broadcast thread
        self.thread = threading.Thread(target=self._broadcast_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop broadcasting and clean up resources."""
        self.running = False
        if self.socket:
            self.socket.close()
            self.socket = None

    def _broadcast_loop(self):
        """Main broadcast loop. Runs in a separate thread."""
        while self.running:
            try:
                self.socket.sendto(
                    self.offer_message,
                    (BROADCAST_ADDRESS, UDP_BROADCAST_PORT)
                )
                # Non-busy wait between broadcasts
                time.sleep(OFFER_BROADCAST_INTERVAL)
            except Exception as e:
                if self.running:
                    print(f"⚠️ Broadcast error: {e}")
                    time.sleep(OFFER_BROADCAST_INTERVAL)


# =============================================================================
# UDP LISTENER (Client-side)
# =============================================================================

class UDPListener:
    """
    Handles listening for UDP server offer broadcasts.
    """

    def __init__(self, port: int = UDP_BROADCAST_PORT):
        """
        Initialize the listener.

        Args:
            port: The UDP port to listen on
        """
        self.port = port

    def wait_for_offer(self, timeout: float = OFFER_TIMEOUT) -> Optional[Tuple[str, OfferMessage]]:
        """
        Wait for a server offer broadcast.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            Tuple of (server_ip, OfferMessage) if received, None on timeout
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Always set SO_REUSEADDR for address reuse
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Also try SO_REUSEPORT if available (Linux/Mac)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
        
        try:
            sock.bind(('', self.port))
            sock.settimeout(timeout)
            
            # Blocking wait for offer (not busy-wait)
            data, addr = sock.recvfrom(UDP_BUFFER_SIZE)
            
            # Decode the offer
            offer = decode_offer(data)
            if offer is None:
                return None
            
            return (addr[0], offer)
            
        except socket.timeout:
            return None
        except Exception as e:
            print(f"⚠️ UDP listener error: {e}")
            return None
        finally:
            sock.close()


# =============================================================================
# TCP SERVER
# =============================================================================

class TCPServer:
    """
    Handles TCP server operations: listening and accepting connections.
    Supports dynamic port assignment (pass port=0 to let OS choose).
    """
    
    def __init__(self, port: int = 0):
        """
        Initialize the TCP server.
        
        Args:
            port: The port to listen on. Use 0 to let OS assign an available port.
        """
        self.requested_port = port
        self.actual_port: int = 0  # Will be set after binding
        self.socket: Optional[socket.socket] = None
        self.running = False
    
    def get_port(self) -> int:
        """
        Get the actual port the server is listening on.
        Must be called after start() to get the dynamically assigned port.
        
        Returns:
            The actual TCP port number
        """
        return self.actual_port
    
    def bind(self) -> int:
        """
        Bind the server socket and return the assigned port.
        Call this before start() if you need to know the port early
        (e.g., for UDP broadcast).
        
        Returns:
            The actual TCP port number
        """
        if self.socket is None:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(('', self.requested_port))
            self.actual_port = self.socket.getsockname()[1]
        return self.actual_port
    
    def start(self, connection_handler: Callable[['TCPConnection', Tuple[str, int]], None]):
        """
        Start listening for connections and dispatch to handler.
        
        Args:
            connection_handler: Function to call for each new connection.
                               Receives (TCPConnection, client_address).
        """
        self.running = True
        
        # Bind if not already bound
        if self.socket is None:
            self.bind()
        
        try:
            self.socket.listen(5)
            
            # Set a timeout so accept() doesn't block forever
            # This allows Ctrl+C to work on Windows
            self.socket.settimeout(1.0)
            
            while self.running:
                try:
                    # Blocking accept with timeout (not busy-wait, just interruptible)
                    client_socket, client_addr = self.socket.accept()
                    
                    # Wrap in TCPConnection
                    connection = TCPConnection(client_socket)
                    
                    # Handle client in separate thread
                    client_thread = threading.Thread(
                        target=self._handle_connection,
                        args=(connection_handler, connection, client_addr),
                        daemon=True
                    )
                    client_thread.start()
                    
                except socket.timeout:
                    # This is expected - just continue the loop to check self.running
                    continue
                except socket.error as e:
                    if self.running:
                        print(f"⚠️ Accept error: {e}")
                        
        except Exception as e:
            raise RuntimeError(f"Failed to start TCP server: {e}")
    
    def _handle_connection(self, handler: Callable, connection: 'TCPConnection', addr: Tuple[str, int]):
        """Wrapper to ensure connection cleanup after handler completes."""
        try:
            handler(connection, addr)
        finally:
            connection.close()
    
    def stop(self):
        """Stop the server and clean up resources."""
        self.running = False
        if self.socket:
            self.socket.close()
            self.socket = None


# =============================================================================
# TCP CONNECTION (Wrapper for client-server communication)
# =============================================================================

class TCPConnection:
    """
    Wraps a TCP socket with game-specific send/receive methods.
    Used by both client and server for clean communication.
    
    IMPORTANT: Uses buffered reading to handle TCP stream framing.
    TCP may combine multiple sends into one receive, or split one send
    into multiple receives. This class handles both cases correctly.
    """
    
    def __init__(self, sock: socket.socket, timeout: float = TCP_TIMEOUT):
        """
        Initialize the connection wrapper.
        
        Args:
            sock: The TCP socket to wrap
            timeout: Default timeout for operations
        """
        self.socket = sock
        self.socket.settimeout(timeout)
        self._closed = False
        self._buffer = b""  # Buffer for incomplete messages
    
    @classmethod
    def connect(cls, host: str, port: int, timeout: float = TCP_TIMEOUT) -> 'TCPConnection':
        """
        Create a new connection to a server.
        
        Args:
            host: Server hostname or IP
            port: Server port
            timeout: Connection timeout
            
        Returns:
            New TCPConnection instance
            
        Raises:
            ConnectionError: If connection fails
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        
        try:
            sock.connect((host, port))
            return cls(sock, timeout)
        except socket.timeout:
            sock.close()
            raise ConnectionError(f"Connection to {host}:{port} timed out")
        except ConnectionRefusedError:
            sock.close()
            raise ConnectionError(f"Connection to {host}:{port} refused")
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
    
    # =========================================================================
    # RAW SEND/RECEIVE
    # =========================================================================
    
    def send_raw(self, data: bytes) -> bool:
        """
        Send raw bytes over the connection.
        
        Args:
            data: Bytes to send
            
        Returns:
            True if successful, False on error
        """
        try:
            self.socket.sendall(data)
            return True
        except Exception as e:
            print(f"⚠️ Send error: {e}")
            return False
    
    def receive_exact(self, num_bytes: int) -> Optional[bytes]:
        """
        Receive exactly the specified number of bytes.
        Uses internal buffer to handle TCP stream framing.
        
        Args:
            num_bytes: Exact number of bytes to receive
            
        Returns:
            Exactly num_bytes bytes, or None on error/timeout
        """
        # Keep receiving until we have enough bytes in the buffer
        while len(self._buffer) < num_bytes:
            try:
                chunk = self.socket.recv(TCP_BUFFER_SIZE)
                if not chunk:
                    # Connection closed
                    return None
                self._buffer += chunk
            except socket.timeout:
                return None
            except ConnectionResetError:
                return None
            except Exception as e:
                print(f"⚠️ Receive error: {e}")
                return None
        
        # Extract the requested bytes from buffer
        result = self._buffer[:num_bytes]
        self._buffer = self._buffer[num_bytes:]
        return result
    
    def receive_raw(self, buffer_size: int = TCP_BUFFER_SIZE) -> Optional[bytes]:
        """
        Receive raw bytes from the connection (for variable-length messages).
        Note: For fixed-size messages, use receive_exact() instead.
        
        Args:
            buffer_size: Maximum bytes to receive
            
        Returns:
            Received bytes, or None on error/timeout
        """
        # If we have buffered data, return it first
        if self._buffer:
            result = self._buffer[:buffer_size]
            self._buffer = self._buffer[buffer_size:]
            return result
        
        try:
            data = self.socket.recv(buffer_size)
            if not data:
                return None
            return data
        except socket.timeout:
            return None
        except ConnectionResetError:
            return None
        except Exception as e:
            print(f"⚠️ Receive error: {e}")
            return None
    
    # =========================================================================
    # GAME REQUEST (Client → Server)
    # =========================================================================
    
    # Request message size: 4 (magic) + 1 (type) + 1 (rounds) + 32 (name) = 38 bytes
    REQUEST_SIZE = 38
    
    def send_request(self, num_rounds: int, client_name: str) -> bool:
        """
        Send a game request to the server.
        
        Args:
            num_rounds: Number of rounds to play
            client_name: Client's team name
            
        Returns:
            True if successful
        """
        data = encode_request(num_rounds, client_name)
        return self.send_raw(data)
    
    def receive_request(self) -> Optional[RequestMessage]:
        """
        Receive a game request from a client.
        
        Returns:
            RequestMessage if valid, None on error
        """
        data = self.receive_exact(self.REQUEST_SIZE)
        if data is None:
            return None
        return decode_request(data)
    
    # =========================================================================
    # SERVER PAYLOAD (Server → Client)
    # =========================================================================
    
    # Server payload size: 4 (magic) + 1 (type) + 1 (result) + 2 (rank) + 1 (suit) = 9 bytes
    SERVER_PAYLOAD_SIZE = 9
    
    def send_card(self, result: int, card_rank: int, card_suit: int) -> bool:
        """
        Send a card and game state to the client.
        
        Args:
            result: Game result (0=ongoing, 1=tie, 2=loss, 3=win)
            card_rank: Card rank 1-13 (0 for no card)
            card_suit: Card suit 0-3
            
        Returns:
            True if successful
        """
        data = encode_server_payload(result, card_rank, card_suit)
        return self.send_raw(data)
    
    def send_result(self, result: int) -> bool:
        """
        Send just a result (no card) to the client.
        
        Args:
            result: Game result code
            
        Returns:
            True if successful
        """
        return self.send_card(result, 0, 0)
    
    def receive_server_payload(self) -> Optional[ServerPayload]:
        """
        Receive a server payload (card + result).
        
        Returns:
            ServerPayload if valid, None on error
        """
        data = self.receive_exact(self.SERVER_PAYLOAD_SIZE)
        if data is None:
            return None
        return decode_server_payload(data)
    
    # =========================================================================
    # CLIENT PAYLOAD (Client → Server)
    # =========================================================================
    
    # Client payload size: 4 (magic) + 1 (type) + 5 (decision) = 10 bytes
    CLIENT_PAYLOAD_SIZE = 10
    
    def send_decision(self, decision: str) -> bool:
        """
        Send a hit/stand decision to the server.
        
        Args:
            decision: "hit" or "stand"
            
        Returns:
            True if successful
        """
        try:
            data = encode_client_payload(decision)
            return self.send_raw(data)
        except ValueError as e:
            print(f"⚠️ Invalid decision: {e}")
            return False
    
    def receive_decision(self) -> Optional[ClientPayload]:
        """
        Receive a client decision (hit/stand).
        
        Returns:
            ClientPayload if valid, None on error
        """
        data = self.receive_exact(self.CLIENT_PAYLOAD_SIZE)
        if data is None:
            return None
        return decode_client_payload(data)
