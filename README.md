# 🃏 Blackjack Network Game

A client-server implementation of simplified Blackjack over TCP/UDP, created for the Intro to Computer Networks Hackathon.

## 🎮 Features

- **UDP Server Discovery**: Servers broadcast offers, clients auto-discover
- **TCP Game Sessions**: Full blackjack gameplay over reliable TCP
- **Multi-client Support**: Server handles multiple clients simultaneously
- **Fun Output**: Engaging messages and emoji-rich display
- **Statistics Tracking**: Win rates, round counts, session summaries
- **Robust Error Handling**: Timeouts, invalid input, connection issues

## 📁 File Structure

```
blackjack/
├── variables.py    # All configurable constants (ports, timeouts, messages)
├── protocol.py     # Message encoding/decoding (offer, request, payload)
├── network.py      # Network layer (UDP broadcast, TCP connections)
├── server.py       # The dealer - game logic only
├── client.py       # The player - game logic + user I/O
└── README.md       # This file
```

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      variables.py                           │
│              (constants, ports, timeouts)                   │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┴─────────────────────┐
        ▼                                           ▼
┌───────────────────┐                     ┌───────────────────┐
│   protocol.py     │                     │   network.py      │
│ (encode/decode)   │                     │ (sockets, I/O)    │
└───────────────────┘                     └───────────────────┘
        │                                           │
        └─────────────────────┬─────────────────────┘
                              │
        ┌─────────────────────┴─────────────────────┐
        ▼                                           ▼
┌───────────────────┐                     ┌───────────────────┐
│    server.py      │                     │    client.py      │
│  (dealer logic)   │                     │  (player logic)   │
└───────────────────┘                     └───────────────────┘
```

## 🚀 Quick Start

### Start the Server (Dealer)
```bash
python server.py                          # Default Server name
python server.py "My Awesome Server"        # Custom Server name
python server.py "Server Name" 12345        # Custom Server name and port
```

### Start the Client (Player)
```bash
python client.py                          # Default team name
python client.py "Player One"             # Custom team name
```

## 📡 Protocol Specification

### Offer Message (UDP Broadcast)
| Field | Size | Description |
|-------|------|-------------|
| Magic Cookie | 4 bytes | `0xABCDDCBA` |
| Message Type | 1 byte | `0x02` |
| TCP Port | 2 bytes | Server's TCP port |
| Server Name | 32 bytes | Null-padded name |

### Request Message (TCP)
| Field | Size | Description |
|-------|------|-------------|
| Magic Cookie | 4 bytes | `0xABCDDCBA` |
| Message Type | 1 byte | `0x03` |
| Rounds | 1 byte | Number of rounds (1-255) |
| Client Name | 32 bytes | Null-padded name |

### Payload Message (TCP)

**Client → Server:**
| Field | Size | Description |
|-------|------|-------------|
| Magic Cookie | 4 bytes | `0xABCDDCBA` |
| Message Type | 1 byte | `0x04` |
| Decision | 5 bytes | `"Hit"` or `"Stand"` |

**Server → Client:**
| Field | Size | Description |
|-------|------|-------------|
| Magic Cookie | 4 bytes | `0xABCDDCBA` |
| Message Type | 1 byte | `0x04` |
| Result | 1 byte | 0=ongoing, 1=tie, 2=loss, 3=win |
| Card Rank | 2 bytes | 1-13 (0 if no card) |
| Card Suit | 1 byte | 0-3 (H,D,C,S) |

## 🎲 Game Rules

1. Player receives 2 cards face-up
2. Dealer receives 2 cards (1 hidden)
3. Player can Hit (draw) or Stand (stop)
4. If player > 21: BUST (loss)
5. Dealer reveals and draws until ≥17
6. If dealer > 21: Player wins
7. Higher hand wins; tie if equal

### Card Values
- Number cards (2-10): Face value
- Face cards (J, Q, K): 10 points
- Ace: 11 points (simplified)

## ⚙️ Configuration

Edit `variables.py` to customize:
- Network ports and timeouts
- Team name
- Fun messages
- Game constants

## 🔧 Requirements

- Python 3.x
- No external dependencies (standard library only)

## 📝 Notes

- Server broadcasts offers every 1 second
- Client listens on UDP port 13122 (hardcoded per spec)
- Uses `SO_REUSEPORT` for multiple clients on same machine
- No busy-waiting - uses blocking sockets with timeouts

## 👥 Team

**Itay & Einav** 🧙‍♂️

---

Good luck, and may the cards be ever in your favor! 🎰
