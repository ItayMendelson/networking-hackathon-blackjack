#!/usr/bin/env python3
"""
Blackjack Network Game - Server (Dealer)
=========================================
The server acts as the dealer in the blackjack game.
It broadcasts UDP offers and handles TCP game sessions.

Usage:
    python server.py
    python server.py "Team Name"
    python server.py "Team Name" 12345
"""

import random
import sys
from variables import *
from network_protocol import *

# =============================================================================
# CARD AND DECK
# =============================================================================

class Card:
    """Represents a playing card."""

    def __init__(self, rank, suit):
        """
        Initialize a card.
        Args:
            rank: 1-13 (1=Ace, 11=Jack, 12=Queen, 13=King)
            suit: 0-3 (Hearts, Diamonds, Clubs, Spades)
        """
        self.rank = rank
        self.suit = suit

    @property
    def value(self):
        """Get the blackjack value."""
        return CARD_VALUES[self.rank]

    @property
    def name(self):
        """Get human-readable name."""
        return f"{RANKS[self.rank]}{SUIT_SYMBOLS[self.suit]}"

    def __repr__(self):
        return self.name


class Deck:
    """A standard 52-card deck."""

    def __init__(self):
        self.cards = []
        self.reset()

    def reset(self):
        """Reset and shuffle the deck."""
        # Creates all 52 cards
        self.cards = [Card(rank, suit) for suit in range(4) for rank in range(1, 14)]
        random.shuffle(self.cards)

    def draw(self):
        """Draw a card. Resets if empty."""
        if not self.cards:
            self.reset()
        return self.cards.pop()


def calculate_hand_value(cards):
    """Calculate total hand value."""
    return sum(card.value for card in cards)


def format_hand(cards, hide_second=False):
    """Format a hand for display."""
    if hide_second and len(cards) >= 2:
        return f"[{cards[0].name}] [🂠 Hidden]"
    return " ".join(f"[{card.name}]" for card in cards)


# =============================================================================
# BLACKJACK SERVER
# =============================================================================

class BlackjackServer:
    """The Blackjack dealer server."""

    def __init__(self, server_name=DEFAULT_TEAM_NAME, tcp_port=DEFAULT_TCP_PORT):
        self.server_name = server_name
        self.requested_port = tcp_port

        # Network components
        self.tcp_server = TCPServer(tcp_port)
        self.broadcaster: UDPBroadcaster = None

        # Statistics
        self.total_games = 0
        self.total_wins = 0    # Dealer wins
        self.total_losses = 0  # Dealer losses (player wins)
        self.total_ties = 0

    def start(self):
        """Start the server."""
        # Bind TCP first to get the actual port
        actual_port = self.tcp_server.bind()

        # Create broadcaster with actual port
        self.broadcaster = UDPBroadcaster(actual_port, self.server_name)

        # Get local IP
        local_ip = get_local_ip()

        # Print startup banner
        self._print_banner()
        print(f"🎰 Server started, listening on IP address {local_ip}")
        print(f"📌 Accepting TCP connections on port {actual_port}")
        print(f"🏷️  Server name: {self.server_name}")
        print("=" * 60)
        print()

        # Start UDP broadcast
        self.broadcaster.start()
        print(f"📢 Broadcasting offers every second on port 13122...")
        print(f"👂 Waiting for players to connect...")
        print()

        # Start TCP listener (blocking)
        try:
            self.tcp_server.start(self._handle_client)
        except KeyboardInterrupt:
            self.stop()

    def _print_banner(self):
        """Print startup banner."""
        print()
        print("=" * 60)
        print("🃏" + " " * 20 + "BLACKJACK SERVER" + " " * 20 + "🃏")
        print("=" * 60)
        print("         ♠ ♥ ♦ ♣  The Dealer Awaits  ♣ ♦ ♥ ♠")
        print("=" * 60)

    def _handle_client(self, conn, client_addr):
        """Handle a client connection."""
        client_id = f"{client_addr[0]}:{client_addr[1]}"
        print(f"🔗 New connection from {client_id}")

        try:
            # Receive request
            request = conn.receive_request()
            if request is None:
                print(f"❌ [{client_id}] Invalid request - disconnecting")
                return

            client_name = request.client_name
            num_rounds = request.num_rounds
            print(f"🎮 {client_name} wants to play {num_rounds} round(s)")

            # Play the rounds
            client_wins = 0
            client_losses = 0
            client_ties = 0

            for round_num in range(1, num_rounds + 1):
                print(f"\n{'─' * 40}")
                print(f"🎲 Round {round_num}/{num_rounds} with {client_name}")
                print(f"{'─' * 40}")

                result = self._play_round(conn, client_name)

                if result == RESULT_WIN:  # Client wins
                    client_wins += 1
                    self.total_losses += 1
                elif result == RESULT_LOSS:  # Client loses
                    client_losses += 1
                    self.total_wins += 1
                else:  # Tie
                    client_ties += 1
                    self.total_ties += 1

                self.total_games += 1

            # Session summary
            print(f"\n{'=' * 40}")
            print(f"📊 Session complete with {client_name}")
            print(f"   Player wins: {client_wins} | Losses: {client_losses} | Ties: {client_ties}")
            print(f"{'=' * 40}\n")

        except Exception as e:
            print(f"❌ [{client_id}] Error: {e}")

    def _play_round(self, conn, client_name):
        """
        Play a single round of blackjack.
        Returns the result from the CLIENT's perspective.
        """
        deck = Deck()

        # Deal initial cards
        player_cards = [deck.draw(), deck.draw()]
        dealer_cards = [deck.draw(), deck.draw()]

        player_value = calculate_hand_value(player_cards)
        dealer_value = calculate_hand_value(dealer_cards)

        print(f"🎴 Dealer's hand: {format_hand(dealer_cards, hide_second=True)}")
        print(f"🎴 {client_name}'s hand: {format_hand(player_cards)} (Value: {player_value})")

        # Send initial cards: player's 2 cards + dealer's visible card
        conn.send_card(RESULT_NOT_OVER, player_cards[0].rank, player_cards[0].suit)
        conn.send_card(RESULT_NOT_OVER, player_cards[1].rank, player_cards[1].suit)
        conn.send_card(RESULT_NOT_OVER, dealer_cards[0].rank, dealer_cards[0].suit)

        # Set longer timeout for player decisions
        conn.set_timeout(PLAYER_DECISION_TIMEOUT)

        # ===== PLAYER TURN =====
        while True:
            decision = conn.receive_decision()

            if decision is None:
                print(f"⏰ {client_name} timed out, treating as stand")
                break

            if decision.decision == "Stand":
                print(f"✋ {client_name} stands with {player_value}")
                break

            elif decision.decision == "Hit":
                new_card = deck.draw()
                player_cards.append(new_card)
                player_value = calculate_hand_value(player_cards)

                print(f"🔥 {client_name} hits! Drew {new_card.name}")
                print(f"🎴 {client_name}'s hand: {format_hand(player_cards)} (Value: {player_value})")

                if player_value > BUST_THRESHOLD:
                    # Player busts
                    print(f"{COLOR_GREEN}💥 {client_name} BUSTS with {player_value}!{COLOR_RESET}")
                    conn.send_card(RESULT_LOSS, new_card.rank, new_card.suit)
                    return RESULT_LOSS
                else:
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

            print(f"🔥 Dealer hits! Drew {new_card.name}")
            print(f"🎴 Dealer's hand: {format_hand(dealer_cards)} (Value: {dealer_value})")

            if dealer_value > BUST_THRESHOLD:
                # Dealer busts - client wins
                print(f"{COLOR_RED}💥 Dealer BUSTS with {dealer_value}!{COLOR_RESET}")
                conn.send_card(RESULT_WIN, new_card.rank, new_card.suit)
                return RESULT_WIN
            else:
                conn.send_card(RESULT_NOT_OVER, new_card.rank, new_card.suit)

        # ===== DETERMINE WINNER =====
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

        conn.send_result(result)
        return result

    def stop(self):
        """Stop the server gracefully."""
        if self.broadcaster:
            self.broadcaster.stop()
        self.tcp_server.stop()

        print("\n🛑 Server stopped")
        print(f"📊 Total games played: {self.total_games}")
        print(f"   Dealer wins: {self.total_wins}")
        print(f"   Player wins: {self.total_losses}")
        print(f"   Ties: {self.total_ties}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point."""
    server_name = DEFAULT_TEAM_NAME
    tcp_port = DEFAULT_TCP_PORT

    # Parse command line arguments
    if len(sys.argv) >= 2:
        server_name = sys.argv[1]
    if len(sys.argv) >= 3:
        try:
            tcp_port = int(sys.argv[2])
        except ValueError:
            print(f"⚠️ Invalid port: {sys.argv[2]}, using auto-assign")
            tcp_port = 0

    server = BlackjackServer(server_name=server_name, tcp_port=tcp_port)

    try:
        server.start()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        server.stop()


if __name__ == "__main__":
    main()
