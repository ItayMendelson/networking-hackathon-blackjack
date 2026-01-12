#!/usr/bin/env python3
"""
Blackjack Network Game - Client (Player)
=========================================
The client connects to a blackjack server and plays rounds.

Features:
- Listens for UDP offer broadcasts
- Connects to server via TCP
- Interactive gameplay with Hit/Stand decisions
- Fun and engaging output with statistics
- Special modes: Auto-Play, Party

Usage:
    python client.py
    python client.py "Team Name"
"""

import random
import sys
import time
from typing import Optional, List

from variables import *

from network import (
    UDPListener, TCPConnection
)
from protocol import ServerPayload


# =============================================================================
# CARD UTILITIES
# =============================================================================

class Card:
    """Represents a playing card received from the server."""

    def __init__(self, rank: int, suit: int):
        """
        Initialize a card.

        Args:
            rank: Card rank (1-13)
            suit: Card suit (0-3)
        """
        self.rank = rank
        self.suit = suit

    @property
    def value(self) -> int:
        """Get the blackjack value of this card."""
        if self.rank == 0:
            return 0
        return CARD_VALUES.get(self.rank, 0)

    @property
    def name(self) -> str:
        """Get a human-readable name for this card."""
        if self.rank == 0:
            return "??"
        return f"{RANKS[self.rank]}{SUIT_SYMBOLS[self.suit]}"

    def __repr__(self) -> str:
        return self.name


def format_hand(cards: List[Card]) -> str:
    """Format a list of cards for display."""
    return " ".join(f"[{card.name}]" for card in cards)


def calculate_hand_value(cards: List[Card]) -> int:
    """Calculate the total value of a hand."""
    return sum(card.value for card in cards)


def get_random_message(category: str) -> str:
    """Get a random fun message from a category."""
    messages = MESSAGES.get(category, [""])
    return random.choice(messages)


def get_party_message(category: str) -> str:
    """Get a random party mode message."""
    messages = PARTY_MESSAGES.get(category, ["🎉"])
    return random.choice(messages)


def drunk_text(text: str) -> str:
    """Make text look 'drunk' with random effects."""
    effects = [
        lambda t: t.replace('s', 'sh').replace('S', 'Sh'),
        lambda t: t + " *hic*",
        lambda t: t.upper() + "!",
        lambda t: "".join(c.upper() if random.random() > 0.5 else c.lower() for c in t),
        lambda t: t + " 🍺",
    ]
    return random.choice(effects)(text)


def get_auto_decision(player_value: int, dealer_visible_value: int) -> str:
    """
    Get decision using basic blackjack strategy.

    Simple strategy:
    - Always hit on 11 or less
    - Always stand on 17+
    - In between: hit if dealer shows 7+, stand if dealer shows 6 or less
    """
    if player_value <= AUTO_STRATEGY_HIT_ON:
        return 'hit'
    if player_value >= AUTO_STRATEGY_STAND_ON:
        return 'stand'

    # 12-16: depends on dealer's visible card
    if dealer_visible_value >= 7:
        return 'hit'  # Dealer likely has strong hand
    else:
        return 'stand'  # Dealer might bust


# =============================================================================
# CLIENT CORE
# =============================================================================

class BlackjackClient:
    """
    The Blackjack player client.
    Listens for server offers and plays games.
    """

    def __init__(self, team_name: str = DEFAULT_TEAM_NAME):
        """
        Initialize the client.

        Args:
            team_name: The client's team name
        """
        self.team_name = team_name
        self.running = False
        self.mode = MODE_NORMAL  # Current game mode
        self.dealer_visible_value = 0  # For auto-play strategy

        # Network component
        self.udp_listener = UDPListener()

        # Lifetime statistics
        self.total_rounds = 0
        self.total_wins = 0
        self.total_losses = 0
        self.total_ties = 0

        # Session statistics
        self.session_wins = 0
        self.session_losses = 0
        self.session_ties = 0

    def _select_mode(self) -> int:
        """Let user select a game mode."""
        print("\n" + "=" * 50)
        print("🎮 SELECT GAME MODE")
        print("=" * 50)
        print(f"  {COLOR_GREEN}[1]{COLOR_RESET} 🎯 Normal Mode - Classic blackjack")
        print(f"  {COLOR_CYAN}[2]{COLOR_RESET} 🤖 Auto-Play Mode - Bot uses basic strategy")
        print(f"  {COLOR_MAGENTA}[3]{COLOR_RESET} 🎉 Party Mode - *hic* Things get weird...")
        print("=" * 50)

        while True:
            try:
                choice = input("\n🕹️  Choose mode (1-3): ").strip()

                if choice == '1':
                    print("\n🎯 Normal Mode selected - Good luck!")
                    return MODE_NORMAL
                elif choice == '2':
                    print("\n🤖 Auto-Play Mode selected - Sit back and watch!")
                    return MODE_AUTO
                elif choice == '3':
                    print(f"\n{COLOR_MAGENTA}🎉 PARTY MODE ACTIVATED! *hic* 🍺{COLOR_RESET}")
                    time.sleep(0.5)
                    return MODE_PARTY
                else:
                    print("⚠️ Please enter 1, 2, or 3!")

            except (EOFError, KeyboardInterrupt):
                return MODE_NORMAL

    def start(self):
        """Start the client and begin looking for servers."""
        self.running = True

        # Print startup banner
        self._print_banner()
        print(f"🏷️  Playing as: {self.team_name}")
        print("=" * 60)

        # Select game mode
        self.mode = self._select_mode()
        print()

        # Main client loop
        while self.running:
            try:
                # Get number of rounds from user
                num_rounds = self._get_num_rounds()

                # Look for a server
                print(f"\n👂 Client started, listening for offer requests...")
                result = self.udp_listener.wait_for_offer()

                if result is None:
                    print("⏰ No server found. Please try again :)")
                    continue

                server_ip, offer = result
                print(f"📡 Received offer from server \"{offer.server_name}\" at {server_ip}")

                # Connect and play
                self._play_session(server_ip, offer.tcp_port, offer.server_name, num_rounds)

            except KeyboardInterrupt:
                print("\n\n👋 Thanks for playing! See you next time!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                print("🔄 Restarting client loop...")

        self._print_final_stats()

    def _print_banner(self):
        """Print a fancy startup banner."""
        print()
        print("=" * 60)
        print("🃏" + " " * 20 + "BLACKJACK CLIENT" + " " * 20 + "🃏")
        print("=" * 60)
        print("        ♠ ♥ ♦ ♣  Ready to Beat the Dealer  ♣ ♦ ♥ ♠")
        print("=" * 60)

    def _get_num_rounds(self) -> int:
        """
        Get the number of rounds from the user.
        Also allows changing mode.

        Returns:
            Number of rounds to play (1-255)

        Raises:
            KeyboardInterrupt: If user types 'exit' or presses Ctrl+C
        """
        # Show current mode
        mode_names = {
            MODE_NORMAL: "🎯 Normal",
            MODE_AUTO: "🤖 Auto-Play",
            MODE_PARTY: "🎉 Party"
        }

        while True:
            try:
                print()
                print(f"Current mode: {mode_names.get(self.mode, 'Unknown')}")
                user_input = input("🎲 Rounds (1-255), 'mode' to change, or 'exit': ").strip()

                # Check for exit command
                if user_input.lower() == 'exit':
                    raise KeyboardInterrupt

                # Check for mode change
                if user_input.lower() == 'mode':
                    self.mode = self._select_mode()
                    continue

                num_rounds = int(user_input)

                if 1 <= num_rounds <= 255:
                    return num_rounds
                else:
                    print("⚠️ Please enter a number between 1 and 255!")

            except ValueError:
                print("⚠️ That's not a valid number! Please try again.")
            except EOFError:
                # Handle Ctrl+D
                raise KeyboardInterrupt

    def _play_session(self, server_ip: str, tcp_port: int, server_name: str, num_rounds: int):
        """
        Connect to a server and play the requested rounds.

        Args:
            server_ip: Server's IP address
            tcp_port: Server's TCP port
            server_name: Server's team name
            num_rounds: Number of rounds to play
        """
        # Reset session stats
        self.session_wins = 0
        self.session_losses = 0
        self.session_ties = 0
        rounds_played = 0

        try:
            # Connect to server
            print(f"🔌 Connecting to {server_name} at {server_ip}:{tcp_port}...")
            conn = TCPConnection.connect(server_ip, tcp_port)

            # Mode-specific welcome message
            if self.mode == MODE_PARTY:
                print(f"✅ Connected! {COLOR_MAGENTA}{get_party_message('welcome')}{COLOR_RESET}")
            elif self.mode == MODE_AUTO:
                print(f"✅ Connected! 🤖 Bot is ready to play!")
            else:
                print(f"✅ Connected! {get_random_message('welcome')}")

        except ConnectionError as e:
            print(f"❌ {e}")
            return

        try:
            # Send request message
            conn.send_request(num_rounds, self.team_name)

            print(f"\n🎮 Starting {num_rounds} round(s) against {server_name}!")

            # Play each round
            for round_num in range(1, num_rounds + 1):
                print(f"\n{'═' * 50}")
                print(f"🎲 ROUND {round_num} of {num_rounds}")
                print(f"{'═' * 50}")

                result = self._play_round(conn, server_name)

                # Check for disconnection
                if result == RESULT_DISCONNECTED:
                    print(f"\n{get_random_message('timeout')}")
                    print(f"🚪 Leaving the table after {rounds_played} round(s)...")
                    break

                rounds_played += 1

                if result == RESULT_WIN:
                    self.session_wins += 1
                    self.total_wins += 1
                elif result == RESULT_LOSS:
                    self.session_losses += 1
                    self.total_losses += 1
                else:
                    self.session_ties += 1
                    self.total_ties += 1

                self.total_rounds += 1

            # Print session summary
            if rounds_played > 0:
                win_rate = (self.session_wins / rounds_played * 100)
                print(f"\n{'═' * 50}")
                print(f"🏁 Session complete: {rounds_played} round(s) played")
                print(f"   Wins: {self.session_wins} | Losses: {self.session_losses} | Ties: {self.session_ties}")
                print(f"   Session win rate: {win_rate:.1f}%")
                print(f"{'═' * 50}")

            # Show lifetime stats
            self._print_session_lifetime_stats()

        except Exception as e:
            print(f"❌ Error during session: {e}")
            print(f"{get_random_message('disconnected')}")
        finally:
            conn.close()

    def _print_session_lifetime_stats(self):
        """Print lifetime statistics after each session."""
        if self.total_rounds > 0:
            win_rate = (self.total_wins / self.total_rounds * 100)
            print(f"\n📊 Lifetime stats: {self.total_rounds} rounds | "
                  f"W:{self.total_wins} L:{self.total_losses} T:{self.total_ties} | "
                  f"Win rate: {win_rate:.1f}%")

    def _play_round(self, conn: TCPConnection, server_name: str) -> int:
        """
        Play a single round of blackjack.

        Args:
            conn: TCP connection to server
            server_name: Server's name for display

        Returns:
            Result code: WIN, LOSS, TIE, or DISCONNECTED
        """
        my_cards: List[Card] = []
        dealer_cards: List[Card] = []

        try:
            # Receive initial deal: 2 player cards + 1 visible dealer card
            # First player card
            payload = conn.receive_server_payload()
            if payload is None:
                return RESULT_DISCONNECTED
            my_cards.append(Card(payload.card_rank, payload.card_suit))

            # Second player card
            payload = conn.receive_server_payload()
            if payload is None:
                return RESULT_DISCONNECTED
            my_cards.append(Card(payload.card_rank, payload.card_suit))

            # Dealer's visible card
            payload = conn.receive_server_payload()
            if payload is None:
                return RESULT_DISCONNECTED
            dealer_cards.append(Card(payload.card_rank, payload.card_suit))

            # Store dealer's visible value for auto-play strategy
            self.dealer_visible_value = dealer_cards[0].value

            # Display initial hands (with party mode effects if enabled)
            my_value = calculate_hand_value(my_cards)
            if self.mode == MODE_PARTY:
                print(f"\n{COLOR_MAGENTA}{get_party_message('dealer_cards')}{COLOR_RESET}")
                time.sleep(0.3)
                print(f"🎴 Your hand: {format_hand(my_cards)} (Value: {drunk_text(str(my_value))})")
                print(f"🎴 Dealer shows: {format_hand(dealer_cards)} [🂠 *hic* Hidden]")
            else:
                print(f"\n🎴 Your hand: {format_hand(my_cards)} (Value: {my_value})")
                print(f"🎴 Dealer shows: {format_hand(dealer_cards)} [🂠 Hidden]")

            # ===== PLAYER TURN =====
            while True:
                my_value = calculate_hand_value(my_cards)

                # Get player decision
                decision = self._get_decision(my_value)

                # Send decision to server
                conn.send_decision(decision)

                if decision.lower() == "stand":
                    print(f"\n{get_random_message('stand')}")
                    break

                # Hit - receive new card
                print(f"\n{get_random_message('hit')}")
                payload = conn.receive_server_payload()
                if payload is None:
                    return RESULT_DISCONNECTED

                new_card = Card(payload.card_rank, payload.card_suit)
                my_cards.append(new_card)
                my_value = calculate_hand_value(my_cards)

                print(f"🎴 You drew: {new_card.name}")
                print(f"🎴 Your hand: {format_hand(my_cards)} (Value: {my_value})")

                # Check if round is over (server determines bust)
                if payload.result == RESULT_LOSS:
                    print(f"\n{COLOR_RED}💥 BUST! You went over 21!")
                    print(f"{get_random_message('bust')}{COLOR_RESET}")
                    return RESULT_LOSS
                elif payload.result == RESULT_WIN:
                    # Shouldn't happen during player turn, but handle it
                    return RESULT_WIN
                elif payload.result == RESULT_TIE:
                    return RESULT_TIE
                # If RESULT_NOT_OVER, continue the loop

            # ===== DEALER TURN =====
            print(f"\n{'─' * 40}")
            print("🎰 DEALER'S TURN")
            print(f"{'─' * 40}")

            # Receive dealer's hidden card
            payload = conn.receive_server_payload()
            if payload is None:
                return RESULT_DISCONNECTED

            dealer_cards.append(Card(payload.card_rank, payload.card_suit))
            dealer_value = calculate_hand_value(dealer_cards)
            print(f"🎴 Dealer reveals: {format_hand(dealer_cards)} (Value: {dealer_value})")

            # Receive additional dealer cards until result
            while payload.result == RESULT_NOT_OVER:
                payload = conn.receive_server_payload()
                if payload is None:
                    return RESULT_DISCONNECTED

                if payload.card_rank > 0:
                    new_card = Card(payload.card_rank, payload.card_suit)
                    dealer_cards.append(new_card)
                    dealer_value = calculate_hand_value(dealer_cards)
                    print(f"🎴 Dealer draws: {new_card.name}")
                    print(f"🎴 Dealer's hand: {format_hand(dealer_cards)} (Value: {dealer_value})")

            # ===== RESULT =====
            result = payload.result
            my_value = calculate_hand_value(my_cards)
            dealer_value = calculate_hand_value(dealer_cards)

            print(f"\n{'─' * 40}")
            print(f"📊 FINAL: You = {my_value} | Dealer = {dealer_value}")

            # Display result with mode-specific effects
            if self.mode == MODE_PARTY:
                # Party mode - extra crazy celebration/commiseration
                if result == RESULT_WIN:
                    print(f"\n{COLOR_MAGENTA}{'🎉' * 10}{COLOR_RESET}")
                    print(f"{COLOR_MAGENTA}{get_party_message('win')}{COLOR_RESET}")
                    print(f"{COLOR_MAGENTA}{'🎊' * 10}{COLOR_RESET}")
                elif result == RESULT_LOSS:
                    print(f"\n{COLOR_MAGENTA}{get_party_message('lose')}{COLOR_RESET}")
                else:
                    print(f"\n{COLOR_MAGENTA}🍺 *hic* It's a tie... another round? 🍻{COLOR_RESET}")
            else:
                # Normal/Auto
                if result == RESULT_WIN:
                    if dealer_value > BUST_THRESHOLD:
                        print(f"\n{COLOR_GREEN}🎉 {get_random_message('dealer_bust')}{COLOR_RESET}")
                    else:
                        print(f"\n{COLOR_GREEN}🎉 {get_random_message('win')}{COLOR_RESET}")
                elif result == RESULT_LOSS:
                    print(f"\n{COLOR_RED}😢 {get_random_message('lose')}{COLOR_RESET}")
                else:
                    print(f"\n{COLOR_YELLOW}🤝 {get_random_message('tie')}{COLOR_RESET}")

            return result

        except Exception as e:
            print(f"❌ Error during round: {e}")
            return RESULT_DISCONNECTED

    def _get_decision(self, current_value: int) -> str:
        """
        Get the player's hit/stand decision.
        Handles different modes: normal, auto-play, party

        Args:
            current_value: Current hand value

        Returns:
            "hit" or "stand"
        """
        # === AUTO-PLAY MODE ===
        if self.mode == MODE_AUTO:
            decision = get_auto_decision(current_value, self.dealer_visible_value)
            print(f"\n🤖 Hand value: {current_value} | Dealer shows: {self.dealer_visible_value}")
            time.sleep(0.8)  # Dramatic pause
            if decision == 'hit':
                print(f"🤖 Bot decision: {COLOR_CYAN}HIT{COLOR_RESET} (basic strategy)")
            else:
                print(f"🤖 Bot decision: {COLOR_YELLOW}STAND{COLOR_RESET} (basic strategy)")
            time.sleep(0.5)
            return decision

        # === PARTY MODE ===
        if self.mode == MODE_PARTY:
            print(f"\n{COLOR_MAGENTA}🍺 Your hand value: {drunk_text(str(current_value))}{COLOR_RESET}")
            while True:
                try:
                    prompt = random.choice([
                        "   *hic* [H]it or [S]tand? ",
                        "   🍻 Wanna [H]it or [S]tand? ",
                        "   🎉 [H]ITTTT or [S]TANDDDD? ",
                    ])
                    choice = input(prompt).strip().lower()

                    if choice in ['h', 'hit']:
                        print(f"{COLOR_MAGENTA}{get_party_message('hit')}{COLOR_RESET}")
                        time.sleep(0.3)
                        return 'hit'
                    elif choice in ['s', 'stand']:
                        print(f"{COLOR_MAGENTA}{get_party_message('stand')}{COLOR_RESET}")
                        time.sleep(0.3)
                        return 'stand'
                    else:
                        print(f"{COLOR_MAGENTA}🍺 Whaaaat? Try again... *hic*{COLOR_RESET}")

                except EOFError:
                    return 'stand'

        # === NORMAL MODE ===
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
                # Handle Ctrl+D - default to stand
                return 'stand'

    def _print_final_stats(self):
        """Print lifetime statistics when the client exits."""
        if self.total_rounds > 0:
            win_rate = (self.total_wins / self.total_rounds * 100)
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
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point for the client."""
    team_name = DEFAULT_TEAM_NAME

    # Allow command-line argument for team name
    if len(sys.argv) >= 2:
        team_name = sys.argv[1]

    client = BlackjackClient(team_name=team_name)
    client.start()


if __name__ == "__main__":
    main()