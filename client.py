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

Usage:
    python client.py
    python client.py "Team Name"
"""

import random
import sys
from typing import Optional, List

from variables import (
    DEFAULT_TEAM_NAME,
    SUIT_SYMBOLS, RANKS, CARD_VALUES,
    BUST_THRESHOLD,
    RESULT_NOT_OVER, RESULT_TIE, RESULT_LOSS, RESULT_WIN,
    RESULT_DISCONNECTED,
    MESSAGES
)
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
    
    def start(self):
        """Start the client and begin looking for servers."""
        self.running = True
        
        # Print startup banner
        self._print_banner()
        print(f"🏷️  Playing as: {self.team_name}")
        print("=" * 60)
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
                    print("⏰ No server found. Retrying...")
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
        
        Returns:
            Number of rounds to play (1-255)
        """
        while True:
            try:
                print()
                user_input = input("🎲 How many rounds would you like to play? (1-255): ").strip()
                
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
            
            # Display initial hands
            my_value = calculate_hand_value(my_cards)
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
                    print(f"\n💥 BUST! You went over 21!")
                    print(get_random_message('bust'))
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
            
            if result == RESULT_WIN:
                if dealer_value > BUST_THRESHOLD:
                    print(f"\n🎉 {get_random_message('dealer_bust')}")
                else:
                    print(f"\n🎉 {get_random_message('win')}")
            elif result == RESULT_LOSS:
                print(f"\n😢 {get_random_message('lose')}")
            else:
                print(f"\n🤝 {get_random_message('tie')}")
            
            return result
            
        except Exception as e:
            print(f"❌ Error during round: {e}")
            return RESULT_DISCONNECTED
    
    def _get_decision(self, current_value: int) -> str:
        """
        Get the player's hit/stand decision.
        
        Args:
            current_value: Current hand value
            
        Returns:
            "hit" or "stand"
        """
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
