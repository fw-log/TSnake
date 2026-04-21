# 🐍 TSnake

```
 _____ ____  _   _       _
|_   _/ ___|| \ | | ___ | | _____
  | | \___ \|  \| |/ _ \| |/ / _ \
  | |  ___) | |\  | (_) |   <  __/
  |_| |____/|_| \_|\___/|_|\_\___|
```

> A terminal snake game with human, bot, and fullscreen screensaver modes.  
> Zero dependencies — pure Python stdlib.

---

## Features

- **Human mode** — classic snake with arrow keys or WASD
- **Bot mode** — single AI snake with BFS pathfinding + tail-chase survival; auto-restarts on death
- **Screensaver mode (`--ss`)** — 5 color-coded AI snakes competing across your entire terminal with 25 fruits, head-danger lookahead to avoid collisions, and automatic respawning
- Configurable board size (`small` / `medium` / `large`) and fruit count (`1` / `3` / `5`)
- Smooth Unicode rendering with box-drawing borders and directional snake heads (▲ ▶ ▼ ◀)

---

## Requirements

- Python 3.6+
- A terminal with UTF-8 support and color (virtually any modern terminal emulator)

No third-party packages required.

---

## Install

### Run directly

```bash
git clone https://github.com/yourusername/TSnake.git
cd TSnake
python snake.py
```

### Make it a system command

```bash
chmod +x snake.py
sudo cp snake.py /usr/local/bin/tsnake
```

Then from anywhere:

```bash
tsnake
tsnake --ss
```

---

## Usage

```
usage: snake.py [--ss] [--mode {human,bot}] [--size {small,medium,large}] [--fruits {1,3,5}]
```

### Modes

| Flag | Description |
|------|-------------|
| *(none)* | Human-controlled snake, medium board, 1 fruit |
| `--mode bot` | Single AI snake that auto-restarts on death |
| `--ss` | **Screensaver** — 5 AI snakes, 25 fruits, full terminal. Overrides all other flags. |

### Options

| Flag | Values | Default | Description |
|------|--------|---------|-------------|
| `--size` | `small` `medium` `large` | `medium` | Board size (22×10 / 42×20 / 62×30) |
| `--fruits` | `1` `3` `5` | `1` | Number of fruits on the board at once |

### Examples

```bash
# Play yourself on a large board with 5 fruits
python snake.py --size large --fruits 5

# Watch the bot play on a small board
python snake.py --mode bot --size small

# Screensaver — just let it run
python snake.py --ss
```

---

## Controls

| Key | Action |
|-----|--------|
| `↑ ↓ ← →` or `W A S D` | Move (human mode) |
| `R` | Restart after game over |
| `Q` | Quit |

---

## How the AI works

The bot uses a **three-strategy cascade**:

1. **Safe fruit path** — BFS to the nearest fruit; before committing, simulates the full path and verifies the snake can still reach its own tail afterwards (prevents self-trapping)
2. **Tail chase** — if no safe fruit path exists, follow the tail to stay in open space
3. **Any safe move** — last resort: any direction that doesn't immediately cause death

In screensaver mode each bot also computes a **head-danger zone** — every cell any other snake's head could occupy next tick — and routes around it with soft avoidance (falls back to ignoring danger only if no safe path exists).

---

## License

MIT — do whatever you want with it.
