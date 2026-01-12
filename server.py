#!/usr/bin/env python3
"""
Blackjack Network Game - Server (Dealer)
=========================================
The server acts as the dealer in the blackjack game.
It broadcasts UDP offers and handles TCP game sessions.

Features:
- UDP broadcast to advertise the server
- Multi-threaded TCP handling for multiple clients
- Full blackjack game logic
- Fun and engaging output

Usage:
    python server.py
    python server.py "Team Name"
    python server.py "Team Name" 12345
"""

import random
import sys
from typing import List, Tuple

from variables import *
from network import (
    UDPBroadcaster, TCPServer, TCPConnection,
    get_local_ip
)


# =============================================================================
# CARD AND DECK UTILITIES
# =============================================================================

class Card:
    """Represents a playing card with rank and suit."""

    def __init__(self, rank: int, suit: int):
        """
        Initialize a card.

        Args:
            rank: Card rank (1-13, where 1=Ace, 11=Jack, 12=Queen, 13=King)
            suit: Card suit (0-3: Hearts, Diamonds, Clubs, Spades)
        """
        self.rank = rank
        self.suit = suit

    @property
    def value(self) -> int:
        """Get the blackjack value of this card."""
        return CARD_VALUES[self.rank]

    @property
    def name(self) -> str:
        """Get a human-readable name for this card."""
        return f"{RANKS[self.rank]}{SUIT_SYMBOLS[self.suit]}"

    def __repr__(self) -> str:
        return self.name


class Deck:
    """A standard 52-card deck that can be shuffled and dealt from."""

    def __init__(self):
        """Create and shuffle a new deck."""
        self.cards: List[Card] = []
        self.reset()

    def reset(self):
        """Reset and shuffle the deck."""
        self.cards = [Card(rank, suit) for suit in range(4) for rank in range(1, 14)]
        random.shuffle(self.cards)

    def draw(self) -> Card:
        """Draw a card from the deck. Resets if empty."""
        if not self.cards:
            self.reset()
        return self.cards.pop()


def calculate_hand_value(cards: List[Card]) -> int:
    """
    Calculate the total value of a hand.
    Note: This simplified version treats Ace as always 11.

    Args:
        cards: List of cards in the hand

    Returns:
        Total hand value
    """
    return sum(card.value for card in cards)


def format_hand(cards: List[Card], hide_second: bool = False) -> str:
    """
    Format a hand for display.

    Args:
        cards: List of cards
        hide_second: If True, hide the second card (dealer's hidden card)

    Returns:
        Formatted string representation
    """
    if hide_second and len(cards) >= 2:
        return f"[{cards[0].name}] [🂠 Hidden]"
    return " ".join(f"[{card.name}]" for card in cards)


# =============================================================================
# SERVER CORE
# =============================================================================

class BlackjackServer:
    """
    The Blackjack dealer server.
    Handles UDP broadcasting and TCP game sessions.
    """

    def __init__(self, server_name: str = DEFAULT_TEAM_NAME, tcp_port: int = DEFAULT_TCP_PORT):
        """
        Initialize the server.

        Args:
            server_name: The server's name (sent in offer broadcasts)
            tcp_port: The TCP port to listen on (0 = auto-assign)
        """
        self.server_name = server_name
        self.requested_port = tcp_port

        # Network components (broadcaster created after we know the port)
        self.tcp_server = TCPServer(tcp_port)
        self.broadcaster: UDPBroadcaster = None

        # Statistics
        self.total_games = 0
        self.total_wins = 0
        self.total_losses = 0
        self.total_ties = 0

    def start(self):
        """Start the server and begin accepting connections."""
        # Bind TCP server first to get the actual port
        actual_port = self.tcp_server.bind()

        # Now create broadcaster with the actual port
        self.broadcaster = UDPBroadcaster(actual_port, self.server_name)

        # Get the local IP address
        local_ip = get_local_ip()

        # Print startup banner
        self._print_banner()
        print(f"🎰 Server started, listening on IP address {local_ip}")
        print(f"📡 Broadcasting offers to find players...")
        print(f"🔌 Accepting TCP connections on port {actual_port}")
        print(f"🏷️  Server name: {self.server_name}")
        print("=" * 60)
        print()

        # Start UDP broadcast thread
        self.broadcaster.start()
        print(f"📢 Broadcasting offers every second...")
        print(f"👂 Listening for TCP connections on port {actual_port}...")
        print()

        # Start TCP listener (blocking)
        self.tcp_server.start(self._handle_client)

    def _print_banner(self):
        """Print a fancy startup banner."""
        print()
        print("=" * 60)
        print("🃏" + " " * 20 + "BLACKJACK SERVER" + " " * 20 + "🃏")
        print("=" * 60)
        print("         ♠ ♥ ♦ ♣  The Dealer Awaits  ♣ ♦ ♥ ♠")
        print("=" * 60)

    def _handle_client(self, conn: TCPConnection, client_addr: Tuple[str, int]):
        """
        Handle a client connection and play the requested rounds.

        Args:
            conn: The TCP connection wrapper
            client_addr: The client's address tuple
        """
        client_id = f"{client_addr[0]}:{client_addr[1]}"
        print(f"🔗 New connection from {client_id}")

        try:
            # Receive the request message
            request = conn.receive_request()
            if request is None:
                print(f"❌ [{client_id}] Invalid or empty request - client may have disconnected")
                return

            client_name = request.client_name
            num_rounds = request.num_rounds

            print(f"🎮 {client_name} wants to play {num_rounds} round(s)")

            # Play the requested rounds
            client_wins = 0
            client_losses = 0
            client_ties = 0

            for round_num in range(1, num_rounds + 1):
                print(f"\n{'─' * 40}")
                print(f"🎲 Round {round_num}/{num_rounds} with {client_name}")
                print(f"{'─' * 40}")

                result = self._play_round(conn, client_name)

                if result == RESULT_WIN:
                    client_wins += 1
                    self.total_losses += 1
                elif result == RESULT_LOSS:
                    client_losses += 1
                    self.total_wins += 1
                else:
                    client_ties += 1
                    self.total_ties += 1

                self.total_games += 1

            # Print session summary
            print(f"\n{'=' * 40}")
            print(f"📊 Session complete with {client_name}")
            print(f"   Wins: {client_wins} | Losses: {client_losses} | Ties: {client_ties}")
            print(f"{'=' * 40}\n")

        except Exception as e:
            print(f"❌ {client_addr}: Error handling client: {e}")

    def _play_round(self, conn: TCPConnection, client_name: str) -> int:
        """
        Play a single round of blackjack.

        Args:
            conn: The TCP connection wrapper
            client_name: The client's name for display

        Returns:
            Result code (from client's perspective): WIN, LOSS, or TIE
        """
        # Create a fresh shuffled deck
        deck = Deck()

        # Deal initial cards
        player_cards: List[Card] = [deck.draw(), deck.draw()]
        dealer_cards: List[Card] = [deck.draw(), deck.draw()]

        player_value = calculate_hand_value(player_cards)
        dealer_value = calculate_hand_value(dealer_cards)

        print(f"🎴 Dealer's hand: {format_hand(dealer_cards, hide_second=True)}")
        print(f"🎴 {client_name}'s hand: {format_hand(player_cards)} (Value: {player_value})")

        # Send initial cards to client (player's two cards + dealer's visible card)
        conn.send_card(RESULT_NOT_OVER, player_cards[0].rank, player_cards[0].suit)
        conn.send_card(RESULT_NOT_OVER, player_cards[1].rank, player_cards[1].suit)
        conn.send_card(RESULT_NOT_OVER, dealer_cards[0].rank, dealer_cards[0].suit)

        # Set longer timeout for player decisions
        conn.set_timeout(PLAYER_DECISION_TIMEOUT)

        # ===== PLAYER TURN =====
        while True:
            # Wait for player decision
            decision = conn.receive_decision()

            if decision is None:
                print(f"⏰ {client_name} timed out or disconnected, treating as stand")
                break

            if decision.decision == "Stand":
                print(f"✋ {client_name} stands with {player_value}")
                break

            elif decision.decision == "Hit":
                # Draw a new card for the player
                new_card = deck.draw()
                player_cards.append(new_card)
                player_value = calculate_hand_value(player_cards)

                print(f"📥 {client_name} hits! Drew {new_card.name}")
                print(f"🎴 {client_name}'s hand: {format_hand(player_cards)} (Value: {player_value})")

                if player_value > BUST_THRESHOLD:
                    # Player busts!
                    print(f"{COLOR_GREEN}💥 {client_name} BUSTS with {player_value}!{COLOR_RESET}")
                    conn.send_card(RESULT_LOSS, new_card.rank, new_card.suit)
                    return RESULT_LOSS
                else:
                    # Send the card, game continues
                    conn.send_card(RESULT_NOT_OVER, new_card.rank, new_card.suit)

        # ===== DEALER TURN =====
        print(f"\n🎰 Dealer reveals: {format_hand(dealer_cards)} (Value: {dealer_value})")

        # Send dealer's hidden card
        conn.send_card(RESULT_NOT_OVER, dealer_cards[1].rank, dealer_cards[1].suit)

        # Dealer draws until 17 or bust
        while dealer_value < DEALER_STAND_THRESHOLD:
            new_card = deck.draw()
            dealer_cards.append(new_card)
            dealer_value = calculate_hand_value(dealer_cards)

            print(f"📥 Dealer hits! Drew {new_card.name}")
            print(f"🎴 Dealer's hand: {format_hand(dealer_cards)} (Value: {dealer_value})")

            if dealer_value > BUST_THRESHOLD:
                # Dealer busts - send card with WIN result
                print(f"{COLOR_RED}💥 Dealer BUSTS with {dealer_value}!{COLOR_RESET}")
                conn.send_card(RESULT_WIN, new_card.rank, new_card.suit)
                return RESULT_WIN
            else:
                # Dealer continues - send card with NOT_OVER so client can display it
                conn.send_card(RESULT_NOT_OVER, new_card.rank, new_card.suit)

        # ===== DETERMINE WINNER (dealer stood at 17+) =====
        print(f"\n📊 Final: {client_name}={player_value} vs Dealer={dealer_value}")

        if player_value > dealer_value:
            print(f"{COLOR_RED}🎉 {client_name} WINS!{COLOR_RESET}")
            result = RESULT_WIN
        elif dealer_value > player_value:
            print(f"{COLOR_GREEN}🏠 Dealer WINS!{COLOR_RESET}")
            result = RESULT_LOSS
        else:
            print(f"{COLOR_YELLOW}🤝 It's a TIE!{COLOR_RESET}")
            result = RESULT_TIE

        # Send final result (all cards already sent, just need result)
        conn.send_result(result)

        return result

    def stop(self):
        """Stop the server gracefully."""
        if self.broadcaster:
            self.broadcaster.stop()
        self.tcp_server.stop()

        print("\n🛑 Server stopped")
        print(f"📊 Total games: {self.total_games}")
        print(f"   Dealer wins: {self.total_wins}")
        print(f"   Player wins: {self.total_losses}")
        print(f"   Ties: {self.total_ties}")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point for the server."""
    server_name = DEFAULT_TEAM_NAME
    tcp_port = DEFAULT_TCP_PORT  # 0 = auto-assign

    # Allow command-line arguments for server name and port
    if len(sys.argv) >= 2:
        server_name = sys.argv[1]
    if len(sys.argv) >= 3:
        try:
            tcp_port = int(sys.argv[2])
        except ValueError:
            print(f"⚠️ Invalid port number: {sys.argv[2]}, using auto-assign")
            tcp_port = 0

    server = BlackjackServer(server_name=server_name, tcp_port=tcp_port)

    try:
        server.start()
    except KeyboardInterrupt:
        print("\n👋 Caught interrupt signal...")
        server.stop()


if __name__ == "__main__":
    main()