#!/usr/bin/env python3
"""
Blackjack Network Game - Client (Player)
=========================================
The client connects to a blackjack server and plays rounds.

Usage:
    python client.py
    python client.py "Team Name"
"""

import random
import sys
from variables import *
from network_protocol import *


# =============================================================================
# CARD UTILITIES
# =============================================================================

class Card:
    """Represents a playing card received from the server."""

    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit

    @property
    def value(self):
        """Get blackjack value."""
        if self.rank == 0:
            return 0
        return CARD_VALUES.get(self.rank, 0)

    @property
    def name(self):
        """Get human-readable name."""
        if self.rank == 0:
            return "??"
        return f"{RANKS[self.rank]}{SUIT_SYMBOLS[self.suit]}"

    def __repr__(self):
        return self.name


def format_hand(cards):
    """Format a list of cards for display."""
    return " ".join(f"[{card.name}]" for card in cards)


def calculate_hand_value(cards):
    """Calculate total hand value."""
    return sum(card.value for card in cards)


# =============================================================================
# BLACKJACK CLIENT
# =============================================================================

class BlackjackClient:
    """The Blackjack player client."""

    def __init__(self, team_name=DEFAULT_TEAM_NAME):
        self.team_name = team_name
        self.running = False

        # Network
        self.udp_listener = UDPListener()

        # Lifetime statistics
        self.total_rounds = 0
        self.total_wins = 0
        self.total_losses = 0
        self.total_ties = 0

    def start(self):
        """Start the client."""
        self.running = True

        self._print_banner()
        print(f"🏷️  Playing as: {self.team_name}")
        print("=" * 60)
        print()

        # Main loop - keep playing until quit
        while self.running:
            try:
                # Get number of rounds
                num_rounds = self._get_num_rounds()
                if num_rounds == 0:
                    continue

                # Look for a server
                print(f"\n👂 Client started, listening for offer requests...")
                result = self.udp_listener.wait_for_offer()

                if result is None:
                    print("⏰ No server found. Retrying...")
                    continue

                server_ip, offer = result
                print(f"📡 Received offer from server \"{offer.server_name}\" at {server_ip}, port {offer.tcp_port}")

                # Connect and play
                self._play_session(server_ip, offer.tcp_port, num_rounds)

            except KeyboardInterrupt:
                print("\n👋 Quitting...")
                self.running = False
            except Exception as e:
                print(f"❌ Error: {e}")

        self._print_final_stats()

    def _print_banner(self):
        """Print startup banner."""
        print()
        print("=" * 60)
        print("🃏" + " " * 20 + "BLACKJACK CLIENT" + " " * 20 + "🃏")
        print("=" * 60)
        print("         ♠ ♥ ♦ ♣  Ready to Play!  ♣ ♦ ♥ ♠")
        print("=" * 60)

    def _get_num_rounds(self):
        """Ask the user how many rounds to play. 255 is the maximum as the
         protocol uses one Byte for the number of rounds:
          2^8-1 (0 rounds) = 255"""
        while True:
            try:
                rounds_input = input("\n🎮 How many rounds would you like to play? (1-255): ").strip()
                num_rounds = int(rounds_input)
                if 1 <= num_rounds <= 255:
                    return num_rounds
                print("⚠️ Please enter a number between 1 and 255!")
            except ValueError:
                print("⚠️ Please enter a valid number!")
            except (EOFError, KeyboardInterrupt):
                raise KeyboardInterrupt

    def _play_session(self, server_ip, server_port, num_rounds):
        """Connect to server and play the requested rounds."""
        print(f"\n🔌 Connecting to {server_ip}:{server_port}...")

        try:
            conn = TCPConnection.connect(server_ip, server_port)
        except ConnectionError as e:
            print(f"❌ Connection failed: {e}")
            return

        print("✅ Connected!")

        # Reset session stats
        session_wins = 0
        session_losses = 0
        session_ties = 0

        try:
            # Send request
            conn.send_request(num_rounds, self.team_name)

            # Play rounds
            for round_num in range(1, num_rounds + 1):
                print(f"\n{'═' * 50}")
                print(f"🎲 ROUND {round_num}/{num_rounds}")
                print(f"{'═' * 50}")

                result = self._play_round(conn, round_num)

                if result == RESULT_WIN:
                    session_wins += 1
                    self.total_wins += 1
                elif result == RESULT_LOSS:
                    session_losses += 1
                    self.total_losses += 1
                elif result == RESULT_TIE:
                    session_ties += 1
                    self.total_ties += 1
                else:
                    # Disconnected
                    print("🔌 Connection lost!")
                    break

                self.total_rounds += 1

            # Print session summary
            total_played = session_wins + session_losses + session_ties
            if total_played > 0:
                win_rate = session_wins / total_played * 100
                print(f"\n{'═' * 50}")
                print(f"📊 Finished playing {total_played} rounds, win rate: {win_rate:.1f}%")
                print(f"   Wins: {session_wins} | Losses: {session_losses} | Ties: {session_ties}")
                print(f"{'═' * 50}")

        except Exception as e:
            print(f"❌ Error during session: {e}")
        finally:
            conn.close()
            print("\n🔌 Disconnected from server")

    def _play_round(self, conn: TCPConnection, round_num):
        """
        Play a single round.
        Returns RESULT_WIN, RESULT_LOSS, RESULT_TIE, or -1 for disconnect.
        """
        DISCONNECTED = -1

        try:
            my_cards = []
            dealer_cards = []

            # Receive my first two cards
            for _ in range(2):
                payload = conn.receive_server_payload()
                if payload is None:
                    return DISCONNECTED
                my_cards.append(Card(payload.card_rank, payload.card_suit))

            # Receive dealer's visible card
            payload = conn.receive_server_payload()
            if payload is None:
                return DISCONNECTED
            dealer_cards.append(Card(payload.card_rank, payload.card_suit))

            # Display initial hands
            my_value = calculate_hand_value(my_cards)
            print(f"\n🎴 Your hand: {format_hand(my_cards)} (Value: {my_value})")
            print(f"🎴 Dealer shows: {format_hand(dealer_cards)} [🂠 Hidden]")

            # ===== PLAYER TURN =====
            while True:
                my_value = calculate_hand_value(my_cards)
                decision = self._get_decision(my_value)

                conn.send_decision(decision)

                if decision.lower() == "stand":
                    print(f"\n✋ You stand with {my_value}")
                    break

                # Hit - receive new card
                print(f"\n🔥 Hitting...")
                payload = conn.receive_server_payload()
                if payload is None:
                    return DISCONNECTED

                new_card = Card(payload.card_rank, payload.card_suit)
                my_cards.append(new_card)
                my_value = calculate_hand_value(my_cards)

                print(f"🎴 You drew: [{new_card.name}]")
                print(f"🎴 Your hand: {format_hand(my_cards)} (Value: {my_value})")

                # Check if round is over
                if payload.result == RESULT_LOSS:
                    print(f"\n{COLOR_RED}💥 BUST! You went over 21!")
                    print(f"{random.choice(BUST_MESSAGES)}{COLOR_RESET}")
                    return RESULT_LOSS
                elif payload.result == RESULT_WIN:
                    return RESULT_WIN
                elif payload.result == RESULT_TIE:
                    return RESULT_TIE

            # ===== DEALER TURN =====
            print(f"\n{'─' * 40}")
            print("🎰 DEALER'S TURN")
            print(f"{'─' * 40}")

            # Receive dealer's hidden card
            payload = conn.receive_server_payload()
            if payload is None:
                return DISCONNECTED

            dealer_cards.append(Card(payload.card_rank, payload.card_suit))
            dealer_value = calculate_hand_value(dealer_cards)
            print(f"🎴 Dealer reveals: {format_hand(dealer_cards)} (Value: {dealer_value})")

            # Receive additional dealer cards
            while payload.result == RESULT_NOT_OVER:
                payload = conn.receive_server_payload()
                if payload is None:
                    return DISCONNECTED

                if payload.card_rank > 0:
                    new_card = Card(payload.card_rank, payload.card_suit)
                    dealer_cards.append(new_card)
                    dealer_value = calculate_hand_value(dealer_cards)
                    print(f"🎴 Dealer draws: [{new_card.name}]")
                    print(f"🎴 Dealer's hand: {format_hand(dealer_cards)} (Value: {dealer_value})")

            # ===== RESULT =====
            result = payload.result
            my_value = calculate_hand_value(my_cards)
            dealer_value = calculate_hand_value(dealer_cards)

            print(f"\n{'─' * 40}")
            print(f"📊 FINAL: You = {my_value} | Dealer = {dealer_value}")

            if result == RESULT_WIN:
                if dealer_value > BUST_THRESHOLD:
                    print(f"\n{COLOR_GREEN}🎉 {random.choice(DEALER_BUST_MESSAGES)}{COLOR_RESET}")
                else:
                    print(f"\n{COLOR_GREEN}🎉 {random.choice(WIN_MESSAGES)}{COLOR_RESET}")
            elif result == RESULT_LOSS:
                print(f"\n{COLOR_RED}😢 {random.choice(LOSE_MESSAGES)}{COLOR_RESET}")
            else:
                print(f"\n{COLOR_YELLOW}🤝 {random.choice(TIE_MESSAGES)}{COLOR_RESET}")

            return result

        except Exception as e:
            print(f"❌ Error during round: {e}")
            return DISCONNECTED

    def _get_decision(self, current_value):
        """Get the player's hit/stand decision."""
        while True:
            try:
                print(f"\n🤔 Your hand value: {current_value}")
                choice = input("   [H]it or [S]tand? ").strip().lower()

                if choice in ['h', 'hit']:
                    return 'hit'
                elif choice in ['s', 'stand']:
                    return 'stand'
                else:
                    print("⚠️ Please enter 'H' for Hit or 'S' for Stand!")
            except EOFError:
                return 'stand'

    def _print_final_stats(self):
        """Print lifetime statistics."""
        if self.total_rounds > 0:
            win_rate = self.total_wins / self.total_rounds * 100
            print("\n" + "=" * 50)
            print("📊 LIFETIME STATISTICS")
            print("=" * 50)
            print(f"   Total rounds played: {self.total_rounds}")
            print(f"   Wins: {self.total_wins}")
            print(f"   Losses: {self.total_losses}")
            print(f"   Ties: {self.total_ties}")
            print(f"   Overall win rate: {win_rate:.1f}%")
            print("=" * 50)


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point."""
    team_name = DEFAULT_TEAM_NAME

    if len(sys.argv) >= 2:
        team_name = sys.argv[1]

    client = BlackjackClient(team_name=team_name)
    client.start()


if __name__ == "__main__":
    main()
