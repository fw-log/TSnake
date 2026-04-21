#!/usr/bin/env python3
"""
TSnake - Terminal Snake Game

Usage:
    python snake.py                    # human, medium board, 1 fruit
    python snake.py --mode bot         # single AI snake, auto-restarts
    python snake.py --size large       # larger board
    python snake.py --fruits 5         # more fruits
    python snake.py --ss               # fullscreen screensaver: 5 snakes, 25 fruits

Standalone install (optional):
    chmod +x snake.py
    sudo cp snake.py /usr/local/bin/tsnake

Controls (human mode):
    Arrow keys / WASD  — move
    Q                  — quit
"""

import curses
import random
import argparse
from collections import deque

# ── Board configurations ───────────────────────────────────────────────────────

BOARD_SIZES = {
    "small":  (22, 10),
    "medium": (42, 20),
    "large":  (62, 30),
}

TICK_MS = {
    "human": 120,
    "bot":    40,
    "ss":     45,
}

# ── Directions ─────────────────────────────────────────────────────────────────

UP    = ( 0, -1)
DOWN  = ( 0,  1)
LEFT  = (-1,  0)
RIGHT = ( 1,  0)
ALL_DIRS = [UP, DOWN, LEFT, RIGHT]
OPPOSITE = {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}

# Direction-indicating head glyphs
HEAD_GLYPH = {UP: "▲", DOWN: "▼", LEFT: "◀", RIGHT: "▶"}

# ── Color pair IDs ─────────────────────────────────────────────────────────────

C_BORDER   = 1
C_BODY     = 2
C_HEAD     = 3
C_FRUIT    = 4
C_STATUS   = 5
C_GAMEOVER = 6
C_DIM      = 7
# Pairs 10–14: per-snake colors in screensaver mode
C_SS_BASE  = 10

# Colors assigned to each of the 5 screensaver snakes
SS_SNAKE_COLORS = [
    curses.COLOR_GREEN,
    curses.COLOR_CYAN,
    curses.COLOR_YELLOW,
    curses.COLOR_MAGENTA,
    curses.COLOR_WHITE,
]

# ── Snake ──────────────────────────────────────────────────────────────────────

class Snake:
    def __init__(self, x, y):
        self.body          = deque([(x, y), (x - 1, y), (x - 2, y)])
        self.direction     = RIGHT
        self._pending_grow = False

    @property
    def head(self):
        return self.body[0]

    @property
    def tail(self):
        return self.body[-1]

    def set_dir(self, d):
        if d != OPPOSITE[self.direction]:
            self.direction = d

    def step(self):
        dx, dy = self.direction
        hx, hy = self.head
        self.body.appendleft((hx + dx, hy + dy))
        if self._pending_grow:
            self._pending_grow = False
        else:
            self.body.pop()

    def eat(self):
        self._pending_grow = True

    def body_set(self, skip_tail=False):
        s = set(self.body)
        if skip_tail:
            s.discard(self.body[-1])
        return s

    def hits_self(self):
        h = self.head
        return sum(1 for seg in self.body if seg == h) > 1

# ── Bot AI ─────────────────────────────────────────────────────────────────────

class BotAI:
    def __init__(self, w, h):
        self.w = w
        self.h = h

    def _bfs(self, start, goals, blocked):
        """BFS from start to nearest goal. Returns direction-path or None."""
        if start in goals:
            return []
        q    = deque([(start, [])])
        seen = {start}
        while q:
            pos, path = q.popleft()
            x, y = pos
            for d in ALL_DIRS:
                npos = (x + d[0], y + d[1])
                if (0 <= npos[0] < self.w and 0 <= npos[1] < self.h
                        and npos not in blocked and npos not in seen):
                    seen.add(npos)
                    npath = path + [d]
                    if npos in goals:
                        return npath
                    q.append((npos, npath))
        return None

    def _simulate(self, snake, path, fruit_set):
        """
        Walk the snake along path (eating any fruits hit).
        Returns (final_head, blocked_excluding_tail, final_tail).
        """
        body         = deque(snake.body)
        fruits_left  = set(fruit_set)
        pending_grow = snake._pending_grow

        for d in path:
            dx, dy   = d
            hx, hy   = body[0]
            new_head = (hx + dx, hy + dy)
            body.appendleft(new_head)
            if pending_grow:
                pending_grow = False
            else:
                body.pop()
            if new_head in fruits_left:
                fruits_left.discard(new_head)
                pending_grow = True

        tail    = body[-1]
        blocked = set(body) - {tail}
        return body[0], blocked, tail

    def _head_danger(self, other_snakes):
        """
        Return the set of cells any live other snake's head could occupy next tick.
        Each snake can move in up to 3 directions (all except its own reverse), so
        we conservatively mark all of those cells as dangerous.
        """
        danger = set()
        for other in other_snakes:
            ox, oy = other.head
            for d in ALL_DIRS:
                if d == OPPOSITE[other.direction]:
                    continue  # snake cannot reverse
                nx, ny = ox + d[0], oy + d[1]
                if 0 <= nx < self.w and 0 <= ny < self.h:
                    danger.add((nx, ny))
        return danger

    def choose(self, snake, fruits, other_snakes=None):
        """
        Return the best next direction for snake.

        other_snakes: list of other live Snake objects (used in multi-snake mode).
        Strategy order (each tried with head-danger avoidance first, then without):
          1. Safe path to nearest fruit (BFS + tail-reachability survival check)
          2. Tail-chase to stay in open space
          3. Any immediately non-fatal move
        """
        head      = snake.head
        obstacles = snake.body_set(skip_tail=True)
        danger    = set()

        if other_snakes:
            for other in other_snakes:
                obstacles |= other.body_set()
            danger = self._head_danger(other_snakes)

        fruit_set   = set(fruits)
        safe_obs    = obstacles | danger   # obstacles + predicted head positions

        def _safe_fruit_path(blocked):
            path = self._bfs(head, fruit_set, blocked)
            if path:
                new_head, blocked_after, tail_after = self._simulate(snake, path, fruit_set)
                if self._bfs(new_head, {tail_after}, blocked_after) is not None:
                    return path
            return None

        # Strategy 1: fruit path — try danger-aware first, then without
        for blocked in (safe_obs, obstacles):
            path = _safe_fruit_path(blocked)
            if path:
                return path[0]

        # Strategy 2: tail-chase — try danger-aware first, then without
        for blocked in (safe_obs, obstacles):
            tail_path = self._bfs(head, {snake.tail}, blocked)
            if tail_path:
                return tail_path[0]

        # Strategy 3: any non-suicidal move — prefer cells outside danger zone
        for blocked in (safe_obs, obstacles):
            for d in ALL_DIRS:
                if d == OPPOSITE[snake.direction]:
                    continue
                npos = (head[0] + d[0], head[1] + d[1])
                if (0 <= npos[0] < self.w and 0 <= npos[1] < self.h
                        and npos not in blocked):
                    return d

        return snake.direction  # fully trapped — nothing left to do

# ── Single-Snake Game ──────────────────────────────────────────────────────────

class Game:
    def __init__(self, scr, mode, size, num_fruits):
        self.scr     = scr
        self.mode    = mode
        self.w, self.h = BOARD_SIZES[size]
        self.nfruits = num_fruits
        self.score   = 0

        cx, cy     = self.w // 2, self.h // 2
        self.snake = Snake(cx, cy)
        self.fruits = []
        self._spawn_fruits()

        self.bot = BotAI(self.w, self.h) if mode == "bot" else None
        self.scr.timeout(TICK_MS[mode])

    def _spawn_fruits(self):
        occupied = self.snake.body_set() | set(self.fruits)
        attempts = 0
        while len(self.fruits) < self.nfruits and attempts < 1000:
            attempts += 1
            x, y = random.randint(0, self.w - 1), random.randint(0, self.h - 1)
            if (x, y) not in occupied:
                self.fruits.append((x, y))
                occupied.add((x, y))

    def _handle_key(self, key):
        dir_map = {
            curses.KEY_UP:    UP,    ord("w"): UP,
            curses.KEY_DOWN:  DOWN,  ord("s"): DOWN,
            curses.KEY_LEFT:  LEFT,  ord("a"): LEFT,
            curses.KEY_RIGHT: RIGHT, ord("d"): RIGHT,
        }
        if key in dir_map:
            self.snake.set_dir(dir_map[key])
        elif key in (ord("q"), ord("Q")):
            return "quit"
        return None

    def _update(self):
        if self.bot:
            self.snake.set_dir(self.bot.choose(self.snake, self.fruits))
        self.snake.step()
        hx, hy = self.snake.head
        if not (0 <= hx < self.w and 0 <= hy < self.h):
            return False
        if self.snake.hits_self():
            return False
        if self.snake.head in self.fruits:
            self.fruits.remove(self.snake.head)
            self.snake.eat()
            self.score += 10
            self._spawn_fruits()
        return True

    def _draw(self):
        scr = self.scr
        scr.erase()
        b = curses.color_pair(C_BORDER) | curses.A_BOLD

        scr.addstr(0,          0,          "┌", b)
        scr.addstr(0,          self.w + 1, "┐", b)
        scr.addstr(self.h + 1, 0,          "└", b)
        try:
            scr.addstr(self.h + 1, self.w + 1, "┘", b)
        except curses.error:
            pass
        for x in range(1, self.w + 1):
            scr.addstr(0,          x, "─", b)
            scr.addstr(self.h + 1, x, "─", b)
        for y in range(1, self.h + 1):
            scr.addstr(y, 0,          "│", b)
            scr.addstr(y, self.w + 1, "│", b)

        fa = curses.color_pair(C_FRUIT) | curses.A_BOLD
        for fx, fy in self.fruits:
            scr.addstr(fy + 1, fx + 1, "●", fa)

        ba = curses.color_pair(C_BODY)
        ha = curses.color_pair(C_HEAD) | curses.A_BOLD
        for i, (sx, sy) in enumerate(self.snake.body):
            if i == 0:
                scr.addstr(sy + 1, sx + 1, HEAD_GLYPH[self.snake.direction], ha)
            else:
                scr.addstr(sy + 1, sx + 1, "▓", ba)

        mode_label = "BOT [auto-restart]" if self.mode == "bot" else "HUMAN"
        status = (
            f" Score: {self.score:>5}  │  Length: {len(self.snake.body):>3}  │  "
            f"Mode: {mode_label}  │  Fruits: {self.nfruits}  │  [Q] Quit "
        )
        scr.addstr(self.h + 2, 0, status[:self.w + 2], curses.color_pair(C_STATUS))
        scr.refresh()

    def _game_over(self):
        scr   = self.scr
        mid_y = self.h // 2
        mid_x = max(0, (self.w + 2) // 2 - 10)
        ga    = curses.color_pair(C_GAMEOVER) | curses.A_BOLD
        da    = curses.color_pair(C_DIM)

        for i, ln in enumerate([
            "╔══════════════════╗",
            "║    GAME  OVER    ║",
            f"║  Score: {self.score:<9} ║",
            "╚══════════════════╝",
        ]):
            scr.addstr(mid_y + i, mid_x, ln, ga)

        if self.mode == "bot":
            scr.addstr(mid_y + 4, mid_x, " Restarting in 2s… [Q] quit ", da)
            scr.refresh()
            scr.timeout(2000)
            key = scr.getch()
            scr.timeout(TICK_MS["bot"])
            return key not in (ord("q"), ord("Q"))
        else:
            scr.addstr(mid_y + 4, mid_x, "   [R] Restart   [Q] Quit   ", da)
            scr.refresh()
            scr.timeout(-1)
            while True:
                key = scr.getch()
                if key in (ord("q"), ord("Q")):
                    return False
                if key in (ord("r"), ord("R")):
                    return True

    def run(self):
        """Run one game session. Returns True to restart, False to quit."""
        while True:
            key = self.scr.getch()
            if key != -1 and self._handle_key(key) == "quit":
                return False
            if not self._update():
                return self._game_over()
            self._draw()

# ── Multi-Snake Screensaver (--ss) ─────────────────────────────────────────────

class ScreensaverGame:
    """
    Fills the entire terminal with 5 independently AI-controlled snakes and
    25 fruits. Snakes respawn automatically after death. Runs until Q is pressed.

    Collision rules:
      - Wall / self:        snake dies
      - Head into any part of another snake: only the attacker dies
    """

    NUM_SNAKES    = 5
    NUM_FRUITS    = 25
    RESPAWN_TICKS = 30   # ticks a dead snake waits before respawning

    def __init__(self, scr):
        self.scr = scr
        max_h, max_w = scr.getmaxyx()
        self.w = max_w - 2   # playfield cols (inside left/right border)
        self.h = max_h - 4   # playfield rows (top border + bottom border + status)

        self.snakes = []
        self.timers = []     # timer > 0  →  dead, counting down to respawn
        self.scores = [0] * self.NUM_SNAKES
        self.total  = 0

        # Spread starting positions evenly across the width
        for i in range(self.NUM_SNAKES):
            x = max(3, min(self.w * (i + 1) // (self.NUM_SNAKES + 1), self.w - 4))
            y = self.h // 2
            self.snakes.append(Snake(x, y))
            self.timers.append(0)

        self.fruits = []
        self.bots   = [BotAI(self.w, self.h) for _ in range(self.NUM_SNAKES)]
        self._spawn_fruits()
        scr.timeout(TICK_MS["ss"])

    # ── Helpers ────────────────────────────────────────────────────────────

    def _occupied(self, exclude=None):
        """All cells currently taken by live snakes (optionally excluding one) + fruits."""
        occ = set()
        for i, s in enumerate(self.snakes):
            if i != exclude and self.timers[i] == 0:
                occ |= s.body_set()
        return occ | set(self.fruits)

    def _spawn_fruits(self):
        occ      = self._occupied()
        attempts = 0
        while len(self.fruits) < self.NUM_FRUITS and attempts < 5000:
            attempts += 1
            x, y = random.randint(0, self.w - 1), random.randint(0, self.h - 1)
            if (x, y) not in occ:
                self.fruits.append((x, y))
                occ.add((x, y))

    def _respawn(self, i):
        """Find a safe starting position for snake i and place it there."""
        occ = self._occupied(exclude=i)
        for _ in range(2000):
            x = random.randint(3, self.w - 4)
            y = random.randint(1, self.h - 2)
            cells = {(x, y), (x - 1, y), (x - 2, y)}
            if not cells & occ:
                self.snakes[i] = Snake(x, y)
                return
        self.snakes[i] = Snake(self.w // 2, self.h // 2)  # last-resort fallback

    # ── Update ─────────────────────────────────────────────────────────────

    def _update(self):
        # 1. Tick respawn timers; revive snakes whose timer just reached zero
        for i in range(self.NUM_SNAKES):
            if self.timers[i] > 0:
                self.timers[i] -= 1
                if self.timers[i] == 0:
                    self._respawn(i)

        # 2. Each live bot chooses a direction, aware of all other live snakes
        for i, snake in enumerate(self.snakes):
            if self.timers[i] > 0:
                continue
            others = [self.snakes[j] for j in range(self.NUM_SNAKES)
                      if j != i and self.timers[j] == 0]
            snake.set_dir(self.bots[i].choose(snake, self.fruits, others))

        # 3. Step every live snake and record where its head landed
        new_heads = {}
        for i, snake in enumerate(self.snakes):
            if self.timers[i] > 0:
                continue
            snake.step()
            new_heads[i] = snake.head

        # 4. Detect deaths ─────────────────────────────────────────────────
        to_kill = set()

        for i, head in new_heads.items():
            hx, hy = head
            # Wall
            if not (0 <= hx < self.w and 0 <= hy < self.h):
                to_kill.add(i)
                continue
            # Self-collision
            if self.snakes[i].hits_self():
                to_kill.add(i)
                continue
            # Head touched any part of another snake — only this snake dies
            for j, other in enumerate(self.snakes):
                if j == i or self.timers[j] > 0:
                    continue
                if head in other.body_set():
                    to_kill.add(i)
                    break

        for i in to_kill:
            self.timers[i] = self.RESPAWN_TICKS

        # 5. Fruit eating for snakes that survived this tick
        fruit_set = set(self.fruits)
        for i, head in new_heads.items():
            if i in to_kill:
                continue
            if head in fruit_set:
                self.fruits.remove(head)
                self.snakes[i].eat()
                self.scores[i] += 10
                self.total     += 10
                fruit_set       = set(self.fruits)

        self._spawn_fruits()

    # ── Draw ───────────────────────────────────────────────────────────────

    def _draw(self):
        scr = self.scr
        scr.erase()
        b = curses.color_pair(C_BORDER) | curses.A_BOLD

        # Border
        scr.addstr(0,          0,          "┌", b)
        scr.addstr(0,          self.w + 1, "┐", b)
        scr.addstr(self.h + 1, 0,          "└", b)
        try:
            scr.addstr(self.h + 1, self.w + 1, "┘", b)
        except curses.error:
            pass
        for x in range(1, self.w + 1):
            scr.addstr(0,          x, "─", b)
            scr.addstr(self.h + 1, x, "─", b)
        for y in range(1, self.h + 1):
            scr.addstr(y, 0,          "│", b)
            scr.addstr(y, self.w + 1, "│", b)

        # Fruits
        fa = curses.color_pair(C_FRUIT) | curses.A_BOLD
        for fx, fy in self.fruits:
            scr.addstr(fy + 1, fx + 1, "●", fa)

        # Snakes — each gets its own color pair (C_SS_BASE + i)
        for i, snake in enumerate(self.snakes):
            if self.timers[i] > 0:
                continue
            ca = curses.color_pair(C_SS_BASE + i)
            ha = ca | curses.A_BOLD
            for j, (sx, sy) in enumerate(snake.body):
                glyph = HEAD_GLYPH[snake.direction] if j == 0 else "▓"
                attr  = ha if j == 0 else ca
                scr.addstr(sy + 1, sx + 1, glyph, attr)

        # Status bar: per-snake scores + total
        parts  = "  ".join(f"S{i+1}:{self.scores[i]}" for i in range(self.NUM_SNAKES))
        status = f" {parts}  │  Total: {self.total}  │  [Q] Quit "
        scr.addstr(self.h + 2, 0, status[:self.w + 2], curses.color_pair(C_STATUS))
        scr.refresh()

    # ── Main loop ──────────────────────────────────────────────────────────

    def run(self):
        """Run screensaver indefinitely until Q is pressed."""
        while True:
            key = self.scr.getch()
            if key in (ord("q"), ord("Q")):
                return
            self._update()
            self._draw()

# ── Startup splash ─────────────────────────────────────────────────────────────

def _splash(scr, mode, size, num_fruits, is_ss):
    scr.erase()
    h, w = scr.getmaxyx()

    title = [
        r" _____ ____  _   _       _        ",
        r"|_   _/ ___|| \ | | ___ | | _____ ",
        r"  | | \___ \|  \| |/ _ \| |/ / _ \ ",
        r"  | |  ___) | |\  | (_) |   <  __/",
        r"  |_| |____/|_| \_|\___/|_|\_\___|",
    ]
    start_y = max(0, h // 2 - 7)
    ta = curses.color_pair(C_HEAD) | curses.A_BOLD
    for i, line in enumerate(title):
        col = max(0, (w - len(line)) // 2)
        try:
            scr.addstr(start_y + i, col, line, ta)
        except curses.error:
            pass

    info_y = start_y + len(title) + 1
    if is_ss:
        bw, bh = w - 2, h - 4
        info = [
            "  Mode    : SCREENSAVER  (--ss)",
            f"  Board   : full terminal  ({bw}×{bh})",
            "  Snakes  : 5  (green · cyan · yellow · magenta · white)",
            "  Fruits  : 25",
            "  Rules   : head→body kills attacker · head→head kills both",
            "            dead snakes respawn automatically",
            "",
            "  [Q] to exit at any time",
            "",
            "  Press any key to start…",
        ]
    else:
        bw, bh = BOARD_SIZES[size]
        info = [
            f"  Mode    : {'BOT  (auto-restarts)' if mode == 'bot' else 'HUMAN'}",
            f"  Board   : {size}  ({bw}×{bh})",
            f"  Fruits  : {num_fruits}",
            "",
            "  Controls: Arrow keys / WASD  │  Q = quit",
            "",
            "  Press any key to start…",
        ]

    ia = curses.color_pair(C_STATUS)
    for i, line in enumerate(info):
        col = max(0, (w - 56) // 2)
        try:
            scr.addstr(info_y + i, col, line, ia)
        except curses.error:
            pass

    scr.refresh()
    scr.timeout(-1)
    scr.getch()

# ── Initialization ─────────────────────────────────────────────────────────────

def _init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(C_BORDER,   curses.COLOR_CYAN,    -1)
    curses.init_pair(C_BODY,     curses.COLOR_GREEN,   -1)
    curses.init_pair(C_HEAD,     curses.COLOR_YELLOW,  -1)
    curses.init_pair(C_FRUIT,    curses.COLOR_RED,     -1)
    curses.init_pair(C_STATUS,   curses.COLOR_WHITE,   -1)
    curses.init_pair(C_GAMEOVER, curses.COLOR_MAGENTA, -1)
    curses.init_pair(C_DIM,      curses.COLOR_WHITE,   -1)
    for i, color in enumerate(SS_SNAKE_COLORS):
        curses.init_pair(C_SS_BASE + i, color, -1)


def _run(scr, args):
    curses.curs_set(0)
    _init_colors()
    max_h, max_w = scr.getmaxyx()

    if args.ss:
        min_w, min_h = 30, 14
        if max_h < min_h or max_w < min_w:
            scr.addstr(0, 0,
                f"Terminal too small for --ss! Need {min_w}×{min_h}, "
                f"have {max_w}×{max_h}.",
                curses.color_pair(C_GAMEOVER) | curses.A_BOLD)
            scr.getch()
            return
        _splash(scr, None, None, None, is_ss=True)
        ScreensaverGame(scr).run()
        return

    bw, bh   = BOARD_SIZES[args.size]
    need_w, need_h = bw + 2, bh + 4
    if max_h < need_h or max_w < need_w:
        scr.addstr(0, 0,
            f"Terminal too small! Need {need_w}×{need_h}, "
            f"have {max_w}×{max_h}. Resize and retry.",
            curses.color_pair(C_GAMEOVER) | curses.A_BOLD)
        scr.getch()
        return

    _splash(scr, args.mode, args.size, args.fruits, is_ss=False)
    while True:
        game = Game(scr, args.mode, args.size, args.fruits)
        if not game.run():
            break

# ── CLI ────────────────────────────────────────────────────────────────────────

def _parse_args():
    p = argparse.ArgumentParser(
        description="TSnake – Terminal Snake  (human · bot · screensaver)",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Standalone install:\n"
            "  chmod +x snake.py\n"
            "  sudo cp snake.py /usr/local/bin/tsnake\n"
            "  tsnake --ss"
        ),
    )
    p.add_argument(
        "--ss", action="store_true",
        help=(
            "Screensaver mode: fills the entire terminal with 5 simultaneous\n"
            "AI-controlled snakes competing for 25 fruits. Snakes respawn\n"
            "on death. Runs indefinitely until [Q] is pressed.\n"
            "Overrides --mode / --size / --fruits."
        ),
    )
    p.add_argument(
        "--mode", choices=["human", "bot"], default="human",
        help=(
            "Game mode:\n"
            "  human  — keyboard-controlled\n"
            "  bot    — single AI snake, auto-restarts on death\n"
            "(default: human)"
        ),
    )
    p.add_argument(
        "--size", choices=["small", "medium", "large"], default="medium",
        help=(
            "Board size:\n"
            "  small  — 22×10\n"
            "  medium — 42×20\n"
            "  large  — 62×30\n"
            "(default: medium)"
        ),
    )
    p.add_argument(
        "--fruits", type=int, choices=[1, 3, 5], default=1,
        help="Number of fruits on the board at once: 1, 3, or 5  (default: 1)",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    curses.wrapper(_run, args)
