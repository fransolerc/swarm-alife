# =============================================================================
# agent/navigation.py — Pathfinding and grid movement
# =============================================================================

import heapq
import random
from typing import Optional, TYPE_CHECKING

from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, TOOLBAR_HEIGHT,
    CREATURE_SPEED, WANDER_INTERVAL, GRID_CELL,
)

if TYPE_CHECKING:
    from agent.creature import Creature

_AREA_W = WINDOW_WIDTH
_AREA_H = WINDOW_HEIGHT - TOOLBAR_HEIGHT
_MAX_COL = _AREA_W // GRID_CELL - 1
_MAX_ROW = _AREA_H // GRID_CELL - 1

_DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def cell_center(col: int, row: int) -> tuple[float, float]:
    return col * GRID_CELL + GRID_CELL / 2, row * GRID_CELL + GRID_CELL / 2


def cell_valid(col: int, row: int, world) -> bool:
    if col < 0 or col > _MAX_COL or row < 0 or row > _MAX_ROW:
        return False
    if world is not None and world.is_blocked(col, row):
        return False
    return True


class Navigator:
    """Handles A* pathfinding and grid-based movement."""

    def __init__(self, creature: "Creature"):
        self._creature = creature
        self._target_col: int = creature.grid_col
        self._target_row: int = creature.grid_row
        self._move_progress: float = 1.0
        self._src_x: float = creature.x
        self._src_y: float = creature.y
        self._path: list[tuple[int, int]] = []
        self._path_goal: Optional[tuple[int, int]] = None
        self._wander_timer: float = 0.0
        self._wander_interval: float = random.uniform(*WANDER_INTERVAL)
        self.speed_real: float = 0.0

    @property
    def target_cell(self) -> tuple[int, int]:
        return self._target_col, self._target_row

    @property
    def has_path(self) -> bool:
        return bool(self._path)

    def clear_path(self) -> None:
        self._path = []
        self._path_goal = None

    def astar(self, world, goal_col: int, goal_row: int) -> list[tuple[int, int]]:
        """A* pathfinding to goal cell."""
        start = (self._creature.grid_col, self._creature.grid_row)
        goal = (goal_col, goal_row)

        if start == goal:
            return []

        is_terminal = self._create_terminal_checker(goal, world)
        heuristic = self._create_heuristic(goal)

        return self._astar_search(start, is_terminal, heuristic, world)

    @staticmethod
    def _create_terminal_checker(goal: tuple[int, int], world):
        """Create terminal condition checker for A*."""
        goal_col, goal_row = goal
        goal_blocked = world is not None and not cell_valid(goal_col, goal_row, world)

        def is_terminal(col: int, row: int) -> bool:
            if (col, row) == goal:
                return True
            if goal_blocked:
                return abs(col - goal_col) + abs(row - goal_row) == 1
            return False

        return is_terminal

    @staticmethod
    def _create_heuristic(goal: tuple[int, int]):
        """Create heuristic function for A*."""
        goal_col, goal_row = goal
        return lambda col, row: abs(col - goal_col) + abs(row - goal_row)

    def _astar_search(
        self,
        start: tuple[int, int],
        is_terminal,
        heuristic,
        world
    ) -> list[tuple[int, int]]:
        """Execute A* search algorithm."""
        open_set: list = [(heuristic(*start), 0, start[0], start[1])]
        came_from: dict = {}
        g_score: dict = {start: 0}

        while open_set:
            _, g, col, row = heapq.heappop(open_set)

            if is_terminal(col, row):
                return self._reconstruct_path((col, row), came_from)

            self._explore_neighbors(col, row, g, came_from, g_score, open_set, heuristic, world)

        return []

    @staticmethod
    def _explore_neighbors(
        col: int,
        row: int,
        g: int,
        came_from: dict,
        g_score: dict,
        open_set: list,
        heuristic,
        world
    ) -> None:
        """Explore all valid neighbors from current cell."""
        for dc, dr in _DIRECTIONS:
            nc, nr = col + dc, row + dr
            neighbor = (nc, nr)

            if not cell_valid(nc, nr, world):
                continue

            new_g = g + 1
            if new_g >= g_score.get(neighbor, 10_000):
                continue

            g_score[neighbor] = new_g
            came_from[neighbor] = (col, row)
            heapq.heappush(open_set, (new_g + heuristic(nc, nr), new_g, nc, nr))

    @staticmethod
    def _reconstruct_path(end: tuple[int, int], came_from: dict) -> list[tuple[int, int]]:
        """Reconstruct path from came_from map."""
        path: list[tuple[int, int]] = []
        cur = end
        while cur in came_from:
            path.append(cur)
            cur = came_from[cur]
        path.reverse()
        return path

    def navigate_to(self, world, tx: float, ty: float) -> None:
        """Set A* navigation to (tx, ty). Only recalculates if goal changed."""
        goal = (int(tx // GRID_CELL), int(ty // GRID_CELL))

        if self._path and not cell_valid(self._path[0][0], self._path[0][1], world):
            self._path = []
            self._path_goal = None

        if self._path_goal != goal or not self._path:
            self._path_goal = goal
            self._path = self.astar(world, goal[0], goal[1])

    def update(self, delta: float, world, is_using_obj: bool) -> None:
        """Update movement along the path."""
        speed = CREATURE_SPEED
        progress_rate = speed / GRID_CELL

        if self._move_progress < 1.0:
            self._move_progress = min(1.0, self._move_progress + progress_rate * delta)
            t = self._move_progress
            dst_x, dst_y = cell_center(self._target_col, self._target_row)
            c = self._creature
            c.x = self._src_x + (dst_x - self._src_x) * t
            c.y = self._src_y + (dst_y - self._src_y) * t
            self.speed_real = speed

            if self._move_progress >= 1.0:
                c.grid_col = self._target_col
                c.grid_row = self._target_row
                c.x, c.y = cell_center(c.grid_col, c.grid_row)
                self.speed_real = 0.0

        if self._move_progress >= 1.0:
            if is_using_obj:
                self.speed_real = 0.0
                return

            self._wander_timer += delta
            nc, nr = self._pick_next_cell(world)
            creature = self._creature
            if nc != creature.grid_col or nr != creature.grid_row:
                self._src_x, self._src_y = creature.x, creature.y
                self._target_col = nc
                self._target_row = nr
                self._move_progress = 0.0
            else:
                self.speed_real = 0.0

    def _pick_next_cell(self, world) -> tuple[int, int]:
        creature = self._creature
        if self._path:
            next_col, next_row = self._path[0]
            if cell_valid(next_col, next_row, world):
                self._path.pop(0)
                return next_col, next_row
            else:
                self._path = []
                self._path_goal = None
                dirs = list(_DIRECTIONS)
                random.shuffle(dirs)
                result = self._try_directions(dirs, world)
                if result is not None:
                    return result

        if self._wander_timer >= self._wander_interval:
            self._wander_timer = 0.0
            self._wander_interval = random.uniform(*WANDER_INTERVAL)
            dirs = list(_DIRECTIONS)
            random.shuffle(dirs)
            result = self._try_directions(dirs, world)
            if result is not None:
                return result

        return creature.grid_col, creature.grid_row

    def _try_directions(self, dirs: list, world) -> Optional[tuple[int, int]]:
        c = self._creature
        for dc, dr in dirs:
            nc, nr = c.grid_col + dc, c.grid_row + dr
            if cell_valid(nc, nr, world):
                return nc, nr
        return None

    def reset_to(self, col: int, row: int) -> None:
        """Reset position to cell center."""
        self._target_col = col
        self._target_row = row
        self._move_progress = 1.0

    def find_empty_neighbor(self) -> tuple[int, int]:
        """Find an empty neighboring cell for spawning."""
        creature = self._creature
        dirs = list(_DIRECTIONS)
        random.shuffle(dirs)
        for dc, dr in dirs:
            nc, nr = creature.grid_col + dc, creature.grid_row + dr
            if 0 <= nc <= _MAX_COL and 0 <= nr <= _MAX_ROW:
                return nc, nr
        return creature.grid_col, creature.grid_row
